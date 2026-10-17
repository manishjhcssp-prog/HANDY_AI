"""
JARVIS AI - Web Information & Weather Tools (Tier 3)
Live web information retrieval and real-time weather forecasting.
"""

import logging
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger("JARVIS.Tools.Web")


async def get_weather(city: str = "Bengaluru") -> str:
    """
    Retrieves the current weather forecast for a given city or location.
    """
    clean_city = city.strip().replace(" ", "+")
    url = f"https://wttr.in/{clean_city}?format=j1"
    headers = {"User-Agent": "curl/7.68.0"}

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return f"Weather service temporarily unavailable (status {resp.status_code})."

            data = resp.json()
            current = data.get("current_condition", [{}])[0]
            temp_c = current.get("temp_C", "N/A")
            feels_like = current.get("FeelsLikeC", "N/A")
            desc = current.get("weatherDesc", [{}])[0].get("value", "Clear")
            humidity = current.get("humidity", "N/A")
            wind = current.get("windspeedKmph", "N/A")

            return (
                f"Current weather in {city.title()}: {desc}, {temp_c}°C (feels like {feels_like}°C), "
                f"Humidity: {humidity}%, Wind: {wind} km/h."
            )
    except Exception as e:
        logger.warning(f"Failed to fetch weather for {city}: {e}")
        return f"Could not retrieve weather information for {city}: {str(e)}"


import html
import re
import xml.etree.ElementTree as ET

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None


async def _search_google_news_rss(query: str, max_results: int = 4) -> list[str]:
    """Retrieves real-time news headlines via Google News RSS (zero rate-limit, 100% free)."""
    clean_query = query.strip().replace(" ", "+")
    url = f"https://news.google.com/rss/search?q={clean_query}&hl=en-US&gl=US&ceid=US:en"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    try:
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                root = ET.fromstring(resp.text)
                items = root.findall("./channel/item")
                results = []
                tag_re = re.compile(r"<[^>]+>")
                for item in items[:max_results]:
                    title_elem = item.find("title")
                    if title_elem is not None and title_elem.text:
                        raw_title = html.unescape(tag_re.sub("", title_elem.text).strip())
                        pubdate_elem = item.find("pubDate")
                        pubdate = pubdate_elem.text.strip() if pubdate_elem is not None and pubdate_elem.text else ""
                        if pubdate:
                            parts = pubdate.split()
                            date_str = " ".join(parts[:4]) if len(parts) >= 4 else pubdate
                            results.append(f"• {raw_title} ({date_str})")
                        else:
                            results.append(f"• {raw_title}")
                return results
    except Exception as e:
        logger.debug(f"Google News RSS search failed: {e}")
    return []


def _search_ddgs_sync(query: str, is_news: bool, max_results: int = 4) -> list[str]:
    """Synchronous DDGS search query execution for thread executor."""
    if not DDGS:
        return []
    results = []
    try:
        ddgs = DDGS()
        if is_news:
            raw_news = list(ddgs.news(query, max_results=max_results))
            for item in raw_news:
                title = item.get("title", "").strip()
                body = item.get("body", "").strip()
                source = item.get("source", "")
                if title:
                    src_suffix = f" [{source}]" if source else ""
                    if body:
                        results.append(f"• {title}{src_suffix}: {body}")
                    else:
                        results.append(f"• {title}{src_suffix}")
            if results:
                return results

        # Fallback or standard general text search
        raw_text = list(ddgs.text(query, max_results=max_results))
        for item in raw_text:
            title = item.get("title", "").strip()
            body = item.get("body", "").strip()
            if title and body:
                results.append(f"• {title}: {body}")
            elif title:
                results.append(f"• {title}")
    except Exception as e:
        logger.debug(f"DDGS query execution error: {e}")
    return results


async def search_duckduckgo(query: str, max_results: int = 4) -> str:
    """
    Performs resilient, zero-cost web search with multi-tier fallback:
    Tier 1: Real-time News RSS (if news query)
    Tier 2: DDGS TLS-fingerprinted search (news & web)
    Tier 3: Graceful fallback synthesis without exposing raw HTTP codes.
    """
    clean_query = query.strip()
    if not clean_query:
        return "No search query provided, sir."

    lower = clean_query.lower()
    is_news = any(kw in lower for kw in ["news", "latest", "today", "headlines", "recent", "update", "current"])

    # 1. If it's a news query, Google News RSS is the fastest, never-blocked source
    if is_news:
        news_results = await _search_google_news_rss(clean_query, max_results=max_results)
        if news_results:
            return "\n".join(news_results)

    # 2. DDGS search via thread executor (handles TLS fingerprints cleanly)
    try:
        import asyncio
        loop = asyncio.get_running_loop()
        ddgs_results = await loop.run_in_executor(None, _search_ddgs_sync, clean_query, is_news, max_results)
        if ddgs_results:
            return "\n".join(ddgs_results)
    except Exception as e:
        logger.warning(f"DDGS executor failed: {e}")

    # 3. Fallback: Google News RSS for any remaining queries
    if not is_news:
        fallback_news = await _search_google_news_rss(clean_query, max_results=max_results)
        if fallback_news:
            return "\n".join(fallback_news)

    return f"I was unable to retrieve live web results for '{clean_query}' at the moment, sir."
