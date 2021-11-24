# News-Analysis
Quick and dirty news analysis from Semana and El Tiempo newspapers (for now).

## News Crawling

The crawler is found in the directory NewsCrawler. It defines the specific crawlers for El Tiempo and Semana newspapers. **This crawler works by August 2021**

> Both crawlers extends the class NewsSource that handles the scrapping loop, wait times, etc.

## Notebooks
There are two notebooks:
1. **Crawling Newsheaders.ipynb:** Performs the crawling using the classes defined in News Crawling according to the parameters specified. In this case, the crawler looks for news related to covid-19 and the 2021 Colombian Protests.
2. **NewsHeadersAnalysis.ipynb:** This script performs several Data Mining and NLP techniques to clean the crawled texts and get interesting insights of the behaviour of news in both newspapers.
