from ultralytics import YOLO

def load_yolo_model(model_name="yolov8n.pt"):
    """
    Loads and returns a YOLOv8 model instance.
    """
    model = YOLO(model_name)
    return model
