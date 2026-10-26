"""Tests del Chief of Staff."""

from __future__ import annotations

import pytest
import time
from unittest.mock import Mock

from agents.chief import (
    ChiefOfStaff, ChiefCommand, NightlyStatus, PaperStrategy, GuardianAlert,
    LoopState, StrategyState, create_chief_of_staff,
)
from agents.guardian import GuardianAgent
from knowledge_graph.client import KnowledgeGraph
from orchestration.event_bus import EventBus


@pytest.fixture
def chief_with_mocks(tmp_path):
    """Chief con mocks para testing."""
    db_path = str(tmp_path / "test_chief.db")
    kg = KnowledgeGraph(db_path)
    eb = EventBus(enabled=False)
    guardian = GuardianAgent()

    nightly_runner = Mock()
    paper_runner = Mock()
    tts = Mock()

    chief = ChiefOfStaff(
        kg=kg,
        event_bus=eb,
        guardian=guardian,
        nightly_loop_runner=nightly_runner,
        paper_loop_runner=paper_runner,
        kokoro_tts=tts,
    )
    chief.start()

    yield chief, kg, guardian, nightly_runner, paper_runner, tts

    chief.stop()
    kg.close()


def test_chief_creation():
    kg = KnowledgeGraph("./data/knowledge_graph/test_chief_create.db")
    eb = EventBus(enabled=False)
    guardian = GuardianAgent()
    chief = ChiefOfStaff(kg=kg, event_bus=eb, guardian=guardian)
    assert chief.name == "chief"
    chief.stop()
    kg.close()
    import shutil
    shutil.rmtree("./data/knowledge_graph/test_chief_create.db", ignore_errors=True)


def test_chief_factory():
    kg = KnowledgeGraph("./data/knowledge_graph/test_chief_factory.db")
    eb = EventBus(enabled=False)
    guardian = GuardianAgent()
    chief = create_chief_of_staff(kg=kg, event_bus=eb, guardian=guardian)
    assert isinstance(chief, ChiefOfStaff)
    chief.stop()
    kg.close()
    import shutil
    shutil.rmtree("./data/knowledge_graph/test_chief_factory.db", ignore_errors=True)


def test_register_paper_strategy(chief_with_mocks):
    chief, _, _, _, _, _ = chief_with_mocks
    strat = PaperStrategy(
        strategy_id="test_123",
        name="ema_trend_nq_5m",
        symbol="NQ",
        timeframe="5m",
        regime="trend_up",
        state=StrategyState.PAPER,
        equity=50000,
        unrealized_pnl=100,
        realized_pnl=-50,
        trades_today=2,
        win_rate=0.5,
    )
    chief.register_paper_strategy(strat)

    status = chief.get_status()
    assert "test_123" in status["paper_strategies"]
    assert status["paper_strategies"]["test_123"]["name"] == "ema_trend_nq_5m"


def test_promote_command(chief_with_mocks):
    chief, kg, _, _, _, tts = chief_with_mocks

    # Registrar strategy en KG primero
    from contracts import StrategyDNA, EntryRule, ExitRule, SizingRule, ValidationMetrics, StrategyStatus
    import uuid
    s = StrategyDNA(
        id="test_123",
        hypothesis_id="h1",
        symbol="NQ",
        timeframe="5m",
        entry=EntryRule(kind="ema_cross", params={}),
        exit=ExitRule(kind="atr_trailing", params={}),
        sizing=SizingRule(kind="fixed_contracts", params={}),
        regime_gates=["trend_up"],
        performance=ValidationMetrics(sharpe=1.5, max_drawdown=0.1, trades=100),
        fingerprint="test",
        status=StrategyStatus.VALIDATED,
    )
    kg.write_strategy(s)

    chief.register_paper_strategy(PaperStrategy(
        strategy_id="test_123",
        name="ema_trend_nq_5m",
        symbol="NQ",
        timeframe="5m",
        regime="trend_up",
        state=StrategyState.VALIDATED,
    ))

    # Enviar comando promote
    chief.send_command(ChiefCommand(type="promote", strategy_id="test_123", reason="User approved"))
    time.sleep(0.3)

    status = chief.get_status()
    assert status["paper_strategies"]["test_123"]["state"] == "paper"
    tts.assert_called()


def test_retire_command(chief_with_mocks):
    chief, kg, _, _, _, tts = chief_with_mocks

    from contracts import StrategyDNA, EntryRule, ExitRule, SizingRule, ValidationMetrics, StrategyStatus
    s = StrategyDNA(
        id="test_456",
        hypothesis_id="h2",
        symbol="ES",
        timeframe="5m",
        entry=EntryRule(kind="ema_cross", params={}),
        exit=ExitRule(kind="atr_trailing", params={}),
        sizing=SizingRule(kind="fixed_contracts", params={}),
        regime_gates=["trend_up"],
        performance=ValidationMetrics(sharpe=1.2, max_drawdown=0.15, trades=80),
        fingerprint="test2",
        status=StrategyStatus.PAPER,
    )
    kg.write_strategy(s)

    chief.register_paper_strategy(PaperStrategy(
        strategy_id="test_456",
        name="ema_trend_es_5m",
        symbol="ES",
        timeframe="5m",
        regime="trend_up",
        state=StrategyState.PAPER,
    ))

    chief.send_command(ChiefCommand(type="retire", strategy_id="test_456", reason="Underperforming"))
    time.sleep(0.3)

    status = chief.get_status()
    assert status["paper_strategies"]["test_456"]["state"] == "retired"
    tts.assert_called()


def test_kill_switch_command(chief_with_mocks):
    chief, _, guardian, _, _, tts = chief_with_mocks

    chief.send_command(ChiefCommand(type="kill_switch", reason="Manual emergency"))
    time.sleep(0.3)

    # Verificar que guardian tiene kill switch activo
    guard_status = guardian.get_status()
    assert guard_status["kill_switch"] is True
    tts.assert_called()


def test_pause_resume_nightly(chief_with_mocks):
    chief, _, _, _, _, tts = chief_with_mocks

    # Pause
    chief.send_command(ChiefCommand(type="pause_loop"))
    time.sleep(0.2)
    status = chief.get_status()
    assert status["nightly"]["state"] == "paused"

    # Resume
    chief.send_command(ChiefCommand(type="resume_loop"))
    time.sleep(0.2)
    status = chief.get_status()
    assert status["nightly"]["state"] == "running"

    assert tts.call_count >= 2


def test_run_nightly_now(chief_with_mocks):
    chief, _, _, nightly_runner, _, tts = chief_with_mocks

    chief.send_command(ChiefCommand(type="run_nightly_now"))
    time.sleep(0.3)

    nightly_runner.assert_called_once()
    tts.assert_called()


def test_guardian_alert_subscription(chief_with_mocks):
    chief, _, _, _, _, _ = chief_with_mocks

    # Publicar alerta de guardian via event bus
    from orchestration.event_bus import EventBus
    # Usar el mismo event bus del chief
    chief.event_bus.publish("guardian_alerts", {
        "timestamp": "2024-01-15T10:30:00+00:00",
        "guard_name": "daily_loss_limit",
        "action": "flatten",
        "message": "Daily loss limit exceeded",
        "severity": "critical",
        "strategy_id": "test_123",
        "symbol": "NQ",
    })

    time.sleep(0.2)

    status = chief.get_status()
    alerts = status["guardian_alerts"]
    assert len(alerts) >= 1
    assert alerts[-1]["guard_name"] == "daily_loss_limit"
    assert alerts[-1]["action"] == "flatten"


def test_paper_fill_event_updates_strategy(chief_with_mocks):
    chief, _, _, _, _, _ = chief_with_mocks

    chief.register_paper_strategy(PaperStrategy(
        strategy_id="test_789",
        name="mean_rev_nq_15m",
        symbol="NQ",
        timeframe="15m",
        regime="range_low_vol",
        state=StrategyState.PAPER,
    ))

    # Simular fill event
    chief.event_bus.publish("paper_fills", {
        "strategy_id": "test_789",
        "side": "LONG",
        "qty": 1,
        "price": 15000,
        "realized_pnl": 80,
        "unrealized_pnl": 20,
        "trades_today": 1,
        "win_rate": 1.0,
        "avg_slippage_bps": 0.5,
    })

    time.sleep(0.2)

    status = chief.get_status()
    s = status["paper_strategies"]["test_789"]
    assert s["realized_pnl"] == 80
    assert s["unrealized_pnl"] == 20
    assert s["trades_today"] == 1
    assert s["win_rate"] == 1.0
    assert s["avg_fill_slippage_bps"] == 0.5
    assert "LONG 1 @ 15000" in s["last_fill"]


def test_paper_signal_event(chief_with_mocks):
    chief, _, _, _, _, _ = chief_with_mocks

    chief.register_paper_strategy(PaperStrategy(
        strategy_id="test_999",
        name="breakout_ym_5m",
        symbol="YM",
        timeframe="5m",
        regime="trend_up",
        state=StrategyState.PAPER,
    ))

    chief.event_bus.publish("paper_signals", {
        "strategy_id": "test_999",
        "signal": "ENTRY LONG 2 @ 35000",
    })

    time.sleep(0.2)

    status = chief.get_status()
    assert status["paper_strategies"]["test_999"]["last_signal"] == "ENTRY LONG 2 @ 35000"


def test_get_status_structure(chief_with_mocks):
    chief, _, _, _, _, _ = chief_with_mocks

    status = chief.get_status()

    # Verificar estructura completa
    assert "nightly" in status
    assert "paper_strategies" in status
    assert "guardian_alerts" in status
    assert "guardian_status" in status

    nightly = status["nightly"]
    assert "state" in nightly
    assert "last_run" in nightly
    assert "hypotheses_generated" in nightly
    assert "hypotheses_passed" in nightly
    assert "hypotheses_rejected" in nightly

    guardian_status = status["guardian_status"]
    assert "kill_switch" in guardian_status
    assert "loss_streak" in guardian_status
    assert "trades_today" in guardian_status


def test_update_nightly_status(chief_with_mocks):
    chief, _, _, _, _, _ = chief_with_mocks

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    chief.update_nightly_status(
        state=LoopState.RUNNING,
        last_run=now,
        hypotheses_generated=10,
        hypotheses_passed=2,
        hypotheses_rejected=8,
    )

    status = chief.get_status()
    assert status["nightly"]["state"] == "running"
    assert status["nightly"]["hypotheses_generated"] == 10
    assert status["nightly"]["hypotheses_passed"] == 2
    assert status["nightly"]["hypotheses_rejected"] == 8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])