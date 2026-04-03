"""
Configuration management for RSAF Monitor.

Loads settings from environment variables and config.yaml.
Environment variables take precedence over config file values.
"""

import os
import yaml
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "rsaf_monitor.db"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports"
DEFAULT_LOG_DIR = PROJECT_ROOT / "logs"


@dataclass
class SearchConfig:
    """Search-related settings."""
    keywords: list[str] = field(default_factory=lambda: [
        '"Republic of Singapore Air Force"',
        '"RSAF Singapore"',
        '"RSAF air force"',
        '"RSAF" Singapore',
        '"Singapore fighter jet" RSAF',
        '"RSAF exercise"',
        '"RSAF aircraft"',
        '"RSAF deployment"',
        '"RSAF accident"',
        '"RSAF complaint"',
        '"RSAF noise"',
        '"RSAF training"',
        '"RSAF" site:gov.sg',
        '"RSAF" site:mindef.gov.sg',
        '"RSAF" site:air.mindef.gov.sg',
    ])
    max_results_per_query: int = 20
    max_articles_per_run: int = 50
    lookback_hours: int = 26  # Slightly more than 24h to avoid gaps
    request_delay_seconds: float = 2.0
    user_agent: str = (
        "RSAFMonitorBot/1.0 (+https://github.com/rsaf-monitor; "
        "media-monitoring-research)"
    )
    respect_robots_txt: bool = True
    request_timeout_seconds: int = 30

    # Search provider: "serpapi", "google_cse", or "duckduckgo"
    search_provider: str = "duckduckgo"
    serpapi_key: str = ""
    google_cse_api_key: str = ""
    google_cse_cx: str = ""

    # RSS feeds to check
    rss_feeds: list[str] = field(default_factory=lambda: [
        "https://www.mindef.gov.sg/web/portal/mindef/news-and-events/latest-releases/rss",
        "https://www.channelnewsasia.com/rssfeeds/8395986",  # CNA Singapore
        "https://www.straitstimes.com/news/singapore/rss.xml",
        "https://www.janes.com/feeds/news",
        "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml",
        "https://thediplomat.com/feed/",
    ])

    # Source management
    preferred_sources: list[str] = field(default_factory=lambda: [
        "mindef.gov.sg", "channelnewsasia.com", "straitstimes.com",
        "todayonline.com", "mothership.sg", "janes.com", "defensenews.com",
        "flightglobal.com", "reuters.com", "bbc.com",
    ])
    blocked_sources: list[str] = field(default_factory=list)


@dataclass
class LLMConfig:
    """LLM / Claude API settings."""
    api_key: str = ""
    model: str = "claude-sonnet-4-20250514"
    max_tokens_per_request: int = 4096
    temperature: float = 0.2  # Low for deterministic output
    batch_size: int = 5  # Articles per LLM batch call


@dataclass
class EmailConfig:
    """Email delivery settings."""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    use_tls: bool = True
    sender_email: str = ""
    recipient_email: str = ""
    subject_prefix: str = "RSAF Daily Web Digest"


@dataclass
class AppConfig:
    """Top-level application configuration."""
    search: SearchConfig = field(default_factory=SearchConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    db_path: str = str(DEFAULT_DB_PATH)
    output_dir: str = str(DEFAULT_OUTPUT_DIR)
    log_dir: str = str(DEFAULT_LOG_DIR)
    log_level: str = "INFO"
    dry_run: bool = False
    test_mode: bool = False
    test_lookback_hours: int = 4


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """
    Load configuration from config.yaml, then override with environment variables.

    Environment variables use the prefix RSAF_ and are uppercase.
    Examples:
        RSAF_RECIPIENT_EMAIL=me@example.com
        RSAF_ANTHROPIC_API_KEY=sk-ant-...
        RSAF_SMTP_HOST=smtp.gmail.com
    """
    config = AppConfig()

    # Load YAML config file if it exists
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if path.exists():
        logger.info(f"Loading config from {path}")
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        _apply_yaml(config, data)
    else:
        logger.info(f"No config file at {path}, using defaults + env vars")

    # Override with environment variables
    _apply_env(config)

    # Ensure directories exist
    Path(config.db_path).parent.mkdir(parents=True, exist_ok=True)
    Path(config.output_dir).mkdir(parents=True, exist_ok=True)
    Path(config.log_dir).mkdir(parents=True, exist_ok=True)

    return config


def _apply_yaml(config: AppConfig, data: dict):
    """Apply YAML config values to the config object."""
    search = data.get("search", {})
    if search:
        for key, val in search.items():
            if hasattr(config.search, key):
                setattr(config.search, key, val)

    llm = data.get("llm", {})
    if llm:
        for key, val in llm.items():
            if hasattr(config.llm, key):
                setattr(config.llm, key, val)

    email = data.get("email", {})
    if email:
        for key, val in email.items():
            if hasattr(config.email, key):
                setattr(config.email, key, val)

    for key in ("db_path", "output_dir", "log_dir", "log_level", "dry_run",
                "test_mode", "test_lookback_hours"):
        if key in data:
            setattr(config, key, data[key])


def _apply_env(config: AppConfig):
    """Override config with environment variables."""
    env = os.environ

    # LLM
    config.llm.api_key = env.get("RSAF_ANTHROPIC_API_KEY",
                                  env.get("ANTHROPIC_API_KEY",
                                           config.llm.api_key))
    config.llm.model = env.get("RSAF_LLM_MODEL", config.llm.model)

    # Email
    config.email.smtp_host = env.get("RSAF_SMTP_HOST", config.email.smtp_host)
    config.email.smtp_port = int(env.get("RSAF_SMTP_PORT",
                                          str(config.email.smtp_port)))
    config.email.smtp_username = env.get("RSAF_SMTP_USERNAME",
                                          config.email.smtp_username)
    config.email.smtp_password = env.get("RSAF_SMTP_PASSWORD",
                                          config.email.smtp_password)
    config.email.sender_email = env.get("RSAF_SENDER_EMAIL",
                                         config.email.sender_email)
    config.email.recipient_email = env.get("RSAF_RECIPIENT_EMAIL",
                                            config.email.recipient_email)

    # Search
    config.search.serpapi_key = env.get("RSAF_SERPAPI_KEY",
                                         config.search.serpapi_key)
    config.search.google_cse_api_key = env.get("RSAF_GOOGLE_CSE_API_KEY",
                                                 config.search.google_cse_api_key)
    config.search.google_cse_cx = env.get("RSAF_GOOGLE_CSE_CX",
                                            config.search.google_cse_cx)
    config.search.search_provider = env.get("RSAF_SEARCH_PROVIDER",
                                              config.search.search_provider)

    # App-level
    config.db_path = env.get("RSAF_DB_PATH", config.db_path)
    config.output_dir = env.get("RSAF_OUTPUT_DIR", config.output_dir)
    config.log_level = env.get("RSAF_LOG_LEVEL", config.log_level)
    config.dry_run = env.get("RSAF_DRY_RUN", "").lower() in ("1", "true", "yes") or config.dry_run
    config.test_mode = env.get("RSAF_TEST_MODE", "").lower() in ("1", "true", "yes") or config.test_mode
