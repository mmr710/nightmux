#!/usr/bin/env python3
"""Run the tests/test_*.py functions one at a time (stdlib only).

    python3 tests/run.py [--list] [-k SUBSTR] [--shuffle SEED] [--fast]

Ids are `file.py::test_name`. --fast skips tests whose first line is `# slow`.
Run it with a fake HOME and your own TMUX_TMPDIR, never bare against a live box.
"""
import ast
import glob
import importlib
import os
import random
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))


def collect():
    """[(id, fn, slow)] for every top-level test_* in tests/test_*.py.

    Files are parsed first and imported only if they define one: some are
    scripts that run on import.
    """
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.join(HERE, ".."))
    sys.path.insert(0, os.path.join(HERE, "acceptance"))
    out = []
    for path in sorted(glob.glob(os.path.join(HERE, "test_*.py"))):
        src = open(path, encoding="utf-8").read()
        fns = [n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
        if not fns:
            continue
        base = os.path.basename(path)
        mod = importlib.import_module(base[:-3])
        lines = src.splitlines()
        for n in fns:
            body = lines[n.lineno].strip() if n.lineno < len(lines) else ""
            out.append((f"{base}::{n.name}", getattr(mod, n.name), body.startswith("# slow")))
    return out


def main(argv):
    os.environ.pop("TMUX", None)        # a bare run must never reach a live tmux server
    os.environ.pop("TMUX_PANE", None)
    args, k, seed, fast, only_list = list(argv), None, None, False, False
    while args:
        a = args.pop(0)
        if a == "-k":
            k = args.pop(0)
        elif a == "--shuffle":
            seed = int(args.pop(0))
        elif a == "--fast":
            fast = True
        elif a == "--list":
            only_list = True
        else:
            sys.exit(f"unknown argument {a!r}")
    tests = [t for t in collect() if k is None or k in t[0]]
    if fast:
        tests = [t for t in tests if not t[2]]
    if seed is not None:
        random.Random(seed).shuffle(tests)
    if only_list:
        print("\n".join(t[0] for t in tests))
        return 0
    bad = 0
    for tid, fn, _ in tests:
        try:
            fn()
            print(f"  ok   {tid}", flush=True)
        except KeyboardInterrupt:
            raise
        except BaseException:           # a failing assert must name its line
            bad += 1
            print(f"  FAIL {tid}", flush=True)
            traceback.print_exc()
            sys.stdout.flush()
    print(("FAILED " if bad else "ok ") + f"{len(tests) - bad}/{len(tests)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
