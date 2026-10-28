"""Official prayer-time tables, one fetcher per source.

Each fetcher takes a place from registry/prayer_sources.json and returns
{date: {"fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"}} with times as
minutes after midnight, local time.
"""

import html
import re
import urllib.request
from datetime import date

from common import http_json

PRAYERS = ("fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha")


def minutes(text):
    hours, mins = text.strip()[:5].split(":")
    return int(hours) * 60 + int(mins)


TR_MONTHS = {
    "Ocak": 1, "Şubat": 2, "Mart": 3, "Nisan": 4, "Mayıs": 5, "Haziran": 6,
    "Temmuz": 7, "Ağustos": 8, "Eylül": 9, "Ekim": 10, "Kasım": 11, "Aralık": 12,
}
DIYANET_ROW = re.compile(
    r"<td>(\d+) (\S+) (\d{4}) \S+</td>\s*<td>[^<]*</td>\s*"
    + r"\s*".join([r"<td>(\d\d:\d\d)</td>"] * 6)
)


def diyanet(place):
    """Diyanet's yearly table for a city (today onwards). İmsak in Diyanet = fajr."""
    url = f"https://namazvakitleri.diyanet.gov.tr/tr-TR/{place['id']}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ezan-data)"})
    with urllib.request.urlopen(request, timeout=60) as response:
        page = html.unescape(response.read().decode("utf-8"))
    table = {}
    for day, month, year, *times in DIYANET_ROW.findall(page):
        table[date(int(year), TR_MONTHS[month], int(day))] = dict(zip(PRAYERS, map(minutes, times)))
    return table


MS_MONTHS = {
    "Jan": 1, "Feb": 2, "Mac": 3, "Apr": 4, "Mei": 5, "Jun": 6,
    "Jul": 7, "Ogos": 8, "Sep": 9, "Okt": 10, "Nov": 11, "Dis": 12,
}


def jakim(place):
    """JAKIM e-Solat yearly table for a zone. Uses subuh (fajr), not the 10-minute-earlier imsak."""
    url = f"https://www.e-solat.gov.my/index.php?r=esolatApi/takwimsolat&period=year&zone={place['id']}"
    data = http_json(url)
    if data.get("status") != "OK!":
        raise RuntimeError(f"JAKIM {place['id']}: {data.get('status')}")
    table = {}
    for row in data["prayerTime"]:
        day, month, year = row["date"].split("-")
        table[date(int(year), MS_MONTHS[month], int(day))] = {
            "fajr": minutes(row["fajr"]), "sunrise": minutes(row["syuruk"]),
            "dhuhr": minutes(row["dhuhr"]), "asr": minutes(row["asr"]),
            "maghrib": minutes(row["maghrib"]), "isha": minutes(row["isha"]),
        }
    return table


FETCHERS = {"diyanet": diyanet, "jakim": jakim}

ALADHAN_KEYS = {"fajr": "Fajr", "sunrise": "Sunrise", "dhuhr": "Dhuhr",
                "asr": "Asr", "maghrib": "Maghrib", "isha": "Isha"}


def aladhan(place, country, year, month):
    """What the app shows (before any tune) for a place and month."""
    url = (
        f"https://api.aladhan.com/v1/calendar/{year}/{month}?latitude={place['lat']}"
        f"&longitude={place['lng']}&method={country['method']}&school={country['school']}"
        f"&adjustment=0&latitudeAdjustmentMethod={country['latitude_adjustment']}"
    )
    table = {}
    for row in http_json(url)["data"]:
        day, mon, yr = (int(p) for p in row["date"]["gregorian"]["date"].split("-"))
        table[date(yr, mon, day)] = {p: minutes(row["timings"][k]) for p, k in ALADHAN_KEYS.items()}
    return table
