"""Canonical name -> agent lookup, shared by benchmarking and submission tooling."""

from collections.abc import Callable
from typing import Any

from kaggriculture.agents.baseline import (
    animal_heavy,
    balanced,
    many_hands,
    market_tracker,
    roi_crop,
    wheat_only,
)
from kaggriculture.agents.kaggle_builtin import pro_tier_agent

Agent = Callable[[dict[str, Any]], dict[str, Any]]

AGENTS: dict[str, Agent] = {
    "wheat_only": wheat_only.agent,
    "roi_crop": roi_crop.agent,
    "market_tracker": market_tracker.agent,
    "many_hands": many_hands.agent,
    "animal_heavy": animal_heavy.agent,
    "balanced": balanced.agent,
    "pro_tier": pro_tier_agent.agent,
}
