import subprocess, sys, os
r = subprocess.run(
    [sys.executable, os.path.join(os.path.dirname(__file__), "_final_test.py")],
    cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=150,
)
out = r.stdout + r.stderr
log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_final.txt")
with open(log_path, "w", encoding="utf-8") as f:
    f.write(f"RC={r.returncode}\n")
    f.write(out)
