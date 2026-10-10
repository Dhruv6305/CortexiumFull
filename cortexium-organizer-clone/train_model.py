"""
train_model.py — Standalone training script for Cortexium XR

Usage:
    python train_model.py

Reads usage_data.csv, trains a Random Forest Classifier,
saves the model, encoders, and evaluation metrics.
Can be run independently or triggered via the T key in the app.
"""

import sys
import os

from ml_pipeline import train_and_evaluate


def main():
    data_path = "usage_data.csv"
    model_path = "placement_model.pkl"
    encoder_path = "label_encoder.pkl"
    metrics_path = "metrics.json"

    if not os.path.exists(data_path):
        print(f"[ERROR] Training data not found: {data_path}")
        print("        Run the application in Learn Mode first to collect training data.")
        sys.exit(1)

    try:
        metrics = train_and_evaluate(data_path, model_path, encoder_path, metrics_path)
        print(f"\n[OK] Training complete -- Accuracy: {metrics['accuracy']:.4f} | F1: {metrics['f1_score']:.4f}")
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Unexpected error during training: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
