# Financial News Sentiment Analysis Dashboard

IST 495 Summer 2026 internship project by Jinyang Liu.

This project is a Python dashboard for fast financial news, stock screener, sentiment, and Stocktwits social activity monitoring. It combines live Finviz data, news sentiment scoring, Stocktwits chart/social indicators, realtime quote checks, correlation checks, and alert logic in one Streamlit application.

## Current Status

The project is ready for final internship demonstration and delivery preparation.

Implemented:

- Live Finviz Elite screener for ranked stock candidates.
- TradingView numeric screener collector for a second market-data view of price, volume, market cap, pre-market, and post-market change fields.
- Live Finviz news collection and VADER sentiment scoring.
- Public RSS/newswire collection for GlobeNewswire, PR Newswire, SEC, FDA, and custom RSS feeds.
- Ranked ticker table with sorting, thresholding, sentiment rank, news count, and message density.
- Signals tab with dictionary keyword screening, numeric score, AI-style combined ranking, short-squeeze proxy score, and long-term watchlist hints.
- Professor checklist coverage tab that separates completed features, prototype features, and future infrastructure work.
- Configurable alert thresholds for realtime price movement, chart-window price movement, volume spikes, and social sentiment/message-volume scores.
- Current ticker report export for demo notes and handoff documentation.
- Finviz-style price chart with optional SMA overlays.
- Stocktwits social tab with Stocktwits chart data, parsed message rows when available, and sentiment/message-volume visualization.
- Stocktwits WebSocket quote check during dashboard refresh.
- One-minute dashboard refresh cycle for current-session realtime quote updates.
- Data freshness panel showing chart latest time, WebSocket check time, live quote latest time, and social latest time.
- Alerts for realtime price movement, chart-window price/volume movement, and latest social sentiment/message-volume signals.
- Alert history and CSV export.
- Correlation analysis between price movement, stock volume, message volume, and sentiment.
- FastAPI wrapper for Stocktwits chart, sentiment, and realtime quote snapshots.
- API endpoints for feature coverage, alert rules, and per-ticker demo reports.
- MongoDB storage module for optional resting database work.
- Local tests for parser, sentiment, Finviz, and Stocktwits helper logic.
- Railway deployment files, final demo script, technical recording script, delivery guide, and AI prompt log.

## Important Realtime Note

Stocktwits returns historical chart bars at its own interval. For example, older 1D or 1W chart bars may be 5-minute, 10-minute, or 30-minute bars depending on the symbol, market session, and what Stocktwits returns.

The dashboard adds a realtime layer after the app starts:

- The Stocktwits chart endpoint provides the historical chart window.
- The Stocktwits WebSocket provides the latest quote check.
- Streamlit refreshes every 60 seconds when auto-refresh is enabled.
- New quotes collected after the program starts can be appended to the visible chart.

This means the app can monitor realtime movement while running, but it cannot reconstruct one-minute historical Stocktwits data from before the app was started if Stocktwits only returned 5-minute or 10-minute historical bars.

## Project Structure

```text
fin-news-sentiment/
  README.md
  requirements.txt
  .env.example
  src/
    dashboard.py              # Streamlit dashboard
    api.py                    # Optional FastAPI endpoint
    collect_stocks.py         # Finviz screener collection
    collect_news.py           # News collection
    collect_stocktwits.py     # Stocktwits chart, sentiment, websocket, messages
    sentiment_analysis.py     # Sentiment pipeline
    sentiment_engines.py      # VADER / FinBERT helper layer
    ticker_ranking.py         # Ticker ranking logic
    merge_data.py             # Merge screener + sentiment outputs
    run_pipeline.py           # Pipeline runner
    store_mongo.py            # Optional MongoDB storage
  data/
    raw/
    processed/
    datasets/
    samples/
  scripts/
  tests/
```

## Setup

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copy the environment template:

```bash
copy .env.example .env
```

Add your Finviz Elite token:

```bash
FINVIZ_API_TOKEN=your-token-here
```

Optional API token for the FastAPI wrapper:

```bash
FIN_NEWS_API_TOKEN=your-local-api-token
```

## Run The Dashboard

```bash
streamlit run src/dashboard.py
```

Local URL:

```text
http://localhost:8501
```

Useful Windows command:

```bash
.venv\Scripts\python.exe -m streamlit run src\dashboard.py --server.port 8501 --server.address localhost
```

## Run The Pipeline

```bash
python -m src.run_pipeline --evaluate
```

Collect only live news rows:

```bash
python -m src.collect_news --from-stocks --sources finviz,google,yahoo,globalwire,prnewswire,sec,fda --top-n 20
```

Collect TradingView numeric screener rows:

```bash
python -m src.collect_tradingview --top-n 20 --min-volume 100000 --out data/raw/tradingview_screener.csv
```

Add a custom RSS feed:

```bash
python -m src.collect_news --rss https://example.com/feed.xml --out data/raw/custom_rss_news.csv
```

Optional MongoDB storage:

```bash
python -m src.run_pipeline --evaluate --mongo
```

## Optional API

Start the API:

```bash
uvicorn src.api:app --host 127.0.0.1 --port 8000
```

Health check:

```text
GET /health
```

Stocktwits snapshot:

```text
GET /stocktwits/{ticker}?zoom=1d&include_realtime=true
```

Professor checklist coverage:

```text
GET /features
```

TradingView screener:

```text
GET /tradingview/screener?top_n=20&min_volume=100000&sort_by=change
```

Alert rule documentation:

```text
GET /alerts/rules
```

Compact ticker demo report:

```text
GET /stocktwits/{ticker}/demo-report?zoom=1d
```

If `FIN_NEWS_API_TOKEN` is set, send it as:

```text
X-API-Token: your-local-api-token
```

## Dashboard Walkthrough

### Finviz Filters

The sidebar controls the Finviz news date range, sector filter, minimum news count, sort field, and sort order.

### Live Finviz Chart

The Finviz chart tab displays price bars and SMA overlays for the selected ticker. The optional K-line rolling window can zoom the Finviz chart without changing the Stocktwits social tab.

### Ranked Tickers

The ranked table combines live screener data with news sentiment, news count, and message density. It supports sorting, thresholding, and CSV export.

### News Viewer

The news viewer shows collected news rows with ticker, title, summary, source, published time, URL, and sentiment fields.

### Social / Stocktwits

The Social tab includes:

- Stocktwits chart range selector: 1D, 1W, 1M, 3M, 6M, YTD, 1Y, 5Y, All.
- Stocktwits price line.
- Stock volume bars.
- Sentiment line when returned by Stocktwits.
- Message volume line when returned by Stocktwits.
- Realtime quote extension from the WebSocket after the program starts.
- Parsed Stocktwits message rows when Stocktwits web data is available.
- Per-ticker social counts.
- Correlation analysis.
- Data freshness panel.
- Alerts and alert history export.

## Alerts

The alert section is a prototype signal layer.

Current alert types:

- Realtime Alert: checks price movement using quotes collected after the app starts.
- Chart Window Alert: checks recent chart-window price movement and volume spikes.
- Social Latest Alert: checks latest Stocktwits sentiment and message-volume scores.

Alerts are displayed in the dashboard and stored in session memory. The user can export alert history as CSV.

## Final Delivery Files

The repo includes delivery-focused files for the final internship submission:

- `DEMO_SCRIPT.md`: non-technical demo recording outline.
- `TECHNICAL_RECORDING_SCRIPT.md`: code walkthrough outline.
- `DELIVERY_GUIDE.md`: final submission checklist and Railway notes.
- `AI_PROMPT_LOG.md`: short AI-use log for the professor.
- `Procfile` and `railway.toml`: Railway deployment entrypoint.

Recommended final demo order:

1. Open the Railway URL or local Streamlit URL.
2. Show Finviz filters and ranked tickers.
3. Show News viewer and sentiment fields.
4. Show Signals for keyword, numeric, AI-style, squeeze, and long-term scoring.
5. Show Social tab with Stocktwits chart, sentiment, message volume, and data freshness.
6. Show Alerts and export options.
7. Show Checklist tab and explain Done / Prototype / Future work honestly.

## Data Sources

Primary sources:

- Finviz Elite screener and quote/news data.
- TradingView public scanner data for numeric screener comparison.
- GlobeNewswire public RSS feed.
- PR Newswire public RSS feed.
- SEC press release RSS feed.
- FDA press release RSS feed.
- Custom RSS feeds passed from the command line.
- Stocktwits chart endpoint.
- Stocktwits sentiment/detail endpoint when accessible.
- Stocktwits WebSocket quote stream.
- Stocktwits message/feed parsing when accessible.

Optional/local:

- Financial PhraseBank.
- SEntFiN.
- Local processed CSV outputs from the pipeline.
- MongoDB if enabled.

## Limitations

- Stocktwits may rate-limit or block some requests.
- Stocktwits historical bars are returned at Stocktwits' own interval; the app cannot force old historical bars to one-minute resolution.
- The one-minute refresh applies to the running dashboard session and realtime WebSocket checks.
- Social message parsing may return fewer rows than the official Stocktwits UI because the public page/feed can be protected.
- The dashboard is a research and internship prototype, not financial advice or an order execution system.

## Deployment

See `DELIVERY_GUIDE.md` for the full final submission checklist and Railway deployment notes.

Typical Railway command:

```bash
streamlit run src/dashboard.py --server.address 0.0.0.0 --server.port $PORT
```

Required environment variable:

```text
FINVIZ_API_TOKEN
```

Recommended optional variables:

```text
SOCIAL_SOURCE=stocktwits
STOCKTWITS_USE_CURL_IMPERSONATE=1
STOCKTWITS_USE_PUBLIC_API=0
STOCKTWITS_ALLOW_SAMPLE=0
FIN_NEWS_API_TOKEN=your-api-token
```

## Tests

```bash
python -m py_compile src/dashboard.py src/collect_stocktwits.py src/collect_tradingview.py src/api.py
python -m pytest
```

## Final Deliverables

- Public GitHub repository.
- Professional README.
- Railway public URL.
- Demo recording for a nontechnical user.
- Technical recording explaining the code structure.
- AI prompt log.
- Exit survey / Canvas requirements.
- OneDrive folder shared with the professor.
