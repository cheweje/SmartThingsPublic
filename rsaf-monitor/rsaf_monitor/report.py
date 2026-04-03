"""
Report generation layer.

Generates the morning briefing in multiple formats:
- Plain text email
- Markdown report
- JSON for automation

Uses Jinja2 templates where available, with built-in fallback formatting.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_reports(digest: dict, articles: list, config) -> dict:
    """
    Generate reports in all formats.

    Args:
        digest: Synthesised digest from the LLM
        articles: List of analysed article dicts
        config: AppConfig object

    Returns:
        Dict with keys: 'email_subject', 'email_body', 'markdown', 'json_data'
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%d %b %Y")

    # Subject line
    high_priority = sum(1 for a in articles if a.get("priority_score", 0) >= 7)
    subject = f"{config.email.subject_prefix}, {date_str}"

    # Generate each format
    email_body = _generate_email(digest, articles, date_str, high_priority)
    markdown = _generate_markdown(digest, articles, date_str, high_priority)
    json_data = _generate_json(digest, articles, date_str)

    # Save reports to disk
    output_dir = Path(config.output_dir)
    date_file = now.strftime("%Y-%m-%d")

    md_path = output_dir / f"rsaf_digest_{date_file}.md"
    json_path = output_dir / f"rsaf_digest_{date_file}.json"
    txt_path = output_dir / f"rsaf_digest_{date_file}.txt"

    md_path.write_text(markdown, encoding="utf-8")
    json_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False),
                         encoding="utf-8")
    txt_path.write_text(email_body, encoding="utf-8")

    logger.info(f"Reports saved to {output_dir}")

    return {
        "email_subject": subject,
        "email_body": email_body,
        "markdown": markdown,
        "json_data": json_data,
        "files": {
            "markdown": str(md_path),
            "json": str(json_path),
            "text": str(txt_path),
        },
    }


def _generate_email(digest: dict, articles: list, date_str: str,
                     high_priority: int) -> str:
    """Generate plain text email body, optimised for mobile reading."""
    lines = []

    # Header
    lines.append(f"RSAF DAILY WEB DIGEST — {date_str}")
    lines.append("=" * 50)
    lines.append("")

    # Quick stats
    lines.append(f"New mentions found: {len(articles)}")
    lines.append(f"High-priority items: {high_priority}")
    lines.append("")

    # Executive summary
    lines.append("EXECUTIVE SUMMARY")
    lines.append("-" * 30)
    lines.append(digest.get("executive_summary", "No summary available."))
    lines.append("")

    # Items requiring attention
    attention = digest.get("items_requiring_attention", [])
    if attention:
        lines.append("ITEMS REQUIRING ATTENTION")
        lines.append("-" * 30)
        for i, item in enumerate(attention, 1):
            lines.append(f"{i}. {item.get('title', 'Untitled')}")
            lines.append(f"   Source: {item.get('source', 'Unknown')}")
            lines.append(f"   {item.get('why_attention_needed', '')}")
            lines.append(f"   Link: {item.get('url', '')}")
            lines.append("")

    # Item-by-item breakdown
    if articles:
        lines.append("COVERAGE BREAKDOWN")
        lines.append("-" * 30)
        # Sort by priority
        sorted_articles = sorted(articles,
                                 key=lambda a: a.get("priority_score", 0),
                                 reverse=True)
        for i, a in enumerate(sorted_articles, 1):
            sentiment = a.get("sentiment_label", "neutral")
            priority = a.get("priority_score", 0)
            lines.append(f"{i}. [{sentiment.upper()}] {a.get('title', 'Untitled')}")
            lines.append(f"   Source: {a.get('source', 'Unknown')} | "
                         f"Priority: {priority}/10")
            lines.append(f"   {a.get('summary', 'No summary.')}")
            lines.append(f"   Link: {a.get('url', '')}")
            lines.append("")

    # Sentiment snapshot
    sentiment = digest.get("sentiment_snapshot", {})
    if sentiment:
        lines.append("SENTIMENT SNAPSHOT")
        lines.append("-" * 30)
        lines.append(f"  Positive: {sentiment.get('positive_count', 0)}")
        lines.append(f"  Neutral:  {sentiment.get('neutral_count', 0)}")
        lines.append(f"  Mixed:    {sentiment.get('mixed_count', 0)}")
        lines.append(f"  Negative: {sentiment.get('negative_count', 0)}")
        lines.append(f"  Overall:  {sentiment.get('overall_tone', 'N/A')}")
        lines.append("")

    # Notable themes
    themes = digest.get("notable_themes", [])
    if themes:
        lines.append("NOTABLE THEMES")
        lines.append("-" * 30)
        for t in themes:
            lines.append(f"  • {t.get('theme', '')}: {t.get('description', '')}")
        lines.append("")

    # Risks and opportunities
    risks = digest.get("emerging_risks_or_opportunities", [])
    if risks:
        lines.append("EMERGING RISKS / OPPORTUNITIES")
        lines.append("-" * 30)
        for r in risks:
            label = r.get("type", "note").upper()
            lines.append(f"  [{label}] {r.get('description', '')}")
            lines.append(f"    Action: {r.get('recommended_action', 'None')}")
        lines.append("")

    # Recommended follow-up
    followup = digest.get("recommended_followup", [])
    if followup:
        lines.append("RECOMMENDED FOLLOW-UP")
        lines.append("-" * 30)
        for f in followup:
            lines.append(f"  • {f}")
        lines.append("")

    # Footer
    lines.append("=" * 50)
    lines.append("Generated by RSAF Monitor | Automated daily briefing")
    lines.append("Note: Sentiment and impact assessments are lightweight")
    lines.append("directional indicators, not definitive analysis.")

    return "\n".join(lines)


def _generate_markdown(digest: dict, articles: list, date_str: str,
                       high_priority: int) -> str:
    """Generate Markdown report."""
    lines = []

    lines.append(f"# RSAF Daily Web Digest — {date_str}")
    lines.append("")
    lines.append(f"**New mentions:** {len(articles)} | "
                 f"**High-priority:** {high_priority}")
    lines.append("")

    lines.append("## Executive Summary")
    lines.append(digest.get("executive_summary", "No summary available."))
    lines.append("")

    attention = digest.get("items_requiring_attention", [])
    if attention:
        lines.append("## Items Requiring Attention")
        for item in attention:
            lines.append(f"### {item.get('title', 'Untitled')}")
            lines.append(f"**Source:** {item.get('source', 'Unknown')} | "
                         f"[Link]({item.get('url', '')})")
            lines.append(item.get("why_attention_needed", ""))
            lines.append("")

    if articles:
        lines.append("## Coverage Breakdown")
        sorted_articles = sorted(articles,
                                 key=lambda a: a.get("priority_score", 0),
                                 reverse=True)
        for a in sorted_articles:
            sentiment = a.get("sentiment_label", "neutral")
            priority = a.get("priority_score", 0)
            lines.append(f"### {a.get('title', 'Untitled')}")
            lines.append(f"**Source:** {a.get('source', 'Unknown')} | "
                         f"**Sentiment:** {sentiment} | "
                         f"**Priority:** {priority}/10 | "
                         f"[Link]({a.get('url', '')})")
            lines.append("")
            lines.append(a.get("summary", "No summary."))
            lines.append("")

    sentiment = digest.get("sentiment_snapshot", {})
    if sentiment:
        lines.append("## Sentiment Snapshot")
        lines.append(f"| Label | Count |")
        lines.append(f"|-------|-------|")
        lines.append(f"| Positive | {sentiment.get('positive_count', 0)} |")
        lines.append(f"| Neutral | {sentiment.get('neutral_count', 0)} |")
        lines.append(f"| Mixed | {sentiment.get('mixed_count', 0)} |")
        lines.append(f"| Negative | {sentiment.get('negative_count', 0)} |")
        lines.append("")
        lines.append(f"**Overall:** {sentiment.get('overall_tone', 'N/A')}")
        lines.append("")

    themes = digest.get("notable_themes", [])
    if themes:
        lines.append("## Notable Themes")
        for t in themes:
            lines.append(f"- **{t.get('theme', '')}**: {t.get('description', '')}")
        lines.append("")

    risks = digest.get("emerging_risks_or_opportunities", [])
    if risks:
        lines.append("## Emerging Risks / Opportunities")
        for r in risks:
            label = r.get("type", "note").upper()
            lines.append(f"- **[{label}]** {r.get('description', '')}")
            lines.append(f"  - *Action:* {r.get('recommended_action', 'None')}")
        lines.append("")

    followup = digest.get("recommended_followup", [])
    if followup:
        lines.append("## Recommended Follow-Up")
        for f in followup:
            lines.append(f"- {f}")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by RSAF Monitor. Sentiment and impact assessments "
                 "are lightweight directional indicators.*")

    return "\n".join(lines)


def _generate_json(digest: dict, articles: list, date_str: str) -> dict:
    """Generate structured JSON output."""
    return {
        "date": date_str,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_articles": len(articles),
        "digest": digest,
        "articles": articles,
    }
