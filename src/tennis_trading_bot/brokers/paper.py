"""Virtual Paper Broker simulating order fills and maintaining local JSONL ledger."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from tennis_trading_bot.brokers.base import BaseBroker
from tennis_trading_bot.config import BotConfig
from tennis_trading_bot.models import Order, Position, TradeSignal

logger = logging.getLogger("tennis_trading_bot.brokers.paper")


class PaperBroker(BaseBroker):
    """Zero-risk simulation broker logging virtual orders and equity."""

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.ledger_path = config.ledger_path
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.initial_bankroll = config.bankroll_usd
        self._positions: dict[str, Position] = {}
        self._orders: dict[str, Order] = {}
        self._cash = self.initial_bankroll
        self._load_ledger()

    def _utc_now_iso(self) -> str:
        return datetime.now(UTC).isoformat()

    def _load_ledger(self) -> None:
        """Load past records from the JSONL ledger file."""
        if not self.ledger_path.exists():
            return

        try:
            with self.ledger_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        rec_type = record.get("record_type")
                        if rec_type == "order":
                            order = Order.model_validate(record["data"])
                            self._orders[order.order_id] = order
                        elif rec_type == "position":
                            pos = Position.model_validate(record["data"])
                            self._positions[pos.position_id] = pos
                            if pos.status == "open":
                                self._cash -= pos.stake_usd
                        elif rec_type == "settlement":
                            pnl = float(record.get("realized_pnl_usd", 0.0))
                            stake = float(record.get("stake_usd", 0.0))
                            self._cash += (stake + pnl)
                    except Exception as err:
                        logger.warning(f"Could not parse ledger line: {err}")
        except OSError as exc:
            logger.error(f"Error loading ledger: {exc}")

    def _append_record(self, record_type: str, data: dict[str, Any]) -> None:
        """Atomically append a transaction record to JSONL ledger."""
        payload = {
            "ts_utc": self._utc_now_iso(),
            "record_type": record_type,
            "data": data,
        }
        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def get_balance(self) -> float:
        """Return current virtual cash balance."""
        return max(0.0, self._cash)

    def get_open_positions(self) -> list[Position]:
        """Return active open positions."""
        return [p for p in self._positions.values() if p.status == "open"]

    def place_order(self, signal: TradeSignal) -> Order:
        """Place a paper limit order and immediately simulate fill if liquid."""
        now_iso = self._utc_now_iso()
        order_id = f"paper-{uuid.uuid4().hex[:8]}"

        # Check bankroll
        cost = signal.stake_usd
        if cost > self._cash:
            logger.warning(f"Insufficient virtual cash (${self._cash:.2f} < ${cost:.2f})")
            order = Order(
                order_id=order_id,
                ticker=signal.event_ticker,
                match=signal.match,
                side=signal.side,
                price=signal.market_price,
                count=signal.contracts,
                stake_usd=cost,
                status="rejected",
                placed_at_utc=now_iso,
                broker_type="paper",
                notes="Insufficient virtual cash",
            )
            self._append_record("order", order.model_dump())
            return order

        # Simulate execution at current ask
        order = Order(
            order_id=order_id,
            ticker=signal.event_ticker,
            match=signal.match,
            side=signal.side,
            price=signal.market_price,
            count=signal.contracts,
            stake_usd=cost,
            status="filled",
            placed_at_utc=now_iso,
            filled_at_utc=now_iso,
            fill_price=signal.market_price,
            broker_type="paper",
            notes=signal.reason,
        )
        self._orders[order_id] = order
        self._append_record("order", order.model_dump())

        # Deduct cash & create open position
        self._cash -= cost
        pos_id = f"pos-{signal.event_ticker}"
        position = Position(
            position_id=pos_id,
            ticker=signal.event_ticker,
            match=signal.match,
            side=signal.side,
            entry_price=signal.market_price,
            contracts=signal.contracts,
            stake_usd=cost,
            model_prob_at_entry=signal.model_prob,
            opened_at_utc=now_iso,
            current_market_price=signal.market_price,
            unrealized_pnl_usd=0.0,
            status="open",
        )
        self._positions[pos_id] = position
        self._append_record("position", position.model_dump())

        logger.info(
            f"PAPER FILL: {signal.match} ({signal.event_ticker}) | "
            f"{signal.pick} {signal.side} @ {signal.market_price:.2f} | "
            f"{signal.contracts} contracts (${cost:.2f})"
        )
        return order

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        if order_id in self._orders and self._orders[order_id].status in ("pending", "open"):
            self._orders[order_id].status = "canceled"
            self._append_record("order_cancel", {"order_id": order_id})
            return True
        return False

    def sync_portfolio(self) -> dict[str, Any]:
        """Summarize current paper portfolio metrics."""
        open_pos = self.get_open_positions()
        invested = sum(p.stake_usd for p in open_pos)
        unrealized = sum(p.unrealized_pnl_usd for p in open_pos)
        total_equity = self._cash + invested + unrealized

        return {
            "broker": "paper",
            "cash_usd": round(self._cash, 2),
            "invested_usd": round(invested, 2),
            "total_equity_usd": round(total_equity, 2),
            "open_positions_count": len(open_pos),
            "total_orders_count": len(self._orders),
        }
