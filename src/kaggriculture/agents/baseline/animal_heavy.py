"""Baseline that prioritizes livestock, daily feed, care, and collection."""

from kaggriculture.agents.baseline.common import Strategy, run_strategy

STRATEGY = Strategy(
    crop_mode="fixed",
    target_hands=3,
    animals=(("GOOSE", 2), ("COW", 2), ("SHEEP", 2)),
    buy_land_above=2200,
)


def agent(obs):
    return run_strategy(obs, STRATEGY)
