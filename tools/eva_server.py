#!/usr/bin/env python3
"""
Optional local Eva API (LLM chat if XAI_API_KEY is set; translate works without it).

  export XAI_API_KEY=...
  .venv/bin/python tools/eva_server.py --port 8787

Endpoints:
  GET  /health
  GET  /api/health
  GET  /api/eva/meta
  GET  /api/documents
  GET  /api/changes
  GET  /api/pipeline
  POST /api/eva/ask  {"question":"...","k":8}
  POST /api/eva/translate  {"text":"...","target":"en","source":"ar"}  (Argos / deep-translator, no XAI)
  POST /api/crawl    {"url":"https://…","label":"Saudi Arabia - MEWA"}
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collector"))

from eva_agent import ask, load_summaries  # type: ignore
from eva_llm import get_client  # type: ignore
from eva_translate import engine_status, translate_text  # type: ignore

WEB_DATA = ROOT / "web" / "data"
DATA = ROOT / "data"


def _load_json(name: str, default):
    for folder in (WEB_DATA, DATA):
        path = folder / name
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return default
    return default


def _documents_payload():
    rows = load_summaries()
    bands = {}
    for r in rows:
        cat = str(r.get("ai_relevance_category") or "unscored")
        bands[cat] = bands.get(cat, 0) + 1
    return {"ok": True, "count": len(rows), "bands": bands, "documents": rows}


def _changes_payload():
    cached = _load_json("changes.json", None)
    if isinstance(cached, list):
        rows = cached
    elif isinstance(cached, dict) and isinstance(cached.get("changes"), list):
        rows = cached["changes"]
    else:
        updates = _load_json("updates.json", [])
        rows = []
        if isinstance(updates, list):
            for u in updates:
                rows.append(
                    {
                        "id": u.get("id"),
                        "title": u.get("title"),
                        "summary": u.get("topical_relevance") or "",
                        "change_type": "updated" if "changed" in str(u.get("title") or "").lower() else "new_publication",
                        "source_url": u.get("link") or u.get("source_url"),
                        "detected_date": u.get("discovered_at"),
                        "jurisdiction": u.get("country"),
                        "status": "new" if u.get("alert_status") == "new" else u.get("alert_status") or "new",
                        "priority": "medium",
                        "ai_status": "pending",
                        "authority": u.get("authority"),
                    }
                )
    return {"ok": True, "count": len(rows), "changes": rows}


def _pipeline_payload():
    runs = _load_json("fetch_runs.json", [])
    status = _load_json("crawl_status.json", {})
    crawls = _load_json("active_crawls.json", {})
    docs = load_summaries()
    pending_ai = sum(1 for r in docs if not r.get("ai_status") or r.get("ai_status") == "pending")
    failed = sum(1 for r in docs if r.get("ai_status") == "failed")
    scored = sum(1 for r in docs if r.get("ai_relevance_score") is not None)
    return {
        "ok": True,
        "summaries": len(docs),
        "scored": scored,
        "pending_ai": pending_ai,
        "failed_ai": failed,
        "fetch_runs": len(runs) if isinstance(runs, list) else 0,
        "crawl_status": status if isinstance(status, dict) else {},
        "active_crawls": crawls if isinstance(crawls, dict) else {},
    }


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code: int, obj: dict):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/health", "/api/eva/health", "/api/health"):
            return self._json(
                200,
                {
                    "ok": True,
                    "agent": "Eva",
                    "summaries": len(load_summaries()),
                    "llm": get_client() is not None,
                    "translate": engine_status(),
                },
            )
        if path == "/api/documents":
            return self._json(200, _documents_payload())
        if path == "/api/changes":
            return self._json(200, _changes_payload())
        if path == "/api/pipeline":
            return self._json(200, _pipeline_payload())
        if path == "/api/eva/meta":
            return self._json(
                200,
                {
                    "agent": "Eva",
                    "summaries": len(load_summaries()),
                    "llm": get_client() is not None,
                    "translate": engine_status(),
                },
            )
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/crawl":
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                return self._json(400, {"error": "invalid json"})
            url = (payload.get("url") or "").strip()
            if not url.startswith("http"):
                return self._json(400, {"error": "url required (https://…)"})
            label = (payload.get("label") or "").strip()
            max_pages = str(payload.get("max_pages") or "2000")
            delay = str(payload.get("delay") or "0.25")
            repo = os.environ.get("REGINTEL_GH_REPO") or "tmai-tech/regintel"
            cmd = [
                "gh",
                "workflow",
                "run",
                "crawl-ministry.yml",
                "--repo",
                repo,
                "-f",
                f"url={url}",
                "-f",
                f"label={label}",
                "-f",
                f"max_pages={max_pages}",
                "-f",
                f"delay={delay}",
                "-f",
                "discover_only=false",
            ]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            except FileNotFoundError:
                return self._json(500, {"error": "gh CLI not installed"})
            except Exception as e:
                return self._json(500, {"error": str(e)[:300]})
            if proc.returncode != 0:
                return self._json(
                    500,
                    {"error": (proc.stderr or proc.stdout or "gh workflow run failed")[:500]},
                )
            return self._json(
                200,
                {
                    "ok": True,
                    "url": url,
                    "label": label,
                    "html_url": f"https://github.com/{repo}/actions/workflows/crawl-ministry.yml",
                },
            )
        if path == "/api/eva/translate":
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                return self._json(400, {"error": "invalid json"})
            text = payload.get("text") or ""
            if not str(text).strip():
                return self._json(400, {"error": "text required"})
            try:
                res = translate_text(
                    str(text),
                    target=str(payload.get("target") or "en"),
                    source=payload.get("source") or None,
                )
                return self._json(200, res)
            except Exception as e:
                return self._json(500, {"error": str(e)[:400]})
        if path != "/api/eva/ask":
            return self._json(404, {"error": "not found"})
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return self._json(400, {"error": "invalid json"})
        q = (payload.get("question") or "").strip()
        if not q:
            return self._json(400, {"error": "question required"})
        k = int(payload.get("k") or 10)
        deep = payload.get("deep", True)
        try:
            res = ask(q, k=k, deep=bool(deep))
            return self._json(200, res)
        except Exception as e:
            return self._json(500, {"error": str(e)[:400]})

    def log_message(self, fmt, *args):
        sys.stderr.write("EvaAPI " + (fmt % args) + "\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8787)
    args = p.parse_args()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(
        f"Eva API on http://{args.host}:{args.port}  "
        f"summaries={len(load_summaries())} llm={get_client() is not None}"
    )
    httpd.serve_forever()


if __name__ == "__main__":
    main()
