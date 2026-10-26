"""Tests del PaperExecutionAdapter."""

from __future__ import annotations

import pytest

from execution import PaperExecutionAdapter, Order, OrderSide, OrderType, OrderStatus
from backtest.engine import SymbolSpec, SPECS


def test_paper_basic_flow():
    """Flujo básico: connect -> place market order -> sync -> fill -> position."""
    adapter = PaperExecutionAdapter(starting_equity=50_000.0)
    adapter.connect()

    # Orden market buy 1 MNQ
    order = Order(
        symbol="NQ",
        contract="MNQ",
        side=OrderSide.BUY,
        type=OrderType.MARKET,
        quantity=1,
    )
    submitted = adapter.place_order(order)
    assert submitted.status == OrderStatus.SUBMITTED

    # Sync procesa el fill
    adapter.sync()

    # Verificar fill
    fills = adapter.get_fills(order_id=submitted.id)
    assert len(fills) == 1
    fill = fills[0]
    assert fill.symbol == "NQ"
    assert fill.contract == "MNQ"
    assert fill.side == OrderSide.BUY
    assert fill.quantity == 1
    assert fill.price > 0
    assert fill.commission > 0

    # Verificar posición
    pos = adapter.get_position("NQ", "MNQ")
    assert pos is not None
    assert pos.quantity == 1
    assert pos.avg_entry_price == fill.price

    # Account summary
    summary = adapter.get_account_summary()
    assert summary["equity"] > 0
    assert summary["positions"] == 1


def test_paper_sell_closes_position():
    """Sell cierra posición long."""
    adapter = PaperExecutionAdapter(starting_equity=50_000.0)
    adapter.connect()

    # Buy 1
    buy = Order(symbol="NQ", contract="MNQ", side=OrderSide.BUY, type=OrderType.MARKET, quantity=1)
    adapter.place_order(buy)
    adapter.sync()

    # Sell 1 (flat)
    sell = Order(symbol="NQ", contract="MNQ", side=OrderSide.SELL, type=OrderType.MARKET, quantity=1)
    adapter.place_order(sell)
    adapter.sync()

    # Verificar que la posición se cerró (get_position retorna None para flat)
    pos = adapter.get_position("NQ", "MNQ")
    assert pos is None  # posición flat -> None

    # Verificar P&L realizado en account summary
    summary = adapter.get_account_summary()
    assert summary["realized_pnl"] != 0


def test_paper_risk_daily_loss_limit():
    """Daily loss limit rechaza órdenes."""
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date().isoformat()

    adapter = PaperExecutionAdapter(
        starting_equity=50_000.0,
        risk_limits={"max_daily_loss": 100.0},
    )
    adapter.connect()

    # Forzar daily loss alto para HOY
    adapter.equity = 49_800.0
    adapter._daily_pnl[today] = -200.0

    order = Order(symbol="NQ", contract="MNQ", side=OrderSide.BUY, type=OrderType.MARKET, quantity=1)
    submitted = adapter.place_order(order)
    assert submitted.status == OrderStatus.REJECTED
    assert "DAILY_LOSS_LIMIT" in submitted.error_message


def test_paper_risk_trailing_dd():
    """Trailing drawdown rechaza órdenes."""
    adapter = PaperExecutionAdapter(
        starting_equity=50_000.0,
        risk_limits={"max_trailing_dd": 500.0},
    )
    adapter.connect()

    # Simular peak equity y drawdown
    adapter._peak_equity = 51_000.0
    adapter.equity = 50_400.0  # DD = 600 > 500

    order = Order(symbol="NQ", contract="MNQ", side=OrderSide.BUY, type=OrderType.MARKET, quantity=1)
    submitted = adapter.place_order(order)
    assert submitted.status == OrderStatus.REJECTED
    assert "TRAILING_DD" in submitted.error_message


def test_paper_max_contracts():
    """Límite de contratos por símbolo."""
    adapter = PaperExecutionAdapter(
        starting_equity=50_000.0,
        risk_limits={"max_contracts_per_symbol": 2},
    )
    adapter.connect()

    # Buy 2
    for _ in range(2):
        o = Order(symbol="NQ", contract="MNQ", side=OrderSide.BUY, type=OrderType.MARKET, quantity=1)
        adapter.place_order(o)
        adapter.sync()

    # Tercer buy debe ser rechazado
    o3 = Order(symbol="NQ", contract="MNQ", side=OrderSide.BUY, type=OrderType.MARKET, quantity=1)
    submitted = adapter.place_order(o3)
    assert submitted.status == OrderStatus.REJECTED
    assert "MAX_CONTRACTS" in submitted.error_message


def test_paper_idempotency():
    """client_order_id evita duplicados."""
    adapter = PaperExecutionAdapter(starting_equity=50_000.0)
    adapter.connect()

    o1 = Order(symbol="NQ", contract="MNQ", side=OrderSide.BUY, type=OrderType.MARKET,
               quantity=1, client_order_id="sig_123")
    r1 = adapter.place_order(o1)

    o2 = Order(symbol="NQ", contract="MNQ", side=OrderSide.BUY, type=OrderType.MARKET,
               quantity=1, client_order_id="sig_123")
    r2 = adapter.place_order(o2)

    assert r1.id == r2.id  # misma orden


def test_paper_slippage_applied():
    """Slippage se aplica en contra."""
    adapter = PaperExecutionAdapter(
        starting_equity=50_000.0,
        slippage_ticks={"MNQ": 2.0},  # 2 ticks = 0.5 puntos
    )
    adapter.connect()

    order = Order(symbol="NQ", contract="MNQ", side=OrderSide.BUY, type=OrderType.MARKET, quantity=1)
    adapter.place_order(order)
    adapter.sync()

    fill = adapter.get_fills(order_id=order.id)[0]
    spec = SPECS["MNQ"]
    # Precio de fill = close + slippage (compra paga más)
    # No podemos verificar precio exacto sin data_provider, pero slippage_ticks debe registrarse
    assert fill.slippage_ticks == 2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])