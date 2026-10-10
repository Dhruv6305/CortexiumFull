import os
import json
import time
from config import DATA_DIR

class TrendAnalyzer:
    @staticmethod
    def save_session_to_history(logs):
        """
        Processes the current session logs, appends them to data/session_history.json,
        and bootstraps history with mock data if the file is empty or doesn't exist.
        Returns the full list of all sessions in history.
        """
        if not logs:
            return []
            
        history_file = os.path.join(DATA_DIR, 'session_history.json')
        
        # Calculate summary statistics for the current run
        duration = logs[-1]['timestamp']
        scores = [log['score'] for log in logs]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        tailgating_count = sum(1 for log in logs if log['tailgating'])
        lane_drift_count = sum(1 for log in logs if log['lane_drift'])
        unstable_steering_count = sum(1 for log in logs if log['unstable_steering'])
        collision_risk_count = sum(1 for log in logs if log['collision_risk'])
        
        current_session = {
            "timestamp": int(time.time()),
            "duration": round(duration, 1),
            "avg_score": round(avg_score, 1),
            "tailgating": tailgating_count,
            "lane_drift": lane_drift_count,
            "unstable_steering": unstable_steering_count,
            "collision_risk": collision_risk_count
        }
        
        history = []
        # Load existing history
        try:
            if os.path.exists(history_file):
                with open(history_file, 'r') as f:
                    history = json.load(f)
        except Exception as e:
            print(f"⚠️ Error reading session history file: {e}")
            
        # Bootstrap with 3 mock sessions if empty/missing to immediately provide a trend comparison
        if not history:
            print("🧠 Bootstrapping driving session history with baseline profiles...")
            now = int(time.time())
            history = [
                {
                    "timestamp": now - 86400 * 3,  # 3 days ago
                    "duration": 120.0,
                    "avg_score": 76.5,
                    "tailgating": 45,
                    "lane_drift": 38,
                    "unstable_steering": 22,
                    "collision_risk": 15
                },
                {
                    "timestamp": now - 86400 * 2,  # 2 days ago
                    "duration": 95.0,
                    "avg_score": 81.2,
                    "tailgating": 28,
                    "lane_drift": 24,
                    "unstable_steering": 12,
                    "collision_risk": 5
                },
                {
                    "timestamp": now - 86400,      # 1 day ago
                    "duration": 115.0,
                    "avg_score": 84.8,
                    "tailgating": 18,
                    "lane_drift": 15,
                    "unstable_steering": 8,
                    "collision_risk": 2
                }
            ]
            
        # Append current session
        history.append(current_session)
        
        # Save back to JSON
        try:
            os.makedirs(os.path.dirname(history_file), exist_ok=True)
            with open(history_file, 'w') as f:
                json.dump(history, f, indent=4)
        except Exception as e:
            print(f"⚠️ Error saving session history file: {e}")
            
        return history

    @staticmethod
    def analyze_trends(history):
        """
        Analyzes performance trends between the current session and previous sessions.
        Returns a trend analysis summary dict.
        """
        if len(history) < 2:
            return {
                "score_trend": 0.0,
                "improvement": True,
                "feedback": "First baseline session logged. Keep driving to establish trend patterns!"
            }
            
        current = history[-1]
        previous = history[-2]  # Direct comparison to last session
        
        # 1. Safety Score comparison
        score_diff = current["avg_score"] - previous["avg_score"]
        score_pct = (score_diff / previous["avg_score"]) * 100 if previous["avg_score"] > 0 else 0.0
        
        # 2. Violation Rates (per minute of driving) to normalize across different session durations
        curr_min = current["duration"] / 60.0 if current["duration"] > 0 else 1.0
        prev_min = previous["duration"] / 60.0 if previous["duration"] > 0 else 1.0
        
        curr_tailgating_rate = current["tailgating"] / curr_min
        prev_tailgating_rate = previous["tailgating"] / prev_min
        tailgating_diff = curr_tailgating_rate - prev_tailgating_rate
        
        curr_drift_rate = current["lane_drift"] / curr_min
        prev_drift_rate = previous["lane_drift"] / prev_min
        drift_diff = curr_drift_rate - prev_drift_rate
        
        curr_steering_rate = current["unstable_steering"] / curr_min
        prev_steering_rate = previous["unstable_steering"] / prev_min
        steering_diff = curr_steering_rate - prev_steering_rate
        
        # 3. Formulate feedback coaching recommendations
        improvements = []
        regressions = []
        
        if score_diff > 0:
            improvements.append(f"Safety score improved by {score_diff:+.1f} points ({score_pct:+.1f}%)")
        else:
            regressions.append(f"Safety score dropped by {abs(score_diff):.1f} points ({score_pct:.1f}%)")
            
        if tailgating_diff < -0.5:
            improvements.append("Following distance infractions decreased")
        elif tailgating_diff > 0.5:
            regressions.append("Following too close (tailgating) increased")
            
        if drift_diff < -0.5:
            improvements.append("Lane boundary violations decreased")
        elif drift_diff > 0.5:
            regressions.append("Lateral lane drift incidents increased")
            
        if steering_diff < -0.5:
            improvements.append("Sudden/unstable steering movements decreased")
        elif steering_diff > 0.5:
            regressions.append("Steering instability incidents increased")
            
        # Build custom guidance paragraph
        guidance = ""
        if regressions:
            guidance = "⚠️ Focus Area: " + "; ".join(regressions) + ".\n"
        else:
            guidance = "🎉 Excellent consistency! No performance regressions detected across active safety bands.\n"
            
        if improvements:
            guidance += "✅ Achievements: " + "; ".join(improvements) + "."
        else:
            guidance += "📈 Maintain focus during maneuvers to start showing metric gains next session."
            
        return {
            "score_trend": score_pct,
            "improvement": score_diff >= 0,
            "feedback": guidance,
            "current_rates": {
                "tailgating": curr_tailgating_rate,
                "lane_drift": curr_drift_rate,
                "unstable_steering": curr_steering_rate
            },
            "previous_rates": {
                "tailgating": prev_tailgating_rate,
                "lane_drift": prev_drift_rate,
                "unstable_steering": prev_steering_rate
            }
        }
