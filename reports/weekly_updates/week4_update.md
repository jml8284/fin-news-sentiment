# Week 4 Update

**Period:** May 25–31, 2026

## Completed Work

- Added `src/merge_data.py` to combine `raw_stock_data.csv` with `ticker_ranking.csv` into `final_dataset.csv`.
- Added `src/run_pipeline.py` for one-command demo or live pipeline execution.
- Upgraded `src/dashboard.py`:
  - Sidebar filters (sector, minimum news count, sort column)
  - Summary metrics (ticker count, average sentiment, total news)
  - Plotly sentiment bar chart
  - Per-ticker news viewer with sentiment labels and links
- Improved `src/clean_data.py` to strip HTML tags from news text.
- Updated README with current pipeline commands and project status.

## Current Status

End-to-end flow (professor-approved):

1. Collect stocks from Finviz (`collect_stocks`)
2. Collect news per ticker (`collect_news --from-stocks`)
3. Clean → VADER sentiment → rank tickers
4. Merge stock + sentiment (`merge_data`)
5. Visualize in Streamlit dashboard

Demo mode is fully reproducible. Live Finviz/news collection works on machines without proxy blocks.

## Challenges

- Network/proxy configuration can block Finviz and RSS requests in some environments.
- VADER is a general-purpose baseline; finance-specific models (e.g. FinBERT) not yet evaluated.

## Next Steps (Week 5)

- Evaluate VADER accuracy on local benchmark datasets (`dataset_loaders.py`).
- Consider FinBERT or other finance-tuned models if baseline accuracy is insufficient.
- Add automated tests for parsing and merge logic.
- Optional: schedule daily collection after market close (8:30 PM ET).
