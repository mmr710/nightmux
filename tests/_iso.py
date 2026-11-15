"""One context manager that makes a test safe to run alone, in any order.

    with isolated(nightmux) as iso:
        ...                      # iso.home, iso.sent, iso.calls

It gives the test a temp HOME and its own TMUX_TMPDIR (TMUX/TMUX_PANE dropped),
stubs `mod.send` and `mod.api` (recording into `iso.sent` / `iso.calls`), and on
exit puts the module's globals and the environment back, deleting new keys.

nightmux computes its path globals (CFG_PATH, STATE_DIR, ...) with expanduser at
import, before HOME changes, so every str global under the real home is rewritten
to the temp home for the duration.

The restore is shallow: a dict or list the test mutated in place is not restored.
`tests/run.py --shuffle` is what catches that.
"""
import contextlib
import os
import shutil
import tempfile


class Iso:
    def __init__(self):
        self.home = tempfile.mkdtemp(prefix="nm-iso-")
        self.sent = []      # (cfg, chat, text, ...) for each mod.send call
        self.calls = []     # (method, kwargs) for each mod.api call


@contextlib.contextmanager
def isolated(mod):
    iso = Iso()
    real = os.path.expanduser("~")
    code = os.path.dirname(os.path.abspath(mod.__file__))  # a checkout under HOME (CI) keeps its paths
    saved_mod, saved_env = dict(vars(mod)), dict(os.environ)
    try:
        for k in ("TMUX", "TMUX_PANE"):
            os.environ.pop(k, None)
        os.environ["HOME"] = os.environ["TMUX_TMPDIR"] = iso.home
        for k, v in saved_mod.items():
            if (isinstance(v, str) and (v == real or v.startswith(real + os.sep))
                    and not (v == code or v.startswith(code + os.sep))):
                setattr(mod, k, iso.home + v[len(real):])
        mod.send = lambda c, t, x, *a, **kw: iso.sent.append((c, t, x, a, kw))
        mod.api = lambda c, m, **kw: iso.calls.append((m, kw)) or {}
        yield iso
    finally:
        d = vars(mod)
        for k in [k for k in d if k not in saved_mod]:
            del d[k]
        d.update(saved_mod)
        os.environ.clear()
        os.environ.update(saved_env)
        shutil.rmtree(iso.home, ignore_errors=True)
