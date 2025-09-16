#!/usr/bin/env python3
from __future__ import annotations

import os
from typing import Any, Dict
from fastapi import FastAPI
from pydantic import BaseModel

from src.backends.select import select_backend
from src.debugging_loop.debugger import (
    _design_signature_and_doctests_backend,
    seed_prefix_header_only,
    _complete_backend,
    sanitize_to_function,
    extract_function,
    run_doctest,
    is_bad,
    _add_imports_only,
    _to_standalone,
)

app = FastAPI(title="CodeGen Worker", version="0.1.0")


class RunRequest(BaseModel):
    task: str
    fn: str | None = None
    signature: str | None = None
    doctests: str | None = None
    iters: int = 3
    timeout: int = 120
    max_new_tokens: int = 160
    decode: str = "greedy"
    candidates: int = 1
    no_design: bool = False
    no_test: bool = False
    add_imports: bool = False
    standalone: bool = False
    clean_doc: bool = False
    coverage_repair: bool = False


class RunResponse(BaseModel):
    ok: bool
    code: str
    plan: list[dict] = []
    logs: list[str] = []


MODEL_SPEC = os.getenv("CODEGEN_WORKER_MODEL") or os.getenv("CODEGEN_MODEL_PATH")
BACKEND = None


@app.on_event("startup")
def _load_backend():
    global BACKEND
    if not MODEL_SPEC:
        raise RuntimeError("Set CODEGEN_WORKER_MODEL or CODEGEN_MODEL_PATH before starting the worker")
    BACKEND = select_backend(MODEL_SPEC)


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_SPEC}


@app.post("/run", response_model=RunResponse)
def run(req: RunRequest):
    assert BACKEND is not None, "Backend not initialized"
    logs: list[str] = []
    plan: list[dict] = []

    def add_plan(tag: str, data: dict | None = None):
        evt = {"tag": tag}; evt.update(data or {})
        plan.append(evt)

    fn_name = req.fn or "solution"
    # signature/doctests
    if req.signature:
        signature = req.signature
        doctests = req.doctests
    elif not req.no_design:
        add_plan("design:start", {"fn": fn_name})
        signature, doctests = _design_signature_and_doctests_backend(
            BACKEND, req.task, fn_name, max_new_tokens=200, decode=req.decode
        )
        add_plan("design:done", {"signature": signature, "doctests_present": bool(doctests)})
    else:
        signature = f"def {fn_name}(x)"
        doctests = req.doctests

    prefix = seed_prefix_header_only(req.task, signature, doctests)
    add_plan("generate:start", {"candidates": int(req.candidates), "decode": req.decode})
    code = None
    first_result = None
    # generation loop
    for k in range(max(1, int(req.candidates))):
        gen_body = _complete_backend(BACKEND, prefix, max_new_tokens=req.max_new_tokens, decode=req.decode)
        cand = sanitize_to_function(prefix + gen_body, fn_name)
        if is_bad(cand):
            cand = extract_function(prefix + "    return False\n", fn_name)
        if req.no_test:
            code = cand
            result = {"ok": True}
            break
        res = run_doctest(cand, timeout_s=req.timeout)
        if first_result is None:
            first_result = (cand, res)
        if res.get("ok"):
            code, result = cand, res
            break
    if code is None:
        code, result = first_result
    add_plan("generate:done", {"passed_doctest": bool(result and result.get("ok"))})

    # simple repair loop (optional coverage-guided)
    i = 0
    while not req.no_test and not result.get("ok") and i < req.iters:
        i += 1
        add_plan("repair:start", {"iter": i})
        from src.error_analysis.error_parser import summarize_trace
        err = summarize_trace(result.get("traceback", ""))
        if req.coverage_repair:
            try:
                from pathlib import Path
                tmp = Path("outputs/.tools"); tmp.mkdir(parents=True, exist_ok=True)
                covp = tmp / f"{fn_name}_cov.py"
                covp.write_text(code, encoding="utf-8")
                from src.tools.adapters import run_coverage_doctest
                cov = run_coverage_doctest(covp)
                if cov and cov.get("stdout"):
                    err += "\n\n[Coverage]\n" + cov.get("stdout", "")
            except Exception:
                pass
        from src.codegen.prompts import REPAIR_PROMPT
        prompt = REPAIR_PROMPT.format(task=req.task, prev_code=extract_function(code, fn_name), error=err)
        fix = _complete_backend(BACKEND, prompt, max_new_tokens=req.max_new_tokens, decode=req.decode)
        code = sanitize_to_function(fix, fn_name)
        if is_bad(code):
            code = extract_function(prefix + "    return False\n", fn_name)
        result = run_doctest(code, timeout_s=req.timeout)
        add_plan("repair:done", {"iter": i, "ok": bool(result.get("ok"))})

    final_code = code or ""
    if req.add_imports and not req.standalone:
        final_code = _add_imports_only(final_code)
    if req.standalone:
        final_code = _to_standalone(final_code, fn_name, req.task, doctests)
    return RunResponse(ok=bool(result and result.get("ok")), code=final_code, plan=plan, logs=logs)
