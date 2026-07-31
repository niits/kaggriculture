"""Baseline that keeps production spread across all crop types."""

from kaggriculture.agents.baseline.common import Strategy, run_strategy

STRATEGY = Strategy(crop_mode="balanced", target_plants=20, target_hands=2)


def agent(obs):
    return run_strategy(obs, STRATEGY)
