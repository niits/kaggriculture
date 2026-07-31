import unittest
from pathlib import Path
from tomllib import load

from kaggriculture.evaluation.baseline_benchmark import (
    AGENTS,
    DEFAULT_OUTPUT_DIR,
    DecisionRecorder,
    build_progress_record,
    farm_metrics,
    percentile,
    snapshot_clock,
)


class BaselineBenchmarkTests(unittest.TestCase):
    def test_benchmark_defaults_to_tracked_data_directory(self):
        self.assertEqual(DEFAULT_OUTPUT_DIR, Path("data/baseline_benchmark"))

    def test_registry_includes_kaggle_pro_tier_agent(self):
        self.assertIn("pro_tier", AGENTS)

    def test_pyproject_registers_benchmark_cli(self):
        project_file = Path(__file__).parents[1] / "pyproject.toml"
        with project_file.open("rb") as source:
            project = load(source)

        self.assertEqual(
            project["project"]["scripts"]["kaggriculture-benchmark"],
            "kaggriculture.evaluation.baseline_benchmark:main",
        )

    def test_farm_metrics_capture_assets_and_board_health(self):
        observation = {
            "player": 0,
            "farms": [
                {
                    "money": 100.0,
                    "tiles": [
                        [
                            {
                                "kind": "PLANT",
                                "crop": "WHEAT",
                                "yield_units": 2,
                            },
                            {"kind": "WEED"},
                        ],
                        [
                            {"kind": "COOP", "animal": "GOOSE"},
                            None,
                        ],
                    ],
                    "hands": [[0, 0]],
                    "unlocked_quadrants": ["NW"],
                }
            ],
            "private": {
                "shed": {"WHEAT": 3, "GOOSE": 1},
                "seeds": {"WHEAT": 2},
                "inventories": [{"EGG": 1}],
            },
            "market": {"prices": {"WHEAT": 25, "EGG": 50}},
        }

        metrics = farm_metrics(observation)

        self.assertEqual(metrics["cash"], 100.0)
        self.assertEqual(metrics["plants"], 1)
        self.assertEqual(metrics["animals"], 1)
        self.assertEqual(metrics["weeds"], 1)
        self.assertEqual(metrics["shed_items"], 4)
        self.assertEqual(metrics["carried_items"], 1)
        self.assertEqual(metrics["liquidation_value"], 545.0)

    def test_decision_recorder_tracks_latency_and_action_mix(self):
        recorder = DecisionRecorder("test")

        action = recorder.record(
            lambda _: {
                "farmer": ["PASS"],
                "hands": [["WATER"]],
                "market": [["BUY_SEED", "WHEAT", 1]],
            },
            {},
        )

        self.assertEqual(action["farmer"], ["PASS"])
        self.assertEqual(recorder.calls, 1)
        self.assertEqual(recorder.worker_operations["PASS"], 1)
        self.assertEqual(recorder.worker_operations["WATER"], 1)
        self.assertEqual(recorder.market_operations["BUY_SEED"], 1)
        self.assertEqual(len(recorder.latencies_ms), 1)

    def test_percentile_uses_nearest_rank(self):
        self.assertEqual(percentile([1.0, 2.0, 3.0, 100.0], 95), 100.0)
        self.assertEqual(percentile([], 95), 0.0)

    def test_snapshot_clock_supports_initial_observation_without_time_fields(self):
        self.assertEqual(snapshot_clock({}, 0, 24), (0, 0, 0))
        self.assertEqual(
            snapshot_clock({"step": 25, "day": 1, "hour": 1}, 25, 24), (25, 1, 1)
        )

    def test_progress_record_exposes_winner_rewards_and_eta(self):
        rows = [
            {
                "episode_id": "competition-a-vs-b-r1",
                "mode": "competition",
                "round": 1,
                "seed": 10_000,
                "agent": "a",
                "seat": 0,
                "reward": 20.0,
                "outcome": "win",
            },
            {
                "agent": "b",
                "seat": 1,
                "reward": 10.0,
                "outcome": "loss",
            },
        ]

        record = build_progress_record(rows, 2, 10, 4.0, 1.0)

        self.assertEqual(record["winner_agent"], "a")
        self.assertEqual(record["winner_seat"], 0)
        self.assertEqual(record["rewards"], {"seat_0_a": 20.0, "seat_1_b": 10.0})
        self.assertEqual(record["progress_percent"], 20.0)
        self.assertEqual(record["eta_seconds"], 16.0)


if __name__ == "__main__":
    unittest.main()
