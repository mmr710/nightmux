"""test_joining: cut from the old monolithic selfcheck() (stubbed part)."""
import json
import os
import socket
import sys
import threading
import time
import urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_invite_join_and_peer_secret():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        tok = "123456789:AA" + "x" * 33
        ocfg = {"topics": {"5": "o"}, "topic_names": {"5": "proj"}, "started": {"5": "claude"},
                "bench": {"5": {"claude": "o", "codex": "o-codex", "agy": "o-agy"}}}
        menu_ = ["Do you want to proceed?", "❯ 1. Yes", "  2. No"]
        ostate = {"o": {"mode": "busy", "prog_text": f"● Bash(export K={tok})", "queue": ["a"]},
                  "o-codex": {"mode": "waiting", "scr": menu_},
                  "o-agy": {"mode": "idle", "limit_until": time.time() + 60}}
        sock_ = socket.socket()
        sock_.bind(("127.0.0.1", 0))
        port_ = sock_.getsockname()[1]
        sock_.close()
        threading.Thread(target=nightmux.run_webhook_server, daemon=True,
                         args=(ocfg, ostate, threading.Lock(), {1}, port_)).start()
        for _ in range(100):
            try:
                page = urllib.request.urlopen(f"http://127.0.0.1:{port_}/office").read().decode()
                break
            except OSError:
                time.sleep(0.05)
        # Joining: an invite is a one-use code pointing here; /join buys the bot
        # settings and a fresh peer secret once, and registers the new peer.
        with nightmux.stubbed(save_cfg=lambda c: None):
            jcfg_ = {"token": "T", "chat_id": -1, "allow_users": [7],
                     "office_url": "https://box.ts.net/office"}
            code_, _ = nightmux.join_invite(jcfg_)
            import base64
            inv_ = json.loads(base64.urlsafe_b64decode(code_ + "=" * (-len(code_) % 4)))
            assert inv_["u"] == "https://box.ts.net" and inv_["t"] in nightmux._joins, inv_
            st_, got_ = nightmux.join_accept(jcfg_, threading.Lock(), {"t": inv_["t"], "name": "vps 2",
                                                              "url": "http://100.1.2.3:9091"})
            assert st_ == 200 and got_["token"] == "T" and got_["name"] == "vps-2", got_
            assert jcfg_["peers"]["vps-2"] == {"url": "http://100.1.2.3:9091", "secret": got_["secret"]}
            assert nightmux.join_accept(jcfg_, threading.Lock(), {"t": inv_["t"], "url": "http://x:1"})[0] == 403
            code2_, _ = nightmux.join_invite(jcfg_)
            t2_ = json.loads(base64.urlsafe_b64decode(code2_ + "=" * (-len(code2_) % 4)))["t"]
            assert nightmux.join_accept(jcfg_, threading.Lock(), {"t": t2_, "url": "file:///etc"})[0] == 400
            nightmux._joins[t2_] = time.time() - 1                      # expired
            assert nightmux.join_accept(jcfg_, threading.Lock(), {"t": t2_, "url": "http://x:1"})[0] == 403
        try:
            urllib.request.urlopen(urllib.request.Request(
                f"http://127.0.0.1:{port_}/api/servers/invite", data=b"{}", method="POST"))
            assert False, "invite without the header"
        except urllib.error.HTTPError as e:
            assert e.code == 403
        page_ = urllib.request.urlopen(f"http://127.0.0.1:{port_}/").read().decode()
        assert "+ add server" in page_ and "/api/setup" in page_


def test_hand_broken_config_named():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # A hand-broken config is named in one line: where, and the usual cause.
        try:
            json.loads('{\n "a": 1\n "b": 2\n}')
        except json.JSONDecodeError as e:
            msg_ = nightmux.bad_cfg(e)
        assert "line 3, column 2" in msg_ and "missing comma" in msg_, msg_


def test_down_peer_keeps_topics():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # A peer that is down keeps its topics on the page, marked, and is listed.
        with nightmux.stubbed(peer_call=lambda *a, **k: None, host_name=lambda c: "me"):
            dcfg_ = {"peers": {"vps2": {"url": "u", "secret": "s"}}, "remote": {"2": "vps2"},
                     "topic_names": {"2": "egx"}}
            off_ = nightmux.with_peers(dcfg_, "/api/office", {"rooms": []})
            assert off_["rooms"] == [{"topic": "2", "name": "egx · vps2", "desks": [],
                                      "server": "vps2", "offline": True}], off_
            assert off_["servers"] == [{"name": "me", "ok": True}, {"name": "vps2", "ok": False}]
            assert nightmux.with_peers(dcfg_, "/api/topics", [])[0]["unreachable"]
