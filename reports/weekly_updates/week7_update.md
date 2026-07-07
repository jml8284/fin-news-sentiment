# Week 7 Update

**Period:** June 15–21, 2026

## Completed Work

- **FinBERT integration (`src/sentiment_engines.py`):** Pluggable sentiment engines — `vader` (default) and `finbert` (`ProsusAI/finbert`).
- **`sentiment_analysis.py`:** New `--engine vader|finbert` flag; writes `data/processed/sentiment_engine.txt` metadata.
- **`evaluate_sentiment.py`:** Compare models on PhraseBank + combined CSV; output `sentiment_eval_report.csv` (keeps legacy `vader_eval_report.csv`).
- **`run_pipeline.py`:** `--finbert` uses FinBERT for scoring; `--evaluate` can run `--evaluate-models all`.
- **Dashboard Week 6 fix:** Live chart fragment now re-fetches screener each refresh so **change %** stays in sync with 60s auto-refresh (was stale outside fragment).
- **Dashboard:** Caption and column tooltips show active sentiment engine (VADER vs FINBERT).
- **Tests:** Added `tests/test_sentiment_engines.py` (27 total passing).

## Commands

```bash
# Default pipeline (VADER, fast)
python -m src.run_pipeline

# FinBERT scoring + benchmark both models
python -m src.run_pipeline --finbert --evaluate

# Evaluate only
python -m src.evaluate_sentiment --models vader,finbert

streamlit run src/dashboard.py
python -m pytest tests/ -v
```

## Notes

- FinBERT first run downloads ~440MB model weights; needs `pip install transformers torch`.
- Production demos can stay on VADER for speed; use FinBERT when comparing accuracy for professor.
- Ranked table screener still refreshes on page load / manual Refresh; chart tab is the 60s live path.

## Next Steps (Week 8)

- Stocktwits data source prototype (professor roadmap).
- Optional Redis cache for screener/chart API responses.
- Mockup assignment (FeedFlash-style secondary layers).
- Week 7 activity log docx.
