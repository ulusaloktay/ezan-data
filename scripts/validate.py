"""Safety rules for hijri_corrections.json. Exit code 1 on any violation.

    python3 scripts/validate.py                       # file rules only
    python3 scripts/validate.py --base old.json       # also require a version bump vs old.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    CORRECTIONS, MAX_ABS_OFFSET, PROVENANCE, known_targets, load_json, load_registry,
)

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def version_tuple(version):
    return tuple(int(p) for p in version.split("."))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", help="Previously published hijri_corrections.json")
    args = parser.parse_args()

    errors = []
    data = load_json(CORRECTIONS)
    registry = load_registry()
    targets = known_targets(registry)

    version = str(data.get("_version", ""))
    if not SEMVER.match(version):
        errors.append(f"_version {version!r} is not x.y.z")

    table = data.get("corrections")
    if not isinstance(table, dict) or not table:
        errors.append("corrections is missing or empty")
        table = {}

    for year, months in table.items():
        if not year.isdigit() or not 1300 <= int(year) <= 1700:
            errors.append(f"bad Hijri year {year!r}")
            continue
        for month, entries in months.items():
            if not month.isdigit() or not 1 <= int(month) <= 12:
                errors.append(f"{year}: bad month {month!r}")
                continue
            for key, value in entries.items():
                where = f"{year}/{month}/{key}"
                if key == "_default":
                    if int(year) >= 1448:
                        errors.append(f"{where}: '_default' overrides every authority's own default; "
                                      "use per-country or per-authority entries")
                elif key not in targets:
                    errors.append(f"{where}: unknown country/authority (add it to registry/authorities.json)")
                if not isinstance(value, int) or isinstance(value, bool):
                    errors.append(f"{where}: value must be an integer")
                elif abs(value) > MAX_ABS_OFFSET:
                    errors.append(f"{where}: {value} is outside [-{MAX_ABS_OFFSET}, {MAX_ABS_OFFSET}]")
            for key in ("TR", "diyanet"):
                if month == "10" and entries.get(key) == -1:
                    errors.append(f"{year}/10/{key} = -1 would show 1 Shawwal as Ramadan in Turkey")

    if PROVENANCE.exists():
        for name, entry in load_json(PROVENANCE)["entries"].items():
            year, month, target = name.split("/")
            if table.get(year, {}).get(month, {}).get(target) != entry["offset"]:
                errors.append(f"provenance {name} = {entry['offset']} does not match the corrections file")

    if args.base and Path(args.base).exists():
        base = load_json(args.base)
        if base.get("corrections") != table and SEMVER.match(version):
            if version_tuple(version) <= version_tuple(str(base.get("_version", "0.0.0"))):
                errors.append(f"corrections changed but _version {version} is not above "
                              f"the published {base.get('_version')}; the app would ignore the update")

    for error in errors:
        print("ERROR:", error)
    if errors:
        sys.exit(1)
    print(f"OK: v{version}, {sum(len(m) for m in table.values())} month blocks")


if __name__ == "__main__":
    main()
