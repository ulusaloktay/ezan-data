"""Compare the app's prayer times with official tables and derive per-country tunes.

For every country in registry/prayer_sources.json and every reference place,
diff = app time - official time (minutes) for each day both sources cover.
The tune is the number of minutes the app adds to each prayer:

- fajr (the app shows one time for both the end of suhoor and the start of
  fajr): minimise the largest error either way.
- sunrise (end of fajr time): never later than official  -> tune = -max(diff)
- dhuhr, asr, maghrib, isha: never earlier than official -> tune = -min(diff)
  (praying or breaking the fast before the official time is the worse error)

Each reference place gets its own tune ("regions": the app uses the nearest
one within radius_km). The country-wide tune, used farther away, takes the
worst case over all places, so it is on the safe side everywhere we measured.
Writes prayer_tune.json and reports/prayer/<CC>.json.

    python3 scripts/prayer_check.py [--country TR]
"""

import argparse
import statistics
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, load_json, save_json  # noqa: E402
from prayer_sources import FETCHERS, PRAYERS, aladhan  # noqa: E402

REGISTRY = ROOT / "registry" / "prayer_sources.json"
TUNE = ROOT / "prayer_tune.json"
REPORTS = ROOT / "reports" / "prayer"
MAX_TUNE = 15
# A day whose difference is this far from the median is more likely a typo in
# a table than a real difference; it stops the run so a human looks at it.
OUTLIER = 5
# If a constant tune still leaves this much spread at a single place, that
# place needs its official table in the app rather than a tune.
MAX_RESIDUAL_SPREAD = 4
REGION_RADIUS_KM = 100


def round_half_up(value):
    return int(value + 0.5) if value >= 0 else -int(-value + 0.5)


def tune_for(prayer, diffs):
    low, high = min(diffs), max(diffs)
    if prayer == "fajr":
        return -round_half_up((low + high) / 2)
    if prayer == "sunrise":
        return -high
    return -low


def tune_and_residual(diffs, where, problems):
    minutes = {p: tune_for(p, diffs[p]) for p in PRAYERS}
    residual = {p: [min(diffs[p]) + minutes[p], max(diffs[p]) + minutes[p]] for p in PRAYERS}
    for prayer, value in minutes.items():
        if abs(value) > MAX_TUNE:
            problems.append(f"{where} {prayer}: tune {value:+d} exceeds ±{MAX_TUNE}")
    return minutes, residual


def measure(country):
    fetch = FETCHERS[country["source"]]
    diffs = {p: [] for p in PRAYERS}
    places = []
    for place in country["places"]:
        official = fetch(place)
        app = {}
        for year, month in sorted({(d.year, d.month) for d in official}):
            app.update(aladhan(place, country, year, month))
            time.sleep(0.3)
        days = sorted(set(official) & set(app))
        if len(days) < 28:
            raise SystemExit(f"{place['name']}: only {len(days)} comparable days")
        per_place, place_diffs = {}, {}
        for prayer in PRAYERS:
            values = [app[d][prayer] - official[d][prayer] for d in days]
            median = statistics.median(values)
            outliers = [(d.isoformat(), v) for d, v in zip(days, values) if abs(v - median) > OUTLIER]
            if outliers:
                raise SystemExit(f"{place['name']} {prayer}: suspicious days {outliers[:5]}; check the official table")
            diffs[prayer].extend(values)
            place_diffs[prayer] = values
            per_place[prayer] = {"min": min(values), "max": max(values), "median": median}
        places.append({"place": place, "diffs": place_diffs, "report": {
            "name": place["name"], "id": place["id"], "from": days[0].isoformat(),
            "to": days[-1].isoformat(), "days": len(days), "app_minus_official": per_place}})
    return diffs, places


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--country", help="Only this country code")
    args = parser.parse_args()

    registry = load_json(REGISTRY)["countries"]
    tunes = load_json(TUNE) if TUNE.exists() else {"_version": "1.0.0", "countries": {}}
    before = dict(tunes["countries"])
    problems = []

    for code, country in registry.items():
        if args.country and code != args.country:
            continue
        diffs, places = measure(country)
        minutes, residual = tune_and_residual(diffs, code, problems)
        regions = []
        for entry in places:
            place = entry["place"]
            region_minutes, region_residual = tune_and_residual(entry["diffs"], place["name"], problems)
            for prayer, (low, high) in region_residual.items():
                if high - low > MAX_RESIDUAL_SPREAD:
                    problems.append(f"{code}/{place['name']} {prayer}: still {low:+d}..{high:+d} min after "
                                    "tuning; a constant tune is not enough here")
            regions.append({"name": place["name"], "lat": place["lat"], "lng": place["lng"],
                            "radius_km": REGION_RADIUS_KM, "minutes": region_minutes})
            entry["report"]["tune_minutes"] = region_minutes
            entry["report"]["after_tune_min_max"] = region_residual
        tunes["countries"][code] = {
            "official": country["official"],
            "method": country["method"],
            "school": country["school"],
            "latitude_adjustment": country["latitude_adjustment"],
            "minutes": minutes,
            "regions": regions,
        }
        REPORTS.mkdir(parents=True, exist_ok=True)
        save_json(REPORTS / f"{code}.json", {
            "official": country["official"],
            "checked_at": date.today().isoformat(),
            "country_tune_minutes": minutes,
            "country_after_tune_min_max": residual,
            "places": [entry["report"] for entry in places],
        })
        print(f"{code}: country tune {minutes}")
        print(f"    after tune, worst place (app - official): {residual}")
        for region in regions:
            print(f"    {region['name']}: {region['minutes']}")

    if problems:
        for line in problems:
            print("PROBLEM:", line)
        sys.exit(1)

    if tunes["countries"] != before:
        major, minor, patch = (int(p) for p in tunes["_version"].split("."))
        tunes["_version"] = f"{major}.{minor}.{patch + 1}" if before else tunes["_version"]
        tunes["_lastUpdate"] = date.today().isoformat()
    tunes["_comment"] = (
        "Minutes the app adds to Aladhan's times, per country, only when the user's method/school/"
        "latitude adjustment match. Generated by scripts/prayer_check.py from official tables; "
        "see reports/prayer/ for the measurements."
    )
    tunes["countries"] = {k: tunes["countries"][k] for k in sorted(tunes["countries"])}
    save_json(TUNE, {k: tunes[k] for k in ("_comment", "_version", "_lastUpdate", "countries") if k in tunes})
    print("prayer_tune.json", "updated to v" + tunes["_version"] if tunes["countries"] != before else "unchanged")


if __name__ == "__main__":
    main()
