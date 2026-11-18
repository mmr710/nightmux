"""test_team: cut from tests/selfcheck.py (stubbed part)."""
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_team_watch_prompt_audit():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # team: watch reads, prompt talks but runs no admin commands, audit redacts.
        tc_ = {"allow_users": [1, 2, 3], "roles": {"2": "watch", "3": "prompt"}, "topics": {}}
        assert nightmux.role_denied(tc_, 1, "!kill") is None
        assert nightmux.role_denied(tc_, 2, "!status") is None and "watch" in nightmux.role_denied(tc_, 2, "fix it")
        assert "watch" in nightmux.role_denied(tc_, 2, "", has_file=True) and "watch" in nightmux.role_denied(tc_, 2, "!1")
        assert nightmux.role_denied(tc_, 3, "fix the bug") is None and nightmux.role_denied(tc_, 3, "!1") is None
        assert nightmux.role_denied(tc_, 3, "!y") is None and nightmux.role_denied(tc_, 3, "!usage") is None
        for c_ in ("!kill", "!new x", "!codex", "!raw hi", "!team 3 admin", "/spendcap 1", "!upgrade", "!events x"):
            assert "admin" in (nightmux.role_denied(tc_, 3, c_) or ""), c_
        with tempfile.TemporaryDirectory() as ad_, nightmux.stubbed(STATE_DIR=ad_, save_cfg=lambda c: None):
            nightmux.audit(tc_, 3, {"username": "sam"}, "5", "deploy with ghp_" + "c" * 36)
            au_ = nightmux.audit_cmd("5")
            assert "sam #5 deploy with" in au_ and "c" * 36 not in au_, au_
            nightmux.audit({}, 1, {}, "5", "solo")                        # no team, no log
            assert "solo" not in nightmux.audit_cmd("")
            assert "not in allow_users" in nightmux.team_cmd(tc_, "9 watch")
            assert "3: admin" in nightmux.team_cmd(tc_, "3 admin") and "3" not in tc_["roles"]


def test_arena_judged_races():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # !arena: judged races add up per agent and per kind of task.
        old_sav_ = dict(nightmux._sav)
        nightmux._sav["d"] = {"since": 0}
        try:
            assert "no races" in nightmux.arena_report()
            mk_ = lambda p, w, ok=None: nightmux.arena_note({"prompt": p, "racers": {
                "claude": {"took": 300, "check": {"rc": ok}}, "codex": {"took": 600}}}, w)
            mk_("fix the login crash", "codex")
            mk_("write tests for cart", "claude", 0)
            mk_("add tests for checkout", "claude", 1)
            ar_ = nightmux.arena_report()
            assert "3 races" in ar_ and "claude   2/3 won (67%) · checks 1/2 · avg 5m" in ar_, ar_
            assert "tests → claude (2/2)" in ar_ and "bug fix → codex (1/1)" in ar_, ar_
            assert nightmux.race_kind("Refactor the parser") == "refactor" and nightmux.race_kind("hmm") == "other"
        finally:
            nightmux._sav.update(old_sav_)


def test_voice_briefing():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # Voice briefing: speakable text, and a real voice note where ffmpeg can speak.
        sp_ = nightmux.spoken("☀️ briefing · since 19:30\n\ndone overnight:\n  shop #12 fix login — ready to merge")
        assert "PR 12" in sp_ and "☀" not in sp_ and "\n" not in sp_, sp_
        with nightmux.stubbed(save_cfg=lambda c: None):
            bc_ = {}
            assert "voice note" in nightmux.briefing_cmd(bc_, {}, threading.Lock(), "5", "voice")
            nightmux.briefing_cmd(bc_, {}, threading.Lock(), "5", "07:30")
            assert bc_["briefing"] == {"voice": True, "at": "07:30", "topic": "5"}, bc_
        og_ = nightmux.tts_ogg({}, "good morning")
        assert og_ is None or og_[:4] == b"OggS", og_[:8]
