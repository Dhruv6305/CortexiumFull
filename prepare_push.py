"""
Cortexium 2.0 — Prepare GitHub Push Script
Removes nested .git directories from cortexium and cortexium-organizer-clone
so Git tracks and uploads all their files into the main CortexiumFull repository.
"""
import os
import shutil
import stat
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent

def remove_readonly(func, path, excinfo):
    """Clear the readonly bit and reattempt removal on Windows."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception as e:
        print(f"Warning removing {path}: {e}")

def clean_nested_git():
    subrepos = [
        ROOT_DIR / "cortexium" / ".git",
        ROOT_DIR / "cortexium-organizer-clone" / ".git",
    ]
    for sub in subrepos:
        if sub.exists():
            print(f"[+] Removing nested repository metadata from: {sub}")
            shutil.rmtree(str(sub), onerror=remove_readonly)
            print(f"[✓] Successfully unlocked {sub.parent.name} for full upload.")
        else:
            print(f"[-] No nested .git found at: {sub}")

if __name__ == "__main__":
    print("=" * 60)
    print("Preparing CortexiumFull for Complete GitHub Push")
    print("=" * 60)
    clean_nested_git()
    print("\n[✓] Done. Now run push_to_github.bat to push all module files!")
