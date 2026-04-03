"""
Search and retrieval layer.

Searches multiple sources for RSAF mentions:
- Web search engines (DuckDuckGo free, SerpAPI, Google CSE)
- RSS feeds
- Configurable source list

Designed to be extensible — add new search providers by implementing
a function that returns a list of ArticleStub dicts.
"""

import logging
import time
import feedparser
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ArticleStub:
    """A raw article found during search, before extraction."""
    url: str
    title: str = ""
    source: str = ""
    snippet: str = ""
    published: str = ""
    search_query: str = ""
    found_via: str = ""  # "web_search", "rss", "direct"


def search_all(config, since: Optional[datetime] = None) -> list[ArticleStub]:
    """
    Run all configured search strategies and return combined results.

    Args:
        config: SearchConfig object
        since: Only return results newer than this datetime
    """
    stubs = []

    # 1. Web search
    logger.info("Starting web search...")
    try:
        web_results = _search_web(config, since)
        stubs.extend(web_results)
        logger.info(f"Web search returned {len(web_results)} results")
    except Exception as e:
        logger.error(f"Web search failed: {e}", exc_info=True)

    # 2. RSS feeds
    logger.info("Checking RSS feeds...")
    try:
        rss_results = _search_rss(config, since)
        stubs.extend(rss_results)
        logger.info(f"RSS feeds returned {len(rss_results)} results")
    except Exception as e:
        logger.error(f"RSS search failed: {e}", exc_info=True)

    # Deduplicate by URL (basic — more sophisticated dedup happens later)
    seen_urls = set()
    unique = []
    for stub in stubs:
        if stub.url not in seen_urls:
            seen_urls.add(stub.url)
            unique.append(stub)

    logger.info(f"Total unique stubs after search: {len(unique)}")

    # Enforce max articles per run
    if len(unique) > config.max_articles_per_run:
        logger.info(f"Trimming to {config.max_articles_per_run} articles")
        unique = unique[:config.max_articles_per_run]

    return unique


def _search_web(config, since: Optional[datetime]) -> list[ArticleStub]:
    """Search the web using the configured search provider."""
    provider = config.search_provider.lower()

    if provider == "serpapi" and config.serpapi_key:
        return _search_serpapi(config, since)
    elif provider == "google_cse" and config.google_cse_api_key:
        return _search_google_cse(config, since)
    else:
        # Default: DuckDuckGo (free, no API key needed)
        return _search_duckduckgo(config, since)


def _search_duckduckgo(config, since: Optional[datetime]) -> list[ArticleStub]:
    """
    Search using DuckDuckGo HTML.

    This is a basic approach using the duckduckgo-search library.
    It's free but has rate limits and may not return date-filtered results.
    """
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.error("duckduckgo-search not installed. Run: pip install duckduckgo-search")
        return []

    stubs = []
    ddgs = DDGS()

    for query in config.keywords:
        try:
            logger.debug(f"DuckDuckGo search: {query}")
            results = ddgs.text(
                query,
                max_results=config.max_results_per_query,
                timelimit="d",  # Past day
            )

            for r in results:
                stubs.append(ArticleStub(
                    url=r.get("href", r.get("link", "")),
                    title=r.get("title", ""),
                    snippet=r.get("body", r.get("snippet", "")),
                    source=r.get("source", ""),
                    search_query=query,
                    found_via="duckduckgo",
                ))

            # Be polite — wait between queries
            time.sleep(config.request_delay_seconds)

        except Exception as e:
            logger.warning(f"DuckDuckGo query failed for '{query}': {e}")
            time.sleep(config.request_delay_seconds)
            continue

    return stubs


def _search_serpapi(config, since: Optional[datetime]) -> list[ArticleStub]:
    """Search using SerpAPI (requires API key)."""
    stubs = []
    base_url = "https://serpapi.com/search"

    for query in config.keywords:
        try:
            logger.debug(f"SerpAPI search: {query}")
            params = {
                "q": query,
                "api_key": config.serpapi_key,
                "engine": "google",
                "num": config.max_results_per_query,
                "tbs": "qdr:d",  # Past day
            }
            resp = requests.get(base_url, params=params,
                                timeout=config.request_timeout_seconds)
            resp.raise_for_status()
            data = resp.json()

            for r in data.get("organic_results", []):
                stubs.append(ArticleStub(
                    url=r.get("link", ""),
                    title=r.get("title", ""),
                    snippet=r.get("snippet", ""),
                    source=r.get("source", ""),
                    search_query=query,
                    found_via="serpapi",
                ))

            time.sleep(config.request_delay_seconds)

        except Exception as e:
            logger.warning(f"SerpAPI query failed for '{query}': {e}")
            continue

    return stubs


def _search_google_cse(config, since: Optional[datetime]) -> list[ArticleStub]:
    """Search using Google Custom Search Engine (requires API key + CX)."""
    stubs = []
    base_url = "https://www.googleapis.com/customsearch/v1"

    # Date filter
    date_restrict = "d1"  # Past day

    for query in config.keywords:
        try:
            logger.debug(f"Google CSE search: {query}")
            params = {
                "q": query,
                "key": config.google_cse_api_key,
                "cx": config.google_cse_cx,
                "num": min(config.max_results_per_query, 10),
                "dateRestrict": date_restrict,
            }
            resp = requests.get(base_url, params=params,
                                timeout=config.request_timeout_seconds)
            resp.raise_for_status()
            data = resp.json()

            for r in data.get("items", []):
                stubs.append(ArticleStub(
                    url=r.get("link", ""),
                    title=r.get("title", ""),
                    snippet=r.get("snippet", ""),
                    source=r.get("displayLink", ""),
                    search_query=query,
                    found_via="google_cse",
                ))

            time.sleep(config.request_delay_seconds)

        except Exception as e:
            logger.warning(f"Google CSE query failed for '{query}': {e}")
            continue

    return stubs


def _search_rss(config, since: Optional[datetime]) -> list[ArticleStub]:
    """Check RSS feeds for RSAF mentions."""
    stubs = []
    rsaf_terms = [
        "rsaf", "republic of singapore air force", "singapore air force",
        "mindef", "singapore fighter", "singapore aircraft",
    ]

    for feed_url in config.rss_feeds:
        try:
            logger.debug(f"Checking RSS feed: {feed_url}")
            feed = feedparser.parse(feed_url)

            if feed.bozo and not feed.entries:
                logger.warning(f"RSS feed error for {feed_url}: {feed.bozo_exception}")
                continue

            for entry in feed.entries:
                # Check if entry mentions RSAF
                text = (
                    (entry.get("title", "") + " " +
                     entry.get("summary", "") + " " +
                     entry.get("description", ""))
                    .lower()
                )

                if any(term in text for term in rsaf_terms):
                    # Parse published date
                    pub_date = ""
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        pub_dt = datetime(*entry.published_parsed[:6],
                                          tzinfo=timezone.utc)
                        # Skip if older than our lookback window
                        if since and pub_dt < since:
                            continue
                        pub_date = pub_dt.isoformat()

                    stubs.append(ArticleStub(
                        url=entry.get("link", ""),
                        title=entry.get("title", ""),
                        snippet=entry.get("summary", "")[:500],
                        published=pub_date,
                        search_query="rss_feed",
                        found_via=f"rss:{feed_url}",
                    ))

            time.sleep(1)  # Polite delay between feeds

        except Exception as e:
            logger.warning(f"RSS feed failed for {feed_url}: {e}")
            continue

    return stubs
