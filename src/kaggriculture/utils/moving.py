from kaggriculture.models import MovementActionName


def get_direction(fx: int, fy: int, tx: int, ty: int) -> MovementActionName:
    """Calculates Manhattan directional vector for grid navigation."""
    if fx < tx:
        return "EAST"
    if fx > tx:
        return "WEST"
    if fy < ty:
        return "SOUTH"
    if fy > ty:
        return "NORTH"
    return "PASS"
