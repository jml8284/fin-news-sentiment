Financial News Sentiment Analysis Dashboard
Project Description
This project is for my IST 495 Summer 2026 internship. The goal is to build a Python-based financial newssentiment analysis and stock ticker ranking system.
The system will collect financial news related to stock tickers, analyze the sentiment of each news item,calculate message density, and display ranked tickers in a dashboard. The final dashboard is planned towork similarly to a stock screener, where users can view ticker-level sentiment scores, recent news activity,and related news articles.
This project is connected to the internship topic of using generative AI and agentic AI tools to analyzefinancial news and stock-related information. The project will use Python and may use AI tools such asChatGPT, Microsoft Copilot, Gemini, Claude, CrewAI, or other agent builders to support coding, promptdesign, and workflow automation.
Main Goals
Collect financial news from online sources, RSS feeds, or other available financial news platforms.
Clean and organize collected news data.
Identify related stock tickers from news titles, summaries, or article content.
Analyze sentiment for each financial news item.
Calculate ticker-level sentiment scores.
Calculate message density for each ticker based on the number of related news items.
Rank stock tickers based on sentiment score and news activity.
Build a dashboard to display ranked tickers, sentiment scores, message density, and recent news.
Document the project clearly so that another person can run the code on a separate machine.
Planned Project Structure
fin-news-sentiment/
├── README.md
├── requirements.txt
├── data/
│ ├── raw/
│ └── processed/
├── src/
│ ├── collect_news.py
│ ├── clean_data.py
│ ├── sentiment_analysis.py
•
•
•
•
•
•
•
•
•
1
│ ├── ticker_ranking.py
│ └── dashboard.py
├── notebooks/
│ └── exploration.ipynb
└── reports/
└── weekly_updates/
Folder Description
data/raw/
This folder will store the original collected news data before cleaning.
Example files:
raw_news_data.csv
data/processed/
This folder will store cleaned and processed datasets.
Example files:
cleaned_news_data.csv
sentiment_results.csv
ticker_ranking.csv
src/
This folder will contain the main Python source code.
Planned files:
collect_news.py : collects financial news data from RSS feeds or other sources.
clean_data.py : cleans raw news data and prepares it for analysis.
sentiment_analysis.py : analyzes the sentiment of each news item.
ticker_ranking.py : calculates ticker-level sentiment scores and message density.
dashboard.py : runs the dashboard application.
notebooks/
This folder will contain exploratory analysis notebooks.
•
•
•
•
•
2
Planned file:
exploration.ipynb
: used for testing data cleaning, sentiment analysis, and visualizations.
reports/weekly_updates/
This folder will contain weekly internship progress updates.
Each weekly update will summarize:
What was completed during the week.
Problems or challenges.
Next steps.
Current deliverables.
Tools and Technologies
Planned tools include:
Python
pandas
requests
BeautifulSoup
feedparser
nltk or VADER
Hugging Face models or FinBERT
Streamlit
GitHub
AI tools such as ChatGPT, Copilot, Gemini, Claude, or CrewAI
Planned Workflow
The planned system workflow is:
Financial News Sources
↓
Data Collection
↓
Data Cleaning
↓
Ticker Matching
↓
Sentiment Analysis
↓
Ticker-Level Aggregation
↓
•
•
•
•
•
•
•
•
•
•
•
•
•
•
•
3
Message Density Calculation
↓
Dashboard Visualization
Data Collection Plan
The project will start by collecting financial news data from accessible sources such as RSS feeds or publicfinancial news pages. Possible sources include financial news websites, market news feeds, and stock-related news sources.
The collected data may include:
News title
News summary or article text
Published time
Source name
URL
Related stock ticker
Sentiment Analysis Plan
The project will first use a simple baseline sentiment analysis method. After the baseline version works, theproject may test a finance-specific sentiment model.
Possible sentiment methods include:
VADER
TextBlob
FinBERT
Other transformer-based sentiment models
Each news item will be labeled as one of the following:
Positive
Neutral
Negative
The system may also store a sentiment score for each item.
Ticker Ranking Plan
After sentiment analysis, the project will calculate ticker-level metrics.
Possible metrics include:
Average sentiment score
•
•
•
•
•
•
•
•
•
•
•
•
•
•
4
Number of related news articles
Positive news ratio
Negative news ratio
Message density
Latest sentiment score
The final ranking table may look like this:
Ticker
Average Sentiment
News Count
Message Density
Rank
AAPL
0.35
20
High
1
TSLA
-0.20
35
High
2
NVDA
0.50
18
Medium
3
Dashboard Plan
The planned dashboard will display:
Ranked stock tickers
Sentiment scores
Message density
Recent news articles
Sentiment distribution charts
Filters for ticker, source, and time range
The dashboard will likely be built with Streamlit.
How to Run
The full running instructions will be updated as the project develops.
Planned setup:
pip install -r requirements.txt
Planned dashboard command:
streamlit run src/dashboard.py
Current Status
This repository has been created for the IST 495 internship project. The project is currently in the planningand setup stage.
•
•
•
•
•
•
•
•
•
•
•
5
Current completed items:
GitHub repository created.
Initial README file created.
Project topic selected.
Planned project structure documented.
Next steps:
Create the project folders.
Add a
requirements.txt
file.
Start testing financial news data collection.
Create the first version of the data collection script.
Prepare weekly progress updates.
Internship Information
Course: IST 495 Summer 2026 Internship
Project Topic: Financial News Sentiment Analysis
Student: Jinyang Liu
GitHub Repository:
fin-news-sentiment
Method of Work: Remote
Main Programming Language: Python
Notes
This project is still under development. The README file will be updated throughout the internship as morecode, data processing steps, and dashboard features are completed.
•
•
•
•
•
•
•
•
•
•
•
•
•
•
•
6
