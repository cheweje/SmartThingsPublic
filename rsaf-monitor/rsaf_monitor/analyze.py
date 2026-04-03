"""
LLM analysis layer.

Uses Claude to perform:
1. Relevance confirmation (is this really about RSAF?)
2. Article summarisation
3. Sentiment analysis (lightweight directional)
4. Impact assessment for RSAF communications
5. Daily digest synthesis

All prompts are defined in prompts.py for easy review.
"""

import json
import logging
from typing import Optional

from .prompts import (
    SYSTEM_PROMPT,
    RELEVANCE_CHECK_PROMPT,
    ARTICLE_ANALYSIS_PROMPT,
    DIGEST_SYNTHESIS_PROMPT,
)
from .utils import truncate_text

logger = logging.getLogger(__name__)


class Analyzer:
    """LLM-powered analysis engine."""

    def __init__(self, config):
        """
        Initialise the analyzer with an Anthropic client.

        Args:
            config: LLMConfig object with api_key, model, etc.
        """
        self.config = config
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initialise the Anthropic API client."""
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.config.api_key)
            logger.info(f"Anthropic client initialised (model: {self.config.model})")
        except ImportError:
            logger.error("anthropic package not installed. Run: pip install anthropic")
            raise
        except Exception as e:
            logger.error(f"Failed to initialise Anthropic client: {e}")
            raise

    def _call_llm(self, user_prompt: str) -> str:
        """Make a single LLM API call and return the text response."""
        response = self.client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens_per_request,
            temperature=self.config.temperature,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text

    def check_relevance(self, article) -> dict:
        """
        Check if an article is genuinely about the RSAF.

        Returns dict with: is_relevant, confidence, reason, rsaf_context
        """
        prompt = RELEVANCE_CHECK_PROMPT.format(
            title=article.title,
            source=article.source,
            excerpt=truncate_text(article.excerpt or article.text, 2000),
        )

        try:
            response_text = self._call_llm(prompt)
            result = _parse_json_response(response_text)
            if result:
                return result
        except Exception as e:
            logger.warning(f"Relevance check failed for {article.url}: {e}")

        # Default: mark as relevant with low confidence so it's not lost
        return {
            "is_relevant": True,
            "confidence": "low",
            "reason": "LLM check failed; included by default for manual review",
            "rsaf_context": "unknown",
        }

    def analyze_article(self, article) -> dict:
        """
        Full analysis of a single article: summary, sentiment, impact.

        Returns dict with: summary, sentiment, impact, themes, priority_score
        """
        prompt = ARTICLE_ANALYSIS_PROMPT.format(
            title=article.title,
            source=article.source,
            published=article.published,
            url=article.url,
            text=truncate_text(article.text, 4000),
        )

        try:
            response_text = self._call_llm(prompt)
            result = _parse_json_response(response_text)
            if result:
                return result
        except Exception as e:
            logger.warning(f"Article analysis failed for {article.url}: {e}")

        # Fallback
        return {
            "summary": f"Analysis unavailable. Article from {article.source}: {article.title}",
            "sentiment": {"label": "neutral", "explanation": "Analysis unavailable"},
            "impact": {},
            "themes": [],
            "priority_score": 3,
        }

    def analyze_batch(self, articles: list) -> list[dict]:
        """
        Analyse multiple articles. Calls the LLM per article
        (batching into single prompts risks quality).
        """
        results = []
        for i, article in enumerate(articles):
            logger.info(f"Analysing article {i+1}/{len(articles)}: {article.title[:60]}")
            result = self.analyze_article(article)
            results.append(result)
        return results

    def synthesize_digest(self, articles_data: list[dict]) -> dict:
        """
        Produce the daily digest synthesis from all analysed articles.

        Args:
            articles_data: List of dicts, each containing article info + analysis

        Returns:
            Dict with: executive_summary, items_requiring_attention,
            notable_themes, etc.
        """
        # Prepare a compact JSON representation for the LLM
        compact = []
        for a in articles_data:
            compact.append({
                "title": a.get("title", ""),
                "source": a.get("source", ""),
                "url": a.get("url", ""),
                "summary": a.get("summary", ""),
                "sentiment": a.get("sentiment_label", "neutral"),
                "priority_score": a.get("priority_score", 0),
                "themes": a.get("themes", []),
                "impact": a.get("impact", {}),
            })

        prompt = DIGEST_SYNTHESIS_PROMPT.format(
            articles_json=json.dumps(compact, indent=2)
        )

        try:
            response_text = self._call_llm(prompt)
            result = _parse_json_response(response_text)
            if result:
                return result
        except Exception as e:
            logger.error(f"Digest synthesis failed: {e}")

        # Fallback digest
        return {
            "executive_summary": (
                f"Automated digest generation encountered an error. "
                f"{len(articles_data)} articles were found and analysed individually. "
                f"Please review the item-by-item breakdown below."
            ),
            "items_requiring_attention": [],
            "notable_themes": [],
            "emerging_risks_or_opportunities": [],
            "sentiment_snapshot": {
                "positive_count": 0, "neutral_count": 0,
                "mixed_count": 0, "negative_count": 0,
                "overall_tone": "Unable to assess",
            },
            "recommended_followup": ["Review individual articles manually"],
        }


def _parse_json_response(text: str) -> Optional[dict]:
    """
    Parse a JSON response from the LLM.

    Handles cases where the LLM wraps JSON in markdown code blocks.
    """
    text = text.strip()

    # Strip markdown code block if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

    logger.warning(f"Failed to parse LLM JSON response: {text[:200]}...")
    return None
