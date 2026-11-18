"""test_schedule: cut from the old monolithic selfcheck() (the last part)."""
import os
import queue
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_at_and_scheduled_prompts():
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

        base = 1700000000                             # fixed instant: no clock races
        assert nightmux.at_epoch({}, "+2h", base) == base + 7200
        nxt = nightmux.at_epoch({}, "03:00", base)
        assert 0 < nxt - base <= 86400 and time.gmtime(nxt).tm_hour == 3
        assert nightmux.at_epoch({}, "garbage", base) is None
        st["queue"], st["sched"] = [], [
            {"at": time.time() - 1, "every": None, "text": "one-off"},
            {"at": time.time() - 1, "every": 3600, "text": "recurring"}]
        nightmux.due(cfg, state, "1", "s")
        assert st["queue"] == ["one-off", "recurring"], st["queue"]
        assert [j["text"] for j in st["sched"]] == ["recurring"]   # one-off is spent
        assert st["sched"][0]["at"] > time.time() + 3500   # rearmed from now, so a
        sched_n = len(sent)                                # daemon that was off does
        nightmux.due(cfg, state, "1", "s")                          # not fire a backlog at once
        assert len(sent) == sched_n
        assert nightmux.queue_blob({"s": st})["s"]["sched"]         # and it survives a restart
        st["queue"] = []
        out = nightmux.handle(cfg, state, threading.Lock(), "1", "!at +1h check the build")
        assert out.startswith("⏰") and st["sched"][-1]["text"] == "check the build"
        assert nightmux.handle(cfg, state, threading.Lock(), "1", "!sched").startswith("1.")
        assert nightmux.handle(cfg, state, threading.Lock(), "1", "!at nonsense").startswith("usage:")
        assert nightmux.handle(cfg, state, threading.Lock(), "1", "!sched clear") == \
            "dropped 2 scheduled prompt(s)"
        st.pop("sched")


def test_digest_schedule_reports_directly():
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

        # !digest: on demand reuses !cost/!git plumbing; scheduling rides !every's
        # epoch math, but a fired job reports directly rather than typing "!digest"
        # into the agent the way an ordinary scheduled prompt would.
        st["snap"] = {}
        out = nightmux.handle(cfg, state, threading.Lock(), "1", "!digest")
        assert out.startswith("🌙 digest · s"), out
        sched_out = nightmux.handle(cfg, state, threading.Lock(), "1", "!digest 08:00")
        assert sched_out.startswith("digest daily at") and \
            any(j.get("kind") == "digest" for j in st["sched"]), sched_out
        assert nightmux.handle(cfg, state, threading.Lock(), "1", "!digest off") == \
            "digest schedule cancelled"
        assert nightmux.handle(cfg, state, threading.Lock(), "1", "!digest off") == \
            "no digest scheduled"
        assert nightmux.handle(cfg, state, threading.Lock(), "1", "!digest nonsense") \
            .startswith("usage:")
        st["sched"] = [{"at": time.time() - 1, "every": 3600, "kind": "digest",
                        "text": "!digest", "since": time.time() - 3600}]
        st["queue"], n = [], len(sent)
        nightmux.due(cfg, state, "1", "s")
        assert st["queue"] == [] and len(sent) == n + 1     # a report, never a typed prompt
        assert sent[-1].startswith("🌙 digest · s"), sent[-1]
        assert st["sched"][0]["since"] > time.time() - 5
        assert st["sched"][0]["at"] > time.time() + 3500    # rearmed for the next window
        st.pop("sched"), st.pop("snap")


def test_shift_plan_drains_one_step_per_idle_turn():
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

        # !shift: sequential overnight plan, drained like the queue one idle turn at
        # a time — reuses drain()'s own idle/lockout gate instead of a second one.
        out = nightmux.handle(cfg, state, threading.Lock(), "1", "!shift\nfirst step\nsecond step")
        assert out.startswith("shift set: 2 step(s)") and "first step" in out, out
        assert st["shift"] == ["first step", "second step"] and st["shift_total"] == 2
        assert nightmux.handle(cfg, state, threading.Lock(), "1", "!shift").startswith("shift 0/2")
        st["mode"], t = "busy", len(typed)
        nightmux.drain(cfg, state, "1", "s")                # busy pane: a shift step never fires
        assert len(typed) == t and st["shift"] == ["first step", "second step"]
        st["mode"], n = "idle", len(sent)
        nightmux.drain(cfg, state, "1", "s")
        assert typed[-1] == "first step" and st["shift"] == ["second step"], typed
        assert sent[n].startswith("🌙 shift 1/2 → first step"), sent[n:]
        n = len(sent)
        nightmux.drain(cfg, state, "1", "s")
        assert typed[-1] == "second step"
        assert "shift" not in st and "shift_total" not in st
        assert sent[n] == "🌙 shift 2/2 → second step", sent[n:]
        assert "🌙 s shift done" in sent[n:], sent[n:]
        assert nightmux.handle(cfg, state, threading.Lock(), "1", "!shift") == \
            "no shift plan · !shift then one prompt per line"
        nightmux.handle(cfg, state, threading.Lock(), "1", "!shift one two three")  # single line: one step
        assert st["shift"] == ["one two three"], st["shift"]
        assert nightmux.handle(cfg, state, threading.Lock(), "1", "!shift clear") == \
            "shift cleared (1 step(s) dropped)"
        assert "shift" not in st
