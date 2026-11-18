"""test_sessions: cut from the old monolithic selfcheck() (pre-stub part)."""
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


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


def test_start_session_spawns_with_flags_and_agy_hint():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        cfg2 = {"topics": {}, "agents": {"opencode": ["opencode", "--resume"]}}
        spawned, lk = [], threading.Lock()
        nightmux.spawn = lambda n, cwd, line, cfg=None: spawned.append((n, cwd, line))
        nightmux.has_session = lambda n: False
        nightmux.start_session(cfg2, {}, lk, "9", "box ~ --sandbox", "codex")

        spawned, lk = [], threading.Lock()
        nightmux.spawn = lambda n, cwd, line, cfg=None: spawned.append((n, cwd, line))
        nightmux.has_session = lambda n: False
        assert "started codex" in nightmux.start_session(cfg2, {}, lk, "9", "box ~ --sandbox",
                                                "codex")
        assert spawned[-1][2] == "codex --sandbox", spawned[-1]
        assert cfg2["topics"]["9"] == "box" and cfg2["started"]["9"] == "codex"
        # "!agy box ~" in box's own topic: point at bare !agy, not at !bind.
        nightmux.has_session = lambda n: n == "box"
        assert "send just !agy" in nightmux.start_session(cfg2, {}, lk, "9", "box ~", "agy")
        assert "use !bind box" in nightmux.start_session(cfg2, {}, lk, "8", "box ~", "agy")
        nightmux.has_session = lambda n: False


def test_restore_is_resume_alias():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        cfg2 = {"topics": {}, "agents": {"opencode": ["opencode", "--resume"]}}
        spawned, lk = [], threading.Lock()
        nightmux.spawn = lambda n, cwd, line, cfg=None: spawned.append((n, cwd, line))
        nightmux.has_session = lambda n: False
        nightmux.start_session(cfg2, {}, lk, "9", "box ~ --sandbox", "codex")

        # !restore is !resume under another name — both funnel through resume_session.
        cfg2["topics"]["91"] = "ghost"
        n = len(spawned)
        assert "no directory recorded" in nightmux.handle(cfg2, {}, lk, "91", "!restore")
        assert len(spawned) == n, spawned[n:]        # a topic with no dir stays down
        cfg2.setdefault("dirs", {})["91"] = "/tmp"
        out = nightmux.handle(cfg2, {}, lk, "91", "!restore")
        assert spawned[-1][:2] == ("ghost", "/tmp") and "topic bound" in out, out
        assert cfg2["started"]["91"] == "claude"


def test_restore_startup_button_or_relaunch():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        box = ["╭────────╮", "│ > ", "╰────────╯", "  ? for shortcuts"]
        typed, edits = [], []
        nightmux.inject = lambda s, t: (typed.append(t), True)[1]   # typed it
        nightmux.api = lambda c, m, **kw: edits.append((m, kw)) or {}
        cfg["topics"], cfg["verbose"] = {"1": "s"}, []
        screen[:] = ["● done", "⚠ Our servers are experiencing high traffic right now, please try again in a minute. "
                     "(UNAVAILABLE (code 503): No capacity available for model gemini-pro-agent on the server)"] + box
        st = state["s"] = {"asked_at": time.time(), "asked_msgs": [("1", 77)], "calls": 0, "calls_warned": False,
                           "changed": time.time(), "echo": {"and again"}, "last": "task for gemini",
                           "last_at": time.time(), "mode": "idle", "prev": list(screen), "prog_at": 0.0,
                           "prog_text": "", "queue": [], "ran": True, "react": None, "scr": list(screen),
                           "sent": list(screen), "snap": None, "spend": [], "turns": [time.time()] * 2,
                           "why": "trace=False prev=False mode=idle active=False"}
        cfg2 = {"topics": {}, "agents": {"opencode": ["opencode", "--resume"]}}
        spawned, lk = [], threading.Lock()
        nightmux.spawn = lambda n, cwd, line, cfg=None: spawned.append((n, cwd, line))
        nightmux.has_session = lambda n: False
        nightmux.start_session(cfg2, {}, lk, "9", "box ~ --sandbox", "codex")

        # restore_startup: a dead topic gets a button unless auto_restore says relaunch.
        cfg3 = {"topics": {"1": "gone1", "2": "alive2"}, "dirs": {"1": "/tmp"}, "chat_id": -1}
        st3, n = {}, len(sent)
        nightmux.has_session = lambda s: s == "alive2"
        nightmux.restore_startup(cfg3, st3, lk)
        assert sent[-1].startswith("⚠️ gone1 is gone") and len(sent) == n + 1, sent[n:]
        assert st3["gone1"]["dead"] is True                # pre-armed: watchdog stays quiet
        cfg3["auto_restore"] = True
        nightmux.restore_startup(cfg3, st3, lk)
        assert spawned[-1][0] == "gone1" and sent[-1].startswith("▶️ restored gone1"), sent[-1]
        cfg3["topics"]["3"] = "gone3"                 # never recorded a directory
        nightmux.restore_startup(cfg3, st3, lk)
        assert "not restored" in sent[-1], sent[-1]   # said so, rather than "restored"


def test_no_dir_gets_own_folder():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        cfg2 = {"topics": {}, "agents": {"opencode": ["opencode", "--resume"]}}
        spawned, lk = [], threading.Lock()
        nightmux.spawn = lambda n, cwd, line, cfg=None: spawned.append((n, cwd, line))
        nightmux.has_session = lambda n: False
        nightmux.start_session(cfg2, {}, lk, "9", "box ~ --sandbox", "codex")
        repo = tempfile.mkdtemp(prefix="nightmux-selfcheck-")
        subprocess.run(["git", "init", "-q", repo], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.email", "t@t"], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.name", "t"], check=True)
        with open(os.path.join(repo, "f"), "w") as f:
            f.write("one")
        subprocess.run(["git", "-C", repo, "add", "f"], check=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "init"], check=True)
        wt = nightmux.worktree_path(repo, "feature-a")

        nightmux.has_session = lambda s: False
        # No dir: a folder of its own under projects_root, never loose in $HOME.
        with tempfile.TemporaryDirectory() as pr_:
            nodir_ = {"topics": {}, "projects_root": pr_}
            with nightmux.stubbed(spawn=lambda *a: None, has_session=lambda n: False,
                         save_cfg=lambda c: None):
                nightmux.start_session(nodir_, {}, lk, "95", "fresh", "claude")
                assert nodir_["dirs"]["95"] == os.path.join(pr_, "fresh"), nodir_
        out = nightmux.start_session(cfg2, {}, lk, "92", f"wtses {repo} @feature-b", "claude")
        assert out.startswith("started claude") and "@feature-b" in out, out
        assert cfg2["dirs"]["92"] == os.path.join(f"{repo}-wt", "feature-b")
        assert os.path.isdir(cfg2["dirs"]["92"])
        plaindir = tempfile.mkdtemp(prefix="nightmux-selfcheck-plain-")
        bad = nightmux.start_session(cfg2, {}, lk, "93", f"wtses2 {plaindir} @x", "claude")
        assert "not a git repo" in bad, bad
        shutil.rmtree(plaindir, ignore_errors=True)

        with open(os.path.join(repo, "f"), "w") as f:        # dirty worktree
            f.write("two")
        with nightmux.stubbed(sess_cwd=lambda s: repo):
            nightmux.snapshot_repo("t")                                # unattended: snapshot first
        with open(os.path.join(repo, "f")) as f:
            assert f.read() == "two", "stash create must never touch the worktree"
        pre = [n_ for n_ in nightmux.tmux_git(repo, "for-each-ref", "--format=%(refname:short)",
                                     "refs/heads/nightmux/pre-*").split("\n") if n_.strip()]
        assert len(pre) == 1, pre
        nightmux.tmux_git(repo, "branch", "-D", pre[0])   # clean slate for the deterministic prune below

        for i in range(nightmux.SNAP_KEEP + 2):                                    # deterministic creatordate
            d = f"2020-01-01T00:00:{i:02d}"
            env = dict(os.environ, GIT_AUTHOR_DATE=d, GIT_COMMITTER_DATE=d)
            with open(os.path.join(repo, "f"), "w") as f:
                f.write(str(i))
            subprocess.run(["git", "-C", repo, "commit", "-aq", "-m", str(i)], env=env, check=True)
            subprocess.run(["git", "-C", repo, "branch", f"nightmux/pre-fake{i}", "HEAD"],
                           env=env, check=True)
        nightmux.prune_snapshots(repo)
        survivors = [n_ for n_ in nightmux.tmux_git(
            repo, "for-each-ref", "--sort=-creatordate", "--format=%(refname:short)",
            "refs/heads/nightmux/pre-*").split("\n") if n_.strip()]
        assert len(survivors) == nightmux.SNAP_KEEP, survivors      # only the newest SNAP_KEEP survive
        assert survivors[0] == f"nightmux/pre-fake{nightmux.SNAP_KEEP + 1}", survivors
        assert "nightmux/pre-fake0" not in survivors, survivors

        cfg4 = {"topics": {"1": "s4"}}
        with nightmux.stubbed(sess_cwd=lambda s: repo, has_session=lambda s: True):
            undo_out = nightmux.handle(cfg4, {}, threading.Lock(), "1", "!undo")
            wt_out = nightmux.handle(cfg4, {}, threading.Lock(), "1", "!worktrees")
        assert f"nightmux/pre-fake{nightmux.SNAP_KEEP + 1}" in undo_out, undo_out
        assert "1. 01-01 00:00  same as now" in undo_out, undo_out
        assert f"git diff nightmux/pre-fake{nightmux.SNAP_KEEP + 1}" in undo_out, undo_out
        with open(os.path.join(repo, "f"), "w") as f:      # the agent wrecks the file
            f.write("wrecked")
        with nightmux.stubbed(sess_cwd=lambda s: repo, has_session=lambda s: True,
                     visible=lambda s: ["❯ "]):
            undo_out = nightmux.handle(cfg4, {}, threading.Lock(), "1", "!undo 2")
            assert f"back to nightmux/pre-fake{nightmux.SNAP_KEEP}" in undo_out, undo_out
            with open(os.path.join(repo, "f")) as f:
                assert f.read() == str(nightmux.SNAP_KEEP)
            nightmux.handle(cfg4, {}, threading.Lock(), "1", "!undo 1")   # undo the undo
            with open(os.path.join(repo, "f")) as f:
                assert f.read() == "wrecked"
        with nightmux.stubbed(sess_cwd=lambda s: repo, has_session=lambda s: True,
                     visible=lambda s: ["esc to interrupt"]):
            assert "is working" in nightmux.handle(cfg4, {}, threading.Lock(), "1", "!undo 1")
        assert repo in wt_out and "feature-a" in wt_out, wt_out

        shutil.rmtree(repo, ignore_errors=True)
        shutil.rmtree(f"{repo}-wt", ignore_errors=True)
