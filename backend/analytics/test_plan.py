"""
Plain-assert tests for the periodization engine. No pytest — run with:

    python -m analytics.test_plan        (from the backend/ directory)

Checks the plan's structural invariants: the shape a coach and a UI depend on,
not the exact prose of a workout (which is allowed to evolve).
"""

from datetime import date

from analytics import plan

# A fixed athlete + minimal history so the tests are deterministic.
_ATHLETE = {"threshold_pace_min_per_km": 4.55}
_ACTIVITIES = [
    {"date": "2026-09-07", "type": "run", "distance_km": 10.0, "duration_min": 50, "perceived_effort": 5},
    {"date": "2026-09-14", "type": "run", "distance_km": 15.0, "duration_min": 78, "perceived_effort": 6},
    {"date": "2026-09-20", "type": "run", "distance_km": 12.0, "duration_min": 60, "perceived_effort": 5},
]

_START = date(2026, 9, 21)
_RACE = date(2027, 2, 14)


def _plan():
    return plan.build_plan(_START, _RACE, _ATHLETE, _ACTIVITIES, "marathon")


def test_week_count_and_dates():
    p = _plan()
    # 2026-09-21 (a Monday) through the week of 2027-02-14 inclusive.
    assert p["weeks_to_race"] == 21, p["weeks_to_race"]
    assert p["weeks"][0]["week_of"] == "2026-09-21"
    # Weeks are contiguous Mondays.
    for a, b in zip(p["weeks"], p["weeks"][1:]):
        da = date.fromisoformat(a["week_of"])
        db = date.fromisoformat(b["week_of"])
        assert (db - da).days == 7


def test_phases_ordered():
    p = _plan()
    phases = [ph["phase"] for ph in p["phases"]]
    assert phases == ["Base", "Build", "Peak", "Taper"], phases
    # Taper is the last thing before the race, and Peak precedes it.
    assert p["weeks"][-1]["phase"] == "Taper"


def test_long_run_peaks_then_tapers():
    p = _plan()
    longs = [w["long_run_km"] for w in p["weeks"]]
    peak = max(longs)
    assert peak == p["athlete_snapshot"]["peak_long_run_km"] == 32.0
    # The peak long run happens before the taper, and the taper is strictly lower.
    peak_week = longs.index(peak)
    taper_start = next(i for i, w in enumerate(p["weeks"]) if w["phase"] == "Taper")
    assert peak_week < taper_start
    assert all(l < peak for l in longs[taper_start:])


def test_cutback_weeks_reduce_load():
    p = _plan()
    for i, w in enumerate(p["weeks"][1:], start=1):
        if w["is_cutback"]:
            prev = p["weeks"][i - 1]
            assert w["long_run_km"] < prev["long_run_km"], w["week_of"]


def test_week_structure_is_3_runs_2_strength():
    p = _plan()
    wk = next(w for w in p["weeks"] if w["phase"] == "Build")
    kinds = [s["kind"] for s in wk["sessions"]]
    assert len(wk["sessions"]) == 7
    assert kinds.count("run") == 3
    assert kinds.count("strength") == 2
    assert kinds.count("cross") == 1     # climbing
    assert kinds.count("rest") == 1


def test_paces_derived_from_threshold():
    p = _plan()
    # Easy is slower (bigger min/km) than threshold; interval is faster.
    assert p["paces"]["easy"]["min_per_km"] > 4.55
    assert p["paces"]["interval"]["min_per_km"] < 4.55
    assert p["paces"]["marathon"]["label"].endswith("/km")


def test_race_day_marked():
    p = _plan()
    race_sessions = [s for w in p["weeks"] for s in w["sessions"] if s["kind"] == "race"]
    assert len(race_sessions) == 1
    assert race_sessions[0]["date"] == "2027-02-14"


def test_deterministic():
    assert _plan() == _plan()


def test_estimated_threshold_flag_flows_through():
    athlete = {"threshold_pace_min_per_km": 4.8, "threshold_pace_estimated": True}
    p = plan.build_plan(_START, _RACE, athlete, _ACTIVITIES, "marathon")
    assert p["athlete_snapshot"]["threshold_pace_estimated"] is True


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n{len(tests)} tests passed.")


if __name__ == "__main__":
    _run_all()
