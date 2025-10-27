"""Yoga detection module."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from varga import SIGN_RULERS, ZODIAC_SIGNS

import pandas as pd

DEFAULT_YOGA_FILE = Path("yogas.json")


@dataclass
class Yoga:
    name: str
    description: str
    conditions: Dict[str, str]


class YogaDetector:
    """Evaluate yogas based on planetary placements."""

    def __init__(self, yoga_file: Path | None = None) -> None:
        self.yoga_file = yoga_file or DEFAULT_YOGA_FILE
        self.yogas = self._load_yogas()

    def _load_yogas(self) -> List[Yoga]:
        if not self.yoga_file.exists():
            return [
                Yoga(
                    name="Gajakesari Yoga",
                    description="Moon in kendra from Jupiter.",
                    conditions={"Moon": "kendra_from_Jupiter"},
                ),
                Yoga(
                    name="Chandra-Mangal",
                    description="Moon and Mars in the same house.",
                    conditions={"Moon": "conjunction_Mars"},
                ),
            ]
        data = json.loads(self.yoga_file.read_text(encoding="utf-8"))
        return [Yoga(**item) for item in data]

    def detect(self, houses: Dict[str, float], positions: Dict[str, float]) -> pd.DataFrame:
        rows = []
        for yoga in self.yogas:
            if self._satisfies(yoga, houses, positions):
                rows.append({"Yoga": yoga.name, "Description": yoga.description})
        return pd.DataFrame(rows)

    def _satisfies(self, yoga: Yoga, houses: Dict[str, float], positions: Dict[str, float]) -> bool:
        for planet, rule in yoga.conditions.items():
            planet_lon = positions.get(planet)
            if planet_lon is None:
                return False

            if rule == "kendra_from_Jupiter":
                moon_house = self._house_for_longitude(positions.get("Moon", 0.0), houses)
                jupiter_house = self._house_for_longitude(positions.get("Jupiter", 0.0), houses)
                if (moon_house - jupiter_house) % 12 not in {0, 3, 9}:
                    return False
            elif rule == "conjunction_Mars":
                moon_house = self._house_for_longitude(positions.get("Moon", 0.0), houses)
                mars_house = self._house_for_longitude(positions.get("Mars", 0.0), houses)
                if moon_house != mars_house:
                    return False
            elif rule.startswith("lord_of_house"):
                target_house = int(rule.split("(")[-1].rstrip(")"))
                if self._house_lord(houses, target_house) != planet:
                    return False
            elif rule.startswith("in_trikona_from"):
                reference = rule.split("(")[-1].rstrip(")")
                ref_lon = positions.get(reference)
                if ref_lon is None:
                    return False
                house = self._house_for_longitude(planet_lon, houses)
                ref_house = self._house_for_longitude(ref_lon, houses)
                if (house - ref_house) % 12 not in {0, 4, 8}:
                    return False
            elif rule.startswith("is_aspected_by"):
                aspecting = rule.split("(")[-1].rstrip(")")
                aspect_lon = positions.get(aspecting)
                if aspect_lon is None or not self._has_aspect(aspecting, aspect_lon, planet_lon):
                    return False
            elif rule == "is_combust()":
                sun_lon = positions.get("Sun")
                if sun_lon is None or self._angular_distance(sun_lon, planet_lon) > 8.0:
                    return False
        return True

    def _house_for_longitude(self, longitude: float, houses: Dict[str, float]) -> int:
        asc = houses.get("House 1") or houses.get("Asc", 0.0)
        diff = (longitude - asc + 360.0) % 360.0
        return int(diff // 30) + 1

    def _house_lord(self, houses: Dict[str, float], house: int) -> str:
        cusp = houses.get(f"House {house}", 0.0)
        sign_index = int(cusp // 30) % 12
        sign = ZODIAC_SIGNS[sign_index]
        return SIGN_RULERS.get(sign, "")

    def _angular_distance(self, lon1: float, lon2: float) -> float:
        diff = abs((lon1 - lon2 + 180.0) % 360.0 - 180.0)
        return diff

    def _has_aspect(self, planet: str, aspect_lon: float, target_lon: float) -> bool:
        diff = self._angular_distance(aspect_lon, target_lon)
        if abs(diff - 180.0) <= 6.0:
            return True
        if planet == "Mars" and (abs(diff - 90.0) <= 6.0 or abs(diff - 270.0) <= 6.0):
            return True
        if planet == "Jupiter" and (abs(diff - 120.0) <= 6.0 or abs(diff - 240.0) <= 6.0):
            return True
        if planet == "Saturn" and (abs(diff - 60.0) <= 6.0 or abs(diff - 300.0) <= 6.0):
            return True
        return False
