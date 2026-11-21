"""test_bridge: cut from the old monolithic selfcheck() (stubbed part)."""
import html
import json
import os
import struct
import sys
import threading
import urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_discord_slack_bridge():
    with isolated(nightmux):
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # Discord/Slack bridge: topics above Telegram's range route through
        # bridge_post, formatting and buttons translate, events become updates.
        dt_, st_t_ = str(2 ** 41 + 7), str(2 ** 62 + 9)
        assert nightmux.bridge_of("5") is None and nightmux.bridge_of(dt_) == "discord" and nightmux.bridge_of(st_t_) == "slack"
        assert nightmux.tg_md("<pre>a &lt;b&gt; &amp;</pre>", "discord") == "```\na <b> &\n```"
        assert nightmux.tg_md("<pre>a &lt;b&gt;</pre>", "slack") == "```\na &lt;b&gt;\n```"
        assert nightmux.tg_md('<b>x</b> <a href="https://u">l</a>', "discord") == "**x** [l](https://u)"
        rows_ = json.loads(nightmux.kb([[("yes", "!1"), ("site", "https://e.x")]]))["inline_keyboard"]
        assert nightmux.dc_rows(rows_) == [{"type": 1, "components": [
            {"type": 2, "style": 2, "label": "yes", "custom_id": "!1"},
            {"type": 2, "style": 5, "label": "site", "url": "https://e.x"}]}]
        assert nightmux.sl_blocks("t", rows_)[1]["elements"][0]["value"] == "!1" and "url" in nightmux.sl_blocks("t", rows_)[1]["elements"][1]
        dcalls_, scalls_, disp_ = [], [], []
        bcfg_ = {"discord": {"token": "x", "forum": "900"}, "slack": {"bot_token": "b", "app_token": "a"},
                 "chat_id": "c", "topics": {}, "slack_channels": {st_t_: "C1"}}
        ids_ = iter(range(10 ** 18, 10 ** 18 + 99))
        # api() and send() are stubbed by now; _post is where the bridge sits
        bapi_ = lambda m, **kw: nightmux._post(bcfg_, m, urllib.parse.urlencode(
            {k: v for k, v in kw.items() if v is not None}).encode())

        def fake_dapi_(c, m, path, body=None, raw_type=None):
            dcalls_.append((m, path, body))
            return {"id": str(next(ids_))} if m == "POST" else {}

        def fake_sapi_(c, m, body=None, token=None):
            scalls_.append((m, body))
            return {"ok": True, "ts": "171.0001", "channel": {"name": "shop"}}
        with nightmux.stubbed(discord_api=fake_dapi_, slack_api=fake_sapi_, save_cfg=lambda c: None,
                     dispatch=lambda c, s, l, a, u, k: disp_.append(u)):
            mid_ = bapi_("sendMessage", chat_id="c", message_thread_id=dt_, text="<pre>" + "x" * 3000
                       + "</pre>", parse_mode="HTML", reply_markup=nightmux.kb([[("ok", "!1")]]))["result"]["message_id"]
            assert [c[0] for c in dcalls_] == ["POST", "POST"] and mid_ == 10 ** 18 + 1, dcalls_
            assert dcalls_[0][2]["content"].endswith("```") and dcalls_[1][2]["content"].startswith("```")
            assert "components" in dcalls_[1][2] and "components" not in dcalls_[0][2]
            bapi_("editMessageText", chat_id="c", message_id=mid_, text="<b>done</b>", parse_mode="HTML")
            assert dcalls_[-1][0] == "PATCH" and dcalls_[-1][2]["content"] == "**done**", dcalls_[-1]
            bapi_("setMessageReaction", chat_id="c", message_id=mid_,
                  reaction=json.dumps([{"type": "emoji", "emoji": "👀"}]))
            assert dcalls_[-1][0] == "PUT" and "/reactions/" in dcalls_[-1][1]
            assert bapi_("answerCallbackQuery", callback_query_id="dc:1")["ok"]
            smid_ = bapi_("sendMessage", chat_id="c", message_thread_id=st_t_, text=html.escape("hi & bye"),
                        parse_mode="HTML", reply_markup=nightmux.kb([[("ok", "!1")]]))["result"]["message_id"]
            assert scalls_[-1][0] == "chat.postMessage" and scalls_[-1][1]["channel"] == "C1"
            assert scalls_[-1][1]["text"] == "hi &amp; bye" and scalls_[-1][1]["blocks"][1]["type"] == "actions"
            bapi_("deleteMessage", chat_id="c", message_id=smid_)
            assert scalls_[-1] == ("chat.delete", {"channel": "C1", "ts": "171.0001"})
            assert bapi_("getMe") == {}             # no Telegram token, not a bridge call
            # inbound: a new forum post names the topic, its messages and taps dispatch
            nightmux.discord_event(bcfg_, {}, None, set(), "THREAD_CREATE", {"id": dt_, "parent_id": "900", "name": "shop"})
            nightmux.discord_event(bcfg_, {}, None, set(), "MESSAGE_CREATE", {"id": "55", "channel_id": dt_,
                          "content": "fix it", "author": {"id": "77", "username": "me"},
                          "attachments": [{"url": "https://cdn/x.png"}]})
            nightmux.discord_event(bcfg_, {}, None, set(), "MESSAGE_CREATE", {"id": "56", "channel_id": "123",
                          "content": "elsewhere", "author": {"id": "77"}})
            nightmux.discord_event(bcfg_, {}, None, set(), "MESSAGE_CREATE", {"id": "57", "channel_id": dt_,
                          "content": "me again", "author": {"id": "1", "bot": True}})
            assert disp_[0]["message"]["forum_topic_created"] == {"name": "shop"} and len(disp_) == 2, disp_
            m_ = disp_[1]["message"]
            assert (m_["message_thread_id"], m_["from"]["id"], m_["text"]) == (int(dt_), 77, "fix it\nhttps://cdn/x.png")
            with nightmux.stubbed(_bridge_http=lambda *a: {}):
                nightmux.discord_event(bcfg_, {}, None, set(), "INTERACTION_CREATE", {"type": 3, "id": "9", "token": "t",
                              "channel_id": dt_, "message": {"id": "58"}, "data": {"custom_id": "!1"},
                              "member": {"user": {"id": "77"}}})
            assert disp_[-1]["callback_query"]["data"] == "!1" and disp_[-1]["callback_query"]["id"] == "dc:9"
            disp_.clear()
            nightmux.slack_event(bcfg_, {}, None, set(), {"type": "events_api", "payload": {"event": {
                "type": "message", "channel": "C9", "user": "U1", "text": "see <https://x.y|x.y> &amp; go",
                "ts": "1.2"}}})
            assert disp_[0]["message"]["forum_topic_created"] == {"name": "shop"}
            assert disp_[1]["message"]["text"] == "see https://x.y & go" and disp_[1]["message"]["from"]["id"] == "U1"
            assert nightmux.bridge_of(disp_[1]["message"]["message_thread_id"]) == "slack"


def test_websocket_client():
    with isolated(nightmux):
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # The websocket client against a local server: fragments, a 126-length
        # frame, ping answered with pong, masked client frames, close.
        import socket
        srv_ = socket.socket()
        srv_.bind(("127.0.0.1", 0))
        srv_.listen(1)
        got_ws_ = []

        def ws_server_():
            c, _ = srv_.accept()
            h = b""
            while b"\r\n\r\n" not in h:
                h += c.recv(1)
            c.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n\r\n")
            body = ("é" * 150).encode()
            c.sendall(bytes([0x01, 126]) + struct.pack(">H", 100) + body[:100])
            c.sendall(bytes([0x89, 2]) + b"hi")                          # ping mid-message
            c.sendall(bytes([0x80, 126]) + struct.pack(">H", len(body) - 100) + body[100:])
            for _ in range(2):
                hh = c.recv(2)
                n = hh[1] & 0x7F
                mk = c.recv(4)
                got_ws_.append((hh[0] & 0x0F, bytes(b ^ mk[i % 4] for i, b in enumerate(c.recv(n)))))
            c.sendall(bytes([0x88, 0]))
            c.close()
        threading.Thread(target=ws_server_, daemon=True).start()
        w_ = nightmux.WS(f"ws://127.0.0.1:{srv_.getsockname()[1]}/x", timeout=5)
        assert w_.recv() == "é" * 150
        w_.send("hello")
        assert w_.recv() is None and got_ws_ == [(0xA, b"hi"), (1, b"hello")], got_ws_
        w_.close()
        srv_.close()
