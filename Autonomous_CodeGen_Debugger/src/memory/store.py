from __future__ import annotations
import json
import re
from pathlib import Path
from typing import List, Dict, Any


MEMORY_DIR = Path("outputs/memory")
MEMORY_FILE = MEMORY_DIR / "cases.jsonl"


def _normalize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9_]+", text.lower())


def save_case(task: str, fn: str, signature: str, code: str, plan: List[Dict[str, Any]] | None = None) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    rec = {
        "task": task,
        "fn": fn,
        "signature": signature,
        "code": code,
        "plan": plan or [],
        "tokens": _normalize(task),
    }
    with MEMORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def retrieve_hints(task: str, top_k: int = 2) -> List[Dict[str, Any]]:
    if not MEMORY_FILE.exists():
        return []
    q = set(_normalize(task))
    hits: List[tuple[int, Dict[str, Any]]] = []
    with MEMORY_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            toks = set(rec.get("tokens", []))
            score = len(q & toks)
            if score:
                hits.append((score, rec))
    hits.sort(key=lambda x: x[0], reverse=True)
    return [rec for _, rec in hits[:top_k]]

