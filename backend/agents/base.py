"""Base común de agentes. Un agente = rol + tools + contrato de salida."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class Agent:
    name: str = "agent"
    role: str = ""

    def __init__(self, kg=None):
        self.kg = kg
        self.memory: list[dict] = []

    def _remember(self, item: dict) -> None:
        self.memory.append(item)
        if len(self.memory) > 500:
            self.memory = self.memory[-500:]

    def log(self, msg: str, *args) -> None:
        log.info("[%s] " + msg, self.name, *args)
