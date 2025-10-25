from varga import VargaCalculator, ZODIAC_SIGNS, get_varga


def test_navamsa_rules():
    navamsa = get_varga("D9")
    assert navamsa(0.0) == "Aries"
    assert navamsa(33.3333) in {"Capricorn", "Aquarius"}


def test_drekkana_progression():
    drekkana = get_varga("D3")
    assert drekkana(0.0) == "Aries"
    assert drekkana(150.0) == "Virgo"
    assert drekkana(160.0) == "Capricorn"


def test_uniform_division():
    d12 = get_varga("D12")
    assert d12(0.0) == "Aries"
    assert d12(150.0) in {"Virgo", "Libra"}


def test_varga_calculator_returns_degree_information():
    calc = VargaCalculator(divisions=("D9",))
    placements = calc.compute({"Sun": 123.5})
    sun_navamsa = placements["D9"]["Sun"]
    assert sun_navamsa.sign in ZODIAC_SIGNS
    assert 0.0 <= sun_navamsa.degree < 30.0
