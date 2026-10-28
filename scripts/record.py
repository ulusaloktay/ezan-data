"""Record an official month-start announcement in observations/announcements.json.

    python3 scripts/record.py --target PK --year 1448 --month 7 \
        --first-day 2026-12-11 --source "Pakistan Central Ruet-e-Hilal Committee" \
        --url https://...

--target is a country code (PK) or an authority key from registry/authorities.json
(karachi). Use a country code whenever the announcement covers one country only.
--first-day is the Gregorian date of DAY 1 of the month (daytime), not the evening
the crescent was sighted.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    MAX_ABS_OFFSET, OBSERVATIONS, known_targets, load_json, load_registry, raw_month, save_json,
)

OUT = OBSERVATIONS / "announcements.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True, choices=range(1, 13))
    parser.add_argument("--first-day", required=True, type=date.fromisoformat)
    parser.add_argument("--source", required=True, help="Name of the official body")
    parser.add_argument("--url", required=True, help="Link to the official announcement or a report quoting it")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    registry = load_registry()
    if args.target not in known_targets(registry):
        sys.exit(f"Unknown target {args.target!r}: add it to registry/authorities.json first")
    if not args.url.startswith("https://"):
        sys.exit("--url must be an https link")

    raw_first, _ = raw_month(args.year, args.month)
    offset = (raw_first - args.first_day).days
    if abs(offset) > MAX_ABS_OFFSET:
        sys.exit(
            f"Refusing: {args.first_day} is {offset:+d} days from the raw start {raw_first}. "
            "Check that the Hijri year/month and the day-1 date are right."
        )

    data = load_json(OUT) if OUT.exists() else {"records": []}
    records = [
        r for r in data["records"]
        if (r["target"], r["hijri_year"], r["hijri_month"]) != (args.target, args.year, args.month)
    ]
    replaced = len(records) != len(data["records"])
    records.append({
        "target": args.target,
        "hijri_year": args.year,
        "hijri_month": args.month,
        "first_day": args.first_day.isoformat(),
        "source": args.source,
        "url": args.url,
        "note": args.note,
        "recorded_at": date.today().isoformat(),
    })
    records.sort(key=lambda r: (r["hijri_year"], r["hijri_month"], r["target"]))
    data["_comment"] = "Official announcements, one record per target and month. Add with scripts/record.py."
    data["records"] = records
    save_json(OUT, data)
    print(f"{'Replaced' if replaced else 'Recorded'} {args.target} {args.year}/{args.month}: "
          f"day 1 = {args.first_day}, raw = {raw_first}, offset {offset:+d}")


if __name__ == "__main__":
    main()
