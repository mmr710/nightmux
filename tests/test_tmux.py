"""test_tmux: cut from the old monolithic selfcheck() (pre-stub part)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402


def test_run_times_out():
    with isolated(nightmux):
        # Something that always blocks. `tmux wait-for` only blocks once a server is
        # already running, so this passed on a machine with sessions open and let a
        # clean one through untested — the timeout path is what is being checked.
        assert "timed out after 1s" in nightmux.run("sleep", "5", timeout=1)
        assert nightmux.run("echo", "hi") == "hi"


def test_live_sessions_picks_agent_pane():
    with isolated(nightmux):
        # Which pane a session means. The agent is wherever its status line was last
        # written from, which is not always the pane holding the focus — and reading
        # one pane while typing into another is indistinguishable from a hang.
        panes = ["api\t%1\t0\tclaude\t/w/api\napi\t%2\t1\tbash\t/w/api\n"
                 "web\t%9\t1\tvim\t/w/web"]
        with nightmux.stubbed(tmux_out=lambda *a, **k: panes[0], snapped=lambda: {"%1": 100.0}):
            assert nightmux.live_sessions() == {"api": "%1", "web": "%9"}   # sidecar over focus
            with nightmux.stubbed(snapped=lambda: {"%1": 100.0, "%2": 200.0}):
                assert nightmux.live_sessions()["api"] == "%2"              # two: the newer
            with nightmux.stubbed(snapped=lambda: {}):                      # no sidecar at all:
                assert nightmux.live_sessions() == {"api": "%1", "web": "%9"}   # the agent pane
                panes[0] = "api\t%1\t0\tbash\t/w/api\napi\t%2\t1\tbash\t/w/api"
                assert nightmux.live_sessions() == {"api": "%2"}             # back to the focus
        assert nightmux._cwd == {"api": "/w/api"}, nightmux._cwd     # read from the same call, not a spawn
        with nightmux.stubbed(tmux_out=lambda *a, **k: "s\t%1\t1\tclaude\t/w/has\ttab"):
            nightmux.live_sessions()
            assert nightmux._cwd == {"s": "/w/has\ttab"}, nightmux._cwd   # a tab in the path keeps the pane
        nightmux._cwd.clear()
        assert nightmux.tgt("api") == "api"        # never seen: the session name, as before
        nightmux._target["api"] = "%2"
        assert nightmux.tgt("api") == "%2"
        nightmux._target.clear()



def test_tmux_no_answer_is_not_no_sessions():
    with isolated(nightmux):
        # A tmux that does not answer must not read as a tmux with no sessions. It
        # used to: run() reports a timeout by returning "[tmux timed out]", which is
        # text, so the pane list parsed as empty and every bound topic was told its
        # session had died — then rebaselined, dropping the transcript offset and
        # whatever arrived during the gap. 72 of those in three days on one box.
        with nightmux.stubbed(tmux_out=lambda *a, **k: None):
            assert nightmux.live_sessions() is None
            assert nightmux.status_report({"topics": {"1": "s"}}, {}).startswith("tmux is not")
        with nightmux.stubbed(run=lambda *a, **k: "[tmux timed out after 10s]"):
            assert nightmux.tmux("list-panes") == "[tmux timed out after 10s]"   # unchanged


def test_tmux_out_reads_exit_status():
    with isolated(nightmux):
        # tmux_out reads the exit status, not the text: a failing tmux is None too.
        # Both commands answer without a server, because CI has no tmux running and
        # `display-message` there fails for that reason rather than the one intended.
        assert nightmux.tmux_out("no-such-tmux-command") is None
        # ...and a working one is its text. A loaded CI runner sometimes gets no
        # answer from `tmux -V` inside the timeout: that is None, a skip, not a fail.
        ver_ = nightmux.tmux_out("-V")
        if ver_ is None:
            print("skip: tmux -V did not answer", flush=True)
        else:
            assert ver_.startswith("tmux"), ver_


def test_tmux_outage_announced_once():
    with isolated(nightmux):
        # The outage is announced once, and so is its end — not once per session per
        # tick, which is what nine topics of 💀 looked like.
        tsent = []
        with nightmux.stubbed(send=lambda c, t, x, **k: tsent.append(x)):
            cfgm = {"topics": {"9": "b", "3": "a"}}
            assert nightmux.daemon_topic(cfgm) == "3"                    # lowest bound topic
            assert nightmux.daemon_topic(dict(cfgm, center_topic=77)) == "77"   # or the center
            assert nightmux.daemon_topic({"topics": {}}) is None
            nightmux._tmux_miss[0] = 0
            for _ in range(nightmux.TMUX_MISSES - 1):
                nightmux.tmux_missing(cfgm, True)
            assert tsent == [], tsent                     # a blip says nothing
            nightmux.tmux_missing(cfgm, True)
            assert len(tsent) == 1 and tsent[0].startswith("⚠️ tmux has not answered")
            for _ in range(4):
                nightmux.tmux_missing(cfgm, True)
            assert len(tsent) == 1, tsent                 # still out: not again
            nightmux.tmux_missing(cfgm, False)
            assert tsent[-1] == "✅ tmux is answering again" and nightmux._tmux_miss[0] == 0
            nightmux.tmux_missing(cfgm, False)
            assert len(tsent) == 2, tsent                 # recovery is said once too
            nightmux._tmux_miss[0] = 0
            nightmux.tmux_missing(cfgm, True), nightmux.tmux_missing(cfgm, False)
            assert len(tsent) == 2, tsent                 # a blip that healed: silent
