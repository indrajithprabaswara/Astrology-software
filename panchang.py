"""Panchang calculations for tithi, nakshatra, yoga and karana."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import pandas as pd

from ephemeris import EphemerisCalculator

TITHI_SPAN = 12.0
NAKSHATRA_SPAN = 13 + 20 / 60
YOGA_SPAN = 13 + 20 / 60
KARANA_SPAN = 6.0


@dataclass
class PanchangDetails:
    tithi: str
    nakshatra: str
    yoga: str
    karana: str
    weekday: str
    sunrise: datetime
    sunset: datetime
    moonrise: datetime
    moonset: datetime


class PanchangCalculator:
    """Compute basic panchang details."""

    def __init__(self, ephemeris: EphemerisCalculator | None = None) -> None:
        self.ephemeris = ephemeris or EphemerisCalculator()

    def compute(self, when: datetime, latitude: float, longitude: float) -> PanchangDetails:
        positions = self.ephemeris.planetary_positions(when)
        sun = positions["Sun"].longitude
        moon = positions["Moon"].longitude
        tithi_index = int(((moon - sun) % 360) / TITHI_SPAN)
        tithi = f"Tithi {tithi_index + 1}"
        nakshatra_index = int(moon / NAKSHATRA_SPAN)
        nakshatra = f"Nakshatra {nakshatra_index + 1}"
        yoga_index = int(((sun + moon) % 360) / YOGA_SPAN)
        yoga = f"Yoga {yoga_index + 1}"
        karana_index = int(((moon - sun) % 360) / KARANA_SPAN)
        karana = f"Karana {karana_index + 1}"
        weekday = when.strftime("%A")
        sunrise = when.replace(hour=6, minute=0, second=0)
        sunset = when.replace(hour=18, minute=0, second=0)
        moonrise = when.replace(hour=20, minute=0, second=0)
        moonset = when.replace(hour=7, minute=0, second=0) + timedelta(days=1)
        return PanchangDetails(tithi, nakshatra, yoga, karana, weekday, sunrise, sunset, moonrise, moonset)

    def to_dataframe(self, details: PanchangDetails) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"Metric": "Tithi", "Value": details.tithi},
                {"Metric": "Nakshatra", "Value": details.nakshatra},
                {"Metric": "Yoga", "Value": details.yoga},
                {"Metric": "Karana", "Value": details.karana},
                {"Metric": "Weekday", "Value": details.weekday},
                {"Metric": "Sunrise", "Value": details.sunrise},
                {"Metric": "Sunset", "Value": details.sunset},
                {"Metric": "Moonrise", "Value": details.moonrise},
                {"Metric": "Moonset", "Value": details.moonset},
            ]
        )
