from models.yolo_loader import load_yolo_model
from config import CONFIDENCE_THRESHOLD, CLASSES_TO_DETECT

class VehicleDetector:
    def __init__(self, model_path="yolov8n.pt"):
        self.model = load_yolo_model(model_path)
        self.classes = CLASSES_TO_DETECT
        self.conf = CONFIDENCE_THRESHOLD

    def detect(self, frame):
        results = self.model(frame, classes=self.classes, conf=self.conf, verbose=False)
        detections = []
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                cls = int(box.cls[0].cpu().numpy())
                conf = float(box.conf[0].cpu().numpy())
                
                # Filter out ego car (the car dashboard/hood)
                h, w = frame.shape[:2]
                if y2 >= h * 0.85 and (x2 - x1) * (y2 - y1) > (h * w) * 0.15:
                    continue
                    
                detections.append([int(x1), int(y1), int(x2), int(y2), cls, conf])
                
        return detections
