"""Tests for Finviz-aligned news quality filters."""
from __future__ import annotations

from src.news_filters import (
    in_date_range,
    is_finviz_source,
    is_quality_supplemental,
    mentions_ticker,
    parse_published,
)


def test_is_finviz_source() -> None:
    assert is_finviz_source("Finviz Elite")
    assert not is_finviz_source("Google News")


def test_roundup_excluded() -> None:
    assert not is_quality_supplemental(
        "12 Industrials Stocks Moving In Friday's After-Market Session",
        "Benzinga roundup",
        "SCAG",
        company="Scage Future ADR",
        published="Sun, 14 Jun 2026 21:06:10 GMT",
    )


def test_ticker_specific_recent_kept() -> None:
    assert is_quality_supplemental(
        "Scage Future Plummets 23.36% Post-Market",
        "SCAG dropped after hours",
        "SCAG",
        company="Scage Future ADR",
        published="Sun, 14 Jun 2026 20:38:54 GMT",
        max_age_days=60,
    )


def test_mentions_ticker_requires_symbol_or_company() -> None:
    assert mentions_ticker("SCAG surges", "", "SCAG")
    assert mentions_ticker("Scage Future update", "", "SCAG", company="Scage Future ADR")
    assert not mentions_ticker("Market wrap", "Stocks moved", "SCAG")


def test_parse_finviz_published_format() -> None:
    dt = parse_published("Feb-24-26 10:40AM")
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 2
    assert dt.day == 24
    assert dt.hour == 10


def test_in_date_range_inclusive() -> None:
    from datetime import date

    assert in_date_range(
        "Sun, 14 Jun 2026 12:00:00 GMT",
        start=date(2026, 6, 14),
        end=date(2026, 6, 14),
    )
    assert not in_date_range(
        "Sun, 01 Jan 2020 12:00:00 GMT",
        start=date(2026, 6, 8),
        end=date(2026, 6, 14),
    )
