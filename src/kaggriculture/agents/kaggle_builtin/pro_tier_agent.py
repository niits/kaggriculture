from typing import Literal, cast

from kaggriculture.models import (
    Action,
    Crop,
    MarketOrder,
    Observation,
    Product,
    UnitAction,
    UnitActionName,
)
from kaggriculture.utils.moving import get_direction

TARGET_CROP: Crop = "TOMATO"
TARGET_SEED_COUNT = 15
TARGET_SEED_PRICE = 50
MAX_MARKET_ORDERS = 10

WorkerRole = Literal["farmer", "hand"]
TileTask = tuple[int, int, UnitActionName]


def agent(obs: Observation) -> Action:
    """Coordinate workers around a tomato-focused scaling strategy."""
    try:
        me = obs["farms"][obs["player"]]
        private = obs["private"]
        prices = obs["market"]["prices"]

        tiles = me["tiles"]
        farmer_x, farmer_y = me["farmer"]
        hands = me["hands"]

        market_orders: list[MarketOrder] = []
        shed = private["shed"]
        total_shed_items = sum(shed.values())

        for item, count in shed.items():
            if count <= 0 or item not in prices:
                continue

            product = cast(Product, item)
            current_price = prices[product]
            if total_shed_items > 80 or current_price > 30 or product != "TOMATO":
                market_orders.append(["SELL", product, count])

        if (
            private["seeds"].get(TARGET_CROP, 0) < TARGET_SEED_COUNT
            and me["money"] >= TARGET_SEED_PRICE
        ):
            market_orders.append(["BUY_SEED", TARGET_CROP, 2])

        if me["money"] > 1500 and len(me["unlocked_quadrants"]) < 4:
            market_orders.append(["BUY_LAND"])

        pending_tasks: list[TileTask] = []
        empty_tiles: list[tuple[int, int]] = []

        for y, row in enumerate(tiles):
            for x, tile in enumerate(row):
                if tile == "LOCKED":
                    continue
                if tile is None:
                    empty_tiles.append((x, y))
                    continue

                kind = tile["kind"]
                if kind == "WEED":
                    pending_tasks.append((x, y, "DIG"))
                elif kind == "PLANT":
                    if tile["yield_units"] > 0:
                        pending_tasks.append((x, y, "HARVEST"))
                    elif not tile["watered_today"]:
                        pending_tasks.append((x, y, "WATER"))

        if len(pending_tasks) > 5 and me["money"] > 200 and me["hires_today"] < 2:
            market_orders.append(["HIRE"])

        workers: list[tuple[WorkerRole, int, int]] = [
            ("farmer", farmer_x, farmer_y),
            *(("hand", x, y) for x, y in hands),
        ]
        claimed_targets: set[tuple[int, int]] = set()
        farmer_action: UnitAction = ["PASS"]
        hand_actions: list[UnitAction] = []
        has_seeds = private["seeds"].get(TARGET_CROP, 0) > 0

        for role, worker_x, worker_y in workers:
            worker_action: UnitAction = ["PASS"]
            current_task: UnitActionName | None = None

            for task_x, task_y, task_action in pending_tasks:
                if (
                    task_x == worker_x
                    and task_y == worker_y
                    and (task_x, task_y) not in claimed_targets
                ):
                    current_task = task_action
                    break

            if current_task is not None:
                worker_action = [current_task]
                claimed_targets.add((worker_x, worker_y))
            elif (
                tiles[worker_y][worker_x] is None
                and has_seeds
                and (worker_x, worker_y) not in claimed_targets
            ):
                worker_action = ["PLANT", TARGET_CROP]
                claimed_targets.add((worker_x, worker_y))
            else:
                available_targets = [
                    (x, y) for x, y, _ in pending_tasks if (x, y) not in claimed_targets
                ]
                if not available_targets and has_seeds:
                    available_targets = [
                        (x, y) for x, y in empty_tiles if (x, y) not in claimed_targets
                    ]

                if available_targets:
                    target_x, target_y = min(
                        available_targets,
                        key=lambda target: (
                            abs(worker_x - target[0]) + abs(worker_y - target[1])
                        ),
                    )
                    worker_action = [
                        get_direction(worker_x, worker_y, target_x, target_y)
                    ]
                    claimed_targets.add((target_x, target_y))

            if role == "farmer":
                farmer_action = worker_action
            else:
                hand_actions.append(worker_action)

        return {
            "farmer": farmer_action,
            "hands": hand_actions,
            "market": market_orders[:MAX_MARKET_ORDERS],
        }
    except Exception:  # noqa: BLE001
        return {"farmer": ["PASS"], "hands": [], "market": []}
