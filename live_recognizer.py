"""
Cortexium 2.0 — Live Person Recognizer + Voice Integration
===========================================================
Real-time AR overlay fusing computer vision + microphone:

  VISION  : YOLOv8 detects all persons → IoU tracking → DeepFace identifies
  AUDIO   : Background mic thread → Google STT (or Vosk offline)
            Detects introduction phrases → auto-registers unknown face
            Phrases: "I am X", "I'm X", "my name is X",
                     "here is X", "this is X", "call me X", "meet X"

  STORAGE : backend/data/faces/      — face images (DeepFace DB)
            backend/data/conversations/ — per-person conversation logs

Controls:
  R     — Register closest person manually (type name)
  L     — Log a conversation note for identified person
  Q / ESC — Quit
  Space — Pause / Resume
  M     — Toggle microphone on/off

Run: .venv\\Scripts\\python.exe live_recognizer.py
"""

import os, re, cv2, json, time, threading, queue
import numpy as np
from pathlib import Path
from datetime import datetime

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).resolve().parent
DATA_DIR  = ROOT / "backend" / "data"
FACES_DIR = DATA_DIR / "faces"
CONVOS_DIR= DATA_DIR / "conversations"

FACES_DIR.mkdir(parents=True, exist_ok=True)
CONVOS_DIR.mkdir(parents=True, exist_ok=True)

# ── Model loading ─────────────────────────────────────────────────────────────
print("[Cortexium] Loading YOLOv8...")
try:
    from ultralytics import YOLO
    YOLO_MODEL = YOLO(str(ROOT / "yolov8s.pt"))
    YOLO_MODEL(np.zeros((64,64,3), dtype=np.uint8), verbose=False)
    print("[Cortexium] YOLOv8 ready ✓")
except Exception as e:
    print(f"[Cortexium] YOLOv8 error: {e}")
    YOLO_MODEL = None

try:
    from deepface import DeepFace
    DEEPFACE_OK = True
    print("[Cortexium] DeepFace ready ✓")
except ImportError:
    DEEPFACE_OK = False
    print("[Cortexium] DeepFace not installed — face ID disabled")

try:
    import speech_recognition as sr
    SR_OK = True
    print("[Cortexium] SpeechRecognition ready ✓")
except ImportError:
    SR_OK = False
    print("[Cortexium] SpeechRecognition not installed — audio disabled")

# ── Constants ─────────────────────────────────────────────────────────────────
CLOSE_THRESHOLD   = 0.22
IDENTIFY_INTERVAL = 4.0
EMOTION_INTERVAL  = 3.0
MIC_ENERGY        = 300     # ambient noise threshold

# Name intro patterns (case-insensitive)
NAME_PATTERNS = [
    r"(?:i am|i'm|im)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    r"my name is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    r"(?:here is|this is|meet|introducing|call me)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+here\b",
    r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?),?\s+(?:nice|good|pleasure)",
]

# AR Colours (BGR)
C_GREEN   = (60, 220, 60)
C_CYAN    = (220, 200, 50)
C_UNKNOWN = (140, 120, 200)
C_RED     = (60, 60, 220)
C_WHITE   = (230, 230, 230)
C_DIM     = (80, 80, 100)
C_GOLD    = (40, 190, 255)
C_TEAL    = (180, 220, 60)

FONT      = cv2.FONT_HERSHEY_SIMPLEX
FONT_MONO = cv2.FONT_HERSHEY_DUPLEX


# ══════════════════════════════════════════════════════════════════════════════
#  Conversation store
# ══════════════════════════════════════════════════════════════════════════════

def load_conv(name: str) -> dict:
    fp = CONVOS_DIR / f"{name}.json"
    if fp.exists():
        try:
            return json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"name": name, "entries": [], "last_seen": None, "registered_via": None}


def save_conv(data: dict):
    fp = CONVOS_DIR / f"{data['name']}.json"
    fp.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def touch_last_seen(name: str):
    d = load_conv(name)
    d["last_seen"] = datetime.now().isoformat()
    save_conv(d)


def add_note(name: str, note: str, source: str = "manual"):
    d = load_conv(name)
    d["entries"].append({
        "timestamp": datetime.now().isoformat(),
        "note": note,
        "source": source,
    })
    d["last_seen"] = datetime.now().isoformat()
    save_conv(d)


def last_seen_str(name: str) -> str:
    d = load_conv(name)
    ls = d.get("last_seen")
    if not ls:
        return "Never"
    try:
        delta = int((datetime.now() - datetime.fromisoformat(ls)).total_seconds())
        if delta < 60:    return f"{delta}s ago"
        if delta < 3600:  return f"{delta//60}m ago"
        if delta < 86400: return f"{delta//3600}h ago"
        return f"{delta//86400}d ago"
    except Exception:
        return "?"


def last_notes(name: str, n=3) -> list[str]:
    return [e["note"] for e in load_conv(name).get("entries", [])[-n:]]


# ══════════════════════════════════════════════════════════════════════════════
#  Name extractor
# ══════════════════════════════════════════════════════════════════════════════

def extract_name(text: str) -> str | None:
    """Extract a person name from an introduction phrase."""
    for pattern in NAME_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            name = m.group(1).strip().title()
            # Reject common false positives
            if name.lower() not in ("a", "the", "your", "my", "our", "its",
                                    "here", "there", "that", "this", "not"):
                return name
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  Background microphone thread
# ══════════════════════════════════════════════════════════════════════════════

class MicListener(threading.Thread):
    """
    Continuously listens on the microphone, sends transcriptions to a queue.
    Uses Google Speech Recognition (free, no API key needed for low usage).
    Falls back gracefully if no mic / network unavailable.
    """
    def __init__(self, result_queue: queue.Queue):
        super().__init__(daemon=True)
        self.q       = result_queue
        self.running = True
        self.enabled = True
        self.status  = "starting"

    def run(self):
        if not SR_OK:
            self.status = "disabled"
            return
        try:
            recognizer = sr.Recognizer()
            recognizer.energy_threshold       = MIC_ENERGY
            recognizer.dynamic_energy_threshold = True
            recognizer.pause_threshold        = 0.7   # shorter pause = faster response

            mic = sr.Microphone()
            with mic as source:
                recognizer.adjust_for_ambient_noise(source, duration=1)
                self.status = "listening"
                print("[Mic] Listening for voice introductions...")

            while self.running:
                if not self.enabled:
                    time.sleep(0.2)
                    continue
                try:
                    with mic as source:
                        audio = recognizer.listen(source, timeout=3, phrase_time_limit=6)
                    text = recognizer.recognize_google(audio, language="en-US")
                    print(f"[Mic] Heard: \"{text}\"")
                    self.q.put(text)
                except sr.WaitTimeoutError:
                    pass
                except sr.UnknownValueError:
                    pass   # speech not understood
                except sr.RequestError as e:
                    self.status = f"error: {e}"
                    time.sleep(3)   # back off on network error
                except Exception as e:
                    print(f"[Mic] Error: {e}")
                    time.sleep(1)
        except Exception as e:
            self.status = f"failed: {e}"
            print(f"[Mic] Could not start microphone: {e}")

    def toggle(self):
        self.enabled = not self.enabled
        self.status  = "listening" if self.enabled else "muted"


# ══════════════════════════════════════════════════════════════════════════════
#  Drawing helpers
# ══════════════════════════════════════════════════════════════════════════════

def glow_rect(img, x1, y1, x2, y2, color, thick=2):
    ov = img.copy()
    for i in range(4, 0, -1):
        cv2.rectangle(ov, (x1-i*2, y1-i*2), (x2+i*2, y2+i*2), color, 1)
    cv2.addWeighted(ov, 0.3, img, 0.7, 0, img)
    cv2.rectangle(img, (x1, y1), (x2, y2), color, thick)


def corners(img, x1, y1, x2, y2, color, L=22, thick=2):
    pts = [
        [(x1,y1+L),(x1,y1),(x1+L,y1)],
        [(x2-L,y1),(x2,y1),(x2,y1+L)],
        [(x1,y2-L),(x1,y2),(x1+L,y2)],
        [(x2-L,y2),(x2,y2),(x2,y2-L)],
    ]
    for group in pts:
        for i in range(len(group)-1):
            cv2.line(img, group[i], group[i+1], color, thick, cv2.LINE_AA)


def pill(img, text, x, y, color, fs=0.38, alpha=0.75):
    (tw,th),_ = cv2.getTextSize(text, FONT_MONO, fs, 1)
    p = 4
    ov = img.copy()
    cv2.rectangle(ov, (x-p, y-th-p), (x+tw+p, y+p), (8,8,18), -1)
    cv2.addWeighted(ov, alpha, img, 1-alpha, 0, img)
    cv2.putText(img, text, (x,y), FONT_MONO, fs, color, 1, cv2.LINE_AA)


def side_card(img, name, emotion, confidence, fw, fh):
    W, H = 305, min(fh-40, 430)
    cx, cy = fw - W - 12, 20

    ov = img.copy()
    cv2.rectangle(ov, (cx,cy), (cx+W, cy+H), (10,12,22), -1)
    cv2.addWeighted(ov, 0.84, img, 0.16, 0, img)
    cv2.rectangle(img, (cx,cy), (cx+W, cy+H), (70,150,255), 1)
    cv2.rectangle(img, (cx,cy), (cx+W, cy+3), (80,200,255), -1)

    y = cy + 22
    cv2.putText(img, "IDENTITY MATCHED", (cx+10,y), FONT, 0.32, (70,190,255), 1, cv2.LINE_AA)

    y += 8; cv2.line(img,(cx+8,y),(cx+W-8,y),(45,60,100),1)

    y += 26
    cv2.putText(img, name.upper(), (cx+10,y), FONT_MONO, 0.70, (220,235,255), 1, cv2.LINE_AA)

    y += 22
    emo_colors = {"happy":(80,220,100),"sad":(200,100,80),"angry":(60,60,230),
                  "neutral":(180,180,210),"surprise":(80,220,255),"fear":(130,80,200),
                  "disgust":(70,160,90)}
    ec = emo_colors.get((emotion or "").lower(), (180,180,200))
    cv2.putText(img, f"EMOTION: {(emotion or 'UNKNOWN').upper()}", (cx+10,y), FONT, 0.36, ec, 1, cv2.LINE_AA)
    cv2.putText(img, f"{confidence:.0%}", (cx+W-52,y), FONT, 0.36, (150,210,150), 1, cv2.LINE_AA)

    y += 20
    cv2.putText(img, f"LAST SEEN: {last_seen_str(name)}", (cx+10,y), FONT, 0.33, (130,155,175), 1, cv2.LINE_AA)

    # Registration source
    d = load_conv(name)
    reg_via = d.get("registered_via", "manual")
    y += 16
    cv2.putText(img, f"REGISTERED: {reg_via.upper()}", (cx+10,y), FONT, 0.30,
                (C_GOLD if reg_via=="voice" else C_DIM), 1, cv2.LINE_AA)

    y += 12; cv2.line(img,(cx+8,y),(cx+W-8,y),(40,55,90),1)

    y += 16
    cv2.putText(img, "RECENT CONVERSATIONS", (cx+10,y), FONT, 0.30, (70,150,210), 1, cv2.LINE_AA)

    notes = last_notes(name, 3)
    if notes:
        for note in reversed(notes):
            words = note.split()
            lines, line = [], []
            for w in words:
                if len(" ".join(line+[w])) <= 36: line.append(w)
                else: lines.append(" ".join(line)); line=[w]
            if line: lines.append(" ".join(line))
            y += 18
            cv2.putText(img, f"• {lines[0]}", (cx+12,y), FONT, 0.31, (190,205,225), 1, cv2.LINE_AA)
            for extra in lines[1:2]:
                y += 13
                cv2.putText(img, f"  {extra}", (cx+12,y), FONT, 0.31, (160,175,195), 1, cv2.LINE_AA)
    else:
        y += 18
        cv2.putText(img, "  No notes yet — Press L to log", (cx+12,y), FONT, 0.30, (60,80,110), 1, cv2.LINE_AA)

    y = cy+H-16; cv2.line(img,(cx+8,y-8),(cx+W-8,y-8),(35,50,85),1)
    cv2.putText(img, f"CORTEXIUM 2.0 | {datetime.now().strftime('%H:%M:%S')}",
                (cx+10,y), FONT, 0.28, (45,65,95), 1, cv2.LINE_AA)


def hud_header(img, fw, fh, n_persons, identified, mic_status):
    ov = img.copy()
    cv2.rectangle(ov, (0,0), (fw,34), (6,8,16), -1)
    cv2.addWeighted(ov, 0.86, img, 0.14, 0, img)

    ts = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    cv2.putText(img, f"CORTEXIUM 2.0  |  {ts}", (10,22), FONT_MONO, 0.44, (55,175,255), 1, cv2.LINE_AA)

    mid = f"PERSONS: {n_persons}  |  IDENTIFIED: {len(identified)}"
    cv2.putText(img, mid, (fw//2-110,22), FONT_MONO, 0.40, (155,195,255), 1, cv2.LINE_AA)

    # Mic indicator
    mic_col  = C_GREEN if mic_status=="listening" else (C_RED if "error" in mic_status else C_DIM)
    mic_label= f"MIC: {mic_status.upper()}"
    (tw,_),_ = cv2.getTextSize(mic_label, FONT, 0.34, 1)
    cv2.circle(img, (fw-tw-24, 16), 5, mic_col, -1)
    cv2.putText(img, mic_label, (fw-tw-16,20), FONT, 0.34, mic_col, 1, cv2.LINE_AA)


def voice_toast(img, text, fw, fh, alpha=1.0):
    """Animated toast for voice events."""
    ov = img.copy()
    y0 = fh - 75
    cv2.rectangle(ov, (10, y0), (fw-10, y0+45), (15,40,15), -1)
    cv2.addWeighted(ov, 0.88, img, 0.12, 0, img)
    cv2.rectangle(img, (10, y0), (fw-10, y0+45), C_GREEN, 1)
    cv2.putText(img, "VOICE DETECTED", (22, y0+14), FONT, 0.36, C_GOLD, 1, cv2.LINE_AA)
    cv2.putText(img, text, (22, y0+34), FONT_MONO, 0.46, C_GREEN, 1, cv2.LINE_AA)


# ══════════════════════════════════════════════════════════════════════════════
#  Track state
# ══════════════════════════════════════════════════════════════════════════════

class Track:
    def __init__(self, tid):
        self.tid            = tid
        self.bbox           = None
        self.identity       = None
        self.confidence     = 0.0
        self.emotion        = None
        self.last_id_check  = 0.0
        self.last_emo_check = 0.0
        self.frames         = 0

    def close(self, fh):
        if not self.bbox: return False
        return (self.bbox[3]-self.bbox[1])/fh >= CLOSE_THRESHOLD

    def proximity(self, fh):
        if not self.bbox: return 0.0
        return min(1.0,(self.bbox[3]-self.bbox[1])/fh/CLOSE_THRESHOLD)


def iou(a, b):
    ix1=max(a[0],b[0]); iy1=max(a[1],b[1])
    ix2=min(a[2],b[2]); iy2=min(a[3],b[3])
    inter=max(0,ix2-ix1)*max(0,iy2-iy1)
    if not inter: return 0.0
    ua=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter
    return inter/ua if ua else 0.0


# ══════════════════════════════════════════════════════════════════════════════
#  Face registration helper
# ══════════════════════════════════════════════════════════════════════════════

def register_face(name: str, frame: np.ndarray, source: str = "manual") -> bool:
    """Save face image and conversation record. Returns True on success."""
    try:
        path = FACES_DIR / f"{name}.jpg"
        cv2.imwrite(str(path), frame)
        # Invalidate DeepFace index
        for pkl in FACES_DIR.glob("*.pkl"):
            pkl.unlink()
        d = load_conv(name)
        d["registered_via"] = source
        d["last_seen"] = datetime.now().isoformat()
        save_conv(d)
        add_note(name, f"Auto-registered via {source}", source=source)
        print(f"[Cortexium] Registered '{name}' via {source} → {path}")
        return True
    except Exception as e:
        print(f"[Cortexium] Register error: {e}")
        return False


def face_db_names() -> list[str]:
    return [f.stem for f in FACES_DIR.glob("*.jpg")] + [f.stem for f in FACES_DIR.glob("*.png")]


# ══════════════════════════════════════════════════════════════════════════════
#  Main loop
# ══════════════════════════════════════════════════════════════════════════════

def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[Cortexium] ERROR: Cannot open webcam")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)

    print("\n" + "="*58)
    print("  CORTEXIUM 2.0 — Live Recognizer + Voice")
    print("="*58)
    print("  R       : Register closest person (manual)")
    print("  L       : Log conversation note")
    print("  M       : Toggle microphone on/off")
    print("  SPACE   : Pause / Resume")
    print("  Q / ESC : Quit")
    print("="*58)
    print("  VOICE   : Say 'I am [name]' or 'My name is [name]'")
    print("            to auto-register an unknown face.")
    print("="*58 + "\n")

    # Start mic listener
    speech_queue: queue.Queue = queue.Queue()
    mic = MicListener(speech_queue)
    if SR_OK:
        mic.start()
        time.sleep(0.5)

    tracks: dict[int, Track] = {}
    next_id   = 0
    paused    = False
    last_frame= None

    # Toast state
    toast_text  = None
    toast_until = 0.0

    # Pending voice-name registration
    pending_voice_name: str | None = None
    pending_since = 0.0  # capture next close frame after this

    while True:
        now = time.time()

        # ── Process speech queue ───────────────────────────────────────────────
        while not speech_queue.empty():
            text = speech_queue.get_nowait()
            name = extract_name(text)
            if name:
                known = face_db_names()
                if name.lower() in [k.lower() for k in known]:
                    toast_text  = f"Voice: '{name}' already registered"
                    toast_until = now + 3.0
                    print(f"[Voice] '{name}' already known.")
                else:
                    pending_voice_name = name
                    pending_since      = now
                    toast_text  = f"Voice intro: '{name}' — capturing face..."
                    toast_until = now + 4.0
                    print(f"[Voice] New person detected: '{name}' — will register on next close frame")
            else:
                # Not an intro — could be a note for the identified person
                # (only if someone is actively identified in frame)
                identified_now = [t for t in tracks.values() if t.identity]
                if identified_now and len(text.split()) > 2:
                    closest = max(identified_now, key=lambda t: t.proximity(720))
                    add_note(closest.identity, text, source="voice-auto")
                    toast_text  = f"Note logged for {closest.identity}: \"{text[:40]}\""
                    toast_until = now + 3.0

        if not paused:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue
            last_frame = frame.copy()
        else:
            frame = last_frame if last_frame is not None else np.zeros((720,1280,3),np.uint8)

        fh, fw = frame.shape[:2]

        # ── YOLO detection ─────────────────────────────────────────────────────
        detected = []
        if YOLO_MODEL and not paused:
            for r in YOLO_MODEL(frame, verbose=False, classes=[0]):
                for box in r.boxes:
                    if float(box.conf) > 0.35:
                        detected.append(tuple(int(v) for v in box.xyxy[0].tolist()))

        # ── IoU tracking ───────────────────────────────────────────────────────
        matched = {}
        used = set()
        for bbox in detected:
            best_s, best_id = 0.28, None
            for tid, t in tracks.items():
                if tid in used or not t.bbox: continue
                s = iou(bbox, t.bbox)
                if s > best_s: best_s, best_id = s, tid
            if best_id is not None:
                matched[best_id] = bbox; used.add(best_id)
            else:
                tracks[next_id] = Track(next_id)
                matched[next_id] = bbox
                next_id += 1

        for tid in list(tracks): 
            if tid not in matched: del tracks[tid]
        for tid, bbox in matched.items():
            tracks[tid].bbox = bbox
            tracks[tid].frames += 1

        # ── Auto-register from voice (capture first close unknown person) ──────
        if pending_voice_name and (now - pending_since) < 8.0:
            close_unknown = [t for t in tracks.values()
                             if t.close(fh) and not t.identity]
            if close_unknown:
                target = max(close_unknown, key=lambda t: t.proximity(fh))
                if register_face(pending_voice_name, frame, source="voice"):
                    target.identity   = pending_voice_name
                    target.confidence = 0.95
                    toast_text  = f"✓ Registered '{pending_voice_name}' via voice!"
                    toast_until = now + 5.0
                    for pkl in FACES_DIR.glob("*.pkl"): pkl.unlink()
                pending_voice_name = None
        elif pending_voice_name and (now - pending_since) >= 8.0:
            # Timeout — person didn't come close enough
            toast_text  = f"Timeout: '{pending_voice_name}' not close enough."
            toast_until = now + 3.0
            pending_voice_name = None

        # ── DeepFace per-track ─────────────────────────────────────────────────
        primary_id = None
        best_prox  = 0.0

        for tid, t in tracks.items():
            if not t.bbox: continue
            x1,y1,x2,y2 = t.bbox
            prox = t.proximity(fh)

            # Identity
            if (DEEPFACE_OK and t.close(fh) and face_db_names()
                    and (now - t.last_id_check) > IDENTIFY_INTERVAL):
                t.last_id_check = now
                try:
                    crop = frame[max(0,y1):y2, max(0,x1):x2]
                    if crop.size:
                        res = DeepFace.find(crop, db_path=str(FACES_DIR),
                                            enforce_detection=False, silent=True)
                        if res and not res[0].empty:
                            row = res[0].iloc[0]
                            t.identity   = Path(row["identity"]).stem
                            t.confidence = float(1.0 - min(1.0, row.get("distance", 0.5)))
                            touch_last_seen(t.identity)
                except Exception:
                    pass

            # Emotion
            if (DEEPFACE_OK and t.close(fh)
                    and (now - t.last_emo_check) > EMOTION_INTERVAL):
                t.last_emo_check = now
                try:
                    crop = frame[max(0,y1):y2, max(0,x1):x2]
                    if crop.size:
                        res = DeepFace.analyze(crop, actions=["emotion"],
                                               enforce_detection=False, silent=True)
                        if res:
                            t.emotion = res[0].get("dominant_emotion","").capitalize()
                except Exception:
                    pass

            if t.identity and prox > best_prox:
                best_prox  = prox
                primary_id = t.identity

        # ── Draw ──────────────────────────────────────────────────────────────
        display = frame.copy()

        for tid, t in tracks.items():
            if not t.bbox: continue
            x1,y1,x2,y2 = t.bbox
            is_close = t.close(fh)
            color = C_GREEN if t.identity else (C_CYAN if is_close else C_UNKNOWN)

            glow_rect(display, x1, y1, x2, y2, color)
            corners(display, x1, y1, x2, y2, color)
            pill(display, f"ID:{tid:03d}", x1, y1-8, color)

            if t.identity:
                pill(display, f"  {t.identity.upper()}  ", x1, y1-26, C_GREEN, fs=0.50)
                pill(display, f"{t.confidence:.0%}", x2-62, y1-8, (140,210,140), fs=0.32)

            if t.emotion and is_close:
                pill(display, f"EMOTION: {t.emotion.upper()}", x1, y2+18, (80,210,200), fs=0.34)

            # Scanning pulse
            if is_close and not t.identity:
                if int(now*2)%2:
                    pill(display, "SCANNING...", x1, y2+34, C_CYAN, fs=0.34)

            # Proximity arc
            if t.bbox:
                prox = t.proximity(fh)
                arc_cx = (x1+x2)//2
                arc_cy = y2+22
                r = max(18, int(prox*48))
                ang = int(prox*270)
                if ang > 0:
                    cv2.ellipse(display,(arc_cx,arc_cy),(r,r//3),-90,0,ang,color,1,cv2.LINE_AA)

        # Pending voice name indicator
        if pending_voice_name:
            pill(display, f"VOICE: Waiting for '{pending_voice_name}' to step close...",
                 10, fh//2, C_GOLD, fs=0.48)

        # Side card
        if primary_id:
            pt = next((t for t in tracks.values() if t.identity==primary_id), None)
            if pt:
                side_card(display, primary_id, pt.emotion or "Unknown",
                          pt.confidence, fw, fh)

        # HUD
        hud_header(display, fw, fh, len(tracks),
                   [t.identity for t in tracks.values() if t.identity],
                   mic.status if SR_OK else "disabled")

        # Toast
        if now < toast_until and toast_text:
            voice_toast(display, toast_text, fw, fh)

        # Bottom hint
        ov = display.copy()
        cv2.rectangle(ov,(0,fh-26),(fw,fh),(6,8,16),-1)
        cv2.addWeighted(ov,0.8,display,0.2,0,display)
        hint = "R:Register | L:Log Note | M:Mic Toggle | SPACE:Pause | Q:Quit"
        cv2.putText(display, hint, (fw//2-235, fh-10), FONT, 0.35, (70,90,120), 1, cv2.LINE_AA)

        cv2.imshow("Cortexium 2.0 — Live Recognizer", display)

        # ── Keys ──────────────────────────────────────────────────────────────
        key = cv2.waitKey(1) & 0xFF

        if key in (ord('q'), 27):
            break

        elif key == ord(' '):
            paused = not paused
            print(f"[Cortexium] {'PAUSED' if paused else 'RESUMED'}")

        elif key == ord('m'):
            if SR_OK:
                mic.toggle()
                print(f"[Mic] {'Muted' if not mic.enabled else 'Unmuted'}")

        elif key == ord('r'):
            # Manual register
            close_tracks = [t for t in tracks.values() if t.bbox]
            if close_tracks:
                target = max(close_tracks, key=lambda t: t.bbox[3]-t.bbox[1])
                cv2.destroyAllWindows()
                name = input("\n  Enter name to register: ").strip().title()
                if name:
                    if register_face(name, frame, source="manual"):
                        target.identity   = name
                        target.confidence = 1.0
                        toast_text  = f"Registered '{name}' manually."
                        toast_until = time.time() + 4.0
                cv2.namedWindow("Cortexium 2.0 — Live Recognizer", cv2.WINDOW_NORMAL)

        elif key == ord('l'):
            if primary_id:
                cv2.destroyAllWindows()
                note = input(f"\n  Note for [{primary_id}]: ").strip()
                if note:
                    add_note(primary_id, note, source="manual")
                    toast_text  = f"Note saved for {primary_id}"
                    toast_until = time.time() + 3.0
                cv2.namedWindow("Cortexium 2.0 — Live Recognizer", cv2.WINDOW_NORMAL)
            else:
                print("[!] No identified person visible.")

    mic.running = False
    cap.release()
    cv2.destroyAllWindows()
    print("\n[Cortexium] Session ended.")


if __name__ == "__main__":
    main()
