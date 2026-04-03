"""
RSAF Daily Web Monitoring Agent — Main entry point.

Orchestrates the full pipeline:
1. Search for new RSAF mentions
2. Extract article content
3. Deduplicate
4. Filter for relevance (LLM)
5. Analyse each article (LLM)
6. Synthesise daily digest (LLM)
7. Generate reports
8. Send email briefing

Usage:
    python -m rsaf_monitor.main              # Normal run
    python -m rsaf_monitor.main --dry-run    # Skip email
    python -m rsaf_monitor.main --test       # Short lookback, sample data
    python -m rsaf_monitor.main --mock       # Use mock data only
"""

import argparse
import json
import logging
import sys
import uuid
from datetime import datetime, timezone, timedelta

from .config import load_config
from .storage import Storage
from .search import search_all
from .extract import extract_articles
from .dedupe import deduplicate
from .analyze import Analyzer
from .report import generate_reports
from .deliver import send_email
from .utils import setup_logging

logger = logging.getLogger(__name__)


def main():
    """Run the RSAF monitoring pipeline."""
    args = _parse_args()

    # Load config
    config = load_config(args.config)

    # Apply CLI overrides
    if args.dry_run:
        config.dry_run = True
    if args.test:
        config.test_mode = True
    if args.mock:
        config.test_mode = True

    # Set up logging
    setup_logging(config.log_dir, config.log_level)
    logger.info("=" * 60)
    logger.info("RSAF Monitor starting")
    logger.info(f"  Dry run: {config.dry_run}")
    logger.info(f"  Test mode: {config.test_mode}")
    logger.info(f"  Search provider: {config.search.search_provider}")
    logger.info("=" * 60)

    # Initialise storage
    storage = Storage(config.db_path)
    run_id = str(uuid.uuid4())[:8]
    storage.start_run(run_id)

    try:
        if args.mock:
            # Use mock data instead of real search
            articles_data = _run_mock_pipeline(config)
        else:
            articles_data = _run_pipeline(config, storage, run_id)

        # Generate reports
        if articles_data:
            logger.info(f"Generating reports for {len(articles_data)} articles...")
            digest = _get_digest(config, articles_data)
            reports = generate_reports(digest, articles_data, config)

            # Send email
            email_sent = False
            if not config.dry_run:
                email_sent = send_email(
                    reports["email_subject"],
                    reports["email_body"],
                    config.email,
                )
                if not email_sent:
                    logger.warning("Email send failed. Report saved locally.")
            else:
                logger.info("Dry run — email not sent")

            # Complete run
            storage.complete_run(
                run_id,
                status="success",
                articles_found=len(articles_data),
                articles_relevant=len(articles_data),
                articles_sent=len(articles_data),
                email_sent=email_sent,
            )

            logger.info(f"Run {run_id} complete. {len(articles_data)} articles processed.")
            logger.info(f"Reports: {reports.get('files', {})}")

        else:
            logger.info("No new relevant articles found.")
            # Still generate an empty report
            digest = {
                "executive_summary": "No new RSAF mentions found in the monitoring period.",
                "items_requiring_attention": [],
                "notable_themes": [],
                "emerging_risks_or_opportunities": [],
                "sentiment_snapshot": {
                    "positive_count": 0, "neutral_count": 0,
                    "mixed_count": 0, "negative_count": 0,
                    "overall_tone": "No coverage to assess.",
                },
                "recommended_followup": [],
            }
            reports = generate_reports(digest, [], config)

            if not config.dry_run:
                send_email(reports["email_subject"], reports["email_body"],
                           config.email)

            storage.complete_run(run_id, status="success",
                                 articles_found=0)

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        storage.complete_run(run_id, status="error",
                             error_message=str(e))
        sys.exit(1)
    finally:
        storage.close()


def _run_pipeline(config, storage, run_id) -> list[dict]:
    """Run the full search-extract-analyze pipeline."""

    # Determine lookback window
    last_run = storage.get_last_successful_run_time()
    if config.test_mode:
        since = datetime.now(timezone.utc) - timedelta(
            hours=config.test_lookback_hours)
    elif last_run:
        since = last_run
    else:
        since = datetime.now(timezone.utc) - timedelta(
            hours=config.search.lookback_hours)

    logger.info(f"Searching for articles since {since.isoformat()}")

    # Step 1: Search
    stubs = search_all(config.search, since)
    logger.info(f"Search found {len(stubs)} raw results")

    if not stubs:
        return []

    # Step 2: Extract content
    articles = extract_articles(stubs, config.search)
    logger.info(f"Extracted content from {len(articles)} articles")

    if not articles:
        return []

    # Step 3: Deduplicate
    articles = deduplicate(articles, storage)
    logger.info(f"{len(articles)} unique articles after dedup")

    if not articles:
        return []

    # Step 4: Relevance filter (LLM)
    analyzer = Analyzer(config.llm)
    relevant_articles = []

    for article in articles:
        logger.info(f"Checking relevance: {article.title[:60]}")
        result = analyzer.check_relevance(article)
        article.is_relevant = result.get("is_relevant", False)
        article.relevance_reason = result.get("reason", "")
        article.match_reason = result.get("rsaf_context", "")

        if article.is_relevant:
            relevant_articles.append(article)
        else:
            logger.info(f"  Filtered out: {result.get('reason', 'Not relevant')}")

    logger.info(f"{len(relevant_articles)} relevant articles after LLM filter")

    if not relevant_articles:
        return []

    # Step 5: Analyse each article (LLM)
    articles_data = []
    for article in relevant_articles:
        analysis = analyzer.analyze_article(article)

        # Merge article data with analysis
        article_dict = {
            "url": article.url,
            "title": article.title,
            "source": article.source,
            "author": article.author,
            "published": article.published,
            "excerpt": article.excerpt,
            "match_reason": article.match_reason,
            "summary": analysis.get("summary", ""),
            "sentiment_label": analysis.get("sentiment", {}).get("label", "neutral"),
            "sentiment_explanation": analysis.get("sentiment", {}).get("explanation", ""),
            "impact": analysis.get("impact", {}),
            "themes": analysis.get("themes", []),
            "priority_score": analysis.get("priority_score", 3),
            "analysis_json": json.dumps(analysis),
        }
        articles_data.append(article_dict)

        # Save to storage
        storage.save_article({
            **article_dict,
            "url_normalized": article.url_normalized,
            "content_hash": article.content_hash,
            "is_relevant": True,
            "is_duplicate": False,
        }, run_id)

    return articles_data


def _get_digest(config, articles_data: list[dict]) -> dict:
    """Generate the digest synthesis."""
    try:
        analyzer = Analyzer(config.llm)
        return analyzer.synthesize_digest(articles_data)
    except Exception as e:
        logger.error(f"Digest synthesis failed: {e}")
        # Return a basic fallback digest
        return {
            "executive_summary": (
                f"Found {len(articles_data)} new RSAF mentions. "
                f"Automated synthesis unavailable — see individual items below."
            ),
            "items_requiring_attention": [],
            "notable_themes": [],
            "emerging_risks_or_opportunities": [],
            "sentiment_snapshot": {
                "positive_count": sum(
                    1 for a in articles_data
                    if a.get("sentiment_label") == "positive"),
                "neutral_count": sum(
                    1 for a in articles_data
                    if a.get("sentiment_label") == "neutral"),
                "mixed_count": sum(
                    1 for a in articles_data
                    if a.get("sentiment_label") == "mixed"),
                "negative_count": sum(
                    1 for a in articles_data
                    if a.get("sentiment_label") == "negative"),
                "overall_tone": "See individual assessments",
            },
            "recommended_followup": [],
        }


def _run_mock_pipeline(config) -> list[dict]:
    """Run with mock data for testing the report/email flow."""
    logger.info("Running in MOCK mode with sample data")
    return [
        {
            "url": "https://example.com/rsaf-exercise-2026",
            "title": "RSAF Conducts Major Exercise With RAAF",
            "source": "channelnewsasia.com",
            "author": "Jane Tan",
            "published": "2026-04-02T08:00:00+08:00",
            "excerpt": "The Republic of Singapore Air Force conducted a bilateral exercise...",
            "match_reason": "Direct coverage of RSAF bilateral military exercise",
            "summary": "The RSAF and Royal Australian Air Force completed Exercise Wallaby 2026, a two-week bilateral training exercise in Queensland. Both air forces practised air combat manoeuvres and joint operations.",
            "sentiment_label": "positive",
            "sentiment_explanation": "Positive framing of international defence cooperation.",
            "impact": {
                "reputational": {"level": "low", "reason": "Routine positive coverage."},
                "media_interest": {"level": "medium", "reason": "Defence media likely to pick up."},
                "public_concern": {"level": "low", "reason": "Standard military exercise."},
                "operational_sensitivity": {"level": "low", "reason": "Public exercise information."},
                "stakeholder_sensitivity": {"level": "low", "reason": "Routine bilateral activity."},
                "follow_up_recommended": False,
                "follow_up_note": "None needed",
            },
            "themes": ["bilateral exercises", "Australia partnership"],
            "priority_score": 5,
            "analysis_json": "{}",
        },
        {
            "url": "https://example.com/rsaf-f35-discussion",
            "title": "Singapore's F-35 Acquisition: Progress and Timeline",
            "source": "janes.com",
            "author": "Mike Chen",
            "published": "2026-04-02T14:00:00+08:00",
            "excerpt": "Singapore's acquisition of F-35B aircraft continues...",
            "match_reason": "Coverage of RSAF equipment acquisition programme",
            "summary": "Jane's reports on the timeline for Singapore's F-35B deliveries, noting the RSAF is on track to receive its first operational aircraft by late 2026. The article discusses training programmes and infrastructure preparation at Paya Lebar Air Base.",
            "sentiment_label": "neutral",
            "sentiment_explanation": "Factual reporting on procurement timeline.",
            "impact": {
                "reputational": {"level": "medium", "reason": "High-profile procurement attracts attention."},
                "media_interest": {"level": "high", "reason": "F-35 stories generate broad media interest."},
                "public_concern": {"level": "low", "reason": "No negative framing."},
                "operational_sensitivity": {"level": "medium", "reason": "Acquisition details may attract scrutiny."},
                "stakeholder_sensitivity": {"level": "medium", "reason": "Parliament and defence community interest."},
                "follow_up_recommended": True,
                "follow_up_note": "Monitor for follow-up coverage and verify timeline accuracy.",
            },
            "themes": ["F-35 acquisition", "defence procurement"],
            "priority_score": 7,
            "analysis_json": "{}",
        },
        {
            "url": "https://example.com/rsaf-noise-complaint",
            "title": "Residents Near Tengah Airbase Report Increased Aircraft Noise",
            "source": "mothership.sg",
            "author": "",
            "published": "2026-04-02T18:30:00+08:00",
            "excerpt": "Residents in the Jurong West area reported increased noise levels...",
            "match_reason": "Public complaint related to RSAF operations",
            "summary": "Several residents near Tengah Air Base posted on community forums about increased aircraft noise over the past week. The article includes social media posts and notes that MINDEF has not yet commented.",
            "sentiment_label": "negative",
            "sentiment_explanation": "Negative public sentiment due to noise impact on residents.",
            "impact": {
                "reputational": {"level": "medium", "reason": "Public complaints can gain traction on social media."},
                "media_interest": {"level": "medium", "reason": "Human interest angle could attract mainstream coverage."},
                "public_concern": {"level": "high", "reason": "Direct impact on residents' quality of life."},
                "operational_sensitivity": {"level": "low", "reason": "Routine flight operations."},
                "stakeholder_sensitivity": {"level": "medium", "reason": "MPs and town councils may be asked to respond."},
                "follow_up_recommended": True,
                "follow_up_note": "Monitor social media sentiment. Consider preparing holding statement if queries arise.",
            },
            "themes": ["noise complaints", "community relations"],
            "priority_score": 8,
            "analysis_json": "{}",
        },
    ]


def _parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="RSAF Daily Web Monitoring Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m rsaf_monitor.main                  # Full run
  python -m rsaf_monitor.main --dry-run        # No email
  python -m rsaf_monitor.main --test           # Short lookback
  python -m rsaf_monitor.main --mock           # Mock data only
  python -m rsaf_monitor.main --mock --dry-run # Full test, no email
        """,
    )
    parser.add_argument("--config", "-c", default=None,
                        help="Path to config.yaml (default: config.yaml in project root)")
    parser.add_argument("--dry-run", "-d", action="store_true",
                        help="Run everything except email delivery")
    parser.add_argument("--test", "-t", action="store_true",
                        help="Test mode: short lookback window")
    parser.add_argument("--mock", "-m", action="store_true",
                        help="Use mock sample data instead of real search")
    return parser.parse_args()


if __name__ == "__main__":
    main()
