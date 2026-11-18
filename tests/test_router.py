"""test_router: cut from tests/selfcheck.py (stubbed part)."""
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_router_classes_and_light_task_moves():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # Router: classes, mid-task prompts stay, a light task on a quiet topic moves
        # to the light agent, learned scores outrank the preference list.
        assert nightmux.task_class("rename foo to bar in utils") == "light"
        assert nightmux.task_class("why does the websocket drop under load?") == "heavy"
        assert nightmux.task_class("add a dark mode toggle to settings") == "normal"


def test_drift_old_opencode_tables():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # Drift: opencode 2 left its old tables behind, empty. The reader neither
        # throws nor finds anything; the freshly written database gives it away.
        import sqlite3
        dh = tempfile.mkdtemp(prefix="nightmux-selfcheck-drift-")
        os.makedirs(os.path.join(dh, ".local/share/opencode"))
        con_ = sqlite3.connect(os.path.join(dh, nightmux.DRIFT_STORES["opencode"]))
        con_.executescript("CREATE TABLE message (id, session_id, data, time_created);"
                           "CREATE TABLE part (message_id, data);"
                           "CREATE TABLE session (id, directory);")
        con_.close()
        assert [a_ for a_, _ in nightmux.reader_drift(home=dh)] == ["opencode"], nightmux.reader_drift(home=dh)
        old_ = time.time() - 30 * 86400
        os.utime(os.path.join(dh, nightmux.DRIFT_STORES["opencode"]), (old_, old_))
        assert nightmux.reader_drift(home=dh) == []        # untouched for a month: nothing to say
        shutil.rmtree(dh, ignore_errors=True)
        assert nightmux.task_class("make a snake game") == "heavy"          # creative: not the cheap model
        assert nightmux.task_class("build a landing page for my app") == "heavy"
        assert nightmux.task_class("fix typo in the history page") == "light"  # "story" is a word, not a substring
