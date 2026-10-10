"""
scripts/evaluate_baseline.py
Cortexium – Adaptive AI Reality Engine

Independently reproduces the baseline evaluation metrics by loading
the saved model and the original dataset — without re-training.

Uses identical preprocessing and the same random_state=42 split
to guarantee the same test partition as train_baseline_model.py.
"""

import os
import sys
import json
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier, Pool
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# ──────────────────────────────────────────────────────────────
ROOT         = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH    = os.path.join(ROOT, "data",   "baseline_relationships.csv")
MODEL_PATH   = os.path.join(ROOT, "models", "catboost_baseline.cbm")
MAPPING_PATH = os.path.join(ROOT, "models", "class_mapping.json")
METRICS_PATH = os.path.join(ROOT, "models", "baseline_metrics.json")

# Feature config (must match training)
OBJECT_COL       = "object"
SURFACE_COL      = "surface"
NUMERIC_FEATURES = [
    "object_w", "object_h",
    "surface_w", "surface_h",
    "center_distance_x", "center_distance_y",
]
ALL_FEATURES = [OBJECT_COL] + NUMERIC_FEATURES
CAT_IDX      = [0]

# ──────────────────────────────────────────────────────────────
print("=" * 64)
print("  CORTEXIUM — BASELINE EVALUATION (independent run)")
print("=" * 64)

for path, label in [
    (DATA_PATH,    "Dataset"),
    (MODEL_PATH,   "Saved model"),
    (MAPPING_PATH, "Class mapping"),
]:
    if not os.path.exists(path):
        print(f"[ERROR] {label} not found: {path}")
        print("        Run scripts/train_baseline_model.py first.")
        sys.exit(1)

# ── Load ──
model = CatBoostClassifier()
model.load_model(MODEL_PATH)
print(f"\n  Model loaded       : {MODEL_PATH}")

with open(MAPPING_PATH) as f:
    mapping = json.load(f)
classes    = mapping["surface_classes"]
n_classes  = len(classes)
print(f"  Surface classes    : {n_classes}  →  {classes}")

# ── Preprocess (identical to training script) ──
df = pd.read_csv(DATA_PATH)
df[OBJECT_COL]  = df[OBJECT_COL].astype(str).str.strip().str.lower()
df[SURFACE_COL] = df[SURFACE_COL].astype(str).str.strip().str.lower()
df = df[
    df[OBJECT_COL].notna()  & df[SURFACE_COL].notna() &
    (df[OBJECT_COL]  != "") & (df[SURFACE_COL] != "") &
    (df[OBJECT_COL]  != "nan") & (df[SURFACE_COL] != "nan")
].copy()
df.dropna(subset=NUMERIC_FEATURES, inplace=True)

le = LabelEncoder()
le.classes_ = np.array(classes)
df["surface_enc"] = le.transform(df[SURFACE_COL])

X = df[ALL_FEATURES]
y = df["surface_enc"].values

surf_counts  = df[SURFACE_COL].value_counts()
min_cls_cnt  = int(surf_counts.min())
stratify_arg = y if min_cls_cnt >= 2 else None

_, X_test, _, y_test = train_test_split(
    X, y,
    test_size=0.2,
    random_state=42,
    stratify=stratify_arg,
)

print(f"\n  Dataset size       : {len(df)}")
print(f"  Test split size    : {len(X_test)}  (20%, random_state=42)")

# ── Evaluate ──
test_pool  = Pool(X_test, label=y_test, cat_features=CAT_IDX,
                  feature_names=ALL_FEATURES)
y_pred_enc = model.predict(test_pool).flatten().astype(int)
y_proba    = model.predict_proba(test_pool)

accuracy     = accuracy_score(y_test, y_pred_enc)
balanced_acc = balanced_accuracy_score(y_test, y_pred_enc)
macro_prec   = precision_score(y_test, y_pred_enc, average="macro",    zero_division=0)
macro_rec    = recall_score(   y_test, y_pred_enc, average="macro",    zero_division=0)
macro_f1     = f1_score(       y_test, y_pred_enc, average="macro",    zero_division=0)
weighted_f1  = f1_score(       y_test, y_pred_enc, average="weighted", zero_division=0)

top_k  = min(3, n_classes) if n_classes >= 3 else 1
top3_acc = (
    sum(1 for i, t in enumerate(y_test)
        if t in np.argsort(y_proba[i])[::-1][:top_k])
    / len(y_test)
    if n_classes >= 3 else accuracy
)

report = classification_report(
    y_test, y_pred_enc,
    target_names=classes,
    zero_division=0,
)

print(f"\n  {'Metric':<26} {'Value':>10}")
print("  " + "-" * 38)
print(f"  {'Accuracy':<26} {accuracy:>10.4f}  ({accuracy*100:.1f}%)")
print(f"  {'Balanced Accuracy':<26} {balanced_acc:>10.4f}  ({balanced_acc*100:.1f}%)")
print(f"  {'Macro Precision':<26} {macro_prec:>10.4f}")
print(f"  {'Macro Recall':<26} {macro_rec:>10.4f}")
print(f"  {'Macro F1':<26} {macro_f1:>10.4f}")
print(f"  {'Weighted F1':<26} {weighted_f1:>10.4f}")
print(f"  {'Top-3 Accuracy':<26} {top3_acc:>10.4f}  ({top3_acc*100:.1f}%)")
print(f"\n  Classification Report:\n")
for line in report.splitlines():
    print(f"    {line}")

# ── Compare with saved metrics ──
if os.path.exists(METRICS_PATH):
    with open(METRICS_PATH) as f:
        saved = json.load(f)

    print("\n  Comparison with models/baseline_metrics.json:")
    checks = [
        ("accuracy",          accuracy,     saved.get("accuracy",          0)),
        ("balanced_accuracy", balanced_acc, saved.get("balanced_accuracy", 0)),
        ("macro_f1",          macro_f1,     saved.get("macro_f1",          0)),
        ("weighted_f1",       weighted_f1,  saved.get("weighted_f1",       0)),
        ("top_3_accuracy",    top3_acc,     saved.get("top_3_accuracy",    0)),
    ]
    tol = 0.001
    all_ok = True
    for metric, comp, stored in checks:
        match = abs(comp - stored) <= tol
        status = "✓" if match else f"✗ MISMATCH (Δ={abs(comp-stored):.4f})"
        if not match:
            all_ok = False
        print(f"    {metric:<24} computed={comp:.4f}  saved={stored:.4f}  {status}")

    if all_ok:
        print("\n  ✓ All metrics match — evaluation is fully reproducible.")
    else:
        print("\n  ✗ Mismatches detected. Verify split / preprocessing consistency.")

print("\n" + "=" * 64)
print("  Evaluation complete.")
print("=" * 64 + "\n")
