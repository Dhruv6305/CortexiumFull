from config import KNOWN_CAR_HEIGHT, FOCAL_LENGTH

class DistanceEstimator:
    def __init__(self):
        self.known_height = KNOWN_CAR_HEIGHT
        self.focal_length = FOCAL_LENGTH

    def estimate(self, detections):
        distances = []
        min_distance = float('inf')
        collision_risk = False
        
        for det in detections:
            x1, y1, x2, y2, cls, conf = det
            bbox_height = y2 - y1
            
            # distance = (KNOWN_CAR_HEIGHT * focal_length) / bbox_height
            if bbox_height > 0:
                dist = (self.known_height * self.focal_length) / bbox_height
            else:
                dist = float('inf')
                
            distances.append(dist)
            if dist < min_distance:
                min_distance = dist
                
            if dist < 10.0:
                collision_risk = True
                
        return min_distance, distances, collision_risk
