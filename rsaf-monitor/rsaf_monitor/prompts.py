"""
LLM prompts used by the RSAF Monitor.

All prompts are stored here for easy review and modification.
These are used with Claude for relevance checking, summarisation,
sentiment analysis, and impact assessment.
"""

# ---------------------------------------------------------------------------
# System prompt shared across all analysis calls
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are an expert media analyst supporting a communications
team at the Republic of Singapore Air Force (RSAF). Your role is to analyse
web content and provide concise, accurate, professional assessments.

Rules:
- Be factual and precise. Do not speculate beyond what the text supports.
- If you are uncertain, say so explicitly.
- Keep all outputs concise — this is for busy professionals scanning on mobile.
- Use neutral, professional tone. No hype, no exaggeration.
- Sentiment analysis is lightweight and directional — do not overclaim accuracy.
- Impact assessments are preliminary guidance, not definitive judgements."""

# ---------------------------------------------------------------------------
# Relevance check: Is this article actually about the RSAF?
# ---------------------------------------------------------------------------
RELEVANCE_CHECK_PROMPT = """Analyse the following article and determine whether
it is genuinely about the Republic of Singapore Air Force (RSAF).

The article matched a keyword search, but "RSAF" can refer to other things
(e.g., Royal Saudi Air Force, other acronyms, or unrelated contexts).

Article title: {title}
Article source: {source}
Article excerpt:
---
{excerpt}
---

Respond in this exact JSON format:
{{
  "is_relevant": true or false,
  "confidence": "high" or "medium" or "low",
  "reason": "One sentence explaining your decision",
  "rsaf_context": "Brief note on what aspect of RSAF this covers, or 'not applicable'"
}}

Only mark as relevant if the Republic of Singapore Air Force is clearly
a subject of the article, not just mentioned in passing."""

# ---------------------------------------------------------------------------
# Article summary + sentiment + impact (batched)
# ---------------------------------------------------------------------------
ARTICLE_ANALYSIS_PROMPT = """Analyse the following article about the Republic
of Singapore Air Force (RSAF).

Title: {title}
Source: {source}
Published: {published}
URL: {url}
Full text:
---
{text}
---

Provide your analysis in this exact JSON format:
{{
  "summary": "2-3 sentence summary of the article, focusing on what matters for RSAF communications",

  "sentiment": {{
    "label": "positive" or "neutral" or "mixed" or "negative",
    "explanation": "One sentence explaining the sentiment label. Be honest about uncertainty."
  }},

  "impact": {{
    "reputational": {{
      "level": "low" or "medium" or "high",
      "reason": "1-2 sentences"
    }},
    "media_interest": {{
      "level": "low" or "medium" or "high",
      "reason": "1-2 sentences"
    }},
    "public_concern": {{
      "level": "low" or "medium" or "high",
      "reason": "1-2 sentences"
    }},
    "operational_sensitivity": {{
      "level": "low" or "medium" or "high",
      "reason": "1-2 sentences"
    }},
    "stakeholder_sensitivity": {{
      "level": "low" or "medium" or "high",
      "reason": "1-2 sentences"
    }},
    "follow_up_recommended": true or false,
    "follow_up_note": "Brief note on what to watch, or 'None needed'"
  }},

  "themes": ["theme1", "theme2"],
  "priority_score": 1-10
}}

IMPORTANT:
- Sentiment labels are lightweight directional assessments, not deep analysis.
- Impact assessments are preliminary guidance for a communications professional.
- Priority score: 1 = routine mention, 10 = urgent attention needed.
- If the text is too short or unclear, say so honestly in the summary."""

# ---------------------------------------------------------------------------
# Daily digest synthesis
# ---------------------------------------------------------------------------
DIGEST_SYNTHESIS_PROMPT = """You are preparing a daily RSAF web monitoring
briefing for a senior communications professional. Below are the analysed
articles from the past 24 hours.

Articles (JSON array):
---
{articles_json}
---

Produce the daily digest in this exact JSON format:
{{
  "executive_summary": "3-5 sentence overview of today's RSAF web landscape. What matters most? Any concerns?",

  "items_requiring_attention": [
    {{
      "title": "Article title",
      "source": "Source name",
      "url": "URL",
      "why_attention_needed": "1-2 sentences"
    }}
  ],

  "notable_themes": [
    {{
      "theme": "Theme name",
      "description": "1-2 sentences",
      "articles_count": N
    }}
  ],

  "emerging_risks_or_opportunities": [
    {{
      "type": "risk" or "opportunity",
      "description": "1-2 sentences",
      "recommended_action": "Brief suggestion"
    }}
  ],

  "sentiment_snapshot": {{
    "positive_count": N,
    "neutral_count": N,
    "mixed_count": N,
    "negative_count": N,
    "overall_tone": "One sentence on the day's overall tone"
  }},

  "recommended_followup": [
    "Action item 1",
    "Action item 2"
  ]
}}

Rules:
- Be concise. This will be read on a phone.
- If there are no articles, say so clearly.
- If nothing requires attention, say that explicitly.
- Do not invent concerns that the data does not support.
- Limit items_requiring_attention to the top 3-5 most important."""
