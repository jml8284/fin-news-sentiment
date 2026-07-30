"""Tests for non-Stocktwits social sourcing."""
from __future__ import annotations

from datetime import date
import json
from unittest.mock import patch

import pandas as pd

from src.collect_social import fetch_bluesky_social_posts, fetch_social_posts_with_error
from src.live_social_metrics import build_social_metrics, filter_social_by_date


def test_fetch_social_posts_parses_reddit_json() -> None:
    payload = json.dumps(
        {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "abc",
                            "title": "$AAPL bullish breakout",
                            "selftext": "calls and upside",
                            "created_utc": 1782928800,
                            "permalink": "/r/stocks/comments/abc/aapl/",
                        }
                    }
                ]
            }
        }
    )
    with patch("src.collect_social._subreddits", return_value=["stocks"]):
        with patch("src.collect_social._fetch_url", return_value=(200, payload, "application/json")):
            with patch("src.collect_social._allow_sample", return_value=False):
                with patch("src.collect_social._social_source", return_value="reddit"):
                    df, err = fetch_social_posts_with_error("AAPL")

    assert err is None
    assert len(df) == 1
    assert df.iloc[0]["ticker"] == "AAPL"
    assert df.iloc[0]["source"] == "Reddit r/stocks"
    assert df.iloc[0]["social_sentiment"] == "Bullish"


def test_fetch_bluesky_social_posts_parses_search_json() -> None:
    payload = {
        "posts": [
            {
                "uri": "at://did:plc:abc/app.bsky.feed.post/123",
                "author": {"handle": "finance.example"},
                "record": {
                    "text": "$AAPL bullish breakout watch",
                    "createdAt": "2026-07-06T05:36:12.703637+00:00",
                },
            }
        ]
    }
    with patch("src.collect_social._fetch_bluesky_json", return_value=(200, payload, "")):
        df, err = fetch_bluesky_social_posts("AAPL")

    assert err is None
    assert len(df) == 1
    assert df.iloc[0]["source"] == "Bluesky"
    assert df.iloc[0]["social_sentiment"] == "Bullish"


def test_fetch_social_posts_parses_stocktwits_messages() -> None:
    payload = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "title": "$AAPL live Stocktwits post",
                "summary": "",
                "published": "2026-07-10T12:00:00Z",
                "collected_at": "2026-07-10 12:00:01 UTC",
                "source": "Stocktwits",
                "url": "https://stocktwits.com/symbol/AAPL/message/1",
                "stocktwits_sentiment": "Bullish",
            }
        ]
    )
    with patch("src.collect_social._social_source", return_value="stocktwits"):
        with patch("src.collect_stocktwits.fetch_stocktwits_messages_with_error", return_value=(payload, None)):
            df, err = fetch_social_posts_with_error("AAPL")

    assert err is None
    assert len(df) == 1
    assert df.iloc[0]["source"] == "Stocktwits"
    assert df.iloc[0]["social_sentiment"] == "Bullish"


def test_fetch_social_posts_sample_fallback() -> None:
    with patch("src.collect_social._subreddits", return_value=["stocks"]):
        with patch("src.collect_social._fetch_url", return_value=(403, "Forbidden", "text/html")):
            with patch("src.collect_social._allow_sample", return_value=True):
                with patch("src.collect_social._social_source", return_value="reddit"):
                    df, err = fetch_social_posts_with_error("AAPL")

    assert err is None
    assert len(df) >= 1
    assert "sample" in df.iloc[0]["source"].lower()


def test_filter_social_by_date() -> None:
    messages = pd.DataFrame(
        [
            {"ticker": "AAPL", "published": "2026-06-18T10:00:00Z"},
            {"ticker": "AAPL", "published": "2026-01-01T10:00:00Z"},
        ]
    )
    out = filter_social_by_date(
        messages,
        window_start=date(2026, 6, 1),
        window_end=date(2026, 6, 30),
    )
    assert len(out) == 1


def test_build_social_metrics() -> None:
    messages = pd.DataFrame(
        [
            {"ticker": "AAA", "published": "2026-06-18T10:00:00Z"},
            {"ticker": "AAA", "published": "2026-06-19T10:00:00Z"},
            {"ticker": "BBB", "published": "2026-06-18T10:00:00Z"},
        ]
    )
    metrics, filtered = build_social_metrics(
        messages,
        ["AAA", "BBB", "CCC"],
        window_start=date(2026, 6, 1),
        window_end=date(2026, 6, 30),
    )
    aaa = metrics[metrics["ticker"] == "AAA"].iloc[0]
    ccc = metrics[metrics["ticker"] == "CCC"].iloc[0]
    assert aaa["social_count"] == 2
    assert aaa["social_density"] == "medium"
    assert ccc["social_count"] == 0
    assert len(filtered) == 3
