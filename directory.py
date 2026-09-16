"""Netcare facility directory lookups: province, city, name and proximity.

The directory is loaded from ``directory.json``. Coordinates in that file are
suburb-level approximations, so distances are indicative rather than exact and
are always presented alongside the facility's full address. Replace the file
with Netcare's own geocoded directory before production use.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DIRECTORY_FILE = BASE_DIR / "directory.json"

EARTH_RADIUS_KM = 6371.0
MEDICROSS_KIND = "Medical & dental centre"
MAX_RESULTS = 12
NEAREST_RESULTS = 5


def _normalize(text: str) -> str:
    """Lowercase text and strip punctuation so matching is deterministic."""
    cleaned = str(text or "").lower()
    cleaned = re.sub(r"[^\w\s'-]", " ", cleaned, flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned).strip()


def haversine_km(lat_a: float, lng_a: float, lat_b: float, lng_b: float) -> float:
    """Return the great-circle distance in kilometres between two points."""
    d_lat = math.radians(lat_b - lat_a)
    d_lng = math.radians(lng_b - lng_a)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat_a)) * math.cos(math.radians(lat_b)) * math.sin(d_lng / 2) ** 2
    )
    return EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class FacilityDirectory:
    """Search Netcare facilities by province, city, name or proximity."""

    def __init__(self, path: Path = DIRECTORY_FILE) -> None:
        """Load the directory file into memory."""
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            data = {}
        self.meta: dict[str, Any] = data.get("meta", {})
        self.facilities: list[dict[str, Any]] = data.get("facilities", [])
        self.province_aliases: dict[str, str] = data.get("province_aliases", {})
        self.city_aliases: dict[str, str] = data.get("city_aliases", {})
        self.cities = {facility.get("city", "").lower() for facility in self.facilities}

    def find_province(self, text: str) -> str | None:
        """Return the province named in the text, honouring language aliases."""
        normalized = _normalize(text)
        matches = [
            (len(alias), province)
            for alias, province in self.province_aliases.items()
            if alias in normalized
        ]
        return max(matches)[1] if matches else None

    def find_city(self, text: str) -> str | None:
        """Return the city named in the text, honouring nicknames and aliases."""
        normalized = _normalize(text)
        for alias, city in self.city_aliases.items():
            if alias in normalized:
                return city
        for city in sorted(self.cities, key=len, reverse=True):
            if city and city in normalized:
                return city.title()
        return None

    def find_by_name(self, text: str) -> dict[str, Any] | None:
        """Return a single facility when its name appears in the text."""
        normalized = _normalize(text)
        best: tuple[int, dict[str, Any]] | None = None
        for facility in self.facilities:
            key = _normalize(facility.get("name", ""))
            key = re.sub(r"^(netcare|medicross)\s+", "", key)
            if len(key) > 4 and key in normalized:
                if best is None or len(key) > best[0]:
                    best = (len(key), facility)
        return best[1] if best else None

    def in_area(
        self,
        province: str | None = None,
        city: str | None = None,
        medicross_only: bool = False,
        hospitals_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Return facilities filtered by province, city and facility type."""
        results = []
        for facility in self.facilities:
            if province and facility.get("province") != province:
                continue
            if city and facility.get("city", "").lower() != city.lower():
                continue
            kind = facility.get("kind", "")
            if medicross_only and kind != MEDICROSS_KIND:
                continue
            if hospitals_only and kind == MEDICROSS_KIND:
                continue
            results.append(facility)
        results.sort(key=lambda item: item.get("name", ""))
        return results

    def nearest(self, lat: float, lng: float, limit: int = NEAREST_RESULTS) -> list[dict[str, Any]]:
        """Return the closest facilities, each annotated with distance in km."""
        scored = []
        for facility in self.facilities:
            facility_lat = facility.get("lat")
            facility_lng = facility.get("lng")
            if facility_lat is None or facility_lng is None:
                continue
            distance = haversine_km(lat, lng, float(facility_lat), float(facility_lng))
            annotated = dict(facility)
            annotated["distance_km"] = round(distance, 1)
            scored.append(annotated)
        scored.sort(key=lambda item: item["distance_km"])
        return scored[:limit]

    def province_of(self, hospital_name: str) -> str | None:
        """Return the province of a facility given its name.

        Used to cross-reference a verified doctor record's hospital field
        against a province or city the person asked about, since the doctor
        records themselves don't carry a province field.
        """
        facility = self.find_by_name(hospital_name)
        return facility.get("province") if facility else None

    def city_of(self, hospital_name: str) -> str | None:
        """Return the city of a facility given its name."""
        facility = self.find_by_name(hospital_name)
        return facility.get("city") if facility else None

    @staticmethod
    def map_url(facility: dict[str, Any]) -> str:
        """Return a Google Maps search URL for the facility."""
        from urllib.parse import quote

        query = f"{facility.get('name', '')}, {facility.get('address', '')}"
        return "https://www.google.com/maps/search/?api=1&query=" + quote(query)

    @staticmethod
    def tel_url(facility: dict[str, Any]) -> str:
        """Return a tel: URL for the facility's switchboard."""
        return "tel:" + str(facility.get("phone", "")).replace(" ", "")

    def to_card(self, facility: dict[str, Any]) -> dict[str, Any]:
        """Return the facility as a front-end card payload."""
        return {
            "name": facility.get("name", ""),
            "kind": facility.get("kind", ""),
            "address": facility.get("address", ""),
            "city": facility.get("city", ""),
            "province": facility.get("province", ""),
            "phone": facility.get("phone", ""),
            "tel_url": self.tel_url(facility),
            "map_url": self.map_url(facility),
            "distance_km": facility.get("distance_km"),
        }
