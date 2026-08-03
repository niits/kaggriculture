"""Type contracts for Kaggriculture's JSON observation and action payloads."""

from typing import Literal, NotRequired, TypedDict

Crop = Literal["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"]
Animal = Literal["GOOSE", "COW", "SHEEP"]
AnimalProduct = Literal["EGG", "MILK", "WOOL"]
Product = Crop | AnimalProduct | Literal["FERTILIZER"]
PurchasableProduct = Literal["WHEAT", "FERTILIZER"]
ShedItem = Product | Animal
Quadrant = Literal["NW", "NE", "SW", "SE"]
Shop = Literal[
    "BAKERY",
    "PIZZA_SHOP",
    "BRUNCH_SPOT",
    "YARN_STORE",
    "ICE_CREAM_SHOP",
    "PET_CAFE",
    "SMOOTHIE_SHOP",
    "FARMERS_MARKET",
]
Position = list[int]
Inventory = dict[ShedItem, int]
SeedInventory = dict[Crop, int]


class PlantTile(TypedDict):
    kind: Literal["PLANT"]
    crop: Crop
    planted_day: int
    watered_today: bool
    consecutive_unwatered: int
    yield_units: int
    max_lifespan_step: int
    fertilized_until_day: int


class WeedTile(TypedDict):
    kind: Literal["WEED"]


class StructureTile(TypedDict):
    """An unoccupied animal structure."""

    kind: Literal["COOP", "PASTURE"]


class AnimalTile(TypedDict):
    """An occupied coop or pasture."""

    kind: Literal["COOP", "PASTURE"]
    animal: Animal
    placed_day: int
    yield_units: int
    fed_today: bool
    consecutive_unfed: int
    cared_today: bool
    fertilizer_available: bool
    pending_care_bonus: int


Tile = Literal[None, "LOCKED"] | PlantTile | WeedTile | StructureTile | AnimalTile
Board = list[list[Tile]]


class FarmState(TypedDict):
    money: float
    tiles: Board
    farmer: Position
    hands: list[Position]
    unlocked_quadrants: list[Quadrant]
    hires_today: int


class PrivateState(TypedDict):
    shed: Inventory
    seeds: SeedInventory
    inventories: list[Inventory]


PriceShape = Literal["linear", "sq", "sqrt", "log", "log10"]


class MarketParameters(TypedDict):
    base: int
    I0: int
    T: int
    below_func: PriceShape
    below_target: float
    above_func: PriceShape
    above_target: float


class MarketParameterOverride(TypedDict, total=False):
    base: int
    I0: int
    T: int
    below_func: PriceShape
    below_target: float
    above_func: PriceShape
    above_target: float


class MarketState(TypedDict):
    inventory: dict[Product, int]
    prices: dict[Product, int]
    params: NotRequired[dict[Product, MarketParameters]]


class TownState(TypedDict):
    unlocked_shops: list[Shop]


class Observation(TypedDict):
    player: int
    step: int
    day: int
    hour: int
    farms: list[FarmState]
    private: PrivateState
    market: MarketState
    town: TownState
    remainingOverageTime: NotRequired[float]


MovementActionName = Literal["NORTH", "SOUTH", "EAST", "WEST", "PASS"]
UnitActionName = (
    MovementActionName
    | Literal[
        "PICKUP",
        "PLACE",
        "DROP",
        "PLANT",
        "WATER",
        "HARVEST",
        "FERTILIZE",
        "BUILD_COOP",
        "BUILD_PASTURE",
        "FEED",
        "COLLECT_FERTILIZER",
        "CARE",
        "DIG",
    ]
)
MarketActionName = Literal[
    "BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL", "HIRE", "BUY_LAND"
]
UnitAction = list[UnitActionName | ShedItem | int]
MarketOrder = list[
    MarketActionName | Crop | PurchasableProduct | Animal | Product | int
]


class Action(TypedDict):
    farmer: UnitAction
    hands: list[UnitAction]
    market: list[MarketOrder]


class Configuration(TypedDict, total=False):
    episodeSteps: int
    actTimeout: float
    runTimeout: float
    boardSize: int
    startingMoney: float
    maxMarketOrdersPerTurn: int
    turnsPerDay: int
    shedCapacity: int
    weedSpawnChance: float
    townShopUnlockInterval: int
    townShopSellInterval: int
    townCenterSellInterval: int
    farmHandCostMult: float
    marketParams: dict[Product, MarketParameterOverride]
    seed: int | None


__all__ = [
    "Action",
    "Animal",
    "AnimalProduct",
    "AnimalTile",
    "Board",
    "Configuration",
    "Crop",
    "FarmState",
    "Inventory",
    "MarketActionName",
    "MarketOrder",
    "MarketParameterOverride",
    "MarketParameters",
    "MarketState",
    "MovementActionName",
    "Observation",
    "PlantTile",
    "Position",
    "PriceShape",
    "PrivateState",
    "Product",
    "PurchasableProduct",
    "Quadrant",
    "SeedInventory",
    "ShedItem",
    "Shop",
    "StructureTile",
    "Tile",
    "TownState",
    "UnitAction",
    "UnitActionName",
    "WeedTile",
]
