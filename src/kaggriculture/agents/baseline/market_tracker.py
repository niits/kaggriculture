"""Baseline that targets scarce crops and waits for above-base sale prices."""

from kaggriculture.agents.baseline.common import Strategy, run_strategy

STRATEGY = Strategy(crop_mode="scarcity", target_plants=18, market_sell_ratio=1.1)


def agent(obs):
    return run_strategy(obs, STRATEGY)
