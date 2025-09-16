#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
import threading
from pathlib import Path
from typing import List

import shlex
import streamlit as st


BASE = Path(__file__).resolve().parents[1]  # Autonomous_CodeGen_Debugger/
DEFAULT_MODEL_ROOT = Path(os.getenv("CODEGEN_MODELS_ROOT", "/Volumes/MyProjects/GitHub/AI/Autonomous_CodeGen_Debugger/models"))


def discover_models(root: Path) -> List[Path]:
    if not root.exists():
        return []
    # List immediate subdirectories; users will pick the top folder and our code resolves internally
    return [p for p in root.iterdir() if p.is_dir()]


def build_command(
    py: str,
    task: str,
    model_dir: Path,
    fn_name: str | None,
    iters: int,
    timeout: int,
    tokens: int,
    profile: str,
    add_imports: bool = False,
    standalone: bool = False,
    decode: str = "greedy",
    candidates: int = 1,
    no_design: bool = False,
    signature: str | None = None,
    doctests: str | None = None,
    no_test: bool = False,
) -> List[str]:
    cmd = [
        py,
        "-m",
        "src.debugging_loop.debugger",
        "--task",
        task,
        "--model",
        str(model_dir),
        "--iters",
        str(iters),
        "--timeout",
        str(timeout),
        "--max_new_tokens",
        str(tokens),
        "--profile", profile,
        "--decode", decode,
        "--candidates", str(candidates),
    ]
    if fn_name:
        cmd += ["--fn", fn_name]
    if add_imports:
        cmd += ["--add-imports"]
    if standalone:
        cmd += ["--standalone"]
    if no_design:
        cmd += ["--no-design"]
    if signature:
        cmd += ["--signature", signature]
    if doctests:
        cmd += ["--doctests", doctests]
    if no_test:
        cmd += ["--no-test"]
    return cmd


def call_worker_api(url: str, payload: dict, timeout: int) -> dict:
    endpoint = url.rstrip("/") + "/run"
    try:
        import requests  # type: ignore
    except ImportError:
        requests = None

    if requests is not None:
        try:
            resp = requests.post(endpoint, json=payload, timeout=timeout)
            resp.raise_for_status()
        except Exception as exc:  # pragma: no cover - streamlit UI path
            raise RuntimeError(f"{exc}") from exc
        return resp.json()

    import urllib.error
    import urllib.request

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(endpoint, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310 - user-provided host
            body = resp.read()
    except urllib.error.HTTPError as exc:  # pragma: no cover - streamlit UI path
        detail = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
        raise RuntimeError(f"HTTP {exc.code}: {detail[:2000]}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - streamlit UI path
        raise RuntimeError(f"Connection error: {exc.reason}") from exc

    return json.loads(body.decode("utf-8"))


def call_worker_health(url: str, timeout: int) -> dict:
    endpoint = url.rstrip("/") + "/health"
    try:
        import requests  # type: ignore
    except ImportError:
        requests = None

    if requests is not None:
        resp = requests.get(endpoint, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    import urllib.error
    import urllib.request

    req = urllib.request.Request(endpoint, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:  # pragma: no cover - streamlit UI path
        detail = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
        raise RuntimeError(f"HTTP {exc.code}: {detail[:2000]}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - streamlit UI path
        raise RuntimeError(f"Connection error: {exc.reason}") from exc

    return json.loads(body.decode("utf-8"))


def inject_quit_menu() -> None:
    st.markdown(
        """
        <script>
        (function() {
            const doc = window.parent.document;
            function ensureMenuHook() {
                const menuButton = doc.querySelector('button[aria-label="Main menu"]');
                if (!menuButton) {
                    setTimeout(ensureMenuHook, 1000);
                    return;
                }
                if (menuButton.dataset.quitHooked === '1') {
                    return;
                }
                menuButton.dataset.quitHooked = '1';
                menuButton.addEventListener('click', function() {
                    setTimeout(function() {
                        const menu = doc.querySelector('ul[role="menu"]');
                        if (!menu || menu.dataset.quitAdded === '1') {
                            return;
                        }
                        const item = doc.createElement('li');
                        item.setAttribute('role', 'none');
                        const button = doc.createElement('button');
                        button.setAttribute('role', 'menuitem');
                        const firstItem = menu.querySelector('button[role="menuitem"]');
                        if (firstItem) {
                            button.className = firstItem.className;
                        }
                        button.style.width = '100%';
                        button.style.textAlign = 'left';
                        button.innerText = 'Quit';
                        button.addEventListener('click', function(event) {
                            event.preventDefault();
                            event.stopPropagation();
                            const url = new URL(window.parent.location.href);
                            url.searchParams.set('quit', '1');
                            window.parent.location.href = url.toString();
                        });
                        item.appendChild(button);
                        menu.appendChild(item);
                        menu.dataset.quitAdded = '1';
                    }, 0);
                });
            }
            ensureMenuHook();
            const observer = new MutationObserver(ensureMenuHook);
            observer.observe(doc.body, { childList: true, subtree: true });
        })();
        </script>
        """,
        unsafe_allow_html=True,
    )


def request_shutdown() -> None:
    st.warning("Quit requested. Shutting down services...")

    def _terminate() -> None:
        os._exit(0)

    threading.Timer(0.5, _terminate).start()
    st.stop()


CLEAR_DEFAULTS = {
    "task_input": "",
    "fn_input": "",
    "sig_input": "",
    "doct_input": "",
    "output_mode": "Function",
}


def clear_inputs() -> None:
    for key, value in CLEAR_DEFAULTS.items():
        st.session_state[key] = value
    st.session_state["clear_feedback"] = True



def extract_final_code(all_output: str) -> str | None:
    # Prefer explicit markers if present
    m = re.search(r"^===CODE BEGIN===\n(?P<code>.*?)(?:\n)?^===CODE END===\s*$", all_output, re.S | re.M)
    if m:
        return m.group("code").strip() + "\n"
    # Fallback: find the last occurrence of a def at column 0
    lines = all_output.splitlines()
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].lstrip().startswith("def "):
            code = "\n".join(lines[i:])
            if code.count('"""') % 2 == 1:
                code += '\n"""'
            return code.strip() + "\n"
    return None


def main() -> None:
    st.set_page_config(page_title="Autonomous CodeGen & Debugger", layout="wide")
    st.title("Autonomous Code Generation + Self-Debugger (Local LLM)")
    st.caption("Runs your local model via Hugging Face snapshots. Prints clean, copy/paste code.")
    if "clear_feedback" not in st.session_state:
        st.session_state["clear_feedback"] = False
    inject_quit_menu()
    query_params = st.query_params
    quit_value = query_params.get("quit")
    if quit_value == "1" or quit_value == ["1"]:
        if "quit" in st.query_params:
            del st.query_params["quit"]
        request_shutdown()

    with st.sidebar:
        st.header("Model")
        model_root = st.text_input("Models root", value=str(DEFAULT_MODEL_ROOT))
        root_path = Path(model_root)
        models = discover_models(root_path)
        model_labels = [p.name for p in models] or ["<no models found>"]
        idx = st.selectbox("Choose model directory", options=range(len(model_labels)), format_func=lambda i: model_labels[i]) if models else 0
        selected_model = models[idx] if models else None

        st.header("Settings")
        profile = st.selectbox("Profile", options=["copy", "save", "fast"], index=0, help="copy prints clean code; save writes files; fast optimizes for speed")
        output_mode = st.radio("Output", ["Function", "Full code"], index=0, horizontal=False, key="output_mode")

        # Advanced controls tucked away by default
        with st.expander("Advanced (optional)", expanded=False):
            iters = st.number_input("Fix iterations", value=4, min_value=1, max_value=10, step=1)
            tokens = st.number_input("Max new tokens", value=160, min_value=32, max_value=2048, step=16)
            timeout = st.number_input("Timeout (s)", value=120, min_value=10, max_value=600, step=10)
            decode = st.selectbox("Decoding", options=["greedy", "sample"], index=1)
            candidates = st.number_input("Initial candidates", value=1, min_value=1, max_value=10, step=1)
            run_timeout = st.number_input("Run timeout (s)", value=300, min_value=30, max_value=3600, step=30, help="Maximum wait before labeling the run as long-running")

    worker_url = os.getenv("CODEGEN_WORKER_URL", "").strip()
    worker_ready = False
    worker_error: str | None = None
    if worker_url:
        try:
            health = call_worker_health(worker_url, timeout=int(os.getenv("CODEGEN_WORKER_HEALTH_TIMEOUT", "5")))
            if health.get("status") == "ok":
                worker_ready = True
        except Exception as exc:
            worker_error = str(exc)
    else:
        worker_error = "Set CODEGEN_WORKER_URL to a running FastAPI worker."

    if worker_error:
        st.error("Service temporarily unavailable. Please try again later.")

    task = st.text_area("Task", value=st.session_state.get("task_input", ""), key="task_input", height=100, placeholder="Describe the function you want. For best results, specify behavior and constraints.")
    fn_name = st.text_input("Function name (optional)", value=st.session_state.get("fn_input", ""), key="fn_input")
    signature = st.text_input("Function signature (optional)", value=st.session_state.get("sig_input", ""), key="sig_input", placeholder="e.g., def foo(a: int, b: int) -> int")
    doctests = st.text_area("Doctest examples (optional)", value=st.session_state.get("doct_input", ""), key="doct_input", height=120, placeholder=">>> foo(2, 3)\n5\n>>> foo(1, 1)\n2")

    run_col, clear_col = st.columns([1, 1])
    run_clicked = run_col.button("Run", type="primary", use_container_width=True)
    clear_col.button("Clear", use_container_width=True, on_click=clear_inputs)

    if st.session_state.get("clear_feedback"):
        st.success("Cleared inputs.")
        st.session_state["clear_feedback"] = False

    # Build generated command preview (always visible if enough inputs)
    py = sys.executable
    current_output = st.session_state.get("output_mode")
    add_imports = (current_output == "Function")
    standalone = (current_output == "Full code")
    sig_arg = signature.strip() or None
    doct_arg = doctests.strip() or None
    # These advanced vars exist from the expander scope
    try:
        _ = iters, tokens, timeout, decode, candidates, run_timeout
    except NameError:
        iters = 4; tokens = 160; timeout = 120; decode = "sample"; candidates = 1; run_timeout = 300

    generated_cmd = None
    if selected_model and task.strip():
        generated_cmd = build_command(
            py, task.strip(), selected_model, fn_name.strip() or None,
            int(iters), int(timeout), int(tokens), profile,
            add_imports=add_imports, standalone=standalone,
            decode=decode, candidates=int(candidates),
            signature=sig_arg, doctests=doct_arg
        )

    st.write("Command (generated):")
    if generated_cmd:
        st.code(shlex.join(generated_cmd))
    else:
        st.code("# Fill in Task and select a model to preview the command")

    st.write("Custom command (optional):")
    custom_cmd = st.text_area(
        "Custom command",
        value="",
        placeholder="python -m src.debugging_loop.debugger --task ...",
        height=70,
        label_visibility="visible",
        key="custom_cmd_input",
    )
    run_custom = st.button("Run Custom", use_container_width=False)

    def run_and_stream(cmd_list: List[str]):
        log_box = st.empty()
        code_box = st.empty()
        plan_box = st.empty()
        if not worker_ready:
            st.error("Service temporarily unavailable. Please try again later.")
            return
        try:
            payload = {
                "task": task.strip(),
                "fn": fn_name.strip() or None,
                "signature": signature.strip() or None,
                "doctests": doctests.strip() or None,
                "iters": int(iters),
                "timeout": int(timeout),
                "max_new_tokens": int(tokens),
                "decode": decode,
                "candidates": int(candidates),
                "add_imports": (st.session_state.get("output_mode") == "Function"),
                "standalone": (st.session_state.get("output_mode") == "Full code"),
                "clean_doc": False,
            }
            with st.spinner("Calling worker..."):
                data = call_worker_api(worker_url, payload, int(run_timeout))
            plan_events = data.get("plan", [])
            if plan_events:
                lines = [f"PLAN: {e.get('tag')} { {k:v for k,v in e.items() if k!='tag'} }" for e in plan_events]
                plan_box.code("\n".join(lines))
            code = data.get("code", "")
            logs = data.get("logs", [])
            if logs:
                log_box.code("\n".join(logs[-200:]))
            if code:
                st.success("Final code")
                code_box.code(code, language="python")
                st.download_button("Download .py", data=code, file_name=(fn_name.strip() or "solution") + ".py")
            else:
                st.warning("Worker returned no code.")
        except Exception:
            st.error("Service temporarily unavailable. Please try again later.")

    # Execute generated or custom command based on which button is pressed
    if run_clicked:
        if not selected_model and not worker_ready:
            st.error("No model directories found under the provided models root.")
            st.stop()
        if not task.strip():
            st.error("Please enter a task.")
            st.stop()
        if selected_model:
            st.info(f"Running with model: {selected_model.name}")
        else:
            st.info("Running request via remote worker.")
        run_and_stream(generated_cmd or [])
    elif run_custom and custom_cmd.strip():
        try:
            final_cmd = shlex.split(custom_cmd.strip())
            run_and_stream(final_cmd)
        except Exception:
            st.error("Invalid custom command.")


if __name__ == "__main__":
    main()
