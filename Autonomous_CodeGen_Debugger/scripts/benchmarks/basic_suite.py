#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, time, subprocess, shlex
from pathlib import Path

TASKS = [
    {
        "task": "Write a function is_ipv4(s) that validates IPv4 addresses.",
        "fn": "is_ipv4",
        "signature": "def is_ipv4(s: str) -> bool",
    },
    {
        "task": "Solve quadratic a*x^2 + b*x + c = 0 and return both roots (real or complex).",
        "fn": "quad_solver",
        "signature": "def quad_solver(a: float, b: float, c: float) -> tuple[complex, complex]",
    },
    {
        "task": "Write a function is_palindrome(s) that returns True for palindromic strings.",
        "fn": "is_palindrome",
        "signature": "def is_palindrome(s: str) -> bool",
    },
]


def run_cmd(cmd: list[str], cwd: Path | None = None, timeout: int = 600) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, (proc.stdout + "\n" + proc.stderr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--python", default="python")
    ap.add_argument("--decode", default="sample")
    ap.add_argument("--candidates", type=int, default=3)
    ap.add_argument("--iters", type=int, default=3)
    ap.add_argument("--max_new_tokens", type=int, default=200)
    args = ap.parse_args()

    base = Path(__file__).resolve().parents[1]
    ok = 0
    results = []
    for i, t in enumerate(TASKS, 1):
        cmd = [
            args.python, "-m", "src.debugging_loop.debugger",
            "--task", t["task"],
            "--fn", t["fn"],
            "--signature", t["signature"],
            "--model", args.model,
            "--iters", str(args.iters), "--timeout", "180",
            "--max_new_tokens", str(args.max_new_tokens),
            "--decode", args.decode, "--candidates", str(args.candidates),
            "--profile", "copy", "--add-imports",
        ]
        start = time.time()
        rc, out = run_cmd(cmd, cwd=base)
        dur = time.time() - start
        code_present = ("===CODE BEGIN===" in out and "===CODE END===" in out)
        results.append({"task": t["task"], "fn": t["fn"], "rc": rc, "duration": dur, "code": code_present})
        ok += 1 if (rc == 0 and code_present) else 0
        print(f"[{i}/{len(TASKS)}] {t['fn']}: rc={rc} code={'yes' if code_present else 'no'} time={dur:.1f}s")

    out_path = base / "outputs" / "logs" / "benchmark_basic.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"summary": {"passed": ok, "total": len(TASKS)}, "results": results}, indent=2), encoding="utf-8")
    print(f"Saved report to {out_path}")
    return 0 if ok == len(TASKS) else 1


if __name__ == "__main__":
    raise SystemExit(main())

