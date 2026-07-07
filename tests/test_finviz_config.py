"""Finviz Elite URL builders match professor API workflow."""
from __future__ import annotations

from src.finviz_config import (
    PRESET_TECHNICAL_GAINERS,
    build_elite_export_url,
    build_elite_stock_url,
    build_quote_export_url,
)


def test_preset_matches_jun10_canvas_announcement() -> None:
    assert PRESET_TECHNICAL_GAINERS["view"] == 151
    assert "sh_relvol_o0.75" in PRESET_TECHNICAL_GAINERS["filters"]
    assert "sh_curvol_o100" in PRESET_TECHNICAL_GAINERS["filters"]
    assert PRESET_TECHNICAL_GAINERS["order"] == "-change"


def test_build_quote_export_url_includes_auth() -> None:
    url = build_quote_export_url("SCAG", "test-token", period="i1")
    assert "quote_export" in url
    assert "t=SCAG" in url
    assert "p=i1" in url
    assert "auth=test-token" in url


def test_build_elite_stock_url_professor_pattern() -> None:
    url = build_elite_stock_url("SCAG", "test-token", period="i1")
    assert "stock?t=SCAG" in url
    assert "ty=c" in url
    assert "p=i1" in url
    assert "auth=test-token" in url


def test_build_elite_export_url_includes_columns() -> None:
    url = build_elite_export_url(
        auth_token="tok",
        filters=PRESET_TECHNICAL_GAINERS["filters"],
        view=151,
        columns=PRESET_TECHNICAL_GAINERS["columns"],
        after_row=10,
    )
    assert "v=151" in url
    assert "sh_relvol_o0.75" in url
    assert "c=0%2C1%2C2" in url or "c=0,1,2" in url
    assert "auth=tok" in url
