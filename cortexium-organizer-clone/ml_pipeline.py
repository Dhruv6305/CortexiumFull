"""
ml_pipeline.py — Cortexium XR Machine Learning Pipeline

Active prediction priority (highest → lowest):
  1. learned_rule        — learned_rules.json (Learn Mode observations)
  2. personalized_model  — CatBoost trained on live usage_data.csv
                           saved to models/personalized/catboost_personalized.cbm
  3. baseline_model      — Immutable CatBoost baseline from Visual Genome
                           at models/baseline/catboost_baseline.cbm
  4. default_rule        — Hardcoded fallback table in server.py

The BASELINE model is READ-ONLY and NEVER overwritten during retraining.
The PERSONALIZED model is written to models/personalized/ only.
Reset Learning: clears learned_rules.json + removes personalized model,
                leaving baseline as the active ML model.

Components:
    FeatureExtractor              — Shared 13-feature vector computation
    DataCollector                 — Appends live samples to usage_data.csv
    BaselineCatBoostPredictor     — Wraps immutable baseline model
    PersonalizedCatBoostPredictor — Wraps personalized model (may not exist)
    train_personalized_model      — Trains/saves personalized CatBoost
    get_active_metrics            — Returns metrics for whichever model is active
"""

import os
import csv
import json
import math
import datetime
import numpy as np
import pandas as pd

from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, confusion_matrix, classification_report,
    roc_auc_score, average_precision_score,
)

# ─────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))

BASELINE_MODEL_PATH   = os.path.join(_ROOT, "models", "baseline", "catboost_baseline.cbm")
BASELINE_METRICS_PATH = os.path.join(_ROOT, "models", "baseline", "metrics.json")
BASELINE_CONFIG_PATH  = os.path.join(_ROOT, "models", "baseline", "feature_config.json")

PERSONALIZED_DIR         = os.path.join(_ROOT, "models", "personalized")
PERSONALIZED_MODEL_PATH  = os.path.join(PERSONALIZED_DIR, "catboost_personalized.cbm")
PERSONALIZED_METRICS_PATH = os.path.join(PERSONALIZED_DIR, "metrics.json")

# ─────────────────────────────────────────────
# Feature schema  (must match trained baseline exactly)
# ─────────────────────────────────────────────
FEATURE_COLUMNS = [
    "object_class",
    "surface_class",
    "object_conf",
    "object_area_ratio",
    "surface_area_ratio",
    "area_ratio",
    "overlap_ratio",
    "dx_normalized",
    "dy_normalized",
    "euclidean_dist_normalized",
    "obj_center_x_in_surface",
    "obj_center_y_in_surface",
    "vertical_position_ratio",
]
CAT_FEATURES    = ["object_class", "surface_class"]
CAT_FEATURE_IDX = [0, 1]
TARGET_COLUMN   = "target_surface"


# ─────────────────────────────────────────────
# Feature Extraction  (shared by baseline and personalized)
# ─────────────────────────────────────────────
class FeatureExtractor:
    """Compute the 13-feature vector for one (object, candidate_surface) pair.

    All features are computable from YOLO bounding boxes at live inference.
    """

    @staticmethod
    def compute(
        object_label: str,
        surface_label: str,
        object_box: tuple,   # (x1, y1, x2, y2) in pixels
        surface_box: tuple,  # (x1, y1, x2, y2) in pixels
        object_conf: float,
        frame_shape: tuple,  # (height, width)
    ) -> dict:
        frame_h, frame_w = frame_shape[:2]
        frame_area = max(frame_h * frame_w, 1)
        frame_diag = math.sqrt(frame_h ** 2 + frame_w ** 2)

        ox1, oy1, ox2, oy2 = object_box
        sx1, sy1, sx2, sy2 = surface_box

        obj_area  = max((ox2 - ox1) * (oy2 - oy1), 1)
        surf_area = max((sx2 - sx1) * (sy2 - sy1), 1)

        obj_cx  = (ox1 + ox2) / 2.0;  obj_cy  = (oy1 + oy2) / 2.0
        surf_cx = (sx1 + sx2) / 2.0;  surf_cy = (sy1 + sy2) / 2.0

        inter_x1 = max(ox1, sx1); inter_y1 = max(oy1, sy1)
        inter_x2 = min(ox2, sx2); inter_y2 = min(oy2, sy2)
        inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
        overlap   = inter_area / obj_area

        dx        = (obj_cx - surf_cx) / frame_w
        dy        = (obj_cy - surf_cy) / frame_h
        euclidean = math.sqrt((obj_cx - surf_cx)**2 + (obj_cy - surf_cy)**2) / max(frame_diag, 1)

        cx_in = 1.0 if sx1 <= obj_cx <= sx2 else 0.0
        cy_in = 1.0 if sy1 <= obj_cy <= sy2 else 0.0

        return {
            "object_class":              object_label,
            "surface_class":             surface_label,
            "object_conf":               round(object_conf, 4),
            "object_area_ratio":         round(obj_area  / frame_area, 6),
            "surface_area_ratio":        round(surf_area / frame_area, 6),
            "area_ratio":                round(obj_area  / surf_area,  6),
            "overlap_ratio":             round(overlap, 4),
            "dx_normalized":             round(dx,  4),
            "dy_normalized":             round(dy,  4),
            "euclidean_dist_normalized": round(euclidean, 4),
            "obj_center_x_in_surface":   cx_in,
            "obj_center_y_in_surface":   cy_in,
            "vertical_position_ratio":   round(obj_cy / frame_h, 4),
        }


# ─────────────────────────────────────────────
# Shared CatBoost inference helper
# ─────────────────────────────────────────────
def _catboost_score_candidates(
    cb_model,
    object_label: str,
    surface_candidates: dict,
    object_box: tuple,
    object_conf: float,
    frame_shape: tuple,
    min_prob: float = 0.1,
) -> tuple:
    """Score all candidate surfaces with a loaded CatBoost binary model.

    Returns (best_surface_name, probability) or (None, 0.0).
    """
    if not surface_candidates:
        return None, 0.0

    rows, names = [], []
    for surf_name, surf_box in surface_candidates.items():
        feat = FeatureExtractor.compute(
            object_label, surf_name, object_box, surf_box, object_conf, frame_shape,
        )
        rows.append([str(feat[f]) if f in CAT_FEATURES else feat[f]
                     for f in FEATURE_COLUMNS])
        names.append(surf_name)

    try:
        X = pd.DataFrame(rows, columns=FEATURE_COLUMNS)
        for c in CAT_FEATURES:
            X[c] = X[c].astype(str)
        proba    = cb_model.predict_proba(X)[:, 1]
        best_idx = int(np.argmax(proba))
        best_prob = float(proba[best_idx])
        if best_prob < min_prob:
            return None, 0.0
        return names[best_idx], round(best_prob, 4)
    except Exception:
        return None, 0.0


# ─────────────────────────────────────────────
# Baseline CatBoost Predictor  (READ-ONLY, never retrained)
# ─────────────────────────────────────────────
class BaselineCatBoostPredictor:
    """Immutable baseline trained on Visual Genome data."""

    def __init__(self, model_path: str = BASELINE_MODEL_PATH):
        self._loaded = False
        self.model   = None
        try:
            from catboost import CatBoostClassifier
            if not os.path.exists(model_path):
                return
            m = CatBoostClassifier()
            m.load_model(model_path)
            self.model   = m
            self._loaded = True
        except Exception:
            pass

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def predict(self, object_label, surface_candidates, object_box,
                object_conf, frame_shape) -> tuple:
        if not self._loaded:
            return None, 0.0
        return _catboost_score_candidates(
            self.model, object_label, surface_candidates,
            object_box, object_conf, frame_shape,
        )


# ─────────────────────────────────────────────
# Personalized CatBoost Predictor  (trained on live usage_data.csv)
# ─────────────────────────────────────────────
class PersonalizedCatBoostPredictor:
    """Personalized model derived from live user observations.

    Saved separately to models/personalized/ so the baseline is never touched.
    """

    def __init__(self, model_path: str = PERSONALIZED_MODEL_PATH):
        self._loaded    = False
        self.model      = None
        self.model_path = model_path
        self._try_load(model_path)

    def _try_load(self, path: str):
        try:
            from catboost import CatBoostClassifier
            if not os.path.exists(path):
                return
            m = CatBoostClassifier()
            m.load_model(path)
            self.model   = m
            self._loaded = True
        except Exception:
            self._loaded = False

    def reload(self):
        """Reload after a retrain."""
        self._try_load(self.model_path)

    def disable(self):
        """Mark as not loaded (after reset) without deleting the file."""
        self._loaded = False
        self.model   = None

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def predict(self, object_label, surface_candidates, object_box,
                object_conf, frame_shape) -> tuple:
        if not self._loaded:
            return None, 0.0
        return _catboost_score_candidates(
            self.model, object_label, surface_candidates,
            object_box, object_conf, frame_shape,
        )


# ─────────────────────────────────────────────
# Data Collection
# ─────────────────────────────────────────────
class DataCollector:
    """Append training samples to usage_data.csv."""

    def __init__(self, csv_path: str = "usage_data.csv"):
        self.csv_path = csv_path
        self._ensure_header()

    def _ensure_header(self):
        if not os.path.exists(self.csv_path) or os.path.getsize(self.csv_path) == 0:
            with open(self.csv_path, "w", newline="") as f:
                csv.writer(f).writerow(FEATURE_COLUMNS + [TARGET_COLUMN])

    def log_sample(
        self,
        object_label: str,
        surface_label: str,
        object_box: tuple,
        surface_box: tuple,
        object_conf: float,
        frame_shape: tuple,
        is_positive: bool = True,
    ):
        features = FeatureExtractor.compute(
            object_label, surface_label, object_box, surface_box, object_conf, frame_shape,
        )
        target = surface_label if is_positive else "__none__"
        row    = [features[col] for col in FEATURE_COLUMNS] + [target]
        with open(self.csv_path, "a", newline="") as f:
            csv.writer(f).writerow(row)


# ─────────────────────────────────────────────
# Personalized CatBoost Retraining
# ─────────────────────────────────────────────
def train_personalized_model(
    data_path:    str = "usage_data.csv",
    model_path:   str = PERSONALIZED_MODEL_PATH,
    metrics_path: str = PERSONALIZED_METRICS_PATH,
) -> dict:
    """Train a personalized CatBoost model on live usage_data.csv.

    The model is trained as a BINARY classifier matching the baseline:
      (object, candidate_surface, spatial features) → suitable (1) / not (0)

    Training rows in usage_data.csv that have target != "__none__" are
    label=1; rows with "__none__" are label=0.

    The BASELINE model is NEVER touched.
    Output is saved to models/personalized/.
    """
    from catboost import CatBoostClassifier, Pool

    os.makedirs(os.path.dirname(model_path), exist_ok=True)

    df = pd.read_csv(data_path)
    if len(df) < 4:
        raise ValueError(f"Not enough live data: {len(df)} samples (need ≥ 4).")

    # Convert multiclass target to binary label
    df["label"] = (df[TARGET_COLUMN] != "__none__").astype(int)

    n_pos = int(df["label"].sum())
    n_neg = int((df["label"] == 0).sum())
    if n_pos == 0:
        raise ValueError("No positive samples. Run Learn Mode first.")

    # Encode categoricals as strings for CatBoost
    X = df[FEATURE_COLUMNS].copy()
    for c in CAT_FEATURES:
        X[c] = X[c].astype(str)
    y = df["label"].values

    # Use group-based split if image_id exists, otherwise random split
    if "image_id" in df.columns and df["image_id"].nunique() >= 4:
        groups = df["image_id"].values
        gss    = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
        tr_idx, te_idx = next(gss.split(X, y, groups=groups))
    else:
        # fallback: last 20% as test
        split_at = max(1, int(len(df) * 0.8))
        tr_idx   = list(range(split_at))
        te_idx   = list(range(split_at, len(df)))

    X_train, X_test = X.iloc[tr_idx], X.iloc[te_idx]
    y_train, y_test = y[tr_idx],      y[te_idx]

    train_pool = Pool(X_train, label=y_train, cat_features=CAT_FEATURE_IDX,
                      feature_names=FEATURE_COLUMNS)
    test_pool  = Pool(X_test,  label=y_test,  cat_features=CAT_FEATURE_IDX,
                      feature_names=FEATURE_COLUMNS)

    clf = CatBoostClassifier(
        iterations=300,
        depth=6,
        learning_rate=0.05,
        loss_function="Logloss",
        eval_metric="AUC",
        auto_class_weights="Balanced",
        random_seed=42,
        early_stopping_rounds=40,
        verbose=False,
    )
    clf.fit(train_pool, eval_set=test_pool)

    # ── Evaluate ──
    y_pred  = clf.predict(test_pool).flatten().astype(int)
    y_proba = clf.predict_proba(test_pool)[:, 1]

    accuracy    = float(accuracy_score(y_test, y_pred))
    precision   = float(precision_score(y_test, y_pred, average="macro",    zero_division=0))
    recall      = float(recall_score(   y_test, y_pred, average="macro",    zero_division=0))
    macro_f1    = float(f1_score(       y_test, y_pred, average="macro",    zero_division=0))
    weighted_f1 = float(f1_score(       y_test, y_pred, average="weighted", zero_division=0))

    try:
        roc_auc = float(roc_auc_score(y_test, y_proba))
        pr_auc  = float(average_precision_score(y_test, y_proba))
    except Exception:
        roc_auc = pr_auc = 0.0

    cm     = confusion_matrix(y_test, y_pred, labels=[0, 1]).tolist()
    report = classification_report(
        y_test, y_pred,
        target_names=["not-suitable", "suitable"],
        zero_division=0,
        output_dict=True,
    )

    fi_raw = clf.get_feature_importance()
    feature_importance = dict(zip(FEATURE_COLUMNS, [round(v, 4) for v in fi_raw]))

    ts = datetime.datetime.now().strftime("%H:%M:%S")

    metrics = {
        "model_name":         "CatBoostClassifier (personalized)",
        "model_type":         "personalized",
        "is_personalized":    True,
        "total_samples":      int(len(df)),
        "train_samples":      int(len(X_train)),
        "test_samples":       int(len(X_test)),
        "positive_samples":   n_pos,
        "negative_samples":   n_neg,
        "n_classes":          2,
        "classes":            ["not-suitable", "suitable"],
        "accuracy":           round(accuracy,    4),
        "precision":          round(precision,   4),
        "recall":             round(recall,      4),
        "f1_score":           round(macro_f1,    4),
        "weighted_f1":        round(weighted_f1, 4),
        "roc_auc":            round(roc_auc, 4),
        "pr_auc":             round(pr_auc,  4),
        "cross_val_mean":     round(roc_auc, 4),   # expose roc_auc as cvScore for frontend
        "confusion_matrix":   cm,
        "classification_report": report,
        "feature_importance": feature_importance,
        "last_retrain_time":  ts,
        "training_timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
    }

    clf.save_model(model_path)
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    print("\n" + "=" * 60)
    print("  CORTEXIUM — PERSONALIZED MODEL TRAINING")
    print("=" * 60)
    print(f"  Samples  : {len(df)}  |  Train: {len(X_train)}  |  Test: {len(X_test)}")
    print(f"  Pos/Neg  : {n_pos} / {n_neg}")
    print(f"  Accuracy : {accuracy:.4f}   Precision: {precision:.4f}")
    print(f"  Recall   : {recall:.4f}   Macro F1:  {macro_f1:.4f}")
    print(f"  ROC-AUC  : {roc_auc:.4f}   PR-AUC:   {pr_auc:.4f}")
    print(f"  Model    → {model_path}")
    print(f"  Metrics  → {metrics_path}")
    print("=" * 60 + "\n")

    return metrics


# ─────────────────────────────────────────────
# Active Metrics Helper
# ─────────────────────────────────────────────
def get_active_metrics():
    # type: () -> dict
    """Return metrics for the currently active model.

    Priority:
      1. Personalized metrics (models/personalized/metrics.json) if exists
      2. Baseline metrics    (models/baseline/metrics.json)
      3. None
    """
    for path, model_type in [
        (PERSONALIZED_METRICS_PATH, "personalized"),
        (BASELINE_METRICS_PATH,     "baseline"),
    ]:
        try:
            with open(path) as f:
                raw = json.load(f)
            # Normalise field names for frontend compatibility
            return {
                "model_type":       raw.get("model_type",       model_type),
                "is_personalized":  raw.get("is_personalized",  model_type == "personalized"),
                "accuracy":         raw.get("accuracy",         raw.get("test", {}).get("accuracy", 0.0)),
                "precision":        raw.get("precision",        raw.get("test", {}).get("macro_precision", 0.0)),
                "recall":           raw.get("recall",           raw.get("test", {}).get("macro_recall", 0.0)),
                "f1Score":          raw.get("f1_score",         raw.get("test", {}).get("macro_f1", 0.0)),
                "cvScore":          raw.get("cross_val_mean",   raw.get("roc_auc",
                                     raw.get("test", {}).get("roc_auc", 0.0))),
                "confusionMatrix":  raw.get("confusion_matrix", []),
                "classes":          raw.get("classes",          raw.get("class_names", [])),
                "featureImportance":raw.get("feature_importance", {}),
                "last_retrain_time":raw.get("last_retrain_time", raw.get("training_timestamp", "N/A")),
                "total_samples":    raw.get("total_samples",    raw.get("dataset_size", 0)),
                "train_samples":    raw.get("train_samples",    raw.get("train_size",   0)),
                "test_samples":     raw.get("test_samples",     raw.get("test_size",    0)),
            }
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            continue
    return None


# ─────────────────────────────────────────────
# Backward-compat shim: train_and_evaluate → train_personalized_model
# ─────────────────────────────────────────────
def train_and_evaluate(
    data_path:    str = "usage_data.csv",
    model_path:   str = PERSONALIZED_MODEL_PATH,
    encoder_path: str = None,          # unused in CatBoost — kept for API compat
    metrics_path: str = PERSONALIZED_METRICS_PATH,
) -> dict:
    """Drop-in replacement for the old Random Forest train_and_evaluate.

    Trains the PERSONALIZED CatBoost model and returns the same metrics dict
    shape as the old function so server.py calling code doesn't need to change.
    """
    return train_personalized_model(data_path, model_path, metrics_path)


# ─────────────────────────────────────────────
# Legacy shim: PlacementPredictor — kept so older scripts don't crash
# ─────────────────────────────────────────────
class PlacementPredictor:
    """
    Legacy shim.  Now delegates to PersonalizedCatBoostPredictor.
    Kept so any code that imports PlacementPredictor still works.
    """
    def __init__(self, model_path: str = PERSONALIZED_MODEL_PATH,
                 encoder_path: str = None):
        self._delegate = PersonalizedCatBoostPredictor(model_path)

    @property
    def is_loaded(self) -> bool:
        return self._delegate.is_loaded

    def load_model(self):
        self._delegate.reload()

    def predict(self, object_label, surface_candidates, object_box,
                object_conf, frame_shape) -> tuple:
        return self._delegate.predict(
            object_label, surface_candidates, object_box, object_conf, frame_shape,
        )
