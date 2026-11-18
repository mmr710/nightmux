"""test_router: cut from the old monolithic selfcheck() (stubbed part)."""
import os
import queue
import shutil
import sys
import tempfile
import threading
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


def test_dispatch_keeps_topic_order_and_acks():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        box = ["╭────────╮", "│ > ", "╰────────╯", "  ? for shortcuts"]
        typed, edits = [], []
        nightmux.inject = lambda s, t: (typed.append(t), True)[1]   # typed it
        nightmux.api = lambda c, m, **kw: edits.append((m, kw)) or {}
        cfg["topics"], cfg["verbose"] = {"1": "s"}, []
        screen[:] = ["● done", "⚠ Our servers are experiencing high traffic right now, please try again in a minute. "
                     "(UNAVAILABLE (code 503): No capacity available for model gemini-pro-agent on the server)"] + box
        st = state["s"] = {"asked_at": time.time(), "asked_msgs": [("1", 77)], "calls": 0, "calls_warned": False,
                           "changed": time.time(), "echo": {"and again"}, "last": "task for gemini",
                           "last_at": time.time(), "mode": "idle", "prev": list(screen), "prog_at": 0.0,
                           "prog_text": "", "queue": [], "ran": True, "react": None, "scr": list(screen),
                           "sent": list(screen), "snap": None, "spend": [], "turns": [time.time()] * 2,
                           "why": "trace=False prev=False mode=idle active=False"}

        order, gate, ran = [], threading.Event(), threading.Event()

        def slow(c, s, l, a, upd):     # topic 1's first update hangs until released
            gate.wait(5) if upd["update_id"] == 1 else None
            order.append(upd["update_id"])
            ran.set() if upd["update_id"] == 3 else None

        nightmux.process = slow
        acks = nightmux.Acks()
        for uid, tp in ((1, 1), (2, 1), (3, 2)):
            nightmux.dispatch(cfg, state, threading.Lock(), set(),
                     {"update_id": uid, "message": {"message_thread_id": tp}}, acks)
        assert ran.wait(5), "a slow topic blocked a different one"
        assert order == [3], order          # 1 is hung, and 2 waits behind it in order
        assert nightmux.load_offset() is None        # ...so nothing is acked past the hung one
        gate.set()
        for _ in range(50):
            if len(order) == 3:
                break
            time.sleep(0.1)
        assert order == [3, 1, 2], order    # per topic in order, across topics in parallel
        assert nightmux.load_offset() == 4
        os.remove(nightmux.OFFSET_PATH)
