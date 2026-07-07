"""Tests for Stocktwits fetch and live metrics."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd

from src.collect_stocktwits import (
    fetch_stocktwits_messages,
    fetch_stocktwits_messages_with_error,
    parse_stocktwits_symbol_html,
)
from src.live_stocktwits_metrics import build_stocktwits_metrics, filter_stocktwits_by_date


SAMPLE_PAYLOAD = {
    "messages": [
        {
            "id": 1,
            "body": "Bullish on AAPL",
            "created_at": "2026-06-18T10:00:00Z",
            "entities": {"sentiment": {"basic": "Bullish"}},
        },
        {
            "id": 2,
            "body": "Old post",
            "created_at": "2026-01-01T10:00:00Z",
            "entities": {},
        },
    ]
}


def test_fetch_stocktwits_messages_parses_json() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"messages": [{"id": 1, "body": "Bullish on AAPL", "created_at": "2026-06-18T10:00:00Z", "entities": {"sentiment": {"basic": "Bullish"}}}, {"id": 2, "body": "Old post", "created_at": "2026-01-01T10:00:00Z", "entities": {}}]}'
    mock_resp.headers = {"Content-Type": "application/json"}

    with patch("src.collect_stocktwits._use_web_only", return_value=False):
        with patch("src.collect_stocktwits._fetch_url", return_value=(200, mock_resp.text, "application/json")):
            with patch("src.collect_stocktwits._allow_sample", return_value=False):
                df = fetch_stocktwits_messages("AAPL", max_items=10)

    assert len(df) == 2
    assert df.iloc[0]["ticker"] == "AAPL"
    assert df.iloc[0]["stocktwits_sentiment"] == "Bullish"
    assert df.iloc[0]["source"] == "Stocktwits"


def test_fetch_stocktwits_html_block() -> None:
    html = "<!DOCTYPE html><html><body>blocked</body></html>"
    with patch("src.collect_stocktwits._use_web_only", return_value=False):
        with patch("src.collect_stocktwits._fetch_url", return_value=(200, html, "text/html")):
            with patch("src.collect_stocktwits._fetch_via_web", return_value=(pd.DataFrame(), "blocked")):
                with patch("src.collect_stocktwits._allow_sample", return_value=False):
                    df, err = fetch_stocktwits_messages_with_error("AAPL")
    assert df.empty
    assert err is not None
    assert "HTML" in err or "API blocked" in err


def test_fetch_stocktwits_403() -> None:
    with patch("src.collect_stocktwits._use_web_only", return_value=False):
        with patch("src.collect_stocktwits._fetch_url", return_value=(403, "Forbidden", "text/html")):
            with patch("src.collect_stocktwits._fetch_via_web", return_value=(pd.DataFrame(), "blocked")):
                with patch("src.collect_stocktwits._allow_sample", return_value=False):
                    df, err = fetch_stocktwits_messages_with_error("AAPL")
    assert df.empty
    assert err is not None
    assert "403" in err or "API blocked" in err


def test_fetch_stocktwits_api_403_web_fallback() -> None:
    sample_html = """
    <div data-testid="message-12345">
      <time datetime="2026-06-30T08:54:57Z"></time>
      <div class="RichTextMessage_body__x">Bullish on $AAPL today</div>
      <button data-testid="bullish-button" aria-pressed="true"></button>
    </div>
    """
    with patch("src.collect_stocktwits._use_web_only", return_value=False):
        with patch("src.collect_stocktwits._fetch_url", return_value=(403, "Forbidden", "text/html")):
            with patch("src.collect_stocktwits._web_fallback_enabled", return_value=True):
                with patch("src.collect_stocktwits._fetch_symbol_page_html", return_value=sample_html):
                    with patch("src.collect_stocktwits._allow_sample", return_value=False):
                        df, err = fetch_stocktwits_messages_with_error("AAPL")
    assert err is None
    assert len(df) == 1
    assert df.iloc[0]["stocktwits_sentiment"] == "Bullish"
    assert df.iloc[0]["source"] == "Stocktwits (web)"


def test_fetch_stocktwits_sample_fallback() -> None:
    with patch("src.collect_stocktwits._use_web_only", return_value=False):
        with patch("src.collect_stocktwits._fetch_url", return_value=(403, "Forbidden", "text/html")):
            with patch("src.collect_stocktwits._fetch_via_web", return_value=(pd.DataFrame(), "web blocked")):
                df, err = fetch_stocktwits_messages_with_error("AAPL")
    assert err is None
    assert len(df) >= 1
    assert df.iloc[0]["source"] == "Stocktwits (sample)"


def test_parse_stocktwits_symbol_html() -> None:
    html = """
    <div data-testid="message-999">
      <time datetime="2026-06-18T10:00:00Z"></time>
      <div class="RichTextMessage_body__abc">Hello $AAPL</div>
    </div>
    """
    df = parse_stocktwits_symbol_html(html, "AAPL", max_items=10)
    assert len(df) == 1
    assert df.iloc[0]["published"] == "2026-06-18T10:00:00Z"
    assert "Hello" in df.iloc[0]["title"]


def test_filter_stocktwits_by_date() -> None:
    messages = pd.DataFrame(
        [
            {"ticker": "AAPL", "published": "2026-06-18T10:00:00Z"},
            {"ticker": "AAPL", "published": "2026-01-01T10:00:00Z"},
        ]
    )
    out = filter_stocktwits_by_date(
        messages,
        window_start=date(2026, 6, 1),
        window_end=date(2026, 6, 30),
    )
    assert len(out) == 1


def test_build_stocktwits_metrics_empty_input() -> None:
    metrics, filtered = build_stocktwits_metrics(
        pd.DataFrame(),
        ["AAA", "BBB"],
        window_start=date(2026, 6, 1),
        window_end=date(2026, 6, 30),
    )
    assert len(metrics) == 2
    assert metrics.iloc[0]["stocktwits_count"] == 0
    assert filtered.empty
    assert list(filtered.columns) == [
        "ticker",
        "title",
        "summary",
        "published",
        "collected_at",
        "source",
        "url",
        "stocktwits_sentiment",
    ]


def test_build_stocktwits_metrics() -> None:
    messages = pd.DataFrame(
        [
            {"ticker": "AAA", "published": "2026-06-18T10:00:00Z"},
            {"ticker": "AAA", "published": "2026-06-19T10:00:00Z"},
            {"ticker": "BBB", "published": "2026-06-18T10:00:00Z"},
        ]
    )
    metrics, filtered = build_stocktwits_metrics(
        messages,
        ["AAA", "BBB", "CCC"],
        window_start=date(2026, 6, 1),
        window_end=date(2026, 6, 30),
    )
    aaa = metrics[metrics["ticker"] == "AAA"].iloc[0]
    ccc = metrics[metrics["ticker"] == "CCC"].iloc[0]
    assert aaa["stocktwits_count"] == 2
    assert aaa["social_density"] == "medium"
    assert ccc["stocktwits_count"] == 0
    assert len(filtered) == 3
