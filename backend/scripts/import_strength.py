"""
Generate backend/data/strength_catalog.json from the athlete's PPL spreadsheet.

The spreadsheet is a 6-day Push/Pull/Legs split (one column per day). During a
marathon build the athlete only has TWO strength slots a week, so this script
also emits a curated condensed split — two full-body sessions that keep all the
main compounds and bias toward legs + pressing (climbing already covers pulling
and grip). The generated JSON is committed and is the source of truth the app
seeds its database from; rerun this only when the source plan changes.

    python -m scripts.import_strength ["C:\\path\\to\\Push, Pull, Legs.xlsx"]

The .xlsx itself is personal and lives outside the repo (default: Downloads).
"""

import json
import re
import sys
from pathlib import Path

_DEFAULT_XLSX = Path.home() / "Downloads" / "Push, Pull, Legs.xlsx"
_OUT = Path(__file__).resolve().parent.parent / "data" / "strength_catalog.json"

# Which lifts count as the trackable compounds (progress these by %1RM).
_COMPOUND_KEYS = ("squat", "dead", "bench", "overhead press", "pull up",
                  "pull-up", "hack squat", "leg press")

# Curated condensed split, referenced by exercise NAME (robust to id shifts).
# Bias: legs + push. Climbing covers pulling/grip, so only one gym pull remains.
_SESSION_A = ["Squat working set", "Romanian DL", "Overhead press",
              "Leg Press", "Long lever planks"]
_SESSION_B = ["Dead lift", "Bench press", "Weighted pull up",
              "Single leg calf raise", "Weighted L-sit hold"]


def _is_compound(text: str) -> bool:
    low = text.lower()
    return any(k in low for k in _COMPOUND_KEYS)


def parse_catalog(xlsx_path: Path) -> dict:
    import openpyxl
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb["Sheet1"]
    rows = list(ws.iter_rows(values_only=True))
    headers = rows[0]
    n_days = 6                     # first 6 columns are day templates

    exercises = []
    eid = 0
    for col in range(n_days):
        day_label = headers[col]
        for r in range(2, len(rows)):        # skip header row + "Dynamic stretch" row
            cell = rows[r][col] if col < len(rows[r]) else None
            if not cell:
                continue
            text = str(cell).strip()
            if "=" in text:
                name, scheme = (p.strip() for p in text.split("=", 1))
            else:
                name, scheme = text, ""
            pct = re.search(r"(\d{2,3})\s*%", text)
            eid += 1
            exercises.append({
                "id": eid,
                "day_label": day_label,
                "name": name,
                "scheme": scheme,
                "pct_1rm": int(pct.group(1)) if pct else None,
                "is_compound": _is_compound(text),
            })

    by_name = {e["name"]: e["id"] for e in exercises}

    def ids_for(names):
        missing = [n for n in names if n not in by_name]
        if missing:
            raise SystemExit(f"Condensed split references unknown lifts: {missing}")
        return [by_name[n] for n in names]

    return {
        "source": "Push, Pull, Legs.xlsx (6-day PPL split)",
        "exercises": exercises,
        "condensed_sessions": {
            "Strength A — legs + push": ids_for(_SESSION_A),
            "Strength B — full body + core": ids_for(_SESSION_B),
        },
        "progression_note": "Progress compound lifts weekly by % of 1RM (base/build); "
                            "maintain through peak; back off in the taper.",
    }


def main():
    xlsx = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_XLSX
    if not xlsx.exists():
        raise SystemExit(f"Spreadsheet not found: {xlsx}")
    catalog = parse_catalog(xlsx)
    _OUT.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {_OUT} — {len(catalog['exercises'])} exercises, "
          f"{len(catalog['condensed_sessions'])} condensed sessions.")


if __name__ == "__main__":
    main()
