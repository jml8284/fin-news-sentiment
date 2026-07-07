"""Unit tests for core pipeline logic (production CSV shapes, no demo)."""
from __future__ import annotations

import pandas as pd
import pytest

from src.clean_data import clean_frame, clean_text
from src.dashboard import filter_table
from src.merge_data import merge_stock_and_sentiment
from src.ticker_ranking import density_bucket, rank_tickers


def test_clean_text_strips_html_and_whitespace() -> None:
    assert clean_text("  <b>Hello</b>   world  ") == "Hello world"


def test_clean_frame_deduplicates_by_url_and_title() -> None:
    df = pd.DataFrame(
        [
            {"title": "A", "url": "http://x/a", "summary": "s1", "ticker": "AAA"},
            {"title": "A", "url": "http://x/a", "summary": "dup", "ticker": "AAA"},
            {"title": "", "url": "http://x/b", "summary": "empty title", "ticker": "BBB"},
        ]
    )
    cleaned = clean_frame(df)
    assert len(cleaned) == 1
    assert cleaned.iloc[0]["title"] == "A"


def test_density_bucket_thresholds() -> None:
    assert density_bucket(1) == "low"
    assert density_bucket(2) == "medium"
    assert density_bucket(4) == "high"


def test_rank_tickers_uses_finviz_news_only() -> None:
    df = pd.DataFrame(
        [
            {
                "ticker": "SCAG",
                "sentiment_compound": 0.5,
                "sentiment_label": "positive",
                "source": "Google News",
                "title": "12 Industrials Stocks Moving",
                "summary": "",
                "published": "Sun, 14 Jun 2026 21:00:00 GMT",
            },
            {
                "ticker": "AAA",
                "sentiment_compound": 0.3,
                "sentiment_label": "positive",
                "source": "Finviz Elite",
                "title": "AAA beats earnings",
                "summary": "",
                "published": "Sun, 14 Jun 2026 21:00:00 GMT",
            },
        ]
    )
    ranked = rank_tickers(df)
    scag = ranked[ranked["ticker"] == "SCAG"].iloc[0]
    aaa = ranked[ranked["ticker"] == "AAA"].iloc[0]
    assert scag["news_count"] == 0
    assert scag["rolling_news_count"] == 0
    assert aaa["news_count"] == 1
    assert aaa["avg_sentiment"] == pytest.approx(0.3)


def test_rank_tickers_rolling_window_excludes_old_news() -> None:
    from datetime import date

    df = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "sentiment_compound": 0.9,
                "sentiment_label": "positive",
                "source": "Finviz Elite",
                "title": "AAA recent",
                "summary": "",
                "published": "Sun, 14 Jun 2026 12:00:00 GMT",
            },
            {
                "ticker": "AAA",
                "sentiment_compound": -0.9,
                "sentiment_label": "negative",
                "source": "Finviz Elite",
                "title": "AAA old",
                "summary": "",
                "published": "Sun, 01 Jan 2020 12:00:00 GMT",
            },
        ]
    )
    ranked = rank_tickers(
        df,
        rolling_window_days=None,
        window_start=date(2026, 6, 8),
        window_end=date(2026, 6, 14),
    )
    row = ranked[ranked["ticker"] == "AAA"].iloc[0]
    assert row["news_count"] == 2
    assert row["rolling_news_count"] == 1
    assert row["avg_sentiment"] == pytest.approx(0.9)
    assert row["message_density"] == "low"


def test_merge_stock_and_sentiment_joins_on_ticker() -> None:
    stocks = pd.DataFrame(
        [
            {
                "ticker": "aaa",
                "company": "Co A",
                "sector": "Tech",
                "price": 10.0,
                "change_pct": 5.0,
                "volume": 1000,
                "market_cap": 1.0,
                "pe": 12.0,
            }
        ]
    )
    ranking = pd.DataFrame(
        [
            {
                "rank": 1,
                "ticker": "AAA",
                "avg_sentiment": 0.42,
                "news_count": 3,
                "positive_ratio": 0.6,
                "negative_ratio": 0.1,
                "message_density": "medium",
            }
        ]
    )
    merged = merge_stock_and_sentiment(stocks, ranking)
    assert len(merged) == 1
    assert merged.iloc[0]["ticker"] == "AAA"
    assert merged.iloc[0]["avg_sentiment"] == 0.42
    assert merged.iloc[0]["change_pct"] == 5.0


def test_filter_table_sector_and_min_news() -> None:
    df = pd.DataFrame(
        [
            {"ticker": "A", "sector": "Tech", "news_count": 5},
            {"ticker": "B", "sector": "Health", "news_count": 1},
        ]
    )
    out = filter_table(df, sector="Tech", min_news=3)
    assert len(out) == 1
    assert out.iloc[0]["ticker"] == "A"
