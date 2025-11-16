using UnityEngine;
using UnityEngine.UI;

public class VideoFeedDisplay : MonoBehaviour
{
    public RawImage rawImage;      // Assign your VideoFeed RawImage here
    public Texture2D testFrame;    // Optional test image

    private Texture2D frameTexture;
    private SimpleCommandServer server;

    void Awake()
    {
        if (rawImage == null)
            rawImage = GetComponent<RawImage>();

        // Dummy texture; will be replaced when frames come in
        frameTexture = new Texture2D(2, 2, TextureFormat.RGB24, false);
        rawImage.texture = frameTexture;

        // Find the server in the scene
        server = FindObjectOfType<SimpleCommandServer>();
        if (server == null)
        {
            Debug.LogWarning("VideoFeedDisplay: SimpleCommandServer not found in scene.");
        }
    }

    void Start()
    {
        // TEST MODE: show a static image if assigned
        if (testFrame != null)
        {
            rawImage.texture = testFrame;
            frameTexture = testFrame;
        }
    }

    void Update()
    {
        if (server == null) return;

        // Ask the server if there is a new frame from the Pi
        byte[] frameBytes = server.ConsumeLatestFrame();
        if (frameBytes != null)
        {
            UpdateFrame(frameBytes);
        }
    }

    /// <summary>
    /// Updates the video feed by decoding JPEG/PNG bytes
    /// and applying the result to the RawImage.
    /// </summary>
    public void UpdateFrame(byte[] imageBytes)
    {
        if (imageBytes == null || imageBytes.Length == 0)
            return;

        frameTexture.LoadImage(imageBytes);
        rawImage.texture = frameTexture;
    }
}
