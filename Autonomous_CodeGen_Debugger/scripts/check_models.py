#!/usr/bin/env python3
"""Lightweight verification of local HF model snapshots.

Loads AutoConfig and AutoTokenizer (no weights) for each model under
the user-provided snapshots to confirm files are present and readable.
"""

from __future__ import annotations
import sys
from pathlib import Path

MODELS = {
    'santacoder': 'models--bigcode--santacoder',
    'starcoder2-3b': 'models--bigcode--starcoder2-3b',
    'codellama-7b-instruct': 'models--codellama--CodeLlama-7b-Instruct-hf',
}

ROOT = Path('/Users/enigma/Downloads/models')

def snapshot_path(base: Path) -> Path | None:
    ref = base / 'refs' / 'main'
    if not ref.exists():
        return None
    sha = ref.read_text().strip()
    snap = base / 'snapshots' / sha
    return snap if snap.exists() else None

def main() -> int:
    print('Python:', sys.version)
    try:
        from transformers import AutoConfig, AutoTokenizer  # type: ignore
    except Exception as e:
        print('ERROR: transformers import failed:', repr(e))
        return 1

    errors: dict[str, str] = {}
    for name, rel in MODELS.items():
        base = ROOT / name / rel
        print(f"\n[{name}] base: {base}")
        snap = snapshot_path(base)
        if snap is None:
            errors[name] = 'missing refs/main or snapshot directory'
            print(f'[{name}] ERROR: missing refs/main or snapshot directory')
            continue
        print(f'[{name}] snapshot: {snap}')
        try:
            cfg = AutoConfig.from_pretrained(str(snap), local_files_only=True, trust_remote_code=True)
            print(f'[{name}] config.model_type: {getattr(cfg, "model_type", "?")}')
        except Exception as e:
            errors[name] = f'config load failed: {e}'
            print(f'[{name}] ERROR: config load failed:', e)
            continue
        try:
            tok = AutoTokenizer.from_pretrained(str(snap), local_files_only=True, trust_remote_code=True)
            print(f'[{name}] tokenizer: {tok.__class__.__name__}')
        except Exception as e:
            errors[name] = f'tokenizer load failed: {e}'
            print(f'[{name}] ERROR: tokenizer load failed:', e)

    print('\nSummary:')
    if errors:
        for k, v in errors.items():
            print(f'- {k}: {v}')
        return 2
    print('All configs/tokenizers loaded OK (weights not loaded).')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

