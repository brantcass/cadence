"""
Read-only Garmin connectivity probe.

Run this ONCE after setting your Garmin credentials in .env, to confirm the live
pull works against YOUR account before relying on it in the app. It logs in,
pulls a few recent activities and one day of recovery, runs them through the
mapper, and prints what the app would see. It writes nothing and changes nothing
on Garmin's side.

    cd backend && python -m scripts.garmin_probe

If Garmin throttles the login or wants MFA, that surfaces here as a clean error
instead of silently falling back to sample data inside the running app.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the backend dir regardless of where this is invoked from.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from data import garmin_mapper  # noqa: E402


def main():
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")
    if not (email and password):
        print("No GARMIN_EMAIL / GARMIN_PASSWORD in .env — nothing to probe.")
        sys.exit(1)

    try:
        from garminconnect import Garmin
    except ImportError:
        print("garminconnect not installed. `pip install -r requirements.txt`.")
        sys.exit(1)

    print(f"Logging in as {email} ...")
    client = Garmin(email, password)
    client.login()
    print("Login OK.\n")

    raw = client.get_activities(0, 5)
    print(f"Pulled {len(raw)} recent activities. Mapped:")
    for a in garmin_mapper.map_activities(raw, resting_hr=55, max_hr=190):
        print(f"  {a['date']}  {a['type']:10} {a['distance_km']:>5} km  "
              f"{a['duration_min']:>5} min  hr={a['avg_hr']}  rpe={a['perceived_effort']}")

    end = garmin_mapper._latest_activity_day(raw)
    print(f"\nProbing 3 days of recovery ending {end} ...")
    series = garmin_mapper.build_recovery_series(client, days=3, end_day=end)
    for r in series:
        print(f"  {r['date']}  sleep={r.get('sleep_hours')}  "
              f"hrv={r.get('hrv_ms')}  rhr={r.get('resting_hr')}")

    if not raw:
        print("\nNo activities returned — the app will fall back to sample data.")
    else:
        print("\nLooks good. Set USE_LIVE_GARMIN=true and the app will use this.")


if __name__ == "__main__":
    main()
