"""
Periodized training-plan engine.

Pure functions that lay out a marathon (or half / 10K) build from a start date
to a race date: a week-by-week macrocycle (Base -> Build -> Peak -> Taper) and a
day-by-day microcycle of concrete workouts. Like everything in `analytics/`, this
module touches no network, model, or database — it's math and scheduling over the
athlete's numbers, so it's deterministic and unit-testable.

Design choices worth knowing:

- **Progression comes from the long run and the quality workout, not a volume
  multiplier.** This athlete runs 3 times a week (the other days are strength and
  climbing), so weekly mileage is just the sum of three runs. Overload is the long
  run growing week to week and the quality session getting sharper by phase —
  which is exactly how 3-run marathon plans (e.g. FIRST / "Run Less, Run Faster")
  work.
- **Cutback weeks every 4th week.** Load steps down ~25% so adaptation catches up;
  ramping every single week is how people get hurt.
- **Paces are derived from threshold pace**, the one number the app already knows
  (measured or estimated). Easy / marathon / tempo / interval paces are fixed
  multiples of it, so a faster athlete gets a faster plan automatically.
- **Strength periodizes too:** heavy while there's room (Base/Build), maintenance
  through Peak, minimal in the Taper. You can't build max strength and peak
  marathon fitness in the same week.
"""

from datetime import date, timedelta

# Race presets: canonical distance + a sensible peak long run for that goal.
RACE_PRESETS = {
    "marathon":  {"name": "Marathon",       "distance_km": 42.195, "peak_long_km": 32.0},
    "half":      {"name": "Half marathon",  "distance_km": 21.0975, "peak_long_km": 22.0},
    "10k":       {"name": "10K",            "distance_km": 10.0,    "peak_long_km": 16.0},
    "fitness":   {"name": "Fitness block",  "distance_km": 21.0975, "peak_long_km": 20.0},
}

# Pace zones as multiples of threshold pace (min/km). Slower pace = bigger number,
# so easy/long runs have multipliers ABOVE 1 and intervals BELOW 1.
PACE_MULT = {
    "easy":      1.22,   # Z2 conversational
    "long":      1.18,   # long-run pace: aerobic, a touch quicker than pure easy
    "marathon":  1.09,   # goal marathon pace
    "tempo":     1.04,   # comfortably hard, ~Z3/low-Z4
    "threshold": 1.00,   # lactate threshold
    "interval":  0.95,   # Z5 VO2max reps
}

# Long-run ceiling as a fraction of goal distance is unnecessary here — presets
# give an explicit peak. A cutback week scales the week's long run and volume:
CUTBACK_SCALE = 0.75
CUTBACK_EVERY = 4        # every 4th week within Base/Build is a recovery week

TAPER_WEEKS = 3
PEAK_WEEKS = 3


# ---- small helpers ----

def _monday_on_or_before(d: date) -> date:
    """The Monday of the week containing `d` (weeks are Monday-anchored because
    the athlete's long run is on Monday)."""
    return d - timedelta(days=d.weekday())


def _mmss(min_per_km: float) -> str:
    """4.55 -> '4:33'. Shared display format for pace."""
    minutes = int(min_per_km)
    seconds = round((min_per_km - minutes) * 60)
    if seconds == 60:
        minutes, seconds = minutes + 1, 0
    return f"{minutes}:{seconds:02d}"


def pace_for(kind: str, threshold: float) -> float:
    """Canonical min/km for a workout kind, from the athlete's threshold pace."""
    return round(threshold * PACE_MULT[kind], 2)


def pace_label(kind: str, threshold: float) -> str:
    """'5:33/km (easy)' style label for a workout kind."""
    return f"{_mmss(pace_for(kind, threshold))}/km"


# ---- phase layout ----

def _phase_for_week(index: int, total: int) -> str:
    """Assign a phase to week `index` (1-based) of a `total`-week plan.

    Taper and Peak are fixed-length at the end; the rest splits ~45/55 into Base
    then Build. Short plans degrade gracefully (Peak/Taper shrink first).
    """
    taper = min(TAPER_WEEKS, max(1, total // 6))
    peak = min(PEAK_WEEKS, max(1, (total - taper) // 5))
    remaining = total - taper - peak
    base = round(remaining * 0.45)
    build = remaining - base

    if index > total - taper:
        return "Taper"
    if index > total - taper - peak:
        return "Peak"
    if index <= base:
        return "Base"
    return "Build"


def _phase_bounds(total: int):
    """Ordered [(phase, week_count)] for the overview."""
    counts = {}
    order = []
    for i in range(1, total + 1):
        p = _phase_for_week(i, total)
        if p not in counts:
            order.append(p)
        counts[p] = counts.get(p, 0) + 1
    return [(p, counts[p]) for p in order]


# ---- long-run progression ----

def _long_run_km(index: int, total: int, phase: str, start_long: float,
                 peak_long: float, is_cutback: bool) -> float:
    """Long-run distance for a given week.

    Ramps from `start_long` toward `peak_long` across everything up to Peak, holds
    near peak through Peak, then steps down through the Taper. Cutback weeks pull
    the ramp back so the next hard week starts from a slightly lower rung.
    """
    taper = min(TAPER_WEEKS, max(1, total // 6))
    peak = min(PEAK_WEEKS, max(1, (total - taper) // 5))
    ramp_weeks = total - taper                      # Base+Build+Peak all ramp/hold

    if phase == "Taper":
        # Count how deep into the taper we are (1..taper) and shed distance.
        into_taper = index - (total - taper)
        taper_scale = [0.75, 0.55, 0.35]
        scale = taper_scale[min(into_taper - 1, len(taper_scale) - 1)]
        return round(peak_long * scale, 1)

    # Linear ramp from start_long to peak_long over the ramp weeks.
    frac = (index - 1) / max(1, ramp_weeks - 1)
    km = start_long + (peak_long - start_long) * frac
    km = min(km, peak_long)
    if is_cutback:
        km *= CUTBACK_SCALE
    return round(km, 1)


# ---- quality workout selection ----

def _quality_workout(phase: str, index: int, threshold: float, race_name: str):
    """Pick the week's quality session (title + detail + distance) by phase.

    A small rotation keeps stimulus varied without randomness (deterministic on
    the week index, so the plan is reproducible).
    """
    mp = pace_label("marathon", threshold)
    tempo = pace_label("tempo", threshold)
    thr = pace_label("threshold", threshold)
    ival = pace_label("interval", threshold)

    if phase == "Base":
        rotation = [
            ("Strides + easy", f"8 km easy, finish with 6 × 20 s strides (relaxed, fast). Builds leg speed without load.", 8.0),
            ("Short tempo", f"2 km easy + 3 × 5 min @ tempo ({tempo}) w/ 90 s jog + 2 km easy.", 10.0),
        ]
    elif phase == "Build":
        rotation = [
            ("Threshold intervals", f"2 km w-up + 4 × 1.5 km @ threshold ({thr}) w/ 90 s jog + 2 km c-down.", 13.0),
            ("Marathon-pace run", f"3 km easy + 8 km @ marathon pace ({mp}) + 2 km easy.", 13.0),
            ("Tempo", f"2 km w-up + 6 km @ tempo ({tempo}) + 2 km c-down.", 12.0),
        ]
    elif phase == "Peak":
        rotation = [
            ("Long MP segments", f"3 km easy + 3 × 3 km @ marathon pace ({mp}) w/ 1 km float + 2 km easy.", 15.0),
            ("Threshold", f"2 km w-up + 5 × 1.6 km @ threshold ({thr}) w/ 2 min jog + 2 km c-down.", 15.0),
        ]
    else:  # Taper
        rotation = [
            ("Race-pace sharpener", f"2 km easy + 4 km @ marathon pace ({mp}) + 1 km easy. Legs sharp, not tired.", 8.0),
            ("Short VO2 touch", f"2 km w-up + 5 × 2 min @ interval ({ival}) w/ 2 min jog + 2 km c-down.", 8.0),
        ]

    title, detail, dist = rotation[(index - 1) % len(rotation)]
    return title, detail, dist


# ---- strength periodization ----

def _strength_load(phase: str) -> str:
    """How hard the strength days go, given the running phase."""
    return {
        "Base": "heavy", "Build": "heavy",
        "Peak": "maintain", "Taper": "light",
    }[phase]


# ---- the microcycle (one week of days) ----

_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _week_sessions(week_start: date, phase: str, index: int, total: int,
                   long_km: float, threshold: float, race_name: str,
                   options: dict) -> list:
    """Build the 7-day schedule for a week.

    Default layout (all overridable via `options`):
      Mon long run · Tue strength A · Wed quality run · Thu climbing ·
      Fri rest · Sat easy run · Sun rest (fresh for Monday's long run).
    """
    long_day = options.get("long_run_day", 0)      # Monday
    quality_day = options.get("quality_day", 2)    # Wednesday
    easy_day = options.get("easy_day", 5)          # Saturday
    strength_a_day = options.get("strength_a_day", 1)  # Tuesday
    strength_b_day = options.get("strength_b_day", 4)  # Friday
    climb_day = options.get("climb_day", 3)            # Thursday

    easy_km = 8.0 if phase != "Taper" else 6.0
    q_title, q_detail, q_km = _quality_workout(phase, index, threshold, race_name)
    strength_load = _strength_load(phase)

    sessions = []
    for dow in range(7):
        d = week_start + timedelta(days=dow)
        name = _DAY_NAMES[dow]

        if dow == long_day:
            marathon_pace = pace_label("marathon", threshold)
            detail = f"{long_km:g} km easy @ {pace_label('long', threshold)}."
            # In Build/Peak, finish some long runs at marathon effort.
            if phase in ("Build", "Peak") and index % 2 == 0:
                detail = (f"{long_km:g} km: mostly easy, last "
                          f"{min(8, round(long_km * 0.3)):g} km @ marathon pace ({marathon_pace}).")
            sessions.append(_run(name, d, "Long run", detail, long_km,
                                 pace_for("long", threshold), "long"))
        elif dow == quality_day:
            sessions.append(_run(name, d, q_title, q_detail, q_km,
                                 pace_for("tempo", threshold), "quality"))
        elif dow == easy_day:
            sessions.append(_run(name, d, "Easy run",
                                 f"{easy_km:g} km easy @ {pace_label('easy', threshold)} (Z2, conversational).",
                                 easy_km, pace_for("easy", threshold), "easy"))
        elif dow == strength_a_day:
            sessions.append(_strength(name, d, "Strength A — legs + push", strength_load))
        elif dow == strength_b_day:
            sessions.append(_strength(name, d, "Strength B — full body + core", strength_load))
        elif dow == climb_day:
            sessions.append(_cross(name, d, "Climbing",
                                   "Bouldering / routes — controlled volume. Covers your pulling "
                                   "and grip work. Ease off if legs feel heavy before Monday's long run."))
        else:
            sessions.append(_rest(name, d))
    return sessions


def _run(day, d, title, detail, distance_km, pace, intensity):
    return {
        "day": day, "date": d.isoformat(), "kind": "run",
        "title": title, "detail": detail,
        "distance_km": round(distance_km, 1),
        "target_pace_min_per_km": pace,
        "duration_min": round(distance_km * pace),
        "intensity": intensity,
    }


def _strength(day, d, title, load):
    return {
        "day": day, "date": d.isoformat(), "kind": "strength",
        "title": title, "detail": f"~50 min. Intensity: {load}. See the strength catalog for lifts.",
        "load": load, "intensity": "strength", "duration_min": 50,
    }


def _cross(day, d, title, detail):
    return {"day": day, "date": d.isoformat(), "kind": "cross",
            "title": title, "detail": detail, "intensity": "cross", "duration_min": 60}


def _rest(day, d):
    return {"day": day, "date": d.isoformat(), "kind": "rest",
            "title": "Rest", "detail": "Full rest or light mobility.", "intensity": "rest"}


def _race_day(day, d, preset):
    return {
        "day": day, "date": d.isoformat(), "kind": "race",
        "title": f"🏁 RACE DAY — {preset['name']}",
        "detail": f"{preset['distance_km']:g} km. Trust the taper. Even pacing, fuel early.",
        "distance_km": round(preset["distance_km"], 1),
        "intensity": "race",
    }


# ---- current-fitness snapshot (grounds the plan in real data) ----

def current_fitness(activities) -> dict:
    """Recent weekly volume + longest run, from the athlete's own history.

    Uses a late import of training_metrics to avoid a circular import; both are
    leaf-ish analytics modules but plan.py is the higher-level one.
    """
    from analytics import training_metrics as metrics
    wow = metrics.week_over_week(activities, weeks=4)["weeks"]
    weekly = [w["total_km"] for w in wow if w["total_km"] > 0]
    current_weekly_km = round(sum(weekly) / len(weekly), 1) if weekly else 25.0
    longest = max((w["longest_run_km"] for w in wow), default=0) or 12.0
    return {"current_weekly_km": current_weekly_km, "recent_longest_run_km": round(longest, 1)}


# ---- the public entry point ----

def build_plan(start_date: date, race_date: date, athlete: dict, activities: list,
               race_type: str = "marathon", options: dict = None) -> dict:
    """Build the full periodized plan from `start_date` through race week.

    `athlete` supplies `threshold_pace_min_per_km` (measured or estimated).
    `activities` grounds the starting long run in what they've recently run.
    `options` overrides scheduling (long_run_day, quality_day, ...).
    """
    options = options or {}
    preset = RACE_PRESETS.get(race_type, RACE_PRESETS["marathon"])
    threshold = athlete.get("threshold_pace_min_per_km") or 5.0

    first_monday = _monday_on_or_before(start_date)
    race_monday = _monday_on_or_before(race_date)
    total_weeks = max(1, (race_monday - first_monday).days // 7 + 1)

    fitness = current_fitness(activities)
    # Start the long run near their recent longest (clamped to a sane range) and
    # climb toward the preset peak.
    start_long = min(max(fitness["recent_longest_run_km"], 12.0), 20.0)
    peak_long = preset["peak_long_km"]

    weeks = []
    for i in range(1, total_weeks + 1):
        phase = _phase_for_week(i, total_weeks)
        week_start = first_monday + timedelta(weeks=i - 1)
        # Cutback only inside Base/Build, and never the last week of Build.
        is_cutback = phase in ("Base", "Build") and i % CUTBACK_EVERY == 0
        long_km = _long_run_km(i, total_weeks, phase, start_long, peak_long, is_cutback)
        sessions = _week_sessions(week_start, phase, i, total_weeks, long_km,
                                  threshold, preset["name"], options)
        # Mark the actual race day (it usually lands in the final week, on a day
        # the template would otherwise call easy/rest).
        for j, s in enumerate(sessions):
            if s["date"] == race_date.isoformat():
                sessions[j] = _race_day(s["day"], race_date, preset)
        run_km = round(sum(s.get("distance_km", 0) for s in sessions), 1)
        weeks.append({
            "index": i,
            "phase": phase,
            "week_of": week_start.isoformat(),
            "is_cutback": is_cutback,
            "focus": _phase_focus(phase, is_cutback),
            "long_run_km": long_km,
            "target_run_km": run_km,
            "sessions": sessions,
        })

    return {
        "race": {
            "type": race_type,
            "name": preset["name"],
            "date": race_date.isoformat(),
            "distance_km": preset["distance_km"],
        },
        "start_date": first_monday.isoformat(),
        "weeks_to_race": total_weeks,
        "athlete_snapshot": {
            "threshold_pace_min_per_km": threshold,
            "threshold_pace": f"{_mmss(threshold)}/km",
            "threshold_pace_estimated": bool(athlete.get("threshold_pace_estimated")),
            "current_weekly_km": fitness["current_weekly_km"],
            "start_long_run_km": start_long,
            "peak_long_run_km": peak_long,
        },
        "paces": {kind: {"min_per_km": pace_for(kind, threshold),
                         "label": f"{_mmss(pace_for(kind, threshold))}/km"}
                  for kind in PACE_MULT},
        "phases": [{"phase": p, "weeks": n} for p, n in _phase_bounds(total_weeks)],
        "weeks": weeks,
    }


def _phase_focus(phase: str, is_cutback: bool) -> str:
    if is_cutback:
        return "Cutback week — volume steps down so your body absorbs the work."
    return {
        "Base": "Aerobic base — easy volume, light speed, build the engine.",
        "Build": "Build — threshold and marathon-pace work, long run grows.",
        "Peak": "Peak — biggest long runs and race-specific pace at highest load.",
        "Taper": "Taper — shed fatigue, keep sharpness, arrive fresh.",
    }[phase]


def upcoming_weeks(plan: dict, as_of: date, count: int = 1) -> list:
    """The `count` plan weeks at or after `as_of` — what the coach usually wants."""
    weeks = [w for w in plan["weeks"] if date.fromisoformat(w["week_of"]) + timedelta(days=6) >= as_of]
    return weeks[:count]
