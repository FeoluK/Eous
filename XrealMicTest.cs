using UnityEngine;

public class XrealMicTest : MonoBehaviour
{
    public AudioSource audioSource;      // drag an AudioSource here in Inspector
    public int sampleRate = 16000;      // 16 kHz is fine for voice
    public int lengthSeconds = 10;      // length of the recording buffer

    void Start()
    {
        // Log all available microphone devices
        foreach (var dev in Microphone.devices)
        {
            Debug.Log("Mic device: " + dev);
        }

        // Use default mic (null) or pick a specific device name from the logs
        string deviceName = null; // or "XREAL Mic" / whatever shows up

        // Start continuous recording
        AudioClip clip = Microphone.Start(deviceName, true, lengthSeconds, sampleRate);
        audioSource.loop = true;
        audioSource.clip = clip;

        // Wait until the recording has started before playing it back
        while (!(Microphone.GetPosition(deviceName) > 0)) { }

        audioSource.Play();
        Debug.Log("Mic recording started.");
    }
}
