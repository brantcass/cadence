"""
Tests for units.py — plain asserts, no pytest needed.

Run from the backend dir:   python -m analytics.test_units

Why no framework: the app has no test dependency yet, and unit conversion is
simple enough that a handful of asserts + a round-trip check is plenty. The
round-trip tests (value -> other system -> back) are the important ones: they
catch a swapped constant or an inverted pace formula, which is the whole risk.
"""

from analytics import units

# Tolerance for float comparisons — conversions aren't exact in binary.
EPS = 1e-9


def approx(a, b, eps=EPS):
    return abs(a - b) == 0 or abs(a - b) < eps


def test_known_values():
    # A marathon is 42.195 km ≈ 26.2188 mi.
    assert approx(units.km_to_mi(42.195), 26.218757456454306)
    # 100 kg ≈ 220.462 lb.
    assert approx(units.kg_to_lb(100.0), 220.46226218487757)
    # 5:00/km pace -> per mile is LARGER (a mile takes longer than a km).
    assert units.pace_per_km_to_per_mi(5.0) > 5.0
    assert approx(units.pace_per_km_to_per_mi(5.0), 8.04672)


def test_round_trips():
    # Convert out and back; we must land where we started.
    for km in (0.0, 1.0, 5.0, 16.1, 42.195):
        assert approx(units.mi_to_km(units.km_to_mi(km)), km)
    for kg in (0.0, 20.0, 61.2, 142.5):
        assert approx(units.lb_to_kg(units.kg_to_lb(kg)), kg)
    for pace in (3.5, 4.55, 6.0):
        assert approx(units.pace_per_mi_to_per_km(units.pace_per_km_to_per_mi(pace)), pace)


def test_formatters():
    assert units.format_distance(16.1, units.METRIC) == "16.1 km"
    assert units.format_distance(16.09344, units.IMPERIAL) == "10.0 mi"
    assert units.format_pace(4.55, units.METRIC) == "4:33/km"
    # 4.55 min/km * 1.609344 = 7.3225 min/mi -> 7:19/mi
    assert units.format_pace(4.55, units.IMPERIAL) == "7:19/mi"
    assert units.format_pace(None, units.METRIC) == "—"
    assert units.format_weight(61.235, units.IMPERIAL) == "135.0 lb"
    # mm:ss carry: 4.999 min rounds up to 5:00, not 4:60.
    assert units._mmss(4.999) == "5:00"


def _run():
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n{len(tests)} test groups passed.")


if __name__ == "__main__":
    _run()
