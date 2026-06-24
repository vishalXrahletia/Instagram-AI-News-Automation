"""
News sourcing: pulls AI news from RSS feeds + Hacker News, dedupes near-identical
titles, filters for relevance, and ranks by recency.
"""

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import httpx

RSS_FEEDS = {
    "TechCrunch": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "VentureBeat": "https://venturebeat.com/category/ai/feed/",
    "The Verge": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "Ars Technica": "https://arstechnica.com/ai/feed/",
}

HN_ALGOLIA_URL = "https://hn.algolia.com/api/v1/search_by_date"

KEYWORDS = [
    "ai", "artificial intelligence", "llm", "gpt", "machine learning",
    "model", "openai", "anthropic", "claude", "gemini", "chatbot", "genai",
]


def _parse_date(raw: str) -> datetime:
    if not raw:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def fetch_rss(source: str, url: str, timeout: int = 15) -> list[dict]:
    feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
    items = []
    for entry in feed.entries:
        items.append({
            "title": getattr(entry, "title", ""),
            "link": getattr(entry, "link", ""),
            "summary": getattr(entry, "summary", "") or getattr(entry, "description", ""),
            "source": source,
            "published": getattr(entry, "published", "") or getattr(entry, "updated", ""),
        })
    return items


def fetch_hacker_news(query: str = "AI OR artificial intelligence OR LLM OR GPT", hits: int = 30) -> list[dict]:
    with httpx.Client(timeout=15) as client:
        resp = client.get(HN_ALGOLIA_URL, params={"tags": "story", "query": query, "hitsPerPage": hits})
        resp.raise_for_status()
        data = resp.json()

    items = []
    for hit in data.get("hits", []):
        if not hit.get("title"):
            continue
        items.append({
            "title": hit["title"],
            "link": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
            "summary": hit["title"],
            "source": "Hacker News",
            "published": hit.get("created_at", ""),
        })
    return items


def dedupe_and_rank(items: list[dict], keyword_filter: bool, limit: int) -> list[dict]:
    seen = set()
    filtered = []

    for item in items:
        title_lower = item["title"].lower()
        if not title_lower:
            continue
        if keyword_filter and not any(k in title_lower for k in KEYWORDS):
            continue
        key = re.sub(r"[^a-z0-9]", "", title_lower)[:40]
        if key in seen:
            continue
        seen.add(key)
        filtered.append(item)

    filtered.sort(key=lambda i: _parse_date(i["published"]), reverse=True)
    return filtered[:limit]


def get_top_ai_stories(limit: int = 8) -> list[dict]:
    """Fetch, dedupe, and rank today's top AI stories across all sources."""
    all_items: list[dict] = []

    for source, url in RSS_FEEDS.items():
        try:
            all_items.extend(fetch_rss(source, url))
        except Exception as e:
            print(f"[news] WARNING: failed to fetch {source}: {e}")

    try:
        all_items.extend(fetch_hacker_news())
    except Exception as e:
        print(f"[news] WARNING: failed to fetch Hacker News: {e}")

    return dedupe_and_rank(all_items, keyword_filter=True, limit=limit)
