"""Event bus sobre Redis Streams.

Por qué Streams y no pub/sub: persistencia, replay y consumer groups.
Si Redis no está disponible, el bus degrada a no-op (el loop sigue vivo).
Incluye suscripción local en memoria para testing y modo no-Redis.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable

log = logging.getLogger(__name__)

STREAMS = {
    "discovery": "nexus:discovery",
    "validation": "nexus:validation",
    "deployment": "nexus:deployment",
    "coordination": "nexus:coordination",
    "knowledge": "nexus:knowledge",
    "risk": "nexus:risk",
}


class EventBus:
    def __init__(self, redis_url: str | None = None, enabled: bool = True):
        self.enabled = enabled
        self.url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self._r = None
        # Local in-memory pub/sub for testing/no-Redis mode
        self._local_subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._local_lock = threading.Lock()
        
        if enabled:
            try:
                import redis  # import local para permitir modo no-op

                self._r = redis.Redis.from_url(self.url, decode_responses=True,
                                               socket_connect_timeout=2)
                self._r.ping()
                log.info("EventBus conectado a %s", self.url)
            except Exception as exc:  # noqa: BLE001
                log.warning("EventBus deshabilitado (Redis no disponible: %s)", exc)
                self._r = None
                self.enabled = False

    def publish(self, stream: str, payload: dict) -> str | None:
        if not self.enabled or self._r is None:
            return None
        key = STREAMS.get(stream, stream)
        body = {
            "ts": datetime.now(timezone.utc).isoformat(),
            **{k: (json.dumps(v, default=str) if isinstance(v, (dict, list)) else str(v))
               for k, v in payload.items()},
        }
        return self._r.xadd(key, body, maxlen=10_000, approximate=True)

    def ensure_group(self, stream: str, group: str) -> None:
        if not self.enabled or self._r is None:
            return
        key = STREAMS.get(stream, stream)
        try:
            self._r.xgroup_create(key, group, id="0", mkstream=True)
        except Exception:  # BUSYGROUP
            pass

    def read(self, stream: str, group: str, consumer: str,
             count: int = 20, block_ms: int = 5000) -> list[dict]:
        if not self.enabled or self._r is None:
            return []
        key = STREAMS.get(stream, stream)
        self.ensure_group(stream, group)
        resp = self._r.xreadgroup(group, consumer, {key: ">"}, count=count, block=block_ms)
        out: list[dict] = []
        for _, entries in resp or []:
            for entry_id, data in entries:
                out.append({"id": entry_id, **data})
        return out

    def ack(self, stream: str, group: str, entry_id: str) -> None:
        if not self.enabled or self._r is None:
            return
        self._r.xack(STREAMS.get(stream, stream), group, entry_id)

    def close(self) -> None:
        if self._r is not None:
            try:
                self._r.close()
            except Exception:  # noqa: BLE001
                pass

    # ── Local pub/sub (para testing y modo no-Redis) ──────────
    def subscribe(self, stream: str, callback: Callable[[dict], None]) -> None:
        """Suscribe callback a stream local. Funciona sin Redis."""
        with self._local_lock:
            self._local_subscribers[stream].append(callback)

    def publish_local(self, stream: str, payload: dict) -> None:
        """Publica a suscriptores locales. Funciona sin Redis."""
        with self._local_lock:
            for cb in self._local_subscribers.get(stream, []):
                try:
                    cb(payload)
                except Exception as e:
                    log.warning("Local subscriber error on %s: %s", stream, e)

    # Override publish para que también publique localmente
    def publish(self, stream: str, payload: dict) -> str | None:
        # Publicar localmente siempre
        self.publish_local(stream, payload)
        # Publicar a Redis si disponible
        if not self.enabled or self._r is None:
            return None
        key = STREAMS.get(stream, stream)
        body = {
            "ts": datetime.now(timezone.utc).isoformat(),
            **{k: (json.dumps(v, default=str) if isinstance(v, (dict, list)) else str(v))
               for k, v in payload.items()},
        }
        return self._r.xadd(key, body, maxlen=10_000, approximate=True)
