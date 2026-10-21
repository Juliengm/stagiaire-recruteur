from datetime import date

from veille_pipeline.health import (
    SourceHealth,
    failing_sources,
    invalid_offer_reasons,
    silent_sources,
)


def test_silent_after_three_empty_runs():
    sources = [SourceHealth("a", 0, 2), SourceHealth("b", 0, 3), SourceHealth("c", 0, 5, 7),
               SourceHealth("d", 0, 7, 7)]
    assert silent_sources(sources) == ["b", "d"]


def test_consecutive_failures():
    assert failing_sources([SourceHealth("a", 2, 0), SourceHealth("b", 3, 0)]) == ["b"]


def test_invalid_offers():
    ok = invalid_offer_reasons("T", "https://x", date(2026, 10, 1), date(2026, 10, 1))
    assert ok == []
    assert invalid_offer_reasons(" ", "", None, None) == ["titre vide", "URL vide"]
    assert invalid_offer_reasons("T", "u", date(2026, 10, 5), date(2026, 10, 1)) == [
        "date limite antérieure à la publication"]
    assert invalid_offer_reasons("T", "u", None, date(2026, 10, 1)) == []
