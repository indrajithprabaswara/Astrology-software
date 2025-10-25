"""Swiss Ephemeris wrapper utilities."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Dict
import pandas as pd

try:
    import swisseph as swe
except ImportError:  # pragma: no cover - optional dependency
    swe = None


PLANETS = {
    "Sun": 0,
    "Moon": 1,
    "Mercury": 2,
    "Venus": 3,
    "Mars": 4,
    "Jupiter": 5,
    "Saturn": 6,
    "Uranus": 7,
    "Neptune": 8,
    "Pluto": 9,
    "Rahu": 10,
    "Ketu": 11,
}

UPAGRAHAS = ["Gulika", "Mandi"]

AYANAMSA_OPTIONS = {
    "lahiri": 1,
    "raman": 2,
    "krishnamurti": 5,
}


@dataclass
class PlanetPosition:
    """Positional data of a celestial body."""

    longitude: float
    latitude: float
    speed_longitude: float
    right_ascension: float
    declination: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "longitude": self.longitude,
            "latitude": self.latitude,
            "speed": self.speed_longitude,
            "ra": self.right_ascension,
            "decl": self.declination,
        }


class EphemerisCalculator:
    """High-level Swiss Ephemeris wrapper."""

    def __init__(self, ayanamsa: str = "lahiri") -> None:
        self.ayanamsa = ayanamsa

    def set_ayanamsa(self, ayanamsa: str) -> None:
        self.ayanamsa = ayanamsa

    # ------------------------------------------------------------------
    # Public API

    def planetary_positions(self, when: datetime) -> Dict[str, PlanetPosition]:
        """Return sidereal positions for major planets and nodes."""

        positions: Dict[str, PlanetPosition] = {}
        for name, planet_id in PLANETS.items():
            positions[name] = self._compute_planet(planet_id, when)
        positions.update(self._compute_upagrahas(when))
        return positions

    def house_cusps(self, when: datetime, latitude: float, longitude: float, house_system: str = "P") -> Dict[str, float]:
        """Return house cusps using the Swiss Ephemeris if available."""

        if swe is None:
            return self._fallback_houses(when, latitude, longitude)

        julian_day = self._julian_day(when)
        ayanamsa = AYANAMSA_OPTIONS.get(self.ayanamsa.lower(), AYANAMSA_OPTIONS["lahiri"])
        swe.set_sid_mode(ayanamsa, 0, 0)
        _, cusps, ascmc = swe.houses_ex(julian_day, latitude, longitude, house_system.encode("ascii"), 0)
        cusp_dict = {f"House {i}": self._normalise_angle(angle) for i, angle in enumerate(cusps, start=1)}
        cusp_dict.update({"Asc": ascmc[0], "MC": ascmc[1]})
        return cusp_dict

    def _compute_planet(self, planet_id: int, when: datetime) -> PlanetPosition:
        if swe is None:
            return self._fallback_planet(planet_id, when)

        julian_day = self._julian_day(when)
        ayanamsa = AYANAMSA_OPTIONS.get(self.ayanamsa.lower(), AYANAMSA_OPTIONS["lahiri"])
        swe.set_sid_mode(ayanamsa, 0, 0)
        flags = swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_SIDEREAL
        lon, lat, dist, speed_lon, speed_lat, speed_dist = swe.calc_ut(julian_day, planet_id, flags)
        ra, decl, _ = swe.calc_ut(julian_day, planet_id, swe.FLG_EQUATORIAL)
        return PlanetPosition(
            longitude=self._normalise_angle(lon),
            latitude=lat,
            speed_longitude=speed_lon,
            right_ascension=ra,
            declination=decl,
        )

    def _compute_upagrahas(self, when: datetime) -> Dict[str, PlanetPosition]:
        results: Dict[str, PlanetPosition] = {}
        for name in UPAGRAHAS:
            longitude = self._approximate_upagraha_longitude(name, when)
            results[name] = PlanetPosition(
                longitude=longitude,
                latitude=0.0,
                speed_longitude=0.0,
                right_ascension=longitude,
                declination=0.0,
            )
        return results

    # ------------------------------------------------------------------
    # Helpers

    @staticmethod
    def _julian_day(when: datetime) -> float:
        if swe is not None:
            return swe.julday(when.year, when.month, when.day, when.hour + when.minute / 60 + when.second / 3600)

        # Meeus approximation
        year, month = when.year, when.month
        day = when.day + (when.hour + (when.minute + when.second / 60) / 60) / 24
        if month <= 2:
            year -= 1
            month += 12
        a = math.floor(year / 100)
        b = 2 - a + math.floor(a / 4)
        jd = math.floor(365.25 * (year + 4716)) + math.floor(30.6001 * (month + 1)) + day + b - 1524.5
        return jd

    @staticmethod
    def _normalise_angle(angle: float) -> float:
        return float(angle % 360.0)

    def _approximate_upagraha_longitude(self, name: str, when: datetime) -> float:
        julian_day = self._julian_day(when)
        if name == "Gulika":
            return self._normalise_angle((julian_day * 13.176396) % 360)
        if name == "Mandi":
            return self._normalise_angle((julian_day * 11.0) % 360)
        return 0.0

    def _fallback_planet(self, planet_id: int, when: datetime) -> PlanetPosition:
        # Use simple circular motion as an approximation when Swiss Ephemeris is unavailable.
        julian_day = self._julian_day(when)
        orbital_periods = {
            0: 365.256,  # Sun
            1: 27.321661,  # Moon
            2: 87.969,
            3: 224.701,
            4: 686.98,
            5: 4332.59,
            6: 10759.22,
            7: 30688.5,
            8: 60182.0,
            9: 90465.0,
            10: 6798.0,
            11: 6798.0,
        }
        period = orbital_periods.get(planet_id, 365.25)
        longitude = self._normalise_angle((julian_day % period) / period * 360.0)
        speed = 360.0 / period
        return PlanetPosition(longitude=longitude, latitude=0.0, speed_longitude=speed, right_ascension=longitude, declination=0.0)

    def _fallback_houses(self, when: datetime, latitude: float, longitude: float) -> Dict[str, float]:
        # Simple equal house system fallback.
        ascendant = self._approximate_ascendant(when, latitude, longitude)
        return {f"House {i}": self._normalise_angle(ascendant + (i - 1) * 30.0) for i in range(1, 13)}

    def _approximate_ascendant(self, when: datetime, latitude: float, longitude: float) -> float:
        # Quick approximation using sidereal time.
        jd = self._julian_day(when)
        t = (jd - 2451545.0) / 36525.0
        gmst = 280.46061837 + 360.98564736629 * (jd - 2451545) + 0.000387933 * t ** 2 - t ** 3 / 38710000
        gmst = self._normalise_angle(gmst)
        local_sidereal_time = self._normalise_angle(gmst + longitude)
        asc = math.degrees(math.atan2(-math.cos(math.radians(local_sidereal_time)), math.sin(math.radians(local_sidereal_time)) * math.cos(math.radians(latitude))))
        return self._normalise_angle(asc)


def positions_dataframe(positions: Dict[str, PlanetPosition]) -> pd.DataFrame:
    """Convert the planetary position mapping to a dataframe."""

    data = []
    for name, pos in positions.items():
        row = {"Planet": name}
        row.update(pos.to_dict())
        data.append(row)
    return pd.DataFrame(data)
