# Activity Log

Personal dev notes for the fin-news-sentiment project.  
Jinyang Liu · IST 495 · Summer 2026

---

## Week 1

Set up the GitHub repo and picked the topic: Financial News Sentiment Dashboard.

Wrote the first README, folder structure, and `requirements.txt`. Built the initial pipeline skeleton:

- `collect_news.py` (demo CSV + RSS)
- `clean_data.py`
- `sentiment_analysis.py` (VADER)
- `ticker_ranking.py`
- `dashboard.py` (basic Streamlit table)

Added `demo_mock_news.csv` and confirmed the demo path runs end to end.

Wrote `reports/weekly_updates/week1_update.md`.

---

## Week 2

Built `src/collect_stocks.py` for Finviz stock data.

- Pulls ticker, company, sector, price, change %, volume, market cap, P/E
- Filters: exchange, sector, signal presets (most active, top gainers, etc.)
- cloudscraper fallback when requests get blocked
- `demo_mock_stocks.csv` for offline runs

Demo mode worked immediately. Live Finviz worked when network was fine; sometimes blocked by proxy.

Added cloudscraper + lxml to `requirements.txt`.

Wrote `reports/weekly_updates/week2_update.md`.

---

## Week 3

Extended `collect_news.py` to read tickers from `raw_stock_data.csv` and collect news per ticker.

Sources:
- Google News RSS
- Yahoo Finance RSS
- Finviz quote page

Dedup on ticker + url + title. Logs missing news and continues. Tested with `--from-stocks`.

Wrote `reports/weekly_updates/week3_update.md`.

---

## Week 4 · May 25–31

### Pipeline + dashboard

Added the missing pieces to close the professor's flowchart:

- `merge_data.py` — stock CSV + sentiment ranking → `final_dataset.csv`
- `run_pipeline.py` — one command for demo or live (`--demo`, later `--elite`)
- Upgraded `dashboard.py` — filters, summary metrics, Plotly chart, news viewer
- Improved `clean_data.py` — strip HTML from news text

Ran `python -m src.run_pipeline --demo` successfully. Updated README to match the code.

Wrote `reports/weekly_updates/week4_update.md`.

### Finviz Elite (professor feedback)

Professor wanted the Technical screener ~20 stocks, personal API token, export for the list, stock page for news.

Added:
- `finviz_config.py` — `FINVIZ_API_TOKEN` from `.env`, Elite URLs, technical-gainers preset
- `--elite` on `collect_stocks.py` and `run_pipeline.py`
- Elite `stock?t=TICKER` pages in `collect_news.py`
- `.env.example` (token stays in local `.env` only)

### Demo run

```bash
python -m src.run_pipeline --demo
streamlit run src/dashboard.py
```

Dashboard showed ranked tickers, filters, sentiment chart, news viewer. Demo ranking: NVDA > AAPL > TSLA.

### GitHub

Committed changes locally. Working on push to `github.com/jml8284/fin-news-sentiment`.

### Mockup assignment

Need to hand-draw or software-sketch front end + secondary layers for Canvas (separate from code).

---

## Week 5 · June 1–7

### Production + evaluation

- Pipeline **defaults to Finviz Elite** (no `--demo` flag needed).
- `evaluate_sentiment.py` → `vader_eval_report.csv` (PhraseBank 57.1%, combined 54.3%).
- SEC RSS added to `collect_news.py`; `collected_at` on news rows.
- `store_mongo.py` + `--mongo` flag (optional).
- Dashboard: sentiment **pie chart**; news sorted by published/collected_at.

### Verified production run

```bash
python -m src.run_pipeline --evaluate
streamlit run src/dashboard.py
```

Real screener tickers (e.g. SUGP, STI, SNBR) visible in dashboard — not demo AAPL/TSLA.

Wrote `reports/weekly_updates/week5_update.md`.  
Activity log docx: `~/Downloads/IST495_Week5_Activity_Log_Jinyang_Liu.docx`.

### Still open

- GitHub push (PAT)
- Mockup assignment for Canvas
- FinBERT / social / Redis — Week 6+

Full chat memory: `reports/conversation_memory.md`.

---

## Commands I use

```bash
source .venv/bin/activate

# Production (needs .env FINVIZ_API_TOKEN)
python -m src.run_pipeline --evaluate
streamlit run src/dashboard.py

# Demo / offline
python -m src.run_pipeline --demo
```

---

## Notes

- Small tickers often have no news — test with NVDA, F, INTC
- Proxy can block Finviz; `--demo` is fine for presentations
- Never commit `.env`
- VADER weak on negative financial text — FinBERT candidate for Week 6

---

*Last updated: Week 5 (June 1–7, 2026)*
