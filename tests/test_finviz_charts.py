"""Tests for Finviz quote_export parsing and chart helpers."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from src.finviz_charts import (
    add_indicators,
    build_finviz_style_chart,
    filter_bars_by_date_window,
    latest_price_info,
    parse_quote_export_csv,
    window_change_pct,
)


SAMPLE_CSV = """Date,Open,High,Low,Close,Volume
06/05/2026 09:30,0.28,0.29,0.28,0.28,1200
06/05/2026 09:31,0.28,0.30,0.28,0.29,2400
06/05/2026 09:32,0.29,0.85,0.29,0.84,900000
06/05/2026 09:33,0.84,0.90,0.53,0.55,500000
"""


def test_parse_quote_export_csv() -> None:
    bars = parse_quote_export_csv(SAMPLE_CSV)
    assert len(bars) == 4
    assert list(bars.columns) == ["datetime", "open", "high", "low", "close", "volume"]
    assert bars.iloc[-1]["close"] == pytest.approx(0.55)


def test_add_indicators_adds_sma_and_vwap() -> None:
    bars = parse_quote_export_csv(SAMPLE_CSV)
    enriched = add_indicators(bars)
    assert "sma_5" in enriched.columns
    assert "vwap" in enriched.columns
    assert enriched["sma_5"].notna().all()


def test_build_finviz_style_chart_respects_selected_sma() -> None:
    bars = parse_quote_export_csv(SAMPLE_CSV)
    fig = build_finviz_style_chart(bars, ticker="SCAG", sma_periods=(5,))
    sma_traces = [t for t in fig.data if t.name == "SMA 5"]
    assert len(sma_traces) == 1
    assert not any(t.name == "SMA 20" for t in fig.data)


def test_build_finviz_style_chart_returns_figure() -> None:
    bars = parse_quote_export_csv(SAMPLE_CSV)
    fig = build_finviz_style_chart(bars, ticker="SCAG", company="Scage Future ADR", change_pct=194.58)
    assert fig.layout.paper_bgcolor == "#1a1a1a"
    assert len(fig.data) >= 3


def test_filter_bars_by_date_window() -> None:
    bars = parse_quote_export_csv(SAMPLE_CSV)
    # All sample bars are on 2026-06-05
    filtered = filter_bars_by_date_window(
        bars,
        window_start=date(2026, 6, 5),
        window_end=date(2026, 6, 5),
    )
    assert len(filtered) == 4

    empty = filter_bars_by_date_window(
        bars,
        window_start=date(2026, 1, 1),
        window_end=date(2026, 1, 2),
    )
    assert empty.empty


def test_window_change_pct() -> None:
    bars = parse_quote_export_csv(SAMPLE_CSV)
    pct = window_change_pct(bars)
    assert pct is not None
    assert pct == pytest.approx((0.55 - 0.28) / 0.28 * 100.0)


def test_build_finviz_style_chart_includes_window_label() -> None:
    bars = parse_quote_export_csv(SAMPLE_CSV)
    fig = build_finviz_style_chart(
        bars,
        ticker="SCAG",
        window_label="2026-06-01 → 2026-06-07",
    )
    assert "2026-06-01" in fig.layout.title.text


def test_latest_price_info_uses_previous_close() -> None:
    bars = parse_quote_export_csv(SAMPLE_CSV)
    info = latest_price_info(bars)
    assert info["price"] == pytest.approx(0.55)
    assert info["change_pct"] == pytest.approx((0.55 - 0.84) / 0.84 * 100.0)
