using System;
using System.Net;
using System.Text;
using System.Collections;
using System.IO;
using System.Globalization;
using System.Linq;
using UnityEngine;

public class SimpleCommandServer : MonoBehaviour
{
    private HttpListener listener;

    // ===== Commands (for your robot) =====
    [SerializeField] private string lastCommand = "Waiting for command";

    public void SetLastCommand(string cmd)
    {
        lastCommand = cmd;
        Debug.Log("LastCommand updated to: " + cmd);
    }

    // ===== Video frames (from Pi) =====
    private byte[] latestFrameBytes = null;
    private bool hasNewFrame = false;
    private readonly object frameLock = new object();

    public byte[] ConsumeLatestFrame()
    {
        lock (frameLock)
        {
            if (!hasNewFrame || latestFrameBytes == null)
                return null;

            byte[] data = latestFrameBytes;
            latestFrameBytes = null;
            hasNewFrame = false;
            return data;
        }
    }

    [Serializable]
    private class FramePayload
    {
        public string frame;   // base64-encoded JPEG from Pi
    }

    // ===== Audio recording (served at /audio) =====
    private byte[] latestAudioBytes = null;
    private bool hasAudio = false;
    private Coroutine clearAudioCoroutine = null;

    public void SetLatestAudio(byte[] audioData)
    {
        latestAudioBytes = audioData;
        hasAudio = (audioData != null && audioData.Length > 0);

        if (clearAudioCoroutine != null)
        {
            StopCoroutine(clearAudioCoroutine);
            clearAudioCoroutine = null;
        }

        if (hasAudio)
        {
            clearAudioCoroutine = StartCoroutine(ClearAudioAfterDelay());
            Debug.Log("SimpleCommandServer: New audio set, size = " + audioData.Length);
        }
    }

    private IEnumerator ClearAudioAfterDelay()
    {
        // adjust as you like
        yield return new WaitForSeconds(2f);
        latestAudioBytes = null;
        hasAudio = false;
        clearAudioCoroutine = null;
        Debug.Log("SimpleCommandServer: Audio cleared after delay.");
    }

    // ===== Transcript handoff to GestureLogger (thread-safe) =====
    private string pendingTranscriptText = null;
    private float pendingTranscriptDuration = 0f;
    private bool hasPendingTranscript = false;

    void Start()
    {
        DontDestroyOnLoad(gameObject);

        listener = new HttpListener();
        listener.Prefixes.Add("http://*:5000/");
        listener.Start();

        Debug.Log("Unity HTTP Server started on port 5000 (Android)");
        listener.BeginGetContext(HandleRequest, null);
    }

    void Update()
    {
        // This runs on Unity's main thread – safe to touch GestureLogger here
        if (hasPendingTranscript)
        {
            hasPendingTranscript = false;

            var logger = FindObjectOfType<GestureLogger>();
            if (logger != null)
            {
                logger.SetTranscript(pendingTranscriptText, pendingTranscriptDuration);
            }
            else
            {
                Debug.LogWarning("SimpleCommandServer: No GestureLogger found to set transcript.");
            }
        }
    }

    private void HandleRequest(IAsyncResult result)
    {
        if (listener == null || !listener.IsListening) return;

        HttpListenerContext context = null;

        try
        {
            context = listener.EndGetContext(result);
        }
        catch (ObjectDisposedException)
        {
            return;
        }
        catch (Exception e)
        {
            Debug.LogError("Error in EndGetContext: " + e);
            return;
        }

        listener.BeginGetContext(HandleRequest, null);

        var request = context.Request;
        var response = context.Response;

        string path = request.Url.AbsolutePath;

        try
        {
            if (path == "/command")
            {
                HandleCommandEndpoint(request, response);
            }
            else if (path == "/send")
            {
                HandleFrameEndpoint(request, response);
            }
            else if (path == "/audio")
            {
                HandleAudioEndpoint(request, response);
            }
            else if (path == "/transcript")
            {
                HandleTranscriptEndpoint(request, response);
            }
            else
            {
                byte[] buffer = Encoding.UTF8.GetBytes("Unity HTTP server is running.");
                response.StatusCode = 200;
                response.OutputStream.Write(buffer, 0, buffer.Length);
                response.Close();
            }
        }
        catch (Exception e)
        {
            Debug.LogError("Error handling request: " + e);
            try
            {
                response.StatusCode = 500;
                response.Close();
            }
            catch { }
        }
    }

    // ---------- /command ----------
    private void HandleCommandEndpoint(HttpListenerRequest request, HttpListenerResponse response)
    {
        if (request.HttpMethod == "GET")
        {
            string msg = lastCommand;
            byte[] buffer = Encoding.UTF8.GetBytes(msg);

            response.StatusCode = 200;
            response.OutputStream.Write(buffer, 0, buffer.Length);
            response.Close();
            return;
        }

        if (request.HttpMethod == "POST")
        {
            using (var reader = new StreamReader(request.InputStream))
            {
                string body = reader.ReadToEnd();
                Debug.Log("Received POST /command body: " + body);
            }

            string reply = "{\"status\":\"ok\"}";
            byte[] buffer = Encoding.UTF8.GetBytes(reply);

            response.ContentType = "application/json";
            response.StatusCode = 200;
            response.OutputStream.Write(buffer, 0, buffer.Length);
            response.Close();
        }
        else
        {
            response.StatusCode = 405;
            response.Close();
        }
    }

    // ---------- /send (video frames) ----------
    private void HandleFrameEndpoint(HttpListenerRequest request, HttpListenerResponse response)
    {
        if (request.HttpMethod != "POST")
        {
            response.StatusCode = 405;
            response.Close();
            return;
        }

        string body;
        using (var reader = new StreamReader(request.InputStream))
        {
            body = reader.ReadToEnd();
        }

        FramePayload payload = null;
        try
        {
            payload = JsonUtility.FromJson<FramePayload>(body);
        }
        catch (Exception e)
        {
            Debug.LogError("Failed to parse frame JSON: " + e);
        }

        if (payload == null || string.IsNullOrEmpty(payload.frame))
        {
            byte[] buf = Encoding.UTF8.GetBytes("{\"status\":\"error\",\"reason\":\"no frame\"}");
            response.StatusCode = 400;
            response.ContentType = "application/json";
            response.OutputStream.Write(buf, 0, buf.Length);
            response.Close();
            return;
        }

        try
        {
            byte[] frameBytes = Convert.FromBase64String(payload.frame);

            lock (frameLock)
            {
                latestFrameBytes = frameBytes;
                hasNewFrame = true;
            }

            byte[] buf = Encoding.UTF8.GetBytes("{\"status\":\"ok\"}");
            response.StatusCode = 200;
            response.ContentType = "application/json";
            response.OutputStream.Write(buf, 0, buf.Length);
            response.Close();
        }
        catch (Exception e)
        {
            Debug.LogError("Error decoding base64 frame: " + e);
            byte[] buf = Encoding.UTF8.GetBytes("{\"status\":\"error\",\"reason\":\"decode failed\"}");
            response.StatusCode = 500;
            response.ContentType = "application/json";
            response.OutputStream.Write(buf, 0, buf.Length);
            response.Close();
        }
    }

    // ---------- /audio ----------
    private void HandleAudioEndpoint(HttpListenerRequest request, HttpListenerResponse response)
    {
        if (request.HttpMethod != "GET")
        {
            response.StatusCode = 405;
            response.Close();
            return;
        }

        if (!hasAudio || latestAudioBytes == null || latestAudioBytes.Length == 0)
        {
            response.StatusCode = 404;
            response.Close();
            return;
        }

        response.StatusCode = 200;
        response.ContentType = "audio/wav";
        response.OutputStream.Write(latestAudioBytes, 0, latestAudioBytes.Length);
        response.Close();
    }

    // ---------- /transcript ----------
    // Body: "<number> rest of transcript text"
    private void HandleTranscriptEndpoint(HttpListenerRequest request, HttpListenerResponse response)
    {
        if (request.HttpMethod != "POST")
        {
            response.StatusCode = 405;
            response.Close();
            return;
        }

        string body;
        using (var reader = new StreamReader(request.InputStream))
        {
            body = reader.ReadToEnd();
        }

        if (string.IsNullOrWhiteSpace(body))
        {
            byte[] buf = Encoding.UTF8.GetBytes("{\"status\":\"error\",\"reason\":\"empty body\"}");
            response.StatusCode = 400;
            response.ContentType = "application/json";
            response.OutputStream.Write(buf, 0, buf.Length);
            response.Close();
            return;
        }

        string[] tokens = body.Trim().Split((char[])null, StringSplitOptions.RemoveEmptyEntries);
        if (tokens.Length < 2)
        {
            byte[] buf = Encoding.UTF8.GetBytes("{\"status\":\"error\",\"reason\":\"need <duration> <transcript>\"}");
            response.StatusCode = 400;
            response.ContentType = "application/json";
            response.OutputStream.Write(buf, 0, buf.Length);
            response.Close();
            return;
        }

        if (!float.TryParse(tokens[0], NumberStyles.Float, CultureInfo.InvariantCulture, out float durationSeconds))
        {
            byte[] buf = Encoding.UTF8.GetBytes("{\"status\":\"error\",\"reason\":\"invalid duration\"}");
            response.StatusCode = 400;
            response.ContentType = "application/json";
            response.OutputStream.Write(buf, 0, buf.Length);
            response.Close();
            return;
        }

        string transcript = string.Join(" ", tokens.Skip(1));
        Debug.Log($"SimpleCommandServer: Received transcript '{transcript}' ({durationSeconds}s)");

        // Store as pending; handled on main thread in Update()
        pendingTranscriptText = transcript;
        pendingTranscriptDuration = durationSeconds;
        hasPendingTranscript = true;

        byte[] okBuf = Encoding.UTF8.GetBytes("{\"status\":\"ok\"}");
        response.StatusCode = 200;
        response.ContentType = "application/json";
        response.OutputStream.Write(okBuf, 0, okBuf.Length);
        response.Close();
    }

    void OnApplicationQuit()
    {
        if (listener != null)
        {
            listener.Stop();
            listener.Close();
            listener = null;
        }
    }
}
