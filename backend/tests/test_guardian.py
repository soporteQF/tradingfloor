"""Tests del Guardian Agent."""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from agents.guardian import (
    GuardianAgent, GuardResult, GuardAction, GuardCategory,
    RiskLimits, PortfolioState
)
from agents.execution import Signal, SignalSide, SignalType


def test_guardian_allows_normal_trade():
    """Trade normal pasa todos los guards."""
    guardian = GuardianAgent(limits=RiskLimits(max_daily_loss_usd=1500.0))
    portfolio = PortfolioState(equity=50_000.0, peak_equity=50_000.0, daily_pnl=0.0)

    signal = Signal(strategy_id="test", symbol="NQ", contract="MNQ",
                    side=SignalSide.LONG, signal_type=SignalType.ENTRY, quantity=1)

    results = guardian.check_pre_trade(signal, portfolio)

    # No debe haber acciones de bloqueo
    blocking = [r for r in results if r.is_blocking]
    assert len(blocking) == 0


def test_guardian_blocks_daily_loss_limit():
    """Daily loss limit bloquea nuevas órdenes."""
    guardian = GuardianAgent(limits=RiskLimits(max_daily_loss_usd=100.0))
    portfolio = PortfolioState(equity=49_800.0, peak_equity=50_000.0, daily_pnl=-200.0)

    signal = Signal(strategy_id="test", symbol="NQ", contract="MNQ",
                    side=SignalSide.LONG, signal_type=SignalType.ENTRY, quantity=1)

    results = guardian.check_pre_trade(signal, portfolio)

    blocking = [r for r in results if r.is_blocking]
    assert len(blocking) == 1
    assert blocking[0].guard_name == "daily_loss_limit"
    assert blocking[0].action == GuardAction.FLATTEN


def test_guardian_blocks_trailing_drawdown():
    """Trailing drawdown bloquea y exige flatten."""
    guardian = GuardianAgent(limits=RiskLimits(max_trailing_dd_usd=500.0))
    portfolio = PortfolioState(equity=49_400.0, peak_equity=50_000.0, daily_pnl=0.0)

    signal = Signal(strategy_id="test", symbol="NQ", contract="MNQ",
                    side=SignalSide.LONG, signal_type=SignalType.ENTRY, quantity=1)

    results = guardian.check_pre_trade(signal, portfolio)

    blocking = [r for r in results if r.is_blocking]
    assert len(blocking) == 1
    assert blocking[0].guard_name == "trailing_drawdown"
    assert blocking[0].action == GuardAction.FLATTEN


def test_guardian_kill_switch_blocks_all():
    """Kill switch activo bloquea todo."""
    guardian = GuardianAgent()
    guardian.activate_kill_switch("Test emergency")

    portfolio = PortfolioState(equity=50_000.0)
    signal = Signal(strategy_id="test", symbol="NQ", contract="MNQ",
                    side=SignalSide.LONG, signal_type=SignalType.ENTRY, quantity=1)

    results = guardian.check_pre_trade(signal, portfolio)

    blocking = [r for r in results if r.is_blocking]
    assert len(blocking) == 1
    assert blocking[0].action == GuardAction.KILL
    assert blocking[0].guard_name == "global_kill_switch"


def test_guardian_loss_streak_cooldown():
    """Loss streak activa cooldown y bloquea."""
    guardian = GuardianAgent(limits=RiskLimits(
        loss_streak_cooldown_trades=2,
        loss_streak_cooldown_minutes=5,
    ))

    # Simular 2 trades perdedores
    guardian.check_post_trade(-100.0, "strat_1")
    guardian.check_post_trade(-50.0, "strat_1")

    portfolio = PortfolioState(equity=50_000.0)
    signal = Signal(strategy_id="strat_1", symbol="NQ", contract="MNQ",
                    side=SignalSide.LONG, signal_type=SignalType.ENTRY, quantity=1)

    results = guardian.check_pre_trade(signal, portfolio)

    blocking = [r for r in results if r.is_blocking]
    assert len(blocking) == 1
    assert blocking[0].guard_name == "loss_streak_cooldown"
    assert guardian._cooldown_until is not None


def test_guardian_max_trades_per_hour():
    """Límite de trades por hora."""
    guardian = GuardianAgent(limits=RiskLimits(max_trades_per_hour=2))
    portfolio = PortfolioState(equity=50_000.0, trades_today=0)

    # Simular 2 trades recientes
    now = datetime.now(timezone.utc)
    portfolio.trades_last_hour = [now - timedelta(minutes=10), now - timedelta(minutes=20)]
    portfolio.trades_today = 2

    signal = Signal(strategy_id="test", symbol="NQ", contract="MNQ",
                    side=SignalSide.LONG, signal_type=SignalType.ENTRY, quantity=1)

    results = guardian.check_pre_trade(signal, portfolio)

    blocking = [r for r in results if r.is_blocking]
    assert len(blocking) == 1
    assert blocking[0].guard_name == "max_trades_per_hour"


def test_guardian_max_contracts_per_symbol():
    """Límite de contratos por símbolo."""
    guardian = GuardianAgent(limits=RiskLimits(max_contracts_per_symbol=3))
    portfolio = PortfolioState(
        equity=50_000.0,
        open_positions={"NQ": {"quantity": 3, "notional": 60_000.0}}
    )

    signal = Signal(strategy_id="test", symbol="NQ", contract="MNQ",
                    side=SignalSide.LONG, signal_type=SignalType.ENTRY, quantity=1)

    results = guardian.check_pre_trade(signal, portfolio)

    # Debe haber REDUCE (no block, porque puede reducir size)
    reduce_actions = [r for r in results if r.action == GuardAction.REDUCE]
    assert len(reduce_actions) >= 1
    assert any(r.guard_name == "max_contracts_per_symbol" for r in reduce_actions)


def test_guardian_max_total_contracts():
    """Límite total de contratos."""
    guardian = GuardianAgent(limits=RiskLimits(max_total_contracts=5))
    portfolio = PortfolioState(
        equity=50_000.0,
        open_positions={
            "NQ": {"quantity": 3, "notional": 60_000.0},
            "ES": {"quantity": 2, "notional": 50_000.0},
        }
    )

    signal = Signal(strategy_id="test", symbol="GC", contract="MGC",
                    side=SignalSide.LONG, signal_type=SignalType.ENTRY, quantity=1)

    results = guardian.check_pre_trade(signal, portfolio)

    blocking = [r for r in results if r.is_blocking]
    assert len(blocking) == 1
    assert blocking[0].guard_name == "max_total_contracts"


def test_guardian_correlated_exposure():
    """Exposición correlacionada (NQ+ES+YM)."""
    guardian = GuardianAgent(limits=RiskLimits(
        max_correlated_exposure=0.5,
        max_total_notional=200_000.0,
    ))
    portfolio = PortfolioState(
        equity=50_000.0,
        open_positions={
            "NQ": {"quantity": 5, "notional": 100_000.0},
            "ES": {"quantity": 2, "notional": 50_000.0},
        }
    )

    signal = Signal(strategy_id="test", symbol="YM", contract="MYM",
                    side=SignalSide.LONG, signal_type=SignalType.ENTRY, quantity=1)

    results = guardian.check_pre_trade(signal, portfolio)

    reduce_actions = [r for r in results if r.action == GuardAction.REDUCE]
    assert any(r.guard_name == "correlated_exposure" for r in reduce_actions)


def test_guardian_post_trade_updates_state():
    """Post-trade actualiza loss streak y trades."""
    guardian = GuardianAgent()
    portfolio = PortfolioState(equity=50_000.0)

    # Trade ganador
    results = guardian.check_post_trade(100.0, "strat_1")
    assert guardian._portfolio.trades_today == 1
    assert guardian._portfolio.loss_streak == 0

    # Trade perdedor
    results = guardian.check_post_trade(-50.0, "strat_1")
    assert guardian._portfolio.loss_streak == 1

    # Otro perdedor
    results = guardian.check_post_trade(-30.0, "strat_1")
    assert guardian._portfolio.loss_streak == 2


def test_guardian_strategy_dd_flatten():
    """Max DD por estrategia fuerza flatten."""
    guardian = GuardianAgent(limits=RiskLimits(max_strategy_dd_pct=10.0))
    guardian.set_strategy_dd("strat_1", 12.0)  # > 10%

    portfolio = PortfolioState(equity=50_000.0)
    results = guardian.check_intra_trade(portfolio)

    blocking = [r for r in results if r.is_blocking]
    assert len(blocking) == 1
    assert blocking[0].guard_name == "strategy_max_dd"
    assert blocking[0].action == GuardAction.FLATTEN


def test_guardian_status_report():
    """Status report para Chief UI."""
    guardian = GuardianAgent(limits=RiskLimits(max_daily_loss_usd=1500.0))
    portfolio = PortfolioState(equity=49_500.0, peak_equity=50_000.0, daily_pnl=-500.0)
    guardian.update_portfolio(portfolio)
    guardian.check_post_trade(-100.0, "strat_1")

    status = guardian.get_status()

    assert status["kill_switch"] is False
    assert status["loss_streak"] == 1
    assert status["trades_today"] == 1
    assert status["daily_pnl"] == -500.0
    assert status["trailing_dd"] == 500.0
    assert "limits" in status


if __name__ == "__main__":
    pytest.main([__file__, "-v"])