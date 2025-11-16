import base64
import os
import threading
import time

import requests
from flask import Flask, Response, jsonify, request, send_file

"""
unity.py
--------
Runs on the machine that is displaying the video feed (e.g. your laptop / desktop).
Responsibilities:
  1) Expose an HTTP endpoint that receives base64-encoded JPEG frames from
     the Raspberry Pi (`rpi.py`) and displays them.
  2) While displaying the frames, listen for key presses (W/A/S/D) from the
     browser or keyboard input, and expose the latest command via a GET
     endpoint that the Raspberry Pi polls.
  3) Provide audio and transcript endpoints used by `rpi.py` for the
     voice/Spotify/lyrics flows.
"""


app = Flask(__name__)

# Global storage for the latest JPEG frame received from the Pi
latest_frame_bytes = None
frame_lock = threading.Lock()

# Latest movement command published for the Raspberry Pi to poll.
# Stored as text tokens (e.g., "FORWARD", "BACKWARD", "LEFT", "RIGHT", "STOP").
current_command = "NOT_MOVING"
command_lock = threading.Lock()

# ====== Audio + transcript state ======

# Path to the local audio file to send when requested by the Pi
ASK_AUDIO_PATH = os.path.join(os.path.dirname(__file__), "ask.mp3")

# When True, the next GET to /audio will return the audio file, then reset.
pending_audio_lock = threading.Lock()
pending_audio_ready = False

# Latest transcript text and its expiration time (epoch seconds).
current_transcript = ""
transcript_expire_time = 0.0
transcript_lock = threading.Lock()


def set_current_command_from_key(cmd: str) -> None:
  """
  Map a single-character movement key (W/A/S/D/X) to a text token and store
  it as the latest command for the Raspberry Pi to poll via GET /command.
  """
  global current_command

  cmd = cmd.upper()
  mapping = {
    "W": "FORWARD",
    "S": "BACKWARD",
    "A": "LEFT",
    "D": "RIGHT",
    "X": "Not Moving",
    "P": "PHOTO",
  }

  if cmd not in mapping:
    return

  token = mapping[cmd]
  with command_lock:
    current_command = token
  print(f"Updated current command token to: {token}")


@app.route("/send", methods=["POST"])
def receive_frame():
  """
  Receive a base64-encoded JPEG frame from the Raspberry Pi,
  store it, and make it available for viewing via /latest.jpg.
  """
  data = request.json or {}
  frame_b64 = data.get("frame")

  if not frame_b64:
    return jsonify({"status": "error", "reason": "no frame provided"}), 400

  try:
    # Decode base64 to raw JPEG bytes and store as the latest frame
    frame_bytes = base64.b64decode(frame_b64)

    global latest_frame_bytes
    with frame_lock:
      latest_frame_bytes = frame_bytes

  except Exception as e:
    print(f"Error: {e}")
    return jsonify({"status": "error", "reason": str(e)}), 500

  return jsonify({"status": "ok"})


@app.route("/latest.jpg", methods=["GET"])
def latest_jpg():
  """
  Serve the most recently received frame as a JPEG image.
  """
  with frame_lock:
    if latest_frame_bytes is None:
      return jsonify({"status": "error", "reason": "no frame received yet"}), 404

    return Response(latest_frame_bytes, mimetype="image/jpeg")


@app.route("/", methods=["GET"])
def index():
  """
  Simple HTML page that displays the latest frame and refreshes it periodically.
  """
  return """
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Robot Camera Feed</title>
    <style>
      body { background: #111; color: #eee; font-family: sans-serif; text-align: center; }
      #frame { max-width: 90vw; max-height: 90vh; margin-top: 20px; border: 2px solid #444; }
      #status { margin-top: 10px; font-size: 14px; color: #ccc; }
      #controls { margin-top: 20px; }
      #transcript-box {
        margin-top: 20px;
        padding: 10px 14px;
        border-radius: 4px;
        background: #222;
        border: 1px solid #444;
        min-height: 40px;
        font-size: 16px;
        color: #fff;
        display: inline-block;
        max-width: 80vw;
        white-space: pre-wrap;
      }
    </style>
  </head>
  <body>
    <h1>Robot Camera Feed</h1>
    <p>Latest frame from Raspberry Pi (auto-refreshing).</p>
    <img id="frame" src="/latest.jpg" alt="No frame yet" />
    <div id="status">Hold W/A/S/D to drive, release to stop (focus this tab).</div>

    <div id="controls">
      <button id="send-audio-btn">Send audio</button>
    </div>

    <div id="transcript-box"></div>
    <script>
      const img = document.getElementById('frame');
      const statusEl = document.getElementById('status');
      const transcriptBox = document.getElementById('transcript-box');
      const sendAudioBtn = document.getElementById('send-audio-btn');
      const movementKeys = ['w', 'a', 's', 'd'];
      const pressedKeys = new Set();
      function refresh() {
        const url = '/latest.jpg?cb=' + Date.now();
        img.src = url;
      }
      setInterval(refresh, 200); // refresh every 200 ms

      async function triggerSendAudio() {
        try {
          const resp = await fetch('/send-audio', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
          });
          const data = await resp.json().catch(() => ({}));
          statusEl.textContent = 'Send audio: ' + resp.status + (data.reason ? (' - ' + data.reason) : '');
        } catch (e) {
          statusEl.textContent = 'Error triggering audio send: ' + e;
        }
      }

      sendAudioBtn.addEventListener('click', (e) => {
        e.preventDefault();
        triggerSendAudio();
      });

      async function fetchTranscript() {
        try {
          const resp = await fetch('/transcript/latest');
          if (!resp.ok) return;
          const data = await resp.json();
          const text = data.transcript || '';
          transcriptBox.textContent = text;
        } catch (e) {
          // Ignore errors; will retry on next poll.
        }
      }

      // Poll for transcript updates.
      setInterval(fetchTranscript, 500);

      async function sendCommand(cmd) {
        try {
          const resp = await fetch('/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: cmd })
          });
          statusEl.textContent = 'Sent command ' + cmd + ', response ' + resp.status;
        } catch (e) {
          statusEl.textContent = 'Error sending command ' + cmd + ': ' + e;
        }
      }

      window.addEventListener('keydown', (e) => {
        const key = e.key.toLowerCase();
        if ([...movementKeys, 'x'].includes(key)) {
          e.preventDefault();

          // Avoid spamming repeated keydown events for the same key
          if (!pressedKeys.has(key)) {
            pressedKeys.add(key);
            sendCommand(key.toUpperCase());
          }
        }
      });

      window.addEventListener('keyup', (e) => {
        const key = e.key.toLowerCase();

        if (movementKeys.includes(key)) {
          e.preventDefault();
          pressedKeys.delete(key);

          // If no movement keys remain pressed, send stop command.
          const stillPressed = movementKeys.some(k => pressedKeys.has(k));
          if (!stillPressed) {
            sendCommand('X');
          } else {
            // Optional: if another movement key is still held, reinforce that command.
            const remaining = movementKeys.filter(k => pressedKeys.has(k));
            if (remaining.length > 0) {
              sendCommand(remaining[remaining.length - 1].toUpperCase());
            }
          }
        } else if (key === 'x') {
          // Explicit X key still works as an immediate stop.
          e.preventDefault();
          pressedKeys.clear();
          sendCommand('X');
        }
      });
    </script>
  </body>
</html>
"""


@app.route("/command", methods=["POST", "GET"])
def command_endpoint():
  """
  Movement command endpoint.

  - POST: receive movement commands from the browser (W/A/S/D/X) and update
    the latest command token that the Raspberry Pi will poll.
  - GET: return the latest command token as plain text for the Raspberry Pi.
  """
  global current_command

  if request.method == "POST":
    data = request.json or {}
    cmd = str(data.get("command", "")).upper()

    if cmd not in {"W", "A", "S", "D", "X"}:
      return jsonify({"status": "error", "reason": "invalid command"}), 400

    set_current_command_from_key(cmd)
    return jsonify({"status": "ok"})

  # GET: serve the latest command token as simple plain text, as expected by rpi.py
  with command_lock:
    token = current_command or "NOT_MOVING"
  return Response(token, mimetype="text/plain")


@app.route("/send-audio", methods=["POST"])
def send_audio():
  """
  Mark the local audio file (ask.mp3) as ready to be fetched by the Raspberry Pi.

  The Pi will poll /audio; when audio is pending, /audio will return the file bytes
  once, then clear the pending flag.
  """
  global pending_audio_ready

  if not os.path.exists(ASK_AUDIO_PATH):
    return jsonify({"status": "error", "reason": f"Audio file not found at {ASK_AUDIO_PATH}"}), 404

  with pending_audio_lock:
    pending_audio_ready = True

  return jsonify({"status": "ok"})


@app.route("/audio", methods=["GET"])
def audio():
  """
  Endpoint polled by the Raspberry Pi for audio.

  - If no audio has been requested (no click on "Send audio"), returns 204.
  - If audio is pending, returns ask.mp3 bytes as an audio/mpeg response once.
  """
  global pending_audio_ready

  with pending_audio_lock:
    if not pending_audio_ready:
      # No audio queued for sending.
      return ("", 204)
    # Consume the pending audio flag so this file is only served once per click.
    pending_audio_ready = False

  try:
    return send_file(ASK_AUDIO_PATH, mimetype="audio/mpeg")
  except OSError as e:  # file missing or unreadable
    print(f"Error serving audio file {ASK_AUDIO_PATH}: {e}")
    return jsonify({"status": "error", "reason": "failed_to_read_audio"}), 500


@app.route("/transcript", methods=["POST"])
def receive_transcript():
  """
  Receive a transcript from the Raspberry Pi.

  Request body (raw text):
    "<duration_seconds> <transcript text>"

  Behavior:
    - Parse the first whitespace-separated token as duration (in seconds).
    - The rest of the line is treated as the transcript text.
    - Store the transcript and compute an expiration time: now + duration + 5 seconds.
    - If a new transcript arrives before the previous expires, it overrides the old text
      immediately.
  """
  global current_transcript, transcript_expire_time

  raw = request.get_data(as_text=True) or ""
  raw = raw.strip()

  if not raw:
    return jsonify({"status": "error", "reason": "empty body"}), 400

  # Split into "<duration> <rest of text...>"
  parts = raw.split(maxsplit=1)
  if len(parts) == 1:
    # No explicit duration; default to 0 seconds.
    duration_str = "0"
    text = parts[0]
  else:
    duration_str, text = parts[0], parts[1]

  # Duration (in seconds) of the audio; default to 0 if missing.
  try:
    duration = float(duration_str)
  except (TypeError, ValueError):
    duration = 0.0

  display_seconds = max(0.0, duration) + 5.0
  expires_at = time.time() + display_seconds

  with transcript_lock:
    current_transcript = text
    transcript_expire_time = expires_at

  return jsonify({"status": "ok"})


@app.route("/transcript/latest", methods=["GET"])
def latest_transcript():
  """
  Small helper endpoint for the web UI to poll the current transcript.

  Returns JSON:
    { "transcript": "<text or empty if expired>" }
  """
  now = time.time()

  with transcript_lock:
    if not current_transcript or now >= transcript_expire_time:
      return jsonify({"transcript": ""})

    return jsonify({"transcript": current_transcript})


def keyboard_loop():
  """
  Simple terminal-based control loop.
  Type W/A/S/D/X followed by Enter to send commands to the Raspberry Pi.
  """
  print("Keyboard control ready: type W/A/S/D/X + Enter to drive the robot.")
  print("Press Ctrl+C to stop this control loop.")

  while True:
    try:
      cmd = input().strip().upper()
    except EOFError:
      # End of input (e.g., terminal closed)
      break
    except KeyboardInterrupt:
      break

    if cmd in {"W", "A", "S", "D", "X"}:
      set_current_command_from_key(cmd)
    else:
      if cmd:
        print("Invalid command. Use W/A/S/D/X.")


def main():
  print(f"Listening for frames on http://0.0.0.0:5000/send")
  print("Hosting command server for Raspberry Pi at GET /command")

  # Start keyboard control in a background thread so Flask can run the server.
  kb_thread = threading.Thread(target=keyboard_loop, daemon=True)
  kb_thread.start()

  app.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":
  main()


