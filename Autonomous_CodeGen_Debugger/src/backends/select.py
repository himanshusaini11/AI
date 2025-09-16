from __future__ import annotations
import os
from pathlib import Path
from src.backends.hf import HFBackend
from src.backends.openai_stub import OpenAIBackend, GeminiBackend


def select_backend(model_spec: str):
    # Path-based local HF model
    p = Path(model_spec)
    if p.exists():
        # Resolve to directory with config.json
        if p.is_file():
            p = p.parent
        return HFBackend(str(p))
    # API model aliases
    lower = model_spec.lower()
    if lower.startswith("openai:") or lower.startswith("gpt-"):
        return OpenAIBackend(model_spec.split(":", 1)[-1])
    if lower.startswith("gemini:") or lower.startswith("google:"):
        return GeminiBackend(model_spec.split(":", 1)[-1])
    # Default to local HF attempt
    return HFBackend(model_spec)

