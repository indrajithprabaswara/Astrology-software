from datetime import datetime

from dasha import compute_vimshottari


def test_vimshottari_sequence():
    moon_longitude = 120.0
    birth = datetime(1990, 1, 1, 6, 0, 0)
    periods = compute_vimshottari(moon_longitude, birth, levels=2)
    assert periods
    assert periods[0].lord in {"Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury", "Venus", "Ketu"}
    assert any(period.level == 2 for period in periods)
