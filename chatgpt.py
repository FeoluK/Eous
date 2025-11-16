#!/usr/bin/env python3
"""
Audio Transcription -> ChatGPT -> Text-to-Speech Pipeline

Requirements:
pip install openai pydub
You'll also need ffmpeg installed on your system for audio processing
"""

import os
from pathlib import Path

from openai import OpenAI

def transcribe_audio(client, audio_file_path):
    """
    Transcribe audio file using OpenAI Whisper API
    
    Args:
        client: OpenAI client instance
        audio_file_path: Path to the audio file
    
    Returns:
        str: Transcribed text
    """
    print(f"Transcribing audio file: {audio_file_path}")
    
    with open(audio_file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    
    print(f"Transcription: {transcript.text}")
    return transcript.text

def chat_with_gpt(client, message, conversation_history=None):
    """
    Send message to ChatGPT and get response
    
    Args:
        client: OpenAI client instance
        message: User message to send
        conversation_history: Optional list of previous messages
    
    Returns:
        str: ChatGPT response
    """
    if conversation_history is None:
        conversation_history = []
    
    # Add user message to history
    conversation_history.append({"role": "user", "content": message})
    
    print("Getting ChatGPT response...")
    
    response = client.chat.completions.create(
        model="gpt-4",  # or "gpt-3.5-turbo" for faster/cheaper responses
        messages=conversation_history
    )
    
    assistant_message = response.choices[0].message.content
    
    # Add assistant response to history
    conversation_history.append({"role": "assistant", "content": assistant_message})
    
    print(f"ChatGPT response: {assistant_message}")
    return assistant_message, conversation_history

def text_to_speech(client, text, output_path="response.mp3"):
    """
    Convert text to speech using OpenAI TTS API
    
    Args:
        client: OpenAI client instance
        text: Text to convert to speech
        output_path: Path to save the audio file
    
    Returns:
        str: Path to the generated audio file
    """
    print(f"Converting text to speech...")
    
    response = client.audio.speech.create(
        model="tts-1",  # or "tts-1-hd" for higher quality
        voice="alloy",  # Options: alloy, echo, fable, onyx, nova, shimmer
        input=text
    )
    
    response.stream_to_file(output_path)
    print(f"Audio saved to: {output_path}")
    return output_path


def get_audio_duration(audio_file_path):
    """
    Get the duration (in seconds) of an audio file using ffmpeg/ffprobe.

    This requires ffmpeg/ffprobe to be installed and available on the PATH.
    On a Raspberry Pi / Linux system you can typically install it with:
      sudo apt install ffmpeg
    """
    import subprocess

    # ffprobe command to extract only the duration in seconds
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        audio_file_path,
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip()}")

    duration_str = result.stdout.strip()
    return float(duration_str) if duration_str else 0.0

def play_audio(audio_path):
    """
    Play audio file (platform-specific)
    """
    import platform
    import subprocess
    
    system = platform.system()
    
    try:
        if system == "Darwin":  # macOS
            subprocess.run(["afplay", audio_path])
        elif system == "Linux":
            # Use ffplay (part of ffmpeg) so MP3/encoded audio is decoded correctly.
            # Install with: sudo apt install ffmpeg
            subprocess.run(
                ["ffplay", "-nodisp", "-autoexit", audio_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif system == "Windows":
            subprocess.run(["start", audio_path], shell=True)
        else:
            print(f"Please play the audio file manually: {audio_path}")
    except Exception as e:
        print(f"Error playing audio: {e}")
        print(f"Please play the audio file manually: {audio_path}")

def main(audio_file_path, api_key=None):
    """
    Main pipeline: Transcribe -> Chat -> Speak
    
    Args:
        audio_file_path: Path to input audio file
        api_key: OpenAI API key (if not set in environment)
    """
    # Initialize OpenAI client
    if api_key:
        client = OpenAI(api_key=api_key)
    else:
        # Uses OPENAI_API_KEY environment variable
        client = OpenAI()
    
    # Step 1: Transcribe audio
    transcribed_text = transcribe_audio(client, audio_file_path)
    
    # Step 2: Get ChatGPT response
    gpt_response, _ = chat_with_gpt(client, transcribed_text)
    
    # Step 3: Convert response to speech
    output_audio = text_to_speech(client, gpt_response)
    
    # Step 4: Play the audio
    play_audio(output_audio)
    
    return {
        "transcription": transcribed_text,
        "response": gpt_response,
        "audio_file": output_audio
    }

if __name__ == "__main__":
    import sys
    
    # Check if audio file path is provided
    # if len(sys.argv) < 2:
    #     print("Usage: python script.py <audio_file_path> [api_key]")
    #     print("Example: python script.py recording.mp3")
    #     sys.exit(1)
    
    # audio_path = sys.argv[1]
    # api_key = sys.argv[2] if len(sys.argv) > 2 else None
    
    audio_path = "recording.mp3"
    api_key = ""
    
    # Check if file exists
    if not os.path.exists(audio_path):
        print(f"Error: File not found: {audio_path}")
        sys.exit(1)
    
    # Run the pipeline
    result = main(audio_path, api_key)
    
    print("\n=== Pipeline Complete ===")
    print(f"Transcription: {result['transcription']}")
    print(f"Response: {result['response']}")
    print(f"Audio file: {result['audio_file']}")