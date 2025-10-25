"""Yoga detection module."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

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
        return True

    def _house_for_longitude(self, longitude: float, houses: Dict[str, float]) -> int:
        asc = houses.get("House 1") or houses.get("Asc", 0.0)
        diff = (longitude - asc + 360.0) % 360.0
        return int(diff // 30) + 1
