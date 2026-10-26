"""Tests del Regime Agent."""

from __future__ import annotations

import pytest
import numpy as np
import pandas as pd

from agents.regime import RegimeAgent, RegimeConfig, Regime, create_regime_agent


def make_sample_data(n: int = 500, regime: str = "trend_up") -> pd.DataFrame:
    """Genera datos sintéticos con régimen conocido."""
    np.random.seed(42)
    if regime == "trend_up":
        drift = 0.0005
        vol = 0.001
    elif regime == "trend_down":
        drift = -0.0005
        vol = 0.001
    elif regime == "range_low_vol":
        drift = 0.0
        vol = 0.0005
    elif regime == "range_high_vol":
        drift = 0.0
        vol = 0.003
    else:
        drift = 0.0
        vol = 0.001

    rets = np.random.normal(drift, vol, n)
    close = 20000 * np.exp(np.cumsum(rets))
    high = close * (1 + np.abs(np.random.normal(0, 0.0005, n)))
    low = close * (1 - np.abs(np.random.normal(0, 0.0005, n)))
    open_ = np.concatenate([[close[0]], close[:-1]])
    volume = np.random.randint(100, 1000, n)

    idx = pd.date_range("2024-01-01", periods=n, freq="5min", tz="America/New_York")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def test_regime_agent_creation():
    """Agent se crea correctamente."""
    config = RegimeConfig(symbols=["NQ"], timeframe="5m")
    agent = RegimeAgent(config=config)
    assert agent.name == "regime"
    assert agent.config.symbols == ["NQ"]


def test_regime_agent_factory():
    """Factory function works."""
    agent = create_regime_agent(symbols=["NQ", "ES"], timeframe="5m")
    assert agent.config.symbols == ["NQ", "ES"]


def test_feature_computation():
    """Features se computan sin NaN/inf."""
    agent = create_regime_agent(symbols=["NQ"])
    df = make_sample_data(200, "trend_up")
    X = agent._compute_features(df)

    assert X.shape[0] == len(df)
    assert X.shape[1] >= 1  # al menos returns
    assert not np.any(np.isnan(X))
    assert not np.any(np.isinf(X))


def test_regime_mapping_heuristic():
    """Heurística de mapeo estado -> régimen."""
    agent = create_regime_agent(symbols=["NQ"])

    # Trend up: trend positivo, vol baja
    regime = agent._map_state_to_regime("NQ", 0, np.array([0.001, 0.0005, 0.002]), None)
    assert regime == Regime.TREND_UP

    # Trend down: trend negativo, vol baja
    regime = agent._map_state_to_regime("NQ", 1, np.array([-0.001, 0.0005, -0.002]), None)
    assert regime == Regime.TREND_DOWN

    # Range high vol: vol alta
    regime = agent._map_state_to_regime("NQ", 2, np.array([0.0, 0.02, 0.0]), None)
    assert regime == Regime.RANGE_HIGH_VOL

    # Range low vol: vol baja, trend plano
    regime = agent._map_state_to_regime("NQ", 3, np.array([0.0, 0.0003, 0.0]), None)
    assert regime == Regime.RANGE_LOW_VOL


def test_regime_agent_train_infer_cycle():
    """Ciclo completo: train -> infer -> get_regime."""
    agent = create_regime_agent(symbols=["NQ"], model_dir="./models/test_regime")

    # Mock data provider que devuelve datos sintéticos
    def mock_provider(symbol, tf, lookback):
        return make_sample_data(lookback, "trend_up")

    agent.data_provider = mock_provider

    # Train
    success = agent._train_symbol("NQ")
    assert success is True

    # Infer
    state = agent._infer_regime("NQ")
    assert state is not None
    assert state.symbol == "NQ"
    assert state.regime in Regime
    assert 0.0 <= state.confidence <= 1.0

    # Get regime
    got = agent.get_regime("NQ")
    assert got is not None
    assert got.regime == state.regime

    # Cleanup
    import shutil
    shutil.rmtree("./models/test_regime", ignore_errors=True)


def test_is_trend_is_range():
    """Helpers is_trend / is_range."""
    agent = create_regime_agent(symbols=["NQ"])
    agent.data_provider = lambda s, tf, lb: make_sample_data(lb, "trend_up")

    agent._train_symbol("NQ")
    agent._infer_regime("NQ")

    # Después de train/infer, debe detectar trend
    assert agent.is_trend("NQ") is True
    assert agent.is_range("NQ") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])