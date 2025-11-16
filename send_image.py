import base64
import cv2
import requests

ip = "10.19.183.118"
url = f"http://{ip}:5000/send"

print(f"Streaming webcam feed to {url}")

# Open the default USB webcam (change the index if you have multiple cameras)
print("Opening webcam")
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    raise RuntimeError("Could not open webcam")

try:
    while True:
        # Read a frame from the webcam
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame from webcam")
            break
        
        # Optionally show the frame locally and allow quitting with 'q'
        cv2.imshow("Webcam Feed", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

        # Encode the frame as JPEG
        ok, buffer = cv2.imencode(".jpg", frame)
        if not ok:
            print("Failed to encode frame")
            continue

        # Base64-encode the JPEG bytes so they can be sent as JSON
        frame_b64 = base64.b64encode(buffer.tobytes()).decode("utf-8")

        # Send the encoded frame to the Flask server as JSON
        try:
            resp = requests.post(url, json={"frame": frame_b64})
            print(f"Sent frame, server responded with: {resp.status_code}")
        except requests.RequestException as e:
            print(f"Error sending frame: {e}")
            break

finally:
    cap.release()
    cv2.destroyAllWindows()