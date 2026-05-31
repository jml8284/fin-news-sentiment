# Week 3 Update

## Completed Work

- Extended `src/collect_news.py` to read tickers from `raw_stock_data.csv` and collect news per ticker.
- Added three news sources: Google News RSS, Yahoo Finance RSS, and Finviz quote-page news.
- Implemented deduplication by ticker + URL + title and logging for tickers with no news.
- Confirmed the existing pipeline still works: clean → VADER sentiment → ticker ranking.

## Challenges

- RSS feeds can return empty results for obscure tickers or when network/proxy issues occur.
- Finviz news parsing depends on page HTML structure and may need maintenance.

## Next Steps

- Merge stock and sentiment datasets into a single dashboard-ready file.
- Upgrade Streamlit UI with filters, charts, and a per-ticker news viewer.
