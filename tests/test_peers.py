"""test_peers: cut from the old monolithic selfcheck() (the last part)."""
import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_peer_forwarding_and_server_command():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        # Two servers: the primary forwards a remote topic's update, untouched, to
        # the peer that runs it; the peer serves /peer/ to the secret and nothing else.
        sec_ = "k" * 24
        pcfg_ = {"chat_id": -5, "topics": {"77": "w1"}, "started": {"77": "claude"},
                 "peer_secret": sec_}
        sock_ = socket.socket()
        sock_.bind(("127.0.0.1", 0))
        pport_ = sock_.getsockname()[1]
        sock_.close()
        threading.Thread(target=nightmux.run_webhook_server, daemon=True, kwargs={"peer_only": True},
                         args=(pcfg_, {"w1": {"mode": "idle"}}, threading.Lock(), {1}, pport_)).start()
        prim_ = {"chat_id": -5, "topics": {}, "remote": {"77": "box2"},
                 "peers": {"box2": {"url": f"http://127.0.0.1:{pport_}", "secret": sec_}}}
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{pport_}/")
            except urllib.error.HTTPError as e:
                assert e.code == 404           # the dashboard is not served to the tailnet
                break
            except OSError:
                time.sleep(0.05)
        bad_ = dict(prim_, peers={"box2": dict(prim_["peers"]["box2"], secret="x" * 24)})
        assert nightmux.peer_call(bad_, "box2", "api/topics") is None          # 403
        with nightmux.stubbed(live_sessions=lambda: {"w1": 1}):
            rows_ = nightmux.with_peers(prim_, "/api/topics", [])
        assert [(r["topic"], r["server"]) for r in rows_] == [("77", "box2")], rows_
        got_, real_process = [], nightmux.process
        upd_ = {"update_id": 9, "message": {"message_thread_id": 77, "text": "hello",
                                            "chat": {"id": -5}, "from": {"id": 1}}}
        with nightmux.stubbed(process=lambda c, st, l, a, u: got_.append((c is pcfg_, u))):
            real_process(prim_, {}, threading.Lock(), {1}, upd_)
            for _ in range(100):
                if got_:
                    break
                time.sleep(0.02)
        assert got_ and got_[0][0] and got_[0][1]["_peer"] and \
            got_[0][1]["message"]["text"] == "hello", got_
        psent_ = []
        with nightmux.stubbed(send=lambda c, t, x, mode="mono", buttons=None, quiet=False: psent_.append(x),
                     save_cfg=lambda c: None):
            gone_ = dict(prim_, peers={"box2": {"url": "http://127.0.0.1:1", "secret": sec_}})
            real_process(gone_, {}, threading.Lock(), {1}, upd_)
            assert "did not answer" in psent_[-1], psent_
            lk_ = threading.Lock()
            assert "box2" in nightmux.handle(prim_, {}, lk_, "77", "!server")
            assert "!unbind" in nightmux.handle(dict(prim_, topics={"78": "x"}), {}, lk_, "78", "!server box2")
            assert "no peer" in nightmux.handle(prim_, {}, lk_, "78", "!server nope")
            mv_ = dict(prim_, remote={})
            nightmux.handle(mv_, {}, lk_, "78", "!server box2")
            assert nightmux.peer_of(mv_, "78") == "box2"
            nightmux.handle(mv_, {}, lk_, "78", "!server local")
            assert nightmux.peer_of(mv_, "78") is None
            prim_named_ = dict(mv_, name="vps1")
            nightmux.handle(prim_named_, {}, lk_, "78", "!server BOX2")
            assert nightmux.peer_of(prim_named_, "78") == "box2"
            nightmux.handle(prim_named_, {}, lk_, "78", "!server vps1")
            assert nightmux.peer_of(prim_named_, "78") is None


def test_fleet_stats_sum_servers():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        # Fleet stats: Wrapped, coach and !stats sum every server's numbers; ratios are
        # recomputed from the sums, and a peer that does not answer is left out.
        a1_ = {"days": 30, "took": 1, "tips": [{"agent": "claude", "tip": "t1"}],
               "when": {"projects": [["shop", 3]], "at": {"10": 2}},
               "agents": {"claude": {"sessions": 1, "prompts": 10, "requests": 4, "errors": 0, "big_ctx": 0,
                                     "max_ctx": 50, "tokens": {"input": 10, "cache_read": 90, "cache_write": 0,
                                                               "output": 5, "thinking": 0},
                                     "avg_prompt": 100, "nudge_pct": 0.1, "nudges": [["ok", 1]],
                                     "models": {"opus": 4}, "daily": {"2026-10-12": [400, 4]},
                                     "by_model": {"opus": [1, 2, 3, 4]}}}}
        a2_ = json.loads(json.dumps(a1_))
        a2_["agents"]["claude"].update(prompts=30, avg_prompt=200, nudge_pct=0.5, max_ctx=80,
                                       tokens={"input": 90, "cache_read": 10, "cache_write": 0,
                                               "output": 5, "thinking": 0},
                                       by_model={"opus": [10, 20, 30, 40], "other": [1, 1, 1, 1]})
        a2_["when"] = {"projects": [["shop", 1], ["blog", 2]], "at": {"10": 1, "11": 4}}
        got_ = {"api/analysis?days=30": a2_, "api/savings": {"since": 50, "tokens": 7, "tokens_day": {"2026-10-01": 7}},
                "api/lessons": {"n": 4, "ok": 2, "winners": ["w2"]}}
        fcfg_ = {"peers": {"vps2": {"url": "u"}, "vps3": {"url": "v"}}}
        with nightmux.stubbed(peer_call=lambda c, n, p, b=None, timeout=10: got_.get(p) if n == "vps2" else None,
                     host_name=lambda c: "vps1", analyze_chats=lambda d=30, home=None: a1_,
                     sav_data=lambda: {"since": 100, "tokens": 3, "tokens_day": {"2026-10-01": 1, "2026-09-30": 2}, "spent": {}},
                     prompt_lessons=lambda home=None: {"n": 6, "ok": 5, "winners": ["w1"]}, _analysis={}):
            m_ = nightmux.fleet_analysis(fcfg_, 30)
            c_ = m_["agents"]["claude"]
            assert m_["servers"] == ["vps1", "vps2"] and c_["prompts"] == 40 and c_["max_ctx"] == 80
            assert c_["daily"] == {"2026-10-12": [800, 8]}, c_["daily"]
            assert c_["by_model"] == {"opus": [11, 22, 33, 44], "other": [1, 1, 1, 1]}, c_["by_model"]
            assert c_["cache_hit"] == 0.5 and c_["avg_prompt"] == 175 and c_["nudge_pct"] == 0.4, c_
            assert m_["when"] == {"projects": [("shop", 4), ("blog", 2)], "at": {"10": 3, "11": 4}}, m_["when"]
            assert len(m_["tips"]) == 2 and "vps2" in nightmux.stats_report(m_).splitlines()[0]
            s_ = nightmux.fleet_sav(fcfg_)
            assert s_["since"] == 50 and s_["tokens"] == 10 and s_["tokens_day"] == {"2026-10-01": 8, "2026-09-30": 2}
            assert nightmux.fleet_lessons(fcfg_) == {"n": 10, "ok": 7, "winners": ["w1", "w2"]}
            assert nightmux.fleet_analysis({}, 30) is a1_            # no peers: no merge, no second cache
            # !coach once crashed on an undefined name before drawing anything
            with nightmux.stubbed(threading=type("T", (), {"Thread": lambda *a, **k: type("X", (), {"start": lambda s: None})()})):
                assert nightmux.coach_cmd(fcfg_, "1").startswith("🎯 drawing")
