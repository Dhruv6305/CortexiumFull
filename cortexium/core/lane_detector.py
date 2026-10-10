import cv2
import numpy as np

class LaneDetector:
    def __init__(self):
        pass

    def detect(self, frame):
        # Grayscale -> Gaussian Blur -> Canny -> Hough Lines
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 50, 150)
        
        # ROI mask to exclude the car dashboard/hood
        height, width = edges.shape
        mask = np.zeros_like(edges)
        polygon = np.array([[
            (int(width * 0.1), int(height * 0.85)),
            (int(width * 0.9), int(height * 0.85)),
            (int(width * 0.6), int(height * 0.6)),
            (int(width * 0.4), int(height * 0.6)),
        ]], np.int32)
        cv2.fillPoly(mask, polygon, 255)
        masked_edges = cv2.bitwise_and(edges, mask)
        
        lines = cv2.HoughLinesP(
            masked_edges, rho=1, theta=np.pi/180, threshold=50, 
            minLineLength=50, maxLineGap=200
        )
        
        lane_lines = []
        if lines is not None:
            for line in lines:
                parts = line.flatten()
                if len(parts) == 4:
                    x1, y1, x2, y2 = parts
                    lane_lines.append((x1, y1, x2, y2))
                
        # Calculate lane center and offset
        lane_center = width // 2
        lane_offset = 0.0 # simplified meters
        
        if lane_lines:
            x_coords = []
            for (x1, y1, x2, y2) in lane_lines:
                x_coords.extend([x1, x2])
            lane_center = int(np.mean(x_coords))
            # Assume ~0.01 meters per pixel for basic prototyping offset
            lane_offset = (lane_center - (width / 2)) * 0.01
            
        return lane_lines, lane_center, lane_offset
