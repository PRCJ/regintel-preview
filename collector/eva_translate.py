#!/usr/bin/env python3
"""Free translation for Eva. No XAI_API_KEY required.

Primary: deep-translator (Google free endpoint — `pip install deep-translator`)
Optional: Argos Translate offline MT if EVA_TRANSLATE_ARGOS=1
          (`pip install argostranslate` — large; pulls torch)

  .venv/bin/python collector/eva_translate.py --status
  .venv/bin/python collector/eva_translate.py --text "اللائحة التنفيذية" --to en
"""
from __future__ import annotations

import argparse
import os
import re
import time
from typing import Any

_AR = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")
_CJK = re.compile(r"[\u4e00-\u9fff]")
_DEV = re.compile(r"[\u0900-\u097F]")
_CYR = re.compile(r"[\u0400-\u04FF]")

# Argos package codes we will install on demand (ISO 639-1).
_ARGOS_CODES = {"en", "ar", "fr", "es", "de", "hi", "tr", "pt", "zh", "ru", "ur"}

_installed_pairs: set[tuple[str, str]] = set()
_argos_index_ok: bool | None = None


def detect_lang(text: str) -> str:
    s = str(text or "")
    if not s.strip():
        return "en"
    ar = len(_AR.findall(s))
    cjk = len(_CJK.findall(s))
    dev = len(_DEV.findall(s))
    cyr = len(_CYR.findall(s))
    lat = len(re.findall(r"[A-Za-z]", s))
    n = max(ar + cjk + dev + cyr + lat, 1)
    if ar / n > 0.25:
        return "ar"
    if cjk / n > 0.25:
        return "zh"
    if dev / n > 0.25:
        return "hi"
    if cyr / n > 0.25:
        return "ru"
    return "en"


def _norm_code(code: str | None) -> str:
    c = (code or "en").strip().lower().replace("_", "-")
    if c in ("auto", "autodetect", ""):
        return "en"
    if c.startswith("zh"):
        return "zh"
    return c.split("-")[0]


def chunk_text(text: str, max_len: int = 800) -> list[str]:
    rest = str(text or "")
    out: list[str] = []
    while rest:
        if len(rest) <= max_len:
            out.append(rest)
            break
        cut = rest.rfind(" ", 0, max_len)
        if cut < max_len * 0.4:
            cut = rest.rfind("\n", 0, max_len)
        if cut < max_len * 0.4:
            cut = max_len
        out.append(rest[:cut])
        rest = rest[cut:].lstrip()
    return out


def _argos_wanted() -> bool:
    """Argos pulls torch; only import when explicitly enabled."""
    return os.environ.get("EVA_TRANSLATE_ARGOS", "").strip().lower() in {"1", "true", "yes"}


def engine_status() -> dict[str, Any]:
    argos = False
    deep = False
    if _argos_wanted():
        try:
            import argostranslate.translate  # noqa: F401

            argos = True
        except Exception:
            argos = False
    try:
        from deep_translator import GoogleTranslator  # noqa: F401

        deep = True
    except Exception:
        deep = False
    primary = "argos" if argos else ("deep-translator" if deep else "none")
    return {
        "argos": argos,
        "deep_translator": deep,
        "primary": primary,
    }


def _argos_have_pair(src: str, tgt: str) -> bool:
    if (src, tgt) in _installed_pairs:
        return True
    try:
        import argostranslate.package
        import argostranslate.translate
    except Exception:
        return False
    for pkg in argostranslate.package.get_installed_packages():
        if getattr(pkg, "from_code", None) == src and getattr(pkg, "to_code", None) == tgt:
            _installed_pairs.add((src, tgt))
            return True
    langs = argostranslate.translate.get_installed_languages()
    from_lang = next((l for l in langs if l.code == src), None)
    to_lang = next((l for l in langs if l.code == tgt), None)
    if from_lang and to_lang and from_lang.get_translation(to_lang):
        _installed_pairs.add((src, tgt))
        return True
    return False


def _argos_install_pair(src: str, tgt: str) -> bool:
    if _argos_have_pair(src, tgt):
        return True
    global _argos_index_ok
    try:
        import argostranslate.package
    except Exception:
        return False
    try:
        if _argos_index_ok is not True:
            argostranslate.package.update_package_index()
            _argos_index_ok = True
        available = argostranslate.package.get_available_packages()
        pkg = next((p for p in available if p.from_code == src and p.to_code == tgt), None)
        if pkg is None:
            return False
        if hasattr(pkg, "install"):
            pkg.install()
        else:
            argostranslate.package.install_from_path(pkg.download())
        _installed_pairs.add((src, tgt))
        return True
    except Exception:
        return False


def _argos_translate_chunk(text: str, src: str, tgt: str) -> str:
    import argostranslate.translate

    if not _argos_install_pair(src, tgt):
        raise RuntimeError(f"no Argos model {src}->{tgt}")
    out = argostranslate.translate.translate(text, src, tgt)
    return (out or "").strip()


def _deep_translate_chunk(text: str, src: str, tgt: str) -> str:
    from deep_translator import GoogleTranslator

    sl = "zh-CN" if src == "zh" else src
    tl = "zh-CN" if tgt == "zh" else tgt
    # deep-translator rejects some codes; "auto" is safer for messy extracts
    try:
        tr = GoogleTranslator(source=sl, target=tl)
        out = tr.translate(text)
    except Exception:
        tr = GoogleTranslator(source="auto", target=tl)
        out = tr.translate(text)
    return (out or "").strip()


def translate_text(
    text: str,
    *,
    target: str = "en",
    source: str | None = None,
    prefer: str | None = None,
) -> dict[str, Any]:
    """Translate text with Argos, then deep-translator. Never calls xAI."""
    raw = re.sub(r"\x00", "", str(text or "")).strip()
    tgt = _norm_code(target)
    src = _norm_code(source) if source else detect_lang(raw)
    if not raw:
        return {"text": "", "engine": "empty", "source": src, "target": tgt}
    if src == tgt:
        return {"text": raw, "engine": "same", "source": src, "target": tgt}

    status = engine_status()
    engines: list[str] = []
    if prefer == "deep":
        if status["deep_translator"]:
            engines.append("deep-translator")
        if status["argos"]:
            engines.append("argos")
    else:
        if status["argos"]:
            engines.append("argos")
        if status["deep_translator"]:
            engines.append("deep-translator")

    last_err = ""
    chunks = chunk_text(raw, 800)
    for engine in engines:
        try:
            parts: list[str] = []
            for i, ch in enumerate(chunks):
                if engine == "argos":
                    # Pivot through English when a direct pair is missing
                    if src != "en" and tgt != "en" and not _argos_have_pair(src, tgt):
                        mid = _argos_translate_chunk(ch, src, "en")
                        piece = _argos_translate_chunk(mid, "en", tgt) if tgt != "en" else mid
                    else:
                        piece = _argos_translate_chunk(ch, src, tgt)
                else:
                    piece = _deep_translate_chunk(ch, src, tgt)
                    if i < len(chunks) - 1:
                        time.sleep(0.2)
                if not piece:
                    raise RuntimeError(f"{engine} empty chunk")
                parts.append(piece)
            joined = " ".join(parts).strip()
            if joined:
                return {"text": joined, "engine": engine, "source": src, "target": tgt}
        except Exception as e:
            last_err = f"{engine}: {e}"
            continue
    raise RuntimeError(
        last_err
        or "No free translator available. Install: pip install argostranslate   "
        "(offline) or pip install deep-translator"
    )


def translate_fields(
    *,
    title: str = "",
    summary: str = "",
    key_points: list[str] | None = None,
    target: str = "en",
) -> dict[str, Any]:
    points = [str(p) for p in (key_points or [])]
    blob = "\n".join([title or "", summary or "", *points])
    source = detect_lang(blob)
    tgt = _norm_code(target)
    if source == tgt:
        return {
            "title": title,
            "summary": summary,
            "key_points": points,
            "engine": "same",
            "source": source,
            "target": tgt,
        }

    def _one(s: str) -> str:
        if not (s or "").strip():
            return ""
        return translate_text(s, target=tgt, source=source)["text"]

    title_out = _one(title) if title else ""
    summary_out = _one(summary) if summary else ""
    points_out = [_one(p) if p else "" for p in points]
    engine = engine_status()["primary"]
    return {
        "title": title_out or title,
        "summary": summary_out or summary,
        "key_points": points_out,
        "engine": engine,
        "source": source,
        "target": tgt,
    }


def needs_english(rec: dict) -> bool:
    """True when a stored summary should get an English translation field."""
    if rec.get("summary_en") and str(rec.get("summary_en")).strip():
        return False
    summary = str(rec.get("summary") or "")
    title = str(rec.get("title") or "")
    if not summary.strip() and not title.strip():
        return False
    low = summary.lower()
    if low.startswith("no extractable") or "could not extract readable" in low:
        return False
    if rec.get("method") in {"empty", "extractive_unreadable", "error"}:
        return False
    blob = title + "\n" + summary
    return detect_lang(blob) != "en"


def apply_english(rec: dict) -> dict:
    """Fill title_en / summary_en / key_points_en on a summary row (in place)."""
    if not needs_english(rec):
        if detect_lang(str(rec.get("summary") or rec.get("title") or "")) == "en":
            rec.setdefault("title_en", rec.get("title") or "")
            rec.setdefault("summary_en", rec.get("summary") or "")
            rec.setdefault("key_points_en", list(rec.get("key_points") or []))
            rec.setdefault("translate_engine", "same")
        return rec
    title = str(rec.get("title") or "")
    try:
        from eva_llm import is_placeholder_title
        if is_placeholder_title(title):
            title = ""
    except Exception:
        if title.lower() in {"embedded-url", "click here", "download", "pdf"}:
            title = ""
    fields = translate_fields(
        title=title,
        summary=str(rec.get("summary") or ""),
        key_points=list(rec.get("key_points") or []),
        target="en",
    )
    rec["title_en"] = fields["title"]
    rec["summary_en"] = fields["summary"]
    rec["key_points_en"] = fields["key_points"]
    rec["translate_engine"] = fields["engine"]
    return rec


def main() -> None:
    p = argparse.ArgumentParser(description="Eva free translator (Argos / deep-translator)")
    p.add_argument("--text", help="Translate this string")
    p.add_argument("--to", default="en", dest="target")
    p.add_argument("--from", dest="source", default=None)
    p.add_argument("--status", action="store_true")
    args = p.parse_args()
    st = engine_status()
    if args.status or not args.text:
        print(st)
        if not args.text:
            return
    res = translate_text(args.text, target=args.target, source=args.source)
    print(res)


if __name__ == "__main__":
    main()
