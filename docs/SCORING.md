# Document relevance scoring

Port of CompliGuard / Rhandar `ANALYSIS_PROMPT` bands. Implementation: `collector/eva_score.py`.

## Bands

| Score | Category | Meaning |
|------:|----------|---------|
| 90–100 | critical | Binding legal/regulatory obligations |
| 75–89 | high | Implementation requirements, circulars, mandatory guidance |
| 50–74 | medium | Context, non-binding guidance, extracts of a law |
| 25–49 | low | Internal authority policy, reports, strategy |
| 0–24 | not_relevant | News, jobs, events, brand kits, procurement |

`is_relevant` is true when score ≥ 25. The Documents UI defaults to **high + critical** (score ≥ 75).

## How to run

```bash
# Heuristic backfill (no API key)
.venv/bin/python collector/eva_score.py --all --heuristic

# LLM scoring when XAI_API_KEY is set
export XAI_API_KEY=...
.venv/bin/python collector/eva_score.py --limit 50 --llm --only-unscored
```

Junk URL/filename prefilter (`news`, `press`, `career`, `job`, `tender`, `event`, `blog`, `speech`) skips the LLM and scores 0–24.
