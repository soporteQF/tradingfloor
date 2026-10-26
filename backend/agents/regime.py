"""REGIME AGENT — detección de régimen de mercado (HMM 4 estados).

Estados:
- 0: trend_up      (media móvil ascendente, volatilidad normal)
- 1: trend_down    (media móvil descendente, volatilidad normal)
- 2: range_low_vol (precio lateral, volatilidad baja)
- 3: range_high_vol (precio lateral, volatilidad alta)

Fuente de datos: yfinance 5m (gratis, 60 días historial) o datos locales (Parquet/DuckDB).
Emite eventos RegimeChange al EventBus para que Research/Execution/Guardian reaccionen.

CPU-only: hmmlearn (scikit-learn compatible), sin GPU.
"""

from __future__ import annotations

import logging
import pickle
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from agents.base import Agent
from orchestration.event_bus import EventBus, STREAMS

log = logging.getLogger(__name__)


class Regime(str, Enum):
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    RANGE_LOW_VOL = "range_low_vol"
    RANGE_HIGH_VOL = "range_high_vol"


@dataclass
class RegimeState:
    """Estado actual del régimen para un símbolo."""
    symbol: str
    regime: Regime
    confidence: float
    timestamp: datetime
    features: dict = field(default_factory=dict)  # features usadas para decisión
    model_version: str = "1.0"


@dataclass
class RegimeConfig:
    """Configuración del detector de régimen."""
    symbols: list[str] = field(default_factory=lambda: ["NQ", "ES", "YM", "GC"])
    timeframe: str = "5m"
    lookback_bars: int = 200  # barras para entrenar/inferir
    retrain_interval_hours: int = 24
    min_confidence: float = 0.6
    # HMM params
    n_states: int = 4
    n_iter: int = 100
    covariance_type: str = "diag"
    # Features
    use_returns: bool = True
    use_volatility: bool = True
    use_trend: bool = True
    use_volume: bool = False
    # Persistence
    model_dir: str = "./models/regime"


class RegimeAgent(Agent):
    name = "regime"
    role = "Detecta régimen de mercado (HMM 4 estados) y emite alertas de cambio."

    def __init__(
        self,
        config: Optional[RegimeConfig] = None,
        kg=None,
        event_bus: Optional[EventBus] = None,
        data_provider=None,  # callable(symbol, tf, lookback) -> DataFrame
    ):
        super().__init__(kg=kg)
        self.config = config or RegimeConfig()
        self.event_bus = event_bus or EventBus(enabled=False)
        self.data_provider = data_provider

        # Estado por símbolo
        self._regime_state: dict[str, RegimeState] = {}
        self._models: dict[str, object] = {}  # hmmlearn models
        self._scalers: dict[str, object] = {}  # sklearn scalers
        self._lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_retrain: dict[str, datetime] = {}

        # Crear directorio de modelos
        Path(self.config.model_dir).mkdir(parents=True, exist_ok=True)

    # ── Lifecycle ─────────────────────────────────────────────
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        log.info("RegimeAgent INICIADO: %s %s", self.config.symbols, self.config.timeframe)

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        log.info("RegimeAgent DETENIDO")

    # ── API Pública ───────────────────────────────────────────
    def get_regime(self, symbol: str) -> Optional[RegimeState]:
        """Estado actual del régimen para un símbolo."""
        with self._lock:
            return self._regime_state.get(symbol)

    def get_all_regimes(self) -> dict[str, RegimeState]:
        with self._lock:
            return self._regime_state.copy()

    def is_trend(self, symbol: str) -> bool:
        state = self.get_regime(symbol)
        return state is not None and state.regime in (Regime.TREND_UP, Regime.TREND_DOWN)

    def is_range(self, symbol: str) -> bool:
        state = self.get_regime(symbol)
        return state is not None and state.regime in (Regime.RANGE_LOW_VOL, Regime.RANGE_HIGH_VOL)

    def force_retrain(self, symbol: str) -> bool:
        """Fuerza reentrenamiento inmediato para un símbolo."""
        return self._train_symbol(symbol)

    # ── Loop Principal ────────────────────────────────────────
    def _run_loop(self) -> None:
        while self._running:
            try:
                for symbol in self.config.symbols:
                    self._update_symbol(symbol)
            except Exception as e:
                log.error("Error en RegimeAgent loop: %s", e)

            # Sleep hasta siguiente ciclo (1 min para 5m data)
            for _ in range(60):
                if not self._running:
                    break
                time.sleep(1)

    def _update_symbol(self, symbol: str) -> None:
        # Verificar si necesita reentrenar
        now = datetime.now(timezone.utc)
        last = self._last_retrain.get(symbol)
        if last is None or (now - last) > timedelta(hours=self.config.retrain_interval_hours):
            self._train_symbol(symbol)

        # Inferir régimen actual
        self._infer_regime(symbol)

    # ── Data & Features ───────────────────────────────────────
    def _fetch_data(self, symbol: str, lookback: int) -> Optional[pd.DataFrame]:
        """Obtiene datos para features. Prioriza data_provider, fallback yfinance."""
        if self.data_provider:
            try:
                df = self.data_provider(symbol, self.config.timeframe, lookback)
                if df is not None and len(df) > 0:
                    return df
            except Exception as e:
                log.warning("Data provider falló para %s: %s", symbol, e)

        # Fallback: yfinance (gratis, 5m max 60 días)
        try:
            import yfinance as yf
            ticker_map = {"NQ": "NQ=F", "ES": "ES=F", "YM": "YM=F", "GC": "GC=F"}
            ticker = ticker_map.get(symbol, f"{symbol}=F")
            df = yf.download(ticker, period="60d", interval="5m", progress=False, threads=False)
            if df is not None and len(df) > 0:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                # Normalizar nombres de columnas a lowercase
                df.columns = [c.lower() for c in df.columns]
                df = df.reset_index()
                ts_col = next(c for c in ("datetime", "date", "index") if c in df.columns)
                df = df.rename(columns={ts_col: "ts"})
                df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_convert("America/New_York")
                df = df.set_index("ts").sort_index()
                return df.tail(lookback)
        except Exception as e:
            log.warning("yfinance falló para %s: %s", symbol, e)

        return None

    def _compute_features(self, df: pd.DataFrame) -> np.ndarray:
        """Computa features para HMM: returns, volatility, trend, volume."""
        close = df["close"].values
        high = df["high"].values
        low = df["low"].values
        volume = df["volume"].values if "volume" in df.columns else np.ones(len(close))

        features = []

        # Returns (log)
        if self.config.use_returns:
            ret = np.diff(np.log(close))
            ret = np.concatenate([[0], ret])  # same length
            features.append(ret)

        # Volatility (rolling std of returns)
        if self.config.use_volatility:
            ret = np.diff(np.log(close))
            ret = np.concatenate([[0], ret])
            vol = pd.Series(ret).rolling(20, min_periods=1).std().values
            features.append(vol)

        # Trend (EMA slope)
        if self.config.use_trend:
            ema_fast = pd.Series(close).ewm(span=9).mean().values
            ema_slow = pd.Series(close).ewm(span=21).mean().values
            trend = (ema_fast - ema_slow) / ema_slow
            features.append(trend)

        # Volume (relative)
        if self.config.use_volume:
            vol_ma = pd.Series(volume).rolling(20, min_periods=1).mean().values
            rel_vol = volume / (vol_ma + 1e-9)
            features.append(rel_vol)

        if not features:
            # Fallback: solo returns
            ret = np.diff(np.log(close))
            ret = np.concatenate([[0], ret])
            features.append(ret)

        X = np.column_stack(features)
        # Replace NaN/inf
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        return X

    # ── HMM Training ──────────────────────────────────────────
    def _train_symbol(self, symbol: str) -> bool:
        """Entrena HMM para un símbolo."""
        try:
            from hmmlearn import hmm
            from sklearn.preprocessing import StandardScaler
        except ImportError:
            log.error("hmmlearn no instalado. pip install hmmlearn")
            return False

        df = self._fetch_data(symbol, self.config.lookback_bars)
        if df is None or len(df) < 50:
            log.warning("Datos insuficientes para %s: %d barras", symbol, len(df) if df is not None else 0)
            return False

        X = self._compute_features(df)

        # Scaler
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # HMM
        model = hmm.GaussianHMM(
            n_components=self.config.n_states,
            covariance_type=self.config.covariance_type,
            n_iter=self.config.n_iter,
            random_state=42,
        )

        try:
            model.fit(X_scaled)
        except Exception as e:
            log.error("HMM fit falló para %s: %s", symbol, e)
            return False

        # Guardar
        with self._lock:
            self._models[symbol] = model
            self._scalers[symbol] = scaler
            self._last_retrain[symbol] = datetime.now(timezone.utc)

            # Persistir a disco
            model_path = Path(self.config.model_dir) / f"{symbol}_hmm.pkl"
            with open(model_path, "wb") as f:
                pickle.dump({"model": model, "scaler": scaler}, f)

        log.info("RegimeAgent: HMM entrenado para %s (%d barras, %d features)", symbol, len(df), X.shape[1])
        return True

    def _load_model(self, symbol: str) -> bool:
        """Carga modelo persistido."""
        model_path = Path(self.config.model_dir) / f"{symbol}_hmm.pkl"
        if not model_path.exists():
            return False
        try:
            with open(model_path, "rb") as f:
                data = pickle.load(f)
            self._models[symbol] = data["model"]
            self._scalers[symbol] = data["scaler"]
            return True
        except Exception as e:
            log.warning("No se pudo cargar modelo %s: %s", symbol, e)
            return False

    # ── Inference ─────────────────────────────────────────────
    def _infer_regime(self, symbol: str) -> Optional[RegimeState]:
        """Infiere régimen actual usando modelo entrenado."""
        if symbol not in self._models:
            if not self._load_model(symbol):
                if not self._train_symbol(symbol):
                    return None

        df = self._fetch_data(symbol, 100)  # últimas 100 barras para inferir
        if df is None or len(df) < 20:
            return None

        X = self._compute_features(df)
        scaler = self._scalers[symbol]
        model = self._models[symbol]

        X_scaled = scaler.transform(X)

        # Predict (última barra)
        try:
            # hmmlearn predict devuelve estado para cada muestra
            states = model.predict(X_scaled)
            current_state = int(states[-1])

            # Probabilidades (para confidence)
            log_probs = model.score_samples(X_scaled[-1:].reshape(1, -1))
            # Confidence aproximada: diferencia entre top 2 probs
            # hmmlearn no expone predict_proba fácilmente, usamos score
            confidence = min(0.95, max(0.5, 0.6 + np.random.normal(0, 0.1)))  # placeholder
        except Exception as e:
            log.warning("Inferencia falló para %s: %s", symbol, e)
            return None

        # Mapear estado HMM (0-3) a Regime semántico
        # Necesita calibración: analizar media/varianza de cada estado
        regime = self._map_state_to_regime(symbol, current_state, X_scaled[-1], model)

        # Detectar cambio
        prev = self._regime_state.get(symbol)
        if prev and prev.regime != regime:
            self._emit_regime_change(symbol, prev.regime, regime, confidence)

        state = RegimeState(
            symbol=symbol,
            regime=regime,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc),
            features={
                "hmm_state": current_state,
                "returns": float(X[-1, 0]) if X.shape[1] > 0 else 0,
                "volatility": float(X[-1, 1]) if X.shape[1] > 1 else 0,
                "trend": float(X[-1, 2]) if X.shape[1] > 2 else 0,
            },
        )

        with self._lock:
            self._regime_state[symbol] = state

        return state

    def _map_state_to_regime(self, symbol: str, state: int, features: np.ndarray, model) -> Regime:
        """Mapea estado HMM numérico a régimen semántico.

        Estrategia: analizar medias de returns y volatility por estado
        en el training set para etiquetar automáticamente.
        """
        # Para v0: heurística simple basada en features actuales
        # En producción: calcular centroids por estado al entrenar
        ret = features[0] if len(features) > 0 else 0
        vol = features[1] if len(features) > 1 else 0
        trend = features[2] if len(features) > 2 else 0

        # Umbrales heurísticos (calibrar con datos reales)
        vol_threshold = 0.01  # ~1% vol 5m
        trend_threshold = 0.001

        if trend > trend_threshold and vol < vol_threshold * 2:
            return Regime.TREND_UP
        elif trend < -trend_threshold and vol < vol_threshold * 2:
            return Regime.TREND_DOWN
        elif vol > vol_threshold:
            return Regime.RANGE_HIGH_VOL
        else:
            return Regime.RANGE_LOW_VOL

    # ── Event Emission ────────────────────────────────────────
    def _emit_regime_change(self, symbol: str, old: Regime, new: Regime, confidence: float) -> None:
        """Emite evento RegimeChange al EventBus."""
        event = {
            "type": "regime_change",
            "symbol": symbol,
            "old_regime": old.value,
            "new_regime": new.value,
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.event_bus.publish("coordination", event)
        log.info("🔄 REGIME CHANGE: %s %s → %s (conf=%.2f)", symbol, old.value, new.value, confidence)

        # Log a KG si disponible
        if self.kg:
            try:
                from contracts import InsightNode
                ins = InsightNode(
                    kind="regime_change",
                    description=f"{symbol}: {old.value} → {new.value} (conf={confidence:.2f})",
                    symbol=symbol,
                    confidence=confidence,
                    source_agent=self.name,
                )
                self.kg.write_insight(ins)
            except Exception:
                pass


# ── Helper para uso standalone / testing ──────────────────────
def create_regime_agent(
    symbols: list[str] = None,
    timeframe: str = "5m",
    model_dir: str = "./models/regime",
) -> RegimeAgent:
    """Factory para crear RegimeAgent configurado."""
    config = RegimeConfig(
        symbols=symbols or ["NQ", "ES", "YM", "GC"],
        timeframe=timeframe,
        model_dir=model_dir,
    )
    return RegimeAgent(config=config)


if __name__ == "__main__":
    # Test rápido
    logging.basicConfig(level=logging.INFO)
    agent = create_regime_agent(symbols=["NQ"])
    agent.start()
    time.sleep(10)
    for s in ["NQ"]:
        state = agent.get_regime(s)
        print(f"{s}: {state.regime if state else 'N/A'} conf={state.confidence if state else 0}")
    agent.stop()