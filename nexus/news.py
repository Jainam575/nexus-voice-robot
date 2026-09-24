"""Nexus Robot — News (Google News RSS, no API key needed)."""
import logging
import requests
import xml.etree.ElementTree as ET

from .config import NEWS_TOPIC

logger = logging.getLogger("Nexus.News")


def get_news(topic=None, count=3):
    topic = (topic or NEWS_TOPIC or "").strip()
    if topic:
        url = f"https://news.google.com/rss/search?q={requests.utils.quote(topic)}&hl=en-IN&gl=IN&ceid=IN:en"
    else:
        url = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
    try:
        r = requests.get(url, timeout=6)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        items = root.findall(".//item")[:count]
        headlines = []
        for item in items:
            title = item.findtext("title") or ""
            headline = title.rsplit(" - ", 1)[0].strip()
            if headline:
                headlines.append(headline)
        if not headlines:
            return "I couldn't find any news right now."
        lead = f"Here's the latest on {topic}: " if topic else "Here's today's top news: "
        return lead + ". ".join(headlines) + "."
    except requests.exceptions.Timeout:
        return "The news service is taking too long to respond."
    except requests.exceptions.ConnectionError:
        return "I can't reach the news service right now. Check your internet connection."
    except Exception as e:
        logger.error("News fetch error: %s", e, exc_info=True)
        return "Sorry, I couldn't reach the news right now."
