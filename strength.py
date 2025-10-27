"""Planetary and house strength calculations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict

import pandas as pd

from ephemeris import PlanetPosition
from varga import ZODIAC_SIGNS

PLANET_GENDERS = {
    "Sun": "male",
    "Moon": "female",
    "Mars": "male",
    "Mercury": "neutral",
    "Jupiter": "male",
    "Venus": "female",
    "Saturn": "neutral",
    "Rahu": "neutral",
    "Ketu": "neutral",
}

EXALTATION_POINTS = {
    "Sun": 10.0 + 120.0,  # 10 Aries
    "Moon": 3.0 + 30.0,  # 3 Taurus
    "Mars": 28.0 + 270.0,  # 28 Capricorn
    "Mercury": 15.0 + 150.0,  # 15 Virgo
    "Jupiter": 5.0 + 90.0,  # 5 Cancer
    "Venus": 27.0 + 330.0,  # 27 Pisces
    "Saturn": 20.0 + 180.0,  # 20 Libra
}

DEBILITATION_POINTS = {planet: (point + 180.0) % 360 for planet, point in EXALTATION_POINTS.items()}

FRIENDSHIP = {
    "Sun": {"friends": {"Moon", "Mars", "Jupiter"}, "enemies": {"Venus", "Saturn"}},
    "Moon": {"friends": {"Sun", "Mercury"}, "enemies": {"None"}},
    "Mars": {"friends": {"Sun", "Moon", "Jupiter"}, "enemies": {"Mercury"}},
    "Mercury": {"friends": {"Sun", "Venus"}, "enemies": {"Moon"}},
    "Jupiter": {"friends": {"Sun", "Moon", "Mars"}, "enemies": {"Venus", "Mercury"}},
    "Venus": {"friends": {"Mercury", "Saturn"}, "enemies": {"Sun", "Moon"}},
    "Saturn": {"friends": {"Mercury", "Venus"}, "enemies": {"Sun", "Moon"}},
}

NAISARGIKA_BALA = {
    "Sun": 60.0,
    "Moon": 51.4,
    "Venus": 42.9,
    "Jupiter": 34.3,
    "Mercury": 25.7,
    "Mars": 17.1,
    "Saturn": 8.6,
    "Rahu": 8.6,
    "Ketu": 8.6,
}

DIG_BALA_OPTIMA = {
    "Sun": 10,
    "Mars": 10,
    "Jupiter": 1,
    "Mercury": 1,
    "Moon": 4,
    "Venus": 4,
    "Saturn": 7,
    "Rahu": 7,
    "Ketu": 7,
}

PLANET_HOUSE_OWNERSHIP = {
    "Sun": [5],
    "Moon": [4],
    "Mars": [1, 8],
    "Mercury": [3, 6],
    "Jupiter": [9, 12],
    "Venus": [2, 7],
    "Saturn": [10, 11],
    "Rahu": [],
    "Ketu": [],
}

MOOLATRIKONA_SIGN = {
    "Sun": "Leo",
    "Moon": "Taurus",
    "Mars": "Aries",
    "Mercury": "Virgo",
    "Jupiter": "Sagittarius",
    "Venus": "Libra",
    "Saturn": "Aquarius",
    "Rahu": "Gemini",
    "Ketu": "Sagittarius",
}

MOOLATRIKONA_RANGE = {
    "Sun": (0, 20),
    "Moon": (3, 30),
    "Mars": (0, 12),
    "Mercury": (15, 20),
    "Jupiter": (0, 10),
    "Venus": (0, 15),
    "Saturn": (0, 20),
    "Rahu": (0, 30),
    "Ketu": (0, 30),
}


@dataclass
class ShadbalaBreakdown:
    planet: str
    sthana: float
    dig: float
    kala: float
    ayana: float
    cheshta: float
    naisargika: float
    drig: float

    def total(self) -> float:
        return self.sthana + self.dig + self.kala + self.ayana + self.cheshta + self.naisargika + self.drig


class StrengthCalculator:
    """Compute Shadbala and Bhavabala."""

    def __init__(self, positions: Dict[str, PlanetPosition], houses: Dict[str, float], vargas: Dict[str, Dict[str, str]]) -> None:
        self.positions = positions
        self.houses = houses
        self.vargas = vargas

    # ------------------------------------------------------------------
    # Shadbala

    def shadbala(self) -> pd.DataFrame:
        rows = []
        for planet, position in self.positions.items():
            if planet not in PLANET_GENDERS:
                continue
            sthana = self._sthana_bala(planet, position)
            dig = self._dig_bala(planet, position)
            kala = self._kala_bala(planet)
            ayana = self._ayana_bala(planet, position)
            cheshta = self._cheshta_bala(planet, position)
            naisargika = NAISARGIKA_BALA.get(planet, 5.0)
            drig = self._drig_bala(planet)
            total = sthana + dig + kala + ayana + cheshta + naisargika + drig
            rows.append(
                {
                    "Planet": planet,
                    "Sthana": sthana,
                    "Dig": dig,
                    "Kala": kala,
                    "Ayana": ayana,
                    "Cheshta": cheshta,
                    "Naisargika": naisargika,
                    "Drig": drig,
                    "Total": total,
                }
            )
        return pd.DataFrame(rows)

    def _sthana_bala(self, planet: str, position: PlanetPosition) -> float:
        uchcha = self._uchcha_bala(planet, position)
        saptavargaja = self._saptavargaja_bala(planet)
        oja_yugma = self._oja_yugma_bala(planet, position)
        kendradi = self._kendradi_bala(planet, position)
        drekkana = self._drekkana_bala(planet, position)
        return uchcha + saptavargaja + oja_yugma + kendradi + drekkana

    def _uchcha_bala(self, planet: str, position: PlanetPosition) -> float:
        exalt = EXALTATION_POINTS.get(planet)
        if exalt is None:
            return 15.0
        debil = DEBILITATION_POINTS[planet]
        distance = (position.longitude - debil + 360.0) % 360.0
        if distance > 180.0:
            distance = 360.0 - distance
        return min(60.0, distance / 3.0)

    def _saptavargaja_bala(self, planet: str) -> float:
        divisions = ["D1", "D2", "D3", "D7", "D9", "D12", "D30"]
        weights = {"own": 30.0, "friend": 20.0, "neutral": 15.0, "enemy": 10.0}
        total = 0.0
        for division in divisions:
            varga_sign = self.vargas.get(division, {}).get(planet)
            if varga_sign is None:
                continue
            relation = self._relationship(planet, varga_sign)
            total += weights.get(relation, 15.0)
        return total

    def _relationship(self, planet: str, sign: str) -> str:
        owners = PLANET_HOUSE_OWNERSHIP.get(planet, [])
        sign_index = ZODIAC_SIGNS.index(sign)
        ruler = self._sign_lord(sign_index)
        if ruler == planet:
            return "own"
        friends = FRIENDSHIP.get(planet, {}).get("friends", set())
        enemies = FRIENDSHIP.get(planet, {}).get("enemies", set())
        if ruler in friends:
            return "friend"
        if ruler in enemies:
            return "enemy"
        return "neutral"

    def _moolatrikona_bala(self, planet: str, position: PlanetPosition) -> float:
        mt_sign = MOOLATRIKONA_SIGN.get(planet)
        if mt_sign is None:
            return 0.0

        sign_idx = int(position.longitude // 30)
        planet_sign = ZODIAC_SIGNS[sign_idx]
        if planet_sign != mt_sign:
            return 0.0

        lon_in_sign = position.longitude % 30
        start, end = MOOLATRIKONA_RANGE.get(planet, (0, 0))
        if start <= lon_in_sign <= end:
            return 45.0
        return 0.0

    def _sign_lord(self, sign_index: int) -> str:
        rulers = [
            "Mars",
            "Venus",
            "Mercury",
            "Moon",
            "Sun",
            "Mercury",
            "Venus",
            "Mars",
            "Jupiter",
            "Saturn",
            "Saturn",
            "Jupiter",
        ]
        return rulers[sign_index % 12]

    def _oja_yugma_bala(self, planet: str, position: PlanetPosition) -> float:
        sign_idx = int(position.longitude // 30)
        navamsa_sign = self.vargas.get("D9", {}).get(planet)
        gender = PLANET_GENDERS.get(planet, "neutral")
        score = 0.0
        if gender == "male" and sign_idx % 2 == 0:
            score += 15.0
        if gender == "female" and sign_idx % 2 == 1:
            score += 15.0
        if navamsa_sign is not None:
            nav_idx = ZODIAC_SIGNS.index(navamsa_sign)
            if gender == "male" and nav_idx % 2 == 0:
                score += 15.0
            if gender == "female" and nav_idx % 2 == 1:
                score += 15.0
            if gender == "neutral" and nav_idx % 2 == 0:
                score += 10.0
        return score

    def _kendradi_bala(self, planet: str, position: PlanetPosition) -> float:
        house = self._house_for_longitude(position.longitude)
        if house in {1, 4, 7, 10}:
            return 60.0
        if house in {2, 5, 8, 11}:
            return 30.0
        return 15.0

    def _drekkana_bala(self, planet: str, position: PlanetPosition) -> float:
        gender = PLANET_GENDERS.get(planet, "neutral")
        part = int((position.longitude % 30) // 10)
        if gender == "male" and part == 0:
            return 15.0
        if gender == "female" and part == 1:
            return 15.0
        if gender == "neutral" and part == 2:
            return 15.0
        return 7.5

    def _house_for_longitude(self, longitude: float) -> int:
        asc = self.houses.get("House 1") or self.houses.get("Asc", 0.0)
        distance = (longitude - asc + 360.0) % 360.0
        return int(distance // 30) + 1

    def _dig_bala(self, planet: str, position: PlanetPosition) -> float:
        optimal_house = DIG_BALA_OPTIMA.get(planet)
        if optimal_house is None:
            return 15.0
        house = self._house_for_longitude(position.longitude)
        distance = min((house - optimal_house) % 12, (optimal_house - house) % 12)
        return max(0.0, 60.0 - distance * 10.0)

    def _kala_bala(self, planet: str) -> float:
        # Basic implementation using diurnal/nocturnal preference and paksha bala.
        if planet in {"Sun", "Jupiter", "Venus"}:
            return 30.0
        if planet in {"Moon", "Mars", "Saturn"}:
            return 30.0
        return 20.0

    def _ayana_bala(self, planet: str, position: PlanetPosition) -> float:
        obliquity = 23.4367
        kranti = position.declination
        if planet in {"Sun", "Mars", "Jupiter", "Venus"}:
            value = 30.0 * (obliquity + kranti) / obliquity
        elif planet in {"Moon", "Saturn"}:
            value = 30.0 * (obliquity - kranti) / obliquity
        else:
            value = 30.0
        return max(0.0, min(60.0, value))

    def _cheshta_bala(self, planet: str, position: PlanetPosition) -> float:
        speed = position.speed_longitude
        if speed < 0:
            return 60.0
        if speed < 0.5:
            return 30.0
        if speed < 1.0:
            return 20.0
        return 45.0

    def _drig_bala(self, planet: str) -> float:
        benefics = {"Jupiter", "Venus", "Mercury", "Moon"}
        malefics = {"Saturn", "Mars", "Sun"}
        total = 0.0
        for other, pos in self.positions.items():
            if other == planet:
                continue
            aspect = self._aspect_strength(self.positions[planet].longitude, pos.longitude)
            if other in benefics:
                total += aspect
            elif other in malefics:
                total -= aspect
        return total

    def _aspect_strength(self, lon1: float, lon2: float) -> float:
        diff = abs((lon1 - lon2 + 180) % 360 - 180)
        if diff < 5:
            return 20.0
        if diff < 30:
            return 10.0
        if diff < 60:
            return 5.0
        return 0.0

    # ------------------------------------------------------------------
    # Bhavabala

    def bhavabala(self) -> pd.DataFrame:
        shadbala_df = self.shadbala().set_index("Planet")
        rows = []
        for house in range(1, 13):
            strength = self._house_strength(house, shadbala_df)
            rows.append({"House": house, "Strength": strength})
        return pd.DataFrame(rows)

    def _house_strength(self, house: int, shadbala_df: pd.DataFrame) -> float:
        lord = self._house_lord(house)
        lord_strength = shadbala_df.get("Total", pd.Series()).get(lord, 120.0)
        occupants = [planet for planet, pos in self.positions.items() if self._house_for_longitude(pos.longitude) == house]
        benefics = {"Jupiter", "Venus", "Mercury", "Moon"}
        malefics = {"Saturn", "Mars", "Sun", "Rahu", "Ketu"}
        occupancy_score = len([p for p in occupants if p in benefics]) * 10.0 - len([p for p in occupants if p in malefics]) * 10.0
        aspect_score = 0.0
        cusp_longitude = self.houses.get(f"House {house}", 0.0)
        for planet, pos in self.positions.items():
            diff = abs((pos.longitude - cusp_longitude + 180) % 360 - 180)
            if planet in benefics and diff < 120:
                aspect_score += 5.0
            if planet in malefics and diff < 120:
                aspect_score -= 5.0
        sign_quality = 10.0 if house in {1, 4, 7, 10} else 5.0
        return lord_strength / 4 + occupancy_score + aspect_score + sign_quality

    def _house_lord(self, house: int) -> str:
        cusp = self.houses.get(f"House {house}", 0.0)
        sign = int(cusp // 30)
        return self._sign_lord(sign)

    # ------------------------------------------------------------------
    # Ishta/Kashta Bala

    def compute_ishta_kashta(self) -> pd.DataFrame:
        results = []
        for planet, position in self.positions.items():
            if planet not in PLANET_GENDERS:
                continue

            uchcha_bala = self._uchcha_bala(planet, position)
            mt_bala = self._moolatrikona_bala(planet, position)
            if mt_bala == 0.0:
                current_sign = ZODIAC_SIGNS[int(position.longitude // 30)]
                if self._relationship(planet, current_sign) == "own":
                    mt_bala = 30.0
            cheshta_bala = self._cheshta_bala(planet, position)
            dig_bala = self._dig_bala(planet, position)
            paksha_bala = 30.0

            ishta = math.sqrt(max(0.01, uchcha_bala) * max(0.01, cheshta_bala))
            ishta += mt_bala / 2 + dig_bala / 4 + paksha_bala / 2
            kashta = math.sqrt(max(0.01, 60.0 - uchcha_bala) * max(0.01, 60.0 - cheshta_bala))
            kashta += max(0.0, 30.0 - mt_bala / 2)

            ratio = ishta / (ishta + kashta) if (ishta + kashta) > 0 else 0.5

            results.append({
                "Planet": planet,
                "Ishta": round(ishta, 2),
                "Kashta": round(kashta, 2),
                "Ratio": round(ratio, 3),
            })

        return pd.DataFrame(results)
