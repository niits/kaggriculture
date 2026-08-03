"""Run reproducible self-play and pairwise benchmarks for baseline agents."""

import argparse
import csv
import json
import math
import resource
import time
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from statistics import mean
from typing import Any

from kaggriculture.agents.registry import AGENTS, Agent

SEED_COST = {
    "WHEAT": 10,
    "CARROT": 20,
    "TOMATO": 50,
    "STRAWBERRY": 100,
    "MELON": 80,
}
ANIMAL_COST = {"GOOSE": 300, "COW": 400, "SHEEP": 500}
BASE_PRICE = {
    "WHEAT": 25,
    "CARROT": 35,
    "TOMATO": 60,
    "STRAWBERRY": 120,
    "MELON": 250,
    "EGG": 50,
    "MILK": 160,
    "WOOL": 200,
}
DEFAULT_OUTPUT_DIR = Path("data/baseline_benchmark")


def percentile(values: list[float], rank: int) -> float:
    """Return a nearest-rank percentile, or zero for an empty sample."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(rank / 100 * len(ordered)) - 1)
    return ordered[index]


def snapshot_clock(
    observation: dict[str, Any], step_index: int, turns_per_day: int
) -> tuple[int, int, int]:
    """Read game time, including Kaggle's field-less initial observation."""
    game_step = observation.get("step", step_index)
    day = observation.get("day", game_step // turns_per_day)
    hour = observation.get("hour", game_step % turns_per_day)
    return game_step, day, hour


@dataclass
class DecisionRecorder:
    agent_name: str
    calls: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    worker_operations: Counter[str] = field(default_factory=Counter)
    market_operations: Counter[str] = field(default_factory=Counter)

    def record(self, agent: Agent, observation: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter_ns()
        try:
            action = agent(observation)
        finally:
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            self.calls += 1
            self.latencies_ms.append(elapsed_ms)

        for worker_action in [action.get("farmer", ["PASS"]), *action.get("hands", [])]:
            operation = worker_action[0] if worker_action else "PASS"
            self.worker_operations[operation] += 1
        for market_order in action.get("market", []):
            if market_order:
                self.market_operations[market_order[0]] += 1
        return action


def farm_metrics(observation: dict[str, Any]) -> dict[str, int | float]:
    """Extract cash, liquid assets, deployed capital, and board health."""
    player = observation["player"]
    farm = observation["farms"][player]
    private = observation["private"]
    prices = observation["market"]["prices"]

    metrics: dict[str, int | float] = {
        "cash": float(farm["money"]),
        "shed_items": sum(private["shed"].values()),
        "carried_items": sum(
            sum(inventory.values()) for inventory in private["inventories"]
        ),
        "seed_items": sum(private["seeds"].values()),
        "hands": len(farm["hands"]),
        "unlocked_quadrants": len(farm["unlocked_quadrants"]),
        "plants": 0,
        "animals": 0,
        "weeds": 0,
        "empty_tiles": 0,
        "locked_tiles": 0,
    }
    for crop in SEED_COST:
        metrics[f"plants_{crop.lower()}"] = 0
    for animal in ANIMAL_COST:
        metrics[f"animals_{animal.lower()}"] = 0

    deployed_capital = 0.0
    for row in farm["tiles"]:
        for tile in row:
            if tile == "LOCKED":
                metrics["locked_tiles"] += 1
            elif tile is None:
                metrics["empty_tiles"] += 1
            elif tile.get("kind") == "WEED":
                metrics["weeds"] += 1
            elif tile.get("kind") == "PLANT":
                crop = tile["crop"]
                metrics["plants"] += 1
                metrics[f"plants_{crop.lower()}"] += 1
                deployed_capital += SEED_COST[crop]
            elif tile.get("animal") in ANIMAL_COST:
                animal = tile["animal"]
                metrics["animals"] += 1
                metrics[f"animals_{animal.lower()}"] += 1
                deployed_capital += ANIMAL_COST[animal]

    liquidation_value = float(farm["money"])
    for inventory in [private["shed"], *private["inventories"]]:
        for item, quantity in inventory.items():
            if item in BASE_PRICE:
                liquidation_value += quantity * prices[item]
            elif item in ANIMAL_COST:
                liquidation_value += quantity * ANIMAL_COST[item]
    for crop, quantity in private["seeds"].items():
        liquidation_value += quantity * SEED_COST[crop]

    metrics["liquidation_value"] = liquidation_value
    metrics["deployed_capital"] = deployed_capital
    metrics["net_worth_proxy"] = liquidation_value + deployed_capital
    return metrics


def _decision_metrics(recorder: DecisionRecorder) -> dict[str, Any]:
    return {
        "decision_calls": recorder.calls,
        "decision_mean_ms": mean(recorder.latencies_ms)
        if recorder.latencies_ms
        else 0.0,
        "decision_p50_ms": percentile(recorder.latencies_ms, 50),
        "decision_p95_ms": percentile(recorder.latencies_ms, 95),
        "decision_max_ms": max(recorder.latencies_ms, default=0.0),
        "worker_operations": json.dumps(
            dict(recorder.worker_operations), sort_keys=True
        ),
        "market_operations": json.dumps(
            dict(recorder.market_operations), sort_keys=True
        ),
    }


def _trajectory_rows(
    env: Any,
    episode_id: str,
    mode: str,
    round_number: int,
    seed: int,
    names: tuple[str, str],
    turns_per_day: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    final_index = len(env.steps) - 1
    for step_index, states in enumerate(env.steps):
        if (
            step_index != 0
            and (step_index + 1) % turns_per_day != 0
            and step_index != final_index
        ):
            continue
        for seat, name in enumerate(names):
            observation = states[seat].observation
            prices = observation["market"]["prices"]
            price_index = mean(prices[item] / BASE_PRICE[item] for item in BASE_PRICE)
            game_step, day, hour = snapshot_clock(
                observation, step_index, turns_per_day
            )
            rows.append(
                {
                    "episode_id": episode_id,
                    "mode": mode,
                    "round": round_number,
                    "seed": seed,
                    "seat": seat,
                    "agent": name,
                    "opponent": names[1 - seat],
                    "step_index": step_index,
                    "game_step": game_step,
                    "day": day,
                    "hour": hour,
                    "market_price_index": price_index,
                    **farm_metrics(observation),
                }
            )
    return rows


def run_match(
    names: tuple[str, str],
    mode: str,
    round_number: int,
    seed: int,
    episode_steps: int,
    turns_per_day: int = 24,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], float]:
    """Run one episode and return player summaries plus daily trajectories."""
    from kaggle_environments import make

    recorders = [DecisionRecorder(name) for name in names]

    def wrapped(seat: int) -> Agent:
        return lambda obs: recorders[seat].record(AGENTS[names[seat]], obs)

    env = make(
        "kaggriculture",
        configuration={"episodeSteps": episode_steps, "seed": seed},
        debug=True,
    )
    started = time.perf_counter()
    env.run([wrapped(0), wrapped(1)])
    elapsed_seconds = time.perf_counter() - started

    episode_id = f"{mode}-{names[0]}-vs-{names[1]}-r{round_number}"
    final_states = env.steps[-1]
    rewards = [float(state.reward or 0.0) for state in final_states]
    if rewards[0] == rewards[1]:
        outcomes = ("draw", "draw")
    elif rewards[0] > rewards[1]:
        outcomes = ("win", "loss")
    else:
        outcomes = ("loss", "win")

    episode_rows: list[dict[str, Any]] = []
    for seat, name in enumerate(names):
        observation = final_states[seat].observation
        episode_rows.append(
            {
                "episode_id": episode_id,
                "mode": mode,
                "round": round_number,
                "seed": seed,
                "seat": seat,
                "agent": name,
                "opponent": names[1 - seat],
                "outcome": outcomes[seat],
                "status": final_states[seat].status,
                "reward": rewards[seat],
                "episode_steps": len(env.steps),
                "elapsed_seconds": elapsed_seconds,
                "environment_steps_per_second": len(env.steps) / elapsed_seconds,
                **farm_metrics(observation),
                **_decision_metrics(recorders[seat]),
            }
        )
    trajectory_rows = _trajectory_rows(
        env,
        episode_id,
        mode,
        round_number,
        seed,
        names,
        turns_per_day,
    )
    return episode_rows, trajectory_rows, elapsed_seconds


def _summary_rows(episode_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in episode_rows:
        grouped[(row["mode"], row["agent"])].append(row)

    summaries: list[dict[str, Any]] = []
    for (mode, agent), rows in sorted(grouped.items()):
        summaries.append(
            {
                "mode": mode,
                "agent": agent,
                "games": len(rows),
                "wins": sum(row["outcome"] == "win" for row in rows),
                "draws": sum(row["outcome"] == "draw" for row in rows),
                "losses": sum(row["outcome"] == "loss" for row in rows),
                "win_rate": mean(row["outcome"] == "win" for row in rows),
                "average_reward": mean(row["reward"] for row in rows),
                "average_net_worth_proxy": mean(row["net_worth_proxy"] for row in rows),
                "average_plants": mean(row["plants"] for row in rows),
                "average_animals": mean(row["animals"] for row in rows),
                "average_weeds": mean(row["weeds"] for row in rows),
                "decision_mean_ms": mean(row["decision_mean_ms"] for row in rows),
                "decision_p95_ms": max(row["decision_p95_ms"] for row in rows),
            }
        )
    return summaries


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _operation_totals(
    rows: Iterable[dict[str, Any]], field_name: str
) -> dict[str, int]:
    totals: Counter[str] = Counter()
    for row in rows:
        totals.update(json.loads(row[field_name]))
    return dict(totals)


def build_progress_record(
    episode_rows: list[dict[str, Any]],
    completed: int,
    total: int,
    benchmark_elapsed: float,
    match_elapsed: float,
) -> dict[str, Any]:
    """Build an interruption-safe match result and progress snapshot."""
    winner = next((row for row in episode_rows if row["outcome"] == "win"), None)
    average_match_seconds = benchmark_elapsed / completed
    return {
        "episode_id": episode_rows[0]["episode_id"],
        "mode": episode_rows[0]["mode"],
        "round": episode_rows[0]["round"],
        "seed": episode_rows[0]["seed"],
        "completed_matches": completed,
        "total_matches": total,
        "progress_percent": completed / total * 100,
        "match_elapsed_seconds": match_elapsed,
        "benchmark_elapsed_seconds": benchmark_elapsed,
        "eta_seconds": average_match_seconds * (total - completed),
        "winner_agent": winner["agent"] if winner else "draw",
        "winner_seat": winner["seat"] if winner else None,
        "rewards": {
            f"seat_{row['seat']}_{row['agent']}": row["reward"] for row in episode_rows
        },
    }


def run_benchmark(
    rounds: int,
    episode_steps: int,
    output_dir: Path,
    selected_agents: tuple[str, ...] = tuple(AGENTS),
) -> dict[str, Any]:
    """Run self-play and all unique pairings, then persist CSV and JSON reports."""
    unknown = set(selected_agents) - AGENTS.keys()
    if unknown:
        raise ValueError(f"Unknown agents: {', '.join(sorted(unknown))}")

    output_dir.mkdir(parents=True, exist_ok=True)
    matches: list[tuple[str, tuple[str, str], int, int]] = []
    for round_index in range(rounds):
        round_number = round_index + 1
        seed = 10_000 + round_index
        for name in selected_agents:
            matches.append(("self_play", (name, name), round_number, seed))
        for first, second in combinations(selected_agents, 2):
            names = (first, second) if round_index % 2 == 0 else (second, first)
            matches.append(("competition", names, round_number, seed))

    all_episode_rows: list[dict[str, Any]] = []
    all_trajectory_rows: list[dict[str, Any]] = []
    benchmark_started = time.perf_counter()
    progress_path = output_dir / "match_progress.jsonl"
    with progress_path.open("w", encoding="utf-8") as progress_output:
        for index, (mode, names, round_number, seed) in enumerate(matches, start=1):
            episode_rows, trajectory_rows, elapsed = run_match(
                names, mode, round_number, seed, episode_steps
            )
            all_episode_rows.extend(episode_rows)
            all_trajectory_rows.extend(trajectory_rows)
            benchmark_elapsed = time.perf_counter() - benchmark_started
            progress = build_progress_record(
                episode_rows, index, len(matches), benchmark_elapsed, elapsed
            )
            progress_output.write(json.dumps(progress) + "\n")
            progress_output.flush()
            rewards = " | ".join(
                f"{row['agent']}[s{row['seat']}]={row['reward']:.0f}"
                for row in episode_rows
            )
            print(
                f"[{index:03d}/{len(matches)} {progress['progress_percent']:5.1f}%] "
                f"{mode} r{round_number}: {rewards} | "
                f"winner={progress['winner_agent']}[s{progress['winner_seat']}] | "
                f"match={elapsed:.2f}s eta={progress['eta_seconds']:.0f}s",
                flush=True,
            )

    elapsed_seconds = time.perf_counter() - benchmark_started
    summaries = _summary_rows(all_episode_rows)
    _write_csv(output_dir / "episodes.csv", all_episode_rows)
    _write_csv(output_dir / "trajectory.csv", all_trajectory_rows)
    _write_csv(output_dir / "agent_summary.csv", summaries)

    system_report = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "configuration": {
            "rounds": rounds,
            "episode_steps": episode_steps,
            "agents": list(selected_agents),
            "seeds": [10_000 + index for index in range(rounds)],
        },
        "matches": len(matches),
        "player_episode_rows": len(all_episode_rows),
        "trajectory_rows": len(all_trajectory_rows),
        "elapsed_seconds": elapsed_seconds,
        "environment_steps": len(matches) * episode_steps,
        "environment_steps_per_second": len(matches) * episode_steps / elapsed_seconds,
        "decision_calls": sum(row["decision_calls"] for row in all_episode_rows),
        "decision_mean_ms": mean(row["decision_mean_ms"] for row in all_episode_rows),
        "decision_p95_ms": max(row["decision_p95_ms"] for row in all_episode_rows),
        "worker_operations": _operation_totals(all_episode_rows, "worker_operations"),
        "market_operations": _operation_totals(all_episode_rows, "market_operations"),
        "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "artifacts": [
            "match_progress.jsonl",
            "episodes.csv",
            "trajectory.csv",
            "agent_summary.csv",
        ],
    }
    with (output_dir / "system_performance.json").open("w", encoding="utf-8") as output:
        json.dump(system_report, output, indent=2)
        output.write("\n")
    return system_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--episode-steps", type=int, default=720)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--agents", nargs="+", choices=tuple(AGENTS), default=tuple(AGENTS)
    )
    args = parser.parse_args()
    report = run_benchmark(
        rounds=args.rounds,
        episode_steps=args.episode_steps,
        output_dir=args.output_dir,
        selected_agents=tuple(args.agents),
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
