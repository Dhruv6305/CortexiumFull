# Cortexium XR 2.0

> **Unified Ambient Intelligence Platform & Spatial XR Telemetry System**  
> Weaving real-time computer vision, voice interaction, spatial memory, and 3D AR HUD overlays into physical environments.

---

## 🌟 Modules Overview

1. **Central Gateway Portal (`dashboard/`)** — Port `3020`
   - Single entry point routing all module traffic, Vite proxies, and health monitors.

2. **Social Intelligence Module (`frontend-web/`)** — Internal Port `3021`
   - Real-time face recognition (DeepFace ArcFace), persistent person memory graphs, voice transcription, and contextual summaries.

3. **Spatial Organizer Module (`cortexium-organizer-clone/frontend/`)** — Internal Port `3022`
   - YOLOv8 object detection, persistent 3D spatial anchoring, and personalized CatBoost ML placement intelligence.

4. **Vehicle Telemetry & 3D AR HUD (`cortexium-vehicle-web/` & `cortexium/`)** — Internal Port `3023`
   - Real-time ADAS forward perception, monocular headway ranging, ground-perspective 3D AR lane chevrons, driver behavior audits, and automated PDF coaching reports.

5. **Unified FastAPI Backend (`backend/`)** — Port `4040`
   - Serves all REST APIs, WebSocket hubs, vision inference pipelines, and background workers.

---

## 🚀 Quick Start

### 1. Requirements
- Windows 10/11
- Python 3.10+
- Node.js 18+
- Ollama (Optional, for offline local LLM fallback)

### 2. Environment Setup
```powershell
cp .env.example .env
# Edit .env with your optional Mistral or Hugging Face API keys
```

### 3. Launch All Systems
Run the master launcher:
```powershell
.\launch.bat
```
This automatically starts:
- Unified Backend at `http://localhost:4040`
- Social Module at `http://localhost:3020/module/social`
- Organizer Module at `http://localhost:3020/module/organizer`
- Vehicle AR HUD at `http://localhost:3020/module/vehicle`
- Central Dashboard at `http://localhost:3020`
- Cloudflare Tunnel for remote testing

---

## 📁 Repository Structure

```
├── backend/                  # Unified FastAPI backend & CV pipelines
├── dashboard/                # Central React Gateway dashboard (Vite)
├── frontend-web/             # Social Intelligence web client
├── cortexium-organizer-clone/# Spatial Organizer module
├── cortexium-vehicle-web/    # Vehicle Telemetry & 3D AR HUD web interface
├── cortexium/                # Native OpenCV & PyTorch ADAS engine
├── launch.bat                # One-click master startup script
├── run_backend.py            # Backend runner
└── requirements.txt          # Python dependencies
```

---

## 📜 License
MIT License
