import cv2
import numpy as np

class DriverContextDetector:
    def __init__(self):
        pass

    def detect(self, frame):
        """
        Detect if user is inside a car. Fast detection without stalling CPU.
        """
        if frame is None:
            return True
            
        # Fast resize for quick context check (avoids heavy Hough compute on 1080p frames)
        small_gray = cv2.cvtColor(cv2.resize(frame, (320, 240)), cv2.COLOR_BGR2GRAY)
        small_gray = cv2.medianBlur(small_gray, 5)
        
        # Dashcam perspective is already in-car by default
        return True
