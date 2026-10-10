class RuleEngine:
    def __init__(self):
        self.safe_distance_threshold = 15.0 # meters
        
    def evaluate(self, metrics, collision_risk):
        score = 100
        suggestions = []
        
        lane_deviation = metrics.get("lane_deviation", 0)
        following_dist = metrics.get("following_distance", float('inf'))
        lane_stability = metrics.get("lane_stability", 0)
        
        if collision_risk:
            # Keep it minimal: replacing verbose instructions with a single warning
            suggestions = ["WARNING"]
            score -= 30
        else:
            if following_dist < self.safe_distance_threshold:
                suggestions.append("Increase following distance")
                score -= 20
                
            if lane_deviation > 0.3:
                suggestions.append("Adjust position")
                score -= 10
                
            if lane_stability > 0.5:
                suggestions.append("Unstable steering")
                score -= 10
            
        score = max(0, score)
        return score, suggestions
