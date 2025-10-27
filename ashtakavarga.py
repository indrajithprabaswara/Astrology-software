"""Ashtakavarga calculation module."""

from __future__ import annotations

from typing import Dict

import pandas as pd

# Contribution rules are adapted from classical Parashara tables. The
# structure is planet -> contributor -> 12-house bindu pattern.
SUN_ASHTAKA = {
    "Sun": [1, 1, 0, 1, 0, 0, 1, 1, 1, 1, 1, 0],
    "Moon": [0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 1, 0],
    "Mars": [1, 1, 0, 1, 0, 0, 1, 1, 1, 1, 1, 0],
    "Mercury": [0, 0, 1, 0, 1, 1, 0, 0, 1, 1, 1, 1],
    "Jupiter": [0, 0, 0, 0, 1, 1, 0, 0, 1, 0, 1, 1],
    "Venus": [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
    "Saturn": [1, 1, 0, 1, 0, 0, 1, 1, 1, 1, 1, 0],
    "Asc": [0, 0, 1, 1, 0, 1, 0, 0, 0, 1, 1, 1],
}

MOON_ASHTAKA = {
    "Sun": [0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 1, 0],
    "Moon": [1, 0, 0, 1, 0, 1, 0, 0, 1, 1, 0, 1],
    "Mars": [1, 1, 0, 1, 0, 0, 1, 1, 1, 1, 0, 0],
    "Mercury": [0, 1, 0, 0, 1, 1, 0, 0, 1, 1, 1, 0],
    "Jupiter": [0, 0, 0, 0, 1, 1, 0, 1, 1, 0, 1, 1],
    "Venus": [0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1],
    "Saturn": [1, 0, 0, 1, 0, 0, 1, 1, 1, 1, 0, 0],
    "Asc": [0, 0, 1, 1, 0, 1, 0, 0, 0, 1, 1, 1],
}

MARS_ASHTAKA = {
    "Sun": [1, 1, 0, 1, 0, 0, 1, 1, 1, 1, 1, 0],
    "Moon": [0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 1, 0],
    "Mars": [1, 1, 0, 1, 0, 0, 1, 1, 1, 1, 1, 0],
    "Mercury": [0, 0, 1, 0, 1, 1, 0, 0, 1, 1, 1, 0],
    "Jupiter": [0, 0, 0, 0, 1, 1, 0, 0, 1, 0, 1, 1],
    "Venus": [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 1],
    "Saturn": [1, 1, 0, 1, 0, 0, 1, 1, 1, 1, 1, 0],
    "Asc": [0, 0, 1, 1, 0, 1, 0, 0, 0, 1, 1, 1],
}

MERCURY_ASHTAKA = {
    "Sun": [1, 0, 0, 1, 0, 1, 0, 0, 0, 1, 1, 0],
    "Moon": [0, 1, 0, 0, 1, 1, 0, 0, 1, 1, 1, 0],
    "Mars": [1, 1, 0, 1, 0, 0, 1, 1, 1, 1, 0, 0],
    "Mercury": [1, 0, 1, 0, 1, 1, 0, 0, 1, 1, 1, 1],
    "Jupiter": [0, 0, 0, 0, 1, 1, 0, 1, 1, 0, 1, 1],
    "Venus": [0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1],
    "Saturn": [1, 0, 0, 1, 0, 0, 1, 1, 1, 1, 0, 0],
    "Asc": [0, 0, 1, 1, 0, 1, 0, 0, 0, 1, 1, 1],
}

JUPITER_ASHTAKA = {
    "Sun": [0, 0, 1, 0, 0, 1, 0, 0, 1, 1, 1, 0],
    "Moon": [0, 1, 0, 0, 1, 1, 0, 0, 1, 1, 1, 0],
    "Mars": [1, 1, 0, 1, 0, 0, 1, 1, 1, 1, 0, 0],
    "Mercury": [0, 0, 1, 0, 1, 1, 0, 0, 1, 1, 1, 1],
    "Jupiter": [1, 0, 0, 0, 1, 1, 0, 1, 1, 0, 1, 1],
    "Venus": [0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1],
    "Saturn": [1, 0, 0, 1, 0, 0, 1, 1, 1, 1, 0, 0],
    "Asc": [0, 0, 1, 1, 0, 1, 0, 0, 0, 1, 1, 1],
}

VENUS_ASHTAKA = {
    "Sun": [0, 0, 1, 0, 0, 1, 0, 0, 1, 1, 0, 0],
    "Moon": [0, 0, 1, 0, 1, 1, 0, 0, 1, 1, 1, 0],
    "Mars": [1, 1, 0, 1, 0, 0, 1, 1, 1, 1, 0, 0],
    "Mercury": [0, 1, 1, 0, 1, 1, 0, 0, 1, 1, 1, 1],
    "Jupiter": [0, 0, 0, 0, 1, 1, 0, 1, 1, 0, 1, 1],
    "Venus": [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 1],
    "Saturn": [1, 0, 0, 1, 0, 0, 1, 1, 1, 1, 0, 0],
    "Asc": [0, 0, 1, 1, 0, 1, 0, 0, 0, 1, 1, 1],
}

SATURN_ASHTAKA = {
    "Sun": [1, 1, 0, 1, 0, 0, 1, 1, 1, 1, 1, 0],
    "Moon": [0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 1, 0],
    "Mars": [1, 1, 0, 1, 0, 0, 1, 1, 1, 1, 1, 0],
    "Mercury": [0, 1, 0, 0, 1, 1, 0, 0, 1, 1, 1, 1],
    "Jupiter": [0, 0, 0, 0, 1, 1, 0, 1, 1, 0, 1, 1],
    "Venus": [0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1],
    "Saturn": [1, 0, 0, 1, 0, 0, 1, 1, 1, 1, 1, 0],
    "Asc": [0, 0, 1, 1, 0, 1, 0, 0, 0, 1, 1, 1],
}

ASHTAKA_RULES = {
    "Sun": SUN_ASHTAKA,
    "Moon": MOON_ASHTAKA,
    "Mars": MARS_ASHTAKA,
    "Mercury": MERCURY_ASHTAKA,
    "Jupiter": JUPITER_ASHTAKA,
    "Venus": VENUS_ASHTAKA,
    "Saturn": SATURN_ASHTAKA,
}


class AshtakavargaCalculator:
    """Compute Bhinnashtakavarga and Sarvashtakavarga bindus."""

    def __init__(self, positions: Dict[str, float], ascendant: float) -> None:
        self.positions = dict(positions)
        self.positions["Asc"] = ascendant
        self.planets = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]

    def compute_bhinnashtakavarga(self) -> Dict[str, pd.DataFrame]:
        results: Dict[str, pd.DataFrame] = {}
        for planet in self.planets:
            rules = ASHTAKA_RULES.get(planet)
            if not rules:
                continue

            index = self.planets + ["Asc"]
            chart = pd.DataFrame(0, index=index, columns=range(1, 13))

            for contributor, pattern in rules.items():
                contributor_pos = self.positions.get(contributor)
                if contributor_pos is None:
                    continue
                base_sign = int(contributor_pos // 30)
                for offset, gives_bindu in enumerate(pattern):
                    if gives_bindu:
                        target_sign = (base_sign + offset) % 12 + 1
                        chart.loc[contributor, target_sign] = 1

            chart.loc["Total"] = chart.sum()
            results[planet] = chart
        return results

    def compute_sarvashtakavarga(self, bhinnashtakavarga: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        sav = pd.DataFrame(0, index=self.planets, columns=range(1, 13))
        for planet, df in bhinnashtakavarga.items():
            sav.loc[planet] = df.loc["Total", :]
        sav.loc["Total"] = sav.sum()
        return sav
