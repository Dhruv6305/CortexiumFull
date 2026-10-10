"""
Cortexium 2.0 — Session Summary Manager  (v2)
==============================================
Generates, stores, and retrieves per-person per-session summaries.

Storage layout:
  backend/data/summaries/<PersonName>/<PersonName>_YYYY-MM-DD_S<NNN>.json

What's new in v2:
  - Junk text filtering (short/incomplete ASR fragments removed)
  - Auto-finalization: any unfinished session is finalized (rule-based,
    instant) when the user asks for their last summary
  - Fast LLM path: uses llm_client.generate_summary() (10s timeout, 50 tokens)
  - Sequential backfill: one session at a time, rule-based only, no LLM spam
"""
import asyncio
import json
import re
from datetime import datetime, date
from pathlib import Path
from typing import Optional

DATA_DIR      = Path(__file__).resolve().parent.parent / "data"
CONVOS_DIR    = DATA_DIR / "conversations"
SUMMARIES_DIR = DATA_DIR / "summaries"
SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)

# ─── Common English stop-words (for junk detection) ──────────────────────────
_STOPS = {
    "a","an","the","and","or","but","in","on","at","to","for","of","with",
    "is","was","are","were","be","been","being","have","has","had","do","does",
    "did","will","would","could","should","may","might","shall","i","my","me",
    "we","our","us","you","your","it","its","this","that","these","those",
    "he","she","they","their","what","which","who","when","where","how","why",
    "so","if","then","also","too","very","just","not","no","yes","oh","um",
    "uh","like","from","by","about","into","through","during","before","after",
    "above","below","up","down","out","off","over","under","again","further",
    "once","here","there","than","more","most","other","some","such","only",
    "own","same","as","while","because","until","both","each","few","many",
    "s","t","re","ve","ll","d",
}


# ═════════════════════════════════════════════════════════════════════════════
#  Text cleaning helpers
# ═════════════════════════════════════════════════════════════════════════════

def _meaningful_word_count(text: str) -> int:
    """Return count of non-stop words in text."""
    words = re.findall(r"[a-zA-Z']+", text.lower())
    return sum(1 for w in words if w not in _STOPS and len(w) > 1)


def _is_junk(text: str) -> bool:
    """
    Return True if text is a low-quality ASR fragment not worth storing.
    Preserves valid short sentences while filtering out empty or single-filler noise.
    """
    if not text or not text.strip():
        return True
    cleaned = text.strip()
    words = cleaned.split()
    if not words:
        return True
    # If single word, reject noise/filler
    if len(words) == 1:
        w = re.sub(r"[^\w]", "", words[0].lower())
        if len(w) < 2 or w in ("uh", "um", "ah", "oh", "er", "hmm"):
            return True
    # Require at least some letters
    if not re.search(r"[a-zA-Z]{2,}", cleaned):
        return True
    return False


def _clean_texts(raw_texts: list[str]) -> list[str]:
    """
    Filter and clean a list of raw ASR transcripts:
      1. Remove junk fragments
      2. Remove near-duplicates (same first 40 chars)
      3. Strip leading/trailing noise words
    """
    cleaned, seen = [], set()
    for t in raw_texts:
        t = t.strip().rstrip(".,;:")
        if _is_junk(t):
            continue
        # Dedup by first 40 chars (handles re-deliveries)
        key = re.sub(r"\s+", " ", t.lower())[:40]
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(t)
    return cleaned


# ═════════════════════════════════════════════════════════════════════════════
#  Summarisation helpers
# ═════════════════════════════════════════════════════════════════════════════

def _rule_based_summary(person_name: str, texts: list[str]) -> str:
    """
    Instant fallback summary — no LLM, no network call.
    Joins up to 5 unique phrases, truncates at 200 chars.
    """
    if not texts:
        return "No meaningful conversation recorded this session."
    joined = ". ".join(t.rstrip(".") for t in texts[:5])
    if len(joined) > 200:
        cut = joined[:197].rsplit(" ", 1)[0]
        return cut + "."
    return joined + ("." if not joined.endswith(".") else "")


async def _llm_summarise(person_name: str, texts: list[str]) -> str:
    """
    Calls llm_client.generate_summary() — 10 s timeout, 50 tokens max.
    Falls back to rule-based instantly on timeout or error.
    """
    fallback = _rule_based_summary(person_name, texts)
    try:
        from ..ai.llm_client import llm_client
        result = await llm_client.generate_summary(person_name, texts)
        if result and len(result) >= 10:
            # Reject JSON responses
            if not result.strip().startswith("{"):
                return result
    except Exception as e:
        print(f"[SummaryMgr] LLM error: {e}")
    return fallback


# ═════════════════════════════════════════════════════════════════════════════
#  Path / file helpers
# ═════════════════════════════════════════════════════════════════════════════

def _safe_name(name: str) -> str:
    return re.sub(r"[^\w\s-]", "", name).strip().title()


def _person_dir(name: str) -> Path:
    d = SUMMARIES_DIR / _safe_name(name)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _next_session_code(person_name: str, date_str: str) -> str:
    """Return next available code like '2026-08-27_S003'."""
    d      = _person_dir(person_name)
    slug   = _safe_name(person_name)
    prefix = f"{slug}_{date_str}_S"
    existing = sorted(d.glob(f"{prefix}*.json"))
    if not existing:
        return f"{date_str}_S001"
    m = re.search(r"_S(\d+)$", existing[-1].stem)
    n = int(m.group(1)) + 1 if m else 1
    return f"{date_str}_S{n:03d}"


def _summary_path(person_name: str, session_code: str) -> Path:
    slug = _safe_name(person_name)
    return _person_dir(person_name) / f"{slug}_{session_code}.json"


def _find_by_session_id(person_name: str, session_id: str) -> dict | None:
    """Return existing summary file data for a session_id, or None."""
    for f in _person_dir(person_name).glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("session_id") == session_id:
                return data
        except Exception:
            pass
    return None


# ═════════════════════════════════════════════════════════════════════════════
#  Core: generate_and_save
# ═════════════════════════════════════════════════════════════════════════════

async def generate_and_save(
    person_name: str,
    session_id:  str,
    entries:     list[dict],
    use_llm:     bool = True,
) -> dict | None:
    """
    Generate a summary for a session and persist it to disk.
    Returns the saved summary dict, or None if no useful entries.
    """
    slug = _safe_name(person_name)

    # Already summarised?
    existing = _find_by_session_id(person_name, session_id)
    if existing:
        return existing

    # Filter entries to this session
    session_entries = [
        e for e in entries
        if e.get("session_id") == session_id and e.get("note", "").strip()
    ]
    if not session_entries:
        # Check if this profile has ANY entries with session_id. 
        # If yes, this is a modern profile and the current session is just empty.
        has_any_session_id = any(e.get("session_id") for e in entries)
        if has_any_session_id:
            return None
        # Otherwise, legacy fallback: all entries (no session_id tag)
        session_entries = [e for e in entries if e.get("note", "").strip()]
    if not session_entries:
        return None

    # ── Clean + deduplicate raw texts ────────────────────────────────────
    raw_texts   = [e["note"] for e in session_entries]
    clean_texts = _clean_texts(raw_texts)

    if not clean_texts:
        print(f"[SummaryMgr] All entries filtered as junk for {slug}/{session_id}")
        return None

    # ── Timestamps ───────────────────────────────────────────────────────
    timestamps = []
    for e in session_entries:
        try:
            timestamps.append(datetime.fromisoformat(e["timestamp"]))
        except Exception:
            pass
    now        = datetime.utcnow()
    started_at = (min(timestamps) if timestamps else now).isoformat()
    ended_at   = (max(timestamps) if timestamps else now).isoformat()
    date_str   = (min(timestamps) if timestamps else now).strftime("%Y-%m-%d")

    # ── Generate summary ─────────────────────────────────────────────────
    if use_llm:
        summary_text = await _llm_summarise(slug, clean_texts)
    else:
        summary_text = _rule_based_summary(slug, clean_texts)

    # ── Persist ──────────────────────────────────────────────────────────
    session_code = _next_session_code(person_name, date_str)
    path         = _summary_path(person_name, session_code)

    data = {
        "person":       slug,
        "session_id":   session_id,
        "session_code": session_code,
        "date":         date_str,
        "started_at":   started_at,
        "ended_at":     ended_at,
        "summary":      summary_text,
        "transcript":   clean_texts,
        "entry_count":  len(session_entries),
        "clean_count":  len(clean_texts),
        "generated_at": now.isoformat(),
        "llm_used":     use_llm,
    }

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[SummaryMgr] Saved: {path.name}  ({len(clean_texts)}/{len(session_entries)} entries kept, llm={use_llm})")
    return data


# ═════════════════════════════════════════════════════════════════════════════
#  Retrieval helpers
# ═════════════════════════════════════════════════════════════════════════════

def get_last_summary(person_name: str, exclude_session_id: str | None = None) -> dict | None:
    """
    Return the most recent completed session summary for a person.
    Pass exclude_session_id to skip the live session and get the PREVIOUS one.
    """
    d     = _person_dir(person_name)
    files = sorted(d.glob("*.json"), reverse=True)
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if exclude_session_id and data.get("session_id") == exclude_session_id:
                continue
            return data
        except Exception:
            pass
    return None


def get_by_date(person_name: str, date_query: str) -> list[dict]:
    """Return all session summaries on a given date (fuzzy date parsing)."""
    target = _parse_date(date_query)
    if not target:
        return []
    target_str = target.strftime("%Y-%m-%d")
    results = []
    for f in sorted(_person_dir(person_name).glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("date") == target_str:
                results.append(data)
        except Exception:
            pass
    return results


def list_sessions(person_name: str, limit: int = 20) -> list[dict]:
    """Return all session summaries for a person, newest first."""
    out = []
    for f in sorted(_person_dir(person_name).glob("*.json"), reverse=True)[:limit]:
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return out


def _parse_date(query: str) -> date | None:
    """Parse a fuzzy date string (ISO, month+day, 'yesterday', 'today')."""
    q = query.strip().lower()
    today = date.today()
    if q in ("today", "now"):
        return today
    if q in ("yesterday", "last day"):
        from datetime import timedelta
        return today - timedelta(days=1)
    m = re.search(r"(\d{4}-\d{2}-\d{2})", q)
    if m:
        try:
            return date.fromisoformat(m.group(1))
        except Exception:
            pass
    MONTHS = {
        "jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
        "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12,
        "january":1,"february":2,"march":3,"april":4,"june":6,
        "july":7,"august":8,"september":9,"october":10,
        "november":11,"december":12,
    }
    for mname, mnum in MONTHS.items():
        m2 = re.search(rf"{mname}\s+(\d{{1,2}})", q)
        if m2:
            try:
                return date(today.year, mnum, int(m2.group(1)))
            except Exception:
                pass
        m3 = re.search(rf"(\d{{1,2}})\s*(?:st|nd|rd|th)?\s+{mname}", q)
        if m3:
            try:
                return date(today.year, mnum, int(m3.group(1)))
            except Exception:
                pass
    return None


# ═════════════════════════════════════════════════════════════════════════════
#  Auto-finalize: ensure current session has a summary before showing last
# ═════════════════════════════════════════════════════════════════════════════

async def auto_finalize_if_new(
    person_name: str,
    session_id:  str,
    entries:     list[dict],
) -> dict | None:
    """
    If this session has ≥3 useful entries and no summary yet, generate one
    immediately using rule-based (fast, no LLM).  Used before showing 'last
    session' so the session that just happened is captured.
    """
    if _find_by_session_id(person_name, session_id):
        return None  # already done
    useful = _clean_texts([e["note"] for e in entries if e.get("session_id") == session_id and e.get("note")])
    if len(useful) < 1:
        return None  # not enough content
    return await generate_and_save(person_name, session_id, entries, use_llm=True)


# ═════════════════════════════════════════════════════════════════════════════
#  Startup backfill
# ═════════════════════════════════════════════════════════════════════════════

async def backfill_all():
    """
    Scan conversations/*.json and generate missing summary files.
    Uses rule-based only (no LLM) to avoid flooding Ollama at startup.
    Runs sequentially with small yields to avoid blocking the event loop.
    """
    if not CONVOS_DIR.exists():
        return

    total_created = 0
    for conv_file in CONVOS_DIR.glob("*.json"):
        person_name = conv_file.stem
        try:
            profile = json.loads(conv_file.read_text(encoding="utf-8"))
            entries = profile.get("entries", [])
            if not entries:
                continue

            # Group by session_id
            groups: dict[str, list[dict]] = {}
            no_session: list[dict]        = []
            for e in entries:
                sid = e.get("session_id")
                if sid:
                    groups.setdefault(sid, []).append(e)
                else:
                    no_session.append(e)

            for sid, ents in groups.items():
                if not _find_by_session_id(person_name, sid):
                    result = await generate_and_save(
                        person_name, sid, ents, use_llm=False
                    )
                    if result:
                        total_created += 1
                    await asyncio.sleep(0.02)  # yield control

            # Legacy (no session_id)
            if no_session and not _find_by_session_id(person_name, "legacy"):
                result = await generate_and_save(
                    person_name, "legacy", no_session, use_llm=False
                )
                if result:
                    total_created += 1
                await asyncio.sleep(0.02)

        except Exception as ex:
            print(f"[SummaryMgr] Backfill error for {person_name}: {ex}")

    print(f"[SummaryMgr] Backfill complete — {total_created} new summary file(s) created")
