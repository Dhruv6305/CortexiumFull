from ultralytics import YOLO
import cv2

model = YOLO("yolov8s.pt")

url = "http://192.168.1.106:8080/videofeed"

cap = cv2.VideoCapture(url)

frame_count = 0

while True:

    ret, frame = cap.read()

    if not ret:
        print("Failed to grab frame")
        break

    frame = cv2.resize(frame,(480,360))

    frame_count += 1

    if frame_count % 3 != 0:
        cv2.imshow("Detection", frame)
        if cv2.waitKey(1) == 27:
            break
        continue

    results = model(frame, imgsz=416, conf=0.4)

    annotated = results[0].plot()

    cv2.imshow("Detection", annotated)

    if cv2.waitKey(1) == 27:
        break

cap.release()
cv2.destroyAllWindows()