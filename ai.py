"""AI assisted auspicious time predictor with divisional and strength context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

from dasha import compute_vimshottari
from ephemeris import EphemerisCalculator
from strength import StrengthCalculator
from varga import VargaCalculator

ACTIVITY_WEIGHTS: Dict[str, Dict[str, object]] = {
    "Business": {
        "planet_weights": {"Mercury": 1.2, "Jupiter": 1.0, "Saturn": 0.8},
        "house_weights": {10: 1.0, 11: 1.0, 2: 0.8},
        "ishta_kashta_impact": 1.5,
        "dasha_impact": -2.0,
    },
    "Marriage": {
        "planet_weights": {"Venus": 1.5, "Jupiter": 1.2, "Moon": 1.0},
        "house_weights": {7: 2.0, 2: 0.5, 1: 0.5},
        "ishta_kashta_impact": 1.0,
        "dasha_impact": -1.5,
    },
    "Travel": {
        "planet_weights": {"Mercury": 1.0, "Moon": 1.0, "Mars": 0.8},
        "house_weights": {3: 0.5, 9: 1.0, 12: 0.5},
        "ishta_kashta_impact": 0.8,
        "dasha_impact": -1.0,
    },
    "Exams": {
        "planet_weights": {"Mercury": 1.4, "Jupiter": 1.1},
        "house_weights": {5: 1.0, 9: 1.0},
        "ishta_kashta_impact": 1.2,
        "dasha_impact": -1.0,
    },
}


@dataclass
class PredictionResult:
    start: datetime
    end: datetime
    score: float
    explanation: str


class AIPredictor:
    """Rank time ranges based on combined strengths and natal context."""

    def __init__(self, ephemeris: EphemerisCalculator) -> None:
        self.ephemeris = ephemeris
        self.activity_weights = ACTIVITY_WEIGHTS
        self.varga_calculator = VargaCalculator(divisions=("D1", "D9"))

    def predict(
        self,
        activity: str,
        start: datetime,
        end: datetime,
        latitude: float,
        longitude: float,
        birth_dt: Optional[datetime] = None,
        birth_moon_lon: Optional[float] = None,
        birth_ashtakavarga: Optional[pd.DataFrame] = None,
        interval_minutes: int = 60,
    ) -> pd.DataFrame:
        weights = self.activity_weights.get(activity, {})
        planet_weights: Dict[str, float] = weights.get("planet_weights", {"Jupiter": 1.0})  # type: ignore[arg-type]
        house_weights: Dict[int, float] = weights.get("house_weights", {})  # type: ignore[arg-type]
        results: List[PredictionResult] = []
        current = start
        while current < end:
            positions = self.ephemeris.planetary_positions(current, latitude, longitude)
            houses = self.ephemeris.house_cusps(current, latitude, longitude)
            varga_details = self.varga_calculator.compute(
                {planet: pos.longitude for planet, pos in positions.items() if planet not in {"Gulika", "Mandi"}}
            )
            varga_summary = {
                division: {planet: placement.sign for planet, placement in placements.items()}
                for division, placements in varga_details.items()
            }
            strength = StrengthCalculator(positions, houses, varga_summary)
            shadbala_df = strength.shadbala().set_index("Planet")
            bhava_df = strength.bhavabala().set_index("House")
            ishta_df = strength.compute_ishta_kashta().set_index("Planet")

            shadbala_score = sum(shadbala_df.get("Total", pd.Series()).get(p, 0.0) * w for p, w in planet_weights.items())
            bhava_score = sum(bhava_df.get("Strength", pd.Series()).get(h, 0.0) * w for h, w in house_weights.items())
            ishta_score = sum(ishta_df.get("Ratio", pd.Series()).get(p, 0.5) * w for p, w in planet_weights.items())

            penalties = self._temporal_penalties(current, latitude, longitude)
            natal_bonus = 0.0
            if birth_ashtakavarga is not None:
                for planet, weight in planet_weights.items():
                    pos = positions.get(planet)
                    if pos is None or planet not in birth_ashtakavarga.index:
                        continue
                    sign = int(pos.longitude // 30) + 1
                    bindus = birth_ashtakavarga.loc[planet, sign]
                    if bindus > 4:
                        natal_bonus += (bindus - 4) * weight

            dasha_penalty = 0.0
            if birth_dt and birth_moon_lon is not None:
                dashas = compute_vimshottari(birth_moon_lon, birth_dt, levels=3)
                antardasha_lord = self._find_active_antardasha(dashas, current)
                if antardasha_lord in {"Saturn", "Mars", "Rahu", "Ketu"}:
                    dasha_penalty = weights.get("dasha_impact", 0.0)  # type: ignore[arg-type]

            score = shadbala_score + bhava_score + ishta_score * weights.get("ishta_kashta_impact", 1.0) * 10  # type: ignore[arg-type]
            score += natal_bonus + dasha_penalty
            score *= penalties["multiplier"]

            explanation_parts = []
            for planet in planet_weights:
                total = shadbala_df.get("Total", pd.Series()).get(planet, 0.0)
                ratio = ishta_df.get("Ratio", pd.Series()).get(planet, 0.0)
                explanation_parts.append(f"{planet}:{total:.1f} Ishta:{ratio:.2f}")
            if penalties["notes"]:
                explanation_parts.append("Penalties:" + ",".join(penalties["notes"]))
            explanation = "; ".join(explanation_parts)
            results.append(
                PredictionResult(
                    start=current,
                    end=current + timedelta(minutes=interval_minutes),
                    score=float(score),
                    explanation=f"Planet strengths - {explanation}; Bhava score {bhava_score:.1f}",
                )
            )
            current += timedelta(minutes=interval_minutes)
        df = pd.DataFrame(
            {
                "Start": [r.start for r in results],
                "End": [r.end for r in results],
                "Score": [r.score for r in results],
                "Explanation": [r.explanation for r in results],
            }
        )
        return df.sort_values("Score", ascending=False).reset_index(drop=True)

    def _temporal_penalties(self, when: datetime, latitude: float, longitude: float) -> dict:
        periods = self.ephemeris.rahu_kalam_periods(when, latitude, longitude)
        multiplier = 1.0
        notes: List[str] = []
        for period in periods:
            if period.start <= when < period.end:
                if period.name == "Rahu Kalam":
                    multiplier *= 0.6
                elif period.name == "Yamaganda":
                    multiplier *= 0.75
                elif period.name == "Gulika Kalam":
                    multiplier *= 0.8
                notes.append(period.name)
        return {"multiplier": multiplier, "notes": notes}

    def _find_active_antardasha(self, dashas, when: datetime) -> Optional[str]:
        active: Optional[str] = None
        for period in dashas:
            if period.level == 2 and period.start <= when < period.end:
                active = period.lord
                break
        if active is None:
            for period in dashas:
                if period.level == 1 and period.start <= when < period.end:
                    active = period.lord
                    break
        return active
