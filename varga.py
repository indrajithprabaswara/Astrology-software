"""Divisional chart (varga) calculations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Tuple

ZODIAC_SIGNS = [
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
]


def _sign_index(longitude: float) -> int:
    return int((longitude % 360) // 30)


def _nth_part(longitude: float, division: int) -> int:
    degrees_in_part = 30.0 / division
    part = int(((longitude % 30.0) // degrees_in_part) % division)
    return part


def _odd_even_start(sign_idx: int, division: int) -> int:
    if sign_idx % 2 == 0:
        return 0
    return division // 2 if division % 2 == 0 else division - 1


def rasi(longitude: float) -> str:
    return ZODIAC_SIGNS[_sign_index(longitude)]


def hora(longitude: float) -> str:
    sign = _sign_index(longitude)
    part = _nth_part(longitude, 2)
    if sign % 2 == 0:
        return "Sun" if part == 0 else "Moon"
    return "Moon" if part == 0 else "Sun"


def drekkana(longitude: float) -> str:
    sign = _sign_index(longitude)
    part = _nth_part(longitude, 3)
    target = (sign + part * 4) % 12
    return ZODIAC_SIGNS[target]


def navamsa(longitude: float) -> str:
    sign = _sign_index(longitude)
    part = _nth_part(longitude, 9)
    target = (sign * 9 + part) % 12
    return ZODIAC_SIGNS[target]


def _uniform_division(longitude: float, division: int, offset: int = 0) -> str:
    sign = _sign_index(longitude)
    part = _nth_part(longitude, division)
    target = (sign * division + part + offset) % (12 * division)
    target_sign = (target // division) % 12
    return ZODIAC_SIGNS[target_sign]


def get_varga(name: str) -> Callable[[float], str]:
    mapping: Dict[str, Callable[[float], str]] = {
        "D1": rasi,
        "D2": lambda lon: _uniform_division(lon, 2),
        "D3": drekkana,
        "D4": lambda lon: _uniform_division(lon, 4),
        "D5": lambda lon: _uniform_division(lon, 5),
        "D6": lambda lon: _uniform_division(lon, 6),
        "D7": lambda lon: _uniform_division(lon, 7),
        "D8": lambda lon: _uniform_division(lon, 8),
        "D9": navamsa,
        "D10": lambda lon: _uniform_division(lon, 10),
        "D11": lambda lon: _uniform_division(lon, 11),
        "D12": lambda lon: _uniform_division(lon, 12),
        "D16": lambda lon: _uniform_division(lon, 16),
        "D20": lambda lon: _uniform_division(lon, 20),
        "D24": lambda lon: _uniform_division(lon, 24),
        "D27": lambda lon: _uniform_division(lon, 27),
        "D30": lambda lon: _uniform_division(lon, 30),
        "D40": lambda lon: _uniform_division(lon, 40),
        "D45": lambda lon: _uniform_division(lon, 45),
        "D60": lambda lon: _uniform_division(lon, 60),
    }
    if name not in mapping:
        raise KeyError(f"Unknown varga {name}")
    return mapping[name]


@dataclass
class VargaResult:
    """Container for divisional chart placement."""

    planet: str
    longitude: float
    varga_sign: str


class VargaCalculator:
    """Compute varga placements for planets."""

    def __init__(self, divisions: Tuple[str, ...] | None = None) -> None:
        self.divisions = divisions or (
            "D1",
            "D2",
            "D3",
            "D4",
            "D5",
            "D6",
            "D7",
            "D8",
            "D9",
            "D10",
            "D11",
            "D12",
            "D16",
            "D20",
            "D24",
            "D27",
            "D30",
            "D40",
            "D45",
            "D60",
        )

    def compute(self, planetary_longitudes: Dict[str, float]) -> Dict[str, Dict[str, str]]:
        """Return mapping of division -> planet -> sign."""

        results: Dict[str, Dict[str, str]] = {}
        for division in self.divisions:
            func = get_varga(division)
            results[division] = {planet: func(lon) for planet, lon in planetary_longitudes.items()}
        return results
