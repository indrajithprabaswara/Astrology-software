"""Swiss Ephemeris wrapper utilities."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple
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

#: Mapping of user friendly ayanamsa identifiers to Swiss Ephemeris constants.
_AYANAMSA_ALIASES = {
    "lahiri": "SIDM_LAHIRI",
    "chitrapaksha": "SIDM_LAHIRI",
    "raman": "SIDM_RAMAN",
    "krishnamurti": "SIDM_KRISHNAMURTI",
    "yukteswar": "SIDM_YUKTESWAR",
    "fagan": "SIDM_FAGAN_BRADLEY",
    "fagan_bradley": "SIDM_FAGAN_BRADLEY",
    "bradley": "SIDM_FAGAN_BRADLEY",
    "djwhal_khul": "SIDM_DJWHAL_KHUL",
    "galactic_center": "SIDM_GALCENT_0SAG",
    "surya_siddhanta": "SIDM_SURYASIDDHANTA",
    "suryasiddhanta": "SIDM_SURYASIDDHANTA",
    "j2000": "SIDM_J2000",
    "aryabhata": "SIDM_ARYABHATA",
}

# Pre-resolved ayanamsa codes used when Swiss Ephemeris is unavailable.
_FALLBACK_AYANAMSA_CODES = {
    "lahiri": 1,
    "chitrapaksha": 1,
    "raman": 2,
    "krishnamurti": 5,
    "yukteswar": 7,
    "fagan": 0,
    "fagan_bradley": 0,
    "bradley": 0,
    "surya_siddhanta": 11,
    "suryasiddhanta": 11,
    "j2000": 17,
}

# Default Swiss Ephemeris house system identifiers mapped to descriptive names.
HOUSE_SYSTEMS = {
    "P": "Placidus",
    "K": "Koch",
    "O": "Porphyrius",
    "R": "Regiomontanus",
    "C": "Campanus",
    "E": "Equal",
    "H": "Horizontal",
    "W": "Whole Sign",
}

ZENITH_DEGREES = 90.8333  # Civil twilight approximation used for sunrise/sunset


@dataclass
class PlanetPosition:
    """Positional data of a celestial body."""

    longitude: float
    latitude: float
    speed_longitude: float
    right_ascension: float
    declination: float
    retrograde: bool = False

    def to_dict(self) -> Dict[str, float | bool]:
        return {
            "longitude": self.longitude,
            "latitude": self.latitude,
            "speed": self.speed_longitude,
            "ra": self.right_ascension,
            "decl": self.declination,
            "retrograde": self.retrograde,
        }


@dataclass
class RiseSetTimes:
    """Simple container for sunrise/sunset data."""

    sunrise: datetime
    sunset: datetime
    moonrise: datetime | None = None
    moonset: datetime | None = None

    @property
    def daylight_duration(self) -> timedelta:
        return self.sunset - self.sunrise


@dataclass
class DailyPeriod:
    """Represents a named auspicious or inauspicious window."""

    name: str
    start: datetime
    end: datetime


class EphemerisCalculator:
    """High-level Swiss Ephemeris wrapper."""

    def __init__(self, ayanamsa: str = "lahiri") -> None:
        self.ayanamsa = ayanamsa
        self.house_system = "P"

    def set_ayanamsa(self, ayanamsa: str) -> None:
        self.ayanamsa = ayanamsa

    def set_house_system(self, house_system: str) -> None:
        if house_system.upper() not in HOUSE_SYSTEMS:
            raise ValueError(f"Unsupported house system: {house_system}")
        self.house_system = house_system.upper()

    # ------------------------------------------------------------------
    # Public API

    def planetary_positions(
        self, when: datetime, latitude: float | None = None, longitude: float | None = None
    ) -> Dict[str, PlanetPosition]:
        """Return sidereal positions for major planets and nodes."""

        positions: Dict[str, PlanetPosition] = {}
        for name, planet_id in PLANETS.items():
            positions[name] = self._compute_planet(planet_id, when)
        positions.update(self._compute_upagrahas(when, latitude, longitude))
        return positions

    def house_cusps(self, when: datetime, latitude: float, longitude: float, house_system: str = "P") -> Dict[str, float]:
        """Return house cusps using the Swiss Ephemeris if available."""

        if swe is None:
            return self._fallback_houses(when, latitude, longitude)

        julian_day = self._julian_day(when)
        ayanamsa = self._resolve_ayanamsa_code(self.ayanamsa)
        swe.set_sid_mode(ayanamsa, 0, 0)
        hs = house_system or self.house_system
        _, cusps, ascmc = swe.houses_ex(julian_day, latitude, longitude, hs.encode("ascii"), 0)
        cusp_dict = {f"House {i}": self._normalise_angle(angle) for i, angle in enumerate(cusps, start=1)}
        cusp_dict.update({"Asc": ascmc[0], "MC": ascmc[1]})
        return cusp_dict

    def _compute_planet(self, planet_id: int, when: datetime) -> PlanetPosition:
        if swe is None:
            return self._fallback_planet(planet_id, when)

        julian_day = self._julian_day(when)
        ayanamsa = self._resolve_ayanamsa_code(self.ayanamsa)
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
            retrograde=speed_lon < 0,
        )

    def compute_gulika_mandi(
        self, when: datetime, latitude: float, longitude: float, tz_offset_hours: float | None = None
    ) -> Tuple[float, float]:
        """Return the ecliptic longitudes of Gulika and Mandi."""

        tz_offset_hours = self._infer_timezone_offset(when, tz_offset_hours)
        riseset = self.sunrise_sunset(when, latitude, longitude, tz_offset_hours)
        if riseset is None:
            gulika = self._approximate_upagraha_longitude("Gulika", when)
            mandi = self._approximate_upagraha_longitude("Mandi", when)
            return gulika, mandi

        weekday = when.weekday()
        day_segment = riseset.daylight_duration / 8
        gulika_indices = [5, 4, 3, 2, 1, 0, 6]
        gulika_index = gulika_indices[weekday]
        gulika_start = riseset.sunrise + gulika_index * day_segment
        mandi_start = gulika_start + day_segment / 2
        gulika_longitude = self.ascendant_longitude(gulika_start, latitude, longitude)
        mandi_longitude = self.ascendant_longitude(mandi_start, latitude, longitude)
        return gulika_longitude, mandi_longitude

    # ------------------------------------------------------------------
    # Public astronomical helpers

    def sunrise_sunset(
        self, when: datetime, latitude: float, longitude: float, tz_offset_hours: float | None = None
    ) -> RiseSetTimes | None:
        """Compute sunrise and sunset times for the calendar date of *when*.

        The method currently relies on an approximation derived from the NOAA
        sunrise equation.  When Swiss Ephemeris is available a more precise
        computation is used.  The returned datetimes are timezone aware using
        the supplied or inferred offset.
        """

        tz_offset_hours = self._infer_timezone_offset(when, tz_offset_hours)
        local_tz = timezone(timedelta(hours=tz_offset_hours))
        date = when.astimezone(local_tz).date()

        if swe is not None:
            try:
                sunrise = self._swiss_rise_set(date, latitude, longitude, tz_offset_hours, is_sunrise=True)
                sunset = self._swiss_rise_set(date, latitude, longitude, tz_offset_hours, is_sunrise=False)
                return RiseSetTimes(sunrise=sunrise, sunset=sunset)
            except Exception:
                pass

        sunrise = self._approximate_rise_set(date, latitude, longitude, tz_offset_hours, is_sunrise=True)
        sunset = self._approximate_rise_set(date, latitude, longitude, tz_offset_hours, is_sunrise=False)
        if sunrise is None or sunset is None:
            return None
        if sunrise > sunset:
            sunrise -= timedelta(days=1)
        return RiseSetTimes(sunrise=sunrise, sunset=sunset)

    def rahu_kalam_periods(
        self, when: datetime, latitude: float, longitude: float, tz_offset_hours: float | None = None
    ) -> List[DailyPeriod]:
        riseset = self.sunrise_sunset(when, latitude, longitude, tz_offset_hours)
        if riseset is None:
            return []

        weekday = when.weekday()
        day_segment = riseset.daylight_duration / 8
        rahu_indices = [1, 6, 4, 5, 3, 2, 7]
        yamaganda_indices = [3, 2, 1, 0, 6, 5, 4]
        gulika_indices = [5, 4, 3, 2, 1, 0, 6]

        def _build(name: str, index: int) -> DailyPeriod:
            start = riseset.sunrise + index * day_segment
            end = start + day_segment
            return DailyPeriod(name=name, start=start, end=end)

        return [
            _build("Rahu Kalam", rahu_indices[weekday]),
            _build("Yamaganda", yamaganda_indices[weekday]),
            _build("Gulika Kalam", gulika_indices[weekday]),
        ]

    def body_rise_set(
        self, when: datetime, latitude: float, longitude: float, body: str, tz_offset_hours: float | None = None
    ) -> Tuple[datetime | None, datetime | None]:
        tz_offset_hours = self._infer_timezone_offset(when, tz_offset_hours)
        local_tz = timezone(timedelta(hours=tz_offset_hours))
        date = when.astimezone(local_tz).date()
        planet_id = PLANETS.get(body.title())
        if planet_id is None:
            raise ValueError(f"Unknown body: {body}")
        if swe is not None:
            jd = self._julian_day(datetime(date.year, date.month, date.day, tzinfo=timezone.utc))
            flag_rise = swe.CALC_RISE
            flag_set = swe.CALC_SET
            try:
                rise_res = swe.rise_trans(jd, planet_id, None, flag_rise, latitude, longitude, 0)
                set_res = swe.rise_trans(jd, planet_id, None, flag_set, latitude, longitude, 0)
                rise_local_hours = rise_res[1] + tz_offset_hours
                set_local_hours = set_res[1] + tz_offset_hours
                base = datetime(date.year, date.month, date.day, tzinfo=local_tz)
                return base + timedelta(hours=rise_local_hours), base + timedelta(hours=set_local_hours)
            except swe.Error:
                pass

        # Fallback: use sunrise as baseline and adjust using mean motion.
        riseset = self.sunrise_sunset(when, latitude, longitude, tz_offset_hours)
        if riseset is None:
            fallback_rise = datetime(date.year, date.month, date.day, 6, 0, tzinfo=local_tz)
            fallback_set = fallback_rise + timedelta(hours=12)
            return fallback_rise, fallback_set

        positions = self.planetary_positions(when, latitude, longitude)
        sun = positions["Sun"]
        target = positions.get(body.title())
        if target is None:
            return riseset.sunrise, riseset.sunset

        phase_diff = (target.longitude - sun.longitude) % 360
        rise_offset = phase_diff / 360 * 24
        rise = riseset.sunrise + timedelta(hours=rise_offset)
        set_time = rise + timedelta(hours=12)
        return rise, set_time

    def sidereal_longitude(self, tropical_longitude: float, when: datetime) -> float:
        """Convert a tropical longitude to sidereal using the configured ayanamsa."""

        ayanamsa_value = self.ayanamsa_value(when)
        return self._normalise_angle(tropical_longitude - ayanamsa_value)

    def ayanamsa_value(self, when: datetime) -> float:
        """Return the ayanamsa value in degrees for the configured mode."""

        julian_day = self._julian_day(when)
        if swe is not None:
            code = self._resolve_ayanamsa_code(self.ayanamsa)
            swe.set_sid_mode(code, 0, 0)
            return swe.get_ayanamsa_ut(julian_day)
        # Fallback: linear precession approximation (~24° for Lahiri circa 2000)
        t = (julian_day - 2451545.0) / 36525.0
        return 24.0 + 0.0001 * t

    def _compute_upagrahas(
        self, when: datetime, latitude: float | None, longitude: float | None
    ) -> Dict[str, PlanetPosition]:
        results: Dict[str, PlanetPosition] = {}
        if latitude is not None and longitude is not None:
            gulika, mandi = self.compute_gulika_mandi(when, latitude, longitude)
            mapping = {"Gulika": gulika, "Mandi": mandi}
        else:
            mapping = {name: self._approximate_upagraha_longitude(name, when) for name in UPAGRAHAS}
        for name, position in mapping.items():
            results[name] = PlanetPosition(
                longitude=self._normalise_angle(position),
                latitude=0.0,
                speed_longitude=0.0,
                right_ascension=self._normalise_angle(position),
                declination=0.0,
            )
        return results

    # ------------------------------------------------------------------
    # Helpers

    @staticmethod
    def _julian_day(when: datetime) -> float:
        if when.tzinfo is not None:
            when = when.astimezone(timezone.utc).replace(tzinfo=None)
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
        return PlanetPosition(
            longitude=longitude,
            latitude=0.0,
            speed_longitude=speed,
            right_ascension=longitude,
            declination=0.0,
            retrograde=False,
        )

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

    def ascendant_longitude(self, when: datetime, latitude: float, longitude: float) -> float:
        if swe is None:
            return self._approximate_ascendant(when, latitude, longitude)
        julian_day = self._julian_day(when)
        code = self._resolve_ayanamsa_code(self.ayanamsa)
        swe.set_sid_mode(code, 0, 0)
        _, cusps, ascmc = swe.houses_ex(julian_day, latitude, longitude, self.house_system.encode("ascii"), 0)
        return self._normalise_angle(ascmc[0])

    def _resolve_ayanamsa_code(self, ayanamsa: str) -> int:
        key = ayanamsa.lower()
        if swe is not None:
            attr = _AYANAMSA_ALIASES.get(key)
            if attr and hasattr(swe, attr):
                return int(getattr(swe, attr))
        return _FALLBACK_AYANAMSA_CODES.get(key, _FALLBACK_AYANAMSA_CODES.get("lahiri", 1))

    def _infer_timezone_offset(self, when: datetime, tz_offset_hours: float | None) -> float:
        if tz_offset_hours is not None:
            return tz_offset_hours
        if when.tzinfo is not None:
            offset = when.utcoffset()
            if offset is not None:
                return offset.total_seconds() / 3600
        return 0.0

    def _swiss_rise_set(
        self, date, latitude: float, longitude: float, tz_offset_hours: float, is_sunrise: bool
    ) -> datetime:
        raise RuntimeError("Swiss ephemeris rise/set not implemented in this environment")

    def _approximate_rise_set(
        self, date, latitude: float, longitude: float, tz_offset_hours: float, *, is_sunrise: bool
    ) -> datetime | None:
        day_of_year = date.timetuple().tm_yday
        lng_hour = longitude / 15.0
        t = day_of_year + ((6 - lng_hour) / 24 if is_sunrise else (18 - lng_hour) / 24)
        m = (0.9856 * t) - 3.289
        l = m + 1.916 * math.sin(math.radians(m)) + 0.020 * math.sin(math.radians(2 * m)) + 282.634
        l = self._normalise_angle(l)
        ra = math.degrees(math.atan(0.91764 * math.tan(math.radians(l))))
        l_quadrant = math.floor(l / 90.0) * 90
        ra_quadrant = math.floor(ra / 90.0) * 90
        ra = ra + (l_quadrant - ra_quadrant)
        ra /= 15.0
        sin_dec = 0.39782 * math.sin(math.radians(l))
        cos_dec = math.cos(math.asin(sin_dec))
        cos_h = (
            math.cos(math.radians(ZENITH_DEGREES))
            - sin_dec * math.sin(math.radians(latitude))
        ) / (cos_dec * math.cos(math.radians(latitude)))
        if cos_h > 1:
            return None  # Sun never rises on this location at this date
        if cos_h < -1:
            return None  # Sun never sets
        h = 360 - math.degrees(math.acos(cos_h)) if is_sunrise else math.degrees(math.acos(cos_h))
        h /= 15.0
        t_local = h + ra - (0.06571 * t) - 6.622
        ut = (t_local - lng_hour) % 24
        local_time_hours = ut + tz_offset_hours
        local_tz = timezone(timedelta(hours=tz_offset_hours))
        base = datetime(date.year, date.month, date.day, tzinfo=local_tz)
        return base + timedelta(hours=local_time_hours)


def positions_dataframe(positions: Dict[str, PlanetPosition]) -> pd.DataFrame:
    """Convert the planetary position mapping to a dataframe."""

    data = []
    for name, pos in positions.items():
        row = {"Planet": name}
        row.update(pos.to_dict())
        data.append(row)
    return pd.DataFrame(data)
