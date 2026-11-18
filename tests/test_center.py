"""test_center: cut from the old monolithic selfcheck() (the last part)."""
import os
import queue
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_center_binds_to_every_session_and_points_plain_text():
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

        # !center: binds a topic to control every session, never to one of them.
        assert cfg.get("center_topic") is None
        out = nightmux.handle(cfg, state, threading.Lock(), "501", "!center")
        assert out == "this topic is now the command center — try !board", out
        assert cfg["center_topic"] == "501" and "501" not in cfg["topics"]
        out2 = nightmux.handle(cfg, state, threading.Lock(), "502", "!center")
        assert out2 == "command center moved here from topic 501", out2
        assert cfg["center_topic"] == "502" and "502" not in cfg["topics"]
        # A center topic controls, it does not converse — plain text and an
        # unrecognised command both point at !board instead of erroring or typing.
        assert nightmux.handle(cfg, state, threading.Lock(), "502", "hello there") == \
            "this topic controls every session — try !board"
        assert nightmux.handle(cfg, state, threading.Lock(), "502", "!bogus") == \
            "this topic controls every session — try !board"
        assert nightmux.handle(cfg, state, threading.Lock(), "502", "!center off") == \
            "command center off"
        assert cfg.get("center_topic") is None
        assert nightmux.handle(cfg, state, threading.Lock(), "502", "!center off") == \
            "no command center was set"


def test_board_reuses_status():
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

        # !board reuses !status's own classification rather than reclassifying.
        board = nightmux.handle(cfg, state, threading.Lock(), "1", "!board")
        assert nightmux.status_report(cfg, state) in board, board


def test_all_fan_out_skips_readonly_and_digest_loops_topics():
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

        # !all: fan-out reuses send_prompt, echoes who it hit before sending, and
        # a readonly-bound or missing target is skipped, never typed into.
        cfg["topics"]["9"] = "other"
        state.setdefault("other", {})
        assert nightmux.handle(cfg, state, threading.Lock(), "1", "!all").startswith("usage:")
        n, sent_n = len(typed), len(sent)
        out3 = nightmux.handle(cfg, state, threading.Lock(), "1", "!all s,other broadcast one")
        assert out3 is None
        echo = sent[sent_n]
        assert echo.startswith("📣 !all → ") and "s" in echo and "other" in echo, echo
        assert typed[n:] == ["broadcast one", "broadcast one"], typed[n:]
        cfg["modes"] = {"9": "readonly"}
        n, sent_n = len(typed), len(sent)
        nightmux.handle(cfg, state, threading.Lock(), "1", "!all --all skip-ro")
        echo2 = sent[sent_n]
        head, _, tail = echo2.partition("\n(skipped:")
        assert "other" not in head and "s" in head, echo2
        assert "other (read-only)" in tail, echo2
        assert typed[n:] == ["skip-ro"], typed[n:]        # only s got it
        cfg.pop("modes")
        n, sent_n = len(typed), len(sent)
        nightmux.handle(cfg, state, threading.Lock(), "1", "!all bogus,s hi-there")
        echo3 = sent[sent_n]
        assert "bogus (not bound)" in echo3 and "s" in echo3.split("\n")[0], echo3
        assert typed[n:] == ["hi-there"], typed[n:]
        out4 = nightmux.handle(cfg, state, threading.Lock(), "1", "!all bogus2 nope")
        assert out4.startswith("nothing to send to"), out4

        # !digest from the command center loops every bound topic instead of one.
        nightmux.handle(cfg, state, threading.Lock(), "1", "!center")
        assert cfg["center_topic"] == "1"
        state["s"]["snap"], state["other"]["snap"] = {}, {}
        dig = nightmux.handle(cfg, state, threading.Lock(), "1", "!digest")
        assert dig.count("🌙 digest ·") == 2 and "s" in dig and "other" in dig, dig
        assert nightmux.handle(cfg, state, threading.Lock(), "1", "!digest 09:00") == \
            "!digest here is report-only — schedule it from each session's own topic"
        state["s"].pop("snap"), state["other"].pop("snap")
        cfg["topics"].pop("9"), state.pop("other")
