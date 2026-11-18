"""test_coach: cut from tests/selfcheck.py (stubbed part)."""
import json
import os
import re
import struct
import sys
import tempfile
import threading
import time
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_prompt_coach():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # Prompt coach: vague prompts held, corrections learned, model ladder, fresh.
        assert nightmux.lint_why("fix it") and nightmux.lint_why("still broken") and nightmux.lint_why("Doesn't work")
        assert not nightmux.lint_why("no, do not do that") and not nightmux.lint_why("fix the null check in app.js")
        assert not nightmux.lint_why("add a dark mode toggle")
        ccfg_ = {"topics": {"9": "k"}, "ladder": {"9": "on"}}
        cst_, csaid_, clog_ = {"k": {"mode": "idle"}}, [], []
        with nightmux.stubbed(send=lambda c, t, x, **k: csaid_.append(x), coach_log=clog_.append,
                     agent_key=lambda c, t, s: "claude", visible=lambda s: "TypeError: x is null\nok"):
            assert nightmux.coach(ccfg_, cst_, threading.Lock(), "9", "k", "fix it") == ""
            assert nightmux._lint_hold["9"]["text"] == "fix it" and "held" in csaid_[-1]
            better = nightmux.improve_plain(ccfg_, "9", "k", "fix it")
            assert "TypeError" in better and "root cause" in better, better
            nightmux._lint_pass.add("9")
            assert nightmux.coach(ccfg_, cst_, threading.Lock(), "9", "k", "fix it") is None
            assert "9" not in nightmux._lint_pass and "9" not in nightmux._lint_hold
            note, queued = nightmux.coach_after(ccfg_, cst_, "9", "k", "rename foo to bar in utils")
            assert queued and "haiku" in note and cst_["k"]["queue"] == [
                "/model haiku", "rename foo to bar in utils"], cst_
            assert nightmux._route_last["9"] == ("light", "claude")
            cst_["k"]["queue"] = []
            assert nightmux.coach(ccfg_, cst_, threading.Lock(), "9", "k", "that's wrong, keep the old name") is None
            assert ccfg_["route_stats"]["light"]["claude"] == [0, 1] and clog_
            nightmux._route_last["9"] = ("light", "claude")
            nightmux.coach(ccfg_, cst_, threading.Lock(), "9", "k", "no, use snake_case there")
            assert cst_["k"]["queue"] == ["/model sonnet"], cst_    # two corrections: step up
            cst_["k"]["queue"], cst_["k"]["ctx_tok"] = [], 300000
            nightmux._ladder.pop("9", None)
            assert nightmux.ladder_set(ccfg_, cst_, "9", "k", 0, "t") is None      # big thread: stay put
            assert nightmux.ladder_set(ccfg_, cst_, "9", "k", 0, "t", up=True) and cst_["k"]["queue"] == ["/model sonnet"]
            cst_["k"]["queue"] = []
            nightmux.ladder_up(ccfg_, cst_, "9", "k", "x")                 # already escalated this task
            assert cst_["k"]["queue"] == [], cst_
            cst_["k"]["queue"], cst_["k"]["ctx_tok"] = [], 10000
            assert nightmux.fresh_after(ccfg_, cst_, "9", "k", "done") is None          # small: keep
            assert nightmux.fresh_after(ccfg_, cst_, "9", "k", "done", force=True)
            assert cst_["k"]["queue"] == ["/clear"], cst_
            ccfg_["fresh"] = {"9": "off"}
            assert nightmux.fresh_after(ccfg_, cst_, "9", "k", "done", force=True) is None
        nightmux._ladder.pop("9", None)
        nightmux._route_last.pop("9", None)
        nightmux._coach.pop("9", None)
        with tempfile.TemporaryDirectory() as lh_:
            os.makedirs(os.path.join(lh_, ".claude", "projects", "x"))
            rows_ = ["fix the parser in lexer.py so `tokens()` handles tabs, tests must pass",
                     "continue", "now add a cli flag", "that's wrong, it should be --tabs",
                     "add tests in test_lexer.py for the error on line 3 until they pass", "thanks"]
            with open(os.path.join(lh_, ".claude", "projects", "x", "s.jsonl"), "w") as f:
                for r_ in rows_:
                    f.write(json.dumps({"type": "user", "message": {"content": r_}},
                                       separators=(",", ":")) + "\n")
            les_ = nightmux.prompt_lessons(home=lh_)
            assert les_["n"] == 4 and les_["ok"] == 3, les_
            assert les_["feats"]["file"][0] == 1.0 and les_["winners"][0].startswith(("add tests", "fix the")), les_
            # OpenCode prompts count too: they never did, sqlite3 was used there without an import.
            import sqlite3
            os.makedirs(os.path.join(lh_, ".local", "share", "opencode"))
            ocon_ = sqlite3.connect(os.path.join(lh_, ".local", "share", "opencode", "opencode.db"))
            ocon_.executescript("CREATE TABLE message (id TEXT, session_id TEXT, time_created INTEGER, data TEXT);"
                                "CREATE TABLE part (id TEXT, message_id TEXT, data TEXT);")
            for oi_, otxt_ in enumerate(["rename the flag in cli.py to --tab-width", "add a test for it in test_cli.py"]):
                ocon_.execute("INSERT INTO message VALUES (?, 's', ?, ?)",
                              (f"m{oi_}", int(time.time() * 1000) + oi_, '{"role":"user"}'))
                ocon_.execute("INSERT INTO part VALUES (?, ?, ?)",
                              (f"p{oi_}", f"m{oi_}", json.dumps({"type": "text", "text": otxt_})))
            ocon_.commit()
            ocon_.close()
            assert nightmux.prompt_lessons(home=lh_)["n"] == les_["n"] + 1


def test_point_and_fix_photo():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        os.makedirs(nightmux.FILE_DIR, exist_ok=True)
        # Point and fix: a photo soon after a preview carries the page, its console
        # and DOM; one with no recent preview stays a plain image path.
        with nightmux.stubbed(page_probe=lambda c, u: (['Uncaught TypeError: x is null  (app.js:12)'],
                                             "<html><body>hi</body></html>")):
            nightmux._preview.clear()
            assert nightmux.point_fix({}, "3", "this", "/i.jpg") is None
            nightmux._preview["3"] = {"url": "http://127.0.0.1:5173/cart", "at": time.time()}
            pf_ = nightmux.point_fix({}, "3", "button overlaps", "/i.jpg")
            assert pf_.startswith("button overlaps") and "/i.jpg" in pf_ and "/cart" in pf_, pf_
            assert "x is null  (app.js:12)" in pf_ and "-dom.html" in pf_, pf_
            os.remove(re.search(r"Rendered DOM: (\S+)", pf_).group(1))
            nightmux._preview["3"]["at"] -= nightmux.POINT_FOR + 1
            assert nightmux.point_fix({}, "3", "", "/i.jpg") is None
            nightmux._preview.clear()
        cm_ = nightmux.CONSOLE.search('[1:2:INFO:CONSOLE(7)] "Uncaught ReferenceError: foo", source: http://h/a.js (7)')
        assert cm_ and cm_.group(1) == "Uncaught ReferenceError: foo" and cm_.group(3) == "7"


def test_night_reel_story_and_gif():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # Night reel: the busiest room is told as a story, PNG frames decode, and the
        # GIF is well formed — one image block per frame, a loop, a trailer.
        t0_ = 1_700_000_000
        recs_ = [{"t": t0_, "r": [{"topic": "1", "name": "quiet", "d": [["claude", "idle", True, 0]]},
                                  {"topic": "2", "name": "busy", "d": [["claude", "busy", True, 0],
                                                                        ["codex", "idle", False, 0]]}]},
                 {"t": t0_ + 3600, "r": [{"topic": "1", "name": "quiet", "d": [["claude", "idle", True, 0]]},
                                         {"topic": "2", "name": "busy", "d": [["claude", "limit", True, 1],
                                                                               ["codex", "busy", False, 0]]}]}]
        rname_, rfr_ = nightmux.reel_story({}, recs_, t0_, t0_ + 7200)
        assert rname_ == "busy" and len(rfr_) == nightmux.REEL_FRAMES, rname_
        assert "claude hits its limit, codex gets to work" in rfr_[-1]["o"]["caption"], rfr_[-1]["o"]
        assert nightmux.reel_story({}, [{"t": t0_, "r": recs_[0]["r"][:1]}], t0_, t0_ + 60) is None   # nobody busy
        raw_ = b"".join(bytes([1]) + bytes([10, 20, 30]) + bytes([5, 5, 5]) * 3 for _ in range(2))
        png_ = (b"\x89PNG\r\n\x1a\n" + struct.pack(">I4s", 13, b"IHDR")
                + struct.pack(">IIBBBBB", 4, 2, 8, 2, 0, 0, 0) + b"\0" * 4)
        idat_ = zlib.compress(raw_)
        png_ += struct.pack(">I4s", len(idat_), b"IDAT") + idat_ + b"\0" * 4 + struct.pack(">I4s", 0, b"IEND") + b"\0" * 4
        pw_, ph_, prow_ = nightmux.png_pixels(png_)
        assert (pw_, ph_) == (4, 2) and prow_[0][:6] == bytes([10, 20, 30, 15, 25, 35]), prow_
        g_ = nightmux.gif([(pw_, ph_, prow_)] * 3)
        assert g_[:6] == b"GIF89a" and g_.endswith(b";") and g_.count(b"!\xf9\x04") == 3
