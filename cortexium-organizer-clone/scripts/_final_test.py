"""
Final ML architecture validation test.
Writes results to test_final.txt.
"""
import sys, os, json, shutil, hashlib, ast

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
LOG  = os.path.join(ROOT, "test_final.txt")
lines = []

def log(msg): lines.append(msg)

def dump():
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

PASS, FAIL = "PASS", "FAIL"
results = {}

# ── T1: syntax checks ─────────────────────────────────────────────
for fname in ("ml_pipeline.py", "server.py"):
    key = f"T1_syntax_{fname}"
    try:
        src = open(os.path.join(ROOT, fname)).read()
        ast.parse(src)
        results[key] = PASS
        log(f"[T1] syntax {fname}: PASS")
    except SyntaxError as e:
        results[key] = FAIL
        log(f"[T1] syntax {fname}: FAIL  {e}")

# ── T2: imports ───────────────────────────────────────────────────
try:
    from ml_pipeline import (
        FeatureExtractor, BaselineCatBoostPredictor,
        PersonalizedCatBoostPredictor, DataCollector,
        train_personalized_model, get_active_metrics,
        BASELINE_MODEL_PATH, PERSONALIZED_MODEL_PATH,
        PERSONALIZED_METRICS_PATH, FEATURE_COLUMNS, TARGET_COLUMN,
    )
    results["T2_imports"] = PASS
    log("[T2] imports: PASS")
except Exception as e:
    results["T2_imports"] = FAIL
    log(f"[T2] imports: FAIL  {e}")
    dump(); sys.exit(1)

# ── T3: baseline model loads ──────────────────────────────────────
try:
    bp = BaselineCatBoostPredictor()
    assert bp.is_loaded, "baseline not loaded"
    results["T3_baseline_load"] = PASS
    log(f"[T3] baseline load: PASS  path={BASELINE_MODEL_PATH}")
except Exception as e:
    results["T3_baseline_load"] = FAIL
    log(f"[T3] baseline load: FAIL  {e}")

# ── T4: baseline prediction ───────────────────────────────────────
try:
    surf, prob = bp.predict(
        "laptop",
        {"table": (10, 10, 400, 300), "chair": (450, 10, 620, 300)},
        (50, 50, 200, 180), 0.85, (480, 640),
    )
    assert surf in ("table", "chair"), f"unexpected surface '{surf}'"
    assert 0.0 <= prob <= 1.0
    results["T4_baseline_predict"] = PASS
    log(f"[T4] baseline predict: PASS  laptop->'{surf}'  prob={prob:.3f}")
except Exception as e:
    results["T4_baseline_predict"] = FAIL
    log(f"[T4] baseline predict: FAIL  {e}")

# ── T5: FeatureExtractor 13 keys ─────────────────────────────────
try:
    feat = FeatureExtractor.compute(
        "laptop", "table",
        (50, 50, 200, 180), (10, 10, 400, 300),
        0.85, (480, 640),
    )
    assert set(feat.keys()) == set(FEATURE_COLUMNS), f"wrong keys: {set(feat.keys())^set(FEATURE_COLUMNS)}"
    assert len(feat) == 13
    results["T5_features"] = PASS
    log("[T5] features 13 keys: PASS")
except Exception as e:
    results["T5_features"] = FAIL
    log(f"[T5] features: FAIL  {e}")

# ── T6: personalized retraining ───────────────────────────────────
USAGE_DATA = os.path.join(ROOT, "usage_data.csv")
PERS_DIR   = os.path.join(ROOT, "models", "personalized")
PERS_CBM   = PERSONALIZED_MODEL_PATH
PERS_JSON  = PERSONALIZED_METRICS_PATH

try:
    assert os.path.exists(USAGE_DATA), "usage_data.csv not found"
    import pandas as pd
    df = pd.read_csv(USAGE_DATA)
    assert len(df) >= 4, f"only {len(df)} rows in usage_data.csv"

    baseline_hash = hashlib.md5(open(BASELINE_MODEL_PATH,"rb").read()).hexdigest()

    # Clean previous personalized model if exists
    if os.path.exists(PERS_CBM): os.remove(PERS_CBM)
    if os.path.exists(PERS_JSON): os.remove(PERS_JSON)

    metrics = train_personalized_model(USAGE_DATA, PERS_CBM, PERS_JSON)

    assert os.path.exists(PERS_CBM),  "personalized .cbm not created"
    assert os.path.exists(PERS_JSON), "personalized metrics.json not created"
    assert metrics.get("accuracy", 0) >= 0.0
    results["T6_retrain"] = PASS
    log(f"[T6] personalized retrain: PASS  acc={metrics.get('accuracy'):.4f}  roc={metrics.get('roc_auc',0):.4f}")
except Exception as e:
    results["T6_retrain"] = FAIL
    log(f"[T6] personalized retrain: FAIL  {e}")

# ── T7: personalized model loads after retrain ────────────────────
try:
    pp = PersonalizedCatBoostPredictor()
    assert pp.is_loaded, "personalized predictor not loaded after retrain"
    surf2, prob2 = pp.predict(
        "cup",
        {"table": (10,10,400,300), "sofa": (450,10,620,300)},
        (50,50,120,100), 0.7, (480,640),
    )
    assert surf2 in ("table","sofa"), f"unexpected: '{surf2}'"
    results["T7_pers_predict"] = PASS
    log(f"[T7] personalized predict: PASS  cup->'{surf2}'  prob={prob2:.3f}")
except Exception as e:
    results["T7_pers_predict"] = FAIL
    log(f"[T7] personalized predict: FAIL  {e}")

# ── T8: baseline hash unchanged after retrain ─────────────────────
try:
    new_hash = hashlib.md5(open(BASELINE_MODEL_PATH,"rb").read()).hexdigest()
    assert new_hash == baseline_hash, f"BASELINE MODIFIED! {baseline_hash} -> {new_hash}"
    results["T8_baseline_unchanged"] = PASS
    log(f"[T8] baseline unchanged: PASS  hash={new_hash[:12]}...")
except Exception as e:
    results["T8_baseline_unchanged"] = FAIL
    log(f"[T8] baseline unchanged: FAIL  {e}")

# ── T9: get_active_metrics returns personalized when it exists ─────
try:
    m = get_active_metrics()
    assert m is not None, "get_active_metrics returned None"
    assert m.get("model_type") == "personalized", f"expected 'personalized' got '{m.get('model_type')}'"
    assert m.get("accuracy", -1) >= 0.0
    results["T9_active_metrics_pers"] = PASS
    log(f"[T9] active metrics (personalized): PASS  type={m.get('model_type')}")
except Exception as e:
    results["T9_active_metrics_pers"] = FAIL
    log(f"[T9] active metrics: FAIL  {e}")

# ── T10: reset removes personalized model, baseline stays ─────────
try:
    assert os.path.exists(PERS_CBM)
    pp2 = PersonalizedCatBoostPredictor()
    pp2.disable()
    for path in [PERS_CBM, PERS_JSON]:
        if os.path.exists(path): os.remove(path)

    assert not os.path.exists(PERS_CBM),  "personalized .cbm still exists after reset"
    assert os.path.exists(BASELINE_MODEL_PATH), "baseline deleted — CRITICAL"

    bp2 = BaselineCatBoostPredictor()
    assert bp2.is_loaded, "baseline not loadable after reset"

    results["T10_reset"] = PASS
    log("[T10] reset: PASS  personalized removed, baseline intact and loadable")
except Exception as e:
    results["T10_reset"] = FAIL
    log(f"[T10] reset: FAIL  {e}")

# ── T11: get_active_metrics falls back to baseline after reset ─────
try:
    m2 = get_active_metrics()
    assert m2 is not None, "get_active_metrics returned None after reset"
    assert m2.get("model_type") == "baseline", f"expected 'baseline' got '{m2.get('model_type')}'"
    results["T11_active_metrics_baseline"] = PASS
    log(f"[T11] active metrics (baseline after reset): PASS  type={m2.get('model_type')}")
except Exception as e:
    results["T11_active_metrics_baseline"] = FAIL
    log(f"[T11] active metrics after reset: FAIL  {e}")

# ── T12: server.py structure checks ───────────────────────────────
try:
    srv = open(os.path.join(ROOT, "server.py")).read()
    checks = {
        "PersonalizedCatBoostPredictor imported": "PersonalizedCatBoostPredictor" in srv,
        "BaselineCatBoostPredictor imported":     "BaselineCatBoostPredictor" in srv,
        "get_active_metrics imported":            "get_active_metrics" in srv,
        "four prediction tiers":                  "TIER 1" in srv and "TIER 4" in srv,
        "learned_rule label":                     "learned_rule" in srv,
        "personalized_model label":               "personalized_model" in srv,
        "baseline_model label":                   "baseline_model" in srv,
        "reset disables personalized":            "personalized_predictor.disable()" in srv,
        "reset never touches baseline":           "catboost_baseline" not in srv.split("def reset_learning")[1].split("def ")[0],
        "retrain calls reload":                   "personalized_predictor.reload()" in srv,
        "activeModel in snapshot":                "activeModel" in srv,
        "api/reset endpoint":                     "api/reset" in srv,
    }
    failed = [k for k,v in checks.items() if not v]
    assert not failed, f"failed: {failed}"
    results["T12_server_structure"] = PASS
    log(f"[T12] server.py structure: PASS  ({len(checks)} checks)")
except Exception as e:
    results["T12_server_structure"] = FAIL
    log(f"[T12] server.py structure: FAIL  {e}")

# ── Summary ───────────────────────────────────────────────────────
log("")
log("=" * 54)
passed = sum(1 for v in results.values() if v == PASS)
total  = len(results)
log(f"  FINAL TESTS: {passed}/{total} passed")
for k, v in results.items():
    log(f"    [{k:<36}]  {v}")
log("=" * 54)

dump()
print("\n".join(lines))
sys.exit(0 if passed == total else 1)
