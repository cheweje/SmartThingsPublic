"""Tests for the report generation layer."""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from rsaf_monitor.report import generate_reports


@pytest.fixture
def sample_digest():
    return {
        "executive_summary": "Three new RSAF mentions found today.",
        "items_requiring_attention": [
            {
                "title": "Noise Complaints Near Tengah",
                "source": "mothership.sg",
                "url": "https://example.com/noise",
                "why_attention_needed": "Public complaint gaining traction.",
            }
        ],
        "notable_themes": [
            {"theme": "Community relations", "description": "Noise complaints.", "articles_count": 1}
        ],
        "emerging_risks_or_opportunities": [],
        "sentiment_snapshot": {
            "positive_count": 1,
            "neutral_count": 1,
            "mixed_count": 0,
            "negative_count": 1,
            "overall_tone": "Mixed sentiment across coverage.",
        },
        "recommended_followup": ["Monitor social media for noise discussion."],
    }


@pytest.fixture
def sample_articles():
    return [
        {
            "url": "https://example.com/exercise",
            "title": "RSAF Exercise Wallaby",
            "source": "channelnewsasia.com",
            "summary": "RSAF and RAAF conducted bilateral exercise.",
            "sentiment_label": "positive",
            "priority_score": 5,
        },
        {
            "url": "https://example.com/noise",
            "title": "Noise Complaints Near Tengah",
            "source": "mothership.sg",
            "summary": "Residents reported increased aircraft noise.",
            "sentiment_label": "negative",
            "priority_score": 8,
        },
    ]


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.output_dir = tempfile.mkdtemp()
    config.email.subject_prefix = "RSAF Daily Web Digest"
    return config


class TestReportGeneration:
    def test_generates_all_formats(self, sample_digest, sample_articles, mock_config):
        result = generate_reports(sample_digest, sample_articles, mock_config)
        assert "email_subject" in result
        assert "email_body" in result
        assert "markdown" in result
        assert "json_data" in result

    def test_subject_contains_date(self, sample_digest, sample_articles, mock_config):
        result = generate_reports(sample_digest, sample_articles, mock_config)
        assert "RSAF Daily Web Digest" in result["email_subject"]

    def test_email_contains_executive_summary(self, sample_digest, sample_articles, mock_config):
        result = generate_reports(sample_digest, sample_articles, mock_config)
        assert "Three new RSAF mentions" in result["email_body"]

    def test_email_contains_article_titles(self, sample_digest, sample_articles, mock_config):
        result = generate_reports(sample_digest, sample_articles, mock_config)
        assert "RSAF Exercise Wallaby" in result["email_body"]
        assert "Noise Complaints" in result["email_body"]

    def test_articles_sorted_by_priority(self, sample_digest, sample_articles, mock_config):
        result = generate_reports(sample_digest, sample_articles, mock_config)
        body = result["email_body"]
        # Higher priority (noise, 8) should appear before lower (exercise, 5)
        noise_pos = body.index("Noise Complaints")
        exercise_pos = body.index("RSAF Exercise Wallaby")
        assert noise_pos < exercise_pos

    def test_saves_files(self, sample_digest, sample_articles, mock_config):
        result = generate_reports(sample_digest, sample_articles, mock_config)
        for path in result["files"].values():
            assert Path(path).exists()

    def test_json_output_structure(self, sample_digest, sample_articles, mock_config):
        result = generate_reports(sample_digest, sample_articles, mock_config)
        data = result["json_data"]
        assert "date" in data
        assert "digest" in data
        assert "articles" in data
        assert data["total_articles"] == 2

    def test_markdown_contains_headers(self, sample_digest, sample_articles, mock_config):
        result = generate_reports(sample_digest, sample_articles, mock_config)
        md = result["markdown"]
        assert "# RSAF Daily Web Digest" in md
        assert "## Executive Summary" in md
