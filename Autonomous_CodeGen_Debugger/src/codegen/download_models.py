#!/usr/bin/env python3
import os
from huggingface_hub import snapshot_download

HF_TOKEN = os.getenv("HF_TOKEN")
if not HF_TOKEN:
    raise SystemExit("Set HF_TOKEN env var first (export HF_TOKEN=...)")

MODELS = [
    ("bigcode/santacoder",        "/Users/enigma/Downloads/models/santacoder"),
    ("bigcode/starcoder2-3b",     "/Users/enigma/Downloads/models/starcoder2-3b"),
    # Uncomment if you have access on HF:
    ("codellama/CodeLlama-7b-Instruct-hf", "/Users/enigma/Downloads/models/codellama-7b-instruct"),
]

def pull(repo_id, dest):
    os.makedirs(dest, exist_ok=True)
    print(f"\n>>> Downloading {repo_id} -> {dest}")
    snapshot_download(
        repo_id=repo_id,
        cache_dir=dest,
        token=HF_TOKEN,
        revision="main",
        resume_download=True,
        local_files_only=False,
    )
    print(f"✔ Done: {repo_id}")

if __name__ == "__main__":
    for rid, path in MODELS:
        pull(rid, path)
    print("\nAll requested models downloaded.")