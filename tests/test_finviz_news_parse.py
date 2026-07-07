"""Tests for live Finviz news HTML parsing."""
from __future__ import annotations

from src.collect_news import parse_finviz_news_html

SAMPLE_HTML = """
<html><body>
<table class="fullview-news-outer">
  <tr><td>Jun-19-26 10:40AM</td><td><a href="/news/123">Apple beats estimates</a></td></tr>
  <tr><td>11:05AM</td><td><a href="https://example.com/a">Analyst upgrade</a></td></tr>
</table>
</body></html>
"""

ID_TABLE_HTML = """
<html><body>
<table id="news-table">
  <tr><td>Jun-18-26 09:00AM</td><td><a href="/news/456">Tesla delivery news</a></td></tr>
</table>
</body></html>
"""


def test_parse_finviz_news_html_fullview_table() -> None:
    df = parse_finviz_news_html(SAMPLE_HTML, "AAPL")
    assert len(df) == 2
    assert df.iloc[0]["title"] == "Apple beats estimates"
    assert df.iloc[1]["published"] == "Jun-19-26 11:05AM"
    assert df.iloc[1]["url"] == "https://example.com/a"


def test_parse_finviz_news_html_id_table() -> None:
    df = parse_finviz_news_html(ID_TABLE_HTML, "TSLA")
    assert len(df) == 1
    assert df.iloc[0]["ticker"] == "TSLA"


def test_parse_finviz_news_html_empty_when_missing_table() -> None:
    df = parse_finviz_news_html("<html><body></body></html>", "X")
    assert df.empty
