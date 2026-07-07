# IST 495 Activity Log — Week 8

**Name:** Jinyang Liu  
**Email:** jml8284@psu.edu  
**Week:** June 22–28, 2026  
**Project:** fin-news-sentiment

---

## Daily Activity Log

| Day | Time of Day | From – To | Description of Activity | Individual or Group? | Duration |
|-----|-------------|-----------|-------------------------|----------------------|----------|
| **Monday** | Morning | 9:30 – 12:00 | Looked up how Stocktwits API works (professor roadmap social part). Read their JSON format for messages and dates. | Individual | 2.5 hrs |
| **Monday** | Afternoon | 1:30 – 4:00 | Wrote `collect_stocktwits.py` to pull messages for each ticker from the public API. | Individual | 2.5 hrs |
| **Tuesday** | Morning | 10:00 – 12:30 | Made `live_stocktwits_metrics.py` — fetch all 20 tickers, count posts in the same date range as Finviz news. | Individual | 2.5 hrs |
| **Tuesday** | Afternoon | 2:00 – 4:30 | Added Stocktwits to the dashboard: new tab, two new columns in the table, updated the live fetch line at the top. | Individual | 2.5 hrs |
| **Wednesday** | Morning | 9:00 – 11:30 | Fixed date parsing for Stocktwits timestamps. Wrote unit tests with fake JSON so I don't need the API every time. | Individual | 2.5 hrs |
| **Wednesday** | Afternoon | 1:00 – 3:30 | Tested on my Mac. Finviz still works (15 news for 7 days, 228 for 6 months). Stocktwits curl only gives HTML on my wifi — not a token problem. | Individual | 2.5 hrs |
| **Thursday** | Morning | 10:00 – 12:00 | Fixed a bug where the app crashed when Stocktwits returned nothing (KeyError on empty table). | Individual | 2 hrs |
| **Thursday** | Afternoon | 2:00 – 4:00 | Shortened the yellow and blue warning messages so they make more sense to me when I demo. | Individual | 2 hrs |
| **Friday** | Morning | 9:30 – 11:30 | Practiced what to tell the professor for Week 7 + Week 8 (live Finviz, FinBERT file, Stocktwits tab). | Individual | 2 hrs |
| **Friday** | Afternoon | 1:00 – 3:00 | Wrote week8 notes and a knowledge pack for myself. Ran pytest. | Individual | 2 hrs |
| **Saturday** | Morning | 10:00 – 12:00 | Read Canvas posts about video interns — not my main task but good to know Mockup is separate from weekly log. | Individual | 2 hrs |
| **Sunday** | Afternoon | 2:00 – 4:30 | Ran Streamlit one more time (4 tabs, SDOT chart looked fine). Finished this activity log. | Individual | 2.5 hrs |

**Estimated total:** ~26 hours

---

## Comments: Learning experience I enjoyed this week

I liked seeing Finviz and Stocktwits in the same dashboard. Finviz works fine with my token, but Stocktwits on my home network just gives back a web page instead of data — took me a while to figure out that's not the same as a wrong Finviz password. Also having **social_density** next to **message_density** makes it easier to see news vs social posts for the same week.

---

## External Help

| Source | Areas | Approx. time |
|--------|-------|----------------|
| **Cursor / AI helper** | Stocktwits code, dashboard hookup, crash fix, wording on alerts, first draft of this log | ~4–5 hrs |
| **Stocktwits + Streamlit docs** | API URL, tab layout | ~1 hr |

I still ran and checked Finviz myself on my laptop.

---

## External materials (links)

- https://elite.finviz.com/api_explanation  
- https://api.stocktwits.com/developers/docs  
- https://docs.streamlit.io/  
- https://feedflash-production.up.railway.app/  
- https://github.com/jml8284/fin-news-sentiment  

---

## My contributions to the course project (Week 8)

1. Stocktwits fetch code (`collect_stocktwits.py`).  
2. Count posts per ticker + social_density (`live_stocktwits_metrics.py`).  
3. Dashboard Stocktwits tab and new table columns.  
4. Bug fix when Stocktwits empty; simpler warning text.  
5. Tests in `tests/test_stocktwits.py`.  
6. Finviz live from Week 7 still works for demo; Stocktwits code is in even if my network shows zero.

---

*Word: `week8_activity_log_IST495.docx` or Downloads folder*
