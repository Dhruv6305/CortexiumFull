# PLAN: Core Model Integration (Phase 06)

## Goal
Integrate the three core local AI engines (LLM via Ollama, Object Detection via YOLOv8, and Face Recognition via DeepFace) into the FastAPI backend. This replaces the need for paid cloud APIs and establishes the "Adaptive Learning" foundation.

## Proposed Changes

### Backend (Python)
- **[NEW] [model_loader.py](file:///e:/Codes/Cortexium2.0/backend/cv/model_loader.py)**: Singleton class to load and hold model instances in memory (YOLOv8, DeepFace, Mediapipe).
- **[NEW] [llm_client.py](file:///e:/Codes/Cortexium2.0/backend/ai/llm_client.py)**: Async client to communicate with the local Ollama server.
- **[MODIFY] [vision.py](file:///e:/Codes/Cortexium2.0/backend/routers/vision.py)**: Update `/api/vision/frame` to call the model loader and return real inference results.
- **[MODIFY] [agents.py](file:///e:/Codes/Cortexium2.0/backend/routers/agents.py)**: Update agent endpoints to leverage the LLM for reasoning based on CV events.

## Verification Plan

### Automated
1. **Model Load Test**: `pytest backend/tests/test_cv_models.py` to ensure models load without memory errors.
2. **Inference Test**: `pytest backend/tests/test_inference.py` using a mock frame to verify object/face detection outputs.
3. **LLM Connectivity**: `pytest backend/tests/test_llm.py` to check connection to local Ollama (`http://localhost:11434`).

### Manual
1. Start the FastAPI server and local Ollama.
2. Send a sample image to `/api/vision/frame` using `curl` or Postman.
3. Verify the JSON response contains detected objects (e.g., "cup", "keyboard") and face embeddings/names.
