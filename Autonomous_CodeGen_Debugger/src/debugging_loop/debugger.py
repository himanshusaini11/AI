import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"  # avoid fork warnings

import argparse, re
from pathlib import Path
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

from src.execution_sandbox.sandbox import run_doctest
from src.error_analysis.error_parser import summarize_trace
from src.codegen.prompts import REPAIR_PROMPT, DESIGN_PROMPT
from src.codegen.generate import _resolve_model_dir, _load  # your loader
from src.backends.select import select_backend
from src.security.guard import assert_write_allowed


# ----------------------------- helpers ----------------------------------------

FORBID = (
    "input(", "while True", "open(", "requests.", "urllib", "socket.",
    "subprocess", "os.system", "eval(", "exec(", "time.sleep(", "threading.",
    "multiprocessing", "http://", "https://"
)

def is_bad(code_text: str) -> bool:
    return any(tok in code_text for tok in FORBID) or len(code_text) > 4000

def _complete(tok, model, prompt, max_new_tokens=160, decode="greedy"):
    enc = tok(prompt, return_tensors="pt", return_attention_mask=True, add_special_tokens=True)
    enc = {k: v.to(model.device) for k, v in enc.items()}
    gen_kwargs = dict(max_new_tokens=max_new_tokens, eos_token_id=tok.eos_token_id, pad_token_id=tok.pad_token_id)
    if decode == "sample":
        gen_kwargs.update(dict(do_sample=True, temperature=0.2, top_p=0.95))
    else:
        gen_kwargs.update(dict(do_sample=False))
    with torch.no_grad():
        out = model.generate(**enc, **gen_kwargs)
    gen = out[0, enc["input_ids"].shape[1]:]
    text = tok.decode(gen, skip_special_tokens=True)
    cut = re.split(r"\n\s*\n(def |class |if __name__)", text, maxsplit=1)
    return (cut[0] if cut else text).strip()

def propose_default_fn(task: str) -> str:
    m = re.search(r"`?([A-Za-z_][A-Za-z0-9_]*)\s*\(", task)
    return m.group(1) if m else "solution"

def detect_func_name(task: str) -> str:
    m = re.search(r"`?([A-Za-z_][A-Za-z0-9_]*)\s*\(", task)
    return m.group(1) if m else propose_default_fn(task)

def seed_prefix_header_only(task: str, signature: str, doctests: str | None = None) -> str:
    doc = f"\n    \"\"\"{task.strip()}\n"
    if doctests:
        lines = [ln.rstrip() for ln in doctests.splitlines()]
        for ln in lines:
            if ln:
                doc += f"\n    {ln}"
    doc += "\n    \"\"\"\n"
    return signature.rstrip() + ":\n" + doc

def extract_function(text: str, fn_name: str) -> str:
    pat = rf"(?s)^\s*def\s+{re.escape(fn_name)}\s*\(.*?\):\s*(?:.*?\n)*?(?=^\s*def\s+|^\s*class\s+|^\s*if __name__|^\Z)"
    m = re.search(pat, text, flags=re.M)
    out = (m.group(0).rstrip() if m else text.strip())
    # normalize occasional bad indent on first statement
    lines = out.splitlines()
    if len(lines) >= 2 and lines[1].startswith("  ") and not lines[1].startswith("    "):
        lines[1] = "    " + lines[1].lstrip()
    # ensure docstring closes if model forgot
    if out.count('"""') % 2 == 1:
        lines.append('"""')
        out = "\n".join(lines)
    return out

def sanitize_to_function(text: str, fn_name: str) -> str:
    m = re.search(rf"(?ms)^\s*def\s+{re.escape(fn_name)}\s*\(.*", text)
    text = text[m.start():] if m else text
    func = extract_function(text, fn_name)
    # Strip markdown code fences but keep the content inside
    lines = func.splitlines()
    cut = []
    for ln in lines:
        if re.match(r"^\s*`{3,}", ln):
            # skip fence line and continue
            continue
        cut.append(ln)
    func = "\n".join(cut).strip() + ("\n" if cut else "")
    if not func.strip():
        # Fallback to original extracted text if sanitization yielded empty
        func = extract_function(text, fn_name)
    # Normalize doctest ellipsis indentation inside the first docstring, if present
    try:
        first = func.index('"""')
        second = func.index('"""', first + 3)
        pre = func[:first+3]
        body = func[first+3:second]
        post = func[second:]
        body_lines = body.splitlines()
        body_lines = [('    ...' if ln.strip() == '...' else ln) for ln in body_lines]
        body_norm = "\n".join(body_lines)
        # Ensure a space after exception colon before ellipsis, e.g., "ValueError:..." -> "ValueError: ..."
        body_norm = re.sub(r":\s*\.\.\.", ": ...", body_norm)
        # Strip comment-only lines outside the docstring
        body_after = post.splitlines()
        cleaned_after: list[str] = []
        for ln in body_after:
            # keep blank lines for readability but drop pure comments
            if ln.lstrip().startswith('#'):
                continue
            cleaned_after.append(ln)
        func = pre + body_norm + "\n".join(cleaned_after)
    except ValueError:
        pass
    return func

def filename_for(fn_name: str) -> str:
    return f"{fn_name}_autofixed.py"

def _complete_backend(backend, prompt: str, max_new_tokens=160, decode="greedy") -> str:
    text = backend.complete(prompt, max_new_tokens=max_new_tokens, decode=decode)
    cut = re.split(r"\n\s*\n(def |class |if __name__)", text, maxsplit=1)
    return (cut[0] if cut else text).strip()

def _design_signature_and_doctests_backend(backend, task: str, fn_name: str, max_new_tokens=200, decode="greedy") -> tuple[str, str | None]:
    prompt = DESIGN_PROMPT.format(task=task, fn_name=fn_name)
    text = _complete_backend(backend, prompt, max_new_tokens=max_new_tokens, decode=decode)
    m = re.search(r"```\s*(.*?)```", text, re.S)
    block = m.group(1) if m else text
    sig = None
    doctests = None
    sm = re.search(r"SIGNATURE:\s*(def\s+[^\n]+)", block)
    if sm:
        sig = sm.group(1).strip()
    else:
        dm = re.search(r"^(def\s+[^\n]+)", block, re.M)
        if dm:
            sig = dm.group(1).strip()
    dm2 = re.search(r"DOCTESTS:\s*(.+)\Z", block, re.S)
    if dm2:
        doctests = dm2.group(1).strip()
    else:
        # Fallback: collect any lines starting with doctest prompts
        lines = [ln for ln in block.splitlines() if ln.strip().startswith(">>> ")]
        if lines:
            doctests = "\n".join(lines)
    if sig and not sig.startswith(f"def {fn_name}"):
        sig = re.sub(r"^def\s+[A-Za-z_][A-Za-z0-9_]*", f"def {fn_name}", sig)
    if sig and sig.endswith(":"):
        sig = sig[:-1]
    return sig or f"def {fn_name}(x)", doctests
def _rewrite_docstring(code_text: str, fn_name: str, task: str) -> str:
    """Replace doctest-style docstring with Args/Returns docstring derived from signature and task.
    Keeps indentation and quotes intact, removes examples.
    """
    # Find function header and opening docstring
    m = re.search(rf"^(\s*def\s+{re.escape(fn_name)}\s*\(.*?\)\s*(?:->\s*[^:]+)?\s*:\s*\n)(\s*)\"\"\"", code_text, re.M | re.S)
    if not m:
        return code_text
    header = m.group(1)
    indent = m.group(2) or "    "
    start = m.end() - 3  # position at first quote of opening triple
    # Find end of the first docstring
    end_match = re.search(r"\"\"\"", code_text[start+3:])
    if not end_match:
        return code_text
    end = start + 3 + end_match.start()
    # Parse signature for args and return annotation
    sig_m = re.search(rf"^\s*def\s+{re.escape(fn_name)}\s*\((.*?)\)\s*(?:->\s*([^:]+))?\s*:\s*$", header, re.M)
    params = []
    if sig_m:
        params_src = sig_m.group(1)
        for p in [s.strip() for s in params_src.split(',') if s.strip()]:
            # drop default values and type hints for name
            name = p.split(':', 1)[0].split('=', 1)[0].strip()
            if name in ("self", "cls"):
                continue
            params.append(name)
        ret = (sig_m.group(2) or "").strip()
    else:
        ret = ""
    # Build new docstring body
    desc = task.strip().rstrip('.') + '.'
    lines = [desc, "", "Args:"] if params else [desc]
    if params:
        for name in params:
            lines.append(f"{name}: Description.")
    # Always include a Returns section; if no return annotation, keep it generic
    if lines and lines[-1] != "":
        lines.append("")
    lines.append("Returns:")
    if ret:
        lines.append(f"{ret}: Description.")
    else:
        lines.append("Return value: Description.")
    new_body = ("\n" + indent).join(lines)
    # Compose final text
    before = code_text[:start]
    after = code_text[end+3:]
    return before + '"""' + new_body + '"""' + after

def _first_doctest_call(doctests: str | None, fn_name: str) -> str | None:
    if not doctests:
        return None
    lines = [ln.rstrip() for ln in doctests.splitlines()]
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith('>>>'):
            cmd = stripped[4:].strip()
            if re.search(rf"\b{re.escape(fn_name)}\s*\(", cmd) and '=' not in cmd.split(fn_name, 1)[0]:
                parts = [cmd]
                j = i + 1
                while j < len(lines):
                    cont = lines[j].strip()
                    if cont.startswith('...'):
                        parts.append(cont[4:].strip())
                        j += 1
                    else:
                        break
                return ' '.join([p for p in parts if p]).strip()
        i += 1
    return None


def _to_standalone(code: str, fn_name: str, task: str, doctests: str | None = None) -> str:
    """Wrap the function into a runnable script with inferred imports and a simple example."""
    imports: list[str] = []
    body = code

    def has_import(pattern: str) -> bool:
        return bool(re.search(pattern, body, re.M))

    def add_import(line: str):
        if line and line not in imports and not has_import(rf"^\s*{re.escape(line)}\b"):
            imports.append(line)

    qualified_modules = [
        ('math', r"\bmath\."),
        ('re', r"\bre\."),
        ('json', r"\bjson\."),
        ('random', r"\brandom\."),
        ('datetime', r"\bdatetime\."),
        ('heapq', r"\bheapq\."),
        ('bisect', r"\bbisect\."),
        ('functools', r"\bfunctools\."),
        ('operator', r"\boperator\."),
        ('statistics', r"\bstatistics\."),
        ('collections', r"\bcollections\."),
        ('pathlib', r"\bpathlib\."),
    ]
    for mod, pat in qualified_modules:
        if re.search(pat, body) and not has_import(rf"^\s*import\s+{mod}\b|^\s*from\s+{mod}\s+import\b"):
            add_import(f"import {mod}")

    if re.search(r"\bpd\.", body) and not has_import(r"^\s*import\s+pandas\s+as\s+pd\b"):
        add_import('import pandas as pd')
    if re.search(r"\bnp\.", body) and not has_import(r"^\s*import\s+numpy\s+as\s+np\b"):
        add_import('import numpy as np')

    def need_names(names: list[str]) -> list[str]:
        needed: list[str] = []
        for nm in names:
            if re.search(rf"\b{nm}\s*\(", body) or re.search(rf"\b{nm}\b", body):
                needed.append(nm)
        return needed

    math_syms = ['sqrt', 'log', 'floor', 'ceil', 'fabs', 'factorial', 'gcd', 'lcm', 'cos', 'sin', 'tan', 'pi', 'inf', 'nan', 'hypot']
    missing = [s for s in need_names(math_syms) if not re.search(r"^\s*from\s+math\s+import\b|^\s*import\s+math\b", body, re.M)]
    if missing:
        if 'log' in missing and not re.search(r"^\s*import\s+math\b", body, re.M):
            body = re.sub(r"(?<!\.)\blog\s*\(", 'math.log(', body)
            missing = [m for m in missing if m != 'log']
        add_import('import math')
        constants = [x for x in missing if x in ('pi', 'inf', 'nan')]
        if constants:
            add_import('from math import ' + ', '.join(sorted(set(constants))))

    coll_syms = ['deque', 'Counter', 'defaultdict', 'namedtuple']
    coll_missing = [s for s in need_names(coll_syms) if not re.search(r"^\s*from\s+collections\s+import\b|^\s*import\s+collections\b", body, re.M)]
    if coll_missing:
        add_import('from collections import ' + ', '.join(sorted(set(coll_missing))))

    heap_syms = ['heappush', 'heappop', 'heapify', 'heapreplace', 'nlargest', 'nsmallest']
    heap_missing = [s for s in need_names(heap_syms) if not re.search(r"^\s*from\s+heapq\s+import\b|^\s*import\s+heapq\b", body, re.M)]
    if heap_missing:
        add_import('from heapq import ' + ', '.join(sorted(set(heap_missing))))

    bis_syms = ['bisect_left', 'bisect_right', 'insort', 'insort_left', 'insort_right']
    bis_missing = [s for s in need_names(bis_syms) if not re.search(r"^\s*from\s+bisect\s+import\b|^\s*import\s+bisect\b", body, re.M)]
    if bis_missing:
        add_import('from bisect import ' + ', '.join(sorted(set(bis_missing))))

    fn_syms = ['lru_cache', 'reduce', 'cmp_to_key', 'partial']
    fn_missing = [s for s in need_names(fn_syms) if not re.search(r"^\s*from\s+functools\s+import\b|^\s*import\s+functools\b", body, re.M)]
    if fn_missing:
        add_import('from functools import ' + ', '.join(sorted(set(fn_missing))))

    op_syms = ['itemgetter', 'attrgetter']
    op_missing = [s for s in need_names(op_syms) if not re.search(r"^\s*from\s+operator\s+import\b|^\s*import\s+operator\b", body, re.M)]
    if op_missing:
        add_import('from operator import ' + ', '.join(sorted(set(op_missing))))

    st_syms = ['mean', 'median', 'stdev', 'variance']
    st_missing = [s for s in need_names(st_syms) if not re.search(r"^\s*from\s+statistics\s+import\b|^\s*import\s+statistics\b", body, re.M)]
    if st_missing:
        add_import('from statistics import ' + ', '.join(sorted(set(st_missing))))

    if re.search(r"\bPath\s*\(", body) and not has_import(r"^\s*from\s+pathlib\s+import\s+Path\b|^\s*import\s+pathlib\b"):
        add_import('from pathlib import Path')
    if re.search(r"\bpathlib\.Path\b", body) and not has_import(r"^\s*import\s+pathlib\b"):
        add_import('import pathlib')

    sig_m = re.search(rf"^\s*def\s+{re.escape(fn_name)}\s*\(([^)]*)\)\s*(?:->\s*[^:]+)?\s*:", code, re.M)
    params: list[tuple[str, str]] = []
    if sig_m:
        params_src = sig_m.group(1)
        for p in [s.strip() for s in params_src.split(',') if s.strip()]:
            name = p.split(':', 1)[0].split('=', 1)[0].strip()
            if name not in ('self', 'cls'):
                params.append((name, p))

    def placeholder(spec: str) -> str:
        if '=' in spec:
            default = spec.split('=', 1)[1].strip()
            if default:
                return default
        ann = ''
        if ':' in spec:
            ann = spec.split(':', 1)[1].split('=', 1)[0].strip().lower()
        if ann.startswith('int') or 'int' in ann:
            return '0'
        if ann.startswith('float') or 'float' in ann:
            return '0.0'
        if ann.startswith('bool') or 'bool' in ann:
            return 'False'
        if ann.startswith('str') or 'str' in ann:
            return "'example'"
        if 'list' in ann or 'sequence' in ann or 'iterable' in ann:
            if 'int' in ann:
                return '[0]'
            if 'float' in ann:
                return '[0.0]'
            return "['example']"
        if 'dict' in ann or 'mapping' in ann:
            return "{'key': 'value'}"
        if 'set' in ann:
            return "{'example'}"
        if 'tuple' in ann:
            return "('example',)"
        if 'path' in ann:
            return "Path('path/to/file')"
        if 'callable' in ann:
            return 'lambda *args, **kwargs: None'
        return 'None'

    example_call = _first_doctest_call(doctests, fn_name)
    if example_call:
        call_expr = example_call
    else:
        call_expr = ', '.join(placeholder(spec) for _, spec in params)
        if 'Path(' in call_expr and 'from pathlib import Path' not in imports and not has_import(r"^\s*from\s+pathlib\s+import\s+Path\b"):
            add_import('from pathlib import Path')

    main_lines = ["if __name__ == '__main__':"]
    if example_call:
        main_lines.append('    # Example doctest usage.')
        if call_expr.startswith('print('):
            main_lines.append(f'    {call_expr}')
        else:
            main_lines.append(f'    print({call_expr})')
    elif params:
        main_lines.append('    # Example usage: replace the arguments with your own values.')
        main_lines.append(f"    print({fn_name}({call_expr}))")
    else:
        main_lines.append(f"    print({fn_name}())")

    header = "\n".join(imports)
    if header:
        header += "\n\n"
    return header + body.rstrip() + "\n\n" + "\n".join(main_lines) + "\n"

def _add_imports_only(code: str) -> str:
    """Add required imports (best-effort) at the top of the code without adding a CLI wrapper."""
    imports: list[str] = []
    body = code

    def has_import(pattern: str) -> bool:
        return bool(re.search(pattern, body, re.M))

    def add_import(line: str):
        if line and line not in imports and not has_import(rf"^\s*{re.escape(line)}\b"):
            imports.append(line)

    # Qualified modules
    qualified_modules = [
        ("math", r"\bmath\."),
        ("re", r"\bre\."),
        ("json", r"\bjson\."),
        ("random", r"\brandom\."),
        ("datetime", r"\bdatetime\."),
        ("heapq", r"\bheapq\."),
        ("bisect", r"\bbisect\."),
        ("functools", r"\bfunctools\."),
        ("operator", r"\boperator\."),
        ("statistics", r"\bstatistics\."),
        ("collections", r"\bcollections\."),
        ("pathlib", r"\bpathlib\."),
    ]
    for mod, pat in qualified_modules:
        if re.search(pat, body) and not has_import(rf"^\s*import\s+{mod}\b|^\s*from\s+{mod}\s+import\b"):
            add_import(f"import {mod}")

    # Aliases
    if re.search(r"\bpd\.", body) and not has_import(r"^\s*import\s+pandas\s+as\s+pd\b"):
        add_import("import pandas as pd")
    if re.search(r"\bnp\.", body) and not has_import(r"^\s*import\s+numpy\s+as\s+np\b"):
        add_import("import numpy as np")

    # From-imports for common unqualified names
    def need_names(names: list[str]) -> list[str]:
        needed = []
        for nm in names:
            if re.search(rf"\b{nm}\s*\(", body) or re.search(rf"\b{nm}\b", body):
                needed.append(nm)
        return needed

    math_syms = ["sqrt", "log", "floor", "ceil", "fabs", "factorial", "gcd", "lcm", "cos", "sin", "tan", "pi", "inf", "nan", "hypot"]
    missing = [s for s in need_names(math_syms) if not re.search(r"^\s*from\s+math\s+import\b|^\s*import\s+math\b", body, re.M)]
    if missing:
        if "log" in missing and not re.search(r"^\s*import\s+math\b", body, re.M):
            body = re.sub(r"(?<!\.)\blog\s*\(", "math.log(", body)
            missing = [m for m in missing if m != "log"]
        add_import("import math")
        constants = [x for x in missing if x in ("pi", "inf", "nan")]
        if constants:
            add_import("from math import " + ", ".join(sorted(set(constants))))

    coll_syms = ["deque", "Counter", "defaultdict", "namedtuple"]
    coll_missing = [s for s in need_names(coll_syms) if not re.search(r"^\s*from\s+collections\s+import\b|^\s*import\s+collections\b", body, re.M)]
    if coll_missing:
        add_import("from collections import " + ", ".join(sorted(set(coll_missing))))

    heap_syms = ["heappush", "heappop", "heapify", "heapreplace", "nlargest", "nsmallest"]
    heap_missing = [s for s in need_names(heap_syms) if not re.search(r"^\s*from\s+heapq\s+import\b|^\s*import\s+heapq\b", body, re.M)]
    if heap_missing:
        add_import("from heapq import " + ", ".join(sorted(set(heap_missing))))

    bis_syms = ["bisect_left", "bisect_right", "insort", "insort_left", "insort_right"]
    bis_missing = [s for s in need_names(bis_syms) if not re.search(r"^\s*from\s+bisect\s+import\b|^\s*import\s+bisect\b", body, re.M)]
    if bis_missing:
        add_import("from bisect import " + ", ".join(sorted(set(bis_missing))))

    fn_syms = ["lru_cache", "reduce", "cmp_to_key", "partial"]
    fn_missing = [s for s in need_names(fn_syms) if not re.search(r"^\s*from\s+functools\s+import\b|^\s*import\s+functools\b", body, re.M)]
    if fn_missing:
        add_import("from functools import " + ", ".join(sorted(set(fn_missing))))

    op_syms = ["itemgetter", "attrgetter"]
    op_missing = [s for s in need_names(op_syms) if not re.search(r"^\s*from\s+operator\s+import\b|^\s*import\s+operator\b", body, re.M)]
    if op_missing:
        add_import("from operator import " + ", ".join(sorted(set(op_missing))))

    st_syms = ["mean", "median", "stdev", "variance"]
    st_missing = [s for s in need_names(st_syms) if not re.search(r"^\s*from\s+statistics\s+import\b|^\s*import\s+statistics\b", body, re.M)]
    if st_missing:
        add_import("from statistics import " + ", ".join(sorted(set(st_missing))))

    if re.search(r"\bPath\s*\(", body) and not has_import(r"^\s*from\s+pathlib\s+import\s+Path\b|^\s*import\s+pathlib\b"):
        add_import("from pathlib import Path")
    if re.search(r"\bpathlib\.Path\b", body) and not has_import(r"^\s*import\s+pathlib\b"):
        add_import("import pathlib")

    header = "\n".join(imports) + ("\n\n" if imports else "")
    return header + body


# ------------------------------- main -----------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--fn", default=None, help="Override target function name")
    ap.add_argument("--model", default=os.environ.get("CODEGEN_MODEL_PATH"))
    ap.add_argument("--iters", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--max_new_tokens", type=int, default=160)
    ap.add_argument("--decode", choices=["greedy", "sample"], default="greedy")
    ap.add_argument("--candidates", type=int, default=1, help="Generate N initial candidates and pick first passing")
    ap.add_argument("--no-design", action="store_true", help="Skip signature/doctest design stage")
    ap.add_argument("--tools", default="", help="Comma-separated tools: ruff,mypy,bandit,coverage,pytest")
    ap.add_argument("--tools-on-each-iter", action="store_true", help="Run selected tools after each attempt (slower)")
    ap.add_argument("--early-stop-on-tools", action="store_true", help="Stop early if tools report OK (even if no tests)")
    ap.add_argument("--planner", action="store_true", help="Print planner/event log lines (PLAN:/EVENT:)")
    ap.add_argument("--save-run", action="store_true", help="Save run JSON (code + logs + results) under outputs/logs/")
    ap.add_argument("--verbose", action="store_true", help="Print detailed intermediate outputs for troubleshooting")
    ap.add_argument("--signature", default=None, help="Explicit function signature (e.g., 'def foo(a: int) -> int')")
    ap.add_argument("--doctests", default=None, help="Doctest lines to embed in the docstring (one string; can be multiline)")
    ap.add_argument("--no-test", action="store_true", help="Skip doctest execution and repair (generate only)")
    ap.add_argument("--coverage-repair", action="store_true", help="Use coverage report to guide repairs when tests fail")
    ap.add_argument("--no-save", action="store_true", help="Do not write output file")
    ap.add_argument("--print-only", action="store_true", help="Print final code to stdout")
    ap.add_argument("--clean-doc", action="store_true", help="Replace doctest docstring with Args/Returns")
    ap.add_argument("--final-only", action="store_true", help="Suppress intermediate logs; only final output")
    ap.add_argument("--thinking", action="store_true", help="Show high-level progress messages during generation and repair")
    ap.add_argument("--profile", choices=["copy", "save", "fast"], default=None,
                    help="Preset behavior: 'copy' prints clean code and saves nothing; 'save' writes outputs with progress logs")
    ap.add_argument("--standalone", action="store_true", help="Emit a runnable script with needed imports and a simple CLI main()")
    ap.add_argument("--add-imports", action="store_true", help="Augment the function with required imports (no CLI main)")
    ap.add_argument("--no-memory-hints", action="store_true", help="Disable retrieval hints in prompts")
    args = ap.parse_args()
    assert args.model, "Set --model or CODEGEN_MODEL_PATH"

    # Apply profile presets
    if args.profile == "copy":
        args.clean_doc = True
        args.print_only = True
        args.no_save = True
        args.final_only = True
        args.thinking = True
    elif args.profile == "save":
        args.clean_doc = False
        args.print_only = False
        args.no_save = False
        args.final_only = False
        # show progress by default
        if not args.thinking:
            args.thinking = True
    elif args.profile == "fast":
        # Favor speed over robustness; user flags still take precedence if explicitly set later
        args.no_design = True
        args.decode = "greedy"
        args.candidates = 1
        args.iters = 2
        if args.max_new_tokens and args.max_new_tokens > 120:
            args.max_new_tokens = 120

    # Verbose mode implies planner + thinking + full logs
    if args.verbose:
        args.planner = True
        args.thinking = True
        args.final_only = False

    # Logging helpers (define before any use)
    def log(msg: str):
        if not args.print_only and not args.no_save and not getattr(args, 'final_only', False):
            print(msg)

    def think(msg: str):
        if getattr(args, 'thinking', False):
            print(f"Thinking: {msg}")

    backend = select_backend(args.model)

    def vprint(*a):
        if args.verbose:
            print(*a)

    def _trim(txt: str, n: int = 1200) -> str:
        return (txt if len(txt) <= n else txt[:n] + "\n...[truncated]...")

    plan_events = []
    def plan(tag: str, data: dict | None = None):
        evt = {"tag": tag}
        if data: evt.update(data)
        plan_events.append(evt)
        if args.planner:
            print(f"PLAN: {tag} {data or {}}")

    fn_name = args.fn or detect_func_name(args.task)
    # Codex-like: choose signature/doctests (explicit > design > stub)
    # Helper: doctest validation and synthesis
    def _count_pairs(dt: str | None) -> int:
        if not dt:
            return 0
        lines = [ln.rstrip("\n") for ln in dt.splitlines()]
        cnt = 0
        i = 0
        while i < len(lines):
            if lines[i].strip().startswith(">>> ") and i + 1 < len(lines) and not lines[i+1].strip().startswith(">>>") and lines[i+1].strip() != "":
                cnt += 1
                i += 2
            else:
                i += 1
        return cnt

    def _synthesize_doctests(task: str, fn: str, signature: str) -> str | None:
        t = task.lower()
        if "quadratic" in t or "ax^2" in t or "a.x^2" in t:
            return (f">>> {fn}(1, -3, 2)\n(2+0j, 1+0j)\n"
                    f">>> {fn}(1, 2, 5)\n((-1+2j), (-1-2j))")
        if "ipv4" in t:
            return (f">>> {fn}('192.168.0.1')\nTrue\n"
                    f">>> {fn}('256.0.0.1')\nFalse")
        if "palindrome" in t:
            return (f">>> {fn}('racecar')\nTrue\n"
                    f">>> {fn}('hello')\nFalse")
        # Generic non-triviality: ensure return type not None
        return None

    fn_name = args.fn or detect_func_name(args.task)
    if args.signature:
        signature = args.signature.strip()
        doctests = args.doctests
    elif not args.no_design:
        think("Designing signature and doctests...")
        plan("design:start", {"fn": fn_name})
        signature, doctests = _design_signature_and_doctests_backend(backend, args.task, fn_name, max_new_tokens=200, decode=args.decode)
        # Validate doctests; synthesize if insufficient
        if _count_pairs(doctests) < 2:
            synth = _synthesize_doctests(args.task, fn_name, signature)
            if synth:
                doctests = synth
                plan("design:doctests_synth", {"pairs": _count_pairs(doctests)})
        plan("design:done", {"signature": signature, "doctests_present": bool(doctests), "pairs": _count_pairs(doctests)})
        vprint("[DESIGN] Signature:\n" + signature)
        if doctests:
            vprint("[DESIGN] Doctests:\n" + _trim(doctests))
    else:
        signature = f"def {fn_name}(x)"
        doctests = args.doctests
    # Optional memory hint
    task_for_prefix = args.task
    if not getattr(args, 'no_memory_hints', False):
        try:
            from src.memory.store import retrieve_hints
            _h = retrieve_hints(args.task, top_k=1)
            if _h:
                task_for_prefix += "\n\nHint: A similar task was previously solved; use a robust approach."
        except Exception:
            pass
    prefix = seed_prefix_header_only(task_for_prefix, signature, doctests)
    vprint("[PREFIX]\n" + _trim(prefix))

    # GEN-0
    think("Generating initial candidate...")
    plan("generate:start", {"candidates": int(args.candidates), "decode": args.decode})
    code = None
    best_code = None
    first_result = None
    n = max(1, int(args.candidates))
    for k in range(n):
        gen_body = _complete_backend(backend, prefix, max_new_tokens=args.max_new_tokens, decode=args.decode)
        cand = sanitize_to_function(prefix + gen_body, fn_name)
        if is_bad(cand):
            cand = extract_function(prefix + "    return False\n", fn_name)
        vprint(f"[CAND-{k}]\n" + _trim(cand))
        if args.no_test:
            code = cand
            result = {"ok": True, "traceback": "", "stdout": "", "stderr": ""}
            break
        res = run_doctest(cand, timeout_s=args.timeout)
        if first_result is None:
            first_result = (cand, res)
        if res["ok"]:
            code, result = cand, res
            best_code = cand
            break
    if code is None:
        code, result = first_result
    plan("generate:done", {"passed_doctest": bool(result and result.get("ok"))})

    if not args.no_test:
        think("Running doctests on initial candidate...")
        if not getattr(args, 'final_only', False):
            print("[GEN-0] pass=", result["ok"])
            if not result["ok"]:
                print("\n[SNIPPET]\n" + "\n".join(code.splitlines()[:60]))
        plan("test:gen0", {"ok": bool(result.get("ok"))})

    # Optionally run external tools on the current candidate
    tools = [t for t in args.tools.split(",") if t.strip()]
    tools_results = None
    code_path_for_tools = None
    if tools:
        # Save the current code to outputs/tmp for tooling
        tmp_dir = Path("outputs/.tools"); tmp_dir.mkdir(parents=True, exist_ok=True)
        code_path_for_tools = tmp_dir / f"{fn_name}_current.py"
        code_path_for_tools.write_text(code, encoding="utf-8")
        from src.tools.adapters import run_selected_tools
        tools_results = run_selected_tools(code_path_for_tools, tools, cwd=None)
        plan("tools:gen0", {"ok": tools_results.get("ok", False), "tools": list((tools_results.get("tools") or {}).keys())})
        if args.verbose:
            vprint("[TOOLS:gen0] results:")
            for t, res in (tools_results.get("tools") or {}).items():
                vprint(f"  - {t}: ok={res.get('ok')} rc={res.get('returncode')}\n    cmd: {res.get('cmd')}\n    stdout:\n{_trim(res.get('stdout',''))}\n    stderr:\n{_trim(res.get('stderr',''))}")
        if args.early_stop_on_tools and tools_results.get("ok") and (args.no_test or result.get("ok")):
            # Early stop: tools are happy and either tests are disabled or passed
            plan("early-stop", {"reason": "tools_ok"})
            # proceed to output

    # FIX loop (only if testing enabled)
    if not args.no_test:
        i = 0
        while not result["ok"] and i < args.iters:
            i += 1
            think(f"Attempting fix iteration {i}...")
            plan("repair:start", {"iter": i})
            err = summarize_trace(result["traceback"])
            if args.coverage_repair:
                try:
                    tmp_dir = Path("outputs/.tools"); tmp_dir.mkdir(parents=True, exist_ok=True)
                    cov_path = tmp_dir / f"{fn_name}_cov.py"
                    cov_path.write_text(code, encoding="utf-8")
                    from src.tools.adapters import run_coverage_doctest
                    cov = run_coverage_doctest(cov_path)
                    if cov and cov.get("stdout"):
                        err += "\n\n[Coverage]\n" + _trim(cov.get("stdout", ""))
                except Exception:
                    pass
            vprint("[ERROR] Summary:\n" + _trim(err))
            prompt = REPAIR_PROMPT.format(
                task=args.task,
                prev_code=extract_function(code, fn_name),
                error=err
            )
            fix = _complete_backend(backend, prompt, max_new_tokens=args.max_new_tokens, decode=args.decode)
            code = sanitize_to_function(fix, fn_name)
            vprint(f"[FIX-{i}] candidate:\n" + _trim(code))
            if is_bad(code):
                code = extract_function(prefix + "    return False\n", fn_name)
            result = run_doctest(code, timeout_s=args.timeout)
            if not getattr(args, 'final_only', False):
                print(f"[FIX-{i}] pass=", result["ok"])
                if not result["ok"]:
                    print("\n[SNIPPET]\n" + "\n".join(code.splitlines()[:60]))
            plan("repair:done", {"iter": i, "ok": bool(result.get("ok"))})
            if result.get("ok"):
                best_code = code
            if args.tools_on_each_iter and tools:
                code_path_for_tools.write_text(code, encoding="utf-8")
                tools_results = run_selected_tools(code_path_for_tools, tools, cwd=None)
                plan("tools:fix", {"iter": i, "ok": tools_results.get("ok", False)})
                if args.verbose:
                    vprint(f"[TOOLS:fix-{i}] results:")
                    for t, res in (tools_results.get("tools") or {}).items():
                        vprint(f"  - {t}: ok={res.get('ok')} rc={res.get('returncode')}\n    cmd: {res.get('cmd')}\n    stdout:\n{_trim(res.get('stdout',''))}\n    stderr:\n{_trim(res.get('stderr',''))}")
                if args.early_stop_on_tools and tools_results.get("ok") and (args.no_test or result.get("ok")):
                    plan("early-stop", {"reason": "tools_ok", "iter": i})
                    break

    # No hardcoded fallbacks in Codex-like mode

    if not result["ok"] and not code.lstrip().startswith("def "):
        # Minimal stub fallback if still failing
        code = (signature.rstrip() + ":\n    \"\"\"" + args.task.strip() + "\"\"\"\n    pass\n")

    # If code somehow became empty, fall back to last known good
    if not (code and code.strip()) and best_code:
        vprint("[FALLBACK] Restoring last passing code for output")
        code = best_code

    # Optionally clean the docstring for presentation
    if args.clean_doc:
        code = _rewrite_docstring(code, fn_name, args.task)

    # If no doctests were provided/designed, enforce a minimal quality gate
    def _nontrivial(c: str) -> bool:
        bad_tokens = ["pass\n", "# Your code here", "return x"]
        lines = c.splitlines()
        # strip signature and docstring block
        try:
            start = 1
            if len(lines) > 1 and lines[1].lstrip().startswith('"""'):
                # skip docstring block
                j = 2
                while j < len(lines) and '"""' not in lines[j]:
                    j += 1
                start = j + 1
        except Exception:
            start = 1
        body_lines = [ln for ln in lines[start:] if not ln.lstrip().startswith('#')]
        body = "\n".join(body_lines)
        if any(tok in body for tok in bad_tokens):
            return False
        # must contain a return and some arithmetic/indexing hints
        has_return = re.search(r"\breturn\b", body) is not None
        has_math = bool(re.search(r"[+\-*/]", body)) or "m[" in body or "[" in body
        has_def_dup = re.search(r"^\s*def\s+", body, re.M) is not None
        return has_return and has_math and not has_def_dup and len(body.strip()) > 20

    if (args.no_test or not (doctests and ">>>" in doctests)) and not _nontrivial(code):
        think("Improving body for non-trivial implementation...")
        improve_prompt = (
            f"# Task: {args.task}\n"
            f"# Implement the full function {fn_name} with a correct body.\n"
            f"# Return ONLY the function definition. Avoid placeholders or stubs.\n"
            f"{signature}:\n\n\"\"\"{args.task}\"\"\"\n"
        )
        tries = 0
        while tries < 3:
            improved = _complete_backend(backend, improve_prompt, max_new_tokens=max(args.max_new_tokens, 200), decode="sample")
            cand = sanitize_to_function(signature + ":\n" + improved, fn_name)
            if _nontrivial(cand):
                code = cand
                break
            tries += 1

    # Optionally add imports only, or emit full standalone script
    if args.add_imports and not args.standalone:
        code = _add_imports_only(code)
    if args.standalone:
        code = _to_standalone(code, fn_name, args.task, doctests)

    # Print code to stdout if requested (with explicit markers for UIs)
    if args.print_only:
        print("===CODE BEGIN===")
        # Ensure trailing newline
        print(code.rstrip() + "\n")
        print("===CODE END===")
    # Save unless suppressed
    if not args.no_save:
        outdir = Path("outputs/generated_code"); outdir.mkdir(parents=True, exist_ok=True)
        out_path = outdir / filename_for(fn_name)
        assert_write_allowed(out_path)
        out_path.write_text(code, encoding="utf-8")
        if not getattr(args, 'final_only', False):
            print(f"[SAVED] {out_path}")

    # Save run JSON (code + results + plan)
    if args.save_run:
        logs_dir = Path("outputs/logs"); logs_dir.mkdir(parents=True, exist_ok=True)
        import time, json
        ts = int(time.time())
        slug = re.sub(r"[^A-Za-z0-9_]+", "_", fn_name)[:40]
        run_path = logs_dir / f"run_{slug}_{ts}.json"
        payload = {
            "task": args.task,
            "fn": fn_name,
            "settings": {
                "iters": args.iters,
                "timeout": args.timeout,
                "max_new_tokens": args.max_new_tokens,
                "decode": args.decode,
                "candidates": args.candidates,
                "tools": tools,
            },
            "result": {"ok": bool(result.get("ok")) if isinstance(result, dict) else None},
            "plan": plan_events,
            "tools": tools_results,
            "code": code,
        }
        run_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if not getattr(args, 'final_only', False):
            print(f"[LOG] saved {run_path}")

    # Save successful outcome to memory store (best-effort)
    try:
        if isinstance(result, dict) and result.get("ok") and code:
            from src.memory.store import save_case
            save_case(args.task, fn_name, signature, code, plan_events)
    except Exception:
        pass

    if not result["ok"] and not getattr(args, 'final_only', False):
        print("\n[FINAL ERROR]\n" + summarize_trace(result["traceback"]))


if __name__ == "__main__":
    main()
