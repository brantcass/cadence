"""
Unit conversion + display formatting.

This is a LEAF module: pure functions, no imports from the rest of the app, no
I/O, no model. It exists so the whole codebase can keep storing and computing in
ONE canonical system — metric (km, kg, min/km) — and convert only at the edge,
right before a number is shown to the user or right as a typed-in number comes
back. Nothing in `training_metrics.py` should ever learn about the user's unit
preference; that logic lives here and in the frontend, and nowhere else.

"""

# Exact conversion constants (international definitions, not approximations).
_KM_PER_MILE = 1.609344
_KG_PER_POUND = 0.45359237

# The two systems the app supports. "metric" is canonical (what we store).
METRIC = "metric"
IMPERIAL = "imperial"


# ---- distance: kilometres <-> miles ----

def km_to_mi(km: float) -> float:
    return km / _KM_PER_MILE


def mi_to_km(mi: float) -> float:
    return mi * _KM_PER_MILE


# ---- weight: kilograms <-> pounds ----

def kg_to_lb(kg: float) -> float:
    return kg / _KG_PER_POUND


def lb_to_kg(lb: float) -> float:
    return lb * _KG_PER_POUND


# ---- pace: min/km <-> min/mi (note: inverse of distance) ----

def pace_per_km_to_per_mi(min_per_km: float) -> float:
    """A mile is longer, so minutes-per-mile is LARGER than minutes-per-km."""
    return min_per_km * _KM_PER_MILE


def pace_per_mi_to_per_km(min_per_mi: float) -> float:
    return min_per_mi / _KM_PER_MILE


# ---- display formatters (canonical metric value in, string out) ----

def _mmss(decimal_minutes: float) -> str:
    """4.55 -> '4:33'. Humans read pace as mm:ss, not decimal minutes."""
    minutes = int(decimal_minutes)
    seconds = round((decimal_minutes - minutes) * 60)
    if seconds == 60:            # e.g. 4.999 would render as 4:60
        minutes, seconds = minutes + 1, 0
    return f"{minutes}:{seconds:02d}"


def format_distance(km: float, system: str = METRIC, digits: int = 1) -> str:
    """Canonical km -> 'X.X mi' or 'X.X km' for display."""
    if system == IMPERIAL:
        return f"{round(km_to_mi(km), digits)} mi"
    return f"{round(km, digits)} km"


def format_pace(min_per_km: float, system: str = METRIC) -> str:
    """Canonical min/km -> '4:33/km' or '7:19/mi'."""
    if min_per_km is None:
        return "—"
    if system == IMPERIAL:
        return f"{_mmss(pace_per_km_to_per_mi(min_per_km))}/mi"
    return f"{_mmss(min_per_km)}/km"


def format_weight(kg: float, system: str = METRIC, digits: int = 1) -> str:
    """Canonical kg -> 'X.X lb' or 'X.X kg'. (Nothing feeds this until strength
    weights land, but it belongs with the other converters.)"""
    if system == IMPERIAL:
        return f"{round(kg_to_lb(kg), digits)} lb"
    return f"{round(kg, digits)} kg"
