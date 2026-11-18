#!/usr/bin/env python3
"""T2.2 + T2.4  The code and its tests stay in pieces a person can hold.

Ratchets, measured on 2026-11-11 and lowered by each PR that earns it. Never
raise one to make a PR pass.
"""
import ast
import glob
import os
import re
import subprocess
import sys

from _h import ROOT, run

# Ratchets for T2.2 / T2.3 PRs. Final values: MAX_TEST_FUNC 200, MAX_FUNC 250,
# MAX_SILENT_EXCEPT 0, MIN_TESTS 150.
MAX_TEST_FUNC = 200      # longest test function; final value, selfcheck() is gone (T2.2d)
MAX_FUNC = 253           # nightmux.py: do_GET (handle is 106)
MAX_SILENT_EXCEPT = 44   # `except ...: pass` with no reason on the line
MIN_TESTS = 198          # tests/run.py --list after T2.2d (final); never fewer


def _funcs(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    return [(n.end_lineno - n.lineno + 1, n.name) for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def test_no_giant_test_function():
    big = [(n, os.path.basename(f), name) for f in glob.glob(os.path.join(ROOT, "tests", "*.py"))
           for n, name in _funcs(f) if n > MAX_TEST_FUNC]
    assert not big, f"test functions over {MAX_TEST_FUNC} lines: {sorted(big, reverse=True)[:5]}"


def test_runner_lists_and_filters():
    runner = os.path.join(ROOT, "tests", "run.py")
    assert os.path.exists(runner), "T2.2 not built: tests/run.py is missing"
    r = subprocess.run([sys.executable, runner, "--list"], capture_output=True, text=True, timeout=60)
    names = [l for l in r.stdout.split() if "test_" in l]
    assert r.returncode == 0 and len(names) >= MIN_TESTS, f"--list gave {len(names)} tests, want {MIN_TESTS}+"
    assert len(set(names)) == len(names), "duplicate test names"
    r = subprocess.run([sys.executable, runner, "-k", "chunks"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and "chunks" in r.stdout, f"-k chunks: {r.stdout[-200:]}{r.stderr[-200:]}"
    ran = len(re.findall(r"^\s*ok\b", r.stdout, re.M))
    assert 1 <= ran < 20, f"-k chunks ran {ran} tests: the filter is not filtering"


def test_order_independent():
    runner = os.path.join(ROOT, "tests", "run.py")
    assert os.path.exists(runner), "T2.2 not built: tests/run.py is missing"
    for seed in ("1", "2"):
        r = subprocess.run([sys.executable, runner, "--shuffle", seed, "--fast"],
                           capture_output=True, text=True, timeout=600)
        assert r.returncode == 0, f"--shuffle {seed} failed: a test leans on one before it\n{r.stdout[-800:]}"


def test_no_giant_function():
    big = sorted(((n, name) for n, name in _funcs(os.path.join(ROOT, "nightmux.py")) if n > MAX_FUNC),
                 reverse=True)
    assert not big, f"functions over {MAX_FUNC} lines: {big}"


def test_no_silent_except():
    src = open(os.path.join(ROOT, "nightmux.py"), encoding="utf-8").read()
    silent = [m.start() for m in re.finditer(r"except[^\n#]*:[ \t]*\n[ \t]+pass[ \t]*\n", src)]
    lines = sorted({src.count("\n", 0, p) + 1 for p in silent})
    assert len(lines) <= MAX_SILENT_EXCEPT, (
        f"{len(lines)} `except: pass` with no reason (cap {MAX_SILENT_EXCEPT}); say why on the "
        f"except line (`# why: ...`) or log it. First: lines {lines[:8]}")


if __name__ == "__main__":
    sys.exit(run([test_no_giant_test_function, test_runner_lists_and_filters, test_order_independent,
                  test_no_giant_function, test_no_silent_except]))
