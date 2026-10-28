"""Rebuild hijri_corrections.json from observations/*.json.

For every observed month start the offset is (raw start - official start) in
days: +1 means the authority starts the month one day earlier than the raw
calendar, -1 one day later. That is exactly what the app adds to the raw date.

Entries that no observation covers are left untouched (hand-set values from
before this pipeline existed). Months nobody has observed get no entry, so the
app keeps using the authority's built-in default. Nothing is ever guessed.

    python3 scripts/build.py           # write the files
    python3 scripts/build.py --check   # fail if the files are not up to date
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    CORRECTIONS, MAX_ABS_OFFSET, PROVENANCE, authority_of, load_json, load_observations,
    load_registry, next_month, raw_month, save_json,
)


def compute(records, registry):
    """{(year, month, target): provenance entry} for every observation."""
    starts = {(r["target"], r["hijri_year"], r["hijri_month"]): r for r in records}
    if len(starts) != len(records):
        raise SystemExit("Duplicate observation for the same target and month")
    result, warnings = {}, []
    for (target, year, month), record in sorted(starts.items(), key=lambda kv: kv[0][1:] + (kv[0][0],)):
        if target not in registry and authority_of(registry, target) is None:
            raise SystemExit(f"{record['_file']}: unknown target {target!r}")
        official = date.fromisoformat(record["first_day"])
        raw_first, raw_len = raw_month(year, month)
        offset = (raw_first - official).days
        if abs(offset) > MAX_ABS_OFFSET:
            raise SystemExit(f"{record['_file']}: {target} {year}/{month} offset {offset:+d} is implausible")
        entry = {
            "offset": offset,
            "official_first_day": official.isoformat(),
            "raw_first_day": raw_first.isoformat(),
            "source": record["source"],
            "url": record["url"],
            "recorded_at": record["recorded_at"],
        }
        following = starts.get((target,) + next_month(year, month))
        if following:
            official_len = (date.fromisoformat(following["first_day"]) - official).days
            if official_len != raw_len:
                entry["month_length"] = {"official": official_len, "raw": raw_len}
                warnings.append(
                    f"{target} {year}/{month}: official month has {official_len} days, raw {raw_len}; "
                    "the boundary day will be off by one in the app"
                )
        result[(year, month, target)] = entry
    return result, warnings


def apply(corrections, computed, registry):
    table = corrections["corrections"]
    for (year, month, target), entry in computed.items():
        month_data = table.setdefault(str(year), {}).setdefault(str(month), {})
        if target in registry:
            # The app looks up the country code before the authority key, so a
            # stale country entry would hide the observed authority value.
            for country in registry[target]["countries"]:
                if country in month_data and (year, month, country) not in computed:
                    del month_data[country]
        month_data[target] = entry["offset"]
    for year in list(table):
        table[year] = {m: table[year][m] for m in sorted(table[year], key=int) if table[year][m]}
    corrections["corrections"] = {y: table[y] for y in sorted(table, key=int)}


def bump(version):
    major, minor, patch = (int(p) for p in version.split("."))
    return f"{major}.{minor}.{patch + 1}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    registry = load_registry()
    corrections = load_json(CORRECTIONS)
    before = json.dumps(corrections["corrections"], sort_keys=True)
    computed, warnings = compute(load_observations(), registry)
    apply(corrections, computed, registry)
    changed = json.dumps(corrections["corrections"], sort_keys=True) != before

    provenance = {
        "_comment": "Why each generated entry in hijri_corrections.json has its value. Written by scripts/build.py.",
        "entries": {f"{y}/{m}/{t}": e for (y, m, t), e in sorted(computed.items())},
    }
    old_provenance = load_json(PROVENANCE) if PROVENANCE.exists() else None

    if args.check:
        stale = changed or old_provenance != provenance
        for line in warnings:
            print("WARNING:", line)
        if stale:
            sys.exit("hijri_corrections.json / provenance.json are out of date: run scripts/build.py")
        print("Up to date.")
        return

    if changed:
        corrections["_version"] = bump(corrections["_version"])
        corrections["_lastUpdate"] = date.today().isoformat()
    corrections["_comment"] = (
        "Generated by scripts/build.py from observations/ (see provenance.json for the source of every "
        "generated entry). Entries without provenance were set by hand before the pipeline existed. "
        "Months without an entry use the authority's built-in default in the app."
    )
    save_json(CORRECTIONS, corrections)
    save_json(PROVENANCE, provenance)
    print(f"{'Updated to v' + corrections['_version'] if changed else 'No correction changes'}; "
          f"{len(computed)} observed months")
    for line in warnings:
        print("WARNING:", line)


if __name__ == "__main__":
    main()
