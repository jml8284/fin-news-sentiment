# IST 495 Activity Log — Week 4

**Name:** Jinyang Liu  
**Email:** [your PSU email]  
**Week:** May 25–31, 2026  
**Project:** fin-news-sentiment (Financial News Sentiment Analysis Dashboard)

---

## Daily Activity Log

| Day | Time of Day | From – To | Description of Activity | Individual or Group? | Duration |
|-----|-------------|-----------|-------------------------|--------------------|----------|
| **Monday** | Morning | 9:00 – 11:30 | Built `merge_data.py` to join Finviz stock data with ticker-level sentiment rankings into `final_dataset.csv`. Tested merge output in pandas. | Individual | 2.5 hrs |
| **Monday** | Afternoon | 1:00 – 3:00 | Added `run_pipeline.py` so the full chain (stocks → news → clean → VADER → rank → merge) runs with one command. Ran `--demo` mode end to end. | Individual | 2 hrs |
| **Tuesday** | Morning | 10:00 – 12:30 | Upgraded Streamlit dashboard: sidebar filters (sector, min news count, sort), summary metrics, Plotly sentiment bar chart. | Individual | 2.5 hrs |
| **Tuesday** | Afternoon | 2:00 – 4:00 | Added per-ticker news viewer to dashboard (dropdown, sentiment labels, article links). Improved `clean_data.py` to strip HTML from RSS text. | Individual | 2 hrs |
| **Wednesday** | Morning | 9:30 – 11:00 | Met professor feedback: implemented Finviz Elite export API for the 20-stock Technical screener. Created `finviz_config.py` and `.env.example` for API token. | Individual | 1.5 hrs |
| **Wednesday** | Afternoon | 1:00 – 3:30 | Updated `collect_stocks.py` and `collect_news.py` for Elite mode (`--elite`): export URL for stock list, `stock?t=TICKER` pages for news. | Individual | 2.5 hrs |
| **Thursday** | Morning | 10:00 – 12:00 | Updated README and wrote Week 4 weekly update. Re-ran demo pipeline and fixed small bugs in dashboard column display. | Individual | 2 hrs |
| **Thursday** | Afternoon | 2:00 – 3:00 | Prepared for check-in: rehearsed demo (`run_pipeline --demo` + Streamlit). Drafted presentation talking points. | Individual | 1 hr |
| **Friday** | Morning | 9:00 – 11:00 | Git commit of all Week 4 changes (21 files). Troubleshot GitHub push authentication (PAT vs password). | Individual | 2 hrs |
| **Friday** | Afternoon | 1:00 – 2:30 | Started mockup assignment sketch (dashboard front end + ticker detail / settings secondary layers). Reviewed FeedFlash reference site. | Individual | 1.5 hrs |
| **Saturday** | Morning | 10:00 – 11:30 | Tested Elite pipeline locally with personal Finviz token in `.env`. Verified 20-stock screener filters match professor’s Technical tab setup. | Individual | 1.5 hrs |
| **Sunday** | Afternoon | 2:00 – 3:00 | Wrote activity log and organized project notes. Planned Week 5: VADER benchmark evaluation on local datasets. | Individual | 1 hr |

**Estimated total:** ~22 hours

---

## Comments: Learning experience I enjoyed this week

The most satisfying part was seeing the **full pipeline run in one command** and then opening the dashboard with real merged data — stock price, change %, and sentiment score in the same table. Before this week everything was separate CSVs and a basic table. Connecting merge + filters + chart made it feel like an actual product, not just scripts.

I also learned how **Finviz Elite export API** works (export URL + auth token for the screener, stock page URL for per-ticker news). That matched what the professor described in class and helped me understand the difference between pulling a stock list vs pulling news for one ticker.

---

## External Help

| Source | Areas | Approx. time |
|--------|-------|----------------|
| **Cursor / AI coding assistant** | Debugging Finviz HTML parsing, structuring `merge_data.py`, dashboard Plotly chart, Elite API URL patterns, git commit message, activity log draft | ~3–4 hrs across the week |
| **Finviz Elite API docs** | Export URL format, auth parameter, screener filter codes | ~30 min |
| **Streamlit docs** | `st.cache_data`, column config, sidebar filters | ~45 min |

I wrote and reviewed all core logic myself; AI mainly helped speed up boilerplate and troubleshoot errors.

---

## External materials (links)

- Finviz Elite API explanation: https://elite.finviz.com/api_explanation  
- Finviz screener (Technical filters reference): https://elite.finviz.com/screener  
- FeedFlash dashboard reference (professor): https://feedflash-production.up.railway.app/  
- Streamlit documentation: https://docs.streamlit.io/  
- VADER sentiment (project baseline): https://github.com/cjhutto/vaderSentiment  
- Project repository: https://github.com/jml8284/fin-news-sentiment  

---

## My contributions to the course project (Week 4)

1. **`merge_data.py`** — Merges `raw_stock_data.csv` with `ticker_ranking.csv` into dashboard-ready `final_dataset.csv`.

2. **`run_pipeline.py`** — Single entry point for demo and Elite live runs.

3. **Dashboard upgrade (`dashboard.py`)** — Filters, summary metrics, sentiment bar chart, per-ticker news viewer with VADER labels.

4. **Finviz Elite integration (`finviz_config.py`, `--elite` flags)** — Professor’s 20-stock Technical screener via export API; news from Elite stock pages; token stored in local `.env`.

5. **Documentation** — Updated README, Week 4 report, personal activity log; committed to GitHub (commit `04e7dca`).

6. **End-to-end demo** — Verified `python -m src.run_pipeline --demo` and `streamlit run src/dashboard.py` for internship check-in.

---

*Copy sections above into the Word template: Sample Activity-Log_IST495.docx*
