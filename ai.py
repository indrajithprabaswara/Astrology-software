"""AI assisted auspicious time predictor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

import pandas as pd

from ephemeris import EphemerisCalculator
from strength import StrengthCalculator

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
            positions = self.ephemeris.planetary_positions(current)
            houses = self.ephemeris.house_cusps(current, latitude, longitude)
            vargas = {"D1": {planet: "Aries" for planet in positions.keys()}, "D9": {planet: "Aries" for planet in positions.keys()}}
            strength = StrengthCalculator(positions, houses, vargas)
            shadbala_df = strength.shadbala().set_index("Planet")
            bhava_df = strength.bhavabala().set_index("House")
            planet_scores = sum(shadbala_df.get("Total", pd.Series()).get(p, 100.0) * w for p, w in weights.items())
            bhava_score = bhava_df["Strength"].mean()
            score = float(planet_scores / len(weights) + bhava_score)
            explanation = ", ".join(f"{p}: {shadbala_df.get('Total', pd.Series()).get(p, 0):.1f}" for p in weights)
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
