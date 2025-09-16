#!/usr/bin/env python3
from __future__ import annotations
import subprocess
import sys
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent.parent

MODEL_PATH = Path('/Users/enigma/Downloads/models/starcoder2-3b')

TASKS = [
    "Write a Python function is_ipv4(s) that validates IPv4 addresses; include 3 doctests.",
    "Write a Python function is_palindrome(s) that returns True for palindromic strings; include 3 doctests.",
    "Write a Python function factorial(n) that computes n! for n>=0 and raises ValueError for negatives; include doctests.",
    "Write a Python function fibonacci(n) that returns the nth Fibonacci number (0-indexed) and raises ValueError for negatives; include doctests.",
    "Write a Python function is_prime(n) that returns True if n is prime; include doctests.",
    "Write a Python function reverse_words(s) that reverses word order; include doctests.",
    "Write a Python function sum_nested(lst) that sums all integers in a nested list; include doctests.",
    "Write a Python function balanced_parentheses(s) that checks if parentheses are balanced; include doctests.",
    "Write a Python function is_anagram(a, b) that checks for anagrams ignoring spaces and case; include doctests.",
]

def run_task(py: str, task: str) -> tuple[bool, str]:
    cmd = [
        py, "-m", "src.debugging_loop.debugger",
        "--task", task,
        "--model", str(MODEL_PATH),
        "--iters", "4",
        "--timeout", "90",
        "--max_new_tokens", "160",
    ]
    proc = subprocess.run(cmd, cwd=str(HERE), capture_output=True, text=True)
    out = proc.stdout + "\n" + proc.stderr
    m = None
    for m in re.finditer(r"\[(?:GEN-0|FIX-\d+|FALLBACK)\] pass=\s*(True|False)", out):
        pass
    ok = (m is not None and m.group(1) == "True")
    return ok, out

def main() -> int:
    py = sys.executable
    print(f"Python: {py}")
    results: list[tuple[str, bool]] = []
    for i, task in enumerate(TASKS, 1):
        print(f"\n[{i}/{len(TASKS)}] {task}")
        ok, out = run_task(py, task)
        results.append((task, ok))
        print("PASS" if ok else "FAIL")
    passed = sum(1 for _, ok in results if ok)
    print(f"\nSummary: {passed}/{len(results)} passed")
    for t, ok in results:
        print(f"- {'OK ' if ok else 'FAIL'} {t}")
    return 0 if passed == len(results) else 1

if __name__ == "__main__":
    raise SystemExit(main())

