using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using TMPro;
using UnityEngine;
using UnityEngine.XR.Hands;

public class GestureLogger : MonoBehaviour
{
    // Used for transcript + debug info
    public TextMeshProUGUI outputText;  

    // "RECORDING" GIF / UI object
    public GameObject recordingIndicator;

    // Shutter sound for short-photo pinch
    public AudioClip shutterSound;
    private AudioSource audioSource;

    private XRHandSubsystem m_HandSubsystem;

    // Right hand pinch detection (movement commands)
    private bool isPinching = false;
    private bool wasPinching = false;
    private Vector3 pinchStartPosition;
    private float pinchThreshold = 0.02f;
    private float movementThreshold = 0.05f;

    // Left hand pinch detection (PHOTO / RECORD)
    private bool leftIsPinching = false;
    private bool leftWasPinching = false;
    private float leftPinchStartTime = 0f;
    private const float longPressThreshold = 1.25f;
    private bool leftLongRecordingStarted = false;
    private int photoCount = 0;

    // Reference to the server
    private SimpleCommandServer server;

    // Microphone
    private AudioSource micAudioSource;
    private string selectedMic = null;
    public int micSampleRate = 16000;
    public int micLengthSeconds = 10;

    private bool micFound = false;
    private bool isRecording = false;

    // Transcript display fields
    private string currentTranscript = "";
    private float transcriptExpireTime = 0f;
    private bool hasTranscript = false;

    void Start()
    {
        // XR hands
        var subsystems = new List<XRHandSubsystem>();
        SubsystemManager.GetSubsystems(subsystems);
        
        if (subsystems.Count > 0)
        {
            m_HandSubsystem = subsystems[0];
        }
        else
        {
            Debug.LogError("No XRHandSubsystem found!");
        }

        // Server
        server = FindObjectOfType<SimpleCommandServer>();
        if (server == null)
        {
            Debug.LogWarning("GestureLogger: SimpleCommandServer not found in scene.");
        }

        // Mic
        InitMicrophone();

        // Recording indicator starts hidden
        if (recordingIndicator != null)
        {
            recordingIndicator.SetActive(false);
        }

        // Audio source for shutter
        audioSource = gameObject.AddComponent<AudioSource>();
        audioSource.playOnAwake = false;

        // Initial UI debug text
        if (outputText != null)
        {
            outputText.text = "";
        }
    }

    void Update()
    {
        if (m_HandSubsystem == null)
        {
            if (!hasTranscript && outputText != null)
            {
                outputText.text = "";
            }
            return;
        }

        // ===== RIGHT HAND (movement) =====
        var rightHand = m_HandSubsystem.rightHand;
        
        if (rightHand.isTracked)
        {
            bool thumbValid = rightHand.GetJoint(XRHandJointID.ThumbTip).TryGetPose(out var thumbPose);
            bool indexValid = rightHand.GetJoint(XRHandJointID.IndexTip).TryGetPose(out var indexPose);
            bool wristValid = rightHand.GetJoint(XRHandJointID.Wrist).TryGetPose(out var wristPose);
            
            if (thumbValid && indexValid && wristValid)
            {
                float pinchDistance = Vector3.Distance(thumbPose.position, indexPose.position);
                isPinching = pinchDistance < pinchThreshold;

                if (isPinching && !wasPinching)
                {
                    pinchStartPosition = wristPose.position;
                }

                if (isPinching && wasPinching)
                {
                    Vector3 currentPosition = wristPose.position;
                    Vector3 movement = currentPosition - pinchStartPosition;

                    if (movement.magnitude > movementThreshold)
                    {
                        string direction = GetMovementDirection(movement);
                        SetCommand(direction);
                    }
                    else
                    {
                        SetCommand("Not Moving");
                    }
                }

                if (!isPinching && wasPinching)
                {
                    SetCommand("Not Moving");
                }

                wasPinching = isPinching;
            }
        }
        else
        {
            wasPinching = false;
            isPinching = false;
            SetCommand("Not Moving");
        }

        // ===== LEFT HAND (PHOTO / RECORD) =====
        var leftHand = m_HandSubsystem.leftHand;

        if (leftHand.isTracked)
        {
            bool leftThumbValid = leftHand.GetJoint(XRHandJointID.ThumbTip).TryGetPose(out var leftThumbPose);
            bool leftIndexValid = leftHand.GetJoint(XRHandJointID.IndexTip).TryGetPose(out var leftIndexPose);

            if (leftThumbValid && leftIndexValid)
            {
                float leftPinchDistance = Vector3.Distance(leftThumbPose.position, leftIndexPose.position);
                leftIsPinching = leftPinchDistance < pinchThreshold;

                if (leftIsPinching && !leftWasPinching)
                {
                    leftPinchStartTime = Time.time;
                    leftLongRecordingStarted = false;
                }

                if (leftIsPinching)
                {
                    float heldTime = Time.time - leftPinchStartTime;

                    if (!leftLongRecordingStarted && heldTime >= longPressThreshold && micFound)
                    {
                        StartMicRecording();
                        leftLongRecordingStarted = true;
                        SetCommand("Not Moving");
                    }
                }

                if (!leftIsPinching && leftWasPinching)
                {
                    float totalHeld = Time.time - leftPinchStartTime;

                    if (leftLongRecordingStarted)
                    {
                        StopMicRecording();
                        leftLongRecordingStarted = false;
                        SetCommand("Not Moving");
                    }
                    else
                    {
                        if (totalHeld < longPressThreshold)
                        {
                            photoCount++;

                            if (shutterSound != null && audioSource != null)
                                audioSource.PlayOneShot(shutterSound);

                            SetCommand("PHOTO");
                            StartCoroutine(PhotoCooldown());
                        }
                    }
                }

                leftWasPinching = leftIsPinching;
            }
        }
        else
        {
            leftWasPinching = false;
            leftIsPinching = false;
        }

        // ===== Recording indicator =====
        if (recordingIndicator != null)
        {
            recordingIndicator.SetActive(micFound && isRecording);
        }

        // ===== Transcript expiry =====
        if (hasTranscript && Time.time > transcriptExpireTime)
        {
            hasTranscript = false;
            currentTranscript = "";

            if (outputText != null)
                outputText.text = "";
        }
    }

    // ===== Commands / helpers =====
    private void SetCommand(string cmd)
    {
        if (server != null)
        {
            server.SetLastCommand(cmd);
        }
    }

    private IEnumerator PhotoCooldown()
    {
        yield return new WaitForSeconds(0.5f);
        SetCommand("Not Moving");
    }
    
    private string GetMovementDirection(Vector3 movement)
    {
        float absX = Mathf.Abs(movement.x);
        float absY = Mathf.Abs(movement.y);

        if (absY > absX)
        {
            return movement.y > 0 ? "FORWARD" : "BACKWARD";
        }
        else
        {
            return movement.x > 0 ? "RIGHT" : "LEFT";
        }
    }

    // ===== Microphone logic =====
    private void InitMicrophone()
    {
        string[] devices = Microphone.devices;

        if (devices.Length == 0)
        {
            micFound = false;
            Debug.LogWarning("GestureLogger: No microphone devices found.");
            return;
        }

        selectedMic = devices[0];
        micFound = true;
        Debug.Log("GestureLogger: Mic found: " + selectedMic);
    }

    private void StartMicRecording()
    {
        if (!micFound || isRecording)
            return;

        if (micAudioSource == null)
        {
            micAudioSource = gameObject.AddComponent<AudioSource>();
            micAudioSource.loop = true;
            micAudioSource.playOnAwake = false;
            micAudioSource.volume = 0f;
        }

        AudioClip clip = Microphone.Start(selectedMic, true, micLengthSeconds, micSampleRate);
        StartCoroutine(WaitForMicStart(clip));
    }

    private IEnumerator WaitForMicStart(AudioClip clip)
    {
        while (Microphone.GetPosition(selectedMic) <= 0)
            yield return null;

        micAudioSource.clip = clip;
        isRecording = true;
    }

    private void StopMicRecording()
    {
        if (!micFound || !isRecording)
            return;

        Microphone.End(selectedMic);

        if (micAudioSource != null)
            micAudioSource.Stop();

        isRecording = false;

        if (server != null && micAudioSource != null && micAudioSource.clip != null)
        {
            byte[] wavData = AudioClipToWav(micAudioSource.clip);
            server.SetLatestAudio(wavData);
        }
    }

    private byte[] AudioClipToWav(AudioClip clip)
    {
        if (clip == null)
            return null;

        int samples = clip.samples * clip.channels;
        float[] data = new float[samples];
        clip.GetData(data, 0);

        const int headerSize = 44;
        int byteCount = samples * 2;
        byte[] bytes = new byte[headerSize + byteCount];

        System.Text.Encoding.ASCII.GetBytes("RIFF").CopyTo(bytes, 0);
        BitConverter.GetBytes(headerSize + byteCount - 8).CopyTo(bytes, 4);
        System.Text.Encoding.ASCII.GetBytes("WAVE").CopyTo(bytes, 8);

        System.Text.Encoding.ASCII.GetBytes("fmt ").CopyTo(bytes, 12);
        BitConverter.GetBytes(16).CopyTo(bytes, 16);
        BitConverter.GetBytes((short)1).CopyTo(bytes, 20);
        BitConverter.GetBytes((short)clip.channels).CopyTo(bytes, 22);
        BitConverter.GetBytes(clip.frequency).CopyTo(bytes, 24);
        int byteRate = clip.frequency * clip.channels * 2;
        BitConverter.GetBytes(byteRate).CopyTo(bytes, 28);
        short blockAlign = (short)(clip.channels * 2);
        BitConverter.GetBytes(blockAlign).CopyTo(bytes, 32);
        short bitsPerSample = 16;
        BitConverter.GetBytes(bitsPerSample).CopyTo(bytes, 34);

        System.Text.Encoding.ASCII.GetBytes("data").CopyTo(bytes, 36);
        BitConverter.GetBytes(byteCount).CopyTo(bytes, 40);

        int offset = headerSize;
        for (int i = 0; i < samples; i++)
        {
            short val = (short)Mathf.Clamp(data[i] * 32767f, -32768f, 32767f);
            bytes[offset++] = (byte)(val & 0xFF);
            bytes[offset++] = (byte)((val >> 8) & 0xFF);
        }

        return bytes;
    }

    // ===== Transcript API (called by SimpleCommandServer on main thread) =====
    public void SetTranscript(string transcript, float audioDurationSeconds)
    {
        hasTranscript = true;
        currentTranscript = transcript;
        transcriptExpireTime = Time.time + audioDurationSeconds + 5f;

        if (outputText != null)
        {
            outputText.text = transcript;
        }
    }

}
