# Cortexium Baseline Model

## Overview
Static baseline for Cortexium's object-to-surface placement prediction.
This model does **not** adapt from user behaviour — it is the reference
against which the live adaptive model will later be compared.

---

## Dataset
| Property | Value |
|---|---|
| File | `data/baseline_relationships.csv` |
| Source | Visual Genome relationships |
| Rows | 460 |
| Unique images | 403 |
| Unique objects | 25 |
| Unique surfaces | 16 |

---

## ML Formulation
**Binary candidate-surface suitability classifier**

- Input: `object_class` + `candidate_surface_class` + 11 spatial features
- Target: `1` (object belongs on this surface) / `0` (it does not)

This matches Cortexium's live inference loop exactly: for each detected object,
score every YOLO-detected candidate surface, pick the one with the highest
P(label=1). See `feature_config.json` for inference instructions.

### Why not multiclass (object → surface)?
The live system (`ml_pipeline.py PlacementPredictor`) already uses the binary
candidate-scoring approach. A multiclass model would require a separate
integration path and cannot leverage the spatial relationship between a specific
object and a specific candidate surface.

---

## Features (identical to ml_pipeline.py FeatureExtractor)
| Feature | Type | Available at inference? |
|---|---|---|
| `object_class` | Categorical | ✓ YOLO class name |
| `surface_class` | Categorical | ✓ YOLO candidate surface name |
| `object_conf` | Numeric | ✓ YOLO confidence (set 1.0 for baseline) |
| `object_area_ratio` | Numeric | ✓ obj area / frame area |
| `surface_area_ratio` | Numeric | ✓ surf area / frame area |
| `area_ratio` | Numeric | ✓ obj area / surf area |
| `overlap_ratio` | Numeric | ✓ IoObj with candidate surface |
| `dx_normalized` | Numeric | ✓ center dx / frame_w |
| `dy_normalized` | Numeric | ✓ center dy / frame_h |
| `euclidean_dist_normalized` | Numeric | ✓ center dist / frame diagonal |
| `obj_center_x_in_surface` | Numeric | ✓ containment flag |
| `obj_center_y_in_surface` | Numeric | ✓ containment flag |
| `vertical_position_ratio` | Numeric | ✓ obj_cy / frame_h |

Excluded: `image_id` (identifier), `predicate` (VG annotation, not from YOLO),
absolute pixel coordinates (replaced by normalised relative features).

---

## Negative Sample Strategy
- Positive: each annotated (object, surface) relationship = label 1
- Negative: same object bbox paired with every other surface in the vocabulary,
  using that surface's mean bbox statistics = label 0
- Neg/Pos ratio: ~15:1  (handled by `auto_class_weights=Balanced`)
- Mirrors `DataCollector.log_sample(is_positive=False)` in ml_pipeline.py

---

## Data Split
GroupShuffleSplit on `image_id` (70/15/15, seed=42).
Prevents same-image rows (which share surface bbox values) from appearing in
both train and test.

| Split | Rows | Images |
|---|---|---|
| Train | 5024 | 282 |
| Validation | 1200 | 60 |
| Test | 1136 | 61 |

---

## Model
CatBoostClassifier — binary Logloss, auto_class_weights=Balanced

```
iterations=500, depth=6, learning_rate=0.05,
early_stopping_rounds=50, random_seed=42
Best iteration: 321
```

CatBoost selected over RandomForest because:
- native categorical encoding (no label encoding needed)
- better probability calibration for candidate-ranking inference
- superior ROC-AUC on this dataset (0.9943 vs RF 0.9796)

---

## Results (TEST set)
| Metric | Value |
|---|---|
| Accuracy | 0.9930 |
| Macro Precision | 0.9963 |
| Macro Recall | 0.9437 |
| Macro F1 | 0.9683 |
| Weighted F1 | 0.9928 |
| ROC-AUC | 0.9943 |
| PR-AUC | 0.9799 |
| TP / TN / FP / FN | 63 / 1065 / 0 / 8 |

Validation Accuracy: 0.9933 | Validation ROC-AUC: 0.9995

Top 3 features: ['surface_area_ratio', 'overlap_ratio', 'dy_normalized']

---

## Artefacts
| File | Description |
|---|---|
| `catboost_baseline.cbm` | Trained model |
| `feature_config.json` | Features + inference instructions |
| `metrics.json` | All metrics + config |
| `confusion_matrix.png` | Test confusion matrix |
| `classification_report.txt` | Per-class report |
| `roc_pr_curves.png` | ROC and PR curves |
| `feature_importance.csv` | Sorted feature importances |
| `feature_importance.png` | Feature importance chart |
| `README.md` | This file |

---

## Limitations
1. Negatives are **synthetic** (mean bbox stats, not real non-placements).
   Performance will improve with real live observations from `usage_data.csv`.
2. Source dataset has only 460 rows from 403 images (mostly 1 row/image).
3. Rare surfaces (`dining table`: 2 rows, `rack`: 7 rows) are poorly represented.
4. `object_conf` is set to 1.0 in the baseline; live data provides real YOLO confidence scores.

---

## Relationship to Adaptive Architecture
```
Baseline (this model)
    ↓
Live YOLO detection → candidate surface scoring
    ↓
Adaptive fine-tuning from usage_data.csv
    ↓
User-specific personalised model
    ↓
Reset → return to baseline
```
The baseline serves as the cold-start prior when no user data exists.
