import cv2
cap = cv2.VideoCapture('/dev/video2', cv2.CAP_V4L2)
if not cap.isOpened():
    raise RuntimeError("Could not open /dev/video0")

# Try to pick a sane mode; comment these if the camera negotiates fine on its own
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 30)

while True:
    ok, frame = cap.read()
    if not ok:
        break
    cv2.imshow("USB Camera", frame)
    # press q to quit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
