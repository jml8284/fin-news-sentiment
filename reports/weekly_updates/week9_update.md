# Week 9 Update

**Period:** June 29 – July 5, 2026

## Completed Work

- **K-line rolling window (`src/finviz_charts.py`):** `filter_bars_by_date_window()` trims OHLCV bars to the same UTC date range as news/Stocktwits. `window_change_pct()` shows move within the window.
- **Dashboard:** Sidebar **Rolling window** now applies to Finviz news, Stocktwits counts, **and** the live candlestick chart. Chart metrics show bars-in-window and window change %.
- **Chart title:** Displays active window label when a range is selected; **All on page** shows full Finviz export.
- **Tests:** Extended `tests/test_finviz_charts.py` for window filter + window change.

## Commands

```bash
streamlit run src/dashboard.py
python -m pytest tests/test_finviz_charts.py -v
```

## Demo notes

- Default **Last 7 days** zooms daily chart to recent week (matches `news_count` window).
- Intraday intervals (1M, 5M) only show bars whose calendar date falls in range — use **D** for multi-day windows.
- Finviz quote_export still live; rolling window is a client-side filter on fetched bars.

## Next Steps (Week 10+)

- Mockup assignment (FeedFlash secondary pages) if still pending.
- Optional Redis cache for Finviz / Stocktwits.
- Week 9 activity log docx.
