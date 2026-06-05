"""
Single-GPU coordinator.

The dev box has one 8GB GPU shared by two workloads that don't fit together:
  - qwen3:8b via Ollama (~5GB resident)
  - Stable Fast 3D (~7.3GB peak)

So they must run **sequentially**. A process-wide lock serializes GPU work, and
before SF3D runs we evict the LLM from VRAM (Ollama keep_alive=0) so there's room.
Ollama transparently reloads the model on the next LLM request.
"""
import asyncio
import os
import threading

import httpx
from dotenv import load_dotenv

load_dotenv()

_GPU_LOCK = threading.Lock()


def _ollama_base() -> str:
    base = os.getenv("MODEL_URL", "http://localhost:11434/v1").rstrip("/")
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    return base.rstrip("/")


def unload_llm() -> None:
    """Best-effort: evict the Ollama model from VRAM to free room for SF3D."""
    model = os.getenv("MODEL_NAME", "")
    if not model:
        return
    try:
        httpx.post(
            f"{_ollama_base()}/api/generate",
            json={"model": model, "keep_alive": 0},
            timeout=30,
        )
    except Exception:
        pass  # Ollama may be down / remote; SF3D will still try.


class gpu_lock_sync:
    """Blocking GPU lock for thread/sync context (the SF3D runner)."""

    def __enter__(self):
        _GPU_LOCK.acquire()
        return self

    def __exit__(self, *exc):
        _GPU_LOCK.release()
        return False


class gpu_lock_async:
    """Async GPU lock for the LLM routes — waits without blocking the event loop."""

    async def __aenter__(self):
        await asyncio.to_thread(_GPU_LOCK.acquire)
        return self

    async def __aexit__(self, *exc):
        _GPU_LOCK.release()
        return False
