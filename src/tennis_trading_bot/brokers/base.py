"""Abstract Base Broker interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from tennis_trading_bot.models import Order, Position, TradeSignal


class BaseBroker(ABC):
    """Abstract interface for trade execution brokers."""

    @abstractmethod
    def get_balance(self) -> float:
        """Return current available cash balance in USD."""

    @abstractmethod
    def get_open_positions(self) -> list[Position]:
        """Return list of active open positions."""

    @abstractmethod
    def place_order(self, signal: TradeSignal) -> Order:
        """Submit an order for an actionable trade signal."""

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""

    @abstractmethod
    def sync_portfolio(self) -> dict[str, Any]:
        """Synchronize open positions and update equity metrics."""
