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
    frame = cv2.resize(frame, (480, 360))

    frame_count += 1

    if frame_count % 3 != 0:
        cv2.imshow("Cortexium XR Detection", frame)
        continue

    # run detection
    results = model(frame, imgsz=416, conf=0.4)

    # draw detection boxes
    annotated_frame = results[0].plot()

    # display frame with boxes
    cv2.imshow("Cortexium XR Detection", annotated_frame)

    # exit when ESC pressed
    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()