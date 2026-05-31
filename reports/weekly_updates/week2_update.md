# Week 2 Update

## Completed Work

- Implemented `src/collect_stocks.py` to scrape Finviz screener data (ticker, company, sector, price, change %, volume, market cap, P/E).
- Added CLI filters for exchange, index, sector, signal presets (e.g. most active, top gainers), and sort order.
- Added `cloudscraper` fallback when standard HTTP requests are blocked.
- Created `data/raw/demo_mock_stocks.csv` for offline testing.
- Verified demo output writes to `data/raw/raw_stock_data.csv`.

## Challenges

- Finviz may block automated requests depending on network/proxy settings.
- Some highly active tickers are low-liquidity penny stocks with limited news coverage.

## Next Steps

- Collect news per ticker from Google News, Yahoo Finance, and Finviz.
- Merge stock metrics with sentiment results for the dashboard.
