#!/usr/bin/env python3
"""Rebuild and git-push the public catalog every 10 minutes.

Merges ministry PDFs already on disk (recover writes them only after a site
drain) so SASO files appear before that batch finishes. Stops after the
recover job exits and one final publish, or after --max-hours.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collector"))
sys.path.insert(0, str(ROOT / "scripts"))

from live_publish import publish  # type: ignore

INTERVAL_SEC = 600
MANIFEST = ROOT / "data" / "pdfs" / "manifest.json"
CATALOG = ROOT / "web" / "data" / "pdfs_catalog.json"
LOG = ROOT / "data" / "_publish_catalog_watch.log"

SITE_DIRS = (
    ("Saudi_Arabia_MOMAH", "Saudi Arabia - MOMAH"),
    ("Saudi_Arabia_ZATCA", "Saudi Arabia - ZATCA"),
    ("Saudi_Arabia_SASO", "Saudi Arabia - SASO"),
    ("Saudi_Arabia_GOSI", "Saudi Arabia - GOSI"),
)

URL_SOURCES = (
    "data/_recover_momah.txt",
    "data/_recover_zatca.txt",
    "data/_recover_saso.txt",
    "data/momah_found_docs.txt",
    "data/zatca_found_docs.txt",
    "data/pdfs/ministry_lists/momahgovsa.json",
    "data/pdfs/ministry_lists/zatcagovsa.json",
    "data/pdfs/ministry_lists/sasogovsa.json",
    "data/pdfs/ministry_lists/gosigovsa.json",
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(msg: str) -> None:
    line = f"[{now()}] {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def recover_running() -> bool:
    try:
        out = subprocess.check_output(
            ["pgrep", "-af", "scripts/recover_listed_pdfs.py"],
            text=True,
        )
    except subprocess.CalledProcessError:
        return False
    for line in out.splitlines():
        if "recover_listed_pdfs.py" in line and "publish_catalog_watch" not in line:
            return True
    return False


def urls_from_path(rel: str) -> list[str]:
    p = ROOT / rel
    if not p.exists():
        return []
    if p.suffix == ".json":
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return [
            (d.get("url") or "").strip()
            for d in (data.get("documents") or [])
            if (d.get("url") or "").startswith("http")
        ]
    return [
        ln.strip()
        for ln in p.read_text(encoding="utf-8").splitlines()
        if ln.strip().startswith("http")
    ]


def filename_to_url() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for rel in URL_SOURCES:
        for url in urls_from_path(rel):
            name = unquote(url.rstrip("/").rsplit("/", 1)[-1])
            if name and name not in mapping:
                mapping[name] = url
    return mapping


def known_urls() -> set[str]:
    have: set[str] = set()
    if CATALOG.exists():
        try:
            rows = json.loads(CATALOG.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            rows = []
        for r in rows:
            for key in ("url", "open_url"):
                u = (r.get(key) or "").strip()
                if u:
                    have.add(u)
    if MANIFEST.exists():
        try:
            man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            man = {}
        for d in man.get("downloads") or []:
            u = (d.get("url") or "").strip()
            if u:
                have.add(u)
    return have


def merge_disk_pdfs() -> int:
    """Add completed on-disk ministry PDFs that are not in the manifest yet."""
    names = filename_to_url()
    have = known_urls()
    if MANIFEST.exists():
        try:
            man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            man = {"downloads": []}
    else:
        man = {"downloads": []}
    added = 0
    for folder, label in SITE_DIRS:
        root = ROOT / "data" / "pdfs" / folder
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.pdf")):
            if path.stat().st_size < 128:
                continue
            url = names.get(path.name)
            if not url or url in have:
                continue
            rel = str(path.relative_to(ROOT))
            sha = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
            man.setdefault("downloads", []).append(
                {
                    "url": url,
                    "jurisdiction": label,
                    "source_kind": "ministry",
                    "title": path.stem,
                    "path": rel,
                    "bytes": path.stat().st_size,
                    "sha256": sha,
                    "downloaded_at": datetime.fromtimestamp(
                        path.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                    "status": "downloaded",
                    "scanned_pdf": False,
                    "discovery_method": "recover-watch",
                }
            )
            have.add(url)
            added += 1
            log(f"merge {label} {path.name} ({path.stat().st_size} bytes)")
    if added:
        man["generated_at"] = now()
        MANIFEST.write_text(
            json.dumps(man, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return added


def catalog_count() -> int:
    if not CATALOG.exists():
        return 0
    try:
        rows = json.loads(CATALOG.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0
    return len(rows) if isinstance(rows, list) else 0


def file_hash(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def one_tick(*, force_push: bool = False) -> dict:
    from live_publish import _git_push_live  # type: ignore

    added = merge_disk_pdfs()
    before = catalog_count()
    before_h = file_hash(CATALOG)
    status = publish(
        phase="idle",
        message="periodic recovered catalog snapshot",
        git_push=False,
        force_git=False,
    )
    after = catalog_count()
    changed = added > 0 or after != before or file_hash(CATALOG) != before_h
    pushed = False
    if changed or force_push:
        pushed = bool(_git_push_live(after, "periodic snapshot"))
    log(
        f"publish catalog={after} (was {before}) merged={added} "
        f"changed={changed} pushed={pushed} recover={recover_running()}"
    )
    return {
        "added": added,
        "before": before,
        "after": after,
        "pushed": pushed,
        "status": status,
    }


def main() -> None:
    max_hours = 12.0
    if len(sys.argv) > 1 and sys.argv[1].startswith("--max-hours"):
        if "=" in sys.argv[1]:
            max_hours = float(sys.argv[1].split("=", 1)[1])
        elif len(sys.argv) > 2:
            max_hours = float(sys.argv[2])
    deadline = time.time() + max_hours * 3600
    idle_after_recover = 0
    log(f"watch start interval={INTERVAL_SEC}s max_hours={max_hours}")
    while True:
        try:
            # Force a push only after recover exits, so its final manifest merge goes live.
            one_tick(force_push=idle_after_recover == 1)
        except Exception as e:
            log(f"tick failed: {e!r}")
        if not recover_running():
            idle_after_recover += 1
            log(f"recover not running (cycle {idle_after_recover})")
            if idle_after_recover >= 2:
                log("watch stop: recover finished + final publish")
                return
        else:
            idle_after_recover = 0
        if time.time() >= deadline:
            log("watch stop: max hours reached")
            return
        time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    os.chdir(ROOT)
    main()
