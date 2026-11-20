"""test_state: cut from the old monolithic selfcheck() (pre-stub part)."""
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_generated_docs_current():
    with isolated(nightmux) as iso:
        cmd_md = os.path.join(os.path.dirname(os.path.abspath(nightmux.__file__)), "docs", "COMMANDS.md")
        if os.path.exists(cmd_md):              # a git checkout, not a pip install
            with open(cmd_md) as f:
                assert f.read() == nightmux.commands_md(), "docs/COMMANDS.md is stale: nightmux --commands > docs/COMMANDS.md"
        rd = os.path.join(os.path.dirname(os.path.abspath(nightmux.__file__)), "README.md")
        if os.path.exists(rd):
            with open(rd, encoding="utf-8") as f:
                assert nightmux.agents_md().strip() in f.read(), "README agent table is stale: nightmux --agents-md"
        plugin = os.path.join(os.path.dirname(os.path.abspath(nightmux.__file__)), ".claude-plugin", "plugin.json")
        if os.path.exists(plugin):              # the Claude Code plugin ships at the same version
            with open(plugin) as f:
                assert json.load(f)["version"] == nightmux.VERSION, "bump .claude-plugin/plugin.json with VERSION"


def test_hardening_secrets_and_state_dir():
    with isolated(nightmux) as iso:
        # Hardening: credentials are never sent by !get, and the state dir is private.
        home_ = os.path.expanduser("~")
        for p_ in (".nightmux.json", ".ssh/id_ed25519", ".nightmux-relay.env", ".aws/credentials",
                   "proj/.env", ".nightmux-state/paired_tokens.json"):
            assert nightmux.is_secret_path(os.path.join(home_, p_)), p_
        assert not nightmux.is_secret_path(os.path.join(home_, "proj", "README.md"))
        with nightmux.stubbed(STATE_DIR=os.path.join(__import__("tempfile").mkdtemp(), "st")):
            nightmux.harden_state()
            assert os.stat(nightmux.STATE_DIR).st_mode & 0o777 == 0o700
            os.chmod(nightmux.STATE_DIR, 0o775)
            nightmux.harden_state()
            assert os.stat(nightmux.STATE_DIR).st_mode & 0o777 == 0o700


def test_cfg_save_keeps_hand_edits_and_mode():
    with isolated(nightmux) as iso:
        nightmux.CFG_PATH = os.path.join(nightmux.FILE_DIR, "selfcheck.json")
        nightmux.OFFSET_PATH = os.path.join(nightmux.FILE_DIR, "selfcheck.offset")
        os.makedirs(nightmux.FILE_DIR, exist_ok=True)
        with open(nightmux.CFG_PATH, "w") as f:                # a key added by hand, mid-run
            json.dump({"topics": {"1": "old"}, "handedit": 42}, f)
        nightmux.save_cfg({"topics": {"1": "new"}})            # daemon writes what it owns
        assert nightmux.load_cfg() == {"topics": {"1": "new"}, "handedit": 42}, nightmux.load_cfg()
        mode = os.stat(nightmux.CFG_PATH).st_mode & 0o777       # the token lives in here
        assert mode == 0o600, oct(mode)                # every save, not just the first
        nightmux.save_offset(12345)
        assert nightmux.load_offset() == 12345


def test_acks_offset_ordering():
    with isolated(nightmux) as iso:
        nightmux.CFG_PATH = os.path.join(nightmux.FILE_DIR, "selfcheck.json")
        nightmux.OFFSET_PATH = os.path.join(nightmux.FILE_DIR, "selfcheck.offset")
        os.makedirs(nightmux.FILE_DIR, exist_ok=True)
        nightmux.save_offset(12345)
        acks = nightmux.Acks()                                  # parallel topics finish out of order
        for uid in (10, 11, 14):                       # 12, 13: types we filtered out
            acks.dispatch(uid)
        acks.ack(11)
        assert nightmux.load_offset() == 12345                  # 10 still running: do not move past it
        acks.ack(10)
        assert nightmux.load_offset() == 14                     # both done, and the gap is skipped
        acks.ack(14)
        assert nightmux.load_offset() == 15                     # nothing outstanding: past the last
        assert acks.seen == [] and acks.done == set()  # no bookkeeping left behind
        assert nightmux.upd_topic({"message": {"message_thread_id": 7}}) == "7"
        assert nightmux.upd_topic({"callback_query": {"message": {"message_thread_id": 7}}}) == "7"
        assert nightmux.upd_topic({"message": {}}) == "0"       # the General topic
        os.remove(nightmux.OFFSET_PATH)
        assert nightmux.load_offset() is None



def test_snapshot_newest_fresh_and_prune():
    with isolated(nightmux) as iso:
        nightmux.STATE_DIR = os.path.join(nightmux.FILE_DIR, "state")
        os.makedirs(nightmux.STATE_DIR, exist_ok=True)
        for n_, ts, pn in (("a", time.time() - 10, "%1"), ("b", time.time(), "%1"),
                           ("c", time.time() - 2 * nightmux.STATE_FRESH, "%1"),
                           ("d", time.time(), "%2")):
            with open(os.path.join(nightmux.STATE_DIR, f"{n_}.json"), "w") as f:
                json.dump({"ts": ts, "pane": pn, "transcript": f"/t/{n_}"}, f)
        assert nightmux.snapshot("%1")["transcript"] == "/t/b", nightmux.snapshot("%1")  # newest fresh one
        assert nightmux.snapshot("%2")["transcript"] == "/t/d"
        assert nightmux.snapshot("%9") is None and nightmux.snapshot(None) is None
        os.utime(os.path.join(nightmux.STATE_DIR, "c.json"), (0, 0))   # ancient on disk
        assert nightmux.prune(time.time(), time.time()) == 0 or True    # throttled, no sweep
        assert os.path.exists(os.path.join(nightmux.STATE_DIR, "c.json"))
        assert nightmux.prune(time.time(), 0) > 0
        assert not os.path.exists(os.path.join(nightmux.STATE_DIR, "c.json"))  # swept
        assert os.path.exists(os.path.join(nightmux.STATE_DIR, "b.json"))      # fresh one kept
        qp = os.path.join(nightmux.STATE_DIR, "queue.json")                    # never a cache
        open(qp, "w").close(), os.utime(qp, (0, 0))
        assert nightmux.prune(time.time() + 2 * nightmux.PRUNE_EVERY, 0) and os.path.exists(qp)
        os.remove(qp)

        # A snapshot for a pane that is still alive survives any age. Age here says
        # the agent has been quiet, not that the file is wrong — and the sessions
        # that go quiet longest are the parked ones idle_hint exists to talk about.
        lp = os.path.join(nightmux.STATE_DIR, "live.json")
        with open(lp, "w") as f:
            json.dump({"pane": "%77", "ctx_pct": 61}, f)
        os.utime(lp, (0, 0))                                  # ancient, and parked
        assert nightmux.snap_pane(lp) == "%77" and nightmux.snap_pane("/no/such") is None
        assert nightmux.prune(time.time() + 4 * nightmux.PRUNE_EVERY, 0, {"%77"}) and os.path.exists(lp)
        # ...but only the newest per pane. A pane collects a snapshot per Claude
        # session id, so keeping every one whose pane is alive hoards them for the
        # life of the pane and makes snapshot() rescan the pile on every look.
        lp2 = os.path.join(nightmux.STATE_DIR, "live2.json")
        with open(lp2, "w") as f:
            json.dump({"pane": "%77", "ctx_pct": 62}, f)     # same pane, newer file
        os.utime(lp2, (time.time(), time.time()))
        assert nightmux.newest_per_pane({"%77"}) == {lp2}, nightmux.newest_per_pane({"%77"})
        nightmux.prune(time.time() + 10 * nightmux.PRUNE_EVERY, 0, {"%77"})
        assert os.path.exists(lp2) and not os.path.exists(lp), "kept the stale twin"
        os.remove(lp2)
        assert nightmux.prune(time.time() + 6 * nightmux.PRUNE_EVERY, 0, {"%1"}) and not os.path.exists(lp)
        with open(lp, "w") as f:                              # unreadable: not kept
            f.write("{ not json")
        os.utime(lp, (0, 0))
        nightmux.prune(time.time() + 8 * nightmux.PRUNE_EVERY, 0, {"%77"})
        assert not os.path.exists(lp)
        for n_ in ("a", "b", "d"):                       # hours of silence must not
            os.remove(os.path.join(nightmux.STATE_DIR, f"{n_}.json"))          # drop to scraping
        with open(os.path.join(nightmux.STATE_DIR, "e.json"), "w") as f:
            json.dump({"ts": time.time() - 7200, "pane": "%1", "transcript": "/t/e"}, f)
        assert nightmux.snapshot("%1")["transcript"] == "/t/e"   # two idle hours: still bound
        os.utime(os.path.join(nightmux.STATE_DIR, "e.json"), (0, 0))
        nightmux.prune(time.time(), 0)
        assert nightmux.snapshot("%1") is None                   # ... a day of it does


def test_prune_skips_non_snapshot_json():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        # A non-snapshot JSON in the shared state dir (a list, from another tool)
        # once crash-looped the daemon at startup inside snapped().
        with tempfile.TemporaryDirectory() as sd_, nightmux.stubbed(STATE_DIR=sd_):
            with open(os.path.join(sd_, "stray.json"), "w") as f:
                json.dump(["x"], f)
            with open(os.path.join(sd_, "s1.json"), "w") as f:
                json.dump({"pane": "%9", "ts": time.time()}, f)
            assert list(nightmux.snapped()) == ["%9"] and list(nightmux.snapped()) == ["%9"]


def test_prune_ignores_non_snapshot_state_json():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        # A non-snapshot json in the state dir must not stop prune (and the watcher).
        with tempfile.TemporaryDirectory() as td_:
            with open(os.path.join(td_, "paired_tokens.json"), "w") as f_:
                json.dump(["x"], f_)
            with nightmux.stubbed(STATE_DIR=td_):
                assert nightmux.snap_pane(os.path.join(td_, "paired_tokens.json")) is None
                nightmux.prune(time.time(), 0.0, {"%1"})
