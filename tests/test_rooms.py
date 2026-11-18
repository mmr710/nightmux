"""test_rooms: cut from tests/selfcheck.py (stubbed part)."""
import contextlib
import gzip
import http.client, http.server
import io
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_office_rooms_desks_and_redaction():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        tok = "123456789:AA" + "x" * 33
        # The office: a room per topic, a desk per agent, every state a real one —
        # and redacted, because this page gets opened from a phone.
        ocfg = {"topics": {"5": "o"}, "topic_names": {"5": "proj"}, "started": {"5": "claude"},
                "bench": {"5": {"claude": "o", "codex": "o-codex", "agy": "o-agy"}}}
        menu_ = ["Do you want to proceed?", "❯ 1. Yes", "  2. No"]
        ostate = {"o": {"mode": "busy", "prog_text": f"● Bash(export K={tok})", "queue": ["a"]},
                  "o-codex": {"mode": "waiting", "scr": menu_},
                  "o-agy": {"mode": "idle", "limit_until": time.time() + 60}}
        all_up = {"o": 1, "o-codex": 1, "o-agy": 1}
        with nightmux.stubbed(live_sessions=lambda: all_up, agentless=lambda s: False):
            (room,) = nightmux.office_snapshot(ocfg, ostate)["rooms"]
            desks = {d["agent"]: d for d in room["desks"]}
            assert room["name"] == "proj" and desks["claude"]["live"] and not desks["codex"]["live"]
            assert desks["claude"]["state"] == "busy" and desks["claude"]["queued"] == 1
            assert tok[:20] not in json.dumps(room) and "[redacted]" in desks["claude"]["doing"]
            assert desks["agy"]["state"] == "limit" and desks["agy"]["until"], desks["agy"]
            assert {"text": "1. Yes", "send": "!1 o-codex"} in desks["codex"]["options"]
            # ...and served: the page and its JSON on the webhook port.
            import socket
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
            api_ = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port_}/api/office").read())
            assert "nightmux office" in page and api_["rooms"][0]["topic"] == "5", api_
        with nightmux.stubbed(live_sessions=lambda: {"o": 1}, agentless=lambda s: False):
            states = {d["agent"]: d["state"] for d in nightmux.office_snapshot(ocfg, ostate)["rooms"][0]["desks"]}
            assert states == {"claude": "busy", "codex": "gone", "agy": "gone"}, states
        osent = []
        with nightmux.stubbed(send=lambda c, t, x, mode="mono", buttons=None, quiet=False: osent.append(buttons),
                     office_url_problem=lambda u: None):
            assert "tailscale serve" in nightmux.handle(dict(ocfg), {}, threading.Lock(), "5", "!office")
            nightmux.handle(dict(ocfg, office_url="https://box.ts.net/office"), {}, threading.Lock(), "5", "!office")
            assert "https://box.ts.net/office" in osent[-1], osent


def test_office_link_404_gets_the_fix():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        ocfg = {"topics": {"5": "o"}, "topic_names": {"5": "proj"}, "started": {"5": "claude"},
                "bench": {"5": {"claude": "o", "codex": "o-codex", "agy": "o-agy"}}}
        osent = []
        # A link that answers 404 (another service owns the address) gets the fix, not a button to nowhere.
        osent.clear()
        with nightmux.stubbed(send=lambda c, t, x, mode="mono", buttons=None, quiet=False: osent.append(buttons),
                     office_url_problem=lambda u: "answers HTTP 404"):
            fix_ = nightmux.handle(dict(ocfg, office_url="https://box.ts.net/office", webhook_port=9090),
                          {}, threading.Lock(), "5", "!office")
        assert not osent and "answers HTTP 404" in fix_ and "tailscale serve --bg --https=9090 9090" in fix_ \
            and '"office_url": "https://box.ts.net:9090/office"' in fix_, (osent, fix_)
        # ...found by asking the link itself: 404 and 5xx and a refused connection are answers; 401/403
        # (a login wall), a timeout or a name that does not resolve are not reasons to say it is broken.
        import io
        class Site_(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response({"/office": 200, "/gone": 404, "/auth": 403}.get(self.path, 502))
                self.send_header("Content-Length", "0")
                self.end_headers()
            def log_message(self, *a):
                pass
        site_ = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Site_)
        threading.Thread(target=site_.serve_forever, daemon=True).start()
        base_ = f"http://127.0.0.1:{site_.server_address[1]}"
        assert nightmux.office_url_problem(base_ + "/office") is None and nightmux.office_url_problem(base_ + "/auth") is None
        assert nightmux.office_url_problem(base_ + "/gone") == "answers HTTP 404"
        assert nightmux.office_url_problem(base_ + "/other") == "answers HTTP 502"
        site_.shutdown()
        site_.server_close()                                      # shutdown() stops serving; only closing the socket refuses
        assert nightmux.office_url_problem(base_ + "/office") == "refuses the connection"
        assert nightmux.office_url_problem("ftp://x/office") is None and nightmux.office_url_problem("not a url") is None


def test_office_reads_usage_off_the_lock():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        tok = "123456789:AA" + "x" * 33
        ocfg = {"topics": {"5": "o"}, "topic_names": {"5": "proj"}, "started": {"5": "claude"},
                "bench": {"5": {"claude": "o", "codex": "o-codex", "agy": "o-agy"}}}
        menu_ = ["Do you want to proceed?", "❯ 1. Yes", "  2. No"]
        ostate = {"o": {"mode": "busy", "prog_text": f"● Bash(export K={tok})", "queue": ["a"]},
                  "o-codex": {"mode": "waiting", "scr": menu_},
                  "o-agy": {"mode": "idle", "limit_until": time.time() + 60}}
        # The office must not wait on what it only reads. `agy -p /usage` takes seconds and the page is
        # asked while the daemon's lock is held: it is read on a thread, a failing agy is asked once per
        # five minutes rather than per poll, and the ticks that only want rooms skip the usage bars.
        real_sub_ = subprocess

        class AgySub_:
            def __init__(self, agy):
                self.agy, self.calls = agy, 0
            def __getattr__(self, k):
                return getattr(real_sub_, k)
            def run(self, argv, **kw):
                if argv[0] != "agy":
                    return real_sub_.run(argv, **kw)
                self.calls += 1
                return self.agy()

        def slow_agy_():
            time.sleep(.6)
            return type("R", (), {"stdout": "Gemini Models   Five Hour Limit Remaining   60%\n"
                                            "Claude and GPT models  Five Hour Limit Remaining  25%\n"})()

        def no_agy_():
            raise FileNotFoundError("agy")
        slow_ = AgySub_(slow_agy_)
        nightmux._agy_usage.update(at=0, tried=0, pct=0, claude_pct=0)
        nightmux._oc.update(tried=0, tok=0)
        with nightmux.stubbed(subprocess=slow_, live_sessions=lambda: {}):
            t_ = time.time()
            usage_ = nightmux.office_snapshot(ocfg, ostate)["usage"]
            assert time.time() - t_ < .5, "the office waited for agy"
            assert {"five_hour", "seven_day", "agy_model", "oc_model", "agy_limit", "oc_limit"} <= set(usage_), usage_
            assert "usage" not in nightmux.office_snapshot(ocfg, ostate, usage=False)
            time.sleep(1)
            assert (nightmux._agy_usage["pct"], nightmux._agy_usage["claude_pct"], slow_.calls) == (40, 75, 1), (nightmux._agy_usage, slow_.calls)
            nightmux.office_snapshot(ocfg, ostate)
            assert slow_.calls == 1                               # a fresh reading is not asked for again
        broken_ = AgySub_(no_agy_)
        nightmux._agy_usage.update(at=0, tried=0)
        with nightmux.stubbed(subprocess=broken_):
            for _ in range(5):
                nightmux.agy_limits()
            time.sleep(.3)
            assert broken_.calls == 1, broken_.calls
        nightmux._agy_usage.update(at=0, tried=time.time(), pct=0, claude_pct=0)   # nothing below needs the real agy


def test_peers_asked_together_dead_one_skipped():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # Peers are asked together, and one that just failed is not waited on again: a dead peer used to
        # put its whole timeout on every poll of the office and the dashboard, and a line in the log.
        quick_ = []

        def far_(c, n, p, b=None, timeout=10):
            time.sleep(0 if n == "c" and quick_ else .4)          # the good peer is slow once, to prove they run together
            return None if n in ("a", "b") else {"rooms": [{"topic": "9", "name": "far", "desks": []}]}
        pcfg_ = {"peers": {n_: {"url": "http://x", "secret": "s"} for n_ in "abc"}}
        with nightmux.stubbed(peer_call=far_):
            t_ = time.time()
            got_ = nightmux.peers_ask(pcfg_, "api/office")
            assert got_["a"] is None and got_["b"] is None and got_["c"]["rooms"], got_
            assert time.time() - t_ < .75, "peers are asked one after another"          # 1.2 s in turn
            quick_.append(1)
            t_ = time.time()
            assert nightmux.peers_ask(pcfg_, "api/office")["a"] is None and time.time() - t_ < .2
            for n_ in "ab":                                       # the quiet period is over: one probe, no waiting
                nightmux._peer_down[n_, "api/office"] = time.time() - nightmux.PEER_DOWN_FOR - 1
            t_ = time.time()
            nightmux.peers_ask(pcfg_, "api/office")
            assert time.time() - t_ < .2 and all(nightmux._peer_down[n_, "api/office"] > time.time() for n_ in "ab"), nightmux._peer_down
            time.sleep(.6)                                        # the probes fail: down again, from now
            assert all(nightmux._peer_down[n_, "api/office"] <= time.time() for n_ in "ab"), nightmux._peer_down
        # ...per route: a peer too old for one route answers it 404 and the rest fine. And a failure no
        # poll has looked at for a minute is asked again rather than answered from memory.
        with nightmux.stubbed(peer_call=lambda c, n, p, b=None, timeout=10: None if p == "api/agents" else {"rooms": []}):
            assert nightmux.peers_ask(pcfg_, "api/agents")["a"] is None and nightmux.peers_ask(pcfg_, "api/office")["a"] == {"rooms": []}
            nightmux._peer_down["a", "api/office"] = time.time() - 4 * nightmux.PEER_DOWN_FOR
            assert nightmux.peers_ask(pcfg_, "api/office")["a"] == {"rooms": []} and ("a", "api/office") not in nightmux._peer_down


def test_non_json_200_is_peer_down():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        pcfg_ = {"peers": {n_: {"url": "http://x", "secret": "s"} for n_ in "abc"}}
        # A 200 that is no JSON (an app that answers every path) is a peer down, not a 500 for the office.
        with nightmux.stubbed(peer_call=lambda c, n, p, b=None, timeout=10: "<!doctype html><title>other app</title>"), \
                contextlib.redirect_stderr(io.StringIO()):
            assert [s_["ok"] for s_ in nightmux.with_peers(pcfg_, "/api/office", {"rooms": []})["servers"]] == [True] + [False] * 3


def test_gzip_only_when_asked():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # gzip: only when the client asks and the body is worth it; Content-Length is the compressed size.
        class GzH_:
            def __init__(self, enc):
                self.headers = {"Accept-Encoding": enc} if enc else {}
                self.h, self.wfile = {}, io.BytesIO()
            def send_response(self, c):
                pass
            def send_header(self, k, v):
                self.h[k] = v
            def end_headers(self):
                pass
        big_ = json.dumps({"x": "abc" * 2000})
        gh_ = GzH_("gzip, deflate")
        nightmux.WebhookHandler.reply(gh_, big_, "application/json")
        raw_ = gh_.wfile.getvalue()
        assert gh_.h["Content-Encoding"] == "gzip" and int(gh_.h["Content-Length"]) == len(raw_) < len(big_) / 4
        assert gzip.decompress(raw_).decode() == big_
        gh_ = GzH_(None)
        nightmux.WebhookHandler.reply(gh_, big_, "application/json")
        assert "Content-Encoding" not in gh_.h and gh_.wfile.getvalue().decode() == big_
        gh_ = GzH_("gzip")
        nightmux.WebhookHandler.reply(gh_, "{}", "application/json")
        assert "Content-Encoding" not in gh_.h and gh_.wfile.getvalue() == b"{}"


def test_unrestarted_deploy_told_once():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # A deploy nobody restarted: told once, after it has lasted; not for the seconds an upgrade restarts in.
        stale_sent_ = []
        with nightmux.stubbed(send=lambda c, t, x, mode="mono", buttons=None, quiet=False: stale_sent_.append((t, x)),
                     BOOT_AT=time.time() + 3600):
            assert not nightmux.code_newer_than(nightmux.BOOT_AT) and nightmux.code_newer_than(0)
            nightmux.stale_tick({"topics": {"3": "s"}})
            assert nightmux._stale["since"] == 0 and not stale_sent_
        with nightmux.stubbed(send=lambda c, t, x, mode="mono", buttons=None, quiet=False: stale_sent_.append((t, x)),
                     BOOT_AT=0):
            nightmux._stale.update(since=0, told=False)
            nightmux.stale_tick({"topics": {"3": "s"}})
            assert not stale_sent_                                # just noticed
            nightmux._stale["since"] = time.time() - nightmux.STALE_AFTER - 1
            nightmux.stale_tick({"topics": {"3": "s"}})
            nightmux.stale_tick({"topics": {"3": "s"}})
            assert len(stale_sent_) == 1 and stale_sent_[0][0] == "3" and nightmux.restart_hint() in stale_sent_[0][1], stale_sent_
        nightmux._stale.update(since=0, told=False)


def test_raising_watcher_told_once():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # A watcher that raises every tick: a few log lines for 400 ticks, and its topic told once.
        wf_sent_, wf_err_ = [], io.StringIO()
        with nightmux.stubbed(send=lambda c, t, x, mode="mono", buttons=None, quiet=False: wf_sent_.append((t, x))), \
                contextlib.redirect_stderr(wf_err_):
            nightmux._watch_errs.clear()
            for _ in range(400):
                nightmux.watch_failed({}, "3", "sess", "KeyError: 'x' (f:1)")
        nightmux._watch_errs.clear()
        assert len([l for l in wf_err_.getvalue().splitlines() if l]) <= 4, wf_err_.getvalue()
        assert len(wf_sent_) == 1 and wf_sent_[0][0] == "3" and "sess" in wf_sent_[0][1], wf_sent_
