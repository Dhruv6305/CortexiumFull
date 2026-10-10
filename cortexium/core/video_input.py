import cv2

class VideoInput:
    def __init__(self, source=0):
        # Convert source to int if it's a digit string representing a webcam
        if isinstance(source, str) and source.isdigit():
            source = int(source)
            
        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            raise ValueError(f"Unable to open video source: {source}")
            
    def get_frame(self):
        ret, frame = self.cap.read()
        return ret, frame
        
    def release(self):
        if self.cap:
            self.cap.release()
