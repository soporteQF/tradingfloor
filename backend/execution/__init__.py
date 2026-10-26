"""Execution adapters: paper + live (Tradovate).

Interfaces idénticas para paper/live. El agente no sabe dónde corre.
"""

from .base import ExecutionAdapter, Order, Position, Fill, OrderSide, OrderType, OrderStatus
from .paper import PaperExecutionAdapter

__all__ = [
    "ExecutionAdapter",
    "Order",
    "Position", 
    "Fill",
    "OrderSide",
    "OrderType", 
    "OrderStatus",
    "PaperExecutionAdapter",
]