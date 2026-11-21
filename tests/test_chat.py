"""test_chat: cut from the old monolithic selfcheck() (the last part)."""
import json
import os
import sys
import threading
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_chat_view_logs_and_serves():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        tok = "123456789:AA" + "x" * 33
        ocfg = {"topics": {"5": "o"}, "topic_names": {"5": "proj"}, "started": {"5": "claude"},
                "bench": {"5": {"claude": "o", "codex": "o-codex", "agy": "o-agy"}}}
        ostate = {"o": {"mode": "busy", "prog_text": f"● Bash(export K={tok})", "queue": ["a"]}}
        import socket
        sock_ = socket.socket()
        sock_.bind(("127.0.0.1", 0))
        port_ = sock_.getsockname()[1]
        sock_.close()
        threading.Thread(target=nightmux.run_webhook_server, daemon=True,
                         args=(ocfg, ostate, threading.Lock(), {1}, port_)).start()
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port_}/office").read()
                break
            except OSError:
                time.sleep(0.05)


        # Chat view: both directions are logged with their buttons, a reader asks
        # only for what is new, and the page and the PWA bits are served.
        nightmux._chat.clear()
        nightmux.chat_log("5", "bot", "✅ done", nightmux.kb([[("yes", "!y s")]]))     # what send() records
        nightmux.chat_log("5", "you", "fix the cart")
        first_ = nightmux._chat["5"][0]
        assert first_["who"] == "bot" and first_["buttons"] == [[{"text": "yes", "data": "!y s", "url": None}]], nightmux._chat["5"]
        cj_ = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port_}/api/chat/5?after={first_['id']}").read())
        assert [m["text"] for m in cj_["items"]] == ["fix the cart"], cj_
        assert "message the agent" in urllib.request.urlopen(f"http://127.0.0.1:{port_}/chat?t=5").read().decode()
        assert json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port_}/manifest.json").read())["display"] == "standalone"
        for _ in range(nightmux.CHAT_KEEP + 5):
            nightmux.chat_log("5", "bot", "x")
        assert len(nightmux._chat["5"]) == nightmux.CHAT_KEEP
        nightmux._chat.clear()


def test_briefing_sections_and_command():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        # Briefing: done / waiting / limits / today, from the pieces nightmux already
        # tracks; nothing to say in a section says so in one line.
        with nightmux.stubbed(reel_caption=lambda c, s: ["game: 3 commits, +120 −14"],
                     topics_status=lambda c, s: [
                         {"topic": "1", "session": "g", "mode": "waiting", "queued": 2, "held_until": None},
                         {"topic": "2", "session": "h", "mode": "idle", "queued": 0, "held_until": time.time() + 600}],
                     windows_now=lambda st: {"claude:5h": (40, None)}, gh=lambda *a, **k: "[]"):
            nightmux._err_log[:] = [(time.time(), "1", "TypeError: x")]
            bt_ = nightmux.briefing_text({"topic_names": {"1": "Game"}, "topics": {}}, {}, time.time() - 3600)
        for part_ in ("game: 3 commits", "✋ asking you: Game", "1 production error", "claude:5h 40%",
                      "📥 queued: Game 2", "💤 held: h until"):
            assert part_ in bt_, (part_, bt_)
        nightmux._err_log.clear()
        with nightmux.stubbed(save_cfg=lambda c: None):
            bc_ = {}
            assert "07:30" in nightmux.briefing_cmd(bc_, {}, threading.Lock(), "4", "07:30")
            assert bc_["briefing"] == {"at": "07:30", "topic": "4"}
            nightmux.briefing_cmd(bc_, {}, threading.Lock(), "4", "off")
            assert "briefing" not in bc_
