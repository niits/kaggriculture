"""Shared deterministic planner used by the rule-based baseline agents."""

from dataclasses import dataclass
from typing import Any, Literal

CROPS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")
PRODUCTS = CROPS + ("EGG", "MILK", "WOOL")
SEED_COST = {
    "WHEAT": 10,
    "CARROT": 20,
    "TOMATO": 50,
    "STRAWBERRY": 100,
    "MELON": 80,
}
FIRST_YIELD_DAY = {
    "WHEAT": 2,
    "CARROT": 2,
    "TOMATO": 8,
    "STRAWBERRY": 10,
    "MELON": 10,
}
MAX_YIELD = {
    "WHEAT": 6,
    "CARROT": 4,
    "TOMATO": 4,
    "STRAWBERRY": 4,
    "MELON": 6,
}
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
ANIMAL_DATA = {
    "GOOSE": ("COOP", "EGG", 300),
    "COW": ("PASTURE", "MILK", 400),
    "SHEEP": ("PASTURE", "WOOL", 500),
}

CropMode = Literal["fixed", "roi", "scarcity", "balanced"]


@dataclass(frozen=True)
class Strategy:
    crop_mode: CropMode
    fixed_crop: str = "WHEAT"
    target_plants: int = 18
    seed_batch: int = 4
    target_hands: int = 1
    animals: tuple[tuple[str, int], ...] = ()
    market_sell_ratio: float = 0.0
    buy_land_above: int = 1800


def _crop_counts(tiles: list[list[Any]]) -> dict[str, int]:
    counts = {crop: 0 for crop in CROPS}
    for row in tiles:
        for tile in row:
            if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                counts[tile["crop"]] += 1
    return counts


def _choose_crop(
    obs: dict[str, Any], strategy: Strategy, counts: dict[str, int]
) -> str:
    if strategy.crop_mode == "fixed":
        return strategy.fixed_crop
    if strategy.crop_mode == "roi":
        prices = obs["market"]["prices"]
        return max(
            CROPS,
            key=lambda crop: (
                (prices[crop] * MAX_YIELD[crop] - SEED_COST[crop])
                / (SEED_COST[crop] * FIRST_YIELD_DAY[crop]),
                prices[crop],
            ),
        )
    if strategy.crop_mode == "scarcity":
        inventory = obs["market"]["inventory"]
        return min(
            CROPS, key=lambda crop: (inventory[crop], -obs["market"]["prices"][crop])
        )
    return min(CROPS, key=lambda crop: (counts[crop], CROPS.index(crop)))


def _market_orders(
    obs: dict[str, Any], strategy: Strategy, counts: dict[str, int]
) -> list[list[Any]]:
    me = obs["farms"][obs["player"]]
    private = obs["private"]
    prices = obs["market"]["prices"]
    orders: list[list[Any]] = []

    total_shed = sum(private["shed"].values())
    for product in PRODUCTS:
        quantity = private["shed"].get(product, 0)
        if quantity <= 0:
            continue
        price_is_good = (
            prices[product] >= BASE_PRICE[product] * strategy.market_sell_ratio
        )
        if price_is_good or total_shed >= 80 or obs["day"] >= 28:
            orders.append(["SELL", product, quantity])

    hands_needed = max(0, strategy.target_hands - len(me["hands"]))
    orders.extend([["HIRE"] for _ in range(hands_needed)])

    if strategy.animals:
        animal_counts = {animal: 0 for animal in ANIMAL_DATA}
        for row in me["tiles"]:
            for tile in row:
                if isinstance(tile, dict) and tile.get("animal") in animal_counts:
                    animal_counts[tile["animal"]] += 1
        for inventory in [private["shed"], *private["inventories"]]:
            for animal in animal_counts:
                animal_counts[animal] += inventory.get(animal, 0)

        planned_animals = 0
        for animal, target in strategy.animals:
            missing = max(0, target - animal_counts[animal])
            if missing:
                orders.append(["BUY_ANIMAL", animal, missing])
                planned_animals += missing

        occupied = sum(animal_counts.values()) + planned_animals
        wheat_on_hand = private["shed"].get("WHEAT", 0) + sum(
            inventory.get("WHEAT", 0) for inventory in private["inventories"]
        )
        wheat_needed = max(0, occupied * 2 - wheat_on_hand)
        if wheat_needed:
            orders.append(["BUY_PRODUCT", "WHEAT", wheat_needed])
    else:
        crop = _choose_crop(obs, strategy, counts)
        if strategy.crop_mode == "balanced":
            per_crop_target = max(1, strategy.target_plants // len(CROPS))
            for candidate in CROPS:
                stock = counts[candidate] + private["seeds"].get(candidate, 0)
                if stock < per_crop_target:
                    orders.append(
                        [
                            "BUY_SEED",
                            candidate,
                            min(strategy.seed_batch, per_crop_target - stock),
                        ]
                    )
        else:
            stock = counts[crop] + private["seeds"].get(crop, 0)
            if stock < strategy.target_plants and me["money"] >= SEED_COST[crop]:
                orders.append(
                    [
                        "BUY_SEED",
                        crop,
                        min(strategy.seed_batch, strategy.target_plants - stock),
                    ]
                )

    if (
        me["money"] > strategy.buy_land_above
        and len(me["unlocked_quadrants"]) < 4
        and len(orders) < 10
    ):
        orders.append(["BUY_LAND"])
    return orders[:10]


def _direction(x: int, y: int, target_x: int, target_y: int) -> str:
    if x < target_x:
        return "EAST"
    if x > target_x:
        return "WEST"
    if y < target_y:
        return "SOUTH"
    if y > target_y:
        return "NORTH"
    return "PASS"


def _shed_tiles(board_size: int) -> list[tuple[int, int]]:
    half = board_size // 2
    return [(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)]


def _nearest(x: int, y: int, targets: list[tuple[int, int]]) -> tuple[int, int] | None:
    if not targets:
        return None
    return min(targets, key=lambda target: abs(x - target[0]) + abs(y - target[1]))


def _worker_actions(
    obs: dict[str, Any], strategy: Strategy, counts: dict[str, int]
) -> tuple[list[Any], list[list[Any]]]:
    me = obs["farms"][obs["player"]]
    tiles = me["tiles"]
    private = obs["private"]
    workers = [me["farmer"], *me["hands"]]
    inventories = private["inventories"]
    shed_access = _shed_tiles(len(tiles))

    tile_tasks: list[tuple[int, int, int, str]] = []
    empty_tiles: list[tuple[int, int]] = []
    empty_structures: dict[str, list[tuple[int, int]]] = {"COOP": [], "PASTURE": []}
    animals_need_feed: list[tuple[int, int]] = []
    structure_counts = {"COOP": 0, "PASTURE": 0}
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            if tile == "LOCKED":
                continue
            if tile is None:
                empty_tiles.append((x, y))
            elif tile.get("kind") == "WEED":
                tile_tasks.append((3, x, y, "DIG"))
            elif tile.get("kind") == "PLANT":
                if tile.get("yield_units", 0) > 0:
                    tile_tasks.append((1, x, y, "HARVEST"))
                elif not tile.get("watered_today", False):
                    tile_tasks.append((2, x, y, "WATER"))
            elif tile.get("kind") in empty_structures:
                structure_counts[tile["kind"]] += 1
                if "animal" not in tile:
                    empty_structures[tile["kind"]].append((x, y))
                else:
                    if not tile.get("fed_today", False):
                        animals_need_feed.append((x, y))
                        tile_tasks.append((0, x, y, "FEED"))
                    elif tile.get("yield_units", 0) > 0:
                        tile_tasks.append((1, x, y, "HARVEST"))
                    elif tile.get("fertilizer_available", False):
                        tile_tasks.append((2, x, y, "COLLECT_FERTILIZER"))
                    elif not tile.get("cared_today", False):
                        tile_tasks.append((3, x, y, "CARE"))

    claimed: set[tuple[int, int]] = set()
    seed_stock = dict(private["seeds"])
    shed_stock = dict(private["shed"])
    target_structures = {"COOP": 0, "PASTURE": 0}
    for animal, target in strategy.animals:
        target_structures[ANIMAL_DATA[animal][0]] += target
    structures_to_build = {
        structure: max(0, target - structure_counts[structure])
        for structure, target in target_structures.items()
    }
    actions: list[list[Any]] = []

    for index, (x, y) in enumerate(workers):
        inventory = inventories[index] if index < len(inventories) else {}
        tile = tiles[y][x]
        action: list[Any] = ["PASS"]

        carried_animal = next(
            (animal for animal in ANIMAL_DATA if inventory.get(animal, 0) > 0), None
        )
        if carried_animal and isinstance(tile, dict):
            structure = ANIMAL_DATA[carried_animal][0]
            if tile.get("kind") == structure and "animal" not in tile:
                action = ["PLACE", carried_animal]
                claimed.add((x, y))

        current_task = next(
            (
                task
                for task in sorted(tile_tasks)
                if task[1:3] == (x, y) and (x, y) not in claimed
            ),
            None,
        )
        if action == ["PASS"] and current_task:
            operation = current_task[3]
            if operation != "FEED" or inventory.get("WHEAT", 0) > 0:
                action = [operation]
                claimed.add((x, y))

        if action == ["PASS"] and animals_need_feed and inventory.get("WHEAT", 0) <= 0:
            if (x, y) in shed_access and shed_stock.get("WHEAT", 0) > 0:
                amount = min(4, shed_stock["WHEAT"])
                action = ["PICKUP", "WHEAT", amount]
                shed_stock["WHEAT"] -= amount
            else:
                target = _nearest(x, y, shed_access)
                if target:
                    action = [_direction(x, y, *target)]

        if action == ["PASS"] and carried_animal:
            structure = ANIMAL_DATA[carried_animal][0]
            targets = [
                target
                for target in empty_structures[structure]
                if target not in claimed
            ]
            target = _nearest(x, y, targets)
            if target:
                action = [_direction(x, y, *target)]
                claimed.add(target)

        if action == ["PASS"] and strategy.animals and not carried_animal:
            available_animal = next(
                (
                    animal
                    for animal, _ in strategy.animals
                    if shed_stock.get(animal, 0) > 0
                    and empty_structures[ANIMAL_DATA[animal][0]]
                ),
                None,
            )
            if available_animal:
                if (x, y) in shed_access:
                    action = ["PICKUP", available_animal, 1]
                    shed_stock[available_animal] -= 1
                else:
                    target = _nearest(x, y, shed_access)
                    if target:
                        action = [_direction(x, y, *target)]

        if action == ["PASS"] and tile is None and (x, y) not in claimed:
            if strategy.animals and any(structures_to_build.values()):
                structure = next(
                    structure
                    for structure in ("COOP", "PASTURE")
                    if structures_to_build[structure] > 0
                )
                operation = f"BUILD_{structure}"
                action = [operation]
                structures_to_build[structure] -= 1
                claimed.add((x, y))
            elif not strategy.animals:
                crop = _choose_crop(obs, strategy, counts)
                if strategy.crop_mode == "balanced":
                    crop = min(
                        (
                            candidate
                            for candidate in CROPS
                            if seed_stock.get(candidate, 0) > 0
                        ),
                        key=lambda candidate: (
                            counts[candidate],
                            CROPS.index(candidate),
                        ),
                        default=crop,
                    )
                if seed_stock.get(crop, 0) > 0:
                    action = ["PLANT", crop]
                    seed_stock[crop] -= 1
                    counts[crop] += 1
                    claimed.add((x, y))

        if action == ["PASS"]:
            available_tasks = [
                (task_x, task_y)
                for _, task_x, task_y, operation in sorted(tile_tasks)
                if (task_x, task_y) not in claimed
                and (operation != "FEED" or inventory.get("WHEAT", 0) > 0)
            ]
            if not available_tasks and not strategy.animals:
                has_seed = any(seed_stock.get(crop, 0) > 0 for crop in CROPS)
                if has_seed:
                    available_tasks = [
                        target for target in empty_tiles if target not in claimed
                    ]
            target = _nearest(x, y, available_tasks)
            if target:
                action = [_direction(x, y, *target)]
                claimed.add(target)

        actions.append(action)

    return actions[0], actions[1:]


def run_strategy(obs: dict[str, Any], strategy: Strategy) -> dict[str, Any]:
    """Build one complete action while keeping malformed observations harmless."""
    try:
        me = obs["farms"][obs["player"]]
        counts = _crop_counts(me["tiles"])
        market = _market_orders(obs, strategy, counts)
        farmer, hands = _worker_actions(obs, strategy, counts)
        return {"farmer": farmer, "hands": hands, "market": market}
    except (KeyError, TypeError, ValueError, IndexError):
        hand_count = len(obs.get("farms", [{}])[obs.get("player", 0)].get("hands", []))
        return {
            "farmer": ["PASS"],
            "hands": [["PASS"] for _ in range(hand_count)],
            "market": [],
        }
