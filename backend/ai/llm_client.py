"""
Cortexium 2.0 — LLM + VLM Client (Multi-Provider with Cascade Fallback)
=========================================================================
Text LLM fallback chain:
    1. Mistral AI  (mistral-small-latest)  — ~400 ms, primary
    2. Hugging Face Inference API          — backup if Mistral is down
    3. Rule-based regex                    — always-available offline safety net

Vision (VLM) handling:
    ┌──────────────────────────────────────────────────────┐
    │  YOLOv8 (local)  ←── always running, real-time      │
    │  DeepFace ArcFace (local) ←── face ID, never cloud  │
    │  VLMClient (HF API) ←── optional rich descriptions  │
    └──────────────────────────────────────────────────────┘
    VLM only adds scene-level text descriptions. Face identity
    matching is ALWAYS DeepFace-local, never sent to any API.

All existing callers (audio.py, agents.py, persons.py, summary_manager.py)
are unchanged — same singleton interface as before.
"""
import os
import re
import json
import base64
import asyncio
import httpx
import cv2
import numpy as np
from pathlib import Path
from dotenv import load_dotenv

# ── Pin .env load to project root (2 levels up from this file) ───────────────
# This works regardless of what CWD is when the process starts.
_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=False)
print(f"[LLMClient] Loaded .env from: {_ENV_PATH} (exists={_ENV_PATH.exists()})")

# ── Name extraction regex patterns (offline fallback) ────────────────────────
_NAME_PATTERNS = [
    r"(?:hello|hey|hi)?\s*(?:my name is|i am|i'm|call me|this is|meet|introducing|myself)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)",
    r"^([a-zA-Z]+(?:\s+[a-zA-Z]+)?)\s+here$",
    r"^([a-zA-Z]+(?:\s+[a-zA-Z]+)?),?\s+(?:nice to|good to|pleasure)",
]


def _get_env(key: str, default: str = "") -> str:
    """
    Read an env var at call-time (not at module import time).
    This guarantees we always get the value AFTER load_dotenv() has run,
    even if this module was imported before the env was fully loaded.
    """
    return os.getenv(key, default)

# ── Provider health state (module-level, shared across instances) ─────────────
_provider_health: dict[str, bool] = {
    "mistral":     True,   # assume online until proven otherwise
    "huggingface": True,
}
_COOL_DOWN_SEC = 60.0   # seconds before retrying a failed provider


def _clean_llm_output(text: str) -> str:
    """Strip <think> tags and stray markdown fences from any LLM output."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"^```(?:json)?\s*|```$", "", text, flags=re.MULTILINE)
    return text.strip()


# ════════════════════════════════════════════════════════════════════════════
#  Provider-level call helpers
# ════════════════════════════════════════════════════════════════════════════

async def _call_mistral(
    messages: list[dict],
    model: str = "mistral-small-latest",
    max_tokens: int = 250,
    timeout: float = 3.0,
    api_key: str = "",
) -> str | None:
    """Call Mistral AI via OpenAI-compatible /v1/chat/completions."""
    if not api_key:
        return None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            if r.status_code == 200:
                content = r.json()["choices"][0]["message"]["content"]
                _provider_health["mistral"] = True
                return _clean_llm_output(content)
            else:
                print(f"[LLM/Mistral] HTTP {r.status_code}: {r.text[:200]}")
    except httpx.TimeoutException:
        print(f"[LLM/Mistral] Timeout after {timeout}s")
    except Exception as e:
        print(f"[LLM/Mistral] Error: {e}")

    _provider_health["mistral"] = False
    return None


async def _call_huggingface(
    messages: list[dict],
    model: str | None = None,
    max_tokens: int = 250,
    timeout: float = 3.0,
    api_key: str = "",
) -> str | None:
    """
    Call HF Inference API.
    Tries OpenAI-compat endpoint first (/v1/chat/completions), falls back to
    the raw text-generation endpoint if the model doesn't support it.
    """
    if not api_key:
        return None
    hf_model = model or "mistralai/Mistral-7B-Instruct-v0.3"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    base = f"https://api-inference.huggingface.co/models/{hf_model}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # ── Try OpenAI-compat endpoint ────────────────────────────────────
            r = await client.post(
                f"{base}/v1/chat/completions",
                headers=headers,
                json={
                    "model": hf_model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": 0.2,
                },
            )
            if r.status_code == 200:
                content = r.json()["choices"][0]["message"]["content"]
                _provider_health["huggingface"] = True
                return _clean_llm_output(content)

            if r.status_code == 503:
                # Model is loading — HF cold-start, wait briefly and retry once
                print("[LLM/HF] Model loading (503), retrying in 3s…")
                await asyncio.sleep(3)
                r = await client.post(
                    f"{base}/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": hf_model,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": 0.2,
                    },
                )
                if r.status_code == 200:
                    content = r.json()["choices"][0]["message"]["content"]
                    _provider_health["huggingface"] = True
                    return _clean_llm_output(content)

            # ── Fallback: raw text-generation API ─────────────────────────────
            prompt_text = "\n".join(
                f"{'System' if m['role'] == 'system' else 'User'}: {m['content']}"
                for m in messages
            ) + "\nAssistant:"

            r2 = await client.post(
                base,
                headers=headers,
                json={
                    "inputs": prompt_text,
                    "parameters": {
                        "max_new_tokens": max_tokens,
                        "temperature": 0.2,
                        "return_full_text": False,
                    },
                },
            )
            if r2.status_code == 200:
                result = r2.json()
                if isinstance(result, list) and result:
                    text = result[0].get("generated_text", "").strip()
                    _provider_health["huggingface"] = True
                    return _clean_llm_output(text)

            print(f"[LLM/HF] HTTP {r2.status_code}: {r2.text[:200]}")

    except httpx.TimeoutException:
        print(f"[LLM/HF] Timeout after {timeout}s")
    except Exception as e:
        print(f"[LLM/HF] Error: {e}")

    _provider_health["huggingface"] = False
    return None


# ════════════════════════════════════════════════════════════════════════════
#  LLM Client — cascade fallback: Mistral → HF → rule-based
# ════════════════════════════════════════════════════════════════════════════

class LLMClient:
    """
    Text LLM with automatic cascade fallback.

    Call order:
      1. Primary provider (from LLM_PROVIDER env, default: mistral)
      2. Backup provider  (the other one: mistral ↔ huggingface)
      3. Rule-based regex (always available, no network needed)

    If a provider recovers, it's automatically used again on the next request
    (cool-down period: 60 s).
    """

    def __init__(self):
        # Read keys at instantiation time — after load_dotenv() has run
        self.primary      = _get_env("LLM_PROVIDER", "mistral").lower()
        self.backup       = "huggingface" if self.primary == "mistral" else "mistral"
        self.model        = _get_env("LLM_MODEL", "mistral-small-latest")
        self._mistral_key = _get_env("MISTRAL_API_KEY", "")
        self._hf_key      = _get_env("HF_API_KEY", "")
        self._hf_llm_model= _get_env("HF_LLM_MODEL", "mistralai/Mistral-7B-Instruct-v0.3")
        self._last_fail: dict[str, float] = {}  # provider → timestamp of last failure

        print(
            f"[LLMClient] Primary: {self.primary.upper()} ({self.model}) | "
            f"Backup: {self.backup.upper()}"
        )
        if not self._mistral_key:
            print("[LLMClient] [!] MISTRAL_API_KEY not set - check .env")
        else:
            print(f"[LLMClient] [OK] Mistral key loaded ({self._mistral_key[:12]}...)")
        if not self._hf_key:
            print("[LLMClient] [!] HF_API_KEY not set - check .env")
        else:
            print(f"[LLMClient] [OK] HF key loaded ({self._hf_key[:12]}...)")

    def _is_cooling_down(self, provider: str) -> bool:
        import time
        last = self._last_fail.get(provider, 0.0)
        return (time.time() - last) < _COOL_DOWN_SEC

    def _mark_failed(self, provider: str):
        import time
        self._last_fail[provider] = time.time()
        _provider_health[provider] = False

    async def _dispatch(
        self,
        messages: list[dict],
        max_tokens: int = 250,
        timeout: float = 6.0,
    ) -> str | None:
        """Try primary → backup, respecting cool-down windows."""
        for provider in [self.primary, self.backup]:
            if self._is_cooling_down(provider):
                continue

            if provider == "mistral":
                # Pass the instance key (read at __init__ time, after dotenv loaded)
                result = await _call_mistral(messages, self.model, max_tokens, timeout, api_key=self._mistral_key)
            elif provider == "huggingface":
                result = await _call_huggingface(messages, self._hf_llm_model, max_tokens, timeout, api_key=self._hf_key)
            else:
                continue

            if result is not None:
                # Provider recovered — clear cool-down
                self._last_fail.pop(provider, None)
                _provider_health[provider] = True
                return result
            else:
                self._mark_failed(provider)

        return None   # both providers down → caller uses rule-based fallback

    async def generate_response(self, prompt: str, system_prompt: str = "") -> str:
        """Main LLM call — used by agents.py, audio.py, persons.py."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        result = await self._dispatch(messages, max_tokens=250, timeout=6.0)
        if result:
            return result

        print("[LLMClient] Both providers failed — using rule-based fallback")
        return self._fallback_response(prompt)

    async def generate_summary(self, person_name: str, transcript_lines: list) -> str:
        """
        Session summarization — used by summary_manager.py and persons.py.
        Returns empty string on full failure so caller uses its rule-based fallback.
        """
        lines = transcript_lines[:15]
        numbered = "\n".join(f"{i+1}. {l}" for i, l in enumerate(lines))

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a conversation summarizer. Write a clear 2-3 sentence "
                    "summary in natural English. Rules: plain English only — no JSON, "
                    "no bullet points, no markdown. Write in third person. "
                    "Do not start with 'Summary:'. Maximum 300 characters."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Transcript of what {person_name} said:\n{numbered}\n\n"
                    "Write a 2-3 sentence plain-English summary:"
                ),
            },
        ]
        result = await self._dispatch(messages, max_tokens=300, timeout=12.0)
        if result and len(result) >= 10 and not result.strip().startswith("{"):
            return result[:400]
        return ""

    def _fallback_response(self, prompt: str) -> str:
        """Rule-based name/intent extraction — works fully offline."""
        text = prompt.lower()
        for pattern in _NAME_PATTERNS:
            m = re.search(pattern, prompt, re.IGNORECASE)
            if m:
                raw_name = m.group(1).strip().title()
                if raw_name.lower() not in ("a radio", "the radio", "a car", "radio", "something", "a test"):
                    return json.dumps({
                        "name": raw_name,
                        "intent": "greeting",
                        "confidence": 0.85,
                    })
        if any(w in text for w in ("where", "navigate", "go to", "direction", "route")):
            return json.dumps({"name": None, "intent": "navigation", "confidence": 0.7})
        return json.dumps({"name": None, "intent": "other", "confidence": 0.0})

    @property
    def status(self) -> dict:
        mistral_ok = bool(self._mistral_key) and not self._is_cooling_down("mistral")
        hf_ok      = bool(self._hf_key)      and not self._is_cooling_down("huggingface")

        if mistral_ok and self.primary == "mistral":
            active = "mistral-api"
        elif hf_ok:
            active = "huggingface-api"
        else:
            active = "rule-based-fallback"

        return {
            "mode":              active,
            "primary_provider":  self.primary,
            "backup_provider":   self.backup,
            "model":             self.model,
            "mistral_key":       bool(self._mistral_key),
            "hf_key":            bool(self._hf_key),
            "mistral_healthy":   not self._is_cooling_down("mistral"),
            "hf_healthy":        not self._is_cooling_down("huggingface"),
            "provider_health":   dict(_provider_health),
        }

    # Backward-compat — called by agents.py /llm/status endpoint
    async def _check_ollama(self) -> bool:
        """Pings primary provider to check reachability. Name kept for compat."""
        result = await self._dispatch(
            [{"role": "user", "content": "ping"}], max_tokens=5, timeout=6.0
        )
        return result is not None


# ════════════════════════════════════════════════════════════════════════════
#  VLM Client — Visual understanding via HF + local CV pipeline
# ════════════════════════════════════════════════════════════════════════════
#
#  How visual processing works in Cortexium:
#
#  ┌─────────────────────────────────────────────────────────────────────┐
#  │  LAYER 1 (Always Local, Real-time)                                  │
#  │   YOLOv8   → detects objects, people, hazards in every frame        │
#  │   DeepFace → identifies registered faces (ArcFace, never cloud)     │
#  │                                                                     │
#  │  LAYER 2 (Optional Cloud, On-demand)                                │
#  │   VLMClient → sends a single JPEG frame to HF Qwen2.5-VL           │
#  │               returns rich scene description, mood, suggested action │
#  │               Face identification is NEVER done here                │
#  │               Falls back gracefully if HF is unavailable            │
#  └─────────────────────────────────────────────────────────────────────┘
#
#  VLM is triggered by /api/vision/describe — NOT on every frame.
#  The caller always gets a response (either VLM or YOLOv8-based dict).
# ════════════════════════════════════════════════════════════════════════════

class VLMClient:
    """
    Optional cloud VLM for rich scene descriptions via HF Inference API.
    Face identity matching is always handled by DeepFace locally.
    """

    def __init__(self):
        # Read all config at instantiation time — after load_dotenv() has run
        self._enabled    = _get_env("VLM_ENABLED", "false").lower() == "true"
        self.provider    = _get_env("VLM_PROVIDER", "huggingface").lower()
        self.model       = _get_env("VLM_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct")
        self._hf_key     = _get_env("HF_API_KEY", "")
        self._available: bool | None = None
        self._last_fail: float = 0.0

        if self._enabled and not self._hf_key:
            print("[VLMClient] [!] VLM_ENABLED=true but HF_API_KEY not set - disabling VLM.")
            self._enabled = False
        elif self._enabled:
            print(f"[VLMClient] [OK] HF key loaded ({self._hf_key[:12]}...)")

        status = f"enabled via {self.provider}/{self.model}" if self._enabled else "disabled (using YOLOv8 + DeepFace)"
        print(f"[VLMClient] Scene VLM: {status}")

    def _in_cooldown(self) -> bool:
        import time
        return (time.time() - self._last_fail) < 45.0

    async def _check_availability(self) -> bool:
        if not self._enabled or not self._hf_key:
            self._available = False
            return False
        if self._in_cooldown():
            return False
        try:
            url = f"https://api-inference.huggingface.co/models/{self.model}"
            async with httpx.AsyncClient(timeout=6.0) as client:
                r = await client.get(url, headers={"Authorization": f"Bearer {self._hf_key}"})
                # 200 = ready, 503 = loading (still counts as available)
                self._available = r.status_code in (200, 503)
                if self._available:
                    print(f"[VLMClient] HF model reachable (status={r.status_code})")
                return self._available
        except Exception as e:
            print(f"[VLMClient] Availability check failed: {e}")
        self._available = False
        return False

    async def describe_scene(self, frame: np.ndarray, context: str = "") -> dict:
        """
        Sends a camera frame to HF Qwen2.5-VL for scene description.
        Returns a structured dict. Callers always get a response — either
        from VLM or a minimal fallback dict that triggers the CV pipeline.

        PRIVACY: Only JPEG scene frames are sent — no face embedding, no names.
        """
        if not self._enabled:
            return {"available": False, "description": None}

        if self._available is None:
            await self._check_availability()
        if not self._available:
            return {"available": False, "description": None}

        try:
            # Downscale + compress before sending to cloud (speed + cost)
            h, w = frame.shape[:2]
            if w > 640:
                scale = 640 / w
                frame = cv2.resize(frame, (640, int(h * scale)))
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 72])
            img_b64 = base64.b64encode(buf.tobytes()).decode("utf-8")

            system_prompt = (
                "You are Cortexium's Vision AI. Analyze the scene and return a JSON object:\n"
                '{"description": "1-2 sentence summary", '
                '"objects": ["list of notable objects"], '
                '"persons": ["describe visible people: appearance, expression"], '
                '"hazards": ["safety concerns"], '
                '"mood": "calm|busy|tense|social|crowded|empty", '
                '"suggested_action": "one actionable AR overlay insight"}\n'
                "Return ONLY valid JSON. No markdown. No explanation."
            )
            user_prompt = f"Analyze this scene.{' Context: ' + context if context else ''}"

            hf_base = f"https://api-inference.huggingface.co/models/{self.model}"
            headers = {
                "Authorization": f"Bearer {self._hf_key}",
                "Content-Type": "application/json",
            }

            # Try OpenAI-compat multimodal endpoint (Qwen2.5-VL supports this)
            async with httpx.AsyncClient(timeout=25.0) as client:
                r = await client.post(
                    f"{hf_base}/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {
                                "role": "user",
                                "content": [
                                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                                    {"type": "text", "text": user_prompt},
                                ],
                            },
                        ],
                        "max_tokens": 400,
                        "temperature": 0.2,
                    },
                )

                if r.status_code == 200:
                    raw = r.json()["choices"][0]["message"]["content"].strip()
                    raw = _clean_llm_output(raw)
                    if "{" in raw and "}" in raw:
                        parsed = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
                        parsed["available"] = True
                        parsed["model"] = self.model
                        self._available = True
                        return parsed

                elif r.status_code == 503:
                    print("[VLMClient] HF model still loading — will retry next call")
                    return {"available": False, "description": None}

                else:
                    print(f"[VLMClient] HF error {r.status_code}: {r.text[:200]}")

        except json.JSONDecodeError as e:
            print(f"[VLMClient] JSON parse error: {e}")
        except httpx.TimeoutException:
            print("[VLMClient] describe_scene timed out")
        except Exception as e:
            print(f"[VLMClient] describe_scene error: {e}")

        import time
        self._last_fail = time.time()
        self._available = False
        return {"available": False, "description": None}

    async def identify_person_vlm(self, frame: np.ndarray, known_persons: list[str]) -> dict:
        """
        Person identification via cloud VLM is intentionally disabled.
        DeepFace (ArcFace, local) handles all face identity matching.
        Biometric data is never transmitted to any external API.
        """
        return {"identified": False, "name": None}

    @property
    def status(self) -> dict:
        return {
            "mode":      f"vlm-{self.provider}" if (self._enabled and self._available) else "vlm-cv-fallback",
            "enabled":   self._enabled,
            "provider":  self.provider,
            "model":     self.model,
            "hf_key":    bool(self._hf_key),
            "available": self._available,
            "note":      "Face ID always via DeepFace local — no face data sent to cloud",
        }


# ── Module-level singletons ───────────────────────────────────────────────────
llm_client = LLMClient()
vlm_client = VLMClient()
