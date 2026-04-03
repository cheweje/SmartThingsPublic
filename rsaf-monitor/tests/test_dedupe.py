"""Tests for the deduplication layer."""

import pytest
from rsaf_monitor.utils import normalize_url, content_hash, simhash_text, hamming_distance


class TestNormalizeUrl:
    def test_strips_tracking_params(self):
        url = "https://www.example.com/article?id=1&utm_source=twitter&utm_medium=social"
        result = normalize_url(url)
        assert "utm_source" not in result
        assert "utm_medium" not in result
        assert "id=1" in result

    def test_removes_www(self):
        url = "https://www.example.com/article"
        result = normalize_url(url)
        assert "www." not in result
        assert "example.com" in result

    def test_lowercases_host(self):
        url = "https://WWW.Example.COM/article"
        result = normalize_url(url)
        assert "example.com" in result

    def test_strips_trailing_slash(self):
        url1 = normalize_url("https://example.com/article/")
        url2 = normalize_url("https://example.com/article")
        assert url1 == url2

    def test_strips_fragment(self):
        url = "https://example.com/article#section-2"
        result = normalize_url(url)
        assert "#" not in result


class TestContentHash:
    def test_identical_content(self):
        text1 = "The RSAF conducted an exercise today."
        text2 = "The RSAF conducted an exercise today."
        assert content_hash(text1) == content_hash(text2)

    def test_whitespace_insensitive(self):
        text1 = "The  RSAF   conducted  an exercise."
        text2 = "The RSAF conducted an exercise."
        assert content_hash(text1) == content_hash(text2)

    def test_case_insensitive(self):
        text1 = "The RSAF conducted an exercise."
        text2 = "the rsaf conducted an exercise."
        assert content_hash(text1) == content_hash(text2)

    def test_different_content(self):
        text1 = "The RSAF conducted an exercise."
        text2 = "The Navy held a parade yesterday."
        assert content_hash(text1) != content_hash(text2)


class TestSimHash:
    def test_similar_texts_close_distance(self):
        text1 = ("The Republic of Singapore Air Force conducted a major "
                 "bilateral exercise with the Royal Australian Air Force "
                 "in Queensland this week.")
        text2 = ("The Republic of Singapore Air Force held a major "
                 "bilateral exercise with the Royal Australian Air Force "
                 "in Queensland this week.")
        h1 = simhash_text(text1)
        h2 = simhash_text(text2)
        dist = hamming_distance(h1, h2)
        # Near-duplicates should have small hamming distance
        assert dist <= 10

    def test_different_texts_far_distance(self):
        text1 = ("The Republic of Singapore Air Force conducted a major "
                 "bilateral exercise with the Royal Australian Air Force.")
        text2 = ("Global stock markets fell sharply today as investors "
                 "reacted to inflation data from the United States.")
        h1 = simhash_text(text1)
        h2 = simhash_text(text2)
        dist = hamming_distance(h1, h2)
        # Different texts should have large hamming distance
        assert dist > 10
