# Issues & Resolutions Log (v1 → v2)

This document tracks known issues, decisions, and their resolution status. Update the Status column to “Finished” with a brief note when addressed.

## Legend
- Status: Open | In Progress | Finished | Deferred
- Area: UI | CLI | Core | Security | Models | Docs | Performance | Eval

## Tracker

| ID | Title | Area | Summary | Plan | Status |
|----|-------|------|---------|------|--------|
| 001 | Clear button error | UI | `st.experimental_rerun()` caused exception on clear | Use session_state to reset inputs; show success toast | Finished |
| 002 | Output mode hidden until Run | UI | Mode radio appeared only after clicking Run | Move control to sidebar; persist via `session_state` | Finished |
| 003 | Command string missing quotes | UI | Copied command lacked proper quoting | Render with `shlex.join(cmd)` | Finished |
| 004 | Santacoder TF mismatch | Models | `SequenceSummary` import error with new Transformers | Add loader hint; recommend starcoder2‑3b or pin `transformers==4.36.2` | Finished |
| 005 | No code detected in UI output | UI | Heuristic missed function start | Print between markers `===CODE BEGIN/END===`; UI extracts | Finished |
| 006 | Function name inference | Core | Tasks without names defaulted to `solution` | Heuristics + `--fn` override; design stage proposes signature | Finished |
| 007 | Docstring examples in final output | Core | Users prefer Args/Returns only | `--clean-doc` to rewrite docstring; profiles include it | Finished |
| 008 | Imports missing (e.g., `log`) | Core | Generated code lacked required imports | `--add-imports` (function only) and `--standalone` (imports+CLI) | Finished |
| 009 | Slow first pass | Performance | Cold loads and greedy-only decode | Add `--decode sample`, `--candidates`, and `--profile fast` | Finished |
| 010 | Codex-like behavior | Core | Reduce reliance on fixed seeds | Design stage → build header/tests → best‑of‑N gen → repair loop | Finished |
| 011 | “No-test” quality | Core | `--no-test` yields stubs | Recommend sampled decode + candidates; prefer doctests | Open |
| 012 | Rich tools | Core | Only doctest used | Add adapters: pytest, coverage, mypy, ruff, bandit | Finished |
| 013 | Keep model hot | Performance | Model reload per run | Add in‑process/worker model cache; UI calls worker | Open |
| 014 | Benchmarks | Eval | No pass@k benchmark suite | Integrate HumanEval/MBPP/APPS; scripts + reports | Open |
| 015 | Security guard rails | Security | Prevent file I/O outside project | Add path guard; restrict temp dirs and output writes | Finished |
| 016 | Config paths | Docs | Hardcoded model root in docs/UI | Make configurable; document env vars | Finished |
| 017 | Backend abstraction | Core | Only local HF models supported | Add backend interface + stubs for OpenAI/Gemini (API keys) | Finished |
| 018 | API model docs | Docs | No guidance for API backends | Document env vars and model spec format in this file | Finished |
| 019 | HF backend path resolve | Core | Passing top-level model folder failed to load tokenizer | Resolve to inner snapshot with config/weights before loading | Finished |
| 020 | UI syntax error | UI | Starred conditional unpacking in tools list caused SyntaxError | Build tools list imperatively; join at the end | Finished |
| 021 | Model location guidance | Docs | Repeated permission prompts for models in Downloads | Add .env.example, support CODEGEN_MODELS_ROOT in guard, .gitignore models/ | Finished |
| 022 | Fenced code sanitized away | Core | Sanitizer dropped entire function when model emitted ``` fences | Skip fence lines instead of breaking; fallback if empty | Finished |
| 023 | UI label warning | UI | Streamlit warned about empty label on custom text_area | Add non-empty label with label_visibility | Finished |
| 024 | UI long-running runs | UI | Streamed subprocess could run indefinitely | Add user-configurable run timeout; kill process after limit | Finished |
| 025 | FastAPI worker | Infra | Model cold-start on each run | Add server/worker.py (FastAPI) to keep model hot; UI toggle to use worker | Finished |
| 026 | Spec + doctest synthesis | Core | Weak design examples caused trivial bodies | Validate/synthesize doctests; enforce non-trivial examples | Finished |
| 027 | Coverage-guided repair | Core | Branches left untested | Optional coverage-run appended to repair prompt | Finished |
| 028 | Memory hints | Core | No reuse of prior solutions | Save successful cases; inject gentle hint in prefix (opt-out flag pending) | Finished |
| 029 | Planner timeline UI | UI | Hard to follow steps | Parse PLAN lines (local) and render worker plan in panel | Finished |
| 030 | Benchmark runner | Eval | No quick evaluation harness | Add scripts/benchmarks/basic_suite.py | Finished |

### 012 – Rich tools (Finished)
- Added tool adapters under `src/tools/adapters.py` for ruff, mypy, bandit, coverage (doctest), pytest.
- New CLI flags in debugger: `--tools`, `--tools-on-each-iter`, `--early-stop-on-tools`, `--planner`, `--save-run`.
- UI toggles added under “Tools” and “Planner & Logs”; command preview updated automatically.
- Tool results are included in the plan/events and saved to `outputs/logs/run_*.json` when `--save-run` is set.

## Notes
- When resolving an issue, include a short note with commit hash and date.
- Security guard rails require configuration if models reside outside the repo (see below).

### Security Guard Rails
- The agent now blocks read/write outside the project root by default.
- To allow model reads from a specific directory, set an allowlist:
  - `export CODEGEN_ALLOWED_READ_ROOTS="/absolute/path/to/models:/another/dir"`
- Writes are restricted to the project root (you may expand via `CODEGEN_ALLOWED_WRITE_ROOTS`).
- All sandbox temp files are created under `outputs/.sandbox/` inside the project root.

### Model Backends & API Keys
- Local (default): pass a filesystem path to a HF snapshot (contains `config.json` and weights). Example: `--model /path/to/starcoder2-3b`
- OpenAI (planned): model spec like `--model openai:gpt-4o-mini` with `OPENAI_API_KEY` set. Requires network access and API client implementation.
- Gemini (planned): model spec like `--model gemini:gemini-1.5-flash` with `GOOGLE_API_KEY` (or `GEMINI_API_KEY`) set. Requires network access and API client implementation.

Environment variables:
- `CODEGEN_MODELS_ROOT` — default models root for the UI model picker.
- `OPENAI_API_KEY` — enables OpenAI backend (when implemented).
- `GOOGLE_API_KEY`/`GEMINI_API_KEY` — enables Gemini backend (when implemented).

Implementation status:
- Backend interface added (`src/backends/base.py`).
- Local HF backend implemented (`src/backends/hf.py`).
- OpenAI/Gemini stubs added with helpful errors (`src/backends/openai_stub.py`).
- Backend selection by model spec (`src/backends/select.py`); debugger uses this selector.


```text
Me: I shared this project with one of the industry professional and he said it is very basic project in the domain of Agentic AI. I dont understand why? And how can I improve this project to catch everyones attention?


Codex Answer: Short answer: it’s called “basic” because it’s a single‑loop, single‑agent function fixer. It’s good engineering, but missing the hallmarks of more advanced, agentic systems: planning, tool selection, memory, richer evaluation, and production‑grade polish.

What “basic” means here

Single loop: Generate → doctest → repair. No explicit planner or multi‑step strategy beyond that loop.
One tool, one modality: Only doctest. No static analysis, coverage, fuzzing, types, lint, or security tools.
No memory: The agent doesn’t remember prior attempts, reusable fixes, or task patterns.
No dynamic tool choice: It doesn’t choose tools based on errors or goals; the path is fixed.
Narrow scope: Mostly single functions; not multi‑file refactors or repo‑level tasks.
Limited evaluation: A small internal suite, no recognized benchmarks or pass@k metrics.
Performance: Cold model loads, no model server/caching; purely local inference.
Packaging/ops: Not yet a reusable SDK/worker with APIs, CI, telemetry, or a VS Code extension.
How to elevate it (high‑leverage upgrades)

Agentic architecture
Planner + state machine: Introduce an explicit plan graph (e.g., DesignSpec → Generate → Test → Analyze → Repair → Refactor). Keep state and decisions visible.
Multi‑agent roles: Writer, Tester, Critic/Security Reviewer. Use debate/self‑consistency to improve reliability.
Dynamic toolbelt
Tests: pytest runner, property‑based fuzzing (hypothesis), mutation testing (mutmut), coverage (coverage.py) with coverage‑guided repair.
Static checks: mypy (types), ruff/flake8 (lint), bandit (security), pydocstyle (docs).
Policy tools: Forbidden APIs, network/file access policies with actionable remediation prompts.
Optional: doc search/RAG over local docs to inform fixes (fully offline if needed).
Memory and retrieval
Experience DB: Store tasks, failing traces, final fixes, and short “lessons learned”.
Retrieval‑augmented prompting: Pull similar past fixes to guide new repairs and to propose tests/spec.
Prompt cache: Reuse stable prompts and successful snippets to reduce latency and variance.
Spec and test synthesis
Automated spec: First generate a brief spec and API contract from the task; ask clarifying questions when underspecified.
Test generation: Ask the model to draft N tests; auto‑minimize to essential cases; add coverage targets; regenerate tests for uncovered branches.
Strong evaluation and reporting
Benchmarks: Integrate HumanEval/MBPP/APPS. Report pass@1/pass@k with confidence intervals.
Leaderboard: Track models, decoding presets, and candidate counts across benchmarks; publish results and reproducible commands.
Telemetry: Time per stage, #repairs, tool calls, coverage deltas; export to JSON and simple dashboard.
Performance and infra
Keep the model hot: Switch Streamlit to call an in‑process loop or a local FastAPI worker that holds the tokenizer/model.
Inference server: vLLM/TGI for faster decoding and best‑of‑N sampling.
Decoding strategies: Self‑consistency (sampled) with early stopping when a candidate passes; optional ToT/MCTS for harder tasks.
Developer experience and polish
Package as a library + CLI: pyproject.toml, pre‑commit hooks, type hints across code.
Config: .env or YAML profiles for model path, defaults, and tool policies.
CI: GitHub Actions to run a small regression suite and lint/type checks on PRs.
VS Code extension: “Generate/Repair” command, in‑editor diff view, and run tests.
Safety and guardrails
Stronger sandboxing (seccomp, reduced syscall surface on Linux).
Error classification: runtime vs. logic vs. policy; route to appropriate toolchain (e.g., fix imports vs. rewrite algorithm).
Red team prompts: Prevent file/network misuse and prompt‑injection inside stack traces.
A pragmatic, attention‑worthy roadmap

Phase 1 (1–2 weeks): Quick wins that show sophistication

Add pytest, coverage, mypy, ruff, bandit tool adapters; expose them as selectable tools (flags and UI toggles).
Add “Planner mode” (graph of steps) with an event log; display plan and decisions in UI.
Add best‑of‑N + sampled decoding and early stop on first pass; cache final code and logs to JSON.
Keep model hot in a lightweight worker (FastAPI) and switch UI to call it.
Phase 2 (2–4 weeks): Autonomy and reliability

Spec + test synthesis: “Design” generates spec/tests; “Tester” runs pytest; “Critic” summarizes; “Writer” repairs.
Coverage‑guided repair: Use coverage.py to highlight missed branches; update tests and code iteratively.
Memory: Vector store of “error → fix” exemplars; retrieve similar cases into repair prompts.
Phase 3 (4–6 weeks): Benchmarks and showcase

Add HumanEval/MBPP/APPS scripts; run pass@k across models/presets; publish results, charts, and reproducible commands.
Deliver a polished demo repo: clickable UI, presets for popular tasks, short videos/GIFs.
VS Code extension preview: context menu to generate/repair function; status log pane.
Concrete tasks you can do next

Add adapters: pytest, coverage, mypy, ruff, bandit; add flags and UI toggles to run them; surface findings in the “Thinking” pane.
Implement a plan graph: simple JSON/YAML state machine; each node writes events (start, result, decision) to logs; UI renders a mini timeline.
Worker process: small FastAPI with a single /run endpoint that holds the model; switch UI to use it; measure latency improvements.
Benchmark runner: scripts/benchmarks/{humaneval,mbpp}.py with pass@k; record and plot results.
What will make people take notice

Clear metrics on recognized benchmarks (pass@k with model/preset ablations).
A robust tool‑using agent that adapts its plan and tools based on failures (not just doctest).
Smooth UX: fast, hot‑loaded model; crisp logs; toggleable tools; copy/imports/standalone modes; VS Code integration.
Good storytelling: blog post or README section with design choices, results, and short demos.
If you want, I can start by:

Adding pytest + coverage + mypy/ruff/bandit hooks with flags and UI controls.
Implementing the worker process to keep the model warm and update the UI to call it.
Wiring a minimal plan graph and event log so runs are explainable and structured.
```
