from __future__ import annotations
import os


class OpenAIBackend:
    name = "openai-api"

    def __init__(self, model: str):
        self.model = model
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set. Set it to enable OpenAI backend.")
        # Network use is disabled in some environments; this backend is a stub here.

    def complete(self, prompt: str, max_new_tokens: int = 160, decode: str = "greedy") -> str:
        raise RuntimeError("OpenAI backend not enabled in this environment. Implement API call and enable network to use it.")


class GeminiBackend:
    name = "gemini-api"

    def __init__(self, model: str):
        self.model = model
        key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GOOGLE_API_KEY (or GEMINI_API_KEY) is not set. Set it to enable Gemini backend.")

    def complete(self, prompt: str, max_new_tokens: int = 160, decode: str = "greedy") -> str:
        raise RuntimeError("Gemini backend not enabled in this environment. Implement API call and enable network to use it.")

