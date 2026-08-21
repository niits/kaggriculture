"""Plan-ahead agent - simulate future income, invest only when ROI is positive."""

from typing import Any

from kaggriculture.models import (
    Action,
    MarketOrder,
    Observation,
    UnitAction,
)
from kaggriculture.utils.moving import get_direction

TOTAL_DAYS = 30
TURNS_PER_DAY = 24
SHED_FULL = 80
SAFETY = 500

CROPS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")
PRODUCTS = CROPS + ("EGG", "MILK", "WOOL")

CROP = {
    "WHEAT":      {"cost": 10,  "base": 25,  "type": "one_time",
                   "first": 2,  "max_day": 4, "max_yield": 6, "life": 6},
    "CARROT":     {"cost": 20,  "base": 35,  "type": "one_time",
                   "first": 2,  "max_day": 3, "max_yield": 4, "life": 4},
    "TOMATO":     {"cost": 50,  "base": 60,  "type": "ongoing",
                   "first": 8,  "interval": 1, "max_cumulative": 4},
    "STRAWBERRY": {"cost": 100, "base": 120, "type": "ongoing",
                   "first": 10, "interval": 2, "max_cumulative": 4},
    "MELON":      {"cost": 80,  "base": 250, "type": "one_time",
                   "first": 10, "max_day": 12, "max_yield": 6, "life": 16},
}

BASE_PRICE = {c: d["base"] for c, d in CROP.items()}
BASE_PRICE.update({"EGG": 50, "MILK": 160, "WOOL": 200})


def _shed_tiles(board_size: int) -> list[tuple[int, int]]:
    half = board_size // 2
    return [(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)]


def _count(tiles: list[list[Any]], kind: str | None = None, crop: str | None = None) -> int:
    n = 0
    for row in tiles:
        for t in row:
            if not isinstance(t, dict) or t.get("kind") != kind:
                continue
            if crop and t.get("crop") != crop:
                continue
            n += 1
    return n


def _empty(tiles: list[list[Any]], unlocked: list[str]) -> list[tuple[int, int]]:
    b = len(tiles)
    h = b // 2
    q = {"NW": (0,0,h,h), "NE": (h,0,b,h), "SW": (0,h,h,b), "SE": (h,h,b,b)}
    out = []
    for name in unlocked:
        x0, y0, x1, y1 = q[name]
        for y in range(y0, y1):
            for x in range(x0, x1):
                if tiles[y][x] is None:
                    out.append((x, y))
    return out


def _project_revenue(crop: str, price: float, days_left: int) -> tuple[float, float]:
    d = CROP[crop]
    if d["type"] == "one_time":
        grow = d["first"]
        if days_left < grow:
            return 0, 0
        harvest_day = min(d["max_day"], days_left)
        base_yield = d["max_yield"]
        bonus_window_start = (d["max_day"] + 1) // 2
        bonus_days = max(0, min(harvest_day, d["max_day"]) - bonus_window_start + 1)
        total_yield = base_yield + bonus_days
        revenue = total_yield * price
        cost = d["cost"]
        profit = revenue - cost
        roi = profit / cost if cost > 0 else 0
        daily_roi = roi / max(harvest_day, 1)
        return profit, daily_roi
    else:
        first = d["first"]
        if days_left < first:
            return 0, 0
        interval = d["interval"]
        production_days = (days_left - first) // interval + 1
        total_yield = min(production_days, d["max_cumulative"])
        revenue = total_yield * price
        cost = d["cost"]
        profit = revenue - cost
        roi = profit / cost if cost > 0 else 0
        daily_roi = roi / max(first + total_yield * interval, 1)
        return profit, daily_roi


def _select_crop(prices: dict[str, float], days_left: int, money: float) -> str:
    best, best_profit = "WHEAT", -999999
    for c in CROPS:
        p = prices.get(c, CROP[c]["base"])
        profit, _ = _project_revenue(c, p, days_left)
        if profit > best_profit:
            best, best_profit = c, profit
    return best


def _market(obs: Observation) -> list[MarketOrder]:
    me = obs["farms"][obs["player"]]
    priv = obs["private"]
    prices = obs["market"]["prices"]
    day = obs["day"]
    money = me["money"]
    tiles = me["tiles"]
    hands = me["hands"]
    unlocked = me["unlocked_quadrants"]
    days_left = TOTAL_DAYS - day
    empty = _empty(tiles, unlocked)
    plants = _count(tiles, "PLANT")
    orders: list[MarketOrder] = []

    for prod in PRODUCTS:
        qty = priv["shed"].get(prod, 0)
        if qty <= 0:
            continue
        base = BASE_PRICE[prod]
        p = prices.get(prod, base)
        if day >= 27 or sum(priv["shed"].values()) >= SHED_FULL or p >= base * 1.10:
            orders.append(["SELL", prod, qty])

    crop = _select_crop(prices, days_left, money)
    seeds = priv["seeds"].get(crop, 0)
    max_plantable = min(len(empty), TURNS_PER_DAY * 2)
    need = max(0, max_plantable - seeds)
    cost = CROP[crop]["cost"]
    if money > SAFETY + cost * 4:
        buy = min(need, 4)
        if buy > 0:
            orders.append(["BUY_SEED", crop, buy])

    if plants >= 15 and len(hands) < 2 and money > 2000:
        orders.append(["HIRE"])
    if plants >= 25 and len(hands) < 3 and money > 3000:
        orders.append(["HIRE"])
    if plants >= 20 and money > 4000 and len(unlocked) < 4:
        orders.append(["BUY_LAND"])

    return orders[:10]


def _workers(obs: Observation) -> tuple[UnitAction, list[UnitAction]]:
    me = obs["farms"][obs["player"]]
    priv = obs["private"]
    tiles = me["tiles"]
    workers = [me["farmer"]] + me["hands"]
    invs = priv["inventories"]
    day = obs["day"]
    days_left = TOTAL_DAYS - day

    crop = _select_crop(obs["market"]["prices"], days_left, me["money"])

    tasks: list[tuple[int, int, str]] = []
    empty: list[tuple[int, int]] = []
    for y, row in enumerate(tiles):
        for x, t in enumerate(row):
            if t == "LOCKED":
                continue
            if t is None:
                empty.append((x, y))
            elif isinstance(t, dict):
                k = t.get("kind")
                if k == "WEED":
                    tasks.append((x, y, "DIG"))
                elif k == "PLANT":
                    c = t.get("crop", "")
                    age = day - t.get("planted_day", 0)
                    if not t.get("watered_today"):
                        tasks.append((x, y, "WATER"))
                    elif t.get("yield_units", 0) > 0:
                        cd = CROP.get(c, {})
                        if cd.get("type") == "one_time" and age >= cd.get("first", 2):
                            tasks.append((x, y, "HARVEST"))
                        elif cd.get("type") == "ongoing":
                            interval = cd.get("interval", 1)
                            if (age - cd.get("first", 8)) % interval == 0 and age >= cd.get("first", 8):
                                tasks.append((x, y, "HARVEST"))

    claimed: set[tuple[int, int]] = set()
    seed_stock = dict(priv["seeds"])
    acts: list[UnitAction] = []

    for idx, (wx, wy) in enumerate(workers):
        act: UnitAction = ["PASS"]

        cur = next(
            ((tx, ty, op) for tx, ty, op in tasks if (tx, ty) == (wx, wy) and (wx, wy) not in claimed),
            None,
        )
        if cur:
            act = [cur[2]]
            claimed.add((wx, wy))

        if act == ["PASS"] and (wx, wy) not in claimed:
            if tiles[wy][wx] is None and seed_stock.get(crop, 0) > 0:
                act = ["PLANT", crop]
                seed_stock[crop] -= 1
                claimed.add((wx, wy))
            else:
                cands = [(tx, ty) for tx, ty in empty if (tx, ty) not in claimed and seed_stock.get(crop, 0) > 0]
                tks = [(tx, ty) for tx, ty, _ in tasks if (tx, ty) not in claimed]
                pool = cands if cands else tks
                if pool:
                    tx, ty = min(pool, key=lambda t: abs(wx-t[0])+abs(wy-t[1]))
                    act = [get_direction(wx, wy, tx, ty)]
                    claimed.add((tx, ty))

        acts.append(act)

    return acts[0], acts[1:]


def agent(obs: Observation) -> Action:
    try:
        m = _market(obs)
        f, h = _workers(obs)
        return {"farmer": f, "hands": h, "market": m}
    except Exception:
        n = len(obs.get("farms", [{}])[obs.get("player", 0)].get("hands", []))
        return {"farmer": ["PASS"], "hands": [["PASS"]]*n, "market": []}
