from __future__ import annotations
import os
from pathlib import Path

def _project_root() -> Path:
    # src/security/guard.py -> project root is two levels up from src
    return Path(__file__).resolve().parents[2]

PROJECT_ROOT = _project_root()

def _parse_roots(env_var: str) -> list[Path]:
    raw = os.getenv(env_var, "").strip()
    if not raw:
        return []
    parts = [p for p in raw.split(os.pathsep) if p]
    return [Path(p).resolve() for p in parts]

_extra_read_roots = []
_models_root = os.getenv("CODEGEN_MODELS_ROOT", "").strip()
if _models_root:
    try:
        _extra_read_roots.append(Path(_models_root).resolve())
    except Exception:
        pass
ALLOWED_READ_ROOTS = [PROJECT_ROOT] + _extra_read_roots + _parse_roots("CODEGEN_ALLOWED_READ_ROOTS")
ALLOWED_WRITE_ROOTS = [PROJECT_ROOT] + _parse_roots("CODEGEN_ALLOWED_WRITE_ROOTS")

def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False

def _ensure_allowed(path: Path, roots: list[Path], mode: str) -> None:
    for r in roots:
        if _is_under(path, r):
            return
    roots_str = ", ".join(str(r) for r in roots)
    raise PermissionError(f"Path not allowed for {mode}: {path} (allowed roots: {roots_str})")

def assert_read_allowed(path: str | os.PathLike) -> None:
    _ensure_allowed(Path(path), ALLOWED_READ_ROOTS, "read")

def assert_write_allowed(path: str | os.PathLike) -> None:
    _ensure_allowed(Path(path), ALLOWED_WRITE_ROOTS, "write")

def safe_tempdir_root() -> Path:
    root = PROJECT_ROOT / "outputs" / ".sandbox"
    root.mkdir(parents=True, exist_ok=True)
    return root
