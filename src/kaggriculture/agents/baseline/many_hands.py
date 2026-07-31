"""Baseline that scales a tomato field with five hired farm hands."""

from kaggriculture.agents.baseline.common import Strategy, run_strategy

STRATEGY = Strategy(
    crop_mode="fixed",
    fixed_crop="TOMATO",
    target_plants=25,
    target_hands=5,
    buy_land_above=1200,
)


def agent(obs):
    return run_strategy(obs, STRATEGY)
