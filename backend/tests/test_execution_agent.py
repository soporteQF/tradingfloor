"""Test integración ExecutionAgent + PaperExecutionAdapter."""

from __future__ import annotations

import pytest

from agents.execution import ExecutionAgent, Signal, SignalSide, SignalType
from execution import PaperExecutionAdapter


def test_execution_agent_basic():
    """ExecutionAgent ejecuta señal y reporta fill."""
    adapter = PaperExecutionAdapter(starting_equity=50_000.0)
    adapter.connect()

    agent = ExecutionAgent(adapter)
    agent.connect()

    signal = Signal(
        strategy_id="test_strat",
        symbol="NQ",
        contract="MNQ",
        side=SignalSide.LONG,
        signal_type=SignalType.ENTRY,
        quantity=1,
        source_agent="test",
    )

    report = agent.submit_signal(signal)

    assert report.signal_id == signal.id
    assert report.status.value in ("submitted", "filled")

    # Sync procesa el fill
    adapter.sync()

    # Verificar fill en reporte
    # El reporte original no tiene fills porque se llenan en sync
    # Verificar vía adapter
    fills = adapter.get_fills(order_id=report.order_id)
    assert len(fills) == 1

    agent.disconnect()
    adapter.disconnect()


def test_execution_agent_flat_signal():
    """Signal FLAT cierra posición existente."""
    adapter = PaperExecutionAdapter(starting_equity=50_000.0)
    adapter.connect()
    agent = ExecutionAgent(adapter)
    agent.connect()

    # 1. Abrir long
    signal_long = Signal(
        strategy_id="test_strat",
        symbol="NQ",
        contract="MNQ",
        side=SignalSide.LONG,
        signal_type=SignalType.ENTRY,
        quantity=1,
        source_agent="test",
    )
    agent.submit_signal(signal_long)
    adapter.sync()

    pos = adapter.get_position("NQ", "MNQ")
    assert pos is not None
    assert pos.quantity == 1

    # 2. Cerrar con FLAT
    signal_flat = Signal(
        strategy_id="test_strat",
        symbol="NQ",
        contract="MNQ",
        side=SignalSide.FLAT,
        signal_type=SignalType.EXIT,
        source_agent="test",
    )
    agent.submit_signal(signal_flat)
    adapter.sync()

    pos = adapter.get_position("NQ", "MNQ")
    assert pos is None  # flat -> None

    agent.disconnect()
    adapter.disconnect()


def test_execution_agent_reduce_signal():
    """Signal REDUCE reduce posición."""
    adapter = PaperExecutionAdapter(
        starting_equity=50_000.0,
        risk_limits={"max_position_value": 500_000.0},  # Límite alto para test
    )
    adapter.connect()
    agent = ExecutionAgent(adapter)
    agent.connect()

    # Abrir long 4 contratos
    for _ in range(4):
        s = Signal(strategy_id="test", symbol="NQ", contract="MNQ",
                   side=SignalSide.LONG, signal_type=SignalType.ENTRY, quantity=1)
        agent.submit_signal(s)
        adapter.sync()

    pos = adapter.get_position("NQ", "MNQ")
    assert pos.quantity == 4

    # Reducir a la mitad
    signal_reduce = Signal(
        strategy_id="test",
        symbol="NQ",
        contract="MNQ",
        side=SignalSide.REDUCE,
        signal_type=SignalType.EXIT,
        source_agent="test",
    )
    agent.submit_signal(signal_reduce)
    adapter.sync()

    pos = adapter.get_position("NQ", "MNQ")
    assert pos.quantity == 2  # reducido a la mitad

    agent.disconnect()
    adapter.disconnect()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])