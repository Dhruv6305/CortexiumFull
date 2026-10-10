import time

class SessionLogger:
    def __init__(self):
        self.start_time = time.time()
        self.logs = []
        
    def log_frame(self, score: float, suggestions: list, min_dist: float):
        """
        Logs session metrics for a single frame.
        """
        elapsed = time.time() - self.start_time
        
        # Determine violation states from rule engine suggestion strings
        tailgating = "Increase following distance" in suggestions
        lane_drift = "Adjust position" in suggestions
        unstable_steering = "Unstable steering" in suggestions
        collision_risk = "WARNING" in suggestions
        
        self.logs.append({
            "timestamp": elapsed,
            "score": score,
            "tailgating": tailgating,
            "lane_drift": lane_drift,
            "unstable_steering": unstable_steering,
            "collision_risk": collision_risk,
            "distance": min_dist if min_dist != float('inf') else None
        })
        
    def get_logs(self):
        return self.logs
