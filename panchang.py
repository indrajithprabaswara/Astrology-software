"""Panchang calculations for tithi, nakshatra, yoga and karana."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from ephemeris import DailyPeriod, EphemerisCalculator, RiseSetTimes

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
    moonrise: Optional[datetime]
    moonset: Optional[datetime]
    tithi_start: datetime
    tithi_end: datetime
    nakshatra_end: datetime
    yoga_end: datetime
    karana_end: datetime
    rahu_kalam: DailyPeriod | None
    yamaganda: DailyPeriod | None
    gulika_kalam: DailyPeriod | None


class PanchangCalculator:
    """Compute basic panchang details."""

    def __init__(self, ephemeris: EphemerisCalculator | None = None) -> None:
        self.ephemeris = ephemeris or EphemerisCalculator()

    def compute(
        self, when: datetime, latitude: float, longitude: float, tz_offset_hours: Optional[float] = None
    ) -> PanchangDetails:
        positions = self.ephemeris.planetary_positions(when, latitude, longitude)
        sun = positions["Sun"]
        moon = positions["Moon"]
        weekday = when.strftime("%A")

        tithi_index, tithi_start, tithi_end = self._tithi_interval(when, sun, moon)
        nakshatra_index, nak_end = self._nakshatra_interval(when, moon)
        yoga_index, yoga_end = self._yoga_interval(when, sun, moon)
        karana_index, karana_end = self._karana_interval(when, sun, moon)

        riseset = self.ephemeris.sunrise_sunset(when, latitude, longitude, tz_offset_hours)
        if riseset is None:
            sunrise = when.replace(hour=6, minute=0, second=0, microsecond=0)
            sunset = when.replace(hour=18, minute=0, second=0, microsecond=0)
        else:
            sunrise, sunset = riseset.sunrise, riseset.sunset

        moonrise, moonset = self.ephemeris.body_rise_set(when, latitude, longitude, "Moon", tz_offset_hours)

        periods = self.ephemeris.rahu_kalam_periods(when, latitude, longitude, tz_offset_hours)
        rahu = next((p for p in periods if p.name == "Rahu Kalam"), None)
        yamaganda = next((p for p in periods if p.name == "Yamaganda"), None)
        gulika = next((p for p in periods if p.name == "Gulika Kalam"), None)

        return PanchangDetails(
            tithi=f"Tithi {tithi_index + 1}",
            nakshatra=f"Nakshatra {nakshatra_index + 1}",
            yoga=f"Yoga {yoga_index + 1}",
            karana=f"Karana {karana_index + 1}",
            weekday=weekday,
            sunrise=sunrise,
            sunset=sunset,
            moonrise=moonrise,
            moonset=moonset,
            tithi_start=tithi_start,
            tithi_end=tithi_end,
            nakshatra_end=nak_end,
            yoga_end=yoga_end,
            karana_end=karana_end,
            rahu_kalam=rahu,
            yamaganda=yamaganda,
            gulika_kalam=gulika,
        )

    def to_dataframe(self, details: PanchangDetails) -> pd.DataFrame:
        def fmt(value):
            if isinstance(value, datetime):
                return value.isoformat()
            if isinstance(value, DailyPeriod):
                return f"{fmt(value.start)} - {fmt(value.end)}"
            if value is None:
                return "N/A"
            return value

        return pd.DataFrame(
            [
                {"Metric": "Tithi", "Value": fmt(details.tithi)},
                {"Metric": "Nakshatra", "Value": fmt(details.nakshatra)},
                {"Metric": "Yoga", "Value": fmt(details.yoga)},
                {"Metric": "Karana", "Value": fmt(details.karana)},
                {"Metric": "Weekday", "Value": fmt(details.weekday)},
                {"Metric": "Sunrise", "Value": fmt(details.sunrise)},
                {"Metric": "Sunset", "Value": fmt(details.sunset)},
                {"Metric": "Moonrise", "Value": fmt(details.moonrise)},
                {"Metric": "Moonset", "Value": fmt(details.moonset)},
                {"Metric": "Tithi ends", "Value": fmt(details.tithi_end)},
                {"Metric": "Nakshatra ends", "Value": fmt(details.nakshatra_end)},
                {"Metric": "Yoga ends", "Value": fmt(details.yoga_end)},
                {"Metric": "Karana ends", "Value": fmt(details.karana_end)},
                {"Metric": "Rahu Kalam", "Value": fmt(details.rahu_kalam)},
                {"Metric": "Yamaganda", "Value": fmt(details.yamaganda)},
                {"Metric": "Gulika Kalam", "Value": fmt(details.gulika_kalam)},
            ]
        )

    # ------------------------------------------------------------------
    # Internal helpers

    def _tithi_interval(self, when: datetime, sun, moon):
        diff = (moon.longitude - sun.longitude) % 360
        index = int(diff / TITHI_SPAN)
        remainder = diff - index * TITHI_SPAN
        rel_speed = self._relative_speed(moon.speed_longitude, sun.speed_longitude)
        start = when - self._time_delta_from_degrees(remainder, rel_speed)
        end = when + self._time_delta_from_degrees(TITHI_SPAN - remainder, rel_speed)
        return index, start, end

    def _nakshatra_interval(self, when: datetime, moon):
        diff = moon.longitude % NAKSHATRA_SPAN
        speed = max(abs(moon.speed_longitude), 0.1)
        start = when - self._time_delta_from_degrees(diff, speed)
        end = when + self._time_delta_from_degrees(NAKSHATRA_SPAN - diff, speed)
        index = int(moon.longitude / NAKSHATRA_SPAN)
        return index, end

    def _yoga_interval(self, when: datetime, sun, moon):
        sum_long = (sun.longitude + moon.longitude) % 360
        index = int(sum_long / YOGA_SPAN)
        remainder = sum_long - index * YOGA_SPAN
        speed = max(abs(sun.speed_longitude) + abs(moon.speed_longitude), 0.1)
        end = when + self._time_delta_from_degrees(YOGA_SPAN - remainder, speed)
        return index, end

    def _karana_interval(self, when: datetime, sun, moon):
        diff = (moon.longitude - sun.longitude) % 360
        index = int(diff / KARANA_SPAN)
        remainder = diff - index * KARANA_SPAN
        rel_speed = self._relative_speed(moon.speed_longitude, sun.speed_longitude)
        end = when + self._time_delta_from_degrees(KARANA_SPAN - remainder, rel_speed)
        return index, end

    @staticmethod
    def _relative_speed(moon_speed: float, sun_speed: float) -> float:
        speed = moon_speed - sun_speed
        return max(abs(speed), 0.1)

    @staticmethod
    def _time_delta_from_degrees(delta: float, speed: float) -> timedelta:
        days = delta / speed
        return timedelta(days=days)
