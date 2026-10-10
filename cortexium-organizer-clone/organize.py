from ultralytics import YOLO
import cv2

# Load YOLO model
model = YOLO("yolov8s.pt")

# Mobile camera stream
url = "http://192.168.1.106:8080/videofeed"
cap = cv2.VideoCapture(url)

frame_count = 0
last_frame = None

# Map YOLO labels to nicer surface names
surface_alias = {
    "dining table": "table",
    "bench": "table",
    "bed": "surface",
    "couch": "sofa",
    "chair": "chair"
}

# Surfaces YOLO can detect
surfaces = [
    "dining table",
    "chair",
    "couch",
    "bench",
    "bed",
    "refrigerator",
    "sink"
]

# Object placement expectations
placement_rules = {
    "laptop": "table",
    "cell phone": "table",
    "book": "table",
    "keyboard": "table",
    "mouse": "table",
    "bottle": "table",
    "cup": "table",
    "remote": "sofa",
    "backpack": "chair",
    "handbag": "chair"
}

# Draw XR arrow
def draw_arrow(frame, start, end, color=(0,255,0)):
    cv2.arrowedLine(
        frame,
        start,
        end,
        color,
        3,
        tipLength=0.3
    )

# Check if two boxes overlap
def overlap(boxA, boxB):

    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    if xA < xB and yA < yB:
        return True

    return False


while True:

    ret, frame = cap.read()

    if not ret:
        print("Failed to grab frame")
        break

    frame = cv2.resize(frame,(640,480))
    frame_count += 1

    # Skip frames for speed
    if frame_count % 3 != 0:

        if last_frame is not None:
            cv2.imshow("Cortexium XR Organizer", last_frame)
        else:
            cv2.imshow("Cortexium XR Organizer", frame)

        if cv2.waitKey(1) == 27:
            break

        continue

    results = model(frame, imgsz=416, conf=0.4)

    detected_surfaces = []
    surface_boxes = {}

    for r in results:
        for box in r.boxes:

            cls = int(box.cls)
            label = model.names[cls]

            x1,y1,x2,y2 = map(int, box.xyxy[0])

            # Detect surfaces
            if label in surfaces:

                surface_name = surface_alias.get(label,label)

                detected_surfaces.append(surface_name)
                surface_boxes[surface_name] = (x1,y1,x2,y2)

                cv2.rectangle(frame,(x1,y1),(x2,y2),(255,255,0),2)

                cv2.putText(frame,
                            f"SURFACE: {surface_name}",
                            (x1,y1-10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (255,255,0),
                            2)

            # Object placement reasoning
            if label in placement_rules:

                expected_surface = placement_rules[label]

                correct_placement = False

                if expected_surface in surface_boxes:

                    surface_box = surface_boxes[expected_surface]

                    if overlap((x1,y1,x2,y2), surface_box):
                        correct_placement = True

                if correct_placement:

                    color = (0,255,0)
                    message = f"{label} correctly placed"

                else:

                    color = (0,0,255)
                    message = f"{label} misplaced -> move to {expected_surface}"

                    if expected_surface in surface_boxes:

                        sx1,sy1,sx2,sy2 = surface_boxes[expected_surface]

                        obj_center = ((x1+x2)//2,(y1+y2)//2)
                        surf_center = ((sx1+sx2)//2,(sy1+sy2)//2)

                        draw_arrow(frame,obj_center,surf_center,(0,0,255))

                cv2.rectangle(frame,(x1,y1),(x2,y2),color,2)

                cv2.putText(frame,
                            message,
                            (x1,y1-10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            color,
                            2)

    last_frame = frame.copy()

    cv2.imshow("Cortexium XR Organizer", frame)

    if cv2.waitKey(1) == 27:
        break


cap.release()
cv2.destroyAllWindows()