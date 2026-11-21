"""test_wrapped: cut from the old monolithic selfcheck() (stubbed part)."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_wrapped_private_until_shared():
    with isolated(nightmux):
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # !wrapped is private: nothing leaves the machine until share is tapped.
        class _Now:
            def __init__(self, target, daemon=True):
                self.go = target

            def start(self):
                self.go()
        ups, outs = [], []
        with nightmux.stubbed(browser_bin=lambda c: "chromium", render_html=lambda *a: b"png",
                     wrapped_page=lambda *a, **k: "",
                     wrapped_data=lambda c, d: {"cells": [("3", "turns")], "insights": [], "split": []},
                     send_file=lambda *a, **k: outs.append(k.get("buttons")),
                     send=lambda *a, **k: outs.append(k.get("buttons")),
                     upload_media=lambda *a: ups.append(a) or "https://uguu.se/x.png",
                     threading=type("T", (), {"Thread": _Now})):
            nightmux.wrapped_cmd({}, 1, "7")
            assert ups == [] and "!wrapped share 7" in outs[-1], outs
            nightmux.wrapped_cmd({}, 1, "share 7")
            assert len(ups) == 1 and "Share on X" in outs[-1], outs
        rcfg_ = {"topics": {"4": "r"}, "started": {"4": "claude"}, "route": {"4": "auto"},
                 "bench": {"4": {"claude": "r", "codex": "r-codex"}}}
        rst_ = {"r": {"mode": "idle", "changed": time.time() - 3600}}
        switched_ = []

        def fake_switch(c, st, l, t, k):
            switched_.append(k)
            c["topics"][t], c["started"][t] = c["bench"][t][k], k
        with nightmux.stubbed(has_session=lambda n: True, switch_agent=fake_switch, coach_log=lambda r: None):
            assert nightmux.route(rcfg_, rst_, threading.Lock(), "4", "r", "add a settings page") is None
            rst_["r"]["changed"] = time.time()
            assert nightmux.route(rcfg_, rst_, threading.Lock(), "4", "r", "rename x to y") is None   # mid-task
            rst_["r"]["changed"] = time.time() - 3600
            rst_["r"]["ctx_tok"] = 90000
            assert nightmux.route(rcfg_, rst_, threading.Lock(), "4", "r", "rename x to y") is None   # big thread
            rst_["r"]["ctx_tok"] = 5000
            ro_ = nightmux.route(rcfg_, rst_, threading.Lock(), "4", "r", "rename x to y")
            assert ro_ and ro_[0] == "r-codex" and "light" in ro_[1] and switched_ == ["codex"], ro_
            nightmux.route_learn(rcfg_, "4", -1)
            assert "4" not in nightmux._route_last              # one outcome per task
            nightmux._route_last["4"] = ("light", "codex")
            nightmux.route_learn(rcfg_, "4", -1)
            assert nightmux.route_pick(rcfg_, "light", {"claude": "r", "codex": "r-codex"}) == "claude"
            rcfg_["route_stats"] = {"light": {"codex": [9, 10], "claude": [1, 10]}}
            assert nightmux.route_pick(rcfg_, "light", {"claude": "r", "codex": "r-codex"}) == "codex"
        assert json.loads(nightmux.kb([[("x", "https://a.b")]]))["inline_keyboard"][0][0] == {"text": "x", "url": "https://a.b"}
        nightmux._sav["d"] = {"since": 0}
        sst_ = {"ctx_tok": 150000}
        nightmux.sav_ctx(sst_, 40000)
        nightmux.sav_turn({}, sst_)
        nightmux.sav_turn({}, sst_)
        assert nightmux._sav["d"]["tokens"] == 220000 and nightmux._sav["d"]["drops"] == 1 and "220k tokens" in nightmux.saved_report()
        qst_, qcfg_ = {"q": {}}, {"topics": {"3": "q"}, "tools": {"3": ["browser"]}}
        assert "daily at" in nightmux.qa_cmd(qcfg_, qst_, threading.Lock(), "3", "q", "03:00 http://localhost:3000")
        assert qst_["q"]["sched"][0]["every"] == 86400 and "localhost:3000" in qst_["q"]["sched"][0]["text"]
        assert "daily at" in nightmux.qa_cmd(qcfg_, qst_, threading.Lock(), "3", "q", "")
        assert nightmux.qa_cmd(qcfg_, qst_, threading.Lock(), "3", "q", "off") and not qst_["q"]["sched"]
        with nightmux.stubbed(analyze_chats=lambda d: {"agents": {"claude": {"prompts": 4}}}):
            lb_ = nightmux.leaderboard_cmd("")
            assert '"prompts_30d": 4' in lb_ and "would add" in lb_, lb_
        pcfg_ = {"public": {"token": "abc"}}
        assert nightmux.public_ok(pcfg_, "abc") and not nightmux.public_ok(pcfg_, "abd") and not nightmux.public_ok({}, "")
        with nightmux.stubbed(office_snapshot=lambda c, s, usage=True: {"rooms": [{"topic": "1", "name": "x", "desks": [
                {"agent": "claude", "state": "busy", "screen": ["secret"], "doing": "d"}]}], "usage": {}}):
            ps_ = nightmux.public_snapshot(pcfg_, {})
            assert ps_["rooms"][0]["desks"][0]["state"] == "busy" and "secret" not in json.dumps(ps_)
        dof_ = os.path.join(os.path.dirname(os.path.abspath(nightmux.__file__)), "docs", "office.html")
        if os.path.exists(dof_):                       # the Pages demo is this page, kept in step
            assert "else if (!DEMO && !REEL) { poll(); setInterval(poll, 2000); }" in nightmux.OFFICE_HTML  # live and /public both poll
        assert open(dof_).read() == nightmux.OFFICE_HTML, "docs/office.html is stale: re-export OFFICE_HTML"
        assert nightmux.transcribe({"transcribe_cmd": "echo hello"}, "/x.ogg") == "hello /x.ogg"
        assert nightmux.transcribe({}, "/x.ogg") is None or os.environ.get("NIGHTMUX_TRANSCRIBE")
        with tempfile.TemporaryDirectory() as rr_:
            g_ = ["git", "-C", rr_, "-c", "user.email=t@t", "-c", "user.name=t"]
            subprocess.run(["git", "init", "-q", rr_])
            open(os.path.join(rr_, "a.txt"), "w").write("one\n")
            subprocess.run(g_ + ["add", "."]); subprocess.run(g_ + ["commit", "-qm", "init"])
            rcf_, rst2_, rsaid_ = {"topics": {"8": "rc"}, "dirs": {"8": rr_}}, {}, []
            with nightmux.stubbed(spawn=lambda *a: None, tmux=lambda *a: "", send=lambda c, t, x, **k: rsaid_.append(x),
                         installed_agents=lambda c: ["claude", "codex"]):
                assert nightmux.race_parse(rcf_, "8", "claude,codex fix it") == (["claude", "codex"], "fix it")
                out_ = nightmux.race_cmd(rcf_, rst2_, threading.Lock(), "8", "make a.txt say two")
                assert "race: claude, codex" in out_, out_
                assert ("8", "rc-race-codex") in nightmux.watched(rcf_)
                wt_ = nightmux._race["8"]["racers"]["claude"]["wt"]
                open(os.path.join(wt_, "a.txt"), "w").write("two\n")
                for x_ in nightmux._race["8"]["racers"].values():
                    rst2_[x_["sess"]] = {"ran": True, "mode": "idle", "changed": 0}
                nightmux.race_tick(rcf_, rst2_)
                assert "race done" in rsaid_[-1] and "claude: 1 file changed" in rsaid_[-1], rsaid_
                assert "two" in nightmux.race_cmd(rcf_, rst2_, threading.Lock(), "8", "diff claude")
                assert "wins" in nightmux.race_cmd(rcf_, rst2_, threading.Lock(), "8", "pick claude")
                assert open(os.path.join(rr_, "a.txt")).read() == "two\n" and "8" not in nightmux._race
                assert not os.path.isdir(wt_)
        assert nightmux._post({}, "sendMessage", b"") == {}       # dashboard-only: never reaches the network
        seen_ = {d["state"] for t_ in range(0, 400, 5) for r in nightmux.demo_snapshot(t_)["rooms"] for d in r["desks"]}
        assert seen_ == {"busy", "idle", "limit", "waiting"}, seen_     # --demo shows every state
