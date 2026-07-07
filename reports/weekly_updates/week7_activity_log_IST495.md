# IST 495 Activity Log — Week 7

**Name:** Jinyang Liu  
**Email:** jml8284@psu.edu  
**Week:** June 15–21, 2026  
**Project:** fin-news-sentiment (Financial News Sentiment Analysis Dashboard)

---

## Daily Activity Log

| Day | Time of Day | From – To | Description of Activity | Individual or Group? | Duration |
|-----|-------------|-----------|-------------------------|----------------------|----------|
| **Monday** | Morning | 9:00 – 12:00 | Researched FinBERT (`ProsusAI/finbert`) for professor roadmap item 6 (AI rankings). Started `src/sentiment_engines.py` with pluggable VADER / FinBERT engines and batch scoring API. | Individual | 3 hrs |
| **Monday** | Afternoon | 1:30 – 3:30 | Updated `sentiment_analysis.py` with `--engine vader\|finbert`; added `sentiment_engine.txt` metadata. Installed `transformers` and `torch` in project venv. | Individual | 2 hrs |
| **Tuesday** | Morning | 10:00 – 12:30 | Extended `evaluate_sentiment.py` to compare VADER and FinBERT on Financial PhraseBank and combined benchmark CSV. Generated `sentiment_eval_report.csv`. | Individual | 2.5 hrs |
| **Tuesday** | Afternoon | 2:00 – 4:30 | Wired `run_pipeline.py` flags `--finbert` and `--evaluate-models`. Added `tests/test_sentiment_engines.py`. Ran first FinBERT benchmark (PhraseBank accuracy ~76% vs VADER ~57%). | Individual | 2.5 hrs |
| **Wednesday** | Morning | 9:30 – 12:00 | Refactored dashboard data path: created `src/live_finviz_metrics.py` to scrape Finviz Elite quote-page news in parallel (not pipeline CSV snapshots). | Individual | 2.5 hrs |
| **Wednesday** | Afternoon | 1:00 – 3:30 | Rewrote `src/dashboard.py` ranked table and news viewer for live Finviz data. Added live fetch timestamp, 60s screener/chart refresh, and manual Refresh now button. | Individual | 2.5 hrs |
| **Thursday** | Morning | 10:00 – 12:30 | Fixed Finviz news HTML parser in `collect_news.py` (`fullview-news-outer`, date carry-forward). Removed 80-item Finviz cap (`max_items=0`). Added elite URL fallback and `trust_env=False` for proxy issues. | Individual | 2.5 hrs |
| **Thursday** | Afternoon | 2:00 – 4:00 | Added live metrics tests (`test_live_finviz_metrics.py`, `test_finviz_news_parse.py`). Ran `scripts/verify_live_finviz.py` on local machine; confirmed live screener + quote news working with professor token. | Individual | 2 hrs |
| **Friday** | Morning | 9:00 – 11:30 | Debugged dashboard long loading: fixed `st.fragment(run_every=60)` re-triggering full news scrape every minute. Separated live news cache (5 min) from 60s screener/chart refresh. | Individual | 2.5 hrs |
| **Friday** | Afternoon | 1:00 – 3:00 | Set live Dashboard scoring to VADER for speed; FinBERT reserved for offline pipeline and benchmark report. Fixed Week 6 chart bug (change % stale outside fragment). | Individual | 2 hrs |
| **Saturday** | Morning | 10:00 – 12:00 | Auto-generated `sentiment_eval_report.md` summary alongside CSV (model/dataset explanations, takeaways, deployment notes). Updated message_density display to Sparse / Moderate / Dense labels. | Individual | 2 hrs |
| **Saturday** | Afternoon | 1:30 – 3:00 | Full pytest run (35 passing). Updated `week7_update.md` and `conversation_memory.md`. Rehearsed professor demo: live fetch timestamp, ranked tickers, FinBERT eval report. | Individual | 1.5 hrs |
| **Sunday** | Afternoon | 2:00 – 4:00 | Drafted Week 7 activity log. Verified Streamlit dashboard end-to-end with live Finviz Elite (20 tickers, news_count, sentiment_rank, 3-tab layout). | Individual | 2 hrs |

**Estimated total:** ~27 hours

---

## Comments: Learning experience I enjoyed this week

The biggest breakthrough was moving from **pipeline CSV snapshots** to **true live Finviz scraping** in the dashboard. Seeing the **Live fetch UTC timestamp** update and `news_count` come directly from quote pages made the project feel like a real terminal-style screener, not a static homework export.

Integrating **FinBERT** also helped me understand the difference between a fast baseline (VADER) and a finance-tuned model. Running the benchmark and reading `sentiment_eval_report.csv` showed why we keep VADER for live scoring but still document FinBERT for AI ranking — speed vs accuracy is a real engineering trade-off, not just a model choice.

---

## External Help

| Source | Areas | Approx. time |
|--------|-------|----------------|
| **Cursor / AI coding assistant** | FinBERT engine module, live_finviz_metrics refactor, dashboard fragment/cache debugging, Finviz HTML parser fixes, pytest cases, activity log draft | ~5–6 hrs across the week |
| **Hugging Face / FinBERT model page** | Model ID, transformers usage, first-time download | ~45 min |
| **Streamlit docs** | `st.fragment`, `st.cache_data`, spinner/cache TTL patterns | ~30 min |
| **Finviz Elite API docs** | Quote page news scrape, export screener | ~30 min |

I reviewed, tested, and demoed all changes myself on my local machine with the professor Finviz token.

---

## External materials (links)

- Finviz Elite API: https://elite.finviz.com/api_explanation  
- Finviz screener (Technical preset): https://elite.finviz.com/screener  
- ProsusAI FinBERT (Hugging Face): https://huggingface.co/ProsusAI/finbert  
- Streamlit documentation: https://docs.streamlit.io/  
- VADER sentiment: https://github.com/cjhutto/vaderSentiment  
- FeedFlash reference (professor): https://feedflash-production.up.railway.app/  
- Project repository: https://github.com/jml8284/fin-news-sentiment  

---

## My contributions to the course project (Week 7)

1. **FinBERT integration (`src/sentiment_engines.py`)** — Pluggable VADER / FinBERT engines; `--engine finbert` on pipeline; model metadata file.

2. **Model evaluation (`evaluate_sentiment.py`)** — VADER vs FinBERT on PhraseBank + combined datasets; outputs `sentiment_eval_report.csv` and auto-generated `sentiment_eval_report.md`.

3. **Live Finviz dashboard (`live_finviz_metrics.py`, `dashboard.py`)** — Real-time Finviz Elite screener + quote-page news scrape; live fetch timestamp; 60s screener/chart refresh; 3-tab layout (chart, ranked tickers, news viewer).

4. **Finviz news reliability (`collect_news.py`)** — Robust HTML parser, no row cap, elite fallback URL, proxy-safe requests.

5. **Performance & UX fixes** — Stopped 60s fragment from re-scraping all news; VADER for live scoring; message_density shown as Sparse / Moderate / Dense.

6. **Testing & documentation** — 35 pytest tests passing; `week7_update.md`; `scripts/verify_live_finviz.py` for local live verification.

---

*Copy into Word template `Sample Activity-Log_IST495.docx`, or use `week7_activity_log_IST495.docx` in this folder.*
