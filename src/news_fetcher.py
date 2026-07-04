import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List
import re
import xml.etree.ElementTree as ET


class NewsFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        })

    def fetch_google_news(self, symbol: str, max_articles: int = 5) -> List[dict]:
        query = f"{symbol} cổ phiếu chứng khoán"
        url = "https://news.google.com/rss/search"
        params = {
            "q": query,
            "hl": "vi",
            "gl": "VN",
            "ceid": "VN:vi",
        }
        try:
            resp = self.session.get(url, params=params, timeout=15)
            root = ET.fromstring(resp.content)
            articles = []
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall(".//item")[:max_articles]:
                title = entry.findtext("title", "")
                link = entry.findtext("link", "")
                pub_date = entry.findtext("pubDate", "")
                desc_html = entry.findtext("description", "")
                summary = self._clean_html(desc_html)[:200] if desc_html else ""
                articles.append({
                    "title": title,
                    "url": link,
                    "date": pub_date,
                    "summary": summary,
                    "source": "google-news",
                })
            return articles
        except Exception as e:
            return []

    def fetch_cafef_search(self, symbol: str, max_articles: int = 5) -> List[dict]:
        url = f"https://s.cafef.vn/tim-kiem.chn"
        params = {"keywords": symbol.upper(), "page": 1}
        try:
            resp = self.session.get(url, params=params, timeout=15)
            soup = BeautifulSoup(resp.text, "lxml")
            articles = []
            for item in soup.select(".listnews .item, .news-list .item, .search-item")[:max_articles]:
                title_el = item.select_one("a")
                date_el = item.select_one(".date, .time, .ngay")
                if title_el:
                    href = title_el.get("href", "")
                    full_url = href if href.startswith("http") else "https://s.cafef.vn" + href
                    articles.append({
                        "title": title_el.get_text(strip=True),
                        "url": full_url,
                        "date": date_el.get_text(strip=True) if date_el else "",
                        "summary": "",
                        "source": "cafef",
                    })
            return articles
        except Exception as e:
            return []

    def fetch_vietstock_news(self, symbol: str, max_articles: int = 5) -> List[dict]:
        url = "https://vietstock.vn/tim-kiem.htm"
        params = {"q": symbol.upper()}
        try:
            resp = self.session.get(url, params=params, timeout=15)
            soup = BeautifulSoup(resp.text, "lxml")
            articles = []
            for item in soup.select(".search-list li, .news-item, .result-item")[:max_articles]:
                title_el = item.select_one("a")
                date_el = item.select_one(".date, time, .time")
                if title_el:
                    href = title_el.get("href", "")
                    full_url = href if href.startswith("http") else "https://vietstock.vn" + href
                    articles.append({
                        "title": title_el.get_text(strip=True),
                        "url": full_url,
                        "date": date_el.get_text(strip=True) if date_el else "",
                        "summary": "",
                        "source": "vietstock",
                    })
            return articles
        except Exception as e:
            return []

    def fetch_all_news(self, symbol: str, max_articles: int = 5) -> List[dict]:
        all_news = []
        all_news.extend(self.fetch_google_news(symbol, max_articles))
        all_news.extend(self.fetch_cafef_search(symbol, max_articles))
        all_news.extend(self.fetch_vietstock_news(symbol, max_articles))

        seen = set()
        unique_news = []
        for article in all_news:
            title = article["title"].lower().strip()
            if title and title not in seen:
                seen.add(title)
                unique_news.append(article)

        return unique_news[:max_articles * 3]

    def fetch_market_news(self, max_articles: int = 10) -> List[dict]:
        return self.fetch_google_news("thị trường chứng khoán Việt Nam", max_articles)

    @staticmethod
    def _clean_html(html_text: str) -> str:
        clean = re.sub(r"<[^>]+>", "", html_text)
        return clean.strip()
