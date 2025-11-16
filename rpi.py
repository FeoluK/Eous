import base64
import os
import threading
import time

import cv2
from openai import OpenAI
import requests
import serial

import chatgpt
import lyrics
import spotify

"""
rpi.py
-------
Runs on the Raspberry Pi. Responsibilities:
  1) Capture frames from the Pi's camera and send them to the Unity-side
     machine (running `unity.py`) over HTTP.
  2) Poll a remote command server for movement commands and forward them
     to the Arduino over the USB serial port.
"""

# ====== Configuration (EDIT THESE FOR YOUR NETWORK / HARDWARE) ======

# IP and port of the machine running `unity.py` / command server
UNITY_HOST = "10.16.146.164"  # Glasses
# UNITY_HOST = "10.16.149.153" # laptop
UNITY_PORT = 5000
UNITY_FRAME_ENDPOINT = f"http://{UNITY_HOST}:{UNITY_PORT}/send"
AUDIO_ENDPOINT = f"http://{UNITY_HOST}:{UNITY_PORT}/audio"
TRANSCRIPT_ENDPOINT = f"http://{UNITY_HOST}:{UNITY_PORT}/transcript"
REMOTE_COMMAND_ENDPOINT = f"http://{UNITY_HOST}:{UNITY_PORT}/command"

# Serial connection to the Arduino
SERIAL_PORT = "/dev/ttyUSB0"  # Adjust if your Arduino shows up differently
BAUD_RATE = 9600

# How frequently to poll the remote command server (in seconds)
COMMAND_POLL_INTERVAL = 0.1

ser = None  # type: ignore[assignment]

# OpenAI configuration (copied from chatgpt.py)
OPENAI_API_KEY = ""
openai_client = None

# How frequently to poll the remote audio server (in seconds)
AUDIO_POLL_INTERVAL = 1.0

# Last JPEG frame captured by the camera thread (as raw JPEG bytes).
# Protected by last_frame_lock.
last_frame_jpeg = None
last_frame_lock = threading.Lock()


def get_openai_client():
  """
  Lazily initialize and return a shared OpenAI client.
  """
  global openai_client
  if openai_client is None:
    if OPENAI_API_KEY:
      openai_client = OpenAI(api_key=OPENAI_API_KEY)
    else:
      openai_client = OpenAI()
  return openai_client


def send_transcript_to_server(text, **extra):
  """
  Send a transcript/lyric line back to the Unity/command server.

  Args:
    text: The transcript or lyric line to send.
    extra: Optional extra metadata (currently ignored for raw-body mode).
  """
  # For simplicity and compatibility with the Unity endpoint, we send the
  # transcript as a raw text body (not JSON). If you need to include the
  # duration, encode it into the string, e.g. "3.5 some text".
  body = str(text)
  print(f"Sending transcript to server")
  try:
    resp = requests.post(
      TRANSCRIPT_ENDPOINT,
      data=body.encode("utf-8"),
      headers={"Content-Type": "text/plain; charset=utf-8"},
      timeout=1.0,
    )
    if resp.status_code != 200:
      print(f"Transcript POST failed with status {resp.status_code}")
  except requests.RequestException as e:
    print(f"Error sending transcript to server: {e}")


def handle_chatgpt_tts_flow(transcribed_text: str) -> None:
  """
  Run the basic ChatGPT + TTS flow for a generic (non-music) request.
  """
  client = get_openai_client()

  try:
    gpt_response, _ = chatgpt.chat_with_gpt(client, transcribed_text)
  except Exception as e:  # noqa: BLE001
    print(f"Error during ChatGPT completion: {e}")
    return

  try:
    output_audio = chatgpt.text_to_speech(client, gpt_response)
    # Get the duration of the audio output
    audio_duration = chatgpt.get_audio_duration(output_audio)
    chatgpt.play_audio(output_audio)
  except Exception as e:  # noqa: BLE001
    print(f"Error during text-to-speech or audio playback: {e}")

  # Send the original transcript (and optionally the GPT response) back.
  send_transcript_to_server(
    str(audio_duration) + " " + gpt_response
  )


def handle_music_spotify_flow(transcribed_text: str) -> None:
  """
  Special handling for music/Spotify/song commands.

  1) Use ChatGPT to extract only the song name from the user's spoken command.
  2) Play the song on Spotify (using the spotify.py helper).
  3) Fetch synced lyrics from LRCLIB via lyrics.py.
  4) While the song plays, send each lyric line to the server at the correct time.
  """
  client = get_openai_client()

  music_prompt = (
    "You are an assistant that is parsing through commands to find the most important information. "
    "the task is to take a command that is requesting a song, and output only the song. "
    "when given a task, output ONLY the song name, and nothing else.\n"
    f"the command given is: {transcribed_text}"
  )

  try:
    song_name, _ = chatgpt.chat_with_gpt(client, music_prompt)
  except Exception as e:  # noqa: BLE001
    print(f"Error during ChatGPT music parsing: {e}")
    send_transcript_to_server(
      "5 Error parsing music command",
      mode="music",
      error="chatgpt_music_parsing_failed",
    )
    return

  if not song_name:
    print("ChatGPT returned an empty song name for music command.")
    send_transcript_to_server(
      "5 No Song Name found",
      mode="music",
      error="empty_song_name",
    )
    return

  song_name = song_name.strip()
  print(f"Music command resolved to song: {song_name!r}")
  
  # Fetch synced lyrics for the song via LRCLIB.
  try:
    lyrics_data = lyrics.search_lyrics(track_name=song_name, artist_name="")
  except Exception as e:  # noqa: BLE001
    print(f"Error searching lyrics for {song_name!r}: {e}")
    lyrics_data = None

  if not lyrics_data or not lyrics_data.get("syncedLyrics"):
    print(f"No synced lyrics found for {song_name!r}.")
    send_transcript_to_server(
      f"5 No synced lyrics available for {song_name}",
      mode="music",
      song=song_name,
    )
    return

  lines = lyrics.parse_lrc_timestamps(lyrics_data.get("syncedLyrics", ""))
  if not lines:
    print(f"Synced lyrics for {song_name!r} could not be parsed into timestamps.")
    send_transcript_to_server(
      f"5 Could not parse synced lyrics for {song_name}",
      mode="music",
      song=song_name,
    )
    return

  print(f"Streaming synced lyrics for {song_name!r} to {TRANSCRIPT_ENDPOINT}")

  # Start a stopwatch to align lyrics with playback time.
  start_time = time.time()

  # Start Spotify playback (this will use the configured Spotify account/devices).
  try:
    spotify.play_song(song_name)
  except Exception as e:  # noqa: BLE001
    print(f"Error while starting Spotify playback: {e}")
    send_transcript_to_server(
      "5 Error starting Spotify playback",
      mode="music",
      error="spotify_playback_failed",
      song=song_name,
    )
    return

  try:
    for timestamp, text in lines:
      # Wait until it's time for this lyric line.
      while (time.time() - start_time) < timestamp:
        time.sleep(0.01)

      send_transcript_to_server(
        "10 " + text,
        mode="lyrics",
        song=song_name,
        timestamp=timestamp,
      )
  except KeyboardInterrupt:
    print("\nStopped streaming lyrics due to KeyboardInterrupt.")
  except Exception as e:  # noqa: BLE001
    print(f"Error while streaming lyrics: {e}")


def process_audio_file(audio_path: str) -> None:
  """
  Full pipeline for an audio request:
    1) Transcribe using Whisper.
    2) If the transcript mentions music/spotify/song, run the music flow.
       Otherwise, run the generic ChatGPT + TTS flow.
  """
  client = get_openai_client()

  print(f"Processing audio file from server: {audio_path}")
  try:
    transcribed_text = chatgpt.transcribe_audio(client, audio_path)
  except Exception as e:  # noqa: BLE001
    print(f"Error during audio transcription: {e}")
    return

  if not transcribed_text:
    print("Transcription returned empty text; nothing to do.")
    return

  lower_text = transcribed_text.lower()
  if any(keyword in lower_text for keyword in ("music", "spotify", "song")):
    print("Detected music/Spotify-related command in transcript; using music flow.")
    handle_music_spotify_flow(transcribed_text)
  else:
    print("Using standard ChatGPT + TTS flow for transcript.")
    handle_chatgpt_tts_flow(transcribed_text)
    send_transcript_to_server(
      f"5 No synced lyrics available for {song_name}",
      mode="music",
      song=song_name,
    )


def audio_poll_loop():
  """
  Poll the remote server for new audio at /audio.

  Expected behavior:
    - If no new audio is available, the server may return 204 or an empty body.
    - If audio is available, the server returns raw audio bytes (e.g., MP3/WAV).
  The audio is saved locally and passed into the processing pipeline.
  """
  print(f"Polling audio from {AUDIO_ENDPOINT}")

  while True:
    try:
      resp = requests.get(AUDIO_ENDPOINT, timeout=5.0)
      if resp.status_code == 204 or not resp.content:
        # No audio ready yet; just wait and poll again.
        time.sleep(AUDIO_POLL_INTERVAL)
        continue

      if resp.status_code != 200:
        print(f"Audio GET failed with status {resp.status_code}")
        time.sleep(AUDIO_POLL_INTERVAL)
        continue

      # We expect raw audio bytes in the body.
      audio_bytes = resp.content
      if not audio_bytes:
        time.sleep(AUDIO_POLL_INTERVAL)
        continue

      save_dir = os.path.expanduser("~/Downloads/audio_requests")
      os.makedirs(save_dir, exist_ok=True)
      timestamp = time.strftime("%Y%m%d_%H%M%S")
      audio_path = os.path.join(save_dir, f"audio_{timestamp}.mp3")

      with open(audio_path, "wb") as f:
        f.write(audio_bytes)

      print(f"Received audio from server, saved to {audio_path}")

      # Process this audio file (transcribe, ChatGPT/TTS or Spotify/lyrics).
      process_audio_file(audio_path)
    except requests.RequestException as e:
      print(f"Error polling audio server: {e}")
    except Exception as e:  # noqa: BLE001
      print(f"Unexpected error in audio_poll_loop: {e}")

    time.sleep(AUDIO_POLL_INTERVAL)


def init_serial():
  """
  Try to open the serial port to the Arduino, retrying until successful.
  """
  global ser
  while ser is None:
    try:
      print(f"Opening serial port {SERIAL_PORT} at {BAUD_RATE} baud...")
      ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
      print("Serial connection to Arduino established.")
    except serial.SerialException as e:
      print(f"Failed to open serial port: {e}. Retrying in 2 seconds...")
      time.sleep(2)


def send_command_to_arduino(cmd: str) -> None:
  """
  Forward a single-character command to the Arduino over serial.
  Expected commands: 'W', 'A', 'S', 'D', 'X'.
  """
  if not cmd:
    return

  global ser
  if ser is None:
    init_serial()

  try:
    ser.write(cmd[0].encode("ascii"))
    print(f"Sent command to Arduino: {cmd[0]}")
  except serial.SerialException as e:
    print(f"Error writing to serial: {e}. Will attempt to re-open on next command.")
    ser = None


def command_poll_loop():
  """
  Poll the remote command server for movement commands and forward them to the Arduino.

  Expected response from REMOTE_COMMAND_ENDPOINT:
    JSON object containing a "command" field, e.g. {"command": "W"}.
  Commands should be one of: W, A, S, D, X.
  """
  global last_frame_jpeg

  print(f"Polling commands from {REMOTE_COMMAND_ENDPOINT}")
  last_cmd = None

  while True:
    try:
      resp = requests.get(REMOTE_COMMAND_ENDPOINT, timeout=1.0)
      if resp.status_code != 200:
        # Non-OK status; wait and try again
        print(f"Command GET failed with status {resp.status_code}")
      else:
        # The server returns plain text like "FORWARD", not JSON.
        raw_text = resp.text.strip()
        # For safety, just look at the first whitespace-separated token.
        token = raw_text.split()[0].upper() if raw_text else ""

        # Special case: PHOTO command means "save the last camera frame locally"
        if token == "PHOTO":
          with last_frame_lock:
            jpeg_data = last_frame_jpeg

          if jpeg_data is None:
            print("PHOTO command received, but no frame has been captured yet.")
          else:
            try:
              save_dir = os.path.expanduser("~/Downloads/photos")
              os.makedirs(save_dir, exist_ok=True)
              timestamp = time.strftime("%Y%m%d_%H%M%S")
              filename = os.path.join(save_dir, f"{timestamp}.jpg")
              with open(filename, "wb") as f:
                f.write(jpeg_data)
              print(f"PHOTO command: saved image to {filename}")
            except OSError as e:
              print(f"PHOTO command: failed to save image: {e}")

          # Do not forward PHOTO to the Arduino; move on to the next poll.
          time.sleep(COMMAND_POLL_INTERVAL)
          continue

        # Map server text to Arduino direction commands
        dirs = {
          "FORWARD": "W",
          "BACKWARD": "S",
          "LEFT": "A",
          "RIGHT": "D",
          "NOT": "X",
          "STOP": "X",
          "NOTMOVING": "X",
          "NOT_MOVING": "X",
          "NOT MOVING": "X",
        }

        if token in dirs:
          mapped_cmd = dirs[token]
          # Only send if the mapped command changed to avoid spamming the Arduino
          if mapped_cmd != last_cmd:
            print(f"Received '{raw_text}', mapped to command '{mapped_cmd}'")
            send_command_to_arduino(mapped_cmd)
            last_cmd = mapped_cmd
        else:
          # If the server returned something unexpected, just ignore it
          if raw_text:
            print(f"Ignoring invalid command from server: {raw_text!r}")
    except requests.RequestException as e:
      print(f"Error polling command server: {e}")

    time.sleep(COMMAND_POLL_INTERVAL)


def camera_loop():
  """
  Capture frames from the Pi Camera using Picamera2 and send them to `unity.py` via HTTP.
  Runs in a background thread.
  """
  try:
    from picamera2 import Picamera2
  except ImportError as e:
    raise RuntimeError(
      "The 'picamera2' library is required to use the Raspberry Pi camera module. "
      "Install it with 'sudo apt install python3-picamera2' or 'pip install picamera2'."
    ) from e

  global last_frame_jpeg

  resolution = (640, 480)
  print("Initializing Picamera2...")
  picam2 = Picamera2()
  video_config = picam2.create_video_configuration(
    main={"size": resolution, "format": "RGB888"}
  )
  picam2.configure(video_config)
  picam2.start()

  # Allow the camera to warm up
  time.sleep(2.0)

  print(f"Streaming frames from Picamera2 to {UNITY_FRAME_ENDPOINT}")

  try:
    while True:
      # capture_array returns an RGB image; convert to BGR for OpenCV
      frame = picam2.capture_array()
      image = frame

      ok, buffer = cv2.imencode(".jpg", image)
      if not ok:
        print("Failed to encode frame")
        continue

      jpeg_bytes = buffer.tobytes()

      # Update the last-frame buffer for PHOTO captures
      with last_frame_lock:
        last_frame_jpeg = jpeg_bytes

      frame_b64 = base64.b64encode(jpeg_bytes).decode("utf-8")

      try:
        resp = requests.post(
          UNITY_FRAME_ENDPOINT,
          json={"frame": frame_b64},
          timeout=1.0,
        )
        if resp.status_code != 200:
          print(f"Frame POST failed with status {resp.status_code}")
      except requests.RequestException as e:
        # Network issues: log and keep trying.
        print(f"Error sending frame: {e}")
        time.sleep(0.5)

  finally:
    picam2.stop()
    picam2.close()
    print("Picamera2 stopped and released.")


def main():
  # Ensure serial to Arduino is available
  init_serial()

  # Start camera streaming in a background thread
  camera_thread = threading.Thread(target=camera_loop, daemon=True)
  camera_thread.start()

  # Start command polling in a background thread
  command_thread = threading.Thread(target=command_poll_loop, daemon=True)
  command_thread.start()

  # Start audio polling in a background thread
  audio_thread = threading.Thread(target=audio_poll_loop, daemon=True)
  audio_thread.start()

  # Keep the main thread alive
  print("RPI process started. Camera streaming and command polling are running.")
  try:
    while True:
      time.sleep(1.0)
  except KeyboardInterrupt:
    print("Shutting down rpi.py.")


if __name__ == "__main__":
  main()
