"""Shared field names and helpers for Rhandar-parity product records."""

from __future__ import annotations

from typing import Any

# Scoring bands — same cutoffs as CompliGuard ANALYSIS_PROMPT
SCORE_CRITICAL = 90
SCORE_HIGH = 75
SCORE_MEDIUM = 50
SCORE_LOW = 25

AI_CATEGORIES = ("critical", "high", "medium", "low", "not_relevant")
AI_STATUSES = ("pending", "analyzed", "failed", "not_relevant")
EXTRACT_STATUSES = ("pending", "extracted", "failed", "ocr_required")
CHANGE_TYPES = (
    "new_url",
    "updated",
    "removed",
    "redirected",
    "document_updated",
    "amendment",
    "new_publication",
    "repeal",
    "guidance_update",
    "circular",
    "other",
)
CHANGE_STATUSES = ("new", "reviewing", "actioned", "dismissed")

# Compact fields published to web/data/eva_summaries.json
SCORE_WEB_FIELDS = (
    "ai_relevance_score",
    "ai_relevance_category",
    "ai_document_type",
    "ai_status",
    "ai_confidence",
    "ai_relevance_reason",
    "english_title",
    "english_summary",
    "regulator",
    "sub_ministries",
    "content_hash",
    "text_extraction_status",
    "scored_at",
    "score_method",
)

FIRESTORE_COLLECTIONS = {
    "summaries": "regintel_summaries",
    "monitored_urls": "regintel_monitored_urls",
    "changes": "regintel_changes",
    "sources": "regintel_sources",
    "checklists": "regintel_checklists",
    "checklist_items": "regintel_checklist_items",
    "themes": "regintel_themes",
    "policies": "regintel_policies",
    "policy_impacts": "regintel_policy_impacts",
    "notifications": "regintel_notifications",
}


def category_from_score(score: int | float | None) -> str:
    try:
        n = float(score)
    except (TypeError, ValueError):
        return "not_relevant"
    if n >= SCORE_CRITICAL:
        return "critical"
    if n >= SCORE_HIGH:
        return "high"
    if n >= SCORE_MEDIUM:
        return "medium"
    if n >= SCORE_LOW:
        return "low"
    return "not_relevant"


def clamp_score(score: Any) -> int:
    try:
        n = int(round(float(score)))
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, n))


def empty_score_fields() -> dict[str, Any]:
    return {
        "ai_relevance_score": None,
        "ai_relevance_category": "",
        "ai_document_type": "",
        "ai_status": "pending",
        "ai_confidence": None,
        "ai_relevance_reason": "",
        "english_title": "",
        "english_summary": "",
        "regulator": "",
        "sub_ministries": [],
        "content_hash": "",
        "text_extraction_status": "pending",
        "scored_at": "",
        "score_method": "",
    }
