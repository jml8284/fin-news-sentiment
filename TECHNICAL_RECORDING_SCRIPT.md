# Technical Recording Script

## 1. Project Structure

The project is organized into `src`, `data`, `reports`, `scripts`, and `tests`. The main dashboard is `src/dashboard.py`. The collection and processing code is split into separate modules so the dashboard does not contain all business logic.

## 2. Dashboard Entry Point

In `src/dashboard.py`, the `main()` function creates the Streamlit page, loads the Finviz token, builds sidebar filters, and renders four main tabs: Live Finviz chart, Ranked tickers, News viewer, and Social.

## 3. Finviz Pipeline

`src/collect_stocks.py` collects Finviz Elite screener rows. `src/collect_tradingview.py` collects TradingView numeric screener rows through the public scanner endpoint. `src/collect_news.py` collects ticker-related news. `src/live_finviz_metrics.py` scores live Finviz news and builds ticker-level metrics.

## 4. Sentiment

`src/sentiment_engines.py` provides the sentiment engine interface. The dashboard uses VADER for fast live scoring. The pipeline also has evaluation files for comparing models such as FinBERT.

## 5. Ranking

`src/ticker_ranking.py` creates ticker-level ranking fields, including average sentiment, news count, and message density. The dashboard merges these metrics with Finviz screener data and lets the user sort and filter.

## 6. Stocktwits Collection

`src/collect_stocktwits.py` handles Stocktwits data. It includes:

- Stocktwits chart endpoint.
- Stocktwits sentiment/detail endpoint.
- Stocktwits message parsing.
- Curl impersonation fallback.
- WebSocket quote stream.

The chart endpoint gives historical bars. The WebSocket gives current quote checks after the app starts.

## 7. Stocktwits Chart Rendering

`render_stocktwits_style_market_chart()` in `src/dashboard.py` builds the Plotly chart. It draws price, stock volume, message volume, and sentiment in one view. It also shows the latest realtime quote caption and data freshness metrics.

## 8. Alerts

The alert logic is also inside `render_stocktwits_style_market_chart()`. It creates three groups:

- Realtime alerts.
- Chart-window alerts.
- Social latest alerts.

`render_alert_history()` stores triggered alerts in Streamlit session state and adds a CSV download button.

## 9. Correlation

`render_chart_correlation()` compares price change with stock volume, message volume, and sentiment. It is used as a quick analytical signal, not a trading recommendation.

## 10. API

`src/api.py` creates a FastAPI application. It has `/health` and `/stocktwits/{ticker}` endpoints. The API can use an optional token through `FIN_NEWS_API_TOKEN`.

## 11. Deployment

For Railway, the app starts with:

```bash
streamlit run src/dashboard.py --server.address 0.0.0.0 --server.port $PORT
```

The required environment variable is `FINVIZ_API_TOKEN`.

## 12. Testing

The `tests` folder includes tests for Finviz config, chart parsing, live date filters, Stocktwits parsing, social metrics, and sentiment engines. Before submission, I run syntax checks and targeted tests.
