"""
Cortexium 2.0 — FastAPI Application Entry Point
Includes: CORS middleware, all routers, startup model pre-warming.
"""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routers import vision, agents, ws_hub, audio, memory, adaptive, local_db, persons, organizer, vehicle


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan: runs startup tasks before serving requests.
    Pre-warms models so the first user request is fast.
    """
    print("[Cortexium] Starting up...")
    # Pre-warm local DB (creates default JSON files on first run)
    from .db.database import local_db
    print(f"[Cortexium] Local DB ready at: {local_db.db_path}")
    # ModelLoader and SessionManager are singletons — auto-init on first import
    print("[Cortexium] All systems ready. Auth: local | DB: JSON | Redis: disabled")
    # Backfill session summaries for all existing conversation data (non-blocking)
    import asyncio
    from .core.summary_manager import backfill_all
    asyncio.ensure_future(backfill_all())
    print("[Cortexium] Session summary backfill scheduled")
    # Start organizer detector background thread
    # Pass the running event loop so WebSocket broadcasts work correctly.
    # (Fix for deprecated asyncio.get_event_loop() in Python 3.10+)
    from .routers.organizer import start_organizer_background
    start_organizer_background(asyncio.get_running_loop())
    print("[Cortexium] Organizer detector thread launched")
    yield
    print("[Cortexium] Shutting down.")


app = FastAPI(
    title="Cortexium 2.0 API",
    description=(
        "Ambient Intelligence Platform — Real-time CV, Face Recognition, "
        "Agentic AI, and Adaptive Learning via WebXR."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# ------------------------------------------------------------------
# CORS — allow the Vite dev server and any local origin
# ------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------
# Routers
# ------------------------------------------------------------------
app.include_router(vision.router)
app.include_router(agents.router)
app.include_router(ws_hub.router)
app.include_router(audio.router)
app.include_router(memory.router)
app.include_router(adaptive.router)
app.include_router(local_db.router)
app.include_router(persons.router)
app.include_router(organizer.router)
app.include_router(vehicle.router)

# Serve face images at /faces/<filename> so the frontend can display them
_FACES_DIR = Path(__file__).resolve().parent / "data" / "faces"
_FACES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/faces", StaticFiles(directory=str(_FACES_DIR)), name="faces")


@app.get("/")
async def root():
    return {
        "name": "Cortexium 2.0",
        "status": "operational",
        "docs": "/docs",
        "ws_endpoint": "/ws/events",
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "2.0.0"}


# Alias so the frontend gateway health check (/api/health) also works
@app.get("/api/health")
async def api_health():
    return {"status": "healthy", "version": "2.0.0"}
