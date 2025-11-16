import base64

import cv2
import numpy as np
from flask import Flask, request

app = Flask(__name__)


@app.route("/send", methods=["POST"])
def receive():
    data = request.json or {}

    # Expect a base64-encoded JPEG frame under the "frame" key
    frame_b64 = data.get("frame")
    if not frame_b64:
        return {"status": "error", "reason": "no frame provided"}, 400

    try:
        
        # Decode base64 to raw bytes
        frame_bytes = base64.b64decode(frame_b64)

        # Convert bytes to a NumPy array and then to an OpenCV image
        nparr = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            return {"status": "error", "reason": "failed to decode image"}, 400

        # Display the received frame
        cv2.imshow("Received Webcam Feed", frame)
        # Small delay so the window can update; also lets you press 'q' to close
        if cv2.waitKey(1) & 0xFF == ord("q"):
            # If 'q' pressed, close the window and stop server on next request
            cv2.destroyAllWindows()
        

    except Exception as e:
        return {"status": "error", "reason": str(e)}, 500

    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

