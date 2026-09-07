"""Shared pytest fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "collector"
if str(COLLECTOR) not in sys.path:
    sys.path.insert(0, str(COLLECTOR))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))


@pytest.fixture
def repo_root() -> Path:
    return ROOT


@pytest.fixture
def sample_summaries() -> list[dict]:
    return [
        {
            "id": "law1",
            "title": "Personal Data Protection Law",
            "summary": "This law establishes binding obligations for controllers processing personal data in Saudi Arabia.",
            "document_type": "law",
            "jurisdiction": "Saudi Arabia - SDAIA",
            "url": "https://sdaia.gov.sa/en/laws/pdpl.pdf",
        },
        {
            "id": "brand1",
            "title": "Environment Week 2026 visual identity guideline",
            "summary": "Official visual identity brand book for partners and designers.",
            "document_type": "guidance",
            "jurisdiction": "Saudi Arabia - MEWA",
            "url": "https://mewa.gov.sa/en/media/brand.pdf",
        },
        {
            "id": "news1",
            "title": "Minister visits workshop",
            "summary": "Press release about a conference and workshop.",
            "document_type": "other",
            "jurisdiction": "Saudi Arabia - MEWA",
            "url": "https://mewa.gov.sa/en/news/workshop.pdf",
        },
    ]


@pytest.fixture
def tmp_eva_store(tmp_path, monkeypatch, sample_summaries):
    """Point Eva jsonl + web publish at a temp tree."""
    import eva_summarize

    eva_dir = tmp_path / "data" / "eva"
    web_data = tmp_path / "web" / "data"
    eva_dir.mkdir(parents=True)
    web_data.mkdir(parents=True)
    jsonl = eva_dir / "summaries.jsonl"
    jsonl.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in sample_summaries),
        encoding="utf-8",
    )
    monkeypatch.setattr(eva_summarize, "EVA_DIR", eva_dir)
    monkeypatch.setattr(eva_summarize, "SUMMARIES_JSONL", jsonl)
    monkeypatch.setattr(eva_summarize, "WEB_SUMMARIES", web_data / "eva_summaries.json")
    return {"jsonl": jsonl, "web": web_data / "eva_summaries.json", "meta": web_data / "eva_meta.json"}
