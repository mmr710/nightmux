"""test_pairing: cut from the old monolithic selfcheck() (stubbed part)."""
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


def test_dashboard_management_and_cross_site_posts():
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
        # Dashboard management: a new project is a Telegram topic + folder + session;
        # an agent joins the bench without switching; close stops its sessions,
        # unbinds and closes the Telegram topic, and leaves the files.
        mcalls_, killed_, up_ = [], [], set()

        def fake_api(c, method, **kw):
            mcalls_.append((method, kw))
            return {"ok": True, "result": {"message_thread_id": 321}} if method == "createForumTopic" else {"ok": True}
        with tempfile.TemporaryDirectory() as mr_, nightmux.stubbed(
                api=fake_api, spawn=lambda n, *a: up_.add(n), save_cfg=lambda c: None,
                has_session=lambda n: n in up_,
                send=lambda *a, **k: None, tmux=lambda *a: killed_.append(a)):
            mcfg_, mst_, mlk_ = {"chat_id": -9, "token": "t", "topics": {}, "projects_root": mr_}, {}, threading.Lock()
            ok_, msg_, t_ = nightmux.topic_new(mcfg_, mst_, mlk_, "Habit tracker", "habit-tracker", "", "claude",
                                      idea="streaks")
            assert ok_ and t_ == "321" and mcfg_["topics"]["321"] == "habit-tracker", msg_
            assert os.path.isdir(os.path.join(mr_, "habit-tracker", ".git"))
            assert mcfg_["topic_names"]["321"] == "Habit tracker" and mcfg_["goals"]["321"]
            assert "streaks" in mst_["habit-tracker"]["queue"][0]
            assert not nightmux.topic_start(mcfg_, mst_, mlk_, "9", "bad name", "", "claude")[0]
            ok_, msg_ = nightmux.topic_agent(mcfg_, mst_, mlk_, "321", "codex", False)
            assert ok_ and mcfg_["topics"]["321"] == "habit-tracker" \
                and mcfg_["bench"]["321"]["codex"] == "habit-tracker-codex", msg_
            ok_, msg_ = nightmux.topic_close(mcfg_, mst_, mlk_, "321")
            assert ok_ and "321" not in mcfg_["topics"] and "321" not in (mcfg_.get("goals") or {})
            assert {a[2] for a in killed_ if a[0] == "kill-session"} == {"habit-tracker", "habit-tracker-codex"}
            assert mcalls_[-1][0] == "closeForumTopic" and os.path.isdir(os.path.join(mr_, "habit-tracker"))
        # ...and a page from another site cannot drive it: no X-Nightmux header, 403.
        try:
            urllib.request.urlopen(urllib.request.Request(
                f"http://127.0.0.1:{port_}/api/topic/new", data=b"{}", method="POST"))
            assert False, "accepted without the header"
        except urllib.error.HTTPError as e:
            assert e.code == 403
        # Same for typing into a topic: text/plain is a "simple" cross-site POST.
        try:
            urllib.request.urlopen(urllib.request.Request(
                f"http://127.0.0.1:{port_}/topic/321", data=b"rm -rf ~", method="POST"))
            assert False, "typed into a topic without the header"
        except urllib.error.HTTPError as e:
            assert e.code == 403


def test_pairing_page_and_qr():
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
        # Pairing page and its QR: finder patterns in the corners, quiet zone, sized by length.
        assert "Open in app" in urllib.request.urlopen(f"http://127.0.0.1:{port_}/app").read().decode()
        qsvg_ = urllib.request.urlopen(f"http://127.0.0.1:{port_}/qr.svg?d=https%3A%2F%2Fbox.ts.net%2Fapp").read()
        assert qsvg_.startswith(b"<svg") and b"M4,4h1" in qsvg_


def test_terminal_qr_matches_matrix():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # The terminal QR is the same matrix, module for module, inside a light border.
        qt_ = [[{" ": (1, 1), "▄": (1, 0), "▀": (0, 1), "█": (0, 0)}[c] for c in l]
               for l in nightmux.qr_text("https://box.ts.net/app").split("\n")]
        back_ = [[bool(c[k]) for c in row] for row in qt_ for k in (0, 1)]
        assert [r[2:-2] for r in back_[2:2 + len(nightmux.qr_matrix("https://box.ts.net/app"))]] \
            == nightmux.qr_matrix("https://box.ts.net/app")
        serve_ = json.dumps({"Web": {"box.ts.net:443": {"Handlers": {
            "/": {"Proxy": "http://127.0.0.1:9090"}, "/apk": {"Proxy": "http://127.0.0.1:9091"}}},
            "box.ts.net:8443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:7000"}}}}})
        assert nightmux.phone_url({}, serve_) == "https://box.ts.net"
        assert nightmux.phone_url({"webhook_port": 7000}, serve_) == "https://box.ts.net:8443"
        assert nightmux.phone_url({"webhook_port": 9091}, serve_) is None     # only under /apk
        assert nightmux.phone_url({}, "") is None and nightmux.phone_url({}, "{}") is None
        qm_ = nightmux.qr_matrix("https://box.ts.net/app")
        assert len(qm_) == 25 and qm_[0][:7] == [True] * 7 and qm_[1][1:6] == [False] * 5
        assert len(nightmux.qr_matrix("x" * 200)) == 53 and len(nightmux.qr_matrix("")) == 21


def test_terminal_qr_and_phone_pairing():
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
        # Terminal QR and phone pairing
        qt_ = nightmux.qr_text("https://box.ts.net/app")
        assert "▄" in qt_ or "▀" in qt_ or "█" in qt_
        code_ = nightmux.new_pairing_code()
        assert code_ and len(code_) >= 16
        tok_ = nightmux.redeem_pairing_code(code_)
        assert tok_ and nightmux.is_paired_token(tok_)
        assert nightmux.redeem_pairing_code(code_) is None   # one-time use

        code2_ = nightmux.new_pairing_code()
        pair_res_ = urllib.request.urlopen(f"http://127.0.0.1:{port_}/pair?code={code2_}")
        assert pair_res_.status == 200
        cookie_hdr_ = pair_res_.headers.get("Set-Cookie", "")
        assert "nm_auth=" in cookie_hdr_

        conn_ = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port_}/api/connect").read().decode())
        assert "paired_count" in conn_ and conn_["paired_count"] >= 1

        rev_req_ = urllib.request.Request(f"http://127.0.0.1:{port_}/api/pair/revoke", data=b"{}",
                                          headers={"X-Nightmux": "1"}, method="POST")
        rev_res_ = json.loads(urllib.request.urlopen(rev_req_).read().decode())
        assert rev_res_["ok"] is True
        assert not nightmux.is_paired_token(tok_)

        class DummyHandler(nightmux.WebhookHandler):
            def __init__(self, ip, headers=None, path="/"):
                self.client_address = (ip, 12345)
                self.headers = headers or {}
                self.path = path
                self.status = None
                self.sent_headers = {}
                self.written = b""
            def send_response(self, code):
                self.status = code
            def send_header(self, k, v):
                self.sent_headers[k] = v
            def end_headers(self):
                pass
            @property
            def wfile(self):
                class W:
                    def __init__(self, parent): self.p = parent
                    def write(self, b): self.p.written += b
                return W(self)

        assert nightmux.WebhookHandler.auth_gate(DummyHandler("127.0.0.1")) is True
        h_remote = DummyHandler("192.168.1.50")
        assert nightmux.WebhookHandler.auth_gate(h_remote) is False and h_remote.status == 401
        assert nightmux.WebhookHandler.auth_gate(DummyHandler("192.168.1.50", path="/pair?code=xyz")) is True


def test_peer_requests_secret_then_auth_gate():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        class DummyHandler(nightmux.WebhookHandler):
            def __init__(self, ip, headers=None, path="/"):
                self.client_address = (ip, 12345)
                self.headers = headers or {}
                self.path = path
                self.status = None
                self.sent_headers = {}
                self.written = b""
            def send_response(self, code):
                self.status = code
            def send_header(self, k, v):
                self.sent_headers[k] = v
            def end_headers(self):
                pass
            @property
            def wfile(self):
                class W:
                    def __init__(self, parent): self.p = parent
                    def write(self, b): self.p.written += b
                return W(self)
        # peer requests: secret checked in peer_gate, then auth_gate must not demand a cookie
        class PeerHandler(DummyHandler):
            server = type("S", (), {"cfg": {"peer_secret": "s" * 16}, "peer_only": False})()
        h_ok = PeerHandler("100.64.0.2", headers={"X-Nightmux-Secret": "s" * 16}, path="/peer/api/x")
        assert h_ok.peer_gate() and h_ok.peer and h_ok.auth_gate() is True and h_ok.status is None
        h_bad = PeerHandler("100.64.0.2", headers={"X-Nightmux-Secret": "wrong"}, path="/peer/api/x")
        assert h_bad.peer_gate() is False and h_bad.status == 403
        h_plain = PeerHandler("100.64.0.2", path="/api/topics")
        assert h_plain.peer_gate() and not h_plain.peer and h_plain.auth_gate() is False and h_plain.status == 401

        code3_ = nightmux.new_pairing_code()
        tok3_ = nightmux.redeem_pairing_code(code3_)
        assert nightmux.WebhookHandler.auth_gate(DummyHandler("192.168.1.50", headers={"Cookie": f"nm_auth={tok3_}"})) is True


def test_loopback_open_for_own_names():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        class DummyHandler(nightmux.WebhookHandler):
            def __init__(self, ip, headers=None, path="/"):
                self.client_address = (ip, 12345)
                self.headers = headers or {}
                self.path = path
                self.status = None
                self.sent_headers = {}
                self.written = b""
            def send_response(self, code):
                self.status = code
            def send_header(self, k, v):
                self.sent_headers[k] = v
            def end_headers(self):
                pass
            @property
            def wfile(self):
                class W:
                    def __init__(self, parent): self.p = parent
                    def write(self, b): self.p.written += b
                return W(self)
        # Loopback is open for this machine's own names, and only when nobody forwarded the request.
        for host_ in ("127.0.0.1:9090", "localhost", "[::1]:9090", "mybox", "box.tail1234.ts.net", "mac.local:9090"):
            assert nightmux.WebhookHandler.auth_gate(DummyHandler("127.0.0.1", headers={"Host": host_})) is True, host_
        for host_ in ("evil.example.com", "evil.example.com:9090", "localhost.evil.com", "127.0.0.1.evil.com", ":9090"):
            h_rb_ = DummyHandler("127.0.0.1", headers={"Host": host_})            # DNS rebinding
            assert nightmux.WebhookHandler.auth_gate(h_rb_) is False and h_rb_.status == 403, host_

        class OwnHost(DummyHandler):
            server = type("S", (), {"cfg": {"allowed_hosts": ["Nm.Example.com"]}})()
        assert OwnHost("127.0.0.1", headers={"Host": "nm.example.com:443"}).auth_gate() is True
        for fwd_ in ({"Tailscale-Funnel-Request": "?1"}, {"X-Forwarded-For": "8.8.8.8"},
                     {"X-Forwarded-For": "10.0.0.2, 8.8.8.8"}, {"Cf-Connecting-Ip": "2001:4860:4860::8888"},
                     {"X-Forwarded-For": "nonsense"}):       # funnel, tunnel, proxy: the peer is 127.0.0.1, the person is not
            h_px_ = DummyHandler("127.0.0.1", headers=fwd_)
            assert nightmux.WebhookHandler.auth_gate(h_px_) is False and h_px_.status == 401, fwd_
        for fwd_ in ({"X-Forwarded-For": "100.64.1.2"}, {"X-Forwarded-For": "192.168.1.9"},
                     {"X-Forwarded-For": "fd7a:115c:a1e0::1"}):    # `tailscale serve`: the tailnet is the boundary
            assert nightmux.WebhookHandler.auth_gate(DummyHandler("127.0.0.1", headers=fwd_)) is True, fwd_


def test_pairing_code_needs_login_redeem_does_not():
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
        class DummyHandler(nightmux.WebhookHandler):
            def __init__(self, ip, headers=None, path="/"):
                self.client_address = (ip, 12345)
                self.headers = headers or {}
                self.path = path
                self.status = None
                self.sent_headers = {}
                self.written = b""
            def send_response(self, code):
                self.status = code
            def send_header(self, k, v):
                self.sent_headers[k] = v
            def end_headers(self):
                pass
            @property
            def wfile(self):
                class W:
                    def __init__(self, parent): self.p = parent
                    def write(self, b): self.p.written += b
                return W(self)
        # Asking for a pairing code takes a login; redeeming one does not.
        for path_ in ("/pair", "/pair?code=", "/pair?x=1"):
            h_mint_ = DummyHandler("192.168.1.50", path=path_)
            assert nightmux.WebhookHandler.auth_gate(h_mint_) is False and h_mint_.status == 401, path_
        # ...and on the real server: the page renders (it died on a shadowed `html`), a foreign Host
        # is refused, and the pairing POSTs need the header from loopback too.
        pair_page_ = urllib.request.urlopen(f"http://127.0.0.1:{port_}/pair").read().decode()
        assert "Scan to Pair Phone" in pair_page_ and "/pair?code=" in pair_page_
        try:
            urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port_}/api/connect",
                                                          headers={"Host": "evil.example.com"}))
            assert False, "served a rebinding Host"
        except urllib.error.HTTPError as e:
            assert e.code == 403
        for path_ in ("/api/pair/code", "/api/pair/revoke"):
            try:
                urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port_}{path_}", data=b"{}",
                                                              method="POST"))
                assert False, "pairing POST without the header"
            except urllib.error.HTTPError as e:
                assert e.code == 403
