from __future__ import annotations

from src.collect_news import AVAILABLE_SOURCES, RSS_SOURCE_FEEDS, _mentions_ticker


def test_professor_public_news_sources_are_registered() -> None:
    assert "globalwire" in AVAILABLE_SOURCES
    assert "prnewswire" in AVAILABLE_SOURCES
    assert "sec" in AVAILABLE_SOURCES
    assert "fda" in AVAILABLE_SOURCES
    assert RSS_SOURCE_FEEDS["globalwire"][0] == "GlobeNewswire"


def test_ticker_matching_avoids_loose_substrings() -> None:
    assert _mentions_ticker("$ZCMD moves higher", "", "ZCMD")
    assert _mentions_ticker("ZCMD files update", "", "ZCMD")
    assert not _mentions_ticker("A to Z command center opens", "", "ZCMD")
