from __future__ import annotations
from typing import Protocol


class LLMBackend(Protocol):
    name: str

    def complete(self, prompt: str, max_new_tokens: int = 160, decode: str = "greedy") -> str:
        ...

