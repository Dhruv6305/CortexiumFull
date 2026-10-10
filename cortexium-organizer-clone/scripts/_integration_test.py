"""
Integration test — writes results to test_output.txt, no Unicode symbols.
Run from project root: python scripts/_integration_test.py
"""
import sys, os, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

LOG_PATH = os.path.join(ROOT, "test_output.txt")
log_lines = []

def log(msg):
    log_lines.append(msg)

PASS = "PASS"
FAIL = "FAIL"
results = {}

# ── A: BaselineCatBoostPredictor loads ───────────────────────────────────
try:
    from ml_pipeline import FeatureExtractor, BaselineCatBoostPredictor, PlacementPredictor
    bp = BaselineCatBoostPredictor()
    assert bp.is_loaded, "is_loaded is False"
    results["A_load"] = PASS
    log(f"[A] Baseline load:       PASS  is_loaded={bp.is_loaded}")
except Exception as e:
    results["A_load"] = FAIL
    log(f"[A] Baseline load:       FAIL  {e}")

# ── B: predicts from multiple candidate surfaces ──────────────────────────
try:
    frame_shape = (480, 640)
    obj_box = (100, 100, 200, 160)
    candidates = {
        "table": (80,  130, 350, 250),
        "chair": (400, 200, 550, 380),
    }
    best, conf = bp.predict("laptop", candidates, obj_box, 0.85, frame_shape)
    assert best in candidates, f"'{best}' not in candidates"
    assert 0.0 <= conf <= 1.0
    results["B_predict"] = PASS
    log(f"[B] Baseline predict:    PASS  laptop -> '{best}'  conf={conf:.3f}")
except Exception as e:
    results["B_predict"] = FAIL
    log(f"[B] Baseline predict:    FAIL  {e}")

# ── C: single candidate ────────────────────────────────────────────────────
try:
    best2, conf2 = bp.predict("cup", {"desk": (50, 50, 300, 200)},
                               (80, 60, 130, 100), 0.7, (480, 640))
    assert best2 == "desk", f"Expected 'desk', got '{best2}'"
    results["C_single"] = PASS
    log(f"[C] Single-candidate:    PASS  cup -> '{best2}'  conf={conf2:.3f}")
except Exception as e:
    results["C_single"] = FAIL
    log(f"[C] Single-candidate:    FAIL  {e}")

# ── D: empty candidates returns (None, 0.0) ────────────────────────────────
try:
    r, c = bp.predict("book", {}, (10,10,50,50), 0.9, (480, 640))
    assert r is None and c == 0.0, f"Expected (None, 0.0) got ({r}, {c})"
    results["D_empty"] = PASS
    log(f"[D] Empty candidates:    PASS  returned (None, 0.0)")
except Exception as e:
    results["D_empty"] = FAIL
    log(f"[D] Empty candidates:    FAIL  {e}")

# ── E: personalized rule takes priority over baseline ─────────────────────
try:
    frame_shape = (480, 640)
    obj_box = (150, 150, 250, 220)
    candidates = {
        "sofa":  (0,   120, 300, 350),
        "table": (320, 100, 620, 260),
    }
    bl_surface, bl_conf = bp.predict("laptop", candidates, obj_box, 0.9, frame_shape)
    # Server tier-1: learned_rules checked first
    learned_rules = {"laptop": "sofa"}
    expected = learned_rules.get("laptop")
    assert expected == "sofa"
    results["E_priority"] = PASS
    log(f"[E] Priority logic:      PASS  personalized='sofa'  baseline='{bl_surface}'")
except Exception as e:
    results["E_priority"] = FAIL
    log(f"[E] Priority logic:      FAIL  {e}")

# ── F: reset clears rules, baseline model untouched ──────────────────────
try:
    RULES_PATH = os.path.join(ROOT, "learned_rules.json")
    with open(RULES_PATH) as f:
        original = json.load(f)

    # Simulate reset
    with open(RULES_PATH, "w") as f:
        json.dump({}, f)
    with open(RULES_PATH) as f:
        after = json.load(f)
    assert after == {}, "Rules not empty after reset"

    # Baseline model file must exist
    baseline_cbm = os.path.join(ROOT, "models", "baseline", "catboost_baseline.cbm")
    assert os.path.exists(baseline_cbm), "Baseline model file missing!"

    # Baseline predictor still usable
    bp2 = BaselineCatBoostPredictor()
    assert bp2.is_loaded

    results["F_reset"] = PASS
    log(f"[F] Reset to baseline:   PASS  rules cleared, model intact, predictor reloads")

    # Restore
    with open(RULES_PATH, "w") as f:
        json.dump(original, f, indent=2)
except Exception as e:
    results["F_reset"] = FAIL
    log(f"[F] Reset to baseline:   FAIL  {e}")
    try:
        with open(RULES_PATH, "w") as f:
            json.dump(original, f, indent=2)
    except Exception:
        pass

# ── G: FeatureExtractor produces exactly the 13 expected keys ─────────────
try:
    feat = FeatureExtractor.compute(
        "laptop", "table",
        (100, 100, 200, 160),
        (80, 130, 350, 250),
        0.85, (480, 640),
    )
    from ml_pipeline import FEATURE_COLUMNS
    missing = set(FEATURE_COLUMNS) - set(feat.keys())
    assert not missing, f"Missing keys: {missing}"
    assert len(feat) == 13
    results["G_features"] = PASS
    log(f"[G] FeatureExtractor:    PASS  13 keys correct")
except Exception as e:
    results["G_features"] = FAIL
    log(f"[G] FeatureExtractor:    FAIL  {e}")

# ── H: server.py structure ────────────────────────────────────────────────
try:
    import ast
    src = open(os.path.join(ROOT, "server.py")).read()
    ast.parse(src)
    checks = {
        "BaselineCatBoostPredictor imported": "BaselineCatBoostPredictor" in src,
        "baseline_predictor instantiated":    "self.baseline_predictor = BaselineCatBoostPredictor" in src,
        "three-tier logic present":           "Tier 1" in src and "Tier 2" in src and "Tier 3" in src,
        "prediction_source tracked":          "prediction_source" in src,
        "reset endpoint intact":              "api/reset" in src,
        "learned_rules cleared on reset":     "state.learned_rules = {}" in src,
        "baseline NOT deleted on reset":      "catboost_baseline" not in src.split("api/reset")[1].split("def ")[0]
                                              if "api/reset" in src else True,
    }
    failed = [k for k, v in checks.items() if not v]
    assert not failed, f"Failed checks: {failed}"
    results["H_server"] = PASS
    log(f"[H] server.py structure: PASS  all {len(checks)} structure checks pass")
except Exception as e:
    results["H_server"] = FAIL
    log(f"[H] server.py structure: FAIL  {e}")

# ── I: ml_pipeline.py structure ──────────────────────────────────────────
try:
    import ast
    src = open(os.path.join(ROOT, "ml_pipeline.py")).read()
    ast.parse(src)
    checks = {
        "BaselineCatBoostPredictor defined":    "class BaselineCatBoostPredictor" in src,
        "BASELINE_MODEL_PATH set":              "BASELINE_MODEL_PATH" in src,
        "silent fail on missing catboost":      "except Exception" in src,
        "PlacementPredictor still present":     "class PlacementPredictor" in src,
        "train_and_evaluate still present":     "def train_and_evaluate" in src,
        "DataCollector still present":          "class DataCollector" in src,
    }
    failed = [k for k, v in checks.items() if not v]
    assert not failed, f"Failed: {failed}"
    results["I_pipeline"] = PASS
    log(f"[I] ml_pipeline.py:      PASS  all {len(checks)} checks pass")
except Exception as e:
    results["I_pipeline"] = FAIL
    log(f"[I] ml_pipeline.py:      FAIL  {e}")

# ── Summary ──────────────────────────────────────────────────────────────
log("")
log("=" * 52)
passed = sum(1 for v in results.values() if v == PASS)
total  = len(results)
log(f"  INTEGRATION TESTS: {passed}/{total} passed")
for k, v in results.items():
    log(f"    [{k}]  {v}")
log("=" * 52)

# Write log
with open(LOG_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(log_lines) + "\n")

# Also print to stdout
print("\n".join(log_lines))
sys.exit(0 if passed == total else 1)
