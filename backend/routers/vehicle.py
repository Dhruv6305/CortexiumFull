"""
Cortexium 2.0 — Vehicle Telemetry & AR HUD Router
===================================================
Integrates the Cortexium Context-Aware AI Driving Assistant & AR HUD System (Module 3).
Provides real-time perception, telemetry synchronization, 3D AR projection overlays,
driver behavior scoring, and PDF diagnostic report generation.
"""
import os
import sys
import time
import base64
import numpy as np
import cv2
import pandas as pd
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from typing import Optional, List, Dict

# Ensure cortexium module root is in sys.path
_THIS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _THIS_DIR.parent
_ROOT_DIR = _BACKEND_DIR.parent
_CORTEXIUM_MODULE_DIR = _ROOT_DIR / "cortexium"

if str(_CORTEXIUM_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_CORTEXIUM_MODULE_DIR))

# Import cortexium core modules
try:
    from core.vehicle_detector import VehicleDetector
    from core.lane_detector import LaneDetector
    from core.distance_estimator import DistanceEstimator
    from core.behavior_analyzer import BehaviorAnalyzer
    from core.rule_engine import RuleEngine
    from core.feedback_display import FeedbackDisplay
    from core.session_summary import SessionSummary
    from core.nav_director import NavDirector
    from core.ar_projector import ARProjector
    from core.session_logger import SessionLogger
    from core.report_generator import ReportGenerator
    from utils.smoothing import Smoother
    CORTEXIUM_VEHICLE_AVAILABLE = True
except Exception as e:
    print(f"[VehicleRouter] WARNING: Could not import cortexium core modules: {e}")
    CORTEXIUM_VEHICLE_AVAILABLE = False


router = APIRouter(prefix="/api/vehicle", tags=["vehicle"])

# Singleton state for Vehicle Module
class VehiclePipeline:
    def __init__(self):
        self.sample_videos_dir = _CORTEXIUM_MODULE_DIR / "data" / "sample_videos"
        self.sample_videos_dir.mkdir(parents=True, exist_ok=True)
        self.active_video_name = "Dashcam_Video.mp4"
        self.active_video_path = str(self.sample_videos_dir / self.active_video_name)
        self.telemetry_path = str(_CORTEXIUM_MODULE_DIR / "data" / "telemetry.csv")
        self.telemetry_df = None
        self.telemetry_timestamps = None
        self.frame_count = 0
        self.start_time = time.time()
        self.current_score = 100
        self.last_alerts = []
        self.cap = None
        self.process = None

        self.enabled = CORTEXIUM_VEHICLE_AVAILABLE
        if not self.enabled:
            return

        try:
            self.vehicle_detector = VehicleDetector()
            self.lane_detector = LaneDetector()
            self.dist_estimator = DistanceEstimator()
            self.behavior_analyzer = BehaviorAnalyzer()
            self.rule_engine = RuleEngine()
            self.feedback_display = FeedbackDisplay()
            self.session_summary = SessionSummary()
            self.nav_director = NavDirector(telemetry_file=self.telemetry_path)
            self.ar_projector = ARProjector()
            self.session_logger = SessionLogger()
            self.score_smoother = Smoother(alpha=0.8)
            self._load_telemetry()
        except Exception as e:
            print(f"[VehiclePipeline] Error initializing core modules: {e}")
            self.enabled = False

    def start_main_process(self, video_name: Optional[str] = None):
        import subprocess
        if video_name:
            self.set_active_video(video_name)

        if self.process is not None and self.process.poll() is None:
            self.stop_main_process()

        # Check cortexium/venv first, then workspace .venv, then sys.executable
        cortexium_venv_python = _CORTEXIUM_MODULE_DIR / "venv" / "Scripts" / "python.exe"
        workspace_venv_python = _ROOT_DIR / ".venv" / "Scripts" / "python.exe"

        if cortexium_venv_python.exists():
            python_cmd = str(cortexium_venv_python)
        elif workspace_venv_python.exists():
            python_cmd = str(workspace_venv_python)
        else:
            python_cmd = sys.executable

        rel_video = f"data/sample_videos/{self.active_video_name}"
        try:
            rel_telemetry = os.path.relpath(self.telemetry_path, str(_CORTEXIUM_MODULE_DIR))
        except Exception:
            rel_telemetry = "data/telemetry.csv"

        # Use cmd.exe /c start to open a new interactive console window on Windows
        if os.name == 'nt':
            cmd = ["cmd.exe", "/c", "start", "CORTEXIUM OS", python_cmd, "main.py", "--source", rel_video, "--telemetry", rel_telemetry]
        else:
            cmd = [python_cmd, "main.py", "--source", rel_video, "--telemetry", rel_telemetry]

        print(f"[VehiclePipeline] Launching Cortexium main.py: {' '.join(cmd)}")

        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=str(_CORTEXIUM_MODULE_DIR)
            )
            return {
                "status": "started",
                "pid": self.process.pid,
                "video": self.active_video_name,
                "telemetry": rel_telemetry,
                "python_used": python_cmd
            }
        except Exception as e:
            print(f"[VehiclePipeline] Error launching main.py subprocess: {e}")
            raise RuntimeError(f"Could not launch native main.py: {e}")

    def stop_main_process(self):
        if self.process is not None and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except Exception:
                self.process.kill()
            self.process = None
            return {"status": "stopped"}
        return {"status": "not_running"}

    def is_process_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def _load_telemetry(self):
        try:
            if os.path.exists(self.telemetry_path):
                raw_df = pd.read_csv(self.telemetry_path)
                if 'timestamp_sec' in raw_df.columns:
                    self.telemetry_df = raw_df.sort_values(by='timestamp_sec').reset_index(drop=True)
                    self.telemetry_df = self.telemetry_df.interpolate(method='linear', limit_direction='both')
                    self.telemetry_timestamps = self.telemetry_df['timestamp_sec'].to_numpy()
                else:
                    self.telemetry_df = raw_df.interpolate(method='linear', limit_direction='both')
                    if 'timestamp_sec' in self.telemetry_df.columns:
                        self.telemetry_timestamps = self.telemetry_df['timestamp_sec'].to_numpy()
                print(f"[VehiclePipeline] Telemetry loaded ({len(self.telemetry_df)} records)")
        except Exception as e:
            print(f"[VehiclePipeline] Telemetry load warning: {e}")

    def set_active_video(self, video_name: str, telemetry_name: Optional[str] = None):
        video_file = self.sample_videos_dir / video_name
        if not video_file.exists():
            raise FileNotFoundError(f"Video file '{video_name}' not found")

        self.active_video_name = video_name
        self.active_video_path = str(video_file)

        # Match corresponding telemetry CSV if available
        if telemetry_name:
            t_path = _CORTEXIUM_MODULE_DIR / "data" / telemetry_name
            if t_path.exists():
                self.telemetry_path = str(t_path)
                self._load_telemetry()
        elif "NavTesting_2" in video_name:
            t_path = _CORTEXIUM_MODULE_DIR / "data" / "telemetry_nav2.csv"
            if t_path.exists():
                self.telemetry_path = str(t_path)
                self._load_telemetry()
        elif "NavTesting_3" in video_name:
            t_path = _CORTEXIUM_MODULE_DIR / "data" / "telemetry_nav3.csv"
            if t_path.exists():
                self.telemetry_path = str(t_path)
                self._load_telemetry()

        # Reset capture
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        self.start_time = time.time()
        self.frame_count = 0
        return {"active_video": video_name, "telemetry_path": self.telemetry_path}

    def generate_mjpeg_stream(self):
        if not os.path.exists(self.active_video_path):
            print(f"[VehiclePipeline] Video path not found: {self.active_video_path}")
            return

        cap = cv2.VideoCapture(self.active_video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        delay = 1.0 / fps

        frame_idx = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                # Loop video
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                frame_idx = 0
                continue

            frame_idx += 1
            elapsed_sec = frame_idx / fps

            # Process through perception & AR projection pipeline if enabled
            if getattr(self, 'enabled', False) and hasattr(self, 'vehicle_detector'):
                rendered_frame, _ = self.process_frame(frame, elapsed_sec=elapsed_sec)
            else:
                rendered_frame = frame

            # Encode frame to JPEG
            _, jpeg = cv2.imencode(".jpg", rendered_frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            frame_bytes = jpeg.tobytes()

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
            time.sleep(delay * 0.5)  # Smooth streaming rate

        cap.release()

    def get_synced_telemetry(self, elapsed_sec: float) -> dict:
        if self.telemetry_df is None or len(self.telemetry_df) == 0:
            speed_kmh = round(max(0.0, min(120.0, 62.0 + np.sin(elapsed_sec * 0.2) * 20.0)), 1)
            dist_m = round(max(6.0, min(60.0, 24.0 + np.cos(elapsed_sec * 0.25) * 12.0)), 1)
            lane_off = round(np.sin(elapsed_sec * 0.15) * 0.35, 2)
            fcw = dist_m < 12.0
            score = max(50, min(100, int(98 - (15.0 if fcw else 0.0) - abs(lane_off) * 12.0)))
            return {
                "active_video": self.active_video_name,
                "latitude": 37.774929 + np.sin(elapsed_sec * 0.01) * 0.001,
                "longitude": -122.419416 + np.cos(elapsed_sec * 0.01) * 0.001,
                "speed_mph": round(speed_kmh / 1.60934, 1),
                "speed_kmh": speed_kmh,
                "heading": round((elapsed_sec * 5.0) % 360, 1),
                "safety_score": score,
                "min_distance_m": dist_m,
                "lane_offset_m": lane_off,
                "collision_risk": fcw,
                "synced": False
            }

        idx = 0
        if self.telemetry_timestamps is not None and len(self.telemetry_timestamps) > 0:
            idx = int(np.searchsorted(self.telemetry_timestamps, elapsed_sec, side='left'))
            idx = max(0, min(idx, len(self.telemetry_df) - 1))
        else:
            idx = int((elapsed_sec * 10.0) % len(self.telemetry_df))

        row = self.telemetry_df.iloc[idx]
        speed_val = float(row.get("speed_mph", row.get("speed_kmh", row.get("speed", 45.0))))
        if speed_val < 60:
            speed_kmh = round(speed_val * 1.60934, 1)
            speed_mph = round(speed_val, 1)
        else:
            speed_kmh = round(speed_val, 1)
            speed_mph = round(speed_val / 1.60934, 1)

        dist_m = round(float(row.get("distance_m", 18.5 + np.sin(idx * 0.15) * 8.0)), 1)
        lane_off = round(float(row.get("lane_offset_m", np.sin(idx * 0.08) * 0.35)), 2)
        fcw = dist_m < 12.0
        score = max(50, min(100, int(98 - (15.0 if fcw else 0.0) - abs(lane_off) * 12.0)))

        return {
            "active_video": self.active_video_name,
            "latitude": float(row.get("latitude", row.get("lat", 37.7749))),
            "longitude": float(row.get("longitude", row.get("lon", -122.4194))),
            "speed_mph": speed_mph,
            "speed_kmh": speed_kmh,
            "heading": float(row.get("heading", 0.0)),
            "safety_score": score,
            "min_distance_m": dist_m,
            "lane_offset_m": lane_off,
            "collision_risk": fcw,
            "synced": True,
            "record_index": idx,
        }

    def process_frame(self, frame: np.ndarray, elapsed_sec: float = None) -> tuple[np.ndarray, dict]:
        if elapsed_sec is None:
            elapsed_sec = time.time() - self.start_time

        self.frame_count += 1

        # 1. Perception
        detections = self.vehicle_detector.detect(frame)
        left_line, right_line, lane_center, lane_offset = self.lane_detector.detect(frame)
        
        # 2. Ranging & Collision Risk
        min_dist, distances = self.dist_estimator.estimate(frame, detections)
        collision_risk = min_dist < 12.0

        # 3. Telemetry & Navigation
        telemetry = self.get_synced_telemetry(elapsed_sec)
        nav_info = self.nav_director.get_nav_info(telemetry["latitude"], telemetry["longitude"])

        # 4. Behavior & Rules
        metrics = self.behavior_analyzer.analyze(lane_offset, min_dist, telemetry["speed_mph"])
        alerts, raw_score = self.rule_engine.evaluate(metrics, collision_risk)
        smooth_score = int(self.score_smoother.smooth(raw_score))
        self.current_score = smooth_score

        # Log frame
        self.session_logger.log_frame(
            timestamp=elapsed_sec,
            score=smooth_score,
            alerts=alerts,
            min_dist=min_dist,
            lane_offset=lane_offset,
            speed=telemetry["speed_mph"]
        )

        # 5. AR HUD Render
        rendered_frame = self.ar_projector.project(
            frame,
            left_line=left_line,
            right_line=right_line,
            detections=detections,
            distances=distances,
            nav_info=nav_info,
            telemetry=telemetry,
            collision_risk=collision_risk,
            alerts=alerts,
            score=smooth_score
        )

        hud_data = {
            "timestamp": round(elapsed_sec, 2),
            "frame_count": self.frame_count,
            "safety_score": smooth_score,
            "min_distance_m": round(float(min_dist), 1) if min_dist != float('inf') else None,
            "collision_risk": collision_risk,
            "lane_offset_m": round(float(lane_offset), 2),
            "telemetry": telemetry,
            "nav_info": nav_info,
            "alerts": alerts,
            "vehicle_count": len(detections),
        }

        return rendered_frame, hud_data


# Singleton instance
vehicle_pipeline = VehiclePipeline()


class SelectVideoData(BaseModel):
    video_name: str
    telemetry_name: Optional[str] = None


class VehicleFrameData(BaseModel):
    frame_b64: str
    timestamp_sec: Optional[float] = None


@router.get("/status")
async def vehicle_status():
    is_running = vehicle_pipeline.is_process_running() if hasattr(vehicle_pipeline, 'is_process_running') else False
    pid = vehicle_pipeline.process.pid if is_running and hasattr(vehicle_pipeline, 'process') and vehicle_pipeline.process else None
    return {
        "status": "active" if getattr(vehicle_pipeline, 'enabled', False) else "disabled",
        "module": "Vehicle Telemetry & 3D AR HUD",
        "telemetry_synced": getattr(vehicle_pipeline, 'telemetry_df', None) is not None,
        "current_score": getattr(vehicle_pipeline, 'current_score', 100),
        "frame_count": getattr(vehicle_pipeline, 'frame_count', 0),
        "active_video": getattr(vehicle_pipeline, 'active_video_name', 'Dashcam_Video.mp4'),
        "is_process_running": is_running,
        "process_pid": pid,
    }


@router.post("/start-process")
async def start_vehicle_process(data: Optional[SelectVideoData] = None):
    """Start native Cortexium main.py video perception process."""
    video_name = data.video_name if data else None
    try:
        res = vehicle_pipeline.start_main_process(video_name)
        return {"success": True, "details": res}
    except Exception as e:
        raise HTTPException(500, detail=f"Failed to start vehicle process: {e}")


@router.post("/stop-process")
async def stop_vehicle_process():
    """Stop native Cortexium main.py video perception process."""
    res = vehicle_pipeline.stop_main_process()
    return {"success": True, "details": res}


@router.get("/sample-videos")
async def get_sample_videos():
    """List available driving sample videos in cortexium/data/sample_videos."""
    videos_dir = vehicle_pipeline.sample_videos_dir
    video_files = list(videos_dir.glob("*.mp4")) + list(videos_dir.glob("*.avi")) + list(videos_dir.glob("*.mov"))
    
    result = []
    for f in sorted(video_files, key=lambda x: x.name):
        size_mb = round(f.stat().st_size / (1024 * 1024), 1)
        result.append({
            "name": f.name,
            "size_mb": size_mb,
            "path": str(f.relative_to(_CORTEXIUM_MODULE_DIR)),
            "is_active": f.name == vehicle_pipeline.active_video_name
        })
    return {"videos": result}


@router.post("/select-video")
async def select_video(data: SelectVideoData):
    """Select active driving video source for perception processing."""
    try:
        res = vehicle_pipeline.set_active_video(data.video_name, data.telemetry_name)
        return {"success": True, "details": res}
    except Exception as e:
        raise HTTPException(400, detail=str(e))


@router.post("/upload-video")
async def upload_video(file: UploadFile = File(...)):
    """Upload a custom driving video file."""
    if not file.filename.lower().endswith((".mp4", ".avi", ".mov")):
        raise HTTPException(400, "Only video files (.mp4, .avi, .mov) are allowed")

    target_path = vehicle_pipeline.sample_videos_dir / file.filename
    try:
        contents = await file.read()
        with open(target_path, "wb") as f:
            f.write(contents)
        
        # Set as active video
        vehicle_pipeline.set_active_video(file.filename)
        return {
            "success": True,
            "filename": file.filename,
            "message": f"Video '{file.filename}' uploaded and set as active source."
        }
    except Exception as e:
        raise HTTPException(500, detail=f"Failed to save uploaded video: {e}")


@router.get("/stream")
async def video_feed():
    """MJPEG Live Stream endpoint serving real-time OpenCV + YOLOv8 + AR HUD perception frames."""
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        vehicle_pipeline.generate_mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.get("/telemetry")
async def get_vehicle_telemetry(elapsed: Optional[float] = None):
    if elapsed is None:
        elapsed = time.time() - vehicle_pipeline.start_time
    return vehicle_pipeline.get_synced_telemetry(elapsed)


@router.post("/process-frame")
async def process_vehicle_frame(data: VehicleFrameData):
    if not vehicle_pipeline.enabled:
        raise HTTPException(500, detail="Vehicle module not available")

    # Decode frame
    try:
        b64_clean = data.frame_b64.split(",")[-1]
        img_bytes = base64.b64decode(b64_clean)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("Could not decode frame image")
    except Exception as e:
        raise HTTPException(400, detail=f"Invalid base64 frame: {e}")

    # Process frame through pipeline
    rendered_frame, metrics = vehicle_pipeline.process_frame(frame, data.timestamp_sec)

    # Encode output frame back to base64
    _, buf = cv2.imencode(".jpg", rendered_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    out_b64 = "data:image/jpeg;base64," + base64.b64encode(buf).decode("utf-8")

    return {
        "rendered_frame": out_b64,
        "metrics": metrics,
    }


@router.post("/report")
async def generate_pdf_report():
    """Generate post-trip PDF report for current session."""
    if not vehicle_pipeline.enabled:
        raise HTTPException(500, detail="Vehicle module not available")

    try:
        rg = ReportGenerator()
        report_path = rg.generate_report(vehicle_pipeline.session_logger)
        if report_path and os.path.exists(report_path):
            filename = Path(report_path).name
            return {
                "success": True,
                "filename": filename,
                "download_url": f"/api/vehicle/pdf/{filename}",
                "report_path": report_path
            }
        else:
            raise HTTPException(500, detail="PDF report generation failed")
    except Exception as e:
        raise HTTPException(500, detail=f"Error generating PDF report: {e}")


@router.get("/reports")
async def list_reports():
    """List available post-trip PDF session reports."""
    reports_dir = _CORTEXIUM_MODULE_DIR
    files = sorted(reports_dir.glob("session_report_*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    return {
        "reports": [
            {
                "filename": f.name,
                "size_bytes": f.stat().st_size,
                "created_at": time.ctime(f.stat().st_mtime),
                "download_url": f"/api/vehicle/pdf/{f.name}"
            }
            for f in files
        ]
    }


@router.get("/pdf/{filename}")
async def download_pdf_report(filename: str):
    """Download a specific PDF session report."""
    if not filename.endswith(".pdf") or ".." in filename:
        raise HTTPException(400, "Invalid filename")

    filepath = _CORTEXIUM_MODULE_DIR / filename
    if not filepath.exists():
        raise HTTPException(404, f"Report file '{filename}' not found")

    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="application/pdf"
    )
