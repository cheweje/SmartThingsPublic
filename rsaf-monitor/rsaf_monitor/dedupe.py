"""
Deduplication layer.

Removes duplicate and near-duplicate articles using:
1. Exact URL matching (after normalisation)
2. Content hash matching (exact text duplicates)
3. SimHash matching (near-duplicate detection for syndicated copies)

When duplicates are found, keeps the most authoritative source.
"""

import logging
from .utils import normalize_url, content_hash, simhash_text, hamming_distance
from .storage import Storage

logger = logging.getLogger(__name__)

# SimHash hamming distance threshold for near-duplicate detection.
# Lower = stricter. 3-5 is typical for news article dedup.
SIMHASH_THRESHOLD = 5

# Source authority ranking (higher = more authoritative)
SOURCE_AUTHORITY = {
    "mindef.gov.sg": 100,
    "air.mindef.gov.sg": 100,
    "gov.sg": 90,
    "channelnewsasia.com": 80,
    "straitstimes.com": 80,
    "reuters.com": 75,
    "bbc.com": 75,
    "todayonline.com": 70,
    "janes.com": 70,
    "defensenews.com": 65,
    "flightglobal.com": 65,
    "thediplomat.com": 60,
}


def deduplicate(articles: list, storage: Storage) -> list:
    """
    Remove duplicate and near-duplicate articles.

    Steps:
    1. Normalise URLs and compute content hashes
    2. Check against previously processed articles in storage
    3. Check for duplicates within the current batch
    4. For near-duplicates, keep the most authoritative source

    Returns:
        List of unique articles (duplicates are marked, not removed,
        so we can still log what was filtered).
    """
    logger.info(f"Deduplicating {len(articles)} articles...")

    # Step 1: Compute hashes
    for article in articles:
        article.url_normalized = normalize_url(article.url)
        if article.text:
            article.content_hash = content_hash(article.text)
            article.simhash = simhash_text(article.text)

    # Step 2: Check against storage (previously processed)
    new_articles = []
    for article in articles:
        if storage.url_exists(article.url):
            logger.debug(f"URL already processed: {article.url}")
            article.is_duplicate = True
            continue
        if storage.normalized_url_exists(article.url_normalized):
            logger.debug(f"Normalised URL already processed: {article.url}")
            article.is_duplicate = True
            continue
        if article.content_hash and storage.content_hash_exists(article.content_hash):
            logger.debug(f"Content hash already processed: {article.url}")
            article.is_duplicate = True
            continue
        new_articles.append(article)

    logger.info(f"{len(new_articles)} articles after storage dedup "
                f"({len(articles) - len(new_articles)} duplicates of previous runs)")

    # Step 3: Deduplicate within the current batch
    unique = []
    for article in new_articles:
        is_dup = False

        for existing in unique:
            # Exact content hash match
            if (article.content_hash and existing.content_hash and
                    article.content_hash == existing.content_hash):
                is_dup = True
                # Keep more authoritative source
                if _authority_score(article) > _authority_score(existing):
                    unique.remove(existing)
                    unique.append(article)
                    logger.debug(f"Replaced {existing.url} with more "
                                 f"authoritative {article.url}")
                else:
                    logger.debug(f"Duplicate content: {article.url} "
                                 f"(keeping {existing.url})")
                break

            # SimHash near-duplicate
            if (article.simhash and existing.simhash and
                    hamming_distance(article.simhash, existing.simhash)
                    <= SIMHASH_THRESHOLD):
                is_dup = True
                if _authority_score(article) > _authority_score(existing):
                    unique.remove(existing)
                    unique.append(article)
                    logger.debug(f"Near-dup replaced: {existing.url} -> {article.url}")
                else:
                    logger.debug(f"Near-duplicate: {article.url} "
                                 f"(keeping {existing.url})")
                break

        if not is_dup:
            unique.append(article)

    logger.info(f"{len(unique)} unique articles after batch dedup "
                f"({len(new_articles) - len(unique)} batch duplicates)")

    return unique


def _authority_score(article) -> int:
    """Score an article's source authority. Higher = more authoritative."""
    domain = article.source.lower()
    # Check exact match first
    if domain in SOURCE_AUTHORITY:
        return SOURCE_AUTHORITY[domain]
    # Check suffix matches
    for auth_domain, score in SOURCE_AUTHORITY.items():
        if domain.endswith(auth_domain):
            return score
    return 10  # Default low score for unknown sources
