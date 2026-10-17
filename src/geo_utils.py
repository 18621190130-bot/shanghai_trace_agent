"""Approximate geometry, not street navigation.

WGS84 conversion adapted from googollee/eviltransform (BSD-2-Clause).
See THIRD_PARTY_NOTICES.md for attribution and retained license.
"""

import math


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlat, dlng = lat2 - lat1, math.radians(b[1] - a[1])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1.0, max(0.0, h))))


def wgs84_to_gcj02(lat: float, lng: float) -> tuple[float, float]:
    """Approximate offline conversion; preserves the input outside China bounds."""
    if not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271):
        return lat, lng
    x, y = lng - 105.0, lat - 35.0
    xy, root = x * y, math.sqrt(abs(x))
    xp, yp = x * math.pi, y * math.pi
    shared = 20 * math.sin(6 * xp) + 20 * math.sin(2 * xp)
    dlat = (shared + 20 * math.sin(yp) + 40 * math.sin(yp / 3)
            + 160 * math.sin(yp / 12) + 320 * math.sin(yp / 30)) * 2 / 3
    dlng = (shared + 20 * math.sin(xp) + 40 * math.sin(xp / 3)
            + 150 * math.sin(xp / 12) + 300 * math.sin(xp / 30)) * 2 / 3
    dlat += -100 + 2 * x + 3 * y + .2 * y * y + .1 * xy + .2 * root
    dlng += 300 + x + 2 * y + .1 * x * x + .1 * xy + .1 * root
    rad = math.radians(lat)
    eccentricity = .00669342162296594323
    magic = 1 - eccentricity * math.sin(rad) ** 2
    radius = 6378137.0
    dlat = dlat * 180 / ((radius * (1 - eccentricity)) / (magic ** 1.5) * math.pi)
    dlng = dlng * 180 / (radius / math.sqrt(magic) * math.cos(rad) * math.pi)
    return lat + dlat, lng + dlng


def to_gcj02(lat: float, lng: float, system: str) -> tuple[float, float]:
    if system.startswith("WGS84"):
        return wgs84_to_gcj02(lat, lng)
    if system.startswith("GCJ-02"):
        return lat, lng
    raise ValueError(f"Unsupported coordinate system: {system}")
