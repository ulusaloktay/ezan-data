# ezan-data

Remote data for the Ezan Vakti app. The app downloads `hijri_corrections.json` at most once every 24 hours, so Hijri date corrections reach users without an app release.

## hijri_corrections.json

`corrections[hijriYear][hijriMonth][countryCode] = days`

The value is added to the raw Aladhan Hijri date (method for the country, `adjustment=0`, Aladhan's default HJCoSA calendar). `-1` means the country starts the month one day later than the raw calculation. Lookup order: country code → authority name → `_default` → the authority's built-in default.

### Rules

- **Bump `_version` on every change.** The app ignores a payload whose version is lower than the one it already has, whether that is the version bundled with the app or a cached remote version.
- Values must be within `[-2, 2]`. `TR = -1` for Shawwal is rejected by the validator.
- Do not add `_default: 0` to months that have not been confirmed. It overrides the `-1` defaults of moon-sighting authorities.
- Only enter values confirmed by an official source. Note the source in `_comment`.

### Sources

| Country | How the month starts | Source |
|---|---|---|
| TR (and Diyanet followers) | Calculated in advance | Diyanet's daily Hijri table, e.g. namazvakitleri.diyanet.gov.tr |
| PK / IN / BD | Moon sighting on the 29th | Ruet-e-Hilal Committee / national announcements |
| MA / DZ / TN | Moon sighting on the 29th | Ministry of religious affairs announcements |
| SA (religious months) | Moon sighting | Saudi Supreme Court announcement |

Moon-sighting countries can only be confirmed on the evening of the 29th. Update the file that same evening.
