from __future__ import annotations
import os
from typing import Optional
import os, glob
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from src.security.guard import assert_read_allowed


def _resolve_model_dir(p: str) -> str:
    # If this directory already contains config.json, use it
    if os.path.isfile(os.path.join(p, "config.json")):
        return p
    # Otherwise, search for an inner snapshot that has weights or config
    hits = (
        glob.glob(os.path.join(p, "**", "model*.safetensors"), recursive=True)
        or glob.glob(os.path.join(p, "**", "pytorch_model*.bin"), recursive=True)
        or glob.glob(os.path.join(p, "**", "config.json"), recursive=True)
    )
    if not hits:
        raise FileNotFoundError(f"No model weights/config under: {p}")
    return os.path.dirname(hits[0])


class HFBackend:
    name = "hf-local"

    def __init__(self, model_path: str):
        # Resolve outer directory to actual snapshot directory
        resolved = _resolve_model_dir(model_path)
        assert_read_allowed(resolved)
        tok = AutoTokenizer.from_pretrained(resolved, trust_remote_code=True, local_files_only=True)
        model = AutoModelForCausalLM.from_pretrained(
            resolved,
            torch_dtype=torch.float16 if torch.backends.mps.is_available() else torch.float32,
            device_map="auto",
            trust_remote_code=True,
            local_files_only=True,
        )
        if tok.pad_token_id is None:
            tok.pad_token_id = tok.eos_token_id
        self.tok = tok
        self.model = model

    def complete(self, prompt: str, max_new_tokens: int = 160, decode: str = "greedy") -> str:
        tok = self.tok; model = self.model
        enc = tok(prompt, return_tensors="pt", return_attention_mask=True, add_special_tokens=True)
        enc = {k: v.to(model.device) for k, v in enc.items()}
        gen_kwargs = dict(max_new_tokens=max_new_tokens, eos_token_id=tok.eos_token_id, pad_token_id=tok.pad_token_id)
        if decode == "sample":
            gen_kwargs.update(dict(do_sample=True, temperature=0.2, top_p=0.95))
        else:
            gen_kwargs.update(dict(do_sample=False))
        with torch.no_grad():
            out = model.generate(**enc, **gen_kwargs)
        gen = out[0, enc["input_ids"].shape[1]:]
        text = tok.decode(gen, skip_special_tokens=True)
        return text
