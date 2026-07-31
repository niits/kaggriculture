"""Baseline that plants and sells only wheat."""

from kaggriculture.agents.baseline.common import Strategy, run_strategy

STRATEGY = Strategy(crop_mode="fixed", fixed_crop="WHEAT", target_plants=20)


def agent(obs):
    return run_strategy(obs, STRATEGY)
