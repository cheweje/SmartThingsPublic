"""
Content extraction layer.

Downloads article pages and extracts clean text, metadata,
and other relevant information.

Uses newspaper3k as the primary extractor with BeautifulSoup fallback.
"""

import logging
import time
import requests
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Article:
    """A fully extracted article."""
    url: str
    url_normalized: str = ""
    title: str = ""
    source: str = ""
    author: str = ""
    published: str = ""
    text: str = ""
    excerpt: str = ""
    content_hash: str = ""
    simhash: int = 0
    search_query: str = ""
    found_via: str = ""
    match_reason: str = ""

    # Analysis fields (populated later)
    is_relevant: bool = False
    is_duplicate: bool = False
    relevance_reason: str = ""
    summary: str = ""
    sentiment_label: str = ""
    sentiment_explanation: str = ""
    impact: dict = field(default_factory=dict)
    themes: list = field(default_factory=list)
    priority_score: float = 0.0
    analysis_json: str = ""


def extract_articles(stubs, config) -> list[Article]:
    """
    Download and extract content from a list of ArticleStubs.

    Args:
        stubs: List of ArticleStub objects from the search layer
        config: SearchConfig object

    Returns:
        List of Article objects with extracted content
    """
    articles = []

    for stub in stubs:
        try:
            article = _extract_single(stub, config)
            if article and article.text:
                articles.append(article)
            else:
                logger.debug(f"No content extracted from {stub.url}")
        except Exception as e:
            logger.warning(f"Extraction failed for {stub.url}: {e}")
            continue

        # Polite delay between requests
        time.sleep(config.request_delay_seconds)

    logger.info(f"Extracted {len(articles)} articles with content")
    return articles


def _extract_single(stub, config) -> Optional[Article]:
    """Extract content from a single article."""
    url = stub.url
    if not url:
        return None

    # Try newspaper3k first
    article = _extract_with_newspaper(url, config)

    # Fall back to requests + BeautifulSoup
    if not article or not article.text:
        article = _extract_with_bs4(url, config)

    if article:
        article.search_query = stub.search_query
        article.found_via = stub.found_via
        # Use stub data as fallback
        if not article.title and stub.title:
            article.title = stub.title
        if not article.published and stub.published:
            article.published = stub.published
        if stub.snippet:
            article.excerpt = stub.snippet
        if not article.excerpt and article.text:
            article.excerpt = article.text[:500]

    return article


def _extract_with_newspaper(url: str, config) -> Optional[Article]:
    """Extract article using newspaper3k."""
    try:
        from newspaper import Article as NArticle, Config as NConfig

        nconfig = NConfig()
        nconfig.browser_user_agent = config.user_agent
        nconfig.request_timeout = config.request_timeout_seconds
        nconfig.fetch_images = False
        nconfig.memoize_articles = False

        n_article = NArticle(url, config=nconfig)
        n_article.download()
        n_article.parse()

        if not n_article.text:
            return None

        return Article(
            url=url,
            title=n_article.title or "",
            author=", ".join(n_article.authors) if n_article.authors else "",
            published=n_article.publish_date.isoformat() if n_article.publish_date else "",
            text=n_article.text,
            excerpt=n_article.text[:500] if n_article.text else "",
            source=_domain_from_url(url),
        )

    except ImportError:
        logger.debug("newspaper3k not available, using fallback")
        return None
    except Exception as e:
        logger.debug(f"newspaper3k failed for {url}: {e}")
        return None


def _extract_with_bs4(url: str, config) -> Optional[Article]:
    """Extract article using requests + BeautifulSoup (fallback)."""
    try:
        from bs4 import BeautifulSoup

        headers = {"User-Agent": config.user_agent}
        resp = requests.get(url, headers=headers,
                            timeout=config.request_timeout_seconds)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract title
        title = ""
        if soup.title:
            title = soup.title.string or ""

        # Extract text from article-like elements
        text = ""
        # Try common article containers
        for selector in ["article", "[role='main']", ".article-body",
                         ".story-body", ".post-content", "main"]:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(separator="\n", strip=True)
                break

        # Fallback: get all paragraph text
        if not text:
            paragraphs = soup.find_all("p")
            text = "\n".join(p.get_text(strip=True) for p in paragraphs)

        # Extract author from meta tags
        author = ""
        author_meta = soup.find("meta", attrs={"name": "author"})
        if author_meta:
            author = author_meta.get("content", "")

        # Extract published date from meta tags
        published = ""
        for prop in ["article:published_time", "datePublished",
                     "date", "DC.date.issued"]:
            date_meta = soup.find("meta", attrs={"property": prop}) or \
                        soup.find("meta", attrs={"name": prop})
            if date_meta:
                published = date_meta.get("content", "")
                break

        if not text:
            return None

        return Article(
            url=url,
            title=title.strip(),
            author=author,
            published=published,
            text=text,
            excerpt=text[:500],
            source=_domain_from_url(url),
        )

    except Exception as e:
        logger.debug(f"BS4 extraction failed for {url}: {e}")
        return None


def _domain_from_url(url: str) -> str:
    """Extract domain name from URL."""
    from urllib.parse import urlparse
    try:
        netloc = urlparse(url).netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""
