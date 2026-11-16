"""test_sessions: cut from tests/selfcheck.py (pre-stub part)."""
import os
import subprocess
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402


def test_agentless_session_is_not_typed_into():
    with isolated(nightmux) as iso:
        # A topic with no recorded directory must not come back in $HOME: --continue
        # resumes the last conversation *of that directory*, so one reboot put three
        # topics on the same one. It is learned from the live session instead.
        # A real tmux session with no agent in it: the pane reads idle and ready for
        # work, which is exactly why every send has to ask first. Injecting here
        # would run the prompt as a shell command and lose it.
        subprocess.run(("tmux", "kill-session", "-t", "nm-selfcheck"),
                       capture_output=True)
        subprocess.run(("tmux", "new-session", "-d", "-s", "nm-selfcheck", "-c", "/"),
                       capture_output=True)
        said = []
        try:
            with nightmux.stubbed(send=lambda c, t, x, mode="mono", buttons=None, quiet=False:
                         (said.append(x), 1)[1],
                         save_cfg=lambda c: None):     # !bind below must not touch CFG_PATH
                nightmux.live_sessions()                        # fills _shell, as a tick does
                assert nightmux.pane_state(nightmux.visible("nm-selfcheck")) == "unknown"  # nothing says stop
                assert nightmux.agentless("nm-selfcheck") is True             # ...except this
                assert nightmux.inject("nm-selfcheck", "rm -rf /") is False    # nothing typed
                st3 = {"queue": ["held"]}
                nightmux.drain({"chat_id": -1}, {"nm-selfcheck": st3}, "1", "nm-selfcheck")
                assert st3["queue"] == ["held"] and said == [], (st3, said)  # not spent
                for _ in range(3):                     # said once, on the second tick
                    nightmux.watchdog({"chat_id": -1}, {"nm-selfcheck": st3}, "1",
                             "nm-selfcheck", True)
                assert sum("exited" in s for s in said) == 1, said
                # tmux answers to a prefix; live_sessions() only ever answers to the
                # whole name, so !bind has to store the whole name too.
                assert nightmux.real_session("nm-selfche") == "nm-selfcheck"
                assert nightmux.has_session("nm-selfche") is False
                # A window elsewhere with this session's name must not answer for
                # it. Every Claude Code pane is a window called "claude", so a
                # session called claude resolved to whichever session held one of
                # them, and every command in that topic replied "is gone".
                subprocess.run(("tmux", "new-session", "-d", "-s", "nm-sc-decoy",
                                "-c", "/"), capture_output=True)
                subprocess.run(("tmux", "rename-window", "-t", "nm-sc-decoy:",
                                "nm-selfcheck"), capture_output=True)
                try:
                    assert nightmux.real_session("nm-selfcheck") == "nm-selfcheck"
                    assert nightmux.has_session("nm-selfcheck") is True
                finally:
                    subprocess.run(("tmux", "kill-session", "-t", "nm-sc-decoy"),
                                   capture_output=True)
                cfg9, lk9 = {"topics": {}, "chat_id": -1}, threading.Lock()
                assert nightmux.handle(cfg9, {}, lk9, "9", "!bind nm-selfche") == \
                    "topic bound to 'nm-selfcheck'"
                assert cfg9["topics"]["9"] == "nm-selfcheck", cfg9
        finally:
            subprocess.run(("tmux", "kill-session", "-t", "nm-selfcheck"),
                           capture_output=True)
            nightmux._shell.clear()



def test_autocompact_native_env():
    with isolated(nightmux) as iso:
        # Native mid-turn cap: claude sessions get the token autocompact as their window.
        made = []
        with nightmux.stubbed(tmux=lambda *a: made.append(a)):
            nightmux.spawn("s", "/", "claude", {"autocompact": "150k"})
            nightmux.spawn("s", "/", "claude", {"autocompact": 70})
            nightmux.spawn("s", "/", "claude", {"autocompact": "50k"})
        assert made[0][-2:] == ("-e", "CLAUDE_CODE_AUTO_COMPACT_WINDOW=150000"), made[0]
        assert "-e" not in made[3]                                  # a percentage: no cap
        assert made[6][-1] == "CLAUDE_CODE_AUTO_COMPACT_WINDOW=%d" % nightmux.NATIVE_MIN


def test_resume_and_track_cwd():
    with isolated(nightmux) as iso:
        os.makedirs(nightmux.FILE_DIR, exist_ok=True)
        spawned = []
        with nightmux.stubbed(has_session=lambda s: False, sess_cwd=lambda s: nightmux.FILE_DIR,
                     spawn=lambda *a: spawned.append(a)):
            c, l = {"topics": {"1": "s"}, "dirs": {}}, threading.Lock()
            assert "no directory recorded" in nightmux.resume_session(c, {}, l, "1")
            assert spawned == [], spawned              # nothing started in $HOME
            nightmux.track_cwd(c, l, "1", "s")                  # learned from the live session
            assert c["dirs"]["1"] == nightmux.FILE_DIR, c
            nightmux.resume_session(c, {}, l, "1")
            assert spawned[0][1] == nightmux.FILE_DIR, spawned  # and it comes back there
            # A recorded dir is not moved by an agent cd-ing elsewhere: the next
            # agent switched in would start a second copy of the project there.
            nightmux._cwd["s"] = "/"
            nightmux.track_cwd(c, l, "1", "s")
            assert c["dirs"]["1"] == nightmux.FILE_DIR, c
            nightmux._cwd["s"], ghost_said = "/gone/proj (deleted)", []
            with nightmux.stubbed(send=lambda cf, t, x, mode="mono", buttons=None, quiet=False:
                         ghost_said.append(x)):
                nightmux.track_cwd(c, l, "1", "s")
                nightmux.track_cwd(c, l, "1", "s")
            assert len(ghost_said) == 1 and "deleted folder" in ghost_said[0], ghost_said
            nightmux._ghost.discard("s")
            nightmux._cwd.pop("s", None)
