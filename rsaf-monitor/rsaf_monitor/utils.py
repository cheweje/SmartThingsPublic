"""
Utility functions shared across the RSAF Monitor.
"""

import hashlib
import logging
import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

logger = logging.getLogger(__name__)


def normalize_url(url: str) -> str:
    """
    Normalise a URL for deduplication purposes.

    Strips tracking parameters, fragments, trailing slashes,
    and lowercases the scheme and host.
    """
    try:
        parsed = urlparse(url)

        # Lowercase scheme and host
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        # Remove www. prefix
        if netloc.startswith("www."):
            netloc = netloc[4:]

        # Remove common tracking parameters
        tracking_params = {
            "utm_source", "utm_medium", "utm_campaign", "utm_term",
            "utm_content", "fbclid", "gclid", "ref", "source",
            "ncid", "sr_share",
        }
        query_params = parse_qs(parsed.query, keep_blank_values=False)
        filtered = {k: v for k, v in query_params.items()
                    if k.lower() not in tracking_params}
        query = urlencode(filtered, doseq=True)

        # Strip fragment
        path = parsed.path.rstrip("/") or "/"

        return urlunparse((scheme, netloc, path, parsed.params, query, ""))
    except Exception:
        return url


def content_hash(text: str) -> str:
    """
    Generate a hash of article content for deduplication.

    Uses a normalised version of the text (lowercased, whitespace collapsed)
    to catch near-identical content even with minor formatting differences.
    """
    # Normalise: lowercase, collapse whitespace, strip punctuation
    normalised = re.sub(r"\s+", " ", text.lower().strip())
    normalised = re.sub(r"[^\w\s]", "", normalised)
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()[:32]


def simhash_text(text: str) -> int:
    """
    Compute a simple SimHash for near-duplicate detection.

    This is a lightweight implementation — not as robust as dedicated
    libraries, but good enough for catching syndicated copies.
    """
    # Tokenise
    words = re.sub(r"[^\w\s]", "", text.lower()).split()
    # Build shingles (3-word)
    shingles = [" ".join(words[i:i+3]) for i in range(len(words) - 2)]

    if not shingles:
        return 0

    # Compute SimHash
    hash_bits = 64
    v = [0] * hash_bits

    for shingle in shingles:
        h = int(hashlib.md5(shingle.encode()).hexdigest(), 16)
        for i in range(hash_bits):
            if h & (1 << i):
                v[i] += 1
            else:
                v[i] -= 1

    fingerprint = 0
    for i in range(hash_bits):
        if v[i] > 0:
            fingerprint |= (1 << i)

    return fingerprint


def hamming_distance(hash1: int, hash2: int) -> int:
    """Count the number of differing bits between two hashes."""
    return bin(hash1 ^ hash2).count("1")


def truncate_text(text: str, max_chars: int = 5000) -> str:
    """Truncate text to a maximum character count, preserving word boundaries."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.8:
        truncated = truncated[:last_space]
    return truncated + "..."


def extract_domain(url: str) -> str:
    """Extract the domain from a URL."""
    try:
        netloc = urlparse(url).netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def setup_logging(log_dir: str, log_level: str = "INFO"):
    """Configure logging for the application."""
    from pathlib import Path
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    log_file = Path(log_dir) / "rsaf_monitor.log"

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ],
    )
