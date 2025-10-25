from ephemeris import PlanetPosition
from strength import StrengthCalculator


def make_positions():
    return {
        "Sun": PlanetPosition(120.0, 0.0, 1.0, 0.0, 0.0),
        "Moon": PlanetPosition(150.0, 0.0, 12.0, 0.0, 0.0),
        "Mars": PlanetPosition(210.0, 0.0, 0.5, 0.0, 0.0),
        "Mercury": PlanetPosition(90.0, 0.0, 1.5, 0.0, 0.0),
        "Jupiter": PlanetPosition(60.0, 0.0, 0.8, 0.0, 0.0),
        "Venus": PlanetPosition(30.0, 0.0, 1.2, 0.0, 0.0),
        "Saturn": PlanetPosition(300.0, 0.0, 0.3, 0.0, 0.0),
        "Rahu": PlanetPosition(180.0, 0.0, -0.1, 0.0, 0.0),
        "Ketu": PlanetPosition(0.0, 0.0, 0.1, 0.0, 0.0),
    }


def make_houses():
    return {f"House {i}": (i - 1) * 30.0 for i in range(1, 13)} | {"Asc": 0.0}


def make_vargas():
    return {"D1": {planet: "Aries" for planet in make_positions().keys()}, "D9": {planet: "Aries" for planet in make_positions().keys()}}


def test_shadbala_output():
    calc = StrengthCalculator(make_positions(), make_houses(), make_vargas())
    df = calc.shadbala()
    assert not df.empty
    assert set(df.columns) >= {"Planet", "Total"}


def test_bhavabala_output():
    calc = StrengthCalculator(make_positions(), make_houses(), make_vargas())
    df = calc.bhavabala()
    assert len(df) == 12
    assert df["Strength"].mean() > 0
