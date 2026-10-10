"""
Cortexium 2.0 — Local JSON Database
=====================================
Replaces Supabase with a lightweight on-disk JSON store.
No external services, no API keys, no internet required.

Storage layout (all under backend/data/):
  db/
    settings.json       — app-wide settings (persistent)
    user_profile.json   — local user profile
    known_persons.json  — curated list of registered persons

The encounter log + session data are managed by SessionManager (separate).
The face image DB is managed by ModelLoader (separate).

Usage:
    from backend.db.database import local_db
    local_db.get("settings", "theme", default="dark")
    local_db.set("settings", "theme", "dark")
"""
import json
import os
import threading
from pathlib import Path
from typing import Any, Optional

# ── Storage root ────────────────────────────────────────────────────────────
_DB_DIR = Path(__file__).resolve().parent.parent / "data" / "db"
_DB_DIR.mkdir(parents=True, exist_ok=True)

# Default schemas written on first run
_DEFAULTS: dict[str, dict] = {
    "settings": {
        "theme": "dark",
        "hud_opacity": 0.92,
        "frame_interval_ms": 1500,
        "vlm_enabled": True,
        "voice_enabled": True,
        "auto_register": False,
        "hazard_alerts": True,
    },
    "user_profile": {
        "display_name": "Cortexium User",
        "email": "admin@cortexium.local",
        "created_at": None,
        "total_sessions": 0,
    },
    "known_persons": {
        "persons": []
    },
}


class LocalDatabase:
    """
    Thread-safe, file-backed JSON key-value store.
    Each 'table' is a separate JSON file in backend/data/db/.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._cache: dict[str, dict] = {}
        self._init_defaults()
        print(f"[LocalDB] Initialized at: {_DB_DIR}")

    def _init_defaults(self):
        """Create default JSON files if they don't exist yet."""
        for table, defaults in _DEFAULTS.items():
            fp = _DB_DIR / f"{table}.json"
            if not fp.exists():
                fp.write_text(json.dumps(defaults, indent=2))
                print(f"[LocalDB] Created default table: {table}.json")

    def _load(self, table: str) -> dict:
        """Load a table from disk into the in-memory cache."""
        if table in self._cache:
            return self._cache[table]
        fp = _DB_DIR / f"{table}.json"
        if fp.exists():
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                self._cache[table] = data
                return data
            except Exception as e:
                print(f"[LocalDB] Load error ({table}): {e}")
        return {}

    def _save(self, table: str, data: dict):
        """Persist a table to disk."""
        fp = _DB_DIR / f"{table}.json"
        try:
            fp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"[LocalDB] Save error ({table}): {e}")

    # ── Public API ───────────────────────────────────────────────────────────

    def get(self, table: str, key: str, default: Any = None) -> Any:
        """Get a value from a table by key."""
        with self._lock:
            data = self._load(table)
            return data.get(key, default)

    def set(self, table: str, key: str, value: Any):
        """Set a value in a table and persist to disk."""
        with self._lock:
            data = self._load(table)
            data[key] = value
            self._cache[table] = data
            self._save(table, data)

    def get_all(self, table: str) -> dict:
        """Return the full contents of a table."""
        with self._lock:
            return dict(self._load(table))

    def update(self, table: str, updates: dict):
        """Merge multiple keys into a table at once."""
        with self._lock:
            data = self._load(table)
            data.update(updates)
            self._cache[table] = data
            self._save(table, data)

    def delete(self, table: str, key: str):
        """Remove a key from a table."""
        with self._lock:
            data = self._load(table)
            data.pop(key, None)
            self._cache[table] = data
            self._save(table, data)

    def table_exists(self, table: str) -> bool:
        return (_DB_DIR / f"{table}.json").exists()

    def invalidate_cache(self, table: Optional[str] = None):
        """Force a re-read from disk on next access."""
        with self._lock:
            if table:
                self._cache.pop(table, None)
            else:
                self._cache.clear()

    @property
    def db_path(self) -> str:
        return str(_DB_DIR)


# ── Module-level singleton ──────────────────────────────────────────────────
local_db = LocalDatabase()


# ── Legacy shims (keeps any code that imports the old Supabase helpers working)
def get_supabase():
    return None

def get_supabase_admin():
    return None

def is_available() -> bool:
    return False

def get_error() -> Optional[str]:
    return None
