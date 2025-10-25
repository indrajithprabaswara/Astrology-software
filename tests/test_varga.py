from varga import get_varga


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
