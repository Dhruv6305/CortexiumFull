"""
scripts/baseline_predictor.py
Cortexium – Adaptive AI Reality Engine

Reusable prediction module for the CatBoost baseline model.

The model uses: object (categorical) + spatial features (numeric)
When spatial features are not available, falls back to per-object
average values learned from the training data.

Usage (standalone CLI):
    python scripts/baseline_predictor.py laptop
    python scripts/baseline_predictor.py bottle cup mouse

Usage (imported):
    from scripts.baseline_predictor import BaselinePredictor
    p = BaselinePredictor()

    # With spatial context (live YOLO inference):
    result = p.predict(
        "laptop",
        object_w=120, object_h=80,
        surface_w=400, surface_h=200,
        center_distance_x=30, center_distance_y=15,
    )

    # Without spatial context (fallback to training-data averages):
    result = p.predict("laptop")
"""

import os
import sys
import json

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier

# ──────────────────────────────────────────────────────────────
_SCRIPTS_DIR  = os.path.dirname(os.path.abspath(__file__))
_ROOT         = os.path.dirname(_SCRIPTS_DIR)
_MODEL_PATH   = os.path.join(_ROOT, "models", "catboost_baseline.cbm")
_MAPPING_PATH = os.path.join(_ROOT, "models", "class_mapping.json")

# Feature column order must match training exactly
_ALL_FEATURES = [
    "object",
    "object_w", "object_h",
    "surface_w", "surface_h",
    "center_distance_x", "center_distance_y",
]
_CAT_IDX = [0]


class BaselinePredictor:
    """
    Loads the saved CatBoost baseline model and provides
    object → surface predictions with confidence scores.
    """

    def __init__(
        self,
        model_path:   str = _MODEL_PATH,
        mapping_path: str = _MAPPING_PATH,
    ):
        for path, label in [(model_path, "Model"), (mapping_path, "Class mapping")]:
            if not os.path.exists(path):
                raise FileNotFoundError(
                    f"{label} not found: {path}\n"
                    "Run scripts/train_baseline_model.py first."
                )

        self.model = CatBoostClassifier()
        self.model.load_model(model_path)

        with open(mapping_path) as f:
            mapping = json.load(f)

        self.surface_classes: list[str]      = mapping["surface_classes"]
        self.numeric_features: list[str]     = mapping.get("numeric_features", _ALL_FEATURES[1:])
        self.obj_feature_means: dict         = mapping.get("obj_feature_means", {})
        self.n_classes = len(self.surface_classes)

        # Global fallback means (used when object is completely unseen)
        all_means = [list(v.values()) for v in self.obj_feature_means.values()]
        if all_means:
            self._global_means = dict(zip(
                self.numeric_features,
                np.mean(all_means, axis=0).tolist(),
            ))
        else:
            self._global_means = {k: 0.0 for k in self.numeric_features}

    # ──────────────────────────────────────────────────────────
    def _resolve_spatial(
        self,
        object_name: str,
        object_w:   float | None,
        object_h:   float | None,
        surface_w:  float | None,
        surface_h:  float | None,
        center_distance_x: float | None,
        center_distance_y: float | None,
    ) -> dict:
        """
        Return a full spatial feature dict.
        Uses provided values where available; falls back to
        per-object training-data means otherwise.
        """
        defaults = self.obj_feature_means.get(object_name, self._global_means)
        return {
            "object_w":          object_w           if object_w           is not None else defaults.get("object_w",           self._global_means["object_w"]),
            "object_h":          object_h           if object_h           is not None else defaults.get("object_h",           self._global_means["object_h"]),
            "surface_w":         surface_w          if surface_w          is not None else defaults.get("surface_w",          self._global_means["surface_w"]),
            "surface_h":         surface_h          if surface_h          is not None else defaults.get("surface_h",          self._global_means["surface_h"]),
            "center_distance_x": center_distance_x  if center_distance_x  is not None else defaults.get("center_distance_x",  self._global_means["center_distance_x"]),
            "center_distance_y": center_distance_y  if center_distance_y  is not None else defaults.get("center_distance_y",  self._global_means["center_distance_y"]),
        }

    # ──────────────────────────────────────────────────────────
    def predict(
        self,
        object_name: str,
        *,
        object_w:          float | None = None,
        object_h:          float | None = None,
        surface_w:         float | None = None,
        surface_h:         float | None = None,
        center_distance_x: float | None = None,
        center_distance_y: float | None = None,
        top_k:             int = 5,
    ) -> dict:
        """
        Predict the most appropriate surface for a given object.

        Parameters
        ----------
        object_name : str
            Detected object name (e.g. "laptop", "bottle").
        object_w, object_h : float, optional
            Bounding box width/height of the object (pixels).
        surface_w, surface_h : float, optional
            Bounding box width/height of the candidate surface.
        center_distance_x/y : float, optional
            Horizontal/vertical center-to-center distance.
        top_k : int
            Number of ranked alternatives to return.

        Returns
        -------
        dict:
            object, predicted_surface, confidence, alternatives,
            spatial_context_used (bool)
        """
        name_clean   = str(object_name).strip().lower()
        spatial      = self._resolve_spatial(
            name_clean,
            object_w, object_h, surface_w, surface_h,
            center_distance_x, center_distance_y,
        )
        spatial_used = any(
            v is not None for v in [
                object_w, object_h, surface_w, surface_h,
                center_distance_x, center_distance_y,
            ]
        )

        row = {"object": name_clean, **spatial}
        X   = pd.DataFrame([row])[_ALL_FEATURES]
        proba = self.model.predict_proba(X)[0]

        ranked     = np.argsort(proba)[::-1]
        top_k_act  = min(top_k, self.n_classes)
        top_surface = self.surface_classes[ranked[0]]
        top_prob    = float(proba[ranked[0]])

        return {
            "object":               name_clean,
            "predicted_surface":    top_surface,
            "confidence":           round(top_prob, 4),
            "spatial_context_used": spatial_used,
            "alternatives": [
                {
                    "surface":     self.surface_classes[i],
                    "probability": round(float(proba[i]), 4),
                }
                for i in ranked[:top_k_act]
            ],
        }

    # ──────────────────────────────────────────────────────────
    def predict_batch(
        self,
        object_names: list[str],
        top_k: int = 3,
    ) -> list[dict]:
        """Predict surfaces for a list of objects (object-only, no spatial)."""
        results = []
        for name in object_names:
            results.append(self.predict(name, top_k=top_k))
        return results

    # ──────────────────────────────────────────────────────────
    def __repr__(self):
        return (
            f"BaselinePredictor("
            f"n_classes={self.n_classes}, "
            f"surfaces={self.surface_classes})"
        )


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    predictor = BaselinePredictor()
    print(f"\nCortexium Baseline Predictor  —  {predictor.n_classes} surface classes\n")
    print(f"  {predictor}\n")

    demo_objects = sys.argv[1:] if len(sys.argv) > 1 else [
        "laptop", "bottle", "cup", "book", "mouse",
        "phone", "bag", "keyboard", "pen", "tablet",
    ]

    for obj in demo_objects:
        result = predictor.predict(obj, top_k=5)
        print(f"  Object : {result['object']}")
        print(f"  → Best : {result['predicted_surface']}  "
              f"({result['confidence']*100:.1f}% confidence)  "
              f"[spatial={'yes' if result['spatial_context_used'] else 'no (using avg)'}]")
        print(f"  Ranked alternatives:")
        for alt in result["alternatives"]:
            bar = "▓" * int(alt["probability"] * 30)
            print(f"      {alt['surface']:<16} {alt['probability']*100:5.1f}%  {bar}")
        print()
