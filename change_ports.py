#!/usr/bin/env python3
"""
Cortexium 2.0 — Port & Camera Changer Utility
==============================================
Changes the two user-facing ports AND the organizer camera source
across the entire project.

  FRONTEND  (default 3005) — The single public gateway port for all module UIs.
                              Modules open at:
                                http://localhost:FRONTEND/module/social
                                http://localhost:FRONTEND/module/organizer
                              Dashboard at:
                                http://localhost:FRONTEND

  BACKEND   (default 8005) — Unified FastAPI backend (social + organizer routes).

Internal ports (auto-computed, never exposed to users):
  Social module Vite  = FRONTEND + 1  (default 3006)
  Organizer Vite      = FRONTEND + 2  (default 3007)

Optional service ports:
  REDIS   (default 6379)
  OLLAMA  (default 11434)

Camera source (organizer module):
  CAMERA  (default 0) — local webcam index, or an IP camera URL:
    0                              → default system webcam
    1                              → second webcam
    http://192.168.1.x:8080/video  → Android IP Webcam app
    http://192.168.1.x:8080/videofeed → Android IP Webcam (MJPEG)
    http://192.168.1.x:4747/video  → DroidCam app
    rtsp://user:pass@host/stream   → RTSP camera

Usage:
    python change_ports.py                                       # Interactive mode
    python change_ports.py --frontend 4000 --backend 9000
    python change_ports.py --camera "http://192.168.1.106:8080/video"
    python change_ports.py --camera 0                            # Back to local webcam
    python change_ports.py --list                                # Show current ports + camera
    python change_ports.py --dry-run --frontend 4000             # Preview only
    python change_ports.py --no-backup --frontend 4000 --backend 9000
"""

import re
import sys
import shutil
import argparse
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent

# ─────────────────────────────────────────────────────────────────
# Files to scan & patch
# ─────────────────────────────────────────────────────────────────
TARGET_FILES = [
    # Backend
    "run_backend.py",
    "backend/main.py",
    "backend/ai/llm_client.py",
    ".env",
    # Organizer router (ports + camera source)
    "backend/routers/organizer.py",
    # Frontend gateway (dashboard)
    "dashboard/vite.config.js",
    "dashboard/src/App.jsx",
    # Social module (internal)
    "frontend-web/vite.config.ts",
    "frontend-web/src/App.jsx",
    # Organizer module (internal)
    "cortexium-organizer-clone/frontend/vite.config.js",
    "cortexium-organizer-clone/frontend/src/services/apiService.js",
    # Launch script (fully regenerated — not patched)
    # "launch.bat"  ← handled by regenerate_launch_bat()
]

# ─────────────────────────────────────────────────────────────────
# ANSI colours
# ─────────────────────────────────────────────────────────────────
G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"
C = "\033[96m"; B = "\033[1m";  D = "\033[2m"; X = "\033[0m"

# ─────────────────────────────────────────────────────────────────
# Detect current ports from source files
# ─────────────────────────────────────────────────────────────────
DEFAULTS = {"frontend": 3009, "backend": 8009, "redis": 6379, "ollama": 11434}
CAMERA_DEFAULT = "0"

def detect_ports() -> dict:
    p = dict(DEFAULTS)
    # Frontend: read dashboard vite.config.js  → port: XXXX
    dv = ROOT / "dashboard/vite.config.js"
    if dv.exists():
        m = re.search(r"port\s*:\s*(\d+)", dv.read_text(encoding="utf-8", errors="replace"))
        if m:
            p["frontend"] = int(m.group(1))
    # Backend: run_backend.py  → port=XXXX
    rb = ROOT / "run_backend.py"
    if rb.exists():
        m = re.search(r"port\s*=\s*(\d+)", rb.read_text(encoding="utf-8", errors="replace"))
        if m:
            p["backend"] = int(m.group(1))
    # Redis / Ollama from .env
    env = ROOT / ".env"
    if env.exists():
        t = env.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"REDIS_URL=redis://[^:]+:(\d+)", t)
        if m:
            p["redis"] = int(m.group(1))
        m = re.search(r"LLM_ENDPOINT=http://[^:]+:(\d+)", t)
        if m:
            p["ollama"] = int(m.group(1))
    return p


def detect_camera_source() -> str:
    """Read CAMERA_SOURCE from backend/routers/organizer.py."""
    org = ROOT / "backend/routers/organizer.py"
    if org.exists():
        t = org.read_text(encoding="utf-8", errors="replace")
        # Match: CAMERA_SOURCE: Union[int, str] = 0  or  = "http://..."
        m = re.search(r'CAMERA_SOURCE[^=]*=\s*(\d+|"[^"]*"|\'{[^\']*}\')', t)
        if not m:
            m = re.search(r'CAMERA_SOURCE[^=\n]*=\s*(\d+|"[^"]*")', t)
        if m:
            raw = m.group(1).strip('"\'')
            return raw
    return CAMERA_DEFAULT

# ─────────────────────────────────────────────────────────────────
# Build regex replacement rules
# ─────────────────────────────────────────────────────────────────
def build_rules(old: dict, new: dict) -> list[tuple]:
    rules = []

    # Derive internal ports (frontend ± offset)
    old_soc = old["frontend"] + 1
    new_soc = new["frontend"] + 1
    old_org = old["frontend"] + 2
    new_org = new["frontend"] + 2

    # ── Backend port ─────────────────────────────────────────────
    ob, nb = old["backend"], new["backend"]
    if ob != nb:
        rules += [
            (rf"\bport\s*=\s*{ob}\b",            f"port={nb}",            "backend port="),
            (rf"http://localhost:{ob}\b",          f"http://localhost:{nb}", "backend http ref"),
            (rf"ws://localhost:{ob}\b",            f"ws://localhost:{nb}",   "backend ws ref"),
            (rf"'http://localhost:{ob}'",         f"'http://localhost:{nb}'","backend http string"),
            (rf'"http://localhost:{ob}"',         f'"http://localhost:{nb}"',"backend http string dq"),
            (rf"(?<=port=){ob}\b",                str(nb),                   "backend port= generic"),
        ]

    # ── Frontend gateway port (dashboard public port) ─────────────
    of, nf = old["frontend"], new["frontend"]
    if of != nf:
        rules += [
            # dashboard/vite.config.js port: 3005
            (rf"\bport\s*:\s*{of}\b",             f"port: {nf}",           "dashboard gateway port"),
            # CORS origins in backend/main.py
            (rf"localhost:{of}\b",                f"localhost:{nf}",        f"frontend localhost:{of}"),
            (rf"127\.0\.0\.1:{of}\b",             f"127.0.0.1:{nf}",       f"frontend 127:{of}"),
            # Dashboard App.jsx footer display string
            (rf":{of}\b",                         f":{nf}",                 f"port display :{of}"),
        ]

    # ── Social internal port (frontend+1) ─────────────────────────
    if old_soc != new_soc:
        rules += [
            # frontend-web/vite.config.ts port: XXXX (the internal port)
            (rf"\bport\s*:\s*{old_soc}\b",        f"port: {new_soc}",      "social internal port"),
            # dashboard vite.config proxy target for /module/social
            (rf"localhost:{old_soc}\b",           f"localhost:{new_soc}",   f"social localhost:{old_soc}"),
            (rf"127\.0\.0\.1:{old_soc}\b",        f"127.0.0.1:{new_soc}",  f"social 127:{old_soc}"),
        ]

    # ── Organizer internal port (frontend+2) ──────────────────────
    if old_org != new_org:
        rules += [
            (rf"\bport\s*:\s*{old_org}\b",        f"port: {new_org}",      "organizer internal port"),
            # dashboard vite.config proxy target for /module/organizer
            (rf"localhost:{old_org}\b",           f"localhost:{new_org}",   f"organizer localhost:{old_org}"),
            (rf"127\.0\.0\.1:{old_org}\b",        f"127.0.0.1:{new_org}",  f"organizer 127:{old_org}"),
        ]

    # ── HMR clientPort — always equals the PUBLIC frontend gateway port ──
    # Both internal vite configs (social + organizer) set clientPort = public
    # frontend port so browser HMR requests go through the dashboard proxy.
    if of != nf:
        rules += [
            (rf"\bclientPort\s*:\s*{of}\b",       f"clientPort: {nf}",     "HMR clientPort (public)"),
        ]

    # ── Redis port ────────────────────────────────────────────────
    or_, nr = old["redis"], new["redis"]
    if or_ != nr:
        rules += [
            (rf"(redis://[^:]+):{or_}\b",         rf"\g<1>:{nr}",           "REDIS_URL"),
            (rf"localhost:{or_}\b",               f"localhost:{nr}",         f"redis localhost:{or_}"),
        ]

    # ── Ollama port ───────────────────────────────────────────────
    oo, no = old["ollama"], new["ollama"]
    if oo != no:
        rules += [
            (rf"(http://localhost):{oo}\b",        rf"\g<1>:{no}",           "LLM_ENDPOINT"),
            (rf"localhost:{oo}\b",                f"localhost:{no}",         f"ollama localhost:{oo}"),
        ]

    return rules


def build_camera_rule(old_camera: str, new_camera: str) -> list[tuple]:
    """
    Build a regex rule to patch CAMERA_SOURCE in backend/routers/organizer.py.

    Matches the line:
        CAMERA_SOURCE: Union[int, str] = 0
        CAMERA_SOURCE: Union[int, str] = "http://..."
    and replaces the value after '='.
    """
    if old_camera == new_camera:
        return []

    # New value — integer index uses bare number, URL uses quoted string
    if new_camera.isdigit():
        new_val = new_camera            # e.g. 0
    else:
        new_val = f'"{new_camera}"'    # e.g. "http://192.168.1.x:8080/video"

    # Replace the whole CAMERA_SOURCE assignment line
    # Handles both:  = 0   and   = "url..."
    pattern = r'(CAMERA_SOURCE[^=\n]*=\s*)(?:\d+|"[^"]*")'
    replacement = rf'\g<1>{new_val}'
    return [(pattern, replacement, f"camera source → {new_camera}")]

# ─────────────────────────────────────────────────────────────────
# Apply rules to one file
# ─────────────────────────────────────────────────────────────────
def update_file(fp: Path, rules: list, dry_run: bool, backup: bool) -> list[str]:
    if not fp.exists():
        return []
    original = fp.read_text(encoding="utf-8", errors="replace")
    updated = original
    changes = []
    for pattern, repl, label in rules:
        try:
            new_text, count = re.subn(pattern, repl, updated)
            if count > 0:
                changes.append(f"    {D}[{label}]{X}  {Y}{pattern!r}{X} → {G}{repl!r}{X}  ({count}×)")
                updated = new_text
        except re.error as e:
            print(f"  {R}[regex error] {pattern!r}: {e}{X}")
    if updated != original and not dry_run:
        if backup:
            shutil.copy2(fp, fp.with_suffix(fp.suffix + ".portbak"))
        fp.write_text(updated, encoding="utf-8")
    return changes

# ─────────────────────────────────────────────────────────────────
# --list: show current refs
# ─────────────────────────────────────────────────────────────────
def list_ports(ports: dict, camera: str) -> None:
    soc = ports["frontend"] + 1
    org = ports["frontend"] + 2
    all_ports = {
        f"frontend (gateway)": ports["frontend"],
        f"social (internal)":  soc,
        f"organizer (internal)": org,
        "backend":             ports["backend"],
        "redis":               ports["redis"],
        "ollama":              ports["ollama"],
    }
    print(f"\n{B}{C}─── Cortexium XR 2.0 — Current Port Map ───{X}\n")
    print(f"  {'PUBLIC':9s}  Frontend Gateway : {C}{ports['frontend']}{X}  →  http://localhost:{ports['frontend']}")
    print(f"  {'PUBLIC':9s}  Backend API      : {C}{ports['backend']}{X}  →  http://localhost:{ports['backend']}")
    print(f"  {D}{'internal':9s}  Social module    : {soc}{X}")
    print(f"  {D}{'internal':9s}  Organizer module : {org}{X}")
    cam_label = f"Local webcam (index {camera})" if camera.isdigit() else f"IP Camera: {camera}"
    print(f"  {'CAMERA':9s}  Organizer source : {C}{cam_label}{X}")
    print()
    files_with_hits = 0
    all_scan = list(TARGET_FILES) + ["launch.bat"]
    for rel in all_scan:
        fp = ROOT / rel
        if not fp.exists():
            continue
        content = fp.read_text(encoding="utf-8", errors="replace")
        file_printed = False
        for label, port in all_ports.items():
            hits = [(i+1, l.rstrip()) for i, l in enumerate(content.splitlines())
                    if re.search(rf"(?<!\d){port}(?!\d)", l)]
            if hits:
                if not file_printed:
                    print(f"  {B}{rel}{X}")
                    file_printed = True
                    files_with_hits += 1
                print(f"    {Y}[{label}:{port}]{X}")
                for lineno, line in hits:
                    print(f"      L{lineno:04d}  {line.strip()[:120]}")
        if file_printed:
            print()
    print(f"{C}Scanned {len(all_scan)} files, {files_with_hits} had port references.{X}\n")

# ─────────────────────────────────────────────────────────────────
# Regenerate launch.bat from scratch with new ports
# ─────────────────────────────────────────────────────────────────
def regenerate_launch_bat(ports: dict, dry_run: bool, backup: bool) -> None:
    fe  = ports["frontend"]
    be  = ports["backend"]
    soc = fe + 1   # social internal
    org = fe + 2   # organizer internal

    content = f"""@echo off
title Cortexium 2.0 - Master Launcher
echo ==========================================
echo    CORTEXIUM XR 2.0 -- MASTER LAUNCHER
echo ==========================================
echo.
echo   Frontend  : http://localhost:{fe}
echo   Backend   : http://localhost:{be}
echo.

:: Clean up old processes
echo [+] Clearing previous sessions...
taskkill /f /im python.exe /t >nul 2>&1
taskkill /f /im node.exe /t >nul 2>&1

:: Check Ollama (optional - skip if not installed)
where ollama >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] Ollama not found - LLM will use fallback mode
    echo.
) else (
    echo [+] Ollama detected.
    ollama list | findstr "llama3" >nul
    if %errorlevel% equ 0 (echo [+] llama3 ready.) else (
        ollama list | findstr "mistral" >nul
        if %errorlevel% equ 0 (echo [+] mistral ready.) else (
            echo [!] Pulling llama3 in background...
            start "Ollama Setup" cmd /c "ollama pull llama3"
        )
    )
    echo.
)

:: ──────────────────────────────────────────────────────────
:: 1. Unified Backend  (Port {be})
::    Serves:  /api/*         Social module routes
::             /organizer/*   Organizer module routes
:: ──────────────────────────────────────────────────────────
echo [1/4] Launching Unified Backend (Port {be})...
start "Backend [{be}]" cmd /k "cd /d %~dp0 && .venv\\Scripts\\activate && python run_backend.py"

echo [+] Waiting 8s for backend to start...
timeout /t 8 /nobreak >nul

:: ──────────────────────────────────────────────────────────
:: 2. Social Module  (internal Port {soc})
::    Accessible at: http://localhost:{fe}/module/social
:: ──────────────────────────────────────────────────────────
echo [2/4] Launching Social Module (internal Port {soc})...
start "Social [:{soc}]" cmd /k "cd /d %~dp0frontend-web && npm run dev -- --port {soc}"

:: ──────────────────────────────────────────────────────────
:: 3. Organizer Module  (internal Port {org})
::    Accessible at: http://localhost:{fe}/module/organizer
:: ──────────────────────────────────────────────────────────
echo [3/4] Launching Organizer Module (internal Port {org})...
start "Organizer [:{org}]" cmd /k "cd /d %~dp0cortexium-organizer-clone\\frontend && npm run dev -- --port {org}"

:: Wait for internal Vite servers to start
timeout /t 5 /nobreak >nul

:: ──────────────────────────────────────────────────────────
:: 4. Central Dashboard (public Port {fe}) — opens the browser
::    This is the ONLY port users need.
::    Routes all module traffic through Vite proxy.
:: ──────────────────────────────────────────────────────────
echo [4/5] Launching Frontend Gateway (Port {fe})...
start "Dashboard [{fe}]" cmd /k "cd /d %~dp0dashboard && npm run dev -- --port {fe}"

timeout /t 3 /nobreak >nul

:: ──────────────────────────────────────────────────────────
:: 5. Cloudflare Tunnel (Public HTTPS Website for Remote Laptops)
:: ──────────────────────────────────────────────────────────
echo [5/5] Launching Cloudflare Public HTTPS Tunnel...
where cloudflared >nul 2>nul
if %errorlevel% equ 0 (
    start "Cloudflare Tunnel" cmd /k "cloudflared tunnel --url http://localhost:{fe} --protocol http2"
) else (
    start "Cloudflare Tunnel" cmd /k "npx cloudflared tunnel --url http://localhost:{fe} --protocol http2"
)

echo.
echo ==========================================
echo    ALL SYSTEMS UP
echo ==========================================
echo.
echo   >> LOCAL BROWSER:     http://localhost:{fe}
echo   >> PUBLIC REMOTE HTTPS LINK WILL BE PRINTED IN THE
echo      'Cloudflare Tunnel' WINDOW ABOVE!
echo.
echo   Dashboard            http://localhost:{fe}
echo   Social Module        http://localhost:{fe}/module/social
echo   Organizer Module     http://localhost:{fe}/module/organizer
echo.
echo   Backend API          http://localhost:{be}
echo   API Docs             http://localhost:{be}/docs
echo   Social WS            ws://localhost:{fe}/ws
echo   Organizer WS         ws://localhost:{fe}/organizer/ws
echo.
echo   To change ports:     python change_ports.py
echo ==========================================
pause
"""
    bat = ROOT / "launch.bat"
    if not dry_run:
        if backup and bat.exists():
            shutil.copy2(bat, bat.with_suffix(".bat.portbak"))
        bat.write_text(content, encoding="utf-8")
        print(f"  {G}[OK]{X}  launch.bat  (regenerated: frontend={fe}, backend={be}, social={soc}, organizer={org})")
    else:
        print(f"  {Y}[DRY]{X}  launch.bat  (would regenerate)")

# ─────────────────────────────────────────────────────────────────
# Interactive mode
# ─────────────────────────────────────────────────────────────────
def interactive(current: dict, current_camera: str) -> tuple:
    soc = current["frontend"] + 1
    org = current["frontend"] + 2
    cam_label = f"Local webcam (index {current_camera})" if current_camera.isdigit() else f"IP: {current_camera}"
    print(f"\n{B}{C}─── Cortexium XR 2.0 — Port & Camera Changer ───{X}")
    print(f"\n  Current layout:")
    print(f"    {C}Frontend (public){X}  :  {current['frontend']}    → http://localhost:{current['frontend']}")
    print(f"    {D}Social (internal){X}  :  {soc}    (auto: frontend+1)")
    print(f"    {D}Organizer (internal){X}:  {org}    (auto: frontend+2)")
    print(f"    {C}Backend (public){X}   :  {current['backend']}    → http://localhost:{current['backend']}")
    print(f"    {C}Camera source{X}     :  {cam_label}")
    print(f"\n  Press {Y}ENTER{X} to keep current value.\n")
    new = dict(current)
    for key, desc in [("frontend", "Single public frontend port"), ("backend", "Backend API port"),
                      ("redis", "Redis port (optional)"), ("ollama", "Ollama port (optional)")]:
        while True:
            raw = input(f"  {B}{key.upper():10s}{X}  [{Y}{current[key]}{X}]  {D}{desc}{X}: ").strip()
            if not raw:
                break
            if raw.isdigit() and 1024 <= int(raw) <= 65535:
                new[key] = int(raw)
                break
            print(f"  {R}  Must be 1024–65535.{X}")
        print()

    # Camera source prompt
    print(f"  {B}{'CAMERA':10s}{X}  [{Y}{current_camera}{X}]  {D}Camera source: 0=local webcam, or full IP URL{X}")
    print(f"  {D}  Examples: 0   1   http://192.168.1.x:8080/video   http://192.168.1.x:4747/video{X}")
    new_camera = input(f"  {'':10s}  : ").strip() or current_camera
    print()

    return new, new_camera

# ─────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        description="Cortexium XR 2.0 — Change ports + camera source (frontend + backend + organizer camera)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--frontend", type=int,   metavar="PORT", help="Public frontend gateway port (default 3005)")
    ap.add_argument("--backend",  type=int,   metavar="PORT", help="Backend API port (default 8005)")
    ap.add_argument("--redis",    type=int,   metavar="PORT", help="Redis port (default 6379)")
    ap.add_argument("--ollama",   type=int,   metavar="PORT", help="Ollama port (default 11434)")
    ap.add_argument("--camera",   type=str,   metavar="SRC",
                    help="Organizer camera source: 0 (local webcam), 1, or a URL "
                         "(e.g. http://192.168.1.x:8080/video)")
    ap.add_argument("--list",     action="store_true", help="Show all current port + camera references")
    ap.add_argument("--dry-run",  action="store_true", help="Preview without writing files")
    ap.add_argument("--no-backup",action="store_true", help="Skip .portbak backup files")
    args = ap.parse_args()

    current = detect_ports()
    current_camera = detect_camera_source()

    if args.list:
        list_ports(current, current_camera)
        # Also scan TARGET_FILES for port references (original behaviour)
        soc = current["frontend"] + 1
        org = current["frontend"] + 2
        all_ports = {
            "frontend (gateway)": current["frontend"],
            "social (internal)":  soc,
            "organizer (internal)": org,
            "backend":             current["backend"],
            "redis":               current["redis"],
            "ollama":              current["ollama"],
        }
        files_with_hits = 0
        all_scan = list(TARGET_FILES) + ["launch.bat"]
        for rel in all_scan:
            fp = ROOT / rel
            if not fp.exists():
                continue
            content = fp.read_text(encoding="utf-8", errors="replace")
            file_printed = False
            for label, port in all_ports.items():
                hits = [(i+1, l.rstrip()) for i, l in enumerate(content.splitlines())
                        if re.search(rf"(?<!\d){port}(?!\d)", l)]
                if hits:
                    if not file_printed:
                        print(f"  {B}{rel}{X}")
                        file_printed = True
                        files_with_hits += 1
                    print(f"    {Y}[{label}:{port}]{X}")
                    for lineno, line in hits:
                        print(f"      L{lineno:04d}  {line.strip()[:120]}")
            if file_printed:
                print()
        print(f"{C}Scanned {len(all_scan)} files, {files_with_hits} had port references.{X}\n")
        return

    cli_ports  = any(getattr(args, k) for k in ["frontend","backend","redis","ollama"])
    cli_camera = args.camera is not None

    if cli_ports or cli_camera:
        new = {
            "frontend": args.frontend or current["frontend"],
            "backend":  args.backend  or current["backend"],
            "redis":    args.redis    or current["redis"],
            "ollama":   args.ollama   or current["ollama"],
        }
        new_camera = args.camera.strip() if cli_camera else current_camera
    else:
        new, new_camera = interactive(current, current_camera)

    # Validate ports
    for k, v in new.items():
        if not (1024 <= v <= 65535):
            print(f"{R}Error: {k}={v} is out of range (1024-65535).{X}"); sys.exit(1)

    # Conflict check (only check user-facing ports + their auto-derived internals)
    fe_new = new["frontend"]
    check = {
        "frontend (gateway)": fe_new,
        "social (internal)":  fe_new + 1,
        "organizer (internal)": fe_new + 2,
        "backend":            new["backend"],
    }
    seen: dict[int, str] = {}
    for label, port in check.items():
        if port in seen:
            print(f"{R}Error: {label} and {seen[port]} both resolve to port {port}.{X}"); sys.exit(1)
        seen[port] = label

    # Summary
    print(f"\n{B}{C}─── Change Plan ───{X}")
    old_soc, new_soc = current["frontend"]+1, new["frontend"]+1
    old_org, new_org = current["frontend"]+2, new["frontend"]+2
    rows = [
        ("Frontend (gateway)", current["frontend"], new["frontend"], True),
        ("  Social (internal)",   old_soc,          new_soc,          False),
        ("  Organizer (internal)",old_org,           new_org,          False),
        ("Backend",            current["backend"],  new["backend"],   True),
        ("Redis",              current["redis"],    new["redis"],     True),
        ("Ollama",             current["ollama"],   new["ollama"],    True),
    ]
    any_change = False
    for label, old_p, new_p, public in rows:
        changed = old_p != new_p
        if changed: any_change = True
        pfx = "" if public else D
        sfx = X if not public else ""
        if changed:
            print(f"  {pfx}{label:26s}{sfx}  {Y}{old_p}{X}  →  {G}{new_p}{X}")
        else:
            print(f"  {D}{label:26s}  {old_p}  (unchanged){X}")

    camera_changed = new_camera != current_camera
    if camera_changed:
        any_change = True
        old_cam_lbl = f"Local webcam ({current_camera})" if current_camera.isdigit() else current_camera
        new_cam_lbl = f"Local webcam ({new_camera})"    if new_camera.isdigit()     else new_camera
        print(f"  {'Camera source':26s}  {Y}{old_cam_lbl}{X}  →  {G}{new_cam_lbl}{X}")
    else:
        cam_lbl = f"Local webcam ({current_camera})" if current_camera.isdigit() else current_camera
        print(f"  {D}{'Camera source':26s}  {cam_lbl}  (unchanged){X}")

    if not any_change:
        print(f"\n{G}No changes — nothing to do.{X}"); return

    if args.dry_run:
        print(f"\n{Y}[DRY RUN] — no files will be modified.{X}")
    confirm = input(f"\n{B}Proceed? [y/N]: {X}").strip().lower()
    if confirm not in ("y", "yes"):
        print("Aborted."); return

    rules = build_rules(current, new)
    if camera_changed:
        rules += build_camera_rule(current_camera, new_camera)

    print(f"\n{B}Updating files...{X}")
    total = 0
    for rel in TARGET_FILES:
        fp = ROOT / rel
        if not fp.exists():
            print(f"  {D}SKIP  {rel}{X}"); continue
        changes = update_file(fp, rules, args.dry_run, not args.no_backup)
        if changes:
            marker = f"{Y}[DRY]{X}" if args.dry_run else f"{G}[OK] {X}"
            print(f"  {marker}  {B}{rel}{X}")
            for c in changes: print(c)
            total += 1
        else:
            print(f"  {D}[--]  {rel}{X}")

    print()
    regenerate_launch_bat(new, args.dry_run, not args.no_backup)

    label = "[DRY RUN] " if args.dry_run else ""
    print(f"\n{B}{label}Done! {total+1} file(s) updated.{X}")

    if not args.dry_run:
        fe, be = new["frontend"], new["backend"]
        cam_lbl = f"Local webcam (index {new_camera})" if new_camera.isdigit() else f"IP Camera: {new_camera}"
        print(f"""
{B}─── New Endpoints ───{X}
  {C}http://localhost:{fe}{X}                   → Dashboard (entry point)
  {C}http://localhost:{fe}/module/social{X}     → Social module
  {C}http://localhost:{fe}/module/organizer{X}  → Organizer module
  {C}http://localhost:{be}{X}                   → Backend API
  {C}http://localhost:{be}/docs{X}              → Swagger docs

  Internal (auto):  Social={fe+1}  Organizer={fe+2}
  Organizer Camera: {cam_lbl}

{Y}Run:  launch.bat{X}
""")
        if not args.no_backup:
            print(f"{D}Remove backups:  Get-ChildItem -Recurse -Filter *.portbak | Remove-Item{X}")

if __name__ == "__main__":
    main()
