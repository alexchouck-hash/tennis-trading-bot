"""Quantitative trading strategy and risk sizing engine."""

from __future__ import annotations

import logging
import math
from collections import Counter
from datetime import UTC, datetime

from tennis_trading_bot.config import KALSHI_REFERRAL_URL, BotConfig
from tennis_trading_bot.models import MarketEvaluation, TradeSignal

logger = logging.getLogger("tennis_trading_bot.strategy")

# Deadband where tennis models exhibit coin-flip uncertainty
MX2_DEADBAND = (0.55, 0.60)


def calculate_taker_fee(price: float, rate: float = 0.07) -> float:
    """Continuous Kalshi taker fee per contract (0.07 * p * (1 - p))."""
    p = min(0.99, max(0.01, float(price)))
    return rate * p * (1.0 - p)


def calculate_quarter_kelly(
    win_prob: float,
    ask_price: float,
    fee_per_contract: float = 0.0,
    fraction_multiplier: float = 0.25,
) -> float:
    """Compute fee-aware fractional Kelly bet size.

    Formula:
      b = (1.0 - ask_price) / ask_price
      net_prob = win_prob - fee_per_contract
      kelly = (net_prob * b - (1.0 - net_prob)) / b = (net_prob - ask_price) / (1.0 - ask_price)
    """
    if ask_price <= 0.0 or ask_price >= 1.0:
        return 0.0
    net_p = win_prob - fee_per_contract
    if net_p <= ask_price:
        return 0.0

    b = (1.0 - ask_price) / ask_price
    raw_kelly = (net_p * b - (1.0 - net_p)) / b
    if raw_kelly <= 0.0:
        return 0.0
    return max(0.0, float(raw_kelly * fraction_multiplier))


def parse_iso_datetime(ts: str | None) -> datetime | None:
    """Parse ISO 8601 timestamp string safely."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, TypeError):
        return None


class StrategyEngine:
    """Evaluates market contracts, applies mathematical filters, and sizes positions."""

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.conf_ranks = {"any": 0, "low": 1, "medium": 2, "medium_plus": 2, "high": 3, "high_only": 3, "very_high": 4}

    def evaluate_evaluation(
        self,
        item: MarketEvaluation,
        now: datetime | None = None,
    ) -> tuple[TradeSignal | None, str | None]:
        """Evaluate a single market item against all quantitative risk criteria.

        Returns (TradeSignal, None) if criteria met, or (None, skip_reason).
        """
        now = now or datetime.now(UTC)

        # 0. Basic Validation
        if not item.match or item.our_p1 is None or item.kalshi_p1 is None:
            return None, "missing_match_or_prices"

        # 1. Resolve Players & Sides
        # We test both Player 1 and Player 2 side for +EV opportunity
        p1_prob = float(item.our_p1)
        kalshi_p1 = float(item.kalshi_p1)

        # Check if row is already pre-configured for a position side
        if item.position_side and item.position_our_prob is not None and item.position_buy_price is not None:
            side_prob = float(item.position_our_prob)
            side_ask = float(item.position_buy_price)
            side_bid = float(item.position_bid_price or (side_ask - (item.position_spread or 0.05)))
            side_name = item.position_side
            side_player = item.p1 if side_name == "p1" else item.p2 or "Player"
        else:
            # Default to evaluating Player 1
            side_prob = p1_prob
            side_ask = kalshi_p1
            side_bid = max(0.01, side_ask - 0.02)
            side_name = "yes"
            side_player = item.match.split(" vs ")[0] if " vs " in item.match else "Player 1"

        # 2. Spread Gate
        spread = item.position_spread if item.position_spread is not None else (side_ask - side_bid)
        if spread >= self.config.max_spread:
            return None, f"wide_spread ({spread:.2f} >= {self.config.max_spread:.2f})"

        # 3. Timing Gate (Avoid matches about to start or already in progress)
        match_start_dt = parse_iso_datetime(item.match_start)
        if match_start_dt:
            time_to_start = (match_start_dt - now).total_seconds() / 60.0
            if time_to_start < self.config.min_minutes_to_start:
                return None, f"starts_too_soon ({time_to_start:.1f}m < {self.config.min_minutes_to_start:.1f}m)"

        # 4. MX2 Deadband Filter
        # Models are measurably unreliable in [0.55, 0.60)
        if MX2_DEADBAND[0] <= side_prob < MX2_DEADBAND[1]:
            return None, f"mx2_coinflip_band ({side_prob:.3f} in {MX2_DEADBAND})"

        # 5. Confidence Band Filter
        c_band = str(item.confidence_band or "low").lower()
        required_rank = self.conf_ranks.get(self.config.min_confidence, 2)
        item_rank = self.conf_ranks.get(c_band, 1)
        if item_rank < required_rank:
            return None, f"confidence_too_low ({c_band} < {self.config.min_confidence})"

        # 6. Fee-Aware Edge Calculation
        taker_fee = calculate_taker_fee(side_ask)
        net_edge = side_prob - side_ask - taker_fee
        edge_pp = net_edge * 100.0

        if edge_pp < self.config.min_edge_pp:
            return None, f"edge_below_threshold ({edge_pp:+.1f}pp < {self.config.min_edge_pp:.1f}pp)"

        # 7. Quarter-Kelly Sizing
        kelly_fraction = calculate_quarter_kelly(side_prob, side_ask, fee_per_contract=taker_fee)
        if kelly_fraction <= 0.0:
            return None, "zero_kelly_stake"

        # Cap by safety limit
        kelly_fraction = min(kelly_fraction, self.config.max_stake_fraction)
        stake_usd = round(self.config.bankroll_usd * kelly_fraction, 2)
        contracts = math.floor(stake_usd / side_ask) if side_ask > 0 else 0

        if contracts < 1:
            return None, f"stake_too_small (${stake_usd:.2f} buys 0 contracts at ${side_ask:.2f})"

        # 8. Event Ticker & Action URL
        ticker = item.event_ticker or ""
        trade_url = KALSHI_REFERRAL_URL
        if isinstance(item.trade_action, dict):
            ticker = ticker or item.trade_action.get("ticker", "")
            trade_url = item.trade_action.get("url") or item.trade_action.get("trade_url") or KALSHI_REFERRAL_URL
        elif hasattr(item.trade_action, "url") and item.trade_action.url:
            trade_url = item.trade_action.url

        if not ticker:
            # Generate deterministic fallback ticker slug from match
            ticker = "KXATPMATCH-" + item.match.replace(" vs ", "-").replace(" ", "").upper()[:16]

        signal = TradeSignal(
            event_ticker=ticker,
            match=item.match,
            match_start=item.match_start,
            pick=side_player,
            side=side_name,  # type: ignore
            model_prob=round(side_prob, 4),
            market_price=round(side_ask, 3),
            edge_pp=round(edge_pp, 1),
            spread=round(spread, 3),
            confidence_band=c_band,
            kelly_fraction=round(kelly_fraction, 4),
            stake_usd=stake_usd,
            contracts=contracts,
            direct_trade_url=trade_url,
            reason=f"Fee-aware edge {edge_pp:+.1f}pp exceeds {self.config.min_edge_pp}pp with ¼-Kelly",
        )
        return signal, None

    def scan_evaluations(
        self,
        evaluations: list[MarketEvaluation],
        existing_tickers: set[str] | None = None,
    ) -> tuple[list[TradeSignal], Counter]:
        """Scan a batch of evaluations, deduping against existing open positions."""
        existing_tickers = existing_tickers or set()
        signals: list[TradeSignal] = []
        skip_counter: Counter = Counter()

        for item in evaluations:
            # Deduplicate per event/match
            ticker = item.event_ticker or item.match
            if not ticker:
                skip_counter["missing_match_or_ticker"] += 1
                continue
            if ticker in existing_tickers:
                skip_counter["already_in_portfolio"] += 1
                continue

            signal, reason = self.evaluate_evaluation(item)
            if signal:
                signals.append(signal)
                existing_tickers.add(ticker)
                existing_tickers.add(signal.event_ticker)
                if item.match:
                    existing_tickers.add(item.match)
            elif reason:
                skip_counter[reason.split()[0]] += 1

        return signals, skip_counter
