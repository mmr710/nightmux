"""test_builds: cut from the old monolithic selfcheck() (stubbed part)."""
import json
import os
import socket
import sys
import tempfile
import threading
import time
import urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_android_builds_and_apk():
    with isolated(nightmux):
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # Android: which build runs where, the newest APK outside intermediates, and
        # point-and-fix on a phone screen carries its activity and logcat errors.
        with tempfile.TemporaryDirectory() as ad_:
            assert nightmux.apk_build_cmd(ad_) == (None, None)
            os.makedirs(os.path.join(ad_, "android", "app", "build", "outputs", "apk", "debug"))
            open(os.path.join(ad_, "android", "gradlew"), "w").close()
            assert nightmux.apk_build_cmd(ad_) == (["sh", "./gradlew", "assembleDebug", "--console=plain"],
                                          os.path.join(ad_, "android"))
            os.makedirs(os.path.join(ad_, "android", "app", "build", "intermediates"))
            for rel_ in ("android/app/build/intermediates/x.apk",
                         "android/app/build/outputs/apk/debug/app-debug.apk"):
                open(os.path.join(ad_, rel_), "w").close()
            assert nightmux.newest_apk(ad_).endswith("app-debug.apk")


def test_build_past_limit_stopped_whole():
    with isolated(nightmux):
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # A build past its limit is stopped whole, children included.
        with tempfile.TemporaryDirectory() as at_:
            with open(os.path.join(at_, "gradlew"), "w") as f:
                f.write("#!/bin/sh\nsleep 30 &\necho $! > child.pid\nwait\n")
            asaid_ = []
            with nightmux.stubbed(send=lambda c, t, x, mode="mono", buttons=None, quiet=False: asaid_.append(x)):
                nightmux.apk_start({"apk_timeout": 1}, {}, "77", None, at_, False)
                for _ in range(200):
                    if "77" not in nightmux._apk_busy:
                        break
                    time.sleep(0.05)
            assert "stopped" in asaid_[-1], asaid_
            with open(os.path.join(at_, "child.pid")) as f:
                cpid_ = int(f.read())
            time.sleep(0.2)
            try:
                os.kill(cpid_, 0)
                with open(f"/proc/{cpid_}/stat") as f:
                    assert f.read().split(")")[1].split()[0] == "Z", "build child survived"
            except (OSError, FileNotFoundError):
                pass                                   # gone: what we want
        with nightmux.stubbed(adb=lambda *a, **k: ("  mResumedActivity: ActivityRecord{1 u0 com.x/.CartActivity t9}"
                                         if "dumpsys" in a else "E/Cart: NullPointerException")):
            af_ = nightmux.android_fix("cart overlaps", "/i.jpg", "100.1.2.3:5555")
            assert "com.x/.CartActivity" in af_ and "NullPointerException" in af_ and "/i.jpg" in af_


def test_desktop_mcp_initialize_list_call():
    with isolated(nightmux):
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # Desktop MCP: initialize, list, a failing call is an error result (not a
        # crash), notifications get no reply.
        import io
        mout_ = io.StringIO()
        with nightmux.stubbed(desktop_shot=lambda: None):
            nightmux.mcp_desktop(io.StringIO("\n".join(json.dumps(x) for x in (
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "screenshot"}},
                {"jsonrpc": "2.0", "id": 4, "method": "nope"}))), mout_)
        mr_ = [json.loads(l) for l in mout_.getvalue().splitlines()]
        assert [r["id"] for r in mr_] == [1, 2, 3, 4], mr_
        assert mr_[0]["result"]["protocolVersion"] == "2025-03-26"
        assert {t["name"] for t in mr_[1]["result"]["tools"]} >= {"screenshot", "click", "type", "key"}
        assert mr_[2]["result"]["isError"] and "!desktop" in mr_[2]["result"]["content"][0]["text"]
        assert mr_[3]["error"]["code"] == -32601
        assert nightmux.tool_cmd({}, "desktop")[-1] == "--mcp-desktop"


def test_deploy_preview_bot_comment():
    with isolated(nightmux):
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # Deploy previews: a bot's comment is a preview link, not review feedback.
        assert nightmux.is_bot("vercel[bot]") and nightmux.is_bot("netlify") and not nightmux.is_bot("alice")
        assert nightmux.pr_previews("/", "abc", [{"context": "netlify/site/deploy-preview", "state": "SUCCESS",
                                         "targetUrl": "https://deploy-preview-7--x.netlify.app"}],
                           ["Preview: https://x-git-fix-me.vercel.app)."]) == \
            ["https://deploy-preview-7--x.netlify.app", "https://x-git-fix-me.vercel.app"]


def test_error_feed_sentry_and_plain():
    with isolated(nightmux):
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
                urllib.request.urlopen(f"http://127.0.0.1:{port_}/office").read().decode()
                break
            except OSError:
                time.sleep(0.05)
        # Error feed: Sentry's internal-integration shape and a plain one parse; a
        # repeat is dropped; ask mode is a button, auto queues; wrong key is 403.
        e_ = nightmux.error_parse({"data": {"issue": {"id": "42", "web_url": "https://s.io/i/42"},
                                   "event": {"title": "TypeError: x is undefined", "culprit": "cart.js in add",
                                             "level": "error", "exception": {"values": [{"stacktrace": {
                                                 "frames": [{"filename": "lib.js", "lineno": 1, "in_app": False},
                                                            {"filename": "cart.js", "lineno": 9,
                                                             "function": "add", "in_app": True}]}}]}}}})
        assert e_["frames"] == ["cart.js:9 in add"] and e_["id"] == "42" and e_["url"].endswith("/42"), e_
        assert nightmux.error_parse({"message": "boom", "stack": "a\nb"})["frames"] == ["a", "b"]
        esaid_ = []
        with nightmux.stubbed(send=lambda c, t, x, mode="mono", buttons=None, quiet=False: esaid_.append((x, buttons)),
                     save_cfg=lambda c: None):
            ecfg_, est_ = {"topics": {"8": "e"}, "errors": {"8": "ask"}}, {}
            nightmux._err_seen.clear()
            assert nightmux.error_in(ecfg_, est_, "8", {"title": "boom 123"})[0] == 200
            assert "!errors fix" in esaid_[-1][1] and not est_.get("e")
            assert nightmux.error_in(ecfg_, est_, "8", {"title": "boom 456"})[1] == "seen"     # same error
            ecfg_["errors"]["8"] = "auto"
            nightmux.error_in(ecfg_, est_, "8", {"title": "other"})
            assert "Reproduce it" in est_["e"]["queue"][0]
            assert nightmux.error_in(ecfg_, est_, "9", {})[0] == 404
            nightmux._err_log.clear()   # error_in appends; the next test must not see it
        ocfg["hook_key"] = "k" * 24
        for key_, want_ in (("bad", 403), ("k" * 24, 404)):
            try:
                urllib.request.urlopen(urllib.request.Request(
                    f"http://127.0.0.1:{port_}/hook/5?key={key_}", data=b"{}", method="POST"))
                got_ = 200
            except urllib.error.HTTPError as e:
                got_ = e.code
            assert got_ == want_, (key_, got_)
        ocfg.pop("hook_key")
        nightmux._err_seen.clear()
