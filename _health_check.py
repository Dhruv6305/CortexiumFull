"""Health check script for Cortexium 2.0"""
import sys, os, re
sys.path.insert(0, '.')
os.environ.setdefault('DEBUG_SKIP_AUTH', 'true')

errors = []
warnings = []

# 1. Backend import
try:
    from backend.main import app
    routes = [r.path for r in app.routes]
    vehicle_routes = [r for r in routes if r.startswith('/api/vehicle')]
    print(f"[OK] Backend imports — {len(routes)} routes registered ({len(vehicle_routes)} Vehicle routes)")
except Exception as e:
    errors.append(f"Backend import: {e}")

# 1b. Local DB
try:
    from backend.db.database import local_db
    settings = local_db.get_all("settings")
    print(f"[OK] LocalDB: path={local_db.db_path}, settings_keys={list(settings.keys())}")
except Exception as e:
    errors.append(f"LocalDB: {e}")

# 1c. Local Auth
try:
    from backend.auth.supabase_auth import get_current_user, LocalUser
    print(f"[OK] LocalAuth: using {LocalUser.__name__} — no Supabase required")
except Exception as e:
    errors.append(f"LocalAuth: {e}")

# 2. Model loader
try:
    from backend.cv.model_loader import model_loader
    s = model_loader.status
    print(f"[OK] ModelLoader: yolo={s['yolo_ready']}, deepface={s['deepface_ready']}, faces={s['registered_faces']}")
except Exception as e:
    errors.append(f"ModelLoader: {e}")

# 3. Session manager
try:
    from backend.core.session_manager import session_manager
    stats = session_manager.get_stats()
    print(f"[OK] SessionManager: active={stats['active_sessions']}")
except Exception as e:
    errors.append(f"SessionManager: {e}")

# 4. LLM client
try:
    from backend.ai.llm_client import llm_client
    print(f"[OK] LLMClient: mode={llm_client.status.get('mode', 'unknown')}, model={llm_client.status.get('model', 'none')}")
except Exception as e:
    errors.append(f"LLMClient: {e}")

# 5. Database layer
try:
    from backend.db.database import is_available, get_error
    print(f"[OK] Database: available={is_available()}, error={get_error()}")
except Exception as e:
    errors.append(f"Database: {e}")

# 6. Port consistency check
_HERE = os.path.dirname(os.path.abspath(__file__))
try:
    run_backend = open(os.path.join(_HERE, 'run_backend.py')).read()
    launch_bat  = open(os.path.join(_HERE, 'launch.bat')).read()
except FileNotFoundError as _fe:
    warnings.append(f"Port check skipped: {_fe}")
    run_backend = ""
    launch_bat  = ""
rb_port = re.search(r'port=(\d+)', run_backend)
lb_port = re.search(r'API Trace: http://localhost:(\d+)', launch_bat)
if rb_port and lb_port:
    if rb_port.group(1) == lb_port.group(1):
        print(f"[OK] Port consistency: all on :{rb_port.group(1)}")
    else:
        warnings.append(f"Port mismatch: run_backend={rb_port.group(1)}, launch.bat={lb_port.group(1)}")

print()
if errors:
    print("ERRORS:")
    for e in errors:
        print(f"  - {e}")
else:
    print("All checks passed!")
if warnings:
    print("WARNINGS:")
    for w in warnings:
        print(f"  ! {w}")
