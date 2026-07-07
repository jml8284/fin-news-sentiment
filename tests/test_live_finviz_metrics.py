"""Tests for live Finviz quote-page metrics."""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from src.live_finviz_metrics import build_live_finviz_metrics


def test_build_live_finviz_metrics_counts_and_ranks() -> None:
    def fake_fetch(ticker: str, **kwargs) -> pd.DataFrame:  # noqa: ANN003
        if ticker == "AAA":
            return pd.DataFrame(
                [
                    {"ticker": "AAA", "title": "Great earnings beat", "summary": "", "published": "Jun-19-26", "source": "Finviz Elite", "url": "http://a"},
                    {"ticker": "AAA", "title": "Analyst upgrade", "summary": "", "published": "Jun-18-26", "source": "Finviz Elite", "url": "http://b"},
                ]
            )
        return pd.DataFrame()

    with patch("src.live_finviz_metrics.fetch_finviz_news", side_effect=fake_fetch):
        metrics, scored, errors = build_live_finviz_metrics(["AAA", "BBB"], "token", engine="vader")

    assert errors == []
    aaa = metrics[metrics["ticker"] == "AAA"].iloc[0]
    bbb = metrics[metrics["ticker"] == "BBB"].iloc[0]
    assert aaa["news_count"] == 2
    assert aaa["message_density"] == "medium"
    assert bbb["news_count"] == 0
    assert bbb["message_density"] == "low"
    assert len(scored) == 2
    assert "sentiment_rank" in metrics.columns
