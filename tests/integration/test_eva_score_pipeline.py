import json

import pytest

from eva_score import apply_score, score_store
from eva_summarize import load_existing, publish_web


@pytest.mark.integration
def test_score_store_heuristic_and_publish(tmp_eva_store):
    stats = score_store(limit=0, only_unscored=True, use_llm=False, publish=True)
    assert stats["scored"] == 3
    assert stats["heuristic"] == 3
    existing = load_existing()
    assert all(existing[i].get("ai_relevance_score") is not None for i in existing)
    web = json.loads(tmp_eva_store["web"].read_text(encoding="utf-8"))
    assert len(web) == 3
    assert all("ai_relevance_category" in row for row in web)
    law = next(r for r in web if r["id"] == "law1")
    brand = next(r for r in web if r["id"] == "brand1")
    assert law["ai_relevance_score"] >= 75
    assert brand["ai_relevance_category"] == "not_relevant"
    meta = json.loads(tmp_eva_store["meta"].read_text(encoding="utf-8"))
    assert meta["scored"] == 3
    assert "score_bands" in meta


@pytest.mark.integration
def test_score_store_skips_already_scored(tmp_eva_store):
    score_store(use_llm=False, publish=False)
    stats = score_store(only_unscored=True, use_llm=False, publish=False)
    assert stats["scored"] == 0
    assert stats["skipped"] == 3


@pytest.mark.integration
def test_publish_web_omits_empty_score_fields(tmp_eva_store):
    recs = load_existing()
    recs["law1"]["ai_relevance_score"] = 92
    recs["law1"]["ai_relevance_category"] = "critical"
    recs["law1"]["ai_status"] = "analyzed"
    recs["law1"]["ai_relevance_reason"] = "Binding law"
    publish_web(recs)
    web = json.loads(tmp_eva_store["web"].read_text(encoding="utf-8"))
    law = next(r for r in web if r["id"] == "law1")
    assert law["ai_relevance_score"] == 92
    news = next(r for r in web if r["id"] == "news1")
    assert "ai_relevance_score" not in news
