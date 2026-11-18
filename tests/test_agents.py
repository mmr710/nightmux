"""test_agents: cut from tests/selfcheck.py (stubbed part)."""
import contextlib
import json
import os
import shutil
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_update_runs_each_agents_updater():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # !update: each installed agent's own updater, versions before and after.
        # A fake agent whose updater bumps its version -- never a real installer.
        import tempfile
        ud = tempfile.mkdtemp(prefix="nightmux-selfcheck-update-")
        ver, fake, bump = (os.path.join(ud, n) for n in ("ver", "fakeagent", "bump"))
        with open(ver, "w") as f:
            f.write("1.0\n")
        with open(fake, "w") as f:
            f.write(f"#!/bin/sh\ncat {ver}\n")
        with open(bump, "w") as f:
            f.write(f"#!/bin/sh\necho 1.1 > {ver}\n")
        os.chmod(fake, 0o755), os.chmod(bump, 0o755)
        ucfg = {"agents": {"fakeagent": [fake, ""]}, "update_cmds": {"fakeagent": bump}}
        r = nightmux.update_agents(ucfg, only=["fakeagent"])
        assert r == [("fakeagent", "1.0", "1.1", None)], r
        assert "⬆️ fakeagent: 1.0 → 1.1" in nightmux.update_report(r) and "!restore" in nightmux.update_report(r)
        r = nightmux.update_agents(ucfg, only=["fakeagent"])            # already current
        assert r == [("fakeagent", "1.1", "1.1", None)], r
        assert nightmux.update_report(r) == "✓ fakeagent: 1.1"          # no relaunch nag
        ucfg["update_cmds"]["fakeagent"] = "false"             # failing updater:
        (k, b, a, e), = nightmux.update_agents(ucfg, only=["fakeagent"])  # reported, not raised
        assert e == "exit 1" and nightmux.update_report([(k, b, a, e)]) == "✗ fakeagent: exit 1"
        ucfg["update_cmds"]["fakeagent"] = ""                  # "" turns one off
        assert nightmux.update_agents(ucfg, only=["fakeagent"]) == []
        assert nightmux.update_report([]) == "no installed agent to update"
        assert nightmux.update_every({}) == 0 and nightmux.update_every({"auto_update": False}) == 0
        assert nightmux.update_every({"auto_update": True}) == 86400
        assert nightmux.update_every({"auto_update": "12h"}) == 43200
        shutil.rmtree(ud, ignore_errors=True)


def test_secrets_never_typed_queued_or_logged():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # Secrets: never typed into an agent, queued or logged; deleted from the
        # chat when the bot may. !raw is the deliberate override.
        tok = "123456789:AA" + "x" * 33
        assert nightmux.find_secret(f"here is the bot token {tok}") == "Telegram bot token"
        assert nightmux.find_secret("sk-ant-" + "a" * 30) == "Anthropic API key"
        assert nightmux.find_secret("ghp_" + "b" * 36) == "GitHub token"
        assert nightmux.find_secret("a normal prompt about tokens and keys") is None
        assert tok not in nightmux.redact(f"x {tok} y") and "[redacted]" in nightmux.redact(tok)
        gsent, ghandled, gapi = [], [], []
        gcfg = {"chat_id": -5, "topics": {}}

        def gupd(text):
            return {"message": {"message_id": 42, "message_thread_id": 3, "text": text,
                                "chat": {"id": -5}, "from": {"id": 9}}}
        with nightmux.stubbed(send=lambda c, t, x, mode="mono", buttons=None, quiet=False: gsent.append(x),
                     handle=lambda c, s, l, t, x, mid=None: ghandled.append(x),
                     api=lambda c, m, **k: gapi.append((m, k)) or {"ok": True}):
            import io
            logged = io.StringIO()
            with contextlib.redirect_stdout(logged):
                nightmux.process(gcfg, {}, threading.Lock(), {9}, gupd(f"use {tok} please"))
            assert tok[:20] not in logged.getvalue(), logged.getvalue()   # not in the journal
            assert "[redacted]" in logged.getvalue()
            assert ghandled == [], ghandled                          # never reached the agent
            assert ("deleteMessage", {"chat_id": -5, "message_id": 42}) in gapi, gapi
            assert "Telegram bot token" in gsent[-1] and "deleted from the chat" in gsent[-1]
            assert tok not in gsent[-1]
            nightmux.process(gcfg, {}, threading.Lock(), {9}, gupd(f"!raw export T={tok}"))
            assert ghandled == [f"!raw export T={tok}"], ghandled    # explicit override
            nightmux.process(gcfg, {}, threading.Lock(), {9}, gupd("fix the parser"))
            assert ghandled[-1] == "fix the parser"


def test_failover_hands_work_to_other_agent():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # Failover: a limit-held topic hands its work to another installed agent —
        # the working tree and the cut-off instruction, not a summary the limited
        # agent can't write.
        lk_ = threading.Lock()
        fcfg = {"topics": {"7": "p"}, "started": {"7": "claude"}, "dirs": {"7": "/tmp"},
                "agents": {"claude": ["/bin/sh", ""], "codex": ["/bin/sh", ""]}}
        fstate = {"p": {"queue": ["continue", "also this"], "last": "build the parser",
                        "limit_until": time.time() + 3600}}

        def fake_switch(c, s, l, t, k):
            c["topics"][t] = "p-" + k
            c.setdefault("started", {})[t] = k
            return f"→ {k} ('p-{k}')"
        fsent = []
        with nightmux.stubbed(switch_agent=fake_switch, has_session=lambda s: True,
                     save_queue=lambda s: None,
                     send=lambda c, t, x, mode="mono", buttons=None, quiet=False: fsent.append(x)):
            assert "nothing is held" in nightmux.failover(fcfg, {"p": {}}, lk_, "7", "codex")
            assert "the one that hit" in nightmux.failover(fcfg, fstate, lk_, "7", "claude")
            assert nightmux.failover(fcfg, fstate, lk_, "7", "nosuch").startswith("no nosuch installed")
            assert "!failover codex" in json.dumps(nightmux.failover_buttons(fcfg, "7", "p"))
            assert nightmux.failover_buttons(fcfg, "7", "a-benched-one") is None
            out = nightmux.failover(fcfg, fstate, lk_, "7", "codex")
            q = fstate["p-codex"]["queue"]
            assert "hit its usage limit" in q[0] and "build the parser" in q[0], q
            assert q[1:] == ["also this"] and "queue" not in fstate["p"], fstate
            assert "picks up from the working tree with 1 queued prompt(s)" in out, out
            # A refused prompt was queued as itself: carried as work, not repeated.
            fcfg["topics"]["7"], fcfg["started"]["7"] = "p", "claude"
            fstate = {"p": {"queue": ["build the parser"], "last": "build the parser",
                            "limit_until": time.time() + 3600}}
            nightmux.failover(fcfg, fstate, lk_, "7", "codex")
            q = fstate["p-codex"]["queue"]
            assert q[1:] == ["build the parser"] and "last instruction" not in q[0], q
            # "failover" in the config: unasked, once per hold, whatever the outcome.
            fcfg.update(failover="codex")
            fcfg["topics"]["7"], fcfg["started"]["7"] = "p", "claude"
            fstate = {"p": {"queue": ["continue"], "limit_until": time.time() + 3600}}
            nightmux.failover_tick(fcfg, fstate, lk_)
            assert fcfg["topics"]["7"] == "p-codex" and "auto-failover" in fsent[-1], fsent
            fcfg.update(failover="nosuch")
            fcfg["topics"]["7"], fcfg["started"]["7"] = "p", "claude"
            fstate = {"p": {"queue": ["x"], "limit_until": time.time() + 3600}}
            nightmux.failover_tick(fcfg, fstate, lk_)
            n = len(fsent)
            nightmux.failover_tick(fcfg, fstate, lk_)                         # refused once,
            assert len(fsent) == n and fstate["p"]["queue"] == ["x"]  # not every tick
