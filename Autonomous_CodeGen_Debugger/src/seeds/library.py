"""Seed templates and optional fallbacks for function generation.

This module centralizes:
- Function name detection heuristics
- Seed prefixes (with doctest-style or minimal docstrings)
- Optional known-good fallbacks for a few tasks
"""

from __future__ import annotations
import re


# ------------------------- name detection -------------------------------------

def propose_default_fn(task: str) -> str:
    t = task.lower()
    def has(*words):
        return all(w in t for w in words)
    if any(w in t for w in ("calculation", "calculate", "calculator", "addition", "substraction", "subtraction", "multiplication", "division", "divide")):
        return "basic_calc"
    if any(w in t for w in ("exploratory data analysis", "eda")) or ("dataframe" in t and "analysis" in t):
        return "Auto_EDA"
    if any(w in t for w in ("sub string", "substring", "sub-string")):
        return "find_sub_string"
    m = re.search(r"`?([A-Za-z_][A-Za-z0-9_]*)\s*\(", task)
    if m:
        return m.group(1)
    if has("ipv4"):
        return "is_ipv4"
    if any(w in t for w in ("palindrome",)):
        return "is_palindrome"
    if any(w in t for w in ("anagram",)):
        return "is_anagram"
    if any(w in t for w in ("prime",)):
        return "is_prime"
    if any(w in t for w in ("factorial",)):
        return "factorial"
    if any(w in t for w in ("fibonacci",)):
        return "fibonacci"
    if has("balanced", "parentheses"):
        return "balanced_parentheses"
    if (any(w in t for w in ("greatest", "largest", "maximum", "max")) and
        any(w in t for w in ("array", "list", "sequence"))):
        return "max_in_list"
    if (any(w in t for w in ("smallest", "minimum", "min")) and
        any(w in t for w in ("array", "list", "sequence"))):
        return "min_in_list"
    if ("reverse" in t and any(w in t for w in ("words", "word"))):
        return "reverse_words"
    if ("reverse" in t and "string" in t):
        return "reverse_string"
    return "solution"


# --------------------------- seed templates -----------------------------------

def seed_prefix(task: str, fn_name: str | None = None) -> str:
    fn = fn_name or propose_default_fn(task)
    if fn in ("find_sub_string", "find_substring"):
        return (
            "def find_sub_string(s: str, sub: str) -> int:\n"
            "    \"\"\"Return the starting index of the first occurrence of sub in s, or -1 if absent.\n"
            "\n"
            "    >>> find_sub_string('hello', 'lo')\n"
            "    3\n"
            "    >>> find_sub_string('hello', 'x')\n"
            "    -1\n"
            "    >>> find_sub_string('aaaa', 'aa')\n"
            "    0\n"
            "    \"\"\"\n"
            "    # fill the rest of the body:\n"
        )
    if fn in ("Auto_EDA", "auto_eda"):
        return (
            "def Auto_EDA(df):\n"
            "    \"\"\"Perform a lightweight exploratory data analysis on a pandas DataFrame and print results.\n"
            "\n"
            "    This function prints: shape, column dtypes, basic statistics, missing values per column,\n"
            "    and the first few rows.\n"
            "    \"\"\"\n"
            "    # fill the rest of the body:\n"
        )
    if fn in ("basic_calc", "calc", "calculator"):
        return (
            "def basic_calc(a: float, b: float, op: str) -> float:\n"
            "    \"\"\"Perform a basic calculation on a and b.\n"
            "\n"
            "    Supported operations (op): 'add', 'sub', 'mul', 'div'.\n"
            "\n"
            "    >>> basic_calc(2, 3, 'add')\n"
            "    5\n"
            "    >>> basic_calc(10, 4, 'sub')\n"
            "    6\n"
            "    >>> basic_calc(3, 4, 'mul')\n"
            "    12\n"
            "    >>> basic_calc(8, 2, 'div')\n"
            "    4.0\n"
            "    >>> basic_calc(1, 0, 'div')\n"
            "    Traceback (most recent call last):\n"
            "    ...\n"
            "    ZeroDivisionError: ...\n"
            "    >>> basic_calc(1, 1, 'noop')\n"
            "    Traceback (most recent call last):\n"
            "    ...\n"
            "    ValueError: ...\n"
            "    \"\"\"\n"
            "    # fill the rest of the body:\n"
        )
    if fn == "is_ipv4":
        return (
            "def is_ipv4(s: str) -> bool:\n"
            "    \"\"\"Return True if s is a valid IPv4 address.\n"
            "    >>> is_ipv4('192.168.1.1')\n"
            "    True\n"
            "    >>> is_ipv4('256.0.0.1')\n"
            "    False\n"
            "    >>> is_ipv4('1.2.3')\n"
            "    False\n"
            "    \"\"\"\n"
            "    parts = s.split('.')\n"
            "    if len(parts) != 4:\n"
            "        return False\n"
            "    # fill the rest of the body:\n"
        )
    if fn == "is_palindrome":
        return (
            "def is_palindrome(s: str) -> bool:\n"
            "    \"\"\"Return True if s reads the same forward and backward.\n"
            "\n"
            "    >>> is_palindrome('racecar')\n"
            "    True\n"
            "    >>> is_palindrome('hello')\n"
            "    False\n"
            "    >>> is_palindrome('')\n"
            "    True\n"
            "    \"\"\"\n"
            "    # fill the rest of the body:\n"
        )
    if fn == "factorial":
        return (
            "def factorial(n: int) -> int:\n"
            "    \"\"\"Compute n! for non-negative integers.\n"
            "\n"
            "    >>> factorial(0)\n"
            "    1\n"
            "    >>> factorial(5)\n"
            "    120\n"
            "    >>> factorial(1)\n"
            "    1\n"
            "    >>> factorial(-1)\n"
            "    Traceback (most recent call last):\n"
            "    ...\n"
            "    ValueError: ...\n"
            "    \"\"\"\n"
            "    # fill the rest of the body:\n"
        )
    if fn == "fibonacci":
        return (
            "def fibonacci(n: int) -> int:\n"
            "    \"\"\"Return the nth Fibonacci number (0-indexed).\n"
            "\n"
            "    >>> fibonacci(0)\n"
            "    0\n"
            "    >>> fibonacci(1)\n"
            "    1\n"
            "    >>> fibonacci(7)\n"
            "    13\n"
            "    >>> fibonacci(-1)\n"
            "    Traceback (most recent call last):\n"
            "    ...\n"
            "    ValueError: ...\n"
            "    \"\"\"\n"
            "    # fill the rest of the body:\n"
        )
    if fn == "is_prime":
        return (
            "def is_prime(n: int) -> bool:\n"
            "    \"\"\"Return True if n is a prime number (n >= 2).\n"
            "\n"
            "    >>> is_prime(2)\n"
            "    True\n"
            "    >>> is_prime(1)\n"
            "    False\n"
            "    >>> is_prime(17)\n"
            "    True\n"
            "    >>> is_prime(15)\n"
            "    False\n"
            "    \"\"\"\n"
            "    # fill the rest of the body:\n"
        )
    if fn == "reverse_words":
        return (
            "def reverse_words(s: str) -> str:\n"
            "    \"\"\"Reverse the order of words separated by whitespace.\n"
            "\n"
            "    >>> reverse_words('hello world')\n"
            "    'world hello'\n"
            "    >>> reverse_words('a b c')\n"
            "    'c b a'\n"
            "    >>> reverse_words('single')\n"
            "    'single'\n"
            "    \"\"\"\n"
            "    # fill the rest of the body:\n"
        )
    if fn == "reverse_string":
        return (
            "def reverse_string(s: str) -> str:\n"
            "    \"\"\"Return the reverse of the input string.\n"
            "\n"
            "    >>> reverse_string('abc')\n"
            "    'cba'\n"
            "    >>> reverse_string('')\n"
            "    ''\n"
            "    >>> reverse_string('a')\n"
            "    'a'\n"
            "    \"\"\"\n"
            "    # fill the rest of the body:\n"
        )
    if fn == "sum_nested":
        return (
            "def sum_nested(lst: list) -> int:\n"
            "    \"\"\"Return the sum of all integers in a (possibly) nested list.\n"
            "\n"
            "    >>> sum_nested([1, [2, 3], [], [4, [5]]])\n"
            "    15\n"
            "    >>> sum_nested([])\n"
            "    0\n"
            "    >>> sum_nested([0, [0, [0]]])\n"
            "    0\n"
            "    \"\"\"\n"
            "    # fill the rest of the body:\n"
        )
    if fn == "balanced_parentheses":
        return (
            "def balanced_parentheses(s: str) -> bool:\n"
            "    \"\"\"Return True if parentheses in s are balanced.\n"
            "\n"
            "    >>> balanced_parentheses('()')\n"
            "    True\n"
            "    >>> balanced_parentheses('(())')\n"
            "    True\n"
            "    >>> balanced_parentheses('(()')\n"
            "    False\n"
            "    >>> balanced_parentheses(')(')\n"
            "    False\n"
            "    \"\"\"\n"
            "    # fill the rest of the body:\n"
        )
    if fn == "is_anagram":
        return (
            "def is_anagram(a: str, b: str) -> bool:\n"
            "    \"\"\"Return True if a and b are anagrams (ignore spaces, case).\n"
            "\n"
            "    >>> is_anagram('listen', 'silent')\n"
            "    True\n"
            "    >>> is_anagram('rat', 'car')\n"
            "    False\n"
            "    >>> is_anagram('Dormitory', 'Dirty room')\n"
            "    True\n"
            "    \"\"\"\n"
            "    # fill the rest of the body:\n"
        )
    if fn == "max_in_list":
        return (
            "def max_in_list(nums: list[int]) -> int:\n"
            "    \"\"\"Return the maximum integer in a non-empty list.\n"
            "\n"
            "    >>> max_in_list([1, 3, 2])\n"
            "    3\n"
            "    >>> max_in_list([-5, -2, -10])\n"
            "    -2\n"
            "    >>> max_in_list([42])\n"
            "    42\n"
            "    >>> max_in_list([])\n"
            "    Traceback (most recent call last):\n"
            "    ...\n"
            "    ValueError: ...\n"
            "    \"\"\"\n"
            "    # fill the rest of the body:\n"
        )
    if fn == "min_in_list":
        return (
            "def min_in_list(nums: list[int]) -> int:\n"
            "    \"\"\"Return the minimum integer in a non-empty list.\n"
            "\n"
            "    >>> min_in_list([1, 3, 2])\n"
            "    1\n"
            "    >>> min_in_list([-5, -2, -10])\n"
            "    -10\n"
            "    >>> min_in_list([42])\n"
            "    42\n"
            "    >>> min_in_list([])\n"
            "    Traceback (most recent call last):\n"
            "    ...\n"
            "    ValueError: ...\n"
            "    \"\"\"\n"
            "    # fill the rest of the body:\n"
        )
    # Generic fallback template
    return (
        f"def {fn}(x):\n"
        f"    \"\"\"Implement {fn}.\n"
        f"    >>> isinstance({fn}(0), (int, bool, float, str))\n"
        f"    True\n"
        f"    >>> {fn}(1)\n"
        f"    {fn}(1)\n"
        f"    \"\"\"\n"
    )


# ----------------------------- fallbacks --------------------------------------

def known_good_ipv4() -> str:
    return (
        'def is_ipv4(s: str) -> bool:\n'
        '    """Return True if s is a valid IPv4 address.\n'
        '\n'
        '    An IPv4 address must have exactly 4 decimal numbers (0–255) separated by dots.\n'
        '\n'
        '    >>> is_ipv4("192.168.0.1")\n'
        '    True\n'
        '    >>> is_ipv4("256.100.50.25")\n'
        '    False\n'
        '    >>> is_ipv4("192.168.1")\n'
        '    False\n'
        '    """\n'
        '    parts = s.split(".")\n'
        '    if len(parts) != 4:\n'
        '        return False\n'
        '    for part in parts:\n'
        '        if not part.isdigit():\n'
        '            return False\n'
        '        num = int(part)\n'
        '        if num < 0 or num > 255:\n'
        '            return False\n'
        '        if part != str(num):  # reject leading zeros\n'
        '            return False\n'
        '    return True\n'
    )

def known_good_max_in_list() -> str:
    return (
        'def max_in_list(nums: list[int]) -> int:\n'
        '    """Return the maximum integer in a non-empty list.\n'
        '\n'
        '    >>> max_in_list([1, 3, 2])\n'
        '    3\n'
        '    >>> max_in_list([-5, -2, -10])\n'
        '    -2\n'
        '    >>> max_in_list([42])\n'
        '    42\n'
        '    >>> max_in_list([])\n'
        '    Traceback (most recent call last):\n'
        '    ...\n'
        '    ValueError: ...\n'
        '    """\n'
        '    if not nums:\n'
        '        raise ValueError("Empty list")\n'
        '    m = nums[0]\n'
        '    for v in nums[1:]:\n'
        '        if v > m:\n'
        '            m = v\n'
        '    return m\n'
    )

def fallback_for(fn_name: str) -> str | None:
    if fn_name == "is_ipv4":
        return known_good_ipv4()
    if fn_name == "max_in_list":
        return known_good_max_in_list()
    return None
