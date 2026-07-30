from src.collect_tradingview import build_tradingview_payload, normalize_tradingview_rows


def test_tradingview_payload_has_expected_scanner_fields():
    payload = build_tradingview_payload(top_n=7, min_volume=250000, sort_by="change")

    assert payload["range"] == [0, 7]
    assert payload["sort"] == {"sortBy": "change", "sortOrder": "desc"}
    assert {"left": "volume", "operation": "greater", "right": 250000} in payload["filter"]
    assert "market_cap_basic" in payload["columns"]
    assert "premarket_change" in payload["columns"]
    assert "postmarket_change" in payload["columns"]


def test_tradingview_rows_normalize_to_dashboard_columns():
    raw = {
        "data": [
            {
                "s": "NASDAQ:NVDA",
                "d": [
                    "NVDA",
                    "NVIDIA Corporation",
                    150.25,
                    2.5,
                    1200000,
                    3_000_000_000_000,
                    1.1,
                    -0.4,
                    1.8,
                    "Electronic Technology",
                    "Semiconductors",
                    "NASDAQ",
                ],
            }
        ]
    }

    frame = normalize_tradingview_rows(raw)

    assert len(frame) == 1
    row = frame.iloc[0]
    assert row["ticker"] == "NVDA"
    assert row["source"] == "TradingView"
    assert row["price"] == 150.25
    assert row["change_pct"] == 2.5
    assert row["source_url"] == "https://www.tradingview.com/symbols/NASDAQ-NVDA/"
