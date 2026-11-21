"""test_dashboard: cut from the old monolithic selfcheck() (stubbed part)."""
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_dashboard_extras_metrics_limits_chat():
    with isolated(nightmux):
        nightmux.agent_version = lambda binary: "stub"       # restored on exit; the doctor must not run a real `<agent> --version`
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # Dashboard extras: host metrics, limits per agent, and the chat analysis —
        # which must report counts and never a prompt.
        m_ = nightmux.server_metrics()
        assert m_["cpus"] >= 1 and 0 <= m_["disk_pct"] <= 100, m_
        import tempfile
        with tempfile.TemporaryDirectory() as h_:
            now_ = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
            os.makedirs(os.path.join(h_, ".claude", "projects", "p"))
            with open(os.path.join(h_, ".claude", "projects", "p", "s.jsonl"), "w") as f:
                for i in range(30):
                    f.write(json.dumps({"type": "user", "timestamp": now_, "cwd": "/w/shop", "message": {
                        "content": "continue" if i % 2 else f"SECRETPROMPT refactor {i}"}},
                        separators=(",", ":")) + "\n")       # as Claude writes it
                    u_ = {"input_tokens": 5, "cache_read_input_tokens": 10000,
                          "cache_creation_input_tokens": 90000, "output_tokens": 100}
                    for out_ in (7, 100):         # one line per content block; the last has the final count
                        f.write(json.dumps({"type": "assistant", "timestamp": now_,
                                            "requestId": f"r{i}", "message": {
                                                "model": "claude-x",
                                                "usage": dict(u_, output_tokens=out_)}}) + "\n")
            cdir_ = os.path.join(h_, ".codex", "sessions", "2026", "01", "02")
            os.makedirs(cdir_)
            tok_ = {"input_tokens": 1000, "cached_input_tokens": 900, "output_tokens": 50}
            with open(os.path.join(cdir_, "rollout-a.jsonl"), "w") as f:
                for l_ in ({"type": "turn_context", "payload": {"model": "gpt-x"}},
                           {"type": "event_msg", "payload": {"type": "user_message", "message": "fix the bug"}},
                           {"type": "event_msg", "payload": {"type": "token_count", "info": {
                               "total_token_usage": tok_, "last_token_usage": tok_}}},
                           {"type": "event_msg", "payload": {"type": "token_count", "info": {
                               "total_token_usage": tok_, "last_token_usage": tok_},
                               "rate_limits": {"primary": {"used_percent": 42.0, "window_minutes": 300,
                                                           "resets_at": time.time() + 600}}}}):
                    f.write(json.dumps(l_) + "\n")
            # OpenCode v2 (session_v2 & session_message) fixture test
            os.makedirs(os.path.join(h_, ".local", "share", "opencode"))
            import sqlite3
            con_oc = sqlite3.connect(os.path.join(h_, ".local", "share", "opencode", "opencode.db"))
            con_oc.execute("CREATE TABLE session_v2 (id TEXT, directory TEXT, time_created INTEGER)")
            con_oc.execute("CREATE TABLE session_message (id TEXT, session_id TEXT, time_created INTEGER, data TEXT)")
            now_ms_ = int(time.time() * 1000)
            con_oc.execute("INSERT INTO session_v2 VALUES ('s_oc', NULL, ?)", (now_ms_,))
            con_oc.execute("INSERT INTO session_message VALUES ('m_oc1', 's_oc', ?, ?)",
                           (now_ms_, json.dumps({"role": "user", "content": "build feature"})))
            con_oc.execute("INSERT INTO session_message VALUES ('m_oc2', 's_oc', ?, ?)",
                           (now_ms_, json.dumps({"role": "assistant", "tokens": {"input": 500, "output": 100, "cache": {"read": 200}}})))
            con_oc.commit()
            con_oc.close()

            # Agy transcript.jsonl fixture test
            agy_logs = os.path.join(h_, ".gemini", "antigravity-cli", "brain", "cid_1", ".system_generated", "logs")
            os.makedirs(agy_logs)
            with open(os.path.join(agy_logs, "transcript.jsonl"), "w") as f_agy:
                f_agy.write(json.dumps({"type": "USER_INPUT", "content": "<USER_REQUEST>\nfix test\n</USER_REQUEST>"}) + "\n")
                f_agy.write(json.dumps({"type": "PLANNER_RESPONSE", "input_tokens": 1000, "cache_read_tokens": 2000, "output_tokens": 150}) + "\n")

            r_ = nightmux.analyze_chats(30, home=h_)
            c_ = r_["agents"]["claude"]
            assert (c_["prompts"], c_["requests"], c_["nudge_pct"]) == (30, 30, 0.5), c_
            assert c_["cache_hit"] == 0.1 and c_["nudges"] == [("continue", 15)], c_
            assert c_["tokens"]["output"] == 3000 and c_["by_model"]["claude-x"] == [150, 300000, 2700000, 3000], c_
            assert r_["agents"]["codex"]["requests"] == 1, r_["agents"]["codex"]   # re-announced total
            lo_ = nightmux.fleet_cost(r_["agents"])
            assert lo_["total"] == 0 and set(lo_["left_out"]) == {"claude-x", "gpt-x", "agy", "(no model name)"}, lo_
            assert r_["agents"]["opencode"]["prompts"] == 1 and r_["agents"]["opencode"]["tokens"]["input"] == 500
            assert r_["agents"]["agy"]["prompts"] == 1 and r_["agents"]["agy"]["tokens"]["input"] == 1000
            assert nightmux.check_reader_drift(home=h_)[1] is True
            assert "claude" in nightmux.AGENT_ADAPTERS and callable(nightmux.adapter_for("opencode")["usage_reader"])
            assert "🩺 doctor check:" in nightmux.doctor_report()
            assert "🩺 doctor check:" in nightmux.handle({"topics": {"1": "s"}}, {}, threading.Lock(), "1", "!doctor")

            with tempfile.TemporaryDirectory() as h_drift:
                os.makedirs(os.path.join(h_drift, ".local", "share", "opencode"))
                con_dr = sqlite3.connect(os.path.join(h_drift, ".local", "share", "opencode", "opencode.db"))
                con_dr.execute("CREATE TABLE session (id TEXT, directory TEXT, time_created INTEGER)")
                con_dr.execute("CREATE TABLE message (id TEXT, session_id TEXT, time_created INTEGER, data TEXT)")
                con_dr.execute("INSERT INTO session VALUES ('s_d', '/tmp', ?)", (now_ms_,))
                con_dr.execute("INSERT INTO message VALUES ('m_d', 's_d', ?, '{\"role\":\"assistant\",\"broken\":1}')", (now_ms_,))
                con_dr.commit()
                con_dr.close()
                chk_d, ok_d, fix_d = nightmux.check_reader_drift(home=h_drift)
                assert ok_d is False and "opencode" in fix_d and "0 parsed tokens" in fix_d
            assert "SECRETPROMPT" not in json.dumps(r_) + nightmux.stats_report(r_)
            assert r_["when"]["projects"] == [("shop", 30)], r_["when"]
            w_ = nightmux.when_summary({}, r_["when"])
            assert sum(w_["hours"]) == 30 and w_["streak"] == 1, w_   # codex line has no timestamp
            h0_ = int(time.time() // 3600)
            w_ = nightmux.when_summary({"tz_offset": 3}, {"at": {h0_: 1, h0_ - 24: 2, h0_ - 72: 4}})
            assert w_["streak"] == 2 and w_["busiest"][1] == 4 and w_["active_days"] == 3, w_
            assert w_["peak_hour"] == time.gmtime(h0_ * 3600 + 3 * 3600).tm_hour, w_
            with nightmux.stubbed(analyze_chats=lambda d: r_,
                         sav_data=lambda: {"tokens": 5000000, "model_tokens": 2000000}):
                wd_ = nightmux.wrapped_data({}, 30)
            pg_ = nightmux.wrapped_page(30, wd_)
            assert ("2.0M", "SAVED VIA SMART ROUTING") in wd_["cells"], wd_["cells"]
            assert wd_["saved"] == 5000000 and wd_["cells"][1][1] == "SAVED FROM THE ABYSS (5.0M)", wd_
            assert wd_["cells"][1][0].endswith("%") and wd_["cells"][1][0] != "0%", wd_["cells"]
            assert ("1", "REPOS DOMINATED") in wd_["cells"] and "shop" in pg_, wd_["cells"]
            assert wd_["split"][0][0] == "claude" and "MODELS DEPLOYED" in pg_, wd_["split"]
            sh_ = nightmux.split_html([("claude", 300, 1), ("codex", 100, 1), ("agy", 0, 40), ("opencode", 0, 0)])
            assert "75%" in sh_ and "25%" in sh_ and "agy <em>0</em>" in sh_, sh_
            assert "opencode <em>0</em>" in sh_, sh_
            ps_ = nightmux.wrapped_page(30, wd_, share=True)
            assert "shop" not in ps_ and "project 1" in ps_ and ">30<" in ps_, ps_
            # Dollars: priced by exact model name; anything else is named and left out, never free
            assert nightmux.price_of("anthropic/claude-haiku-4-5-20251001") == nightmux.PRICES["claude-haiku-4-5"]
            assert nightmux.price_of("Claude-Opus-5-5[1m]") == nightmux.PRICES["claude-opus-5-5"] == (4, 20, .2, 5)
            assert nightmux.price_of("claude-x") is nightmux.price_of("gpt-5.5-pro") is nightmux.price_of("") is None
            assert nightmux.price_of("mine", {"mine": [1, 2]}) == (1, 2, 1, 1)
            # !tokens: dollars, what the cache saved, pace, habits; an unpriced model is named, not free
            tk_ = nightmux.tokens_report({"days": 7, "agents": {
                "claude": {"tokens": {"input": 1000000, "cache_read": 9000000, "cache_write": 0, "output": 100000},
                           "by_model": {"claude-sonnet-5-5": [1000000, 9000000, 0, 100000], "mystery-1": [5, 5, 5, 5]},
                           "prompts": 10, "requests": 100, "cache_hit": .7, "avg_ctx": 200000,
                           "daily": {"2026-11-01": [100, 1], "2026-11-02": [200, 1]}}}}, now=1793600000)
            assert "$3.90" in tk_ and "$0.39" in tk_ and "$17.10" in tk_, tk_   # cost, $/prompt, cache saved
            assert "cache hit 70%" in tk_ and "!compact" in tk_ and "not priced: mystery-1" in tk_, tk_
            assert nightmux.tokens_report({"days": 7, "agents": {}}).startswith("no agent transcripts")
            assert nightmux.price_of("gpt-5.5", {"gpt-5.5": [3, 4, 5, 6]}) == (3, 4, 5, 6)
            for junk_ in ("junk", [1], [1, -2], [1, float("nan")], [1, 2, 3, 4, 5], 7):
                assert nightmux.price_of("gpt-5.5", {"gpt-5.5": junk_}) is None, junk_
            fc_ = nightmux.fleet_cost({"claude": {"tokens": {"input": 10**6, "cache_read": 2 * 10**6, "cache_write": 4 * 10**5,
                                                    "output": 10**5},
                                         "by_model": {"claude-opus-5-5": [10**6, 2 * 10**6, 4 * 10**5, 10**5]}},
                              "codex": {"tokens": {"input": 7, "cache_read": 0, "cache_write": 0, "output": 5},
                                        "by_model": {"gpt-9": [7, 0, 0, 3]}}})
            assert round(fc_["total"], 6) == 8.4 and fc_["agents"].keys() == {"claude"}, fc_
            assert fc_["left_out"] == {"gpt-9": 10, "(no model name)": 2}, fc_
            r2_ = dict(r_, agents=dict(r_["agents"], claude=dict(
                r_["agents"]["claude"], by_model={"claude-opus-5-5": [10**6, 2 * 10**6, 4 * 10**5, 10**5]})))
            with nightmux.stubbed(analyze_chats=lambda d: r2_, sav_data=lambda: {"tokens": 0, "model_tokens": 0}):
                assert nightmux.wrapped_data({}, 30)["cells"][1] == ("$8.40", "AT API LIST PRICES")
                assert nightmux.wrapped_data({"prices": {"claude-opus-5-5": [1, 1]}}, 30)["cells"][1][0] == "$3.50"
                assert round(nightmux.wrapped_data({"prices": "junk"}, 30)["cost"]["total"], 6) == 8.4
            t0_ = time.time()
            d0_ = {"since": t0_ - 100 * 86400, "tokens": 1000}
            assert nightmux.saved_in(d0_, 10) == 100 and nightmux.saved_in({"since": t0_, "tokens": 7}, 10) == 7
            d0_["tokens_day"] = {time.strftime("%Y-%m-%d", time.gmtime(t0_)): 40}
            assert 40 + 80 < nightmux.saved_in(d0_, 10) <= 40 + 97, nightmux.saved_in(d0_, 10)   # ledger + ~10/100 of the rest
            assert "peak hour" in pg_ and "from cache" in pg_ and "SECRETPROMPT" not in pg_
            said_ = " ".join(t["tip"] for t in r_["tips"] if t["agent"] == "claude")
            assert "cache hit 10%" in said_ and "nudges" in said_ and "100k tokens" in said_, said_
            lim_cfg = {"topics": {"5": "o"}, "bench": {"5": {"claude": "o", "codex": "o-codex"}}}
            lim_st = {"o": {"mode": "busy", "snap": {"ts": 1, "five_hour": {"used_percentage": 77}}},
                      "o-codex": {"limit_until": time.time() + 60}}
            with nightmux.stubbed(live_sessions=lambda: {"o": 1, "o-codex": 1}):
                lim_ = {r["agent"]: r for r in nightmux.agent_limits(lim_cfg, lim_st, home=h_)}
            assert lim_["claude"]["busy"] == 1 and lim_["claude"]["windows"][0]["pct"] == 77, lim_
            assert lim_["codex"]["held"] == 1 and lim_["codex"]["windows"][0]["label"] == "5h", lim_
        with nightmux.stubbed(tmux=lambda *a: "one\nghp_" + "a" * 36 + "\n\n", has_session=lambda s: True):
            tl_ = nightmux.term_lines({"topics": {"5": "o"}, "bench": {"5": {"claude": "o", "codex": "o-codex"}}},
                             {"o-codex": {"mode": "busy"}}, "5", "codex", "99999")
            assert tl_["session"] == "o-codex" and tl_["agents"] == ["claude", "codex"], tl_
            assert tl_["lines"][0] == "one" and "ghp_" + "a" * 36 not in json.dumps(tl_), tl_
            assert tl_["mode"] == "busy" and len(tl_["lines"]) == 2, tl_
        assert nightmux.term_lines({"topics": {}}, {}, "7")["error"] == "topic not bound"


def test_board_page_and_office_url():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        cfg2 = {"topics": {}, "agents": {"opencode": ["opencode", "--resume"]}}
        spawned, lk = [], threading.Lock()
        nightmux.spawn = lambda n, cwd, line, cfg=None: spawned.append((n, cwd, line))
        nightmux.has_session = lambda n: False
        nightmux.start_session(cfg2, {}, lk, "9", "box ~ --sandbox", "codex")

        # the board: page served, !board without and with office_url
        assert "/api/topics" in nightmux.BOARD_HTML and "'needs'" in nightmux.BOARD_HTML
        sent_b = []
        with nightmux.stubbed(send=lambda *a, **k: sent_b.append((a, k))):
            assert "kanban needs office_url" in nightmux.handle(dict(cfg2, office_url=None), {}, lk, "9", "!kanban")
            assert nightmux.handle(dict(cfg2, office_url="https://b.ts.net:9090/office"), {}, lk, "9", "!kanban") is None
            assert "https://b.ts.net:9090/board" in sent_b[-1][1]["buttons"], sent_b
