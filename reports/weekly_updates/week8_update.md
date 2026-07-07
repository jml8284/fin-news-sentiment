# Week 8 Update

**Period:** June 22–28, 2026

## Completed Work

- **Stocktwits live API (`src/collect_stocktwits.py`):** Fetch symbol streams from `api.stocktwits.com` (no key required).
- **Live social metrics (`src/live_stocktwits_metrics.py`):** Parallel fetch for screener tickers; date-range filter; `stocktwits_count` + `social_density`.
- **Dashboard:** New **Stocktwits** tab; ranked table columns `stocktwits_count` / `social_density`; live fetch caption shows Finviz + Stocktwits totals.
- **Date parsing:** ISO-8601 timestamps (Stocktwits `created_at`) in `news_filters.parse_published`.
- **Tests:** `tests/test_stocktwits.py`.

## Commands

```bash
streamlit run src/dashboard.py
python -m pytest tests/test_stocktwits.py -v
```

## Notes

- Stocktwits returns up to ~30 recent messages per ticker per request (public API rate limits).
- Same sidebar date range applies to Finviz news and Stocktwits messages.
- Professor roadmap item 5 — social sourcing.

## Next Steps (Week 9)

- Mockup assignment (FeedFlash secondary layers) if not done.
- Optional Redis cache for Finviz / Stocktwits responses.
- Week 8 activity log docx.
