#!/usr/bin/env python3
"""Multi-schema reader fixture tests for agent adapters.

Tests every reader against recorded fixtures from real CLI output to guard
against schema and format drift (e.g. OpenCode v1 vs v2, Agy transcripts, Codex rollouts).
"""
import datetime
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def test_opencode_schemas():
    """Verify OpenCode reader handles both v1 and v2 schemas."""
    with tempfile.TemporaryDirectory() as tmp:
        # Test v1
        v1_dir = os.path.join(tmp, ".local", "share", "opencode")
        os.makedirs(v1_dir)
        shutil.copyfile(os.path.join(FIXTURES, "opencode_v1.db"), os.path.join(v1_dir, "opencode.db"))
        stats1 = {}
        nightmux._scan_opencode(stats1, tmp, since=0)
        oc1 = stats1.get("opencode") or {}
        assert oc1.get("sessions") == 1, f"v1 sessions expected 1, got {oc1.get('sessions')}"
        assert oc1.get("prompts") == 1, f"v1 prompts expected 1, got {oc1.get('prompts')}"
        assert oc1.get("input") == 1400, f"v1 input expected 1400, got {oc1.get('input')}"
        assert oc1.get("output") == 250, f"v1 output expected 250, got {oc1.get('output')}"
        assert oc1.get("cache_read") == 3000, f"v1 cache_read expected 3000, got {oc1.get('cache_read')}"

        # Test v2 (session_v2 and session_message schema)
        shutil.copyfile(os.path.join(FIXTURES, "opencode_v2.db"), os.path.join(v1_dir, "opencode.db"))
        stats2 = {}
        nightmux._scan_opencode(stats2, tmp, since=0)
        oc2 = stats2.get("opencode") or {}
        assert oc2.get("sessions") == 1, f"v2 sessions expected 1, got {oc2.get('sessions')}"
        assert oc2.get("prompts") == 1, f"v2 prompts expected 1, got {oc2.get('prompts')}"
        assert oc2.get("input") == 2100, f"v2 input expected 2100, got {oc2.get('input')}"
        assert oc2.get("output") == 450, f"v2 output expected 450, got {oc2.get('output')}"
        assert oc2.get("cache_read") == 5000, f"v2 cache_read expected 5000, got {oc2.get('cache_read')}"
    print("test_opencode_schemas ok (v1 & v2)")


def test_agy_reader():
    """Verify Agy reader parses conversation_summaries.db and transcript.jsonl."""
    with tempfile.TemporaryDirectory() as tmp:
        gemini_dir = os.path.join(tmp, ".gemini", "antigravity-cli")
        logs_dir = os.path.join(gemini_dir, "brain", "c123", ".system_generated", "logs")
        os.makedirs(logs_dir)
        shutil.copyfile(os.path.join(FIXTURES, "agy_summaries.db"),
                        os.path.join(gemini_dir, "conversation_summaries.db"))
        shutil.copyfile(os.path.join(FIXTURES, "agy_transcript.jsonl"),
                        os.path.join(logs_dir, "transcript.jsonl"))

        stats = {}
        nightmux._scan_agy(stats, tmp, since=0)
        ag = stats.get("agy") or {}
        assert ag.get("sessions") == 1, f"agy sessions expected 1, got {ag.get('sessions')}"
        assert ag.get("prompts") == 1, f"agy prompts expected 1, got {ag.get('prompts')}"
        assert ag.get("requests") == 7, f"agy requests expected 7, got {ag.get('requests')}"
        assert ag.get("input") == 7000, f"agy input expected 7000 (3200+3800), got {ag.get('input')}"
        assert ag.get("output") == 590, f"agy output expected 590 (280+310), got {ag.get('output')}"
        assert ag.get("cache_read") == 13700, f"agy cache_read expected 13700 (6500+7200), got {ag.get('cache_read')}"
    print("test_agy_reader ok")


def test_claude_reader():
    """Verify Claude project reader with recorded JSONL."""
    with tempfile.TemporaryDirectory() as tmp:
        p_dir = os.path.join(tmp, ".claude", "projects", "p1")
        os.makedirs(p_dir)
        shutil.copyfile(os.path.join(FIXTURES, "claude_sample.jsonl"), os.path.join(p_dir, "session.jsonl"))
        stats = {}
        nightmux._scan_claude(stats, tmp, since=0)
        cl = stats.get("claude") or {}
        assert cl.get("sessions") == 1, f"claude sessions expected 1, got {cl.get('sessions')}"
        assert cl.get("prompts") == 2, f"claude prompts expected 2, got {cl.get('prompts')}"
        assert cl.get("input") == 2700, f"claude input expected 2700, got {cl.get('input')}"
        assert cl.get("output") == 770, f"claude output expected 770, got {cl.get('output')}"
        assert cl.get("cache_read") == 9500, f"claude cache_read expected 9500, got {cl.get('cache_read')}"
    print("test_claude_reader ok")


def test_codex_reader():
    """Verify Codex reader and rate limit reader with recorded JSONL."""
    with tempfile.TemporaryDirectory() as tmp:
        s_dir = os.path.join(tmp, ".codex", "sessions", "2026", "10", "10")
        os.makedirs(s_dir)
        shutil.copyfile(os.path.join(FIXTURES, "codex_sample.jsonl"), os.path.join(s_dir, "rollout-1.jsonl"))
        stats = {}
        nightmux._scan_codex(stats, tmp, since=0)
        cx = stats.get("codex") or {}
        assert cx.get("sessions") == 1, f"codex sessions expected 1, got {cx.get('sessions')}"
        assert cx.get("prompts") == 1, f"codex prompts expected 1, got {cx.get('prompts')}"
        assert cx.get("input") == 700, f"codex uncached input expected 700 (2500-1800), got {cx.get('input')}"
        assert cx.get("output") == 400, f"codex output expected 400, got {cx.get('output')}"

        limits = nightmux.codex_limits(tmp)
        assert limits is not None and "primary" in limits, f"expected codex primary limit, got {limits}"
        assert limits["primary"]["used_percent"] == 35.0
    print("test_codex_reader ok")


def test_reader_drift_detection():
    """Verify doctor check flags reader drift when activity exists but tokens == 0."""
    real_version, nightmux.agent_version = nightmux.agent_version, lambda binary: "stub"  # no real CLI
    try:
        _reader_drift_body()
    finally:
        nightmux.agent_version = real_version


def _reader_drift_body():
    with tempfile.TemporaryDirectory() as tmp:
        # Create an opencode DB with sessions/prompts but corrupted/zero tokens
        oc_dir = os.path.join(tmp, ".local", "share", "opencode")
        os.makedirs(oc_dir)
        import sqlite3
        con = sqlite3.connect(os.path.join(oc_dir, "opencode.db"))
        con.execute("CREATE TABLE session (id TEXT, directory TEXT, time_created INTEGER)")
        con.execute("CREATE TABLE message (id TEXT, session_id TEXT, time_created INTEGER, data TEXT)")
        now_ms = int(time.time() * 1000)
        con.execute("INSERT INTO session VALUES ('s1', '/tmp', ?)", (now_ms,))
        con.execute("INSERT INTO message VALUES ('m1', 's1', ?, '{\"role\":\"assistant\",\"no_tokens\":1}')", (now_ms,))
        con.commit()
        con.close()

        # Mock installed agents to include opencode
        chk, ok, fix = nightmux.check_reader_drift(cfg={"agents": {}}, home=tmp)
        assert ok is False, "expected reader drift detection to fail when tokens are 0"
        assert "opencode" in fix and "0 parsed tokens" in fix, f"expected opencode drift warning, got {fix}"

    # Also verify that when no drift occurs, ok is True
    chk_ok, ok_pass, _ = nightmux.check_reader_drift(cfg={"agents": {}}, home="/nonexistent")
    assert ok_pass is True, "expected drift check to pass with no activity"
    print("test_reader_drift_detection ok")


def main():
    test_opencode_schemas()
    test_agy_reader()
    test_claude_reader()
    test_codex_reader()
    test_reader_drift_detection()
    print("all reader tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())


def test_agy_context_of_newest_conversation():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        # agy: the context of its newest conversation in this folder, 0 after its CHECKPOINT
        with tempfile.TemporaryDirectory() as ah_:
            root_ = os.path.join(ah_, ".gemini", "antigravity-cli")
            os.makedirs(os.path.join(root_, "brain", "c2", ".system_generated", "logs"))
            con_ = sqlite3.connect(os.path.join(root_, "conversation_summaries.db"))
            con_.execute("CREATE TABLE conversation_summaries (conversation_id text, workspace_uris text, "
                         "nesting_depth integer, last_modified_time datetime)")
            con_.executemany("INSERT INTO conversation_summaries VALUES (?,?,?,?)",
                             [("c1", '["file:///w/app"]', 0, "2026-10-01"), ("c2", '["file:///w/app"]', 0, "2026-10-02"),
                              ("c3", '["file:///w/app2"]', 0, "2026-10-03"), ("c4", '["file:///w/app"]', 1, "2026-10-04")])
            con_.commit()
            con_.close()
            tf_ = os.path.join(root_, "brain", "c2", ".system_generated", "logs", "transcript.jsonl")
            with open(tf_, "w") as f:
                f.write(json.dumps({"type": "PLANNER_RESPONSE", "input_tokens": 3000, "cache_read_tokens": 140000}) + "\n")
            assert nightmux.agy_ctx("/w/app", home=ah_) == 143000 and nightmux.agy_ctx("/w/none", home=ah_) is None
            with open(tf_, "a") as f:
                f.write(json.dumps({"type": "CHECKPOINT"}) + "\n")
            assert nightmux.agy_ctx("/w/app/", home=ah_) == 0
        screens_ = [["Search: Continue", "  esc Go back / Clear search"], ["  esc Go back / Clear search"], [">"]]
        keys_ = []
        with nightmux.stubbed(visible=lambda s_: screens_.pop(0) if len(screens_) > 1 else screens_[0],
                     tmux=lambda *a: keys_.append(a)):
            nightmux.close_picker("x")
        assert [a[-1] for a in keys_] == ["Escape", "Escape"], keys_   # two, never a third
