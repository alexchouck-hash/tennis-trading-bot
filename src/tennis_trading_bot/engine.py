"""Main orchestrator coordinating feed ingestion, strategy evaluation, and order execution."""

from __future__ import annotations

import logging
import time
from typing import Any

from tennis_trading_bot.brokers.base import BaseBroker
from tennis_trading_bot.brokers.kalshi import KalshiBroker
from tennis_trading_bot.brokers.paper import PaperBroker
from tennis_trading_bot.client import PredictionClient
from tennis_trading_bot.config import BotConfig
from tennis_trading_bot.models import Order
from tennis_trading_bot.strategy import StrategyEngine

logger = logging.getLogger("tennis_trading_bot.engine")


class TradingEngine:
    """Coordinates feed ingestion, edge filtering, sizing, and order dispatch."""

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.client = PredictionClient(feed_url=config.predictions_feed_url)
        self.strategy = StrategyEngine(config)
        self.broker: BaseBroker = (
            KalshiBroker(config) if config.trade_mode == "kalshi" else PaperBroker(config)
        )

    def run_once(self, dry_run: bool = False) -> dict[str, Any]:
        """Execute a single evaluation and trading cycle."""
        logger.info(f"Running scan cycle (mode={self.config.trade_mode}, dry_run={dry_run})...")

        # 1. Fetch latest predictions
        feed = self.client.get_predictions(force_refresh=True)
        evaluations = feed.kalshi_evaluations

        if not evaluations:
            logger.info("No active market evaluations found on the predictions feed.")
            return {
                "evaluations_count": 0,
                "signals": [],
                "orders": [],
                "portfolio": self.broker.sync_portfolio(),
            }

        # 2. Get existing positions to prevent duplicate entries
        open_positions = self.broker.get_open_positions()
        existing_tickers = {p.ticker for p in open_positions}

        # 3. Scan evaluations through strategy
        signals, skip_counter = self.strategy.scan_evaluations(
            evaluations, existing_tickers=existing_tickers
        )

        orders: list[Order] = []
        if not dry_run:
            for sig in signals:
                order = self.broker.place_order(sig)
                orders.append(order)

        portfolio_summary = self.broker.sync_portfolio()

        return {
            "evaluations_count": len(evaluations),
            "signals": signals,
            "orders": orders,
            "skip_reasons": dict(skip_counter),
            "portfolio": portfolio_summary,
            "dry_run": dry_run,
        }

    def run_loop(self, poll_interval: int | None = None, dry_run: bool = False) -> None:
        """Run continuous daemon polling loop."""
        interval = poll_interval or self.config.poll_interval_seconds
        logger.info(f"Starting tennis-trading-bot polling loop (interval: {interval}s)...")

        try:
            while True:
                try:
                    res = self.run_once(dry_run=dry_run)
                    logger.info(
                        f"Cycle finished: {len(res['signals'])} signals, "
                        f"{len(res['orders'])} orders | "
                        f"Equity: ${res['portfolio']['total_equity_usd']:.2f}"
                    )
                except Exception as exc:
                    logger.exception(f"Error during execution cycle: {exc}")

                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Trading bot gracefully stopped by user.")
