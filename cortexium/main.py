import argparse
import cv2
import time
import os
import pandas as pd
import numpy as np

from core.video_input import VideoInput
from core.driver_context import DriverContextDetector
from core.vehicle_detector import VehicleDetector
from core.lane_detector import LaneDetector
from core.distance_estimator import DistanceEstimator
from core.behavior_analyzer import BehaviorAnalyzer
from core.rule_engine import RuleEngine
from core.feedback_display import FeedbackDisplay
from core.session_summary import SessionSummary
from utils.smoothing import Smoother
from core.nav_director import NavDirector
from core.audio_alerts import AudioAlertManager
from core.session_logger import SessionLogger
from core.report_generator import ReportGenerator
from core.ar_projector import ARProjector

def main():
    parser = argparse.ArgumentParser(description="CORTEXIUM - Context-Aware AI Driving Assistant")
    parser.add_argument("--source", type=str, default="0", help="Video source (webcam index or file path)")
    parser.add_argument("--telemetry", type=str, default="data/telemetry.csv", help="Path to telemetry CSV file")
    parser.add_argument("--offset", type=float, default=16.0, help="Sync offset in seconds between video and telemetry")
    parser.add_argument("--ar", "--ar_mode", dest="ar_mode", action="store_true", default=True, help="Enable AR display mode")
    parser.add_argument("--no_ar", dest="ar_mode", action="store_false", help="Disable AR display mode")
    parser.add_argument("--dest", type=str, default=None, help="Destination route (downtown, airport, mall)")
    args = parser.parse_args()

    print("🧠 Initializing Cortexium System...\n")
    
    # Init modules
    video_in = VideoInput(args.source)
    
    # HUD UI State
    # Create scalable window
    window_name = "CORTEXIUM OS"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 540, 960) # Fitted portrait aspect ratio

    path_active = True
    hud_alerts_active = True
    session_show_summary = False
    
    context_detector = DriverContextDetector()
    vehicle_detector = VehicleDetector()
    lane_detector = LaneDetector()
    dist_estimator = DistanceEstimator()
    behavior_analyzer = BehaviorAnalyzer()
    rule_engine = RuleEngine()
    feedback_display = FeedbackDisplay()
    session_summary = SessionSummary()
    nav_director = NavDirector(telemetry_file=args.telemetry)
    nav_director.print_route_summary()
    ar_projector = ARProjector()
    audio_alerts = AudioAlertManager()
    session_logger = SessionLogger()
    
    # Load Telemetry for GPS synchronization
    print(f"🛰️ Loading GPS telemetry from: {args.telemetry}...")
    telemetry_timestamps = None
    SYNC_OFFSET_SEC = args.offset  # Tunable manual time shift in seconds
    
    try:
        telemetry_path = args.telemetry
        if os.path.exists(telemetry_path):
            raw_df = pd.read_csv(telemetry_path)
            if 'timestamp_sec' in raw_df.columns:
                telemetry_df = raw_df.sort_values(by='timestamp_sec').reset_index(drop=True)
                telemetry_df = telemetry_df.interpolate(method='linear', limit_direction='both')
                telemetry_timestamps = telemetry_df['timestamp_sec'].to_numpy()
            elif 'frame_idx' in raw_df.columns:
                max_frame = int(raw_df['frame_idx'].max())
                telemetry_df = raw_df.set_index('frame_idx').reindex(range(max_frame + 200))
                telemetry_df = telemetry_df.interpolate(method='linear', limit_direction='both').reset_index()
                if 'timestamp_sec' in telemetry_df.columns:
                    telemetry_timestamps = telemetry_df['timestamp_sec'].to_numpy()
            else:
                telemetry_df = raw_df.interpolate(method='linear', limit_direction='both')
                if 'timestamp_sec' in telemetry_df.columns:
                    telemetry_timestamps = telemetry_df['timestamp_sec'].to_numpy()
        else:
            telemetry_df = None
    except Exception as e:
        print(f"⚠️ Error loading telemetry.csv: {e}")
        telemetry_df = None
        
    frame_count = 0
    last_nav_alert = ""
    announced_milestones = set()
    
    # State tracking to only speak alerts once on edge-trigger transition
    collision_active = False
    tailgating_active = False
    lane_drift_active = False
    steering_unstable_active = False
    score_critical_active = False
    
    # Smoothers
    score_smoother = Smoother(alpha=0.8)
    
    prev_time = time.time()
    
    # Frame skipping and cached AI inference state
    AI_SKIP_FRAMES = 3
    cached_in_car = True
    cached_detections = []
    cached_lane_lines = None
    cached_lane_center = None
    cached_lane_offset = 0.0
    cached_min_dist = float('inf')
    cached_distances = {}
    cached_collision_risk = False
    cached_metrics = {}
    cached_score = 100
    cached_suggestions = []

    print("🚀 Pipeline active.")
    print("⌨️ Controls: [P] Toggle Path  |  [A] Toggle HUD Alerts  |  [M] Mute/Unmute Audio  |  [S] Show Summary & Exit  |  [Q]/[ESC] Exit")
    
    while True:
        ret, frame = video_in.get_frame()
        if not ret:
            if video_in.cap and video_in.cap.isOpened():
                video_in.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                frame_count = 0
                ret, frame = video_in.get_frame()
            if not ret:
                print("End of video stream or error.")
                break
            
        # Track frames
        frame_count += 1
        
        # --- ABSOLUTE TIME-BASED TELEMETRY SYNCHRONIZATION ---
        curr_lat, curr_lon = None, None
        curr_speed, curr_heading = None, None
        
        if telemetry_df is not None:
            # Query exact video playback time in seconds
            video_time_sec = video_in.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0 if video_in.cap else (frame_count / 30.0)
            adjusted_time_sec = video_time_sec + SYNC_OFFSET_SEC
            
            if telemetry_timestamps is not None and len(telemetry_timestamps) > 0:
                # Fast binary search for closest timestamp in the numpy array
                idx = int(np.searchsorted(telemetry_timestamps, adjusted_time_sec, side='left'))
                sync_idx = max(0, min(idx, len(telemetry_df) - 1))
            else:
                sync_idx = max(0, min(frame_count, len(telemetry_df) - 1))

            try:
                curr_lat = telemetry_df.loc[sync_idx, 'latitude']
                curr_lon = telemetry_df.loc[sync_idx, 'longitude']
                curr_speed = telemetry_df.loc[sync_idx, 'speed_kmh'] if 'speed_kmh' in telemetry_df.columns else 0.0
                curr_heading = telemetry_df.loc[sync_idx, 'heading_deg'] if 'heading_deg' in telemetry_df.columns else None
            except KeyError as e:
                print(f"⚠️ Telemetry column lookup error: {e}")
                
        is_vehicle_moving = (curr_speed is not None and curr_speed >= 1.5)
        nav_type, nav_alert, maneuver_text, distance_m = nav_director.get_current_nav_state(
            curr_lat, curr_lon, curr_heading=curr_heading, curr_speed=curr_speed, is_moving=is_vehicle_moving, frame_idx=sync_idx if telemetry_df is not None else frame_count
        )

        # Synchronized Milestone Audio Announcements (Gated by movement)
        if is_vehicle_moving and nav_alert:
            if nav_alert != last_nav_alert:
                # Initial announcement on new maneuver step
                spoken_phrase = f"In {int(distance_m)} meters, {nav_alert}" if distance_m > 30 else nav_alert
                audio_alerts.speak(spoken_phrase, "normal")
                last_nav_alert = nav_alert
                announced_milestones = set()
            else:
                # Milestone triggers (200m, 100m, 50m)
                for milestone in [200, 100, 50]:
                    if milestone not in announced_milestones and distance_m <= milestone and distance_m > (milestone - 15):
                        audio_alerts.speak(f"In {milestone} meters, {nav_alert}", "normal")
                        announced_milestones.add(milestone)
                        break
            
        # FPS calc
        current_time = time.time()
        fps = 1 / (current_time - prev_time) if (current_time - prev_time) > 0 else 0
        prev_time = current_time

        if session_show_summary:
            break

        if path_active or hud_alerts_active:
            # 1. Driver Context & Heavy AI Inference (Executed every AI_SKIP_FRAMES or on 1st frame)
            if frame_count == 1 or frame_count % AI_SKIP_FRAMES == 0:
                cached_in_car = context_detector.detect(frame)
                
                if cached_in_car:
                    # 2. Vehicle Detection
                    cached_detections = vehicle_detector.detect(frame)
                    
                    # 3. Lane Detection
                    cached_lane_lines, cached_lane_center, cached_lane_offset = lane_detector.detect(frame)
                    
                    # 4. Distance Estimation
                    cached_min_dist, cached_distances, cached_collision_risk = dist_estimator.estimate(cached_detections)
                    
                    # 5. Behavior Analysis
                    cached_metrics = behavior_analyzer.analyze(cached_lane_offset, cached_min_dist)
                    
                    # Core Integration 2 (Behavior Scoring Override)
                    # Suppress lane-drifting warning and score deductions during turns/curves
                    if nav_type != "straight":
                        cached_metrics["lane_deviation"] = 0.0
                        cached_metrics["lane_stability"] = 0.0
                    
                    # 6. Rule Engine
                    cached_score, cached_suggestions = rule_engine.evaluate(cached_metrics, cached_collision_risk)

            in_car = cached_in_car
            if not in_car:
                cv2.putText(frame, "System Idle - Driver Not Detected", (50, 50), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                feedback_display.draw_key_guide(frame, audio_muted=audio_alerts.muted)
                cv2.imshow("CORTEXIUM OS", frame)
                
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:
                    break
                elif key == ord('p'):
                    path_active = not path_active
                    print(f"⌨️ Keyboard: Toggle Path -> {path_active}")
                elif key == ord('a'):
                    hud_alerts_active = not hud_alerts_active
                    print(f"⌨️ Keyboard: Toggle Alerts -> {hud_alerts_active}")
                elif key == ord('m'):
                    audio_alerts.muted = not audio_alerts.muted
                    print(f"⌨️ Keyboard: Toggle Mute Audio -> {audio_alerts.muted}")
                continue

            # Assign cached AI data for this frame
            detections = cached_detections
            lane_lines = cached_lane_lines
            lane_center = cached_lane_center
            lane_offset = cached_lane_offset
            min_dist = cached_min_dist
            distances = cached_distances
            collision_risk = cached_collision_risk
            metrics = cached_metrics
            score = cached_score
            suggestions = cached_suggestions
            
            # Smooth score to avoid jittering
            smoothed_score = int(score_smoother.smooth(score))
            
            # Update Session Summary
            session_summary.update(smoothed_score, suggestions)
            
            # Update Session Logger
            session_logger.log_frame(smoothed_score, suggestions, min_dist)
            
            # Trigger non-blocking spoken TTS alerts (state-transition based + custom alert cooldowns)
            
            # 1. Collision Warning
            if collision_risk:
                if not collision_active:
                    audio_alerts.speak("Warning. Collision risk.", "critical", cooldown=6.0)
                    collision_active = True
            else:
                collision_active = False
                
            # Rest of alerts are only triggered if there is no immediate collision warning
            if not collision_risk:
                # 2. Tailgating Warning (distance value too low, threshold adjusted to 12.0m to reduce sensitivity)
                following_dist = metrics.get("following_distance", float('inf'))
                if following_dist < 12.0:
                    if not tailgating_active:
                        audio_alerts.speak("You're following too close", "normal", cooldown=20.0)
                        tailgating_active = True
                else:
                    tailgating_active = False
                    
                # Only check lane-drifting and unstable steering on straight roads
                if nav_type == "straight":
                    # 3. Lane Drift (threshold adjusted to 0.38m to tolerate normal lane changes)
                    if metrics.get("lane_deviation", 0) > 0.38:
                        if not lane_drift_active:
                            audio_alerts.speak("Lane drift detected", "normal", cooldown=20.0)
                            lane_drift_active = True
                    else:
                        lane_drift_active = False
                        
                    # 4. Steering Instability (threshold adjusted to 0.58 to reduce sensitivity)
                    if metrics.get("lane_stability", 0) > 0.58:
                        if not steering_unstable_active:
                            audio_alerts.speak("Steering unstable", "normal", cooldown=25.0)
                            steering_unstable_active = True
                    else:
                        steering_unstable_active = False
                else:
                    lane_drift_active = False
                    steering_unstable_active = False
            else:
                tailgating_active = False
                lane_drift_active = False
                steering_unstable_active = False
                
            # 5. Safety Score Critical (safety score below 50, repeat cooldown set to 30s)
            if smoothed_score < 50:
                if not score_critical_active:
                    audio_alerts.speak("Safety score critical", "critical", cooldown=30.0)
                    score_critical_active = True
            else:
                score_critical_active = False
            
            # Detect active safety alerts
            active_alert = None
            if collision_risk:
                active_alert = "collision risk detected"
            elif metrics.get("following_distance", float('inf')) < 12.0:
                active_alert = "tailgating detected"
            elif nav_type == "straight" and metrics.get("lane_deviation", 0) > 0.38:
                active_alert = "lane drift detected"
            elif nav_type == "straight" and metrics.get("lane_stability", 0) > 0.58:
                active_alert = "steering unstable"

            # --- 1. Target Street Name Resolution ---
            target_street = ""
            if hasattr(nav_director, 'route_steps') and nav_director.route_steps:
                curr_step = nav_director.route_steps[nav_director.current_step_idx]
                target_street = curr_step.get('street_name', '')
                if not target_street and 'onto' in maneuver_text.lower():
                    target_street = maneuver_text.split('onto', 1)[-1].strip()
                elif not target_street and 'on' in maneuver_text.lower():
                    target_street = maneuver_text.split('on', 1)[-1].strip()

            if not target_street:
                target_street = "MAIN CORRIDOR"

            # --- 2. Actionable Driving Problem & Suggestion ---
            detailed_problem = "OPTIMAL"
            action_suggestion = "MAINTAIN PACE"

            if collision_risk:
                detailed_problem = "COLLISION HAZARD"
                action_suggestion = "BRAKE IMMEDIATELY"
            elif metrics.get("following_distance", float('inf')) < 12.0:
                detailed_problem = "TAILGATING HAZARD"
                action_suggestion = "EXPAND GAP (>3 SEC)"
            elif nav_type == "straight" and metrics.get("lane_deviation", 0) > 0.38:
                detailed_problem = "LANE DEVIATION"
                action_suggestion = "RECENTER VEHICLE"
            elif nav_type == "straight" and metrics.get("lane_stability", 0) > 0.58:
                detailed_problem = "UNSTABLE STEERING"
                action_suggestion = "STEADY TRAJECTORY"
            elif suggestions:
                detailed_problem = "DRIVING ADVISORY"
                action_suggestion = suggestions[0].upper()

            # Dynamic speed limit from telemetry dataframe
            dynamic_speed_limit = 40
            if telemetry_df is not None and 'speed_limit' in telemetry_df.columns:
                try:
                    val = telemetry_df.loc[frame_count, 'speed_limit']
                    if pd.notna(val) and int(val) > 0:
                        dynamic_speed_limit = int(val)
                except (KeyError, ValueError):
                    pass
            elif nav_type == "straight" and curr_speed and curr_speed > 60:
                dynamic_speed_limit = 60

            # Dynamic Safety Category
            if collision_risk or smoothed_score < 45:
                dynamic_safety = "Critical Risk"
            elif smoothed_score < 70 or metrics.get("following_distance", float('inf')) < 15.0:
                dynamic_safety = "Moderate Risk"
            else:
                dynamic_safety = "Low Risk"

            current_telemetry = {
                'speed': int(curr_speed) if curr_speed is not None else 0,
                'speed_limit': dynamic_speed_limit,
                'problem': detailed_problem,
                'suggestion': action_suggestion,
                'street_name': target_street.upper(),
                'safety': dynamic_safety,
                'score': smoothed_score,
                'fps': int(fps),
                'maneuver': maneuver_text if maneuver_text else "",
                'distance': distance_m if distance_m is not None else 999,
                'alert': active_alert,
                'muted': audio_alerts.muted,
                'path_active': path_active,
                'hud_active': hud_alerts_active
            }

            # 7. AR Feedback Display
            if args.ar_mode:
                # Retain YOLO bounding boxes, distance tags, and context
                display_frame = feedback_display.display(
                    frame, detections, distances, collision_risk,
                    lane_lines, lane_center, smoothed_score, suggestions,
                    nav_type, nav_alert, path_active, hud_alerts_active,
                    audio_muted=audio_alerts.muted
                )
                if path_active or hud_alerts_active:
                    display_frame = ar_projector.render_ui(display_frame, current_telemetry)

                # Draw FPS (Only in landscape mode to declutter portrait screen)
                if display_frame.shape[0] <= display_frame.shape[1]:
                    cv2.putText(display_frame, f"FPS: {int(fps)}", (20, 30), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
                            
                cv2.imshow("CORTEXIUM OS", display_frame)
            else:
                feedback_display.draw_key_guide(frame, audio_muted=audio_alerts.muted)
                if path_active or hud_alerts_active:
                    frame = ar_projector.render_ui(frame, current_telemetry)
                cv2.imshow("CORTEXIUM OS", frame)
        else:
            display_frame = feedback_display.draw_idle_screen(frame, audio_muted=audio_alerts.muted)
            cv2.imshow("CORTEXIUM OS", display_frame)
            
        # Window event pump and pacing (~30 FPS)
        key = cv2.waitKey(30) & 0xFF
        if key == ord('q') or key == 27: # q or ESC to exit
            break
        elif key == ord('p'): # P to toggle Path
            path_active = not path_active
            print(f"⌨️ Keyboard: Toggle Path -> {path_active}")
        elif key == ord('a'): # A to toggle Alerts HUD
            hud_alerts_active = not hud_alerts_active
            print(f"⌨️ Keyboard: Toggle Alerts HUD -> {hud_alerts_active}")
        elif key == ord('m'): # M to toggle audio mute
            audio_alerts.muted = not audio_alerts.muted
            print(f"⌨️ Keyboard: Toggle Mute Audio -> {audio_alerts.muted}")
        elif key == ord('s'): # S to show summary and exit
            session_show_summary = True
            print("⌨️ Keyboard: Showing summary and exiting...")

    video_in.release()
    cv2.destroyAllWindows()
    
    session_summary.print_summary()
    
    # Process history logging and trend analysis
    history = []
    try:
        from core.trend_analyzer import TrendAnalyzer
        # Save current session to history database
        history = TrendAnalyzer.save_session_to_history(session_logger.get_logs())
        
        # Output trend comparison report to terminal
        if len(history) >= 2:
            trends = TrendAnalyzer.analyze_trends(history)
            print("\n========================================")
            print(" 📈 CORTEXIUM - Safety Trend Analysis")
            print("========================================")
            score_change = trends['score_trend']
            dir_str = "IMPROVEMENT" if trends['improvement'] else "REGRESSION"
            print(f" 🎯 Safety Score Change: {score_change:+.1f}% ({dir_str})")
            print("----------------------------------------")
            print(" 💡 Coaching Recommendations:")
            for line in trends['feedback'].split('\n'):
                print(f"    {line}")
            print("========================================\n")
    except Exception as e:
        print(f"⚠️ Error performing safety trend analysis: {e}")
        
    # Auto-generate session safety report PDF
    try:
        pdf_path = ReportGenerator.generate_pdf(session_logger.get_logs(), history=history)
        if pdf_path:
            print(f"📄 Driving session report saved to: {os.path.abspath(pdf_path)}")
    except Exception as e:
        print(f"⚠️ Error generating driving session report: {e}")

if __name__ == "__main__":
    main()