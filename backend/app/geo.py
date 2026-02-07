from __future__ import annotations

import math
from typing import Iterable


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def filter_within_km(
    rows: Iterable[dict],
    lat: float,
    lon: float,
    km: float,
    lat_key: str = "lat",
    lon_key: str = "lon",
) -> list[dict]:
    results = []
    for row in rows:
        if row.get(lat_key) is None or row.get(lon_key) is None:
            continue
        distance = haversine_km(lat, lon, row[lat_key], row[lon_key])
        if distance <= km:
            row = dict(row)
            row["distance_km"] = round(distance, 2)
            results.append(row)
    return results
