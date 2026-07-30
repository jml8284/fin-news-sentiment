# Final Delivery Guide

This guide is for the final IST 495 stock market project submission.

## What To Submit

- Public GitHub repository.
- Railway public URL.
- Demo recording MP4.
- Technical recording MP4.
- README.md.
- Delivery guide and checklist.
- Weekly activity logs.
- AI prompt log / conversation notes.
- Canvas exit assignments and survey.
- OneDrive parent folder shared with the professor.

## Final Two-Day Priority Order

1. Confirm the app runs locally without a Streamlit error.
2. Push the latest code to GitHub.
3. Deploy on Railway and save the public URL.
4. Record the demo video during market hours if possible.
5. Record the technical walkthrough.
6. Export or screenshot the Checklist tab.
7. Upload all files to OneDrive and Canvas.

## Demo Recording Checklist

Show the app as if the viewer has no technical background.

1. Open the deployed Railway URL or local Streamlit URL.
2. Explain the dashboard goal: find active stocks, collect news/social data, score sentiment, rank tickers, and monitor alerts.
3. Show the Finviz filters.
4. Show the ranked ticker table and explain sorting/thresholding.
5. Open the news viewer and explain article-level sentiment.
6. Open the Social tab.
7. Select one active ticker from the dropdown.
8. Show the Stocktwits chart range selector.
9. Explain price, volume, message volume, and sentiment lines.
10. Show Data freshness.
11. Show Alerts.
12. Export alert history or ranked table CSV.
13. Mention realtime limitation clearly: historical Stocktwits bars come from Stocktwits, while one-minute realtime quote checks begin after the app starts.

## Technical Recording Checklist

Show how the code was developed and how the major modules work.

1. `src/dashboard.py`: Streamlit UI, tabs, refresh logic, chart rendering, alerts, correlation, data freshness.
2. `src/collect_stocks.py`: Finviz Elite screener collection.
3. `src/collect_tradingview.py`: TradingView numeric screener collection.
4. `src/collect_news.py`: news collection.
5. `src/sentiment_engines.py` and `src/sentiment_analysis.py`: VADER/FinBERT sentiment scoring.
6. `src/ticker_ranking.py`: ranking and message density.
7. `src/collect_stocktwits.py`: Stocktwits chart, message parsing, sentiment gateway, and WebSocket quote stream.
8. `src/api.py`: FastAPI wrapper with optional token.
9. `tests/`: parser, Finviz, Stocktwits, sentiment, and pipeline tests.
10. Deployment files: `Procfile`, `railway.toml`, `requirements.txt`, `.env.example`.

### API Demonstration

If there is enough time in the technical recording, briefly show the optional API:

```text
GET /health
GET /features
GET /alerts/rules
GET /tradingview/screener?top_n=20&min_volume=100000
GET /stocktwits/STAK?zoom=1d&include_realtime=true
GET /stocktwits/STAK/demo-report?zoom=1d
```

Explain that `FIN_NEWS_API_TOKEN` can protect these endpoints through the `X-API-Token` header.

## Railway Deployment

Required environment variable:

```text
FINVIZ_API_TOKEN=your-finviz-token
```

Recommended environment variables:

```text
SOCIAL_SOURCE=stocktwits
STOCKTWITS_USE_CURL_IMPERSONATE=1
STOCKTWITS_USE_PUBLIC_API=0
STOCKTWITS_ALLOW_SAMPLE=0
FIN_NEWS_API_TOKEN=your-api-token
```

Start command:

```bash
streamlit run src/dashboard.py --server.address 0.0.0.0 --server.port $PORT
```

After deployment:

- Open the Railway URL.
- Test during market hours if possible.
- Confirm the Finviz token works.
- Confirm the Social tab does not crash if Stocktwits rate-limits.
- Confirm the dashboard shows data freshness and alerts.

## Current Feature Map Against Professor Requirements

Completed or prototyped:

- Finviz news screener.
- Public RSS/newswire sources for GlobeNewswire, PR Newswire, SEC, FDA, and custom feeds.
- Finviz numeric screener.
- TradingView numeric screener integration.
- Stocktwits social sourcing.
- Rolling window chart.
- Sentiment scoring.
- Message volume / message density.
- AI-style ranking through combined sentiment, news count, and numeric screening fields.
- Sorting and thresholding.
- Correlation analysis.
- Realtime alert prototype.
- API wrapper with token support.
- Optional MongoDB module.
- Railway deployment entrypoint.
- Data freshness monitoring.
- Exportable demo evidence.

Partial / future work:

- Interactive Brokers / Charles Schwab broker integration.
- TradingView news feed integration.
- X, Reddit, and Bluesky production-grade social connectors.
- Business Wire, ACCESSWIRE, Benzinga, Dow Jones, and MT Newswires as stable licensed feeds.
- Redis/Kafka RAM-based message queue.
- CVD calculation from true high-resolution trade data.
- Long-term scans.
- Arbitrage module.
- Google Trends.
- Short squeeze module.
- Options/futures module.
- Broker trading and bracket orders.
- Full autonomous AI agent.

## Suggested Final Explanation

This project focuses on the most important live dashboard path first: Finviz news/screener data, public RSS/newswire sources, Stocktwits social/chart data, realtime quote checks, ranking, correlation, and alerts. Some larger items from the professor's long-term list are marked as future extensions because they require broker accounts, paid feeds, or persistent infrastructure.

## Suggested Future Work Explanation

Use this if the professor asks why every item in the long list is not fully production-ready:

The project implemented the highest-value dashboard path for the internship demo. Broker trading, Redis/Kafka, options, futures, arbitrage, and full broker order routing are listed as future production extensions because they require live credentials, paid data, and additional safety controls. The current system still demonstrates the core workflow: collect fast market/news/social data, score it, rank tickers, monitor rolling windows, and generate alerts.
