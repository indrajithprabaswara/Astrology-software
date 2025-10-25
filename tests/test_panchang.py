from datetime import datetime

from panchang import PanchangCalculator


def test_panchang_returns_extended_fields():
    calculator = PanchangCalculator()
    details = calculator.compute(datetime(2023, 6, 1, 6, 0), latitude=28.6139, longitude=77.2090)

    assert details.tithi.startswith("Tithi ")
    assert details.nakshatra.startswith("Nakshatra ")
    assert details.yoga.startswith("Yoga ")
    assert details.karana.startswith("Karana ")

    assert details.tithi_end > details.tithi_start
    assert details.sunset > details.sunrise
    assert details.rahu_kalam is None or details.rahu_kalam.end > details.rahu_kalam.start
