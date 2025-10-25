"""AI assisted auspicious time predictor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

import pandas as pd

from ephemeris import EphemerisCalculator
from strength import StrengthCalculator
from varga import VargaCalculator

ACTIVITY_WEIGHTS = {
    "Business": {"Mercury": 1.2, "Jupiter": 1.0, "Saturn": 0.8},
    "Marriage": {"Venus": 1.5, "Jupiter": 1.2, "Moon": 1.0},
    "Travel": {"Mercury": 1.0, "Moon": 1.0, "Mars": 0.8},
    "Exams": {"Mercury": 1.4, "Jupiter": 1.1},
}


@dataclass
class PredictionResult:
    start: datetime
    end: datetime
    score: float
    explanation: str


class AIPredictor:
    """Rank time ranges based on combined strengths."""

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
        interval_minutes: int = 60,
    ) -> pd.DataFrame:
        weights = self.activity_weights.get(activity, {"Jupiter": 1.0})
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
            planet_scores = sum(shadbala_df.get("Total", pd.Series()).get(p, 100.0) * w for p, w in weights.items())
            bhava_score = bhava_df["Strength"].mean()
            score = float(planet_scores / max(len(weights), 1) + bhava_score)
            penalties = self._temporal_penalties(current, latitude, longitude)
            score *= penalties["multiplier"]

            explanation_parts = []
            for planet in weights:
                total = shadbala_df.get("Total", pd.Series()).get(planet, 0.0)
                navamsa = varga_details.get("D9", {}).get(planet)
                navamsa_part = f" Navamsa:{navamsa.sign}" if navamsa else ""
                explanation_parts.append(f"{planet}:{total:.1f}{navamsa_part}")
            if penalties["notes"]:
                explanation_parts.append("Penalties:" + ",".join(penalties["notes"]))
            explanation = "; ".join(explanation_parts)
            results.append(
                PredictionResult(
                    start=current,
                    end=current + timedelta(minutes=interval_minutes),
                    score=score,
                    explanation=f"Planet strengths - {explanation}; Bhava avg {bhava_score:.1f}",
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
