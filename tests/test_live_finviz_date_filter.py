"""Tests for live Finviz date-range filtering on scraped news."""
from __future__ import annotations

from datetime import date

import pandas as pd

from src.live_finviz_metrics import (
    build_metrics_from_scored,
    filter_scored_news_by_date,
    resolve_news_window_preset,
)


def test_filter_scored_news_by_date() -> None:
    scored = pd.DataFrame(
        [
            {"ticker": "AAA", "published": "Jun-19-26 10:00AM", "sentiment_compound": 0.1},
            {"ticker": "AAA", "published": "Jan-01-20 10:00AM", "sentiment_compound": -0.2},
        ]
    )
    out = filter_scored_news_by_date(
        scored,
        window_start=date(2026, 6, 1),
        window_end=date(2026, 6, 30),
    )
    assert len(out) == 1
    assert out.iloc[0]["published"].startswith("Jun-19-26")


def test_build_metrics_from_scored_respects_window() -> None:
    scored = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "published": "Jun-19-26 10:00AM",
                "sentiment_compound": 0.5,
                "sentiment_label": "positive",
            },
            {
                "ticker": "AAA",
                "published": "Jan-01-20 10:00AM",
                "sentiment_compound": -0.5,
                "sentiment_label": "negative",
            },
            {
                "ticker": "BBB",
                "published": "Jun-18-26 09:00AM",
                "sentiment_compound": 0.2,
                "sentiment_label": "positive",
            },
        ]
    )
    metrics, filtered = build_metrics_from_scored(
        scored,
        ["AAA", "BBB", "CCC"],
        window_start=date(2026, 6, 1),
        window_end=date(2026, 6, 30),
    )
    aaa = metrics[metrics["ticker"] == "AAA"].iloc[0]
    bbb = metrics[metrics["ticker"] == "BBB"].iloc[0]
    ccc = metrics[metrics["ticker"] == "CCC"].iloc[0]
    assert aaa["news_count"] == 1
    assert bbb["news_count"] == 1
    assert ccc["news_count"] == 0
    assert len(filtered) == 2


def test_resolve_news_window_custom() -> None:
    start, end, label = resolve_news_window_preset(
        "Custom",
        custom_start=date(2026, 5, 1),
        custom_end=date(2026, 6, 1),
    )
    assert start == date(2026, 5, 1)
    assert end == date(2026, 6, 1)
    assert "2026-05-01" in label
