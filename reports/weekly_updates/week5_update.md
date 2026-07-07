# Week 5 Update

**Period:** June 1–7, 2026

## Completed Work

- **Production default:** Pipeline runs Finviz Elite 20-stock screener without `--demo`.
- **`evaluate_sentiment.py`:** VADER accuracy / macro-F1 on Financial PhraseBank and combined benchmark CSV → `vader_eval_report.csv`.
- **SEC news source:** Added `sec` to `collect_news.py` (filters SEC press release RSS by ticker mention).
- **`store_mongo.py`:** Optional MongoDB storage for `final_dataset`, `sentiment_results`, `raw_stocks`.
- **Dashboard:** Sentiment distribution pie chart; news sorted by `published` / `collected_at`.
- **`run_pipeline.py`:** Flags `--evaluate` and `--mongo` for Week 5 workflow.

## Current Status

Production command:

```bash
python -m src.run_pipeline --evaluate
streamlit run src/dashboard.py
```

Optional MongoDB (local):

```bash
python -m src.run_pipeline --evaluate --mongo
```

## Challenges

- SEC RSS rarely mentions small-cap screener tickers; Google/Yahoo/Finviz remain primary sources.
- VADER is general-purpose; benchmark eval informs whether FinBERT is needed next.
- MongoDB requires local install or Atlas URI.

## Next Steps (Week 6)

- Review `vader_eval_report.csv`; trial FinBERT if accuracy is low on financial text.
- Explore social sources (Stocktwits) per professor roadmap item 5.
- Redis caching for faster refresh (professor note C).
