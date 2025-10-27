"""Vimshottari dasha calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

try:  # pandas optional dependency.
    import pandas as pd
except ImportError:  # pragma: no cover - executed when pandas is missing.
    pd = None  # type: ignore[assignment]

NAKSHATRA_DEGREES = 13 + 20 / 60

DASHA_ORDER = [
    "Ketu",
    "Venus",
    "Sun",
    "Moon",
    "Mars",
    "Rahu",
    "Jupiter",
    "Saturn",
    "Mercury",
]

DASHA_YEARS = {
    "Ketu": 7,
    "Venus": 20,
    "Sun": 6,
    "Moon": 10,
    "Mars": 7,
    "Rahu": 18,
    "Jupiter": 16,
    "Saturn": 19,
    "Mercury": 17,
}


@dataclass
class DashaPeriod:
    lord: str
    start: datetime
    end: datetime
    level: int
    parent: str | None = None


def compute_vimshottari(moon_longitude: float, birth_datetime: datetime, levels: int = 3) -> List[DashaPeriod]:
    """Compute Vimshottari dasha periods."""

    nakshatra_index = int(moon_longitude // NAKSHATRA_DEGREES)
    balance = ((nakshatra_index + 1) * NAKSHATRA_DEGREES - moon_longitude) / NAKSHATRA_DEGREES
    lord = DASHA_ORDER[nakshatra_index % len(DASHA_ORDER)]
    start = birth_datetime
    remaining_years = DASHA_YEARS[lord] * balance
    end = start + timedelta(days=remaining_years * 365.25)
    periods = [DashaPeriod(lord=lord, start=start, end=end, level=1)]
    current_start = end
    index = (DASHA_ORDER.index(lord) + 1) % len(DASHA_ORDER)
    for _ in range(len(DASHA_ORDER) - 1):
        next_lord = DASHA_ORDER[index]
        duration_years = DASHA_YEARS[next_lord]
        next_end = current_start + timedelta(days=duration_years * 365.25)
        periods.append(DashaPeriod(lord=next_lord, start=current_start, end=next_end, level=1))
        current_start = next_end
        index = (index + 1) % len(DASHA_ORDER)
    if levels > 1:
        sub_periods = []
        for period in periods:
            sub_periods.extend(_sub_dashas(period, levels - 1))
        periods.extend(sub_periods)
    return periods


def _sub_dashas(parent_period: DashaPeriod, levels: int) -> List[DashaPeriod]:
    periods = []
    duration = parent_period.end - parent_period.start
    for lord in DASHA_ORDER:
        proportion = DASHA_YEARS[lord] / 120.0
        start = parent_period.start + duration * sum(DASHA_YEARS[DASHA_ORDER[i]] for i in range(DASHA_ORDER.index(lord))) / 120.0
        end = start + duration * proportion
        period = DashaPeriod(lord=lord, start=start, end=end, level=parent_period.level + 1, parent=parent_period.lord)
        periods.append(period)
        if levels > 1:
            periods.extend(_sub_dashas(period, levels - 1))
    return periods


def periods_to_dataframe(periods: List[DashaPeriod]) -> pd.DataFrame:
    if pd is None:  # pragma: no cover - simple guard
        raise RuntimeError("pandas is required to convert dasha periods to a DataFrame")

    return pd.DataFrame(
        [
            {
                "Lord": period.lord,
                "Start": period.start,
                "End": period.end,
                "Level": period.level,
                "Parent": period.parent,
            }
            for period in periods
        ]
    ).sort_values(["Level", "Start"]).reset_index(drop=True)
