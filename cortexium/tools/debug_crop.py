"""
Debug script: Extracts a few sample crops from the video and saves them to disk,
then runs EasyOCR on them and prints what text is detected.
Run: python tools/debug_crop.py --video data/sample_videos/NavVideoForTesting.mp4
"""
import cv2
import os
import re
import argparse

try:
    import easyocr
    import torch
except ImportError:
    easyocr = None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=str, default="data/sample_videos/NavVideoForTesting.mp4")
    parser.add_argument("--out_dir", type=str, default="data/debug_crops")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"❌ Cannot open {args.video}")
        return

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps   = cap.get(cv2.CAP_PROP_FPS) or 30.0
    print(f"🎬 {args.video} | {total} frames @ {fps:.2f} FPS")

    # Init OCR
    reader = None
    if easyocr:
        cuda_ok = torch.cuda.is_available()
        reader = easyocr.Reader(['en'], gpu=cuda_ok)
        print(f"🧠 EasyOCR ready (GPU={cuda_ok})")

    h_sample = None
    w_sample = None

    # Sample frame 0, 30, 60, 90 seconds in
    sample_secs = [0, 10, 20, 30]
    for sec in sample_secs:
        frame_no = int(sec * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        ret, frame = cap.read()
        if not ret:
            continue

        h, w = frame.shape[:2]
        h_sample, w_sample = h, w

        # Save full frame
        cv2.imwrite(os.path.join(args.out_dir, f"frame_{sec}s_full.jpg"), frame)

        # Try multiple crop zones and save each
        zones = {
            "top20":     frame[0:int(h*0.20), 0:w],
            "mid50_65":  frame[int(h*0.50):int(h*0.65), 0:w],
            "mid60_75":  frame[int(h*0.60):int(h*0.75), 0:w],
            "mid65_80":  frame[int(h*0.65):int(h*0.80), 0:w],
            "mid70_85":  frame[int(h*0.70):int(h*0.85), 0:w],
            "bot85_100": frame[int(h*0.85):h, 0:w],
        }

        print(f"\n--- Frame @ {sec}s (size {w}x{h}) ---")
        for zone_name, crop in zones.items():
            path = os.path.join(args.out_dir, f"frame_{sec}s_{zone_name}.jpg")
            cv2.imwrite(path, crop)

            if reader and crop.size > 0:
                # Run OCR on the raw crop (no thresholding first — see raw result)
                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                gray_big = cv2.resize(gray, (0,0), fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
                results = reader.readtext(gray_big)
                texts = [r[1] for r in results]
                print(f"  [{zone_name}] OCR raw: {texts}")

    cap.release()
    print(f"\n✅ Debug crops saved to '{args.out_dir}/'")
    if h_sample:
        print(f"   Video resolution: {w_sample}x{h_sample}")

if __name__ == "__main__":
    main()
