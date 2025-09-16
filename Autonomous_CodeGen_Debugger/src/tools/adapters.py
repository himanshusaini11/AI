from __future__ import annotations
import subprocess
import shlex
from pathlib import Path
from typing import Dict, Any, List


def _run(cmd: List[str], cwd: Path | None = None, timeout: int = 120) -> Dict[str, Any]:
    try:
        proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout)
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "cmd": " ".join(shlex.quote(c) for c in cmd),
        }
    except FileNotFoundError as e:
        return {"ok": False, "returncode": 127, "stdout": "", "stderr": f"NOT INSTALLED: {e}", "cmd": " ".join(cmd)}
    except subprocess.TimeoutExpired as e:
        return {"ok": False, "returncode": 124, "stdout": e.stdout or "", "stderr": "TIMEOUT", "cmd": " ".join(cmd)}


def run_ruff(path: Path, timeout: int = 120) -> Dict[str, Any]:
    return _run(["ruff", "check", str(path)], timeout=timeout)


def run_mypy(path: Path, timeout: int = 120) -> Dict[str, Any]:
    return _run(["mypy", "--hide-error-codes", str(path)], timeout=timeout)


def run_bandit(path: Path, timeout: int = 120) -> Dict[str, Any]:
    return _run(["bandit", "-q", "-r", str(path)], timeout=timeout)


def run_pytest(cwd: Path, timeout: int = 180) -> Dict[str, Any]:
    return _run(["python", "-m", "pytest", "-q"], cwd=cwd, timeout=timeout)


def run_coverage_doctest(path: Path, timeout: int = 180) -> Dict[str, Any]:
    # Run doctest under coverage, then show report
    first = _run(["coverage", "run", "-m", "doctest", "-v", str(path)], timeout=timeout)
    if not first.get("ok"):
        return first | {"phase": "coverage-run"}
    report = _run(["coverage", "report", "-m"], timeout=timeout)
    return {
        "ok": first.get("ok", False) and report.get("ok", False),
        "returncode": report.get("returncode", 1),
        "stdout": (first.get("stdout", "") or "") + "\n" + (report.get("stdout", "") or ""),
        "stderr": (first.get("stderr", "") or "") + "\n" + (report.get("stderr", "") or ""),
        "cmd": first.get("cmd", "") + " && " + report.get("cmd", ""),
        "phase": "coverage-report",
    }


def run_selected_tools(code_path: Path, tools: List[str], cwd: Path | None = None, timeout: int = 180) -> Dict[str, Any]:
    results: Dict[str, Any] = {"tools": {}, "ok": True}
    tset = {t.strip().lower() for t in tools if t}
    if not tset:
        return results
    if "ruff" in tset:
        results["tools"]["ruff"] = run_ruff(code_path, timeout)
        results["ok"] = results["ok"] and results["tools"]["ruff"]["ok"]
    if "mypy" in tset:
        results["tools"]["mypy"] = run_mypy(code_path, timeout)
        results["ok"] = results["ok"] and results["tools"]["mypy"]["ok"]
    if "bandit" in tset:
        results["tools"]["bandit"] = run_bandit(code_path, timeout)
        results["ok"] = results["ok"] and results["tools"]["bandit"]["ok"]
    if "coverage" in tset:
        results["tools"]["coverage"] = run_coverage_doctest(code_path, timeout)
        results["ok"] = results["ok"] and results["tools"]["coverage"]["ok"]
    if "pytest" in tset and cwd:
        results["tools"]["pytest"] = run_pytest(cwd, timeout)
        results["ok"] = results["ok"] and results["tools"]["pytest"]["ok"]
    return results

