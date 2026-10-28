"""Shared helpers: paths, registry, observations and the raw Aladhan calendar."""

import json
import time
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORRECTIONS = ROOT / "hijri_corrections.json"
PROVENANCE = ROOT / "provenance.json"
REGISTRY = ROOT / "registry" / "authorities.json"
OBSERVATIONS = ROOT / "observations"

# The app corrects the Hijri date Aladhan returns with adjustment=0. Aladhan's
# default calendar for that is HJCoSA, so offsets must be relative to it.
RAW_CALENDAR = "HJCoSA"
MAX_ABS_OFFSET = 2


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def load_registry():
    return load_json(REGISTRY)["authorities"]


def known_targets(registry):
    """Authority keys and country codes that may appear in the corrections."""
    targets = set(registry)
    for authority in registry.values():
        targets.update(authority["countries"])
    return targets


def authority_of(registry, country):
    for key, authority in registry.items():
        if country in authority["countries"]:
            return key
    return None


def load_observations():
    """All records from observations/*.json, tagged with the file they came from."""
    records = []
    for path in sorted(OBSERVATIONS.glob("*.json")):
        for record in load_json(path).get("records", []):
            records.append(dict(record, _file=path.name))
    return records


def http_json(url, attempts=4):
    last_error = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "ezan-data"})
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except Exception as error:  # network hiccups and Aladhan rate limits
            last_error = error
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"GET {url} failed: {last_error}")


_raw_cache = {}


def raw_month(hijri_year, hijri_month):
    """(first Gregorian day, length in days) of a Hijri month in the raw calendar."""
    key = (hijri_year, hijri_month)
    if key not in _raw_cache:
        url = (
            f"https://api.aladhan.com/v1/hToGCalendar/{hijri_month}/{hijri_year}"
            f"?calendarMethod={RAW_CALENDAR}"
        )
        days = http_json(url)["data"]
        first = days[0]
        if int(first["hijri"]["day"]) != 1:
            raise RuntimeError(f"Raw calendar for {hijri_year}/{hijri_month} does not start on day 1")
        _raw_cache[key] = (parse_dmy(first["gregorian"]["date"]), len(days))
    return _raw_cache[key]


def parse_dmy(text):
    day, month, year = (int(part) for part in text.split("-"))
    return date(year, month, day)


def next_month(hijri_year, hijri_month):
    return (hijri_year + 1, 1) if hijri_month == 12 else (hijri_year, hijri_month + 1)
