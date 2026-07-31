import unittest
from typing import get_type_hints


class DataModelTests(unittest.TestCase):
    def test_observation_exposes_documented_sections(self):
        from kaggriculture.models import Observation

        hints = get_type_hints(Observation)

        self.assertEqual(
            set(hints),
            {
                "player",
                "step",
                "day",
                "hour",
                "farms",
                "private",
                "market",
                "town",
                "remainingOverageTime",
            },
        )
        self.assertEqual(
            Observation.__required_keys__,
            {"player", "step", "day", "hour", "farms", "private", "market", "town"},
        )

    def test_tile_variants_match_wire_format(self):
        from kaggriculture.models import AnimalTile, PlantTile, StructureTile, WeedTile

        self.assertEqual(
            PlantTile.__required_keys__,
            {
                "kind",
                "crop",
                "planted_day",
                "watered_today",
                "consecutive_unwatered",
                "yield_units",
                "max_lifespan_step",
                "fertilized_until_day",
            },
        )
        self.assertEqual(WeedTile.__required_keys__, {"kind"})
        self.assertEqual(StructureTile.__required_keys__, {"kind"})
        self.assertIn("animal", AnimalTile.__required_keys__)

    def test_action_requires_all_output_channels(self):
        from kaggriculture.models import Action

        self.assertEqual(Action.__required_keys__, {"farmer", "hands", "market"})

    def test_configuration_is_a_sparse_override(self):
        from kaggriculture.models import Configuration

        self.assertFalse(Configuration.__required_keys__)
        self.assertIn("marketParams", Configuration.__optional_keys__)
        self.assertIn("weedSpawnChance", Configuration.__optional_keys__)


if __name__ == "__main__":
    unittest.main()
