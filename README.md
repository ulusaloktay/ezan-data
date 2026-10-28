# ezan-data

Hijri date corrections for the Ezan Vakti app. The app downloads `hijri_corrections.json` from `main` at most once every 24 hours, so **whatever is merged into `main` reaches every user within a day**. Every change goes through a pull request and needs a human review.

## How it works

```
official sources ──► observations/*.json ──► scripts/build.py ──► hijri_corrections.json + provenance.json
  Diyanet table          (one record per             (offset = raw start          (what the app reads)
  announcements           month start)                − official start)
```

- **Raw date:** what Aladhan returns with `adjustment=0`. Its default calendar is HJCoSA, which follows Saudi announcements. The app adds the correction to this date.
- **Observation:** "authority or country X started Hijri month M of year Y on Gregorian day D", with a link to the official source.
- **Offset:** `raw start − official start` in days. `+1` means the month starts one day earlier than raw, `-1` one day later.
- **No observation, no entry.** For a month nobody has observed, the app keeps using the authority's built-in default (see `app_default` in the registry). Nothing is guessed.

## Who decides, and how we learn it

`registry/authorities.json` lists the 22 authorities the app knows, the 106 countries that follow them, and the official body for each.

| mode | meaning | how observations arrive |
|---|---|---|
| `calculated` | Published in advance | A source script. Today: `scripts/sources/diyanet.py`, weekly, via GitHub Actions |
| `saudi` | Follows Saudi announcements | Nothing needed: the raw HJCoSA calendar already is the Saudi date |
| `sighting` | Announced on the evening of the 29th | `scripts/record.py`, from the official announcement (by the scheduled Claude routine or by hand) |

## Recording an announcement

```
python3 scripts/record.py --target PK --year 1448 --month 7 --first-day 2026-12-11 \
  --source "Pakistan Central Ruet-e-Hilal Committee" --url https://...
python3 scripts/build.py
python3 scripts/validate.py --base <(git show origin/main:hijri_corrections.json)
```

- `--first-day` is **day 1 (daytime)** of the month, not the evening the crescent was seen. Kandil nights are dated by the evening they begin, which is one day before the Hijri date they lead into.
- Use a country code when the announcement covers one country. Use the authority key only when every country of that authority follows the same announcement.
- Use only the official body's announcement or a reputable report that quotes it. Projections, astronomical predictions and social-media rumours are not observations.

## Safety rules (`scripts/validate.py`, run on every PR)

- Offsets stay within ±2. `record.py` refuses anything further from the raw date.
- `_version` must go up whenever the corrections change. The app ignores a payload that is not newer than what it already has, including the copy bundled with the app.
- No `_default` from 1448 on: it would override every authority's own default.
- `TR`/`diyanet` = -1 for Shawwal is rejected (it would show Bayram day as Ramadan).
- Every generated value must match its `provenance.json` entry, and `build.py --check` must be clean.

## Known limit

Corrections are per month. When an authority's month is a different length from the raw month, the boundary day is off by one (for example Diyanet's Cemaziyelahir 1448: 10 Nov and 9 Dec 2026). `build.py` prints a warning in that case.

## Keeping the app in sync

When the app's `countryToAuthority` or `authorityDefaultAdjustment` changes (`lib/utils/hijri_calendar_authority.dart`), update `registry/authorities.json`. When releasing the app, copy the current `hijri_corrections.json` into `assets/json/` so the bundled copy is never older than `main`.
