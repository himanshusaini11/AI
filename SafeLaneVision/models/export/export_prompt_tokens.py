#!/usr/bin/env python3
"""Generate prompt token tensors for mobile inference."""

import json
from pathlib import Path

PROMPTS = ["pothole", "debris", "cone", "lane_block", "flood", "ice"]


def export_token_data(output: Path) -> None:
    try:
        from transformers import AutoTokenizer  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "transformers is required to export prompt tokens. Install with `pip install transformers`."
        ) from exc

    tokenizer = AutoTokenizer.from_pretrained("google/owlvit-base-patch32")
    encoded = tokenizer(PROMPTS, padding="max_length", max_length=16, return_tensors="np")

    payload = {
        "prompts": PROMPTS,
        "input_ids": encoded["input_ids"].tolist(),
        "attention_mask": encoded["attention_mask"].tolist(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2))
    print(f"Wrote prompt tokens to {output}")


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[2] / "mobile" / "src" / "pipeline" / "promptTokens.json"
    export_token_data(target)
