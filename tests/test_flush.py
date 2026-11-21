"""test_flush: cut from the old monolithic selfcheck() (stubbed part)."""
import os
import re
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_spend_cap_counts_turn_cost():
    with isolated(nightmux):
        cfg, state, screen, sent = legacy_stubs(nightmux)
        box = ["╭────────╮", "│ > ", "╰────────╯", "  ? for shortcuts"]
        # A cap in tokens counts what the turns cost. Two greps and two hundred are
        # both "one turn"; only one of them is a loop worth interrupting.
        state.clear(), sent.clear()
        keys, cap_cfg = [], dict(cfg, spendcap="1k")
        with nightmux.stubbed(tmux=lambda *a: keys.append(a) or ""):
            state["s"] = {"spend": [(time.time(), 900.0)]}
            screen[:] = ["hello"] + box
            nightmux.flush_new(cap_cfg, state, "1", "s")
            screen[:] = ["✻ Brewing… (2s · esc to interrupt)"]
            nightmux.flush_new(cap_cfg, state, "1", "s")        # turn starts: 900 < 1000
            assert keys == [] and not any("spend cap" in x for x in sent), sent
            screen[:] = ["hello"] + box
            nightmux.flush_new(cap_cfg, state, "1", "s")        # back to idle: re-arm
            state["s"]["spend"].append((time.time(), 200.0))
            screen[:] = ["✻ Brewing… (2s · esc to interrupt)"]
            nightmux.flush_new(cap_cfg, state, "1", "s")        # 1100 >= 1000: cut it off
            assert any("hit spend cap of 1,000 base-equiv tokens (1,100 burnt)" in x
                       for x in sent), sent
            assert keys and keys[-1][-1] == "C-c", keys
            state["s"]["spend"] = [(time.time() - 400, 9e9)]   # older than the window
            screen[:] = ["hello"] + box
            nightmux.flush_new(cap_cfg, state, "1", "s")
            screen[:] = ["✻ Brewing… (2s · esc to interrupt)"]
            n = len(keys)
            nightmux.flush_new(cap_cfg, state, "1", "s")
            assert len(keys) == n, "spend outside the 5m window still counted"
        state.clear(), sent.clear()


def test_flush_scrape_progress_menus_and_nudge():
    with isolated(nightmux):
        cfg, state, screen, sent = legacy_stubs(nightmux)
        box = ["╭────────╮", "│ > ", "╰────────╯", "  ? for shortcuts"]
        twice = lambda: (nightmux.flush_new(cfg, state, "1", "s"), nightmux.flush_new(cfg, state, "1", "s"))

        screen[:] = ["Do you want to proceed?", "❯ 1. Yes", "  2. No"]
        nightmux.flush_new(cfg, state, "1", "s")   # restart with a prompt already on screen
        assert sent[-1].startswith("🟠 needs input s\n") and len(sent) == 1, sent
        state.clear(), sent.clear()

        screen[:] = ["hello"] + box
        state["s"] = {}                              # watchdog seeded it first
        nightmux.flush_new(cfg, state, "1", "s")              # baseline, nothing dumped
        assert sent == []
        screen[:] = ["hello", "answer line 1"] + box  # output replaces the old box
        nightmux.flush_new(cfg, state, "1", "s")               # first sight: not stable yet
        assert sent == []
        nightmux.flush_new(cfg, state, "1", "s")               # stable: chrome stripped
        assert sent == ["✅ s\nanswer line 1"], sent
        nightmux.flush_new(cfg, state, "1", "s")               # idle, nothing new
        assert len(sent) == 1
        screen[:] = ["hello", "answer line 1", "● two", "  ⎿  noise"] + box
        twice()                                       # tool detail dropped by default
        assert sent[-1] == "✅ s\n● two", sent[-1]

        # A pane sharing nothing with the last capture is not evidence of loss: a
        # screen that turns over wholesale looks identical to one that outran the
        # window, and everything on it really is new. Deliberately not warned about.
        n = len(sent)
        screen[:] = ["totally", "different", "content"] + box
        twice()
        assert sent[-1].startswith("✅ s\n") and "different" in sent[-1], sent[-1]

        cfg["verbose"] = ["1"]
        screen[:] = screen[:-4] + ["● three", "  ⎿  noise"] + box
        twice()
        assert "⎿  noise" in sent[-1], sent[-1]
        cfg["verbose"] = []

        screen[:] = screen[:-4] + ["Do you want to proceed?", "❯ 1. Yes", "  2. No"]
        twice()                                       # waiting prompt flagged
        assert sent[-1].startswith("🟠 needs input s\n") and "1. Yes" in sent[-1], sent[-1]
        n = len(sent)                                 # ... once, however often it redraws
        for _ in range(4):
            screen[-1] += " "                         # pane churns, question does not
            twice()
        assert len(sent) == n, sent[n:]
        screen[:] = ["● done"] + box                  # an idle frame between two menus
        twice()                                       # must not re-arm the announcement
        assert state["s"].get("asked") and sent[-1] == "✅ s\n● done", sent[-1]
        n = len(sent)
        screen[:] = ["● done", "Do you want to proceed?", "❯ 1. Yes", "  2. No"]
        twice()                                       # same question under new output
        assert len(sent) == n, sent[n:]               # ... still silent
        screen[:] = ["✻ Brewing… (2s · esc to interrupt)"]
        twice()                                       # a real turn: re-arm
        assert "asked" not in state["s"]
        state["s"].pop("prog_msg", None)               # leave the throttles as found
        state["s"]["prog_at"] = nightmux._prog_at[0] = 0
        screen[:] = ["hello", "answer line 1", "● two"] + box
        twice()

        nightmux.hooked = lambda s: True          # hook owns delivery: no scrape
        n = len(sent)
        screen[:] = ["hello", "hooked reply"] + box
        twice()
        assert len(sent) == n
        screen[:] = ["hello", "hooked reply", "Do you want to proceed?", "❯ 1. Yes"]
        twice()                                       # except prompts, which still ping
        assert sent[-1].startswith("🟠 needs input"), sent[-1]
        nightmux.hooked = lambda s: False

        screen[:] = ["x"] * (nightmux.MAX_LINES + 50) + box    # oversized flush gets trimmed
        twice()
        assert "lines trimmed" in sent[-1] and len(sent[-1].split("\n")) == nightmux.MAX_LINES + 2

        edits = []
        nightmux.api = lambda c, m, **kw: edits.append((m, kw)) or {}
        st = state["s"]
        screen[:] = ["hello", "● Read(x.py)", "✻ Brewing… (3s · esc to interrupt)"]
        twice()                                       # busy: one live message, then edits
        assert sent[-1].startswith("⚙️ s\n") and "● Read(x.py)" in sent[-1], sent[-1]
        assert st["prog_msg"] == 77
        st["prog_at"] = nightmux._prog_at[0] = 0               # skip both throttles
        screen[:] = screen[:-1] + ["● Bash(ls)", "✻ Brewing… (9s · esc to interrupt)"]
        twice()
        assert edits[-1][0] == "editMessageText" and "Bash(ls)" in edits[-1][1]["text"]
        st["prog_at"] = nightmux._prog_at[0] = 0
        twice()                                       # unchanged pane: no wasted edit
        assert len(edits) == 1
        screen[:] = ["hello", "● Read(x.py)", "● Bash(ls)", "● done"] + box
        twice()                                       # turn over: message id released
        assert "prog_msg" not in st and sent[-1].startswith("✅ s\n")

        screen[:] = ["hi", "● you asked:", "line one", "line two", "● real answer"] + box
        twice()                                       # echo of a multi-line prompt
        assert "line one" in sent[-1] and "line two" in sent[-1], sent[-1]
        nightmux.remember(state, "s", "line one\nline two")    # ... unless we typed it ourselves
        screen[:] = screen[:-4] + ["line one", "line two", "● second answer"] + box
        twice()
        assert sent[-1] == "✅ s\n● second answer", sent[-1]

        big = "x" * (nightmux.BIG_PROMPT + 1)                  # too long to type: goes as a file
        spilled = nightmux.spill("s", big)
        assert spilled != big and "read that file" in spilled, spilled
        path = re.search(r"(/\S+\.md)", spilled).group(1)
        with open(path) as f:
            assert f.read() == big
        os.remove(path)
        assert nightmux.spill("s", "short") == "short"         # ... anything normal is untouched

        typed = []                                    # menu guard on plain text
        nightmux.inject = lambda s, t: (typed.append(t), True)[1]   # typed it
        cfg["topics"] = {"1": "s"}
        screen[:] = ["Do you want to proceed?", "❯ 1. Yes", "  2. No"]
        guard = nightmux.handle(cfg, state, threading.Lock(), "1", "no, do not do that")
        assert guard and "menu is open" in guard and typed == [], (guard, typed)
        nightmux.handle(cfg, state, threading.Lock(), "1", "!raw no, do not do that")
        assert typed == ["no, do not do that"], typed   # explicit override still types

        n = len(sent)                                 # unanswered prompt gets a reminder
        st = state["s"]
        st["mode"], st["wait_since"] = "waiting", time.time()
        nightmux.nudge(cfg, state, "1", "s")
        assert len(sent) == n                         # too soon
        st["wait_since"] = time.time() - nightmux.NUDGE_AFTER - 1
        nightmux.nudge(cfg, state, "1", "s")
        assert sent[-1].startswith("⏰ s has been waiting"), sent[-1]
        nightmux.nudge(cfg, state, "1", "s")                   # not every tick
        assert len(sent) == n + 1
        st["nudged"] = time.time() - nightmux.NUDGE_EVERY - 1  # due again: edit, never a second msg
        edits.clear()
        nightmux.nudge(cfg, state, "1", "s")
        assert len(sent) == n + 1 and edits[-1][0] == "editMessageText", (sent[-1], edits)
        assert edits[-1][1]["message_id"] == st["nudge_msg"] == 77
        st["mode"] = "idle"
        nightmux.nudge(cfg, state, "1", "s")
        assert len(sent) == n + 1

        n, at = len(sent), time.time() + 3600          # warn before the wall, once each
        st["snap"] = {"ts": time.time(),
                      "five_hour": {"used_percentage": 82, "resets_at": at},
                      "ctx_pct": 40}
        nightmux.warn_usage(cfg, st, "1", "s")
        assert sent[-1].startswith("🔶 5-hour limit 82% used"), sent[-1]
        nightmux.warn_usage(cfg, st, "1", "s")                  # same threshold: silent
        assert len(sent) == n + 1
        st["snap"]["five_hour"]["used_percentage"] = 91
        nightmux.warn_usage(cfg, st, "1", "s")                  # next threshold: speaks once
        assert sent[-1].startswith("🔶 5-hour limit 91%") and len(sent) == n + 2
        nightmux.warn_usage(cfg, state.setdefault("other", {"snap": st["snap"]}), "9", "other")
        assert len(sent) == n + 2                      # account-wide: no second topic
        st["snap"]["five_hour"]["resets_at"] = at + 18000
        nightmux.warn_usage(cfg, st, "1", "s")                  # new window: warnings re-arm
        assert sent[-1].startswith("🔶 5-hour limit 91%") and len(sent) == n + 3
        held, n = dict(nightmux._warned), len(sent)             # a restart mid-window
        nightmux._warned.clear()
        nightmux._warned.update(nightmux.load_warned())                  # ...reads back what it said
        assert nightmux._warned == held, (nightmux._warned, held)
        nightmux.warn_usage(cfg, st, "1", "s")                  # ...and does not say it again
        assert len(sent) == n
        nightmux._warned.clear()                                # nothing on disk: back to silence
        os.remove(nightmux.warned_path())
        assert nightmux.load_warned() == {}
        state.pop("other"), nightmux._warned.clear()
