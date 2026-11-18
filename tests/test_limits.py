"""test_limits: cut from tests/selfcheck.py (stubbed part)."""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_usage_limit_hold_resume_and_retry():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        box = ["╭────────╮", "│ > ", "╰────────╯", "  ? for shortcuts"]
        typed = []                                    # menu guard on plain text
        nightmux.inject = lambda s, t: (typed.append(t), True)[1]   # typed it
        st = state["s"] = {"mode": "idle", "queue": [], "snap": {"ts": time.time(), "ctx_pct": 22}}
        tokc, n = {"autocompact": "150k", "topics": {}}, len(sent)
        cfg["topics"] = {"1": "s"}
        typed[:] = ["/compact"] * 2             # two typed by the compact tests that used to run before this one
        # Routine work (no heavy task for two hours) compacts sooner: 130k ≥ 120k.
        st["heavy_at"] = time.time() - nightmux.HEAVY_HOLD - 1
        st["ctx_tok"] = 130000
        nightmux.autocompact(tokc, state, "1", "s")
        assert typed == ["/compact"] * 3 and "≥ 120,000" in sent[-1], sent[-1]
        for k in ("compacted", "compact_at", "compact_tries", "heavy_at"):
            st.pop(k, None)
        nightmux.remember(state, "s", "refactor the whole auth module and migrate every caller")
        assert time.time() - st["heavy_at"] < 5 and st["calls"] == 0
        st["last"] = ""
        st.pop("heavy_at")
        st.pop("ctx_tok"), typed.clear()
        typed[:] = ["/compact"]
        st.pop("snap"), typed.clear()

        n = len(sent)                                 # parked session still holding one
        st.update(mode="idle", queue=[], changed=time.time(),
                  snap={"ts": time.time(), "ctx_pct": 62})
        nightmux.idle_hint(cfg, state, "1", "s")
        assert len(sent) == n                         # just used: not parked
        st["changed"] = time.time() - nightmux.IDLE_PARK - 1
        st["snap"]["ctx_pct"] = 20
        nightmux.idle_hint(cfg, state, "1", "s")
        assert len(sent) == n                         # parked but cheap to resume
        st["snap"]["ctx_pct"] = 62
        nightmux.idle_hint(cfg, state, "1", "s")
        assert sent[-1].startswith("💤 s idle 6h 0m at 62% context"), sent[-1]
        st["changed"], st["ctx_tok"] = time.time(), 90000      # re-arm; a 1M window: 9%
        nightmux.idle_hint(cfg, state, "1", "s")
        st["changed"], st["snap"]["ctx_pct"] = time.time() - nightmux.IDLE_PARK - 1, 9
        nightmux.idle_hint(cfg, state, "1", "s")
        assert sent[-1].startswith("💤 s idle 6h 0m at 90k tokens"), sent[-1]
        st.pop("ctx_tok")
        st["snap"]["ctx_pct"] = 62
        n += 1                                        # the extra hint above
        nightmux.idle_hint(cfg, state, "1", "s")
        assert len(sent) == n + 1                     # once per park, not per tick
        st["changed"] = time.time()
        nightmux.idle_hint(cfg, state, "1", "s")               # touched: re-arm for the next park
        assert "parked" not in st
        st["changed"] = time.time() - nightmux.IDLE_PARK - 1
        nightmux.idle_hint({"idle_ctx": None}, state, "1", "s")
        assert len(sent) == n + 1 and "parked" not in st        # !idlectx off
        st.pop("snap"), st.pop("changed")

        nightmux._queued[0] = None                             # held prompts outlive a restart
        st.update(queue=["one", "two"], limit_until=time.time() + 3600, ctx_warned=True)
        nightmux.save_queue(state)
        nightmux.save_queue(state)                             # unchanged: no second write
        fresh_state = {}
        restored = nightmux.load_queue(fresh_state)
        assert fresh_state["s"]["queue"] == ["one", "two"], fresh_state
        assert restored["s"]["queue"] == ["one", "two"]
        assert "ctx_warned" not in fresh_state["s"]   # caches rebaseline, never restore
        assert "mode" not in fresh_state["s"]         # ...so `fresh` still means fresh
        st["queue"], nightmux._queued[0] = [], None            # drained: the file empties too
        st.pop("limit_until")
        nightmux.save_queue(state)
        empty = {}
        assert nightmux.load_queue(empty) == {} and empty == {}
        st.pop("ctx_warned")

        st.update(mode="idle", queue=[])              # usage limit: hold, then resume
        st.pop("prog_msg", None)                      # no turn open: nothing was cut
        n = len(sent)                                 # quoted output is not the banner
        screen[:] = ["● done",
                     "  ⎿  Error during compaction: You've hit your monthly limit"] + box
        nightmux.flush_new(cfg, state, "1", "s")
        assert len(sent) == n and "limit_line" not in st, sent[-1]
        # ...but the live refusal is quoted the same way, with nothing in front of it.
        # This is what a spend cap actually looks like on screen, and skipping every
        # ⎿ line meant no pane without a sidecar window ever saw one.
        screen[:] = ["● done", "  ⎿  You've hit your monthly spend limit."] + box
        nightmux.flush_new(cfg, state, "1", "s")
        assert sent[-1].startswith("⚠️ s hit a usage limit") and "NOT queued" in sent[-1]
        assert "limit_until" not in st                # no reset time: warn, never hold
        st.pop("limit_line")
        n = len(sent)                                 # that warning re-baselines this
        screen[:] = ["● done", "You've hit your 5-hour limit · resets in 1h 0m"] + box
        st["snap"] = {"ts": time.time(),              # sidecar outranks a stale screen
                      "five_hour": {"used_percentage": 40, "resets_at": time.time() + 99}}
        nightmux.check_limit(cfg, st, "1", "s", screen, False)
        assert len(sent) == n and "limit_until" not in st, sent[-1]
        st["snap"]["five_hour"]["used_percentage"] = 100   # ... and when it is spent
        nightmux.check_limit(cfg, st, "1", "s", screen, False)
        assert sent[-1].startswith("⏸ s hit the usage limit") and st["limit_until"]
        st.pop("limit_until"), st.pop("limit_line")   # a spent week, a healthy 5h:
        st["snap"] = {"ts": time.time(),              # the week is what refuses turns
                      "five_hour": {"used_percentage": 10, "resets_at": time.time() + 99},
                      "seven_day": {"used_percentage": 100, "resets_at": time.time() + 999}}
        nightmux.check_limit(cfg, st, "1", "s", screen, False)
        assert "weekly window spent" in sent[-1] and st["limit_until"] > time.time() + 900
        st.pop("snap"), st.pop("limit_until"), st.pop("limit_line")
        nightmux.flush_new(cfg, state, "1", "s")               # no sidecar: the screen decides
        assert sent[-1].startswith("⏸ s hit the usage limit") and "resumes" in sent[-1], sent[-1]
        assert st["limit_until"] > time.time() + 3500
        nightmux.flush_new(cfg, state, "1", "s")               # same banner: announced once only
        assert not sent[-1].startswith("⏸")
        n = len(sent)                                 # a cap with no reset time on it
        st.pop("limit_until"), st.pop("limit_line")
        screen[:] = ["● done", "You've hit your monthly spend limit · raise it at x"] + box
        nightmux.flush_new(cfg, state, "1", "s")
        assert sent[-1].startswith("⚠️ s hit a usage limit") and "NOT queued" in sent[-1]
        assert "limit_until" not in st                # so nothing gets swallowed
        st["limit_until"] = time.time() + 3600        # back to the queued case
        screen[:] = ["● done", "You've hit your 5-hour limit · resets in 1h 0m"] + box
        n, typed[:] = len(sent), []
        held = nightmux.handle(cfg, state, threading.Lock(), "1", "do the thing later")
        assert held.startswith("📥 queued (1)") and typed == [], (held, typed)
        nightmux.drain(cfg, state, "1", "s")                   # window still shut: nothing moves
        assert typed == [] and len(sent) == n
        nightmux.sav_data().pop("resumes", None)               # a machine that never resumed
        st["limit_until"] = time.time() - 1           # window reset
        nightmux.drain(cfg, state, "1", "s")
        assert typed == ["do the thing later"], typed
        assert sent[-2].startswith("▶️ s resumed") and "limit_until" not in st
        assert nightmux.REPO_URL in sent[-2], sent[-2]         # its first resume asks for a star
        assert sent[-1].startswith("⚙️ s")           # then the live trace for that turn
        assert st["queue"] == [] and st["prog_msg"] == 77   # live trace opened for it
        assert "limit_line" not in st   # the ended window's banner suppresses nothing
        st.pop("prog_msg"), st.pop("last", None)   # not a prompt awaiting its turn
        st["queue"], st["limit_until"], n = ["and again"], time.time() - 1, len(sent)
        nightmux.drain(cfg, state, "1", "s")                   # ...once: the next resume does not
        assert sent[n].startswith("▶️ s resumed") and nightmux.REPO_URL not in sent[n], sent[n:]
        st.pop("prog_msg"), st.pop("last", None)

        # A window that resets with nothing queued must still clear the hold and say
        # so. The silent version left the session flagged as limited for good, and
        # left the topic with no word at the time nightmux had promised one.
        st["limit_until"], n = time.time() - 1, len(sent)
        nightmux.drain(cfg, state, "1", "s")
        assert "limit_until" not in st and "resumed" not in st
        assert sent[-1].startswith("▶️ s usage window reset"), sent[-1]
        nightmux.drain(cfg, state, "1", "s")                   # ...said once, not every tick
        assert len(sent) == n + 1
        st["limit_until"] = time.time() - 1           # and an expired hold never
        assert nightmux.queue_blob({"s": st}).get("s", {}) == {}          # reaches disk again
        st["limit_until"] = time.time() + 60
        assert nightmux.queue_blob({"s": st})["s"]["limit_until"] > time.time()
        st.pop("limit_until")

        # Capacity / 503 error: automatic retry with refused prompt
        st["last"], st["last_at"], st["ran"] = "task for gemini", time.time(), True
        st.pop("limit_until", None), st.pop("limit_line", None)
        screen[:] = ["● done",
                     "⚠ Our servers are experiencing high traffic right now, please try again in a minute. (UNAVAILABLE (code 503): No capacity available for model gemini-pro-agent on the server)"] + box
        nightmux.flush_new(cfg, state, "1", "s")
        assert any("server capacity / high traffic error (503)" in m and "retrying" in m for m in sent[-2:])
        assert st["queue"] == ["task for gemini"]
        assert st["limit_until"] > time.time()
        st.pop("limit_until"), st.pop("limit_line"), st.pop("queue", None)

        # A reset with a queue and a pane read as "unknown" must hold AND say so.
        # The silent version cleared the hold, told nobody, and typed nothing —
        # which from the topic is "auto-resume after a limit does not work".
        st["queue"], st["limit_until"], st["mode"] = ["after unknown"], time.time() - 1, "unknown"
        n, typed[:] = len(sent), []
        nightmux.drain(cfg, state, "1", "s")
        assert typed == [], typed                        # never types into an unread screen
        assert len(sent) == n + 1 and "pane is unknown" in sent[-1], sent[n:]
        assert "!raw" in sent[-1] and "limit_until" not in st
        st["queue"], st["mode"] = [], "idle"
        st.pop("resumed", None)

        # tmux not answering is no reading: the last mode stands, not "unknown".
        saved_screen, st["mode"] = screen[:], "busy"
        screen[:] = ["[tmux timed out after 10s]"]
        nightmux.flush_new(cfg, state, "1", "s")
        assert st["mode"] == "busy", st["mode"]
        screen[:], st["mode"] = saved_screen, "idle"


def test_scheduled_prompt_waits_behind_hold():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # Scheduling rides the queue, so a scheduled prompt waits behind a usage hold
        # and a busy pane exactly as a typed one does.
        assert nightmux.parse_every("4h") == 14400 and nightmux.parse_every("1d 6h") == 108000
        _c0 = 1700000000 - 1700000000 % 86400   # a UTC midnight (a Tuesday)
        assert nightmux.cron_next({}, "30 9 * * *", _c0) == _c0 + 9 * 3600 + 1800
        assert nightmux.cron_next({}, "0 9 * * 1", _c0) == _c0 + 6 * 86400 + 9 * 3600        # next Monday
        assert nightmux.cron_next({}, "*/15 * * * *", _c0 + 60) == _c0 + 900
        assert nightmux.cron_next({}, "0 0 31 2 *", _c0) is None
        assert nightmux.cron_next({"tz_offset": 2}, "0 9 * * *", _c0) == _c0 + 7 * 3600     # 09:00 at +2h
        for _bad in ("* * * *", "61 * * * *", "a b c d e"):
            try:
                nightmux.cron_next({}, _bad, _c0)
                raise AssertionError(_bad)
            except ValueError:
                pass
        assert nightmux.parse_every("no duration here") == 0
