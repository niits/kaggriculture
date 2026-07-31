import unittest

from kaggriculture.agents.baseline import (
    animal_heavy,
    balanced,
    many_hands,
    market_tracker,
    roi_crop,
    wheat_only,
)


def observation(*, hands=None, prices=None):
    hands = hands or []
    prices = prices or {
        "WHEAT": 25,
        "CARROT": 35,
        "TOMATO": 60,
        "STRAWBERRY": 120,
        "MELON": 250,
        "EGG": 50,
        "MILK": 160,
        "WOOL": 200,
        "FERTILIZER": 100,
    }
    farm = {
        "money": 3000.0,
        "tiles": [[None] * 5 for _ in range(5)],
        "farmer": [4, 4],
        "hands": hands,
        "unlocked_quadrants": ["NW"],
        "hires_today": len(hands),
    }
    return {
        "player": 0,
        "step": 0,
        "day": 0,
        "hour": 0,
        "farms": [farm, {**farm, "hands": []}],
        "private": {
            "shed": {
                "WHEAT": 0,
                "CARROT": 0,
                "TOMATO": 0,
                "STRAWBERRY": 0,
                "MELON": 0,
                "EGG": 0,
                "MILK": 0,
                "WOOL": 0,
                "FERTILIZER": 0,
                "GOOSE": 0,
                "COW": 0,
                "SHEEP": 0,
            },
            "seeds": {
                "WHEAT": 0,
                "CARROT": 0,
                "TOMATO": 0,
                "STRAWBERRY": 0,
                "MELON": 0,
            },
            "inventories": [{} for _ in range(1 + len(hands))],
        },
        "market": {
            "inventory": {item: 10_000 for item in prices},
            "prices": prices,
        },
        "town": {"unlocked_shops": []},
    }


class BaselineAgentTests(unittest.TestCase):
    def test_every_agent_returns_one_action_per_worker(self):
        obs = observation(hands=[[3, 4], [4, 3]])

        for module in (
            wheat_only,
            roi_crop,
            market_tracker,
            many_hands,
            animal_heavy,
            balanced,
        ):
            with self.subTest(agent=module.__name__):
                action = module.agent(obs)
                self.assertEqual(set(action), {"farmer", "hands", "market"})
                self.assertEqual(len(action["hands"]), 2)
                self.assertLessEqual(len(action["market"]), 10)

    def test_wheat_only_buys_no_other_seed(self):
        orders = wheat_only.agent(observation())["market"]

        seed_crops = [order[1] for order in orders if order[0] == "BUY_SEED"]
        self.assertEqual(seed_crops, ["WHEAT"])

    def test_roi_agent_uses_current_price_in_crop_choice(self):
        prices = observation()["market"]["prices"] | {"CARROT": 500}
        orders = roi_crop.agent(observation(prices=prices))["market"]

        self.assertIn(["BUY_SEED", "CARROT", 4], orders)

    def test_market_agent_targets_the_most_understocked_product(self):
        obs = observation()
        obs["market"]["inventory"]["MELON"] = 9000

        orders = market_tracker.agent(obs)["market"]

        self.assertIn(["BUY_SEED", "MELON", 4], orders)

    def test_many_hands_agent_hires_toward_six_workers(self):
        orders = many_hands.agent(observation())["market"]

        self.assertGreaterEqual(sum(order == ["HIRE"] for order in orders), 5)

    def test_animal_agent_invests_in_livestock_and_feed(self):
        action = animal_heavy.agent(observation())
        orders = action["market"]

        self.assertTrue(any(order[0] == "BUY_ANIMAL" for order in orders))
        self.assertTrue(any(order[:2] == ["BUY_PRODUCT", "WHEAT"] for order in orders))
        self.assertEqual(action["farmer"], ["BUILD_COOP"])

    def test_balanced_agent_buys_a_mix_of_crop_seeds(self):
        orders = balanced.agent(observation())["market"]

        seed_crops = {order[1] for order in orders if order[0] == "BUY_SEED"}
        self.assertGreaterEqual(len(seed_crops), 3)


if __name__ == "__main__":
    unittest.main()
