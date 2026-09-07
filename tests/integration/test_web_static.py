import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"


@pytest.mark.integration
def test_index_has_product_nav():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    for view in ("home", "documents", "horizon", "pipeline"):
        assert f'data-view="{view}"' in html
    assert 'id="viewDocuments"' in html
    assert 'id="docDrawer"' in html
    assert 'id="evaWidget"' in html


@pytest.mark.integration
def test_eva_summaries_scored():
    meta = json.loads((WEB / "data" / "eva_meta.json").read_text(encoding="utf-8"))
    assert meta["scored"] > 0
    assert meta["count"] == meta["total_indexed"]
    bands = meta.get("score_bands") or {}
    assert "high" in bands or "critical" in bands
    rows = json.loads((WEB / "data" / "eva_summaries.json").read_text(encoding="utf-8"))
    scored = [r for r in rows if r.get("ai_relevance_score") is not None]
    assert len(scored) == meta["scored"]
    high = [r for r in scored if float(r["ai_relevance_score"]) >= 75]
    assert high, "Documents default filter needs some high/critical rows"


@pytest.mark.integration
def test_catalog_and_updates_present():
    pdfs = json.loads((WEB / "data" / "pdfs_catalog.json").read_text(encoding="utf-8"))
    assert isinstance(pdfs, list) and pdfs
    updates = json.loads((WEB / "data" / "updates.json").read_text(encoding="utf-8"))
    assert isinstance(updates, list)
