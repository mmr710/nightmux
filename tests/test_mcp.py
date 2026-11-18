"""test_mcp: cut from the old monolithic selfcheck() (stubbed part)."""
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


def test_mcp_tools_and_live_floor():
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
        # --mcp: the tools read the daemon's own API and refuse nightmux commands.
        base_ = f"http://127.0.0.1:{port_}"
        assert "5: o" in nightmux.nm_call("list_topics", {}, base_)[0]["text"]
        with nightmux.stubbed(tmux=lambda *a: "l1\nl2\nl3", has_session=lambda s: True):
            assert nightmux.nm_call("read_terminal", {"topic": "5", "lines": 2}, base_)[0]["text"] == "l2\nl3"
        try:
            nightmux.nm_call("send_prompt", {"topic": "5", "text": "!kill"}, base_)
            raise AssertionError("a command went through MCP")
        except ValueError:
            pass
        import io
        mo_ = io.StringIO()
        nightmux.mcp_loop("nightmux", nightmux.NM_TOOLS, nightmux.nm_call, io.StringIO(json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n"), mo_)
        assert [t["name"] for t in json.loads(mo_.getvalue())["result"]["tools"]][0] == "list_topics"
        assert "terminal" in urllib.request.urlopen(f"http://127.0.0.1:{port_}/term/5").read().decode()
        dash_ = urllib.request.urlopen(f"http://127.0.0.1:{port_}/").read().decode()
        assert "keyed(" in dash_ and "/api/metrics" in dash_
        # the live floor draws from /api/topics on every tick; the chart from the daily series
        assert "floor(t)" in dash_ and "drawDesk(" in dash_ and "a.daily" in dash_ and "prefers-reduced-motion" in dash_ and "nm-fold" in dash_
        met_ = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port_}/api/metrics").read())
        assert {"server", "limits"} <= set(met_), met_
