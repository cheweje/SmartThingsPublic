"""
Persistent storage using SQLite.

Tracks:
- Processed article URLs and content hashes (for deduplication)
- Run history (last successful run time, status)
- Send status for each digest
"""

import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class Storage:
    """SQLite-backed storage for the RSAF monitor."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        logger.info(f"Storage initialised at {db_path}")

    def _init_schema(self):
        """Create tables if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                url_normalized TEXT,
                content_hash TEXT,
                title TEXT,
                source TEXT,
                author TEXT,
                published TEXT,
                discovered_at TEXT NOT NULL,
                run_id TEXT,
                is_relevant INTEGER DEFAULT 0,
                is_duplicate INTEGER DEFAULT 0,
                analysis_json TEXT,
                priority_score REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT UNIQUE NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT DEFAULT 'running',
                articles_found INTEGER DEFAULT 0,
                articles_relevant INTEGER DEFAULT 0,
                articles_sent INTEGER DEFAULT 0,
                email_sent INTEGER DEFAULT 0,
                error_message TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url);
            CREATE INDEX IF NOT EXISTS idx_articles_hash ON articles(content_hash);
            CREATE INDEX IF NOT EXISTS idx_articles_normalized ON articles(url_normalized);
            CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at);
        """)
        self.conn.commit()

    def get_last_successful_run_time(self) -> Optional[datetime]:
        """Get the timestamp of the last successful run."""
        row = self.conn.execute(
            "SELECT completed_at FROM runs WHERE status = 'success' "
            "ORDER BY completed_at DESC LIMIT 1"
        ).fetchone()
        if row and row["completed_at"]:
            return datetime.fromisoformat(row["completed_at"])
        return None

    def url_exists(self, url: str) -> bool:
        """Check if a URL has already been processed."""
        row = self.conn.execute(
            "SELECT 1 FROM articles WHERE url = ? LIMIT 1", (url,)
        ).fetchone()
        return row is not None

    def normalized_url_exists(self, normalized_url: str) -> bool:
        """Check if a normalised URL variant has been processed."""
        row = self.conn.execute(
            "SELECT 1 FROM articles WHERE url_normalized = ? LIMIT 1",
            (normalized_url,)
        ).fetchone()
        return row is not None

    def content_hash_exists(self, content_hash: str) -> bool:
        """Check if content with this hash has been processed."""
        row = self.conn.execute(
            "SELECT 1 FROM articles WHERE content_hash = ? LIMIT 1",
            (content_hash,)
        ).fetchone()
        return row is not None

    def save_article(self, article: dict, run_id: str):
        """Save an article record."""
        now = datetime.now(timezone.utc).isoformat()
        try:
            self.conn.execute("""
                INSERT OR IGNORE INTO articles
                (url, url_normalized, content_hash, title, source, author,
                 published, discovered_at, run_id, is_relevant, is_duplicate,
                 analysis_json, priority_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article.get("url", ""),
                article.get("url_normalized", ""),
                article.get("content_hash", ""),
                article.get("title", ""),
                article.get("source", ""),
                article.get("author", ""),
                article.get("published", ""),
                now,
                run_id,
                1 if article.get("is_relevant") else 0,
                1 if article.get("is_duplicate") else 0,
                article.get("analysis_json", ""),
                article.get("priority_score", 0),
            ))
            self.conn.commit()
        except sqlite3.IntegrityError:
            logger.debug(f"Article already in DB: {article.get('url')}")

    def start_run(self, run_id: str):
        """Record the start of a new run."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO runs (run_id, started_at) VALUES (?, ?)",
            (run_id, now)
        )
        self.conn.commit()

    def complete_run(self, run_id: str, status: str = "success",
                     articles_found: int = 0, articles_relevant: int = 0,
                     articles_sent: int = 0, email_sent: bool = False,
                     error_message: str = ""):
        """Record the completion of a run."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute("""
            UPDATE runs SET
                completed_at = ?,
                status = ?,
                articles_found = ?,
                articles_relevant = ?,
                articles_sent = ?,
                email_sent = ?,
                error_message = ?
            WHERE run_id = ?
        """, (now, status, articles_found, articles_relevant,
              articles_sent, 1 if email_sent else 0, error_message, run_id))
        self.conn.commit()

    def close(self):
        """Close the database connection."""
        self.conn.close()
