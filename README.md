Devpost Link: https://devpost.com/software/eous



# **Eous — Your AR Bangboo Assistant**

## **Inspiration**
We wanted to build a fully hands-free assistant that lives in augmented reality — something you can wear, gesture to, and speak to, and that can see and act in the physical world. Inspired by *Zenless Zone Zero’s* Bangboo robots, we imagined a tiny helper that follows you around, listens, watches, and supports you in daily tasks. AR glasses felt like the perfect medium to bring that vision to life.

## **What it does**
Eous is an embodied AR assistant that connects your gestures, voice, and environment to a real robot.

- **Gesture-based control:** Move your hand and pinch to drive a robot car in real time.  
- **Photo capture:** Short left-hand pinch triggers image capture with a shutter effect.  
- **Voice recording:** Long left-hand pinch records audio from the AR glasses’ microphone.  
- **Transcription display:** Eous shows live transcriptions inside the AR interface.  
- **Video streaming:** The robot streams a live camera feed into the AR HUD.  
- **On-device processing:** Everything runs on a phone + AR glasses — no PC required.  

Eous becomes a mixed-reality companion that listens, sees, and reacts.

## **How we built it**
- **XReal Air 2 Ultra** for hand tracking and AR display  
- **Unity** running inside an Android host app  
- **Custom gesture recognition** using XR Hands  
- **Local HTTP server** inside Unity (`HttpListener`) handling:
  - `/command` → robot control  
  - `/send` → robot video feed  
  - `/audio` → WAV recording retrieval  
  - `/transcript` → subtitle display in AR  
- **Raspberry Pi-controlled robot** for movement + camera streaming  
- **Python backend** for:
  - Video encoding  
  - Command forwarding  
  - Speech-to-text (STT)  
  - Transcript packaging  

We engineered a realtime bidirectional system between AR glasses ↔ phone ↔ robot.

## **Challenges we ran into**
- Getting **mic access** through AR glasses on Android  
- Preventing **audio feedback** (hearing yourself through the glasses)  
- Streaming a video feed into Unity efficiently  
- Ensuring **gesture detection** was stable and not jittery  
- Synchronizing recording → upload → transcription → AR display  
- Handling **thread-safe communication** between Unity and background HTTP threads  
- Keeping latency low across three devices  

## **Accomplishments that we're proud of**
- Built a seamless **gesture-to-robot control** pipeline  
- Achieved **live AR subtitles** from physical-world voice recordings  
- Got fully working **mic recording + WAV encoding** on XReal glasses  
- Created an intuitive AR UI that feels natural and persistent  
- Integrated AR, robotics, audio, and networking into a single real product  
- All running locally — no cloud dependencies required  

## **What we learned**
- Unity can be used as a full network server on Android  
- AR gesture design requires careful tuning to avoid false triggers  
- Audio pipelines on Android are extremely tricky  
- Efficient video transfer needs strict encoding discipline  
- Managing concurrency in Unity requires main-thread syncing  
- AR UI/UX matters far more than expected — clarity beats complexity  

## **What's next for Eous**
- On-device object detection via lightweight ML  
- Pathfinding so the robot can navigate autonomously  
- Multi-modal memory: store conversations, photos, and events  
- A full web dashboard to review captured data and robot logs  

---

**Eous** is just the beginning — an AR assistant that blends digital intelligence with real-world embodiment.
