# Autonomous CodeGen & Self‑Debugger (Local LLM)

Version 1.0 — a local, agentic pipeline that generates Python functions with a Hugging Face model, executes doctests in a sandbox, observes failures, and repairs the code iteratively until tests pass. Includes a Streamlit UI with copy‑/save‑friendly output modes.

## Highlights

- Model‑agnostic local inference (e.g., StarCoder2‑3B, CodeLlama‑7B‑Instruct)
- Test‑driven repair loop (doctest) in a resource‑limited sandbox
- “Design” stage to draft a function signature and examples from your natural‑language task
- Best‑of‑N initial candidates; greedy or sampled decoding
- Output modes: function only, function+imports, or full standalone script with CLI
- Streamlit UI with model picker, live logs, and copy/download of final code

## How It Works

```
+--------+        HTTP         +-------------------+      JSON      +-------------------------+
|  User  | ------------------> | Streamlit UI       | ------------>  | FastAPI Worker          |
+--------+                     | (`ui/app.py`)      |                | (`server/worker.py`)    |
                                   |                                        |
                                   | form payload                           |
                                   v                                        v
                            +--------------------------+         +----------------------------+
                            | Debugging Loop Orchestrator| <---- | Backend Selector & Models  |
                            | (`src/debugging_loop/     |        | (`src/backends/select.py`) |
                            |  debugger.py`)            |        +----------------------------+
                            |          |                |
                            |          | run doctests & |
                            |          v  tools         |
                            |   +--------------------+  |
                            |   | Tool Adapters      |  |
                            |   | (`src/tools/...`)  |  |
                            |   +--------------------+  |
                            +--------------+------------+
                                           |
                                           v
                                   +---------------+
                                   | Results & Logs|
                                   +---------------+
                                           |
                                           v
                                Streamed back to UI
```

## Repository Structure

- `src/debugging_loop/debugger.py` — main loop (design → generate → test → repair → output)
- `src/execution_sandbox/sandbox.py` — doctest runner with CPU/memory/file‑size limits
- `src/error_analysis/error_parser.py` — extracts concise error summaries
- `src/codegen/generate.py` — one‑shot generation helpers and model loader
- `src/codegen/prompts.py` — prompt templates (design/repair)
- `src/seeds/library.py` — legacy seed templates (debugger no longer depends on these by default)
- `ui/app.py` — Streamlit UI (model picker, settings, output modes)
- `scripts/check_models.py` — verifies local HF snapshots (config/tokenizer)
- `scripts/run_suite.py` — small task suite for sanity checks

## Requirements

- Python 3.10+
- Packages (typical):
  - `transformers` (4.54–4.55 tested; some older models may require 4.36)
  - `torch` (match your platform; MPS on macOS supported)
  - `huggingface_hub`, `safetensors`, `accelerate` (optional)
  - `streamlit` (for the UI)

Install via `requirements.txt` (recommended):

```
pip install -r requirements.txt
```

Known compatibility note: the `santacoder` snapshot expects an older Transformers version. If you see an error mentioning `SequenceSummary`, use `starcoder2-3b` or pin `transformers==4.36.2` for that model.

## Model Setup

Point the tool at a local model directory that contains a Hugging Face snapshot (has a `config.json` and weights):

- Environment variable: `CODEGEN_MODEL_PATH=/path/to/model`
- Or CLI flag: `--model /path/to/model`

Optional helper:

```
export HF_TOKEN=...  # your Hugging Face token
python -m src.codegen.download_models
```

## CLI Usage

Minimal (function‑only, quick):

```
python -m src.debugging_loop.debugger \
  --task "Write a Python function to find the greatest number in an array" \
  --fn max_in_list \
  --model /path/to/model \
  --profile fast
```

Test‑driven (design + repair):

```
python -m src.debugging_loop.debugger \
  --task "Write a function is_ipv4(s) that validates IPv4 addresses." \
  --fn is_ipv4 \
  --model /path/to/model \
  --iters 4 --timeout 120 --max_new_tokens 160 \
  --decode sample --candidates 3 --profile copy
```

Provide your own signature/examples (skip design):

```
python -m src.debugging_loop.debugger \
  --task "Solve a quadratic ax^2+bx+c=0 and return real roots or None." \
  --fn quad_solver \
  --signature "def quad_solver(a: float, b: float, c: float) -> tuple[float, float] | None" \
  --doctests $'>>> quad_solver(1, -3, 2)\n(1.0, 2.0)\n>>> quad_solver(1, 2, 1)\n(-1.0, -1.0)\n>>> quad_solver(1, 0, 1)\nNone' \
  --model /path/to/model --decode sample --candidates 3 --profile copy --add-imports
```

Output modes:

- Function only (default)
- Function + imports: `--add-imports`
- Standalone script (adds CLI): `--standalone`

Profiles:

- `--profile copy` → clean docstring, print‑only, no file writes, high‑level “Thinking” logs
- `--profile save` → write to `outputs/generated_code/`, show progress logs
- `--profile fast` → speed‑oriented defaults (no design, greedy, candidates=1, iters=2, smaller token budget)

Key flags:

- `--fn`, `--signature`, `--doctests`, `--no-design`, `--no-test`
- `--decode greedy|sample`, `--candidates N`, `--iters N`, `--timeout S`, `--max_new_tokens N`
- `--add-imports`, `--standalone`, `--clean-doc`

## UI (Streamlit)

Launch:

```
streamlit run Autonomous_CodeGen_Debugger/ui/app.py
```

Features:

- Model picker (scans a local models root)
- Task + optional function name, signature, examples
- Profiles (copy/save/fast), decoding, candidates, design/testing toggles
- Output modes: function only, function+imports, standalone script
- Live “Thinking” logs, shell‑escaped command preview, copy/download final code

## Evaluation

Run the small sanity suite:

```
python Autonomous_CodeGen_Debugger/scripts/run_suite.py
```

Example baseline (StarCoder2‑3B, local env): 9/9 small tasks pass.

## Tips & Troubleshooting

- Use clear function names and add 2–4 examples for best results.
- For faster runs, try `--profile fast` or lower `--iters`/`--max_new_tokens`.
- If a model fails to load with a `SequenceSummary` import error, pick `starcoder2-3b` or pin `transformers==4.36.2` for that snapshot.
- Prefer sampled decoding (`--decode sample`) and a few candidates for new/ambiguous tasks.
