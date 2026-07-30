"""Unit tests for core pipeline logic (production CSV shapes, no demo)."""
from __future__ import annotations

import pandas as pd
import pytest

from src.clean_data import clean_frame, clean_text
from src.dashboard import build_keyword_signals, build_message_keyword_flags, build_signal_dashboard_table, filter_table
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
    ranked = rank_tickers(df, rolling_window_days=None)
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


def test_keyword_signals_detect_gossip_and_squeeze_terms() -> None:
    scored = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "title": "Rumor of FDA approval and short squeeze",
                "summary": "Traders say low float setup could move soon",
            }
        ]
    )

    signals = build_keyword_signals(scored, ["AAA"])

    row = signals.iloc[0]
    assert row["gossip_hits"] >= 1
    assert row["squeeze_hits"] >= 1
    assert row["catalyst_hits"] >= 1


def test_signal_dashboard_table_adds_ai_reason_and_gossip_flag() -> None:
    filtered = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "company": "Alpha Test",
                "price": 1.25,
                "change_pct": 42.0,
                "volume": 5_000_000,
                "news_count": 4,
                "sentiment_rank": 1,
            }
        ]
    )
    scored = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "title": "Heard buyout rumor as low float squeeze builds",
                "summary": "Possible partnership news",
            }
        ]
    )

    signals = build_signal_dashboard_table(filtered, scored, ["AAA"])

    assert "ai_reason" in signals.columns
    assert "gossip_flag" in signals.columns
    assert signals.iloc[0]["gossip_flag"] == "Possible rumor"
    assert "keyword group" in signals.iloc[0]["ai_reason"]


def test_message_keyword_flags_marks_social_posts() -> None:
    messages = pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "title": "$AAA heard buyout rumor, low float squeeze",
                "summary": "",
                "published": "2026-07-30T10:00:00Z",
                "url": "https://stocktwits.com/symbol/AAA/message/1",
            }
        ]
    )

    flagged = build_message_keyword_flags(messages)

    assert flagged.iloc[0]["keyword_hits"] >= 2
    assert flagged.iloc[0]["gossip_hits"] == 1
    assert flagged.iloc[0]["squeeze_hits"] == 1
