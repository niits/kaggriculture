import unittest

from kaggriculture.agents.kaggle_builtin.pro_tier_agent import agent
from kaggriculture.models import Observation


class ProTierAgentTests(unittest.TestCase):
    def test_action_matches_workers_and_only_sells_market_products(self):
        obs: Observation = {
            "player": 0,
            "step": 0,
            "day": 0,
            "hour": 0,
            "farms": [
                {
                    "money": 3000.0,
                    "tiles": [[None, None], [None, None]],
                    "farmer": [0, 0],
                    "hands": [[1, 0]],
                    "unlocked_quadrants": ["NW", "NE", "SW", "SE"],
                    "hires_today": 0,
                },
                {
                    "money": 3000.0,
                    "tiles": [[None, None], [None, None]],
                    "farmer": [0, 0],
                    "hands": [],
                    "unlocked_quadrants": ["NW"],
                    "hires_today": 0,
                },
            ],
            "private": {
                "shed": {
                    "WHEAT": 1,
                    "CARROT": 1,
                    "TOMATO": 1,
                    "STRAWBERRY": 1,
                    "MELON": 1,
                    "EGG": 1,
                    "MILK": 1,
                    "WOOL": 1,
                    "FERTILIZER": 1,
                    "GOOSE": 1,
                    "COW": 1,
                    "SHEEP": 1,
                },
                "seeds": {"TOMATO": 0},
                "inventories": [{}, {}],
            },
            "market": {
                "inventory": {
                    "WHEAT": 10_000,
                    "CARROT": 10_000,
                    "TOMATO": 10_000,
                    "STRAWBERRY": 10_000,
                    "MELON": 10_000,
                    "EGG": 10_000,
                    "MILK": 10_000,
                    "WOOL": 10_000,
                    "FERTILIZER": 10_000,
                },
                "prices": {
                    "WHEAT": 25,
                    "CARROT": 35,
                    "TOMATO": 60,
                    "STRAWBERRY": 120,
                    "MELON": 250,
                    "EGG": 50,
                    "MILK": 160,
                    "WOOL": 200,
                    "FERTILIZER": 100,
                },
            },
            "town": {"unlocked_shops": []},
        }

        action = agent(obs)

        self.assertEqual(len(action["hands"]), len(obs["farms"][0]["hands"]))
        self.assertLessEqual(len(action["market"]), 10)
        sold_items = {order[1] for order in action["market"] if order[0] == "SELL"}
        self.assertTrue(sold_items.isdisjoint({"GOOSE", "COW", "SHEEP"}))


if __name__ == "__main__":
    unittest.main()
