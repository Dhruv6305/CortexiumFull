---
description: how to run the full application (Backend + Frontend + AI Dependencies)
---

To run Cortexium 2.0, you need to start three core components: the local AI models (Ollama), the FastAPI Backend, and the Vite Frontend.

### 1. Prerequisites (External Services)
Before starting the code, ensure your local AI engine is running:
- **Ollama**: Ensure Ollama is running on your system with the `llama2` (or configured) model pulled.
  - Command: `ollama run llama2` (Keep this terminal open or run as a service)

### 2. Start the Backend API
The backend handles computer vision, biometric registration, and NLP orchestration.
// turbo
1. Open a new terminal in the project root: `e:\Codes\Cortexium2.0`
2. Activate the virtual environment: `.venv\Scripts\activate`
3. Run the optimized launcher: `python run_backend.py`
   - *Alternative*: `uvicorn backend.main:app --host 0.0.0.0 --port 8989`

### 3. Start the Frontend HUD
The frontend is the XR-inspired dashboard.
// turbo
1. Open another terminal in the frontend directory: `e:\Codes\Cortexium2.0\frontend-web`
2. Run the development server: `npm run dev -- --port 3000`
3. Access the application at: [http://localhost:3000](http://localhost:3000)

### 4. Verification
Once both are running:
- The **Vision Link** in the HUD header should turn **GREEN (ONLINE)**.
- Clicking **"INITIALIZE VOICE HUD"** should activate the **Ambient Listening** loop.

### 🛠️ Troubleshooting Windows Dependencies

#### 1. Ollama (NLP Engine)
If `ollama` is not recognized:
1. Download from [ollama.com](https://ollama.com).
2. Install the app and ensure it's running (Check your System Tray).
3. If still not found, add `C:\Users\<YourUser>\AppData\Local\Programs\Ollama` to your Windows environment variables (PATH).

#### 2. YOLO/DeepFace Models
I have updated the code to **automatically download** these models on first run. 
- **YOLOv8**: Will download `yolov8n.pt` (~6MB) to project root.
- **DeepFace**: Will download the VGG-Face weights (~500MB) to `~/.deepface/weights` on first use.
