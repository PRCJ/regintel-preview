import json

import pytest

from eva_score import (
    _parse_llm_json,
    apply_score,
    heuristic_score,
    is_junk_url,
    needs_score,
)
from schema import category_from_score


@pytest.mark.unit
def test_junk_url_news_and_jobs():
    assert is_junk_url("https://mewa.gov.sa/en/news/foo.pdf") is True
    assert is_junk_url("https://sdaia.gov.sa/en/careers/job.pdf") is True
    assert is_junk_url("https://sdaia.gov.sa/en/laws/pdpl.pdf") is False


@pytest.mark.unit
def test_heuristic_law_is_high_or_critical():
    rec = heuristic_score(
        {
            "title": "Personal Data Protection Law",
            "summary": "Binding obligations for controllers of personal data.",
            "document_type": "law",
            "jurisdiction": "Saudi Arabia - SDAIA",
            "url": "https://sdaia.gov.sa/en/laws/pdpl.pdf",
        }
    )
    assert rec["ai_relevance_score"] >= 75
    assert rec["ai_relevance_category"] in {"high", "critical"}
    assert rec["ai_document_type"] in {"LAW", "REGULATION"}
    assert rec["score_method"] == "heuristic"
    assert rec["regulator"]


@pytest.mark.unit
def test_heuristic_brand_kit_not_relevant():
    rec = heuristic_score(
        {
            "title": "Environment Week visual identity guideline",
            "summary": "Brand book and visual identity for partners.",
            "document_type": "guidance",
            "url": "https://mewa.gov.sa/docs/brand.pdf",
        }
    )
    assert rec["ai_relevance_score"] < 25
    assert rec["ai_relevance_category"] == "not_relevant"
    assert rec["ai_status"] == "not_relevant"


@pytest.mark.unit
def test_heuristic_news_url_not_relevant():
    rec = heuristic_score(
        {
            "title": "Workshop announcement",
            "summary": "Join our conference workshop.",
            "document_type": "other",
            "url": "https://mewa.gov.sa/en/news/workshop.pdf",
        }
    )
    assert rec["ai_relevance_category"] == "not_relevant"


@pytest.mark.unit
def test_heuristic_circular_is_high():
    rec = heuristic_score(
        {
            "title": "Regulatory circular on licensing",
            "summary": "Mandatory circular setting compliance procedures for licensed entities.",
            "document_type": "circular",
            "jurisdiction": "Saudi Arabia - SAMA",
            "url": "https://sama.gov.sa/en/circulars/lic.pdf",
        }
    )
    assert rec["ai_relevance_score"] >= 75
    assert rec["ai_relevance_category"] == "high"


@pytest.mark.unit
def test_heuristic_annual_report_capped_low():
    rec = heuristic_score(
        {
            "title": "Annual report 2025",
            "summary": "Annual report of achievements and statistics.",
            "document_type": "report",
            "url": "https://mewa.gov.sa/en/reports/annual.pdf",
        }
    )
    assert rec["ai_relevance_score"] <= 40
    assert rec["ai_relevance_category"] in {"low", "not_relevant"}


@pytest.mark.unit
def test_apply_score_without_llm_writes_fields():
    rec = {"id": "x", "title": "Act", "document_type": "regulation", "summary": "A regulation."}
    out = apply_score(rec, use_llm=False)
    assert out is rec
    assert rec["ai_relevance_score"] is not None
    assert rec["ai_relevance_category"] == category_from_score(rec["ai_relevance_score"])
    assert rec["scored_at"]


@pytest.mark.unit
def test_needs_score_true_until_scored():
    assert needs_score({}) is True
    assert needs_score({"ai_status": "pending"}) is True
    assert needs_score({"ai_status": "analyzed", "ai_relevance_score": 80}) is False


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw",
    [
        '{"relevance_score": 80}',
        "```json\n{\"relevance_score\": 80}\n```",
        "Here you go\n{\"relevance_score\": 80}\nthanks",
    ],
)
def test_parse_llm_json_tolerates_fences(raw):
    data = _parse_llm_json(raw)
    assert data and data["relevance_score"] == 80


@pytest.mark.unit
def test_parse_llm_json_rejects_garbage():
    assert _parse_llm_json("") is None
    assert _parse_llm_json("not json") is None
    assert _parse_llm_json("[1,2]") is None
