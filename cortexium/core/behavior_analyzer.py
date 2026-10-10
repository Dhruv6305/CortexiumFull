import numpy as np

class BehaviorAnalyzer:
    def __init__(self):
        self.lane_offsets = []
        
    def analyze(self, lane_offset, following_dist):
        self.lane_offsets.append(lane_offset)
        if len(self.lane_offsets) > 30:
            self.lane_offsets.pop(0)
            
        lane_stability = np.std(self.lane_offsets) if len(self.lane_offsets) > 1 else 0.0
        
        metrics = {
            "lane_deviation": abs(lane_offset),
            "following_distance": following_dist,
            "lane_stability": lane_stability
        }
        return metrics
