"""The legacy suite, as one test, until it is cut into test_<area>.py files."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402


def test_selfcheck():
    # slow
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "selfcheck.py")
    with isolated(nightmux):
        ns = vars(nightmux)
        with open(path) as f:
            exec(compile(f.read(), path, "exec"), ns)
        ns["selfcheck"]()
