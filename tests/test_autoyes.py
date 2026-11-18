"""test_autoyes: cut from the old monolithic selfcheck() (the last part)."""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_auto_yes_opt_in_affirmative_only():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        cfg2 = {"topics": {}, "agents": {"opencode": ["opencode", "--resume"]}}
        spawned, lk = [], threading.Lock()
        nightmux.spawn = lambda n, cwd, line, cfg=None: spawned.append((n, cwd, line))
        nightmux.has_session = lambda n: False
        nightmux.start_session(cfg2, {}, lk, "9", "box ~ --sandbox", "codex")

        # auto-yes: opt-in per topic and agent, only ever the affirmative option,
        # and it gives up rather than looping.
        ycfg = {"topics": {"7": "ay"}, "bench": {"7": {"agy": "ay", "claude": "ay-c"}},
                "started": {"7": "agy"}, "chat_id": -1, "autoyes": {"7": ["agy"]}}
        assert nightmux.agent_key(ycfg, "7", "ay") == "agy" and nightmux.agent_key(ycfg, "7", "no") is None
        menu = ["Do you want to proceed?", "❯ 1. Yes", "  2. No"]
        ysent, ypress = [], []
        yst = {"ay": {"mode": "waiting"}}
        with nightmux.stubbed(visible=lambda x: menu, press=lambda s_, k_, confirm=False: ypress.append(k_),
                     pick=lambda s_, w_: None, remember=lambda *a: None,
                     send=lambda c, t, x, mode="mono", buttons=None, quiet=False: ysent.append(x)):
            nightmux.autoyes(ycfg, yst, "7", "ay")
            assert ypress == ["1"] and ysent[-1].startswith("🤖 auto-yes ay → 1"), (ypress, ysent)
            nightmux.autoyes(ycfg, yst, "7", "ay")
            assert ypress == ["1"], "answered the same screen twice inside the gap"
            # an agent the topic did not opt in for is never touched
            yst["ay-c"] = {"mode": "waiting"}
            nightmux.autoyes(ycfg, yst, "7", "ay-c")
            assert ypress == ["1"], "answered an agent that was not opted in"
            # a menu with no recognisable yes is left for a human
            yst["ay"].update(mode="waiting", autoyes_at=0)
            with nightmux.stubbed(visible=lambda x: ["Pick a model", "❯ 1. Opus", "  2. Sonnet"]):
                nightmux.autoyes(ycfg, yst, "7", "ay")
            assert ypress == ["1"], "pressed something that was not a yes"
            # ...and it stops rather than looping all night
            yst["ay"].update(mode="waiting", autoyes_at=0,
                             autoyes_hits=[time.time()] * nightmux.AUTOYES_MAX)
            n_ = len(ysent)
            nightmux.autoyes(ycfg, yst, "7", "ay")
            assert ypress == ["1"] and "auto-yes stopped" in ysent[-1], ysent[-1]
            nightmux.autoyes(ycfg, yst, "7", "ay")
            assert len(ysent) == n_ + 1, "said it was capped more than once"
            # Allow / Approve / bracketed options are recognized as affirmative
            yst["ay"].update(mode="waiting", autoyes_at=0, autoyes_hits=[])
            with nightmux.stubbed(visible=lambda x: ["Requesting permission:", "> 1. Allow once", "  2. Deny"]):
                nightmux.autoyes(ycfg, yst, "7", "ay")
            assert ypress[-1] == "1" and "auto-yes ay → 1" in ysent[-1]
            yst["ay"].update(mode="waiting", autoyes_at=0)
            with nightmux.stubbed(visible=lambda x: ["Run this command?", "> [1] Approve", "  [2] Reject"]):
                nightmux.autoyes(ycfg, yst, "7", "ay")
            assert ypress[-1] == "1" and "auto-yes ay → 1" in ysent[-1]
            # A topic that opted in for agy, bound to a session nightmux started as
            # Claude: not an agy pane because Claude is the default agent. It typed
            # 2 into Claude's prompt every few seconds, up to the hourly cap.
            n_ = len(ypress)
            yst["cl"] = {"mode": "waiting"}
            nightmux.autoyes(dict(ycfg, topics={"7": "cl"}, bench={}, started={"7": "claude"}), yst, "7", "cl")
            assert len(ypress) == n_, "answered a Claude pane for an agy opt-in"
            yst["un"] = {"mode": "waiting"}         # one nothing is known about still does
            nightmux.autoyes(dict(ycfg, topics={"7": "un"}, bench={}, started={}), yst, "7", "un")
            assert len(ypress) == n_ + 1, "the single-agent fallback stopped answering"
        assert "auto-yes on for: agy" in nightmux.handle(ycfg, yst, lk, "7", "!autoyes on")
        assert "usage" in nightmux.template_cmd({}, {}, None, "1", "") and "what?" in nightmux.template_cmd({}, {}, None, "1", "api")
        assert all("{what}" in v for v in nightmux.TEMPLATES.values())
        _vc = {}
        assert "on" in nightmux.voice_cmd(_vc, threading.Lock(), 7, "on") and _vc["voice"] == ["7"]
        assert "off" in nightmux.voice_cmd(_vc, threading.Lock(), 7, "off") and _vc["voice"] == []
        assert "usage" in nightmux.voice_cmd(_vc, threading.Lock(), 7, "x")
        _nb = nightmux.ntfy_body("t1", "needs_input", "proj", "ok?")
        assert _nb["topic"] == "t1" and _nb["priority"] == 4 and _nb["title"] == "proj: needs input"
        _nc = {}
        assert "subscribe to 'abc'" in nightmux.events_cmd(_nc, 7, "s", "ntfy abc") and _nc["events_ntfy"] == "abc"
        assert "usage" in nightmux.events_cmd(_nc, 7, "s", "ntfy bad!topic")
        nightmux.events_cmd(_nc, 7, "s", "off")
        assert "events_ntfy" not in _nc
        _led = {"proj": {str(int(time.time() // 3600)): 500, str(int(time.time() // 3600) - 1): 250}, "old": {"1": 9}}
        _rows, _days = nightmux.spend_top(_led, 7)
        assert _rows == [("proj", 750)] and sum(_days.values()) == 750, (_rows, _days)
        assert "proj" in nightmux.spend_top_report(_led, 7) and "no spend" in nightmux.spend_top_report({}, 7)
        assert nightmux.policy_hit({}, 7, "Run: rm -rf build/") and nightmux.policy_hit({}, 7, "git push origin main")
        assert not nightmux.policy_hit({}, 7, "Run: ls -la")
        assert nightmux.policy_hit({"policy": {"7": {"off": True, "deny": ["deploy"]}}}, 7, "deploy now") == "deploy"
        assert not nightmux.policy_hit({"policy": {"7": {"off": True}}}, 7, "sudo ls")
        assert "usage" in nightmux.policy_cmd({"chat_id": -1}, threading.Lock(), 7, "bogus")
        assert not (cfg2.get("autoyes") or {}), "autoyes must never be on by default"
