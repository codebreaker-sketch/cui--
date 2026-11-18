"""Thin client for any OpenAI-compatible chat endpoint (Groq, Ollama, OpenRouter, ...).

Why it exists: one place that talks to a model and returns the token counts
*exactly as the model reports them*, so the trace never invents numbers.
"""
import json
import os
import time

import requests


def _load_env(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


_load_env()

def _env(*names, default=None):
    return next((os.environ[n] for n in names if os.environ.get(n)), default)


BASE_URL = _env("BASE_URL", "LLM_BASE_URL", default="http://localhost:11434/v1").rstrip("/")
API_KEY = _env("API_KEY", "LLM_API_KEY", default="ollama")
MODEL = _env("MODEL_NAME", "LLM_MODEL", default="qwen2.5:1.5b")
TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "90"))


class LLMError(RuntimeError):
    pass


def chat(system, user, max_tokens=400, deadline=None):
    """Returns (text, usage_dict, model_name, seconds). `deadline` = time.time() value we must finish by."""
    body = {
        "model": MODEL,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    last = None
    for attempt in range(3):
        t0 = time.time()
        left = TIMEOUT if deadline is None else min(TIMEOUT, deadline - t0)
        if left < 2:
            raise LLMError(f"time limit reached before the call could finish ({last or 'no reply yet'})")
        try:
            r = requests.post(f"{BASE_URL}/chat/completions", headers=headers,
                              data=json.dumps(body), timeout=left)
            if r.status_code == 429 or r.status_code >= 500:
                last = f"HTTP {r.status_code}: {r.text[:200]}"
                time.sleep(1.5 * (attempt + 1))
                continue
            if r.status_code != 200:
                raise LLMError(f"HTTP {r.status_code}: {r.text[:300]}")
            data = r.json()
            text = data["choices"][0]["message"]["content"] or ""
            usage = data.get("usage") or {}
            return text, {
                "prompt": usage.get("prompt_tokens"),
                "completion": usage.get("completion_tokens"),
                "total": usage.get("total_tokens"),
            }, data.get("model", MODEL), round(time.time() - t0, 2)
        except requests.RequestException as e:
            last = str(e)
            time.sleep(1)
    raise LLMError(f"model call failed after retries: {last}")
