"""test_budget: cut from the old monolithic selfcheck() (the last part)."""
import json
import os
import shutil
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_budget_ledger_warns_and_holds():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        # !budget: the ledger fills from transcript spend; 80% warns once, 100%
        # holds every agent of the topic until the period ends, off lifts it.
        bsaid_ = []
        bcfg_ = {"topics": {"3": "b"}, "bench": {"3": {"claude": "b", "codex": "b-codex"}}, "tz_offset": 0}
        bst_ = {"b": {}}
        s0_, e0_ = nightmux.budget_window(bcfg_, "day", 1760000000)
        assert e0_ - s0_ == 86400 and s0_ % 86400 == 0 and s0_ <= 1760000000 < e0_
        ws_, we_ = nightmux.budget_window(bcfg_, "week", 1760000000)
        assert time.gmtime(ws_).tm_wday == 0 and we_ - ws_ == 7 * 86400
        ms_, _ = nightmux.budget_window(bcfg_, "month", 1760000000)
        assert time.gmtime(ms_).tm_mday == 1
        old_sav_ = dict(nightmux._sav)
        nightmux._sav["d"] = {"since": 0}
        try:
            with nightmux.stubbed(save_cfg=lambda c: None, save_queue=lambda s: None, has_session=lambda s: True,
                         send=lambda c, t, x, mode="mono", buttons=None, quiet=False: bsaid_.append(x)):
                assert "no budget" in nightmux.handle(bcfg_, bst_, threading.Lock(), "3", "!budget")
                assert "usage" in nightmux.handle(bcfg_, bst_, threading.Lock(), "3", "!budget lots")
                assert "of 1.0M this day" in nightmux.handle(bcfg_, bst_, threading.Lock(), "3", "!budget 1M")
                bst_["b"]["unbilled"] = 850000
                nightmux.budget_tick(bcfg_, bst_, "3", "b")
                assert "85%" in bsaid_[-1] and "limit_until" not in bst_["b"], bsaid_
                nightmux.budget_tick(bcfg_, bst_, "3", "b")
                assert len(bsaid_) == 1                     # warned once per period
                bst_["b"]["unbilled"] = 200000
                nightmux.budget_tick(bcfg_, bst_, "3", "b")
                assert "spent its daily budget" in bsaid_[-1], bsaid_
                assert bst_["b"]["limit_until"] > time.time() and bst_["b-codex"]["limit_until"] > time.time()
                assert "hold lifted" in nightmux.handle(bcfg_, bst_, threading.Lock(), "3", "!budget off")
                assert "limit_until" not in bst_["b"] and "3" not in bcfg_["budgets"]
                assert "limit_until" not in bst_["b-codex"]          # every agent of the topic
                # A new amount already spent holds at once; a bigger one lifts it,
                # as the hold message says.
                nightmux.handle(bcfg_, bst_, threading.Lock(), "3", "!budget 1M")
                assert "spent its daily budget" in bsaid_[-1] and bst_["b"]["limit_until"] > time.time(), bsaid_
                assert "of 2.0M" in nightmux.handle(bcfg_, bst_, threading.Lock(), "3", "!budget 2M")
                assert "limit_until" not in bst_["b"] and "limit_until" not in bst_["b-codex"]
                # In dollars: each usage record at its model's list price, and a
                # model with no price at the dearest one, never free.
                d_ = tempfile.mkdtemp()
                tp_ = os.path.join(d_, "t.jsonl")
                open(tp_, "w").close()
                bst_["b"].update(tpos=0, tpath=tp_)
                assert "$0.00 of $2.00 this day" in nightmux.handle(bcfg_, bst_, threading.Lock(), "3", "!budget $2")
                rec_ = lambda m, **u: json.dumps({"message": {"model": m, "usage": u}}) + "\n"
                with open(tp_, "a") as f:
                    f.write(rec_("claude-sonnet-4-5", input_tokens=100000, output_tokens=100000))
                nightmux.tail_transcript(bst_["b"], tp_)
                nightmux.budget_tick(bcfg_, bst_, "3", "b")
                assert "90%" in bsaid_[-1] and "($1.80 of $2.00)" in bsaid_[-1], bsaid_
                with open(tp_, "a") as f:
                    f.write(rec_("claude-next", output_tokens=10000))
                nightmux.tail_transcript(bst_["b"], tp_)
                nightmux.budget_tick(bcfg_, bst_, "3", "b")
                assert "budget: $2.30 of $2.00" in bsaid_[-1] and nightmux.budget_line(bcfg_, "3") == "$2.30 of $2.00 this day"
                shutil.rmtree(d_)
                assert "hold lifted" in nightmux.handle(bcfg_, bst_, threading.Lock(), "3", "!budget off")
                nightmux.spend_note("b", 5, now=time.time() - 40 * 86400)
                assert len(nightmux.sav_data()["spent"]["b"]) == 2   # added, then pruned on the next note
                nightmux.spend_note("b", 5)
                assert len(nightmux.sav_data()["spent"]["b"]) == 1, nightmux.sav_data()["spent"]
        finally:
            nightmux._sav.update(old_sav_)


def test_stopall_holds_until_off():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        cfg2 = {"topics": {}, "agents": {"opencode": ["opencode", "--resume"]}}
        spawned, lk = [], threading.Lock()
        nightmux.spawn = lambda n, cwd, line, cfg=None: spawned.append((n, cwd, line))
        nightmux.has_session = lambda n: False
        nightmux.start_session(cfg2, {}, lk, "9", "box ~ --sandbox", "codex")

        # !stopall interrupts what is working, holds the rest, and only !stopall
        # off lifts it: not a usage window that resets.
        xkeys_ = []
        xcfg_ = {"topics": {"1": "x1", "2": "x2"}, "bench": {"1": {"claude": "x1", "codex": "x1-codex"}}}
        xst_ = {"x1": {"mode": "busy"}, "x2": {"mode": "idle", "queue": ["q"], "limit_until": time.time() - 1}}
        with nightmux.stubbed(save_queue=lambda s: None, has_session=lambda s: True, agentless=lambda s: False,
                     visible=lambda s: [s], pane_state=lambda l: "busy" if l == ["x1"] else "idle",
                     tmux=lambda *a: xkeys_.append(a) or "", snapshot_repo=lambda s: None,
                     inject=lambda s, t: xkeys_.append(("inject", s, t)) or True,
                     send=lambda c, t, x, mode="mono", buttons=None, quiet=False: None):
            out_ = nightmux.handle(xcfg_, xst_, threading.Lock(), "2", "!stopall")
            assert "stopped 3: x1 (interrupted), x1-codex, x2" in out_, out_
            assert xkeys_ == [("send-keys", "-t", nightmux.tgt("x1"), "C-c")], xkeys_
            assert "!stopall off" in nightmux.send_prompt(xcfg_, xst_, "1", "x1", "more") and xst_["x1"]["queue"] == ["more"]
            nightmux.drain(xcfg_, xst_, "2", "x2")
            assert len(xkeys_) == 1 and "limit_until" not in xst_["x2"], xkeys_   # the window reset; still held
            assert nightmux.queue_blob(xst_)["x1-codex"] == {"stop_hold": True}            # and kept across a restart
            assert "3 session(s) go again" in nightmux.handle(xcfg_, xst_, threading.Lock(), "2", "!stopall off")
            nightmux.drain(xcfg_, xst_, "2", "x2")
            assert xkeys_[-1] == ("inject", "x2", "q"), xkeys_
        cfg2["topics"].pop("9")                      # the session died; resume the topic
        nightmux.handle(cfg2, {}, lk, "9", "!resume")
        assert spawned[-1][2] == "codex resume --last", spawned[-1]   # not claude's flag
        nightmux.handle(cfg2, {}, lk, "9", "!resume aider")   # an explicit agent still wins
        assert spawned[-1][2] == "aider --restore-chat-history", spawned[-1]
        nightmux.handle(cfg2, {}, lk, "77", "!opencode side")
        assert spawned[-1][2] == "opencode", spawned[-1]
