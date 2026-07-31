# AI Prompt Log

This file summarizes how AI assistance was used during the project. The project direction, testing decisions, data-source choices, and final review were done by the student. AI was mainly used as a coding/debugging assistant when the implementation became difficult or when live data behavior needed to be investigated.

## Student-Led Work

- Read the project requirements and decided which dashboard features should be prioritized.
- Tested the app locally and on Railway during market and non-market hours.
- Checked Finviz token behavior and updated the deployment environment when the token changed.
- Compared the dashboard with Stocktwits and adjusted the chart layout, ticker selection, and social tab behavior.
- Used Chrome DevTools Network and WebSocket panels to find useful Stocktwits requests.
- Tested different tickers to see which ones had enough live social and chart data.
- Reviewed the final dashboard, README, delivery guide, and public deployment.

## AI-Assisted Work Areas

- Debugged Streamlit runtime errors, import issues, and deployment problems.
- Helped connect the dashboard logic to Finviz, Stocktwits chart data, and Stocktwits WebSocket quote updates.
- Helped redesign the rolling-window feature from the old K-line-only version into a Stocktwits-based social rolling window.
- Helped implement the Stocktwits chart with price, stock volume, sentiment, and message-volume signals in one view.
- Helped explain why historical Stocktwits chart data is usually returned in 5-minute or 10-minute bars, while one-minute updates can only be collected after the app is running.
- Helped add realtime alerts, chart-window alerts, social latest alerts, data freshness checks, and correlation analysis.
- Helped clean the repository for final delivery by removing private process files.
- Helped prepare the demo recording outline, technical recording outline, README, and final delivery checklist.

## Important Prompt Themes

- "Debug why localhost / Streamlit is not opening."
- "Replace Bluesky social source with Stocktwits."
- "Make the rolling window use Stocktwits messages instead of the old K-line logic."
- "Use Stocktwits chart data and make the chart closer to the Stocktwits style, but not identical."
- "Investigate Stocktwits public API limits, web page parsing, sentiment gateway, and WebSocket live quote stream."
- "Explain why the old Stocktwits data is not one-minute resolution."
- "Add one-minute live updates after the program starts."
- "Add realtime alerts and explain how the alerts work."
- "Prepare a nontechnical demo script and a technical code walkthrough."
- "Check the repository for private logs or unrelated delivery files."

## Stocktwits Issue Notes

The Stocktwits part required extra debugging. At first, some requests failed or returned blocked pages, so I tested several approaches: public API calls, frontend JSON files, web scraping with browser-like requests, sentiment gateway requests, and WebSocket messages. The final approach uses Stocktwits chart data when available and extends the latest price with live WebSocket quote updates after the app starts. This means the app can show fresh live updates while it is running, but it cannot recreate one-minute historical data from before the app was started if Stocktwits only returned 5-minute or 10-minute historical bars.

## AI Usage Disclosure

AI was used as an assistant for debugging, implementation support, code review, and documentation drafting. The student selected the project direction, tested the live dashboard, checked the data behavior, and made the final decisions about what to keep in the submitted version. Live results still depend on Finviz and Stocktwits access, market hours, rate limits, and whether each ticker has enough available data.
