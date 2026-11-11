"""Shared by the acceptance tests: stdlib only, plain asserts, like the rest of tests/.

Each test file is the definition of done for one task in PLAN.md and is red until
that task is built. Run one:  python3 tests/acceptance/test_run_cli.py
Run all:                       python3 tests/acceptance/run_all.py
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, ROOT)
import nightmux  # noqa: E402

NM = os.path.join(ROOT, "nightmux.py")


def need(name, task):
    """nightmux.<name>, or a one-line 'not built' failure instead of a traceback."""
    if not hasattr(nightmux, name):
        raise AssertionError(f"{task} not built: nightmux.{name} is missing")
    return getattr(nightmux, name)


def fake_home():
    """A HOME with no 'nightmux' in its path (the migration test rewrites that word)
    and no live config: nothing here may touch the real ~/.nightmux.json or bot."""
    return tempfile.mkdtemp(prefix="nm-acc-")


def cli(*args, home=None, cwd=None, env=None, timeout=120):
    """Run the CLI isolated. Never call this with zero args: that boots the daemon."""
    assert args, "refusing to start a daemon from a test"
    home = home or fake_home()
    e = {k: v for k, v in os.environ.items() if not k.startswith(("TMUX", "NIGHTMUX"))}
    e.update({"HOME": home, "TMUX_TMPDIR": home}, **(env or {}))   # own tmux server
    return subprocess.run([sys.executable, NM, *args], capture_output=True, text=True,
                          cwd=cwd or home, env=e, timeout=timeout)


def run(tests):
    bad = []
    for t in tests:
        try:
            t()
            print(f"  ok   {t.__name__}")
        except AssertionError as e:
            bad.append(t.__name__)
            print(f"  FAIL {t.__name__}: {e}")
    print(("FAILED " if bad else "ok ") + f"{len(tests) - len(bad)}/{len(tests)}")
    return 1 if bad else 0
