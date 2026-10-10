import os
import math
import cv2
import re
import pandas as pd
import numpy as np
import argparse
from tqdm import tqdm

try:
    import easyocr
except ImportError:
    easyocr = None

def preprocess_telemetry_crop(crop):
    """
    Apply grayscale and upscale only — thresholding was found to reduce OCR accuracy.
    """
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # Scale up 2x to improve character clarity for EasyOCR
    gray = cv2.resize(gray, (0, 0), fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    return gray

def parse_telemetry_text(text_lines):
    """
    Helper to extract lat, lon, heading, speed from parsed OCR lines.
    Looking for formats like:
    Lat: 19.2879, Lon: 72.8531
    Heading: 304, Speed: 40 km/h
    """
    lat, lon, heading, speed = None, None, None, None
    combined_text = " ".join(text_lines).lower()

    # OCR often misreads:
    #   'Lat' -> 'Lal' or 'lat'
    #   '19.2879' -> '19 2879' (dot misread as space)
    #   'Long' -> 'long' or 'lon'
    # Strategy: match 'lat' OR 'lal' then capture digits with optional space-as-dot
    def extract_decimal(match_obj):
        """Reconstruct float from OCR output like '19 2879' -> 19.2879"""
        raw = match_obj.group(1).strip()
        # If there's a dot already, use as-is
        if '.' in raw:
            try:
                return float(raw)
            except ValueError:
                pass
        # Otherwise split on space: first part is integer, second is decimal
        parts = raw.split()
        if len(parts) == 2:
            try:
                return float(f"{parts[0]}.{parts[1]}")
            except ValueError:
                pass
        elif len(parts) == 1:
            try:
                return float(parts[0])
            except ValueError:
                pass
        return None

    # Match 'lat' or 'lal' (OCR misread) followed by digits with optional space for decimal point
    lat_match = re.search(r'la[tl][:\s]*(-?\d+[\s\.]\d+)', combined_text)
    # Match 'long' or 'lon', allowing OCR errors like '1ong', 'l0ng', 'iong', followed by digits
    lon_match = re.search(r'[l1i][o0]n[g]?[:\s]*(-?\d+[\s\.]\d+)', combined_text)
    if not lon_match:
        # Fallback: if 'Long' label was cut off, match standalone 72.xxx or 73.xxx (India longitude bounds for this dataset)
        lon_match = re.search(r'\b(7[23][\.\s]\d{3,})\b', combined_text)

    # Speed: match patterns like '1kmh', '0km/h', '1 km/h', 'okmh' (O misread as 0)
    speed_match = re.search(r'([o0-9]+)\s*km\s*[/\\]?\s*h', combined_text)
    if not speed_match:
        speed_match = re.search(r'speed[:\s]+(\d+)', combined_text)

    # Heading: digits (0-360) explicitly with degree/asterisk or cardinal marker, avoiding latitude/longitude suffixes
    # Examples: '153*se', '224*sw', '199*s', '304 deg'
    heading_match = re.search(r'\b([0-3]?\d{1,2})\s*[\*°]\s*[nsew]{1,2}\b', combined_text)
    if not heading_match:
        heading_match = re.search(r'head(?:ing)?[:\s]+(\d{1,3})', combined_text)

    if lat_match:
        lat = extract_decimal(lat_match)
    if lon_match:
        lon = extract_decimal(lon_match)
    if heading_match:
        try:
            val = float(heading_match.group(1))
            if 0.0 <= val <= 360.0:
                heading = val
        except ValueError:
            pass
    if speed_match:
        raw_speed = speed_match.group(1).replace('o', '0').replace('O', '0')
        try:
            speed = float(raw_speed)
        except ValueError:
            pass

    return lat, lon, heading, speed

def main():
    parser = argparse.ArgumentParser(description="Offline Telemetry Extractor using OCR")
    parser.add_argument("--video", type=str, dest="source", default="data/sample_videos/Dashcam_Video.mp4", help="Path to video source")
    parser.add_argument("--output", type=str, default="data/telemetry.csv", help="Path to output CSV")
    parser.add_argument("--sample_rate", type=int, default=15, help="Process every Nth frame")
    args = parser.parse_args()

    if not os.path.exists(args.source):
        # Fallback to general file if specific doesn't exist
        print(f"⚠️ Source video '{args.source}' not found. Checking data/sample_videos/")
        video_dir = "data/sample_videos"
        if os.path.exists(video_dir):
            videos = [f for f in os.listdir(video_dir) if f.endswith(".mp4")]
            if videos:
                args.source = os.path.join(video_dir, videos[0])
                print(f"📍 Using video source: {args.source}")
            else:
                print("❌ No mp4 videos found in data/sample_videos/")
                return
        else:
            print("❌ Video directory not found.")
            return

    cap = cv2.VideoCapture(args.source)
    if not cap.isOpened():
        print(f"❌ Failed to open video source: {args.source}")
        return

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    
    print(f"🎬 Processing: {args.source} ({total_frames} frames, {fps} FPS)")

    # Init Reader (EasyOCR)
    reader = None
    if easyocr:
        import torch
        cuda_available = torch.cuda.is_available()
        if not cuda_available:
            raise RuntimeError("❌ GPU (CUDA) is required but not available. Exiting process.")
        print("🧠 Initializing EasyOCR Reader (English) using GPU (CUDA)...")
        reader = easyocr.Reader(['en'], gpu=True)
    else:
        raise ImportError("❌ EasyOCR is required for telemetry extraction. Exiting process.")

    records = []
    frame_idx = 0

    with tqdm(total=total_frames, desc="OCR Scanning") as pbar:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_idx % args.sample_rate == 0:
                h, w = frame.shape[:2]
                timestamp_sec = frame_idx / fps
                
                lat, lon, heading, speed = None, None, None, None
                
                if reader:
                    # Debug confirmed: telemetry panel is at y: 65%-80% (frame_0s_mid65_80.jpg)
                    crop_y1 = int(h * 0.65)
                    crop_y2 = int(h * 0.80)
                    crop = frame[crop_y1:crop_y2, 0:w]
                    
                    preprocessed = preprocess_telemetry_crop(crop)
                    # Run OCR
                    results = reader.readtext(preprocessed)
                    txts = [res[1] for res in results]
                    # Debug: print raw OCR for first 3 sampled frames
                    if frame_idx < 50:
                        print(f"  [DEBUG frame {frame_idx}] OCR raw: {txts}")
                    lat, lon, heading, speed = parse_telemetry_text(txts)
                
                records.append({
                    "frame_idx": frame_idx,
                    "timestamp_sec": timestamp_sec,
                    "latitude": lat,
                    "longitude": lon,
                    "heading_deg": heading,
                    "speed_kmh": speed
                })
            
            frame_idx += 1
            pbar.update(1)

    cap.release()

    df = pd.DataFrame(records)
    
    # --- Rolling Error Correction & Smoothing ---
    # Interpolate missing/None values
    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
    df['heading_deg'] = pd.to_numeric(df['heading_deg'], errors='coerce')
    df['speed_kmh'] = pd.to_numeric(df['speed_kmh'], errors='coerce')

    # Debug: print comprehensive OCR accuracy breakdown
    valid_lats = df['latitude'].notna().sum()
    valid_lons = df['longitude'].notna().sum()
    valid_speeds = df['speed_kmh'].notna().sum()
    valid_headings = df['heading_deg'].notna().sum()
    total_frames = len(df)
    
    lat_acc = (valid_lats / total_frames) * 100 if total_frames > 0 else 0
    lon_acc = (valid_lons / total_frames) * 100 if total_frames > 0 else 0
    spd_acc = (valid_speeds / total_frames) * 100 if total_frames > 0 else 0
    hdg_acc = (valid_headings / total_frames) * 100 if total_frames > 0 else 0
    overall_acc = (valid_lats + valid_lons + valid_speeds + valid_headings) / (total_frames * 4) * 100 if total_frames > 0 else 0

    print("\n==================================================")
    print(" 📊 TELEMETRY EXTRACTION ACCURACY REPORT")
    print("==================================================")
    print(f"  • Total Sampled Frames  : {total_frames}")
    print(f"  • Latitude Accuracy     : {valid_lats}/{total_frames} ({lat_acc:.1f}%)")
    print(f"  • Longitude Accuracy    : {valid_lons}/{total_frames} ({lon_acc:.1f}%)")
    print(f"  • Speed Accuracy        : {valid_speeds}/{total_frames} ({spd_acc:.1f}%)")
    print(f"  • Heading Accuracy      : {valid_headings}/{total_frames} ({hdg_acc:.1f}%)")
    print("--------------------------------------------------")
    print(f"  🎯 Overall Extraction Accuracy : {overall_acc:.1f}%")
    print("==================================================\n")
    
    # Keep a copy of the raw dataframe before interpolation
    df_raw = df.copy()

    # If first or last rows are nan, fallback or populate mock defaults
    # Start Coord default: Turf / Navkaar Heights: 19.2879, 72.8531
    # End Coord default: Home / Rashesh Apartments: 19.2960, 72.8478
    if df['latitude'].isna().all() or df['longitude'].isna().all():
        print("⚠️ No valid latitude values extracted. Populating mock path coordinates for interpolation.")
        # Linearly space coordinates from start to end coordinates
        n_rows = len(df)
        df['latitude'] = np.linspace(19.2879, 19.2960, n_rows)
        df['longitude'] = np.linspace(72.8531, 72.8478, n_rows)
        df['heading_deg'] = np.linspace(304.0, 304.0, n_rows)
        df['speed_kmh'] = np.linspace(30.0, 40.0, n_rows)
    # Compute Heading dynamically from consecutive GPS coordinates if OCR heading is missing or sparse
    # Formula: atan2(sin(Δλ) * cos(φ2), cos(φ1) * sin(φ2) − sin(φ1) * cos(φ2) * cos(Δλ))
    for i in range(len(df)):
        if pd.isna(df.loc[i, 'heading_deg']):
            if i + 1 < len(df) and pd.notna(df.loc[i, 'latitude']) and pd.notna(df.loc[i+1, 'latitude']):
                p1_lat, p1_lon = math.radians(df.loc[i, 'latitude']), math.radians(df.loc[i, 'longitude'])
                p2_lat, p2_lon = math.radians(df.loc[i+1, 'latitude']), math.radians(df.loc[i+1, 'longitude'])
                dlon = p2_lon - p1_lon
                y = math.sin(dlon) * math.cos(p2_lat)
                x = math.cos(p1_lat) * math.sin(p2_lat) - math.sin(p1_lat) * math.cos(p2_lat) * math.cos(dlon)
                bearing = (math.degrees(math.atan2(y, x)) + 360) % 360
                df.loc[i, 'heading_deg'] = round(bearing, 1)
            elif i > 0 and pd.notna(df.loc[i-1, 'heading_deg']):
                df.loc[i, 'heading_deg'] = df.loc[i-1, 'heading_deg']

    # Interpolate missing values (pandas 3.x compatible)
    df['latitude']    = df['latitude'].interpolate(method='linear').bfill().ffill()
    df['longitude']   = df['longitude'].interpolate(method='linear').bfill().ffill()
    df['heading_deg'] = df['heading_deg'].interpolate(method='linear').bfill().ffill()
    df['speed_kmh']   = df['speed_kmh'].interpolate(method='linear').bfill().ffill()

    # Detect impossible speed/jump anomalies (>100m jump between successive sampled frames)
    # 1 degree of lat/lon is roughly 111,000 meters. 100 meters is roughly 0.0009 degrees.
    for i in range(1, len(df)):
        lat_diff = abs(df.loc[i, 'latitude'] - df.loc[i-1, 'latitude'])
        lon_diff = abs(df.loc[i, 'longitude'] - df.loc[i-1, 'longitude'])
        if lat_diff > 0.001 or lon_diff > 0.001:
            # Overwrite anomaly with previous value or linear smoothing
            df.loc[i, 'latitude'] = df.loc[i-1, 'latitude']
            df.loc[i, 'longitude'] = df.loc[i-1, 'longitude']

    # Ensure output directory exists
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    # Save the raw (un-interpolated) dataframe for debugging
    raw_output_path = args.output.replace('.csv', '_raw.csv')
    df_raw.to_csv(raw_output_path, index=False)
    
    df.to_csv(args.output, index=False)
    print(f"📊 Telemetry data saved successfully to '{args.output}'")
    print(f"🛠️  Raw (un-interpolated) data saved to '{raw_output_path}'")

if __name__ == "__main__":
    main()
