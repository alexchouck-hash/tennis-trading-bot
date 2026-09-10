"""Tests for quantitative strategy, fee modeling, and quarter-Kelly sizing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tennis_trading_bot.config import BotConfig
from tennis_trading_bot.models import MarketEvaluation
from tennis_trading_bot.strategy import (
    StrategyEngine,
    calculate_quarter_kelly,
    calculate_taker_fee,
)


def test_taker_fee_calculation() -> None:
    # At p=0.5, fee = 0.07 * 0.5 * 0.5 = 0.0175
    fee_mid = calculate_taker_fee(0.50)
    assert pytest.approx(fee_mid, 0.0001) == 0.0175

    # At p=0.1, fee = 0.07 * 0.1 * 0.9 = 0.0063
    fee_low = calculate_taker_fee(0.10)
    assert pytest.approx(fee_low, 0.0001) == 0.0063


def test_quarter_kelly_math() -> None:
    # 60% win prob vs 40c price -> positive Kelly
    # b = 0.6 / 0.4 = 1.5
    # raw kelly = (0.6*1.5 - 0.4)/1.5 = (0.9 - 0.4)/1.5 = 0.5/1.5 = 0.3333
    # 1/4 kelly = 0.3333 * 0.25 = 0.0833
    stake = calculate_quarter_kelly(0.60, 0.40, fee_per_contract=0.0)
    assert pytest.approx(stake, 0.001) == 0.0833

    # Negative EV -> 0.0
    zero_stake = calculate_quarter_kelly(0.40, 0.50, fee_per_contract=0.0)
    assert zero_stake == 0.0


def test_mx2_deadband_filter() -> None:
    config = BotConfig(bankroll_usd=1000.0, min_edge_pp=5.0)
    engine = StrategyEngine(config)

    # Item with prob 0.57 (in [0.55, 0.60) deadband)
    item = MarketEvaluation(
        match="Player A vs Player B",
        our_p1=0.57,
        kalshi_p1=0.45,
        confidence_band="high",
        match_start=(datetime.now(UTC) + timedelta(hours=3)).isoformat(),
    )
    sig, reason = engine.evaluate_evaluation(item)
    assert sig is None
    assert reason is not None
    assert "mx2_coinflip_band" in reason


def test_spread_filter() -> None:
    config = BotConfig(bankroll_usd=1000.0, max_spread=0.10)
    engine = StrategyEngine(config)

    # Item with spread 0.18 (> 0.10)
    item = MarketEvaluation(
        match="Player A vs Player B",
        our_p1=0.70,
        kalshi_p1=0.40,
        confidence_band="high",
        position_spread=0.18,
        match_start=(datetime.now(UTC) + timedelta(hours=3)).isoformat(),
    )
    sig, reason = engine.evaluate_evaluation(item)
    assert sig is None
    assert reason is not None
    assert "wide_spread" in reason


def test_successful_signal_generation() -> None:
    config = BotConfig(bankroll_usd=1000.0, min_edge_pp=8.0, max_stake_fraction=0.05)
    engine = StrategyEngine(config)

    # Clean +EV setup: 72% model prob vs 45c ask -> >25pp edge
    item = MarketEvaluation(
        match="Alexander Zverev vs Taylor Fritz",
        our_p1=0.72,
        kalshi_p1=0.45,
        confidence_band="high",
        position_spread=0.02,
        event_ticker="KXATPMATCH-26SEP09ZVEFRI",
        match_start=(datetime.now(UTC) + timedelta(hours=4)).isoformat(),
    )
    sig, reason = engine.evaluate_evaluation(item)
    assert sig is not None
    assert reason is None
    assert sig.event_ticker == "KXATPMATCH-26SEP09ZVEFRI"
    assert sig.edge_pp > 20.0
    assert sig.contracts > 0
    assert sig.stake_usd <= (config.bankroll_usd * config.max_stake_fraction)
