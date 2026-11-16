"""test_compact: cut from tests/selfcheck.py (stubbed part)."""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_context_warnings_and_autocompact():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        typed = []                                    # menu guard on plain text
        nightmux.inject = lambda s, t: (typed.append(t), True)[1]   # typed it
        st = state["s"] = {"mode": "idle", "snap": {"ts": time.time(), "ctx_pct": 40}}
        cfg["topics"] = {"1": "s"}
        # A window that has already turned over still shows up in the payload, with
        # last window's percentage beside a resets_at in the past. Reporting it read
        # as "weekly 92% used, resets in 0m" while the real week was at 22%.
        now, n = time.time(), len(sent)
        stale = {"ts": now, "seven_day": {"used_percentage": 92, "resets_at": now - 5},
                 "five_hour": {"used_percentage": 16, "resets_at": now + 3600}}
        assert nightmux.window(stale, "seven_day") is None
        assert nightmux.window(stale, "five_hour")["used_percentage"] == 16   # the live one stays
        assert "7d" not in nightmux.usage_line({}, stale) and "5h 16%" in nightmux.usage_line({}, stale)
        nightmux.warn_usage(cfg, {"snap": stale}, "1", "s")
        assert len(sent) == n, sent[-1]              # ...and nothing is announced
        nightmux._warned.clear()

        n = len(sent)                                  # context bloat, per session
        nightmux.warn_ctx(cfg, st, "1", "s")
        assert len(sent) == n                          # 40%: nothing to say
        st["snap"]["ctx_pct"] = 88
        nightmux.warn_ctx(cfg, st, "1", "s")
        assert sent[-1].startswith("🧠 s context 88% full") and st["ctx_warned"]
        nightmux.warn_ctx(cfg, st, "1", "s")
        assert len(sent) == n + 1                      # still full: not again
        st["snap"]["ctx_pct"] = 12                     # compacted: re-arm
        nightmux.warn_ctx(cfg, st, "1", "s")
        assert "ctx_warned" not in st and len(sent) == n + 1

        # The warning has to land ahead of the compaction it warns about, or a
        # config of {"autocompact": 70} compacts at 70 and warns at 75: never.
        assert nightmux.ctx_trip({}) == nightmux.CTX_WARN and nightmux.ctx_trip({"autocompact": 70}) == 60
        assert nightmux.ctx_trip({"autocompact": 5}) == nightmux.CTX_LEAD    # never below an empty window
        n = len(sent)
        st["snap"]["ctx_pct"] = 64
        nightmux.warn_ctx(dict(cfg, autocompact=70), st, "1", "s")
        assert sent[-1].startswith("\U0001f9e0 s context 64% full"), sent[-1]

        # No figure at all -- a Claude with no sidecar. Said once, and
        # only to someone who turned autocompact on and is expecting it to run.
        # Non-Claude agents are skipped entirely.
        blind, n = {"mode": "idle", "snap": {"ts": time.time()}}, len(sent)
        c_cfg = {"topics": {"1": "c1"}, "started": {"1": "claude"}}
        c_cfg_auto = {"topics": {"1": "c1"}, "started": {"1": "claude"}, "autocompact": 70}
        nightmux.warn_ctx(c_cfg, blind, "1", "c1")
        assert len(sent) == n, sent[n:]                # never asked for it: not nagged
        nightmux.warn_ctx(c_cfg_auto, blind, "1", "c1")
        assert sent[-1].startswith("\U0001f648 no context figure for c1"), sent[-1]
        nightmux.warn_ctx(c_cfg_auto, blind, "1", "c1")
        assert len(sent) == n + 1                      # once per session, not per tick
        # Tokens from the transcript but no percentage (no sidecar): used to raise
        # "'<' not supported between NoneType and int" on every watch tick.
        tok_only, n0 = {"mode": "idle", "ctx_tok": 50000, "snap": {"ts": time.time()}}, len(sent)
        nightmux.warn_ctx(c_cfg_auto, tok_only, "1", "c1")
        assert len(sent) == n0 and "ctx_warned" not in tok_only

        # Non-claude agent
        a_cfg_auto = {"topics": {"1": "agy1"}, "started": {"1": "agy"}, "autocompact": 70}
        nightmux.warn_ctx(a_cfg_auto, blind, "1", "agy1")
        assert len(sent) == n + 1                      # still n+1, no new message
        n, typed[:] = len(sent), []                   # auto /compact, tightly gated
        st.update(mode="idle", queue=[], snap={"ts": time.time(), "ctx_pct": 82})
        nightmux.autocompact({"topics": {}}, state, "1", "s")
        assert len(sent) == n and typed == []          # not configured: never acts
        ac = {"autocompact": 70, "topics": {}}
        st["mode"] = "busy"
        nightmux.autocompact(ac, state, "1", "s")
        assert typed == []                             # mid-turn: would interrupt work
        st["mode"], st["queue"] = "idle", ["held"]
        nightmux.autocompact(ac, state, "1", "s")
        assert typed == []                             # queue pending: let it drain first
        st["queue"] = []
        nightmux.autocompact(ac, state, "1", "s")
        assert typed == ["/compact"] and sent[-1].startswith("🧹 s context 82%"), sent[-1]
        nightmux.autocompact(ac, state, "1", "s")
        assert typed == ["/compact"]                   # once per crossing, not per tick
        st["snap"]["ctx_pct"] = 20                     # compacted: re-arm for next climb
        nightmux.autocompact(ac, state, "1", "s")
        assert "compacted" not in st and typed == ["/compact"]

        # A /compact that never landed: retried once past the grace period, then
        # reported. Without this the session sits full for ever and says nothing.
        st["snap"]["ctx_pct"] = 82
        nightmux.autocompact(ac, state, "1", "s")
        assert typed == ["/compact"] * 2 and st["compact_tries"] == 1, typed
        nightmux.autocompact(ac, state, "1", "s")
        assert typed == ["/compact"] * 2                # inside the grace period: wait
        st["compact_at"] = time.time() - nightmux.COMPACT_GRACE - 1
        nightmux.autocompact(ac, state, "1", "s")
        assert typed == ["/compact"] * 3 and st["compact_tries"] == 2, typed
        n = len(sent)
        st["compact_at"] = time.time() - nightmux.COMPACT_GRACE - 1
        nightmux.autocompact(ac, state, "1", "s")
        assert typed == ["/compact"] * 3                # out of tries: stops typing
        assert sent[-1].startswith("\u26a0\ufe0f s still at 82% after"), sent[-1]
        st["compact_at"] = time.time() - nightmux.COMPACT_GRACE - 1
        nightmux.autocompact(ac, state, "1", "s")
        assert len(sent) == n + 1                       # ...and says so once
        st["snap"]["ctx_pct"] = 20                      # leave it armed for what follows
        nightmux.autocompact(ac, state, "1", "s")
        typed[:] = ["/compact"]

        # An absolute cap, for the windows a percentage never reaches. Measured on
        # one box: a 700k window means `autocompact: 70` waits for 490k tokens.
        tokc, n = {"autocompact": "150k", "topics": {}}, len(sent)
        st.update(mode="idle", queue=[], snap={"ts": time.time(), "ctx_pct": 22})
        for k in ("compacted", "compact_at", "compact_tries", "compact_gave_up"):
            st.pop(k, None)
        st["ctx_tok"], st["heavy_at"] = 90000, time.time()   # a heavy task: the configured cap
        nightmux.autocompact(tokc, state, "1", "s")
        assert typed == ["/compact"], "fired under the token cap"   # 90k < 150k
        st["ctx_tok"] = 160000                       # over, though only 22% of window
        nightmux.autocompact(tokc, state, "1", "s")
        assert typed == ["/compact"] * 2, typed
        assert "160,000 tokens ≥ 150,000" in sent[-1], sent[-1]
        st["ctx_tok"] = 10000                        # compacted: re-arm
        nightmux.autocompact(tokc, state, "1", "s")
        assert "compacted" not in st and typed == ["/compact"] * 2
