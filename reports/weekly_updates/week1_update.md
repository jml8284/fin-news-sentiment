# Week 1 Update

## Completed Work

- Created the GitHub repository for the project.
- Selected the project topic: Financial News Sentiment Analysis Dashboard.
- Wrote the initial README with project goals, planned structure, workflow, and tools.
- Implemented the first version of the project folder structure and Python module stubs.
- Added `requirements.txt` and a small `demo_mock_news.csv` to test the pipeline end-to-end.
- Planned the main pipeline: news collection, data cleaning, sentiment analysis, ticker ranking, and dashboard.

## Current Thinking

The project will start with a simple baseline sentiment approach (e.g. VADER). After the baseline works, a finance-specific model such as FinBERT may be tested. The dashboard will be built with Streamlit and will show ranked tickers, sentiment scores, news density, and recent articles.

## Challenges / Questions

- Confirm whether RSS feeds are acceptable as the first data source.
- Decide whether ticker identification should start with simple keyword/ticker matching or a more advanced NER approach.
- Confirm whether the first milestone should prioritize a working pipeline or model complexity.

## Next Steps

- Expand `collect_news.py` with one or two stable RSS sources (after approval).
- Harden data cleaning and ticker extraction rules.
- Add basic tests or notebook checks for reproducibility.
- Run baseline sentiment on a larger sample and tune dashboard filters.
