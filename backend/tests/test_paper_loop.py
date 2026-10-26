"""Test PaperTradingLoop integración básica."""

from __future__ import annotations

import pytest

from orchestration.paper_loop import PaperTradingLoop, PaperConfig
from knowledge_graph.client import KnowledgeGraph
from contracts import StrategyDNA, StrategyStatus, ValidationMetrics
from agents.execution import Signal, SignalSide


def test_paper_loop_start_stop():
    """Loop inicia y para correctamente."""
    import tempfile
    import shutil

    tmpdir = tempfile.mkdtemp()
    try:
        kg_path = f"{tmpdir}/test_kuzu.db"
        kg = KnowledgeGraph(kg_path)

        config = PaperConfig(
            symbols=["NQ"],
            timeframes=["1h"],
            starting_equity=50_000.0,
        )
        loop = PaperTradingLoop(kg, config)

        # Start
        loop.start()
        assert loop._running is True

        # Stop
        loop.stop()
        assert loop._running is False
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_paper_loop_register_strategy():
    """Registra estrategia y genera sesión."""
    import tempfile
    import shutil

    tmpdir = tempfile.mkdtemp()
    try:
        kg_path = f"{tmpdir}/test_kuzu.db"
        kg = KnowledgeGraph(kg_path)

        config = PaperConfig(symbols=["NQ"], timeframes=["1h"])
        loop = PaperTradingLoop(kg, config)
        loop.start()

        # Crear StrategyDNA válida
        from contracts import EntryRule, ExitRule, SizingRule
        dna = StrategyDNA(
            hypothesis_id="hyp_test_123",
            symbol="NQ",
            timeframe="1h",
            contract="MNQ",
            entry=EntryRule(kind="ema_cross", params={"fast": 9, "slow": 21}),
            exit=ExitRule(kind="fixed_r", params={"stop_atr": 2.0, "r_multiple": 2.0}),
            sizing=SizingRule(kind="atr_risk", params={"risk_usd": 400.0}),
            regime_gates=["trend_up", "trend_down"],
            performance=ValidationMetrics(trades=50, sharpe=1.5, max_drawdown=-0.1),
            status=StrategyStatus.VALIDATED,
        )

        loop.register_strategy(dna)
        assert dna.id in loop._active_strategies

        stats = loop.get_session_stats(dna.id)
        assert stats is not None
        assert stats["symbol"] == "NQ"
        assert stats["timeframe"] == "1h"

        loop.stop()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_paper_loop_force_signal():
    """Fuerza señal manual y ejecuta."""
    import tempfile
    import shutil

    tmpdir = tempfile.mkdtemp()
    try:
        kg_path = f"{tmpdir}/test_kuzu.db"
        kg = KnowledgeGraph(kg_path)

        config = PaperConfig(
            symbols=["NQ"],
            timeframes=["1h"],
            starting_equity=50_000.0,
        )
        loop = PaperTradingLoop(kg, config)
        loop.start()

        from contracts import EntryRule, ExitRule, SizingRule
        dna = StrategyDNA(
            hypothesis_id="hyp_test_456",
            symbol="NQ",
            timeframe="1h",
            contract="MNQ",
            entry=EntryRule(kind="ema_cross", params={}),
            exit=ExitRule(kind="fixed_r", params={}),
            sizing=SizingRule(kind="atr_risk", params={"risk_usd": 400.0}),
            regime_gates=[],
            performance=ValidationMetrics(),
            status=StrategyStatus.VALIDATED,
        )
        loop.register_strategy(dna)

        # Forzar señal long
        signal = loop.force_signal(dna.id, SignalSide.LONG)
        assert signal is not None
        assert signal.side == SignalSide.LONG

        # Verificar que se ejecutó
        stats = loop.get_session_stats(dna.id)
        assert stats["signals"] == 1

        loop.stop()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])