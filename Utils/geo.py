"""Geographic helpers for gate geofencing."""

from __future__ import annotations

import math
from typing import Optional


def haversine_distance_meters(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Great-circle distance between two WGS84 points, in meters."""
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


def is_within_radius(
    user_lat: float,
    user_lon: float,
    gate_lat: float,
    gate_lon: float,
    radius_meters: float,
) -> tuple[bool, float]:
    """Return (inside, distance_meters)."""
    distance = haversine_distance_meters(user_lat, user_lon, gate_lat, gate_lon)
    return distance <= radius_meters, distance


def gate_has_coordinates(latitude: Optional[float], longitude: Optional[float]) -> bool:
    return latitude is not None and longitude is not None
