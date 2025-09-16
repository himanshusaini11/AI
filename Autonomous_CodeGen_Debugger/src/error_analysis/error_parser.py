import re

def summarize_trace(tb: str) -> str:
    if not tb or tb == "TIMEOUT":
        return "Execution timed out."
    # doctest failure summary lines
    m = re.findall(r"Failed example:\s*(.+?)\nException raised:\n(.+?)\n", tb, re.S)
    if m:
        cases = []
        for ex, msg in m[:3]:
            msg = re.sub(r"\s+", " ", msg.strip())
            cases.append(f"- Example: {ex}\n  Error: {msg}")
        return "Doctest failures:\n" + "\n".join(cases)
    # generic assertion/error lines
    last = tb.strip().splitlines()[-5:]
    return "Last traceback lines:\n" + "\n".join(last)
