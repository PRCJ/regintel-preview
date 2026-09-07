#!/usr/bin/env python3
"""Score Eva summaries for regulatory relevance (CompliGuard bands).

Heuristic is always available. LLM scoring uses XAI_API_KEY when set.

  .venv/bin/python collector/eva_score.py --all --heuristic
  .venv/bin/python collector/eva_score.py --limit 50 --only-unscored
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collector"))

from schema import (  # type: ignore
    SCORE_WEB_FIELDS,
    category_from_score,
    clamp_score,
)

try:
    from eva_llm import chat_text, get_client  # type: ignore
except ImportError:
    chat_text = None  # type: ignore
    get_client = lambda: None  # type: ignore

try:
    from pdf_relevance import regulatory_score  # type: ignore
except ImportError:
    def regulatory_score(url="", title="", text=""):  # type: ignore
        return 0

try:
    from eva_summarize import load_existing, publish_web, rewrite_jsonl  # type: ignore
except ImportError:
    load_existing = None  # type: ignore
    publish_web = None  # type: ignore
    rewrite_jsonl = None  # type: ignore


ANALYSIS_PROMPT = """You are the regulatory-document analysis engine for Horizon Scanner (CompliGuard AI).

You are analyzing a document discovered on an official regulator website.

Your task is to determine whether this document is relevant to regulatory compliance.

DO NOT assume that every document published by a regulator is a law or regulatory requirement.

Analyze the actual document content, NOT the filename.

Classify the document into exactly one of:
LAW, REGULATION, GUIDANCE, POLICY, STANDARD, CIRCULAR, DECISION, RULE, BYLAW, CODE, DIRECTIVE, NOTICE, PROCEDURE, FRAMEWORK, OTHER, NOT_RELEVANT

Assign a relevance score from 0 to 100 using this methodology:

90-100 (Critical): Directly creates or establishes binding legal/regulatory requirements or obligations.
  Examples: Laws, Regulations, Mandatory standards, Binding decisions, Regulatory directives.

75-89 (High): Strong regulatory/compliance relevance but primarily provides implementation requirements, guidance or procedures.
  Examples: Regulatory guidance, Mandatory procedures, Official regulatory circulars, Compliance frameworks.

50-74 (Medium): Useful regulatory context or expectations but limited direct compliance obligations.
  Examples: Policies, Non-binding guidance, Consultation documents, Regulatory frameworks.
  IMPORTANT: HTML pages that do NOT contain the exact full text of the law itself, but only provide extracts, excerpts, summaries, or partial quotations of the law, MUST be scored in this band (50-74) regardless of how important the underlying law is — the score reflects the page's content, not the underlying legislation.

25-49 (Low): Related to the regulator but limited compliance relevance.
  Examples: Annual reports, Statistics, Research, Strategy documents.
  IMPORTANT — apply these rules strictly:
  - Any policy that does NOT impose obligations on external regulated entities, but merely describes the internal policies, internal procedures, or internal governance of the authority or government itself, MUST be scored in this band (25-49).
  - Any report that does NOT impose obligations on entities, but instead describes, boasts about, or discusses what the government or authority has achieved, accomplished, plans to do, or intends to do, MUST be scored in this band (25-49). This includes achievement reports, progress reports, strategic vision documents, press-style accomplishment summaries, and forward-looking intent statements.

0-24 (Not relevant): Not materially relevant to regulatory compliance.
  Examples: Press releases, News, Job advertisements, Events, Speeches, General website content, Procurement notices unrelated to compliance.

Generate:
1. is_relevant: true if relevance_score >= 25, false otherwise
2. relevance_score: 0-100
3. relevance_category: "critical" (90-100), "high" (75-89), "medium" (50-74), "low" (25-49), "not_relevant" (0-24)
4. document_type: One of the taxonomy values above
5. english_title: A concise English title for the document
6. english_summary: A comprehensive English summary of approximately 150 words describing what the document is about
7. relevance_reason: Brief explanation of why this score was assigned
8. confidence: 0-1 confidence in the analysis
9. publication_date: YYYY-MM-DD if found in the text, otherwise null
10. effective_date: YYYY-MM-DD if found in the text, otherwise null
11. jurisdiction: The jurisdiction/region if identifiable from the content
12. regulator: The PRIMARY (main) issuing authority only — a single ministry/authority name. Do NOT combine multiple authorities here. Use the full formal name (e.g. "Saudi Data and Artificial Intelligence Authority (SDAIA)", not "SDAIA" or "Saudi Data & AI Authority").
13. sub_ministries: Array of any co-regulators or sub-ministries associated with the document (empty array if none). The main authority goes in "regulator", not here. Use full formal names.
14. tags: 3-5 relevant keyword tags

Do not invent information that is not supported by the document.

Return ONLY valid JSON."""

DOC_TYPE_MAP = {
    "LAW": "law",
    "REGULATION": "regulation",
    "GUIDANCE": "guidance",
    "POLICY": "other",
    "STANDARD": "standard",
    "CIRCULAR": "circular",
    "DECISION": "decision",
    "RULE": "rule",
    "BYLAW": "regulation",
    "CODE": "standard",
    "DIRECTIVE": "directive",
    "NOTICE": "notice",
    "PROCEDURE": "guidance",
    "FRAMEWORK": "other",
    "OTHER": "other",
    "NOT_RELEVANT": "other",
}

JUNK_URL_RE = re.compile(
    r"(?:/news(?:/|$)|/press|/career|/jobs?(?:/|$)|/tender|/event|/blog|/speech|"
    r"/gallery|/webinar|/workshop|/media-kit|/newsletter)",
    re.I,
)
JUNK_TEXT_RE = re.compile(
    r"\b(?:visual identity|brand book|brand guideline|environment week|"
    r"workshop|webinar|conference agenda|media kit|newsletter|"
    r"press release|job advertisement|vacancy|infographic|brochure|"
    r"tourism|promotional)\b",
    re.I,
)
CRITICAL_TYPE = {"law", "act", "regulation", "decree", "statute"}
HIGH_TYPE = {"circular", "directive", "rule", "standard", "guidance", "decision"}
MEDIUM_TYPE = {"notice", "policy", "framework", "consultation", "procedure"}
LOW_TYPE = {"report", "form", "other", "unknown"}

AUTHORITY_FROM_JURISDICTION = {
    "SDAIA": "Saudi Data and Artificial Intelligence Authority (SDAIA)",
    "MOJ": "Ministry of Justice (MOJ)",
    "MOMAH": "Ministry of Municipalities and Housing (MOMAH)",
    "ZATCA": "Zakat, Tax and Customs Authority (ZATCA)",
    "SASO": "Saudi Standards, Metrology and Quality Organization (SASO)",
    "GOSI": "General Organization for Social Insurance (GOSI)",
    "MEWA": "Ministry of Environment, Water and Agriculture (MEWA)",
    "SAMA": "Saudi Central Bank (SAMA)",
    "CMA": "Capital Market Authority (CMA)",
    "MOF": "Ministry of Finance (MOF)",
    "MOI": "Ministry of Interior (MOI)",
    "GAC": "General Authority for Competition (GAC)",
    "TGA": "Transport General Authority (TGA)",
    "MC": "Ministry of Commerce (MC)",
}


def _blob(rec: dict) -> str:
    parts = [
        rec.get("title") or "",
        rec.get("title_en") or "",
        rec.get("summary") or "",
        rec.get("summary_en") or "",
        " ".join(rec.get("key_points") or []),
        rec.get("url") or rec.get("open_url") or "",
    ]
    return " ".join(str(p) for p in parts)


def _regulator_from_rec(rec: dict) -> str:
    if rec.get("regulator"):
        return str(rec["regulator"])
    jur = str(rec.get("jurisdiction") or "")
    for code, name in AUTHORITY_FROM_JURISDICTION.items():
        if re.search(rf"\b{re.escape(code)}\b", jur, re.I) or jur.endswith(code):
            return name
    return jur.replace("Saudi Arabia - ", "").strip()


def is_junk_url(url: str) -> bool:
    if not url:
        return False
    path = urlparse(url).path or ""
    return bool(JUNK_URL_RE.search(path))


def heuristic_score(rec: dict) -> dict[str, Any]:
    url = rec.get("url") or rec.get("open_url") or ""
    title = rec.get("title") or rec.get("title_en") or ""
    summary = rec.get("summary") or rec.get("summary_en") or ""
    blob = _blob(rec)
    dtype = str(rec.get("document_type") or "other").strip().lower()

    if is_junk_url(url) or JUNK_TEXT_RE.search(blob):
        score = 12
        reason = "Looks like news, marketing, events, or brand material rather than a binding rule."
        ai_type = "NOT_RELEVANT"
    else:
        keep = regulatory_score(url=url, title=title, text=summary[:4000])
        if dtype in CRITICAL_TYPE:
            score = 92 if keep >= 15 else 80
            ai_type = "LAW" if dtype in {"law", "act", "statute"} else "REGULATION"
            reason = "Document type is a law/regulation that typically creates obligations."
        elif dtype in HIGH_TYPE:
            score = 82 if keep >= 15 else 76
            ai_type = dtype.upper() if dtype in DOC_TYPE_MAP else "GUIDANCE"
            reason = "Implementation guidance, circular, or standard with compliance relevance."
        elif dtype in MEDIUM_TYPE:
            score = 62 if keep >= 15 else 52
            ai_type = dtype.upper() if dtype != "consultation" else "OTHER"
            reason = "Useful regulatory context but limited direct obligations."
        elif keep >= 40:
            score = 78
            ai_type = "GUIDANCE"
            reason = "Strong legal/regulatory keywords in title or summary."
        elif keep >= 15:
            score = 55
            ai_type = "OTHER"
            reason = "Some regulatory signals; treat as medium context."
        else:
            score = 18
            ai_type = "NOT_RELEVANT"
            reason = "No clear legal or compliance obligation in the available text."

        if re.search(r"\b(?:annual report|statistics|strategy vision|achievement)\b", blob, re.I):
            score = min(score, 40)
            reason = "Reads as a report or internal strategy, not an external obligation."
            if score < 25:
                ai_type = "NOT_RELEVANT"

    score = clamp_score(score)
    category = category_from_score(score)
    english_title = (rec.get("title_en") or rec.get("title") or "").strip()
    english_summary = (rec.get("summary_en") or rec.get("summary") or "").strip()
    if len(english_summary) > 1200:
        english_summary = english_summary[:1197] + "…"
    return {
        "ai_relevance_score": score,
        "ai_relevance_category": category,
        "ai_document_type": ai_type,
        "ai_status": "not_relevant" if category == "not_relevant" else "analyzed",
        "ai_confidence": 0.45,
        "ai_relevance_reason": reason,
        "english_title": english_title,
        "english_summary": english_summary,
        "regulator": _regulator_from_rec(rec),
        "sub_ministries": rec.get("sub_ministries") or [],
        "text_extraction_status": "extracted" if (summary or title) else "pending",
        "score_method": "heuristic",
        "scored_at": datetime.now(timezone.utc).isoformat(),
    }


def _parse_llm_json(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return obj if isinstance(obj, dict) else None


def llm_score(rec: dict, text: str | None = None) -> dict[str, Any] | None:
    if get_client() is None or chat_text is None:
        return None
    body = (text or rec.get("summary") or rec.get("summary_en") or "")[:8000]
    if len(body.strip()) < 40:
        body = _blob(rec)[:8000]
    meta = (
        f"REGULATOR: {_regulator_from_rec(rec) or 'Unknown'}\n"
        f"SOURCE URL: {rec.get('url') or rec.get('open_url') or ''}\n"
        f"FILENAME: {rec.get('title') or ''}\n"
        f"EXISTING DOCUMENT TYPE: {rec.get('document_type') or ''}\n"
        f"JURISDICTION: {rec.get('jurisdiction') or ''}"
    )
    user = f"{ANALYSIS_PROMPT}\n\n{meta}\n\nDOCUMENT TEXT:\n{body}"
    try:
        raw = chat_text(
            "Return only valid JSON matching the requested keys.",
            user,
            temperature=0.1,
            max_tokens=900,
        )
    except Exception:
        return None
    data = _parse_llm_json(raw)
    if not data:
        return None
    score = clamp_score(data.get("relevance_score"))
    ai_type = str(data.get("document_type") or "OTHER").upper()
    category = data.get("relevance_category") or category_from_score(score)
    if category not in {"critical", "high", "medium", "low", "not_relevant"}:
        category = category_from_score(score)
    return {
        "ai_relevance_score": score,
        "ai_relevance_category": category,
        "ai_document_type": ai_type,
        "ai_status": "not_relevant" if category == "not_relevant" or score < 25 else "analyzed",
        "ai_confidence": float(data.get("confidence") or 0.7),
        "ai_relevance_reason": str(data.get("relevance_reason") or "").strip(),
        "english_title": str(data.get("english_title") or rec.get("title") or "").strip(),
        "english_summary": str(data.get("english_summary") or rec.get("summary") or "").strip(),
        "regulator": str(data.get("regulator") or _regulator_from_rec(rec)).strip(),
        "sub_ministries": list(data.get("sub_ministries") or []),
        "text_extraction_status": "extracted",
        "score_method": "llm",
        "scored_at": datetime.now(timezone.utc).isoformat(),
        "publication_date": data.get("publication_date"),
        "effective_date": data.get("effective_date"),
        "tags": list(data.get("tags") or rec.get("topics") or [])[:8],
    }


def apply_score(rec: dict, *, use_llm: bool = False, text: str | None = None) -> dict:
    fields = None
    if use_llm:
        fields = llm_score(rec, text=text)
    if not fields:
        fields = heuristic_score(rec)
    rec.update(fields)
    return rec


def needs_score(rec: dict) -> bool:
    status = rec.get("ai_status")
    score = rec.get("ai_relevance_score")
    return status in (None, "", "pending") or score is None


def score_store(
    *,
    limit: int = 0,
    only_unscored: bool = True,
    use_llm: bool = False,
    publish: bool = True,
) -> dict[str, int]:
    if load_existing is None:
        raise RuntimeError("eva_summarize.load_existing unavailable")
    existing = load_existing()
    stats = {"scored": 0, "skipped": 0, "llm": 0, "heuristic": 0, "total": len(existing)}
    for rec in existing.values():
        if only_unscored and not needs_score(rec):
            stats["skipped"] += 1
            continue
        apply_score(rec, use_llm=use_llm)
        stats["scored"] += 1
        if rec.get("score_method") == "llm":
            stats["llm"] += 1
        else:
            stats["heuristic"] += 1
        if limit and stats["scored"] >= limit:
            break
    if rewrite_jsonl:
        rewrite_jsonl(existing)
    if publish and publish_web:
        publish_web(existing)
    return stats


def main() -> None:
    p = argparse.ArgumentParser(description="Score Eva summaries (Rhandar bands)")
    p.add_argument("--limit", type=int, default=0, help="Max records to score (0 = all)")
    p.add_argument("--only-unscored", action="store_true", default=True)
    p.add_argument("--reprocess", action="store_true", help="Score even if already scored")
    p.add_argument("--heuristic", action="store_true", help="Force heuristic (no LLM)")
    p.add_argument("--llm", action="store_true", help="Use XAI when available")
    p.add_argument("--all", action="store_true", help="Score every row (implies --reprocess)")
    p.add_argument("--publish-only", action="store_true")
    args = p.parse_args()
    if args.publish_only:
        existing = load_existing()
        publish_web(existing)
        print(json.dumps({"published": len(existing)}, indent=2))
        return
    only = not (args.reprocess or args.all)
    use_llm = bool(args.llm) and not args.heuristic
    stats = score_store(limit=args.limit, only_unscored=only, use_llm=use_llm)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
