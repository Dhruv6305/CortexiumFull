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

# ── Common non-name words to reject ───────────────────────────────────────────
NON_NAME_WORDS = {
    "working", "good", "working good", "fine", "cool", "great", "broken",
    "test", "testing", "ready", "running", "awesome", "fun", "bad", "okay",
    "ok", "true", "false", "nothing", "everything", "here", "there", "now",
    "it", "this", "that", "something", "someone", "project", "system",
    "cortexium", "happy", "sad", "angry", "tired", "busy", "sure", "sorry",
    "going", "doing", "talking", "speaking", "listening", "trying", "looking",
    "better", "worse", "best", "fast", "slow", "alive", "online", "offline",
    "done", "finished", "started", "late", "early", "right", "wrong", "all right",
    "radio", "a radio", "the radio", "car", "a car", "the car", "model", "ai"
}

def is_valid_person_name(name: str | None, text_context: str = "") -> bool:
    """Validate that candidate string is an actual personal human name and not a phrase or adjective."""
    if not name or not isinstance(name, str):
        return False
    clean = name.strip()
    if len(clean) < 2 or len(clean) > 30:
        return False

    # Check if context is a question or status check
    lower_ctx = text_context.strip().lower()
    if lower_ctx.endswith("?") or any(lower_ctx.startswith(q) for q in (
        "is this", "is it", "are you", "are we", "can you", "what is", "how is", "does this", "do you", "how are"
    )):
        return False

    words = [w.lower() for w in clean.split()]
    if any(w in NON_NAME_WORDS for w in words):
        return False
    if clean.lower() in NON_NAME_WORDS:
        return False

    # Reject gerunds or past participles (e.g. "Working", "Tested")
    if any(w.endswith("ing") or w.endswith("ed") for w in words):
        return False

    # Must contain only alphabetic characters, hyphens or spaces
    if not re.match(r"^[A-Za-z\s\-']+$", clean):
        return False

    return True

# ── Name extraction regex patterns (offline fallback) ────────────────────────
_NAME_PATTERNS = [
    # Explicit introduction statements: "my name is Alex", "call me Sarah"
    r"(?:hello|hey|hi)?\s*,?\s*(?:my name is|call me|introducing)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)",
    # "meet [Name]" / "this is my friend [Name]"
    r"(?:meet|this is my (?:friend|colleague|partner|brother|sister))\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)",
    # "I am [Name]" only if capitalized single name at start of sentence or after greeting
    r"(?:^|\.\s+|!\s+)?(?:hello|hey|hi)?\s*,?\s*(?:i am|i'm)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b(?:\s*[,.!]|$)",
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
    "mistral":     True,
    "groq":        True,
    "huggingface": True,
}
_session_disabled_providers: set[str] = set()
_COOL_DOWN_SEC = 60.0   # seconds before retrying a failed provider

# Persistent HTTP clients per provider with connection pooling & separate connect/read timeouts
_provider_clients: dict[str, httpx.AsyncClient] = {}

def _get_provider_client(provider: str) -> httpx.AsyncClient:
    client = _provider_clients.get(provider)
    if client is None or client.is_closed:
        # Separate longer connect timeout (10.0s) from read timeout (12.0s)
        timeout_config = httpx.Timeout(read=12.0, connect=10.0, write=10.0, pool=10.0)
        limits_config = httpx.Limits(max_keepalive_connections=5, max_connections=10, keepalive_expiry=30.0)
        client = httpx.AsyncClient(timeout=timeout_config, limits=limits_config)
        _provider_clients[provider] = client
    return client


def _clean_llm_output(text: str) -> str:
    """Strip <think> tags and stray markdown fences from any LLM output."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"^```(?:json)?\s*|```$", "", text, flags=re.MULTILINE)
    return text.strip()


# ════════════════════════════════════════════════════════════════════════════
#  Provider-level call helpers (with 1-retry backoff for transient errors)
# ════════════════════════════════════════════════════════════════════════════

async def _call_mistral(
    messages: list[dict],
    model: str = "open-mistral-7b",
    max_tokens: int = 250,
    timeout: float = 6.0,
    api_key: str = "",
) -> str | None:
    """Call Mistral AI via /v1/chat/completions."""
    if not api_key or "mistral" in _session_disabled_providers:
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
    url = "https://api.mistral.ai/v1/chat/completions"
    call_timeout = httpx.Timeout(read=timeout, connect=10.0, write=10.0, pool=10.0)

    for attempt in range(2):
        try:
            client = _get_provider_client("mistral")
            r = await client.post(url, headers=headers, json=payload, timeout=call_timeout)
            if r.status_code == 200:
                content = r.json()["choices"][0]["message"]["content"]
                _provider_health["mistral"] = True
                return _clean_llm_output(content)
            elif r.status_code in (401, 402):
                reason = "payment required / no credits" if r.status_code == 402 else "unauthorized"
                if "mistral" not in _session_disabled_providers:
                    _session_disabled_providers.add("mistral")
                    print(f"[LLM/Mistral] HTTP {r.status_code} ({reason}) — disabling provider for remainder of session")
                _provider_health["mistral"] = False
                return None
            elif r.status_code in (429, 503) and attempt == 0:
                print(f"[LLM/Mistral] HTTP {r.status_code} on attempt 1. Retrying in 1.0s...")
                await asyncio.sleep(1.0)
                continue
            else:
                err_msg = ""
                try:
                    err_obj = r.json()
                    err_msg = err_obj.get("message") or err_obj.get("error", {}).get("message") or str(err_obj)
                except Exception:
                    err_msg = r.text[:120]
                print(f"[LLM/Mistral] HTTP {r.status_code}: {err_msg}")
                break
        except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as e:
            exc_desc = f"{type(e).__name__}" + (f": {e}" if str(e).strip() else "")
            if attempt == 0:
                print(f"[LLM/Mistral] Transient connection issue ({exc_desc}). Retrying in 1.0s...")
                await asyncio.sleep(1.0)
                continue
            print(f"[LLM/Mistral] Error after retry ({exc_desc})")
            break
        except Exception as e:
            exc_desc = f"{type(e).__name__}" + (f": {e}" if str(e).strip() else "")
            print(f"[LLM/Mistral] Unexpected error ({exc_desc})")
            break

    _provider_health["mistral"] = False
    return None


async def _call_groq(
    messages: list[dict],
    model: str = "qwen/qwen3.8-27b",
    max_tokens: int = 250,
    timeout: float = 6.0,
    api_key: str = "",
) -> str | None:
    """Call Groq API via /openai/v1/chat/completions."""
    if not api_key or "groq" in _session_disabled_providers:
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
    url = "https://api.groq.com/openai/v1/chat/completions"
    call_timeout = httpx.Timeout(read=timeout, connect=10.0, write=10.0, pool=10.0)

    for attempt in range(2):
        try:
            client = _get_provider_client("groq")
            r = await client.post(url, headers=headers, json=payload, timeout=call_timeout)
            if r.status_code == 200:
                content = r.json()["choices"][0]["message"]["content"]
                _provider_health["groq"] = True
                return _clean_llm_output(content)
            elif r.status_code in (401, 402):
                reason = "payment required / no credits" if r.status_code == 402 else "unauthorized"
                if "groq" not in _session_disabled_providers:
                    _session_disabled_providers.add("groq")
                    print(f"[LLM/Groq] HTTP {r.status_code} ({reason}) — disabling provider for remainder of session")
                _provider_health["groq"] = False
                return None
            elif r.status_code in (429, 503) and attempt == 0:
                print(f"[LLM/Groq] HTTP {r.status_code} on attempt 1. Retrying in 1.0s...")
                await asyncio.sleep(1.0)
                continue
            else:
                err_msg = ""
                try:
                    err_obj = r.json()
                    err_msg = err_obj.get("error", {}).get("message") or err_obj.get("message") or str(err_obj)
                except Exception:
                    err_msg = r.text[:120]
                print(f"[LLM/Groq] HTTP {r.status_code}: {err_msg}")
                break
        except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as e:
            exc_desc = f"{type(e).__name__}" + (f": {e}" if str(e).strip() else "")
            if attempt == 0:
                print(f"[LLM/Groq] Transient connection issue ({exc_desc}). Retrying in 1.0s...")
                await asyncio.sleep(1.0)
                continue
            print(f"[LLM/Groq] Error after retry ({exc_desc})")
            break
        except Exception as e:
            exc_desc = f"{type(e).__name__}" + (f": {e}" if str(e).strip() else "")
            print(f"[LLM/Groq] Unexpected error ({exc_desc})")
            break

    _provider_health["groq"] = False
    return None


async def _call_huggingface(
    messages: list[dict],
    model: str = "meta-llama/Llama-3.1-8B-Instruct",
    max_tokens: int = 250,
    timeout: float = 6.0,
    api_key: str = "",
) -> str | None:
    """
    Call Hugging Face Inference API via new router endpoint.
    URL: https://router.huggingface.co/v1/chat/completions
    """
    if not api_key or "huggingface" in _session_disabled_providers:
        return None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    url = "https://router.huggingface.co/v1/chat/completions"
    call_timeout = httpx.Timeout(read=timeout, connect=10.0, write=10.0, pool=10.0)

    for attempt in range(2):
        try:
            client = _get_provider_client("huggingface")
            r = await client.post(url, headers=headers, json=payload, timeout=call_timeout)
            if r.status_code == 200:
                content = r.json()["choices"][0]["message"]["content"]
                _provider_health["huggingface"] = True
                return _clean_llm_output(content)
            elif r.status_code in (401, 402):
                reason = "payment required / no credits" if r.status_code == 402 else "unauthorized"
                if "huggingface" not in _session_disabled_providers:
                    _session_disabled_providers.add("huggingface")
                    print(f"[LLM/HF] HTTP {r.status_code} ({reason}) — disabling provider for remainder of session")
                _provider_health["huggingface"] = False
                return None
            elif r.status_code in (429, 503) and attempt == 0:
                print(f"[LLM/HF] HTTP {r.status_code} on attempt 1. Retrying in 1.0s...")
                await asyncio.sleep(1.0)
                continue
            else:
                err_msg = ""
                try:
                    err_obj = r.json()
                    err_msg = err_obj.get("error", {}).get("message") if isinstance(err_obj.get("error"), dict) else err_obj.get("error") or str(err_obj)
                except Exception:
                    err_msg = r.text[:120]
                print(f"[LLM/HF] HTTP {r.status_code}: {err_msg}")
                break
        except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as e:
            exc_desc = f"{type(e).__name__}" + (f": {e}" if str(e).strip() else "")
            if attempt == 0:
                print(f"[LLM/HF] Transient connection issue ({exc_desc}). Retrying in 1.0s...")
                await asyncio.sleep(1.0)
                continue
            print(f"[LLM/HF] Error after retry ({exc_desc})")
            break
        except Exception as e:
            exc_desc = f"{type(e).__name__}" + (f": {e}" if str(e).strip() else "")
            print(f"[LLM/HF] Unexpected error ({exc_desc})")
            break

    _provider_health["huggingface"] = False
    return None


# ════════════════════════════════════════════════════════════════════════════
#  LLM Client — cascade fallback: Mistral → Groq → HF → rule-based
# ════════════════════════════════════════════════════════════════════════════

class LLMClient:
    """
    Text LLM with automatic cascade fallback.

    Call order:
      1. Mistral AI        (from LLM_MODEL env, default: open-mistral-7b)
      2. Groq              (from GROQ_LLM_MODEL env, default: qwen/qwen3.8-27b)
      3. Hugging Face      (from HF_LLM_MODEL env, default: meta-llama/Llama-3.1-8B-Instruct)
      4. Rule-based regex  (existing offline fallback, 100% unchanged)

    If a provider recovers, it is automatically used again on future requests
    (cool-down period: 60 s).
    """

    def __init__(self):
        # Read models & keys after load_dotenv() has run
        self.primary          = _get_env("LLM_PROVIDER", "mistral").lower()
        self.model            = _get_env("LLM_MODEL", "open-mistral-7b")
        self.groq_model       = _get_env("GROQ_LLM_MODEL", "qwen/qwen3.8-27b")
        self.hf_model         = _get_env("HF_LLM_MODEL", "meta-llama/Llama-3.1-8B-Instruct")

        self._mistral_key     = _get_env("MISTRAL_API_KEY", "")
        self._groq_key        = _get_env("GROQ_API_KEY", "")
        self._hf_key          = _get_env("HF_API_KEY", "")

        # Configurable provider chain order
        chain_env = _get_env("LLM_PROVIDER_CHAIN", "mistral,groq,huggingface")
        self.chain = [p.strip().lower() for p in chain_env.split(",") if p.strip()]

        self._last_fail: dict[str, float] = {}  # provider → timestamp of last failure

        print(
            f"[LLMClient] Provider chain: {' -> '.join(p.upper() for p in self.chain)} -> OFFLINE FALLBACK | "
            f"Mistral model: {self.model} | Groq model: {self.groq_model}"
        )
        print(f"[LLMClient] Mistral key: {'loaded' if self._mistral_key else 'missing'}")
        print(f"[LLMClient] Groq key: {'loaded' if self._groq_key else 'missing'}")
        print(f"[LLMClient] HF key: {'loaded' if self._hf_key else 'missing'}")

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
        """Try Mistral → Groq → HF in order, respecting cool-down windows and session-disabled providers."""
        for provider in self.chain:
            if provider in _session_disabled_providers:
                continue
            if self._is_cooling_down(provider):
                continue

            result = None
            if provider == "mistral":
                result = await _call_mistral(messages, self.model, max_tokens, timeout, api_key=self._mistral_key)
            elif provider == "groq":
                result = await _call_groq(messages, self.groq_model, max_tokens, timeout, api_key=self._groq_key)
            elif provider == "huggingface":
                result = await _call_huggingface(messages, self.hf_model, max_tokens, timeout, api_key=self._hf_key)

            if result is not None:
                # Provider succeeded — clear cool-down
                self._last_fail.pop(provider, None)
                _provider_health[provider] = True
                return result
            else:
                self._mark_failed(provider)

        return None   # all providers down → caller uses rule-based fallback

    async def generate_response(self, prompt: str, system_prompt: str = "") -> str:
        """Main LLM call — used by agents.py, audio.py, persons.py."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        result = await self._dispatch(messages, max_tokens=250, timeout=6.0)
        if result:
            return result

        print("[LLMClient] All LLM providers failed — using rule-based fallback")
        return self._fallback_response(prompt)

    async def generate_summary(self, person_name: str, transcript_lines: list) -> str:
        """
        Session summarization — used by audio.py and summary_manager.py.
        Returns empty string on failure so caller can handle fallback.
        """
        lines = transcript_lines[:25]
        numbered = "\n".join(f"{i+1}. {l}" for i, l in enumerate(lines))

        system_instruction = (
            "You are a conversation summarizer for speech transcripts. The conversation input may contain mixed Hindi and English speech.\n"
            "Write a short summary in clear English (2 to 4 sentences) covering the topics discussed, "
            "any decisions or follow-ups, and who was mentioned.\n"
            "Rules:\n"
            "- Summarize the conversation; NEVER repeat or quote the transcript verbatim.\n"
            "- Use ONLY information present in the text. Do NOT invent details.\n"
            "- If the text is too short or meaningless to summarize, say so briefly in one sentence.\n"
            "- Plain English only — no JSON, no markdown bullet points, no prefixes like 'Summary:'."
        )

        user_content = (
            f"Transcript of conversation with {person_name}:\n{numbered}\n\n"
            "Write a 2 to 4 sentence summary in clear English:"
        )

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_content},
        ]
        result = await self._dispatch(messages, max_tokens=350, timeout=10.0)
        if result and len(result.strip()) >= 10 and not result.strip().startswith("{"):
            cleaned = result.strip().strip('"').strip("'")
            if cleaned.lower().startswith("summary:"):
                cleaned = cleaned[8:].strip()
            return cleaned[:600]
        return ""

    def _fallback_response(self, prompt: str) -> str:
        """Rule-based name/intent extraction — works fully offline."""
        text = prompt.lower()
        for pattern in _NAME_PATTERNS:
            m = re.search(pattern, prompt, re.IGNORECASE)
            if m:
                raw_name = m.group(1).strip().title()
                if is_valid_person_name(raw_name, prompt):
                    return json.dumps({
                        "name": raw_name,
                        "intent": "greeting",
                        "confidence": 0.9,
                    })
        if any(w in text for w in ("where", "navigate", "go to", "direction", "route")):
            return json.dumps({"name": None, "intent": "navigation", "confidence": 0.7})
        return json.dumps({"name": None, "intent": "other", "confidence": 0.0})

    @property
    def status(self) -> dict:
        mistral_ok = bool(self._mistral_key) and not self._is_cooling_down("mistral")
        groq_ok    = bool(self._groq_key)    and not self._is_cooling_down("groq")
        hf_ok      = bool(self._hf_key)      and not self._is_cooling_down("huggingface")

        if mistral_ok:
            active = "mistral-api"
        elif groq_ok:
            active = "groq-api"
        elif hf_ok:
            active = "huggingface-api"
        else:
            active = "rule-based-fallback"

        return {
            "mode":              active,
            "provider_chain":    self.chain,
            "mistral_model":     self.model,
            "groq_model":        self.groq_model,
            "hf_model":          self.hf_model,
            "mistral_key":       bool(self._mistral_key),
            "groq_key":          bool(self._groq_key),
            "hf_key":            bool(self._hf_key),
            "mistral_healthy":   not self._is_cooling_down("mistral"),
            "groq_healthy":      not self._is_cooling_down("groq"),
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
        print(f"[VLMClient] HF key: {'loaded' if self._hf_key else 'missing'}")

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
