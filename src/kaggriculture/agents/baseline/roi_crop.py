"""Baseline that replans around the crop with the best current ROI."""

from kaggriculture.agents.baseline.common import Strategy, run_strategy

STRATEGY = Strategy(crop_mode="roi", target_plants=20)


def agent(obs):
    return run_strategy(obs, STRATEGY)
