import subprocess, sys, tempfile, textwrap, os, json, signal, resource
from pathlib import Path
from src.security.guard import safe_tempdir_root, assert_write_allowed

def _limit_resources(mem_mb: int, cpu_seconds: int):
    def _setter():
        try:
            resource.setrlimit(resource.RLIMIT_AS, (mem_mb * 1024 * 1024, mem_mb * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
            resource.setrlimit(resource.RLIMIT_FSIZE, (50 * 1024 * 1024, 50 * 1024 * 1024))
        except Exception:
            pass
    return _setter

def run_doctest(code_text: str, timeout_s: int = 5, mem_mb: int = 2048):
    """Write code to temp file and run doctest; return dict with status, stdout, stderr, traceback."""
    safe_root = safe_tempdir_root()
    with tempfile.TemporaryDirectory(dir=str(safe_root)) as td:
        path = os.path.join(td, "candidate.py")
        assert_write_allowed(path)
        with open(path, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(code_text))

        cmd = [sys.executable, "-m", "doctest", "-v", path]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_s,
                preexec_fn=_limit_resources(mem_mb, timeout_s)
            )
            ok = (proc.returncode == 0)
            return {
                "ok": ok, "stdout": proc.stdout, "stderr": proc.stderr,
                "traceback": proc.stdout if not ok else "", "path": path
            }
        except subprocess.TimeoutExpired as e:
            return {"ok": False, "stdout": e.stdout or "", "stderr": "TIMEOUT", "traceback": "TIMEOUT", "path": path}
