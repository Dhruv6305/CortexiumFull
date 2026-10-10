# PLAN: Multi-Modal Identity Recognition & Registration (Phase 08)

## Goal
Establish a "Biometric Identity Fusion" system. The system will:
1. Extract names from live speech (e.g., "I'm Alex" or "Hello Alex") using Local LLM/NLP.
2. Recognize faces from the live camera feed using DeepFace.
3. Automatically register (associate) a face embedding with a name when both are detected simultaneously.
4. Support video file processing for offline testing.

## Proposed Changes

### Backend (Python)
- **[MODIFY] [model_loader.py](file:///e:/Codes/Cortexium2.0/backend/cv/model_loader.py)**:
  - Add `register_face(frame, name)`: Saves face embedding to a local database/folder.
  - Add `identify_face(frame)`: Uses `DeepFace.find` to return a name for detected faces.
- **[NEW] [audio_router.py](file:///e:/Codes/Cortexium2.0/backend/routers/audio.py)**:
  - `POST /api/audio/transcribe`: Accepts audio blob, transcribes using optional local Whisper, and uses LLM to extract names.
- **[MODIFY] [vision.py](file:///e:/Codes/Cortexium2.0/backend/routers/vision.py)**: 
  - Update `/frame` response to include recognized identity.
  - Add `POST /video/process` to handle uploaded videos for testing.

### Frontend React (WebXR)
- **[MODIFY] [App.jsx](file:///e:/Codes/Cortexium2.0/frontend-web/src/App.jsx)**:
  - Implement **Live Camera Feed** using `getUserMedia`.
  - Add **Voice Capture** button (Web Speech API or Audio Recording).
  - High-fidelity **Identity Overlay**: Floating card that shows "Verified" or "Unidentified" status.
  - Implement **Video Upload Testbed** in a hidden/debug panel.

## Verification Plan

### Automated
1. **Mock Identity Test**: Unit test the Identity Agent by providing a known face embedding and a name string to ensure they pair correctly.
2. **NER Extraction**: Test the LLM prompt to ensure it reliably extracts "Alex" from "Hi, I'm Alex".

### Manual
1. Open HUD, allow Camera and Mic permissions.
2. Face the camera and say "I am [Your Name]".
3. Verify the Social Context panel updates from "Unidentified" to "[Your Name]".
4. Upload a video with a person speaking and verify identification.
