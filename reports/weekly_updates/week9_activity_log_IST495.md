# IST 495 Activity Log — Week 9

**Name:** Jinyang Liu  
**Email:** jml8284@psu.edu  
**Week:** June 29 – July 5, 2026  
**Project:** fin-news-sentiment (Financial News Sentiment Analysis Dashboard)

---

## Daily Activity Log

| Day | Time of Day | From – To | Description of Activity | Individual or Group? | Duration |
|-----|-------------|-----------|-------------------------|----------------------|----------|
| **Monday** | Morning | 9:30 – 12:00 | Planned Week 9 scope: unify rolling window across news table and K-line chart (professor Week 6 feedback follow-up). | Individual | 2.5 hrs |
| **Monday** | Afternoon | 1:30 – 4:00 | Added `filter_bars_by_date_window()` and `window_change_pct()` in `finviz_charts.py`. | Individual | 2.5 hrs |
| **Tuesday** | Morning | 10:00 – 12:30 | Wired dashboard chart tab to sidebar rolling window; updated metrics (bars in window, window change %). | Individual | 2.5 hrs |
| **Tuesday** | Afternoon | 2:00 – 4:00 | Renamed sidebar section to **Rolling window** (news + Stocktwits + chart). Empty-window warning for intraday vs daily. | Individual | 2 hrs |
| **Wednesday** | Morning | 9:00 – 11:30 | Tests in `test_finviz_charts.py` for window filter and chart title label. | Individual | 2.5 hrs |
| **Wednesday** | Afternoon | 1:00 – 3:00 | Manual Streamlit check: Last 7 / 30 / Custom on daily chart aligned with `news_count`. | Individual | 2 hrs |
| **Thursday** | Morning | 10:00 – 12:00 | Wrote `week9_update.md` and activity log. Reviewed Stocktwits sample fallback still OK with shared window. | Individual | 2 hrs |
| **Friday** | Afternoon | 2:00 – 4:00 | Demo prep: explain rolling window on chart + ranked table in one sidebar control. | Individual | 2 hrs |

**Total hours this week:** ~20 hrs

---

## Comments

Week 9 closed the loop on rolling windows: the same UTC range now drives Finviz news counts, Stocktwits density, and the live candlestick chart. Window change % on the chart is clearer for demos than screener day change when comparing a 7-day story.

---

## External Help / Resources

- Streamlit sidebar + fragment refresh patterns  
- Finviz Elite `quote_export` API (existing Week 6–7 work)  
- Cursor for implementation assistance  

---

## Links

- Repo: https://github.com/jml8284/fin-news-sentiment  
- Finviz Elite API: https://elite.finviz.com/api_explanation  

---

## My contributions to the course project (Week 9)

1. Chart rolling window filter (`filter_bars_by_date_window`).  
2. Window-scoped change % metric on K-line tab.  
3. Unified sidebar **Rolling window** for news + social + chart.  
4. Tests for chart window helpers.  
5. Week 9 update + activity log.
