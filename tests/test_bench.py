"""test_bench: cut from the old monolithic selfcheck() (the last part)."""
import os
import shutil
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_bench_of_pane_binary_beats_config():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        # Claude's session filed as agy (a topic re-bound while marked agy) sent !agy
        # into claude. The pane's binary decides; a config-defined key is not second-guessed.
        mix_ = {"topics": {"7": "tg"}, "started": {"7": "agy"},
                "bench": {"7": {"agy": "tg", "opencode": "tg-oc", "mine": "tg-m"}}}
        with nightmux.stubbed(_agent={"tg": "claude", "tg-oc": "opencode", "tg-m": "claude"}):
            assert nightmux.bench_of(mix_, "7") == {"claude": "tg", "opencode": "tg-oc", "mine": "tg-m"}
        with nightmux.stubbed(_agent={}):                       # nothing known: trust the config
            assert nightmux.bench_of(mix_, "7")["agy"] == "tg"


def test_bare_agent_switch_reuses_session():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        cfg2 = {"topics": {}, "agents": {"opencode": ["opencode", "--resume"]}}
        spawned, lk = [], threading.Lock()
        nightmux.spawn = lambda n, cwd, line, cfg=None: spawned.append((n, cwd, line))
        nightmux.has_session = lambda n: False
        nightmux.start_session(cfg2, {}, lk, "9", "box ~ --sandbox", "codex")

        # One topic, several agents. Bare !<agent> moves the topic to that agent in
        # the same directory and leaves the one it was on running; switching back
        # must reuse that session, or "switch" would mean "start a new conversation".
        live = {"box"}
        nightmux.has_session = lambda s: s in live
        cfg2["topics"]["9"], cfg2["started"]["9"] = "box", "codex"
        cfg2["dirs"]["9"] = "/tmp"
        out = nightmux.handle(cfg2, {}, lk, "9", "!agy")
        assert spawned[-1][:2] == ("box-agy", "/tmp"), spawned[-1]
        assert cfg2["topics"]["9"] == "box-agy" and cfg2["started"]["9"] == "agy"
        assert cfg2["bench"]["9"] == {"codex": "box", "agy": "box-agy"}, cfg2["bench"]
        assert "also live in the same tree: box" in out, out   # two agents, one tree
        live.add("box-agy")
        n = len(spawned)
        assert "\u2192 codex ('box')" in nightmux.handle(cfg2, {}, lk, "9", "!codex")
        assert len(spawned) == n, "switching back respawned instead of reusing"
        assert cfg2["topics"]["9"] == "box" and cfg2["started"]["9"] == "codex"
        assert "already on codex" in nightmux.handle(cfg2, {}, lk, "9", "!codex")
        assert "\u25cf !codex" in nightmux.handle(cfg2, {}, lk, "9", "!agents")
        nightmux.handle(cfg2, {}, lk, "9", "!agy named /tmp")   # with args: still start-by-name
        assert spawned[-1][0] == "named" and cfg2["bench"]["9"]["agy"] == "box-agy"


def test_at_agent_addresses_bench_without_moving_topic():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        cfg2 = {"topics": {}, "agents": {"opencode": ["opencode", "--resume"]}}
        spawned, lk = [], threading.Lock()
        nightmux.spawn = lambda n, cwd, line, cfg=None: spawned.append((n, cwd, line))
        nightmux.has_session = lambda n: False
        nightmux.start_session(cfg2, {}, lk, "9", "box ~ --sandbox", "codex")

        # ...and one session must never be two topics'. They share a scrape cursor,
        # so the watcher hands the output to whichever topic it reaches first.
        # @agent: one prompt to one bench agent, without moving the topic.
        # Put topic 9 back exactly as found: the tests below turn on which session
        # it is on, and switch_agent short-circuits when the bench already names it.
        (cfg2["topics"].get("9"), cfg2["started"].get("9"),
                dict((cfg2.get("bench") or {}).get("9") or {}))
        cfg2.setdefault("bench", {})["9"] = {"codex": "box", "agy": "box-agy"}
        cfg2["topics"]["9"], cfg2["started"]["9"] = "box", "codex"
        assert nightmux.bench_of(cfg2, "9") == {"codex": "box", "agy": "box-agy"}
        sent_to = []
        with nightmux.stubbed(has_session=lambda s: True,
                     send_prompt=lambda c, st, t, se, tx, mid=None: sent_to.append((se, tx))):
            assert nightmux.address(cfg2, {}, "9", "no prefix here") is None      # falls through
            assert nightmux.address(cfg2, {}, "9", "@agy fix the parser") == "→ agy (box-agy)"
            assert sent_to[-1] == ("box-agy", "fix the parser"), sent_to[-1]
            assert cfg2["topics"]["9"] == "box", "addressing must not switch the topic"
            assert "no gemini in this topic" in nightmux.address(cfg2, {}, "9", "@gemini hi")
            assert nightmux.address(cfg2, {}, "9", "@agy") is None                # no prompt: text
        with nightmux.stubbed(has_session=lambda s: False):
            assert "is gone" in nightmux.address(cfg2, {}, "9", "@agy hello")


def test_consult_two_agents_two_rounds():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        cfg2 = {"topics": {}, "agents": {"opencode": ["opencode", "--resume"]}}
        spawned, lk = [], threading.Lock()
        nightmux.spawn = lambda n, cwd, line, cfg=None: spawned.append((n, cwd, line))
        nightmux.has_session = lambda n: False
        nightmux.start_session(cfg2, {}, lk, "9", "box ~ --sandbox", "codex")
        cfg2.setdefault("bench", {})["9"] = {"codex": "box", "agy": "box-agy"}
        cfg2["topics"]["9"], cfg2["started"]["9"] = "box", "codex"
        cfg2["dirs"]["9"] = "/tmp"
        live = {"box"}
        nightmux.has_session = lambda s: s in live

        # consult: two agents, two rounds, one prompt back.
        assert nightmux.fenced("noise\n```py\nfirst\n```\nmid\n```\nLAST ONE\n```") == "LAST ONE"
        assert nightmux.fenced("no fence here") == ""
        csent, cprompts = [], []
        with nightmux.stubbed(has_session=lambda s: True,
                     send=lambda c, t, x, mode="mono", buttons=None, quiet=False: csent.append(x),
                     send_prompt=lambda c, st, t, se, tx, mid=None: cprompts.append((se, tx))):
            nightmux._consult.clear()
            # Too few agents: said with the command that fixes it and a button,
            # so it is sent rather than returned.
            n_ = len(csent)
            assert nightmux.consult_start({"topics": {"9": "solo"}, "bench": {},
                                  "dirs": {"9": "/www/x"}}, {}, "9", "q?") is None
            assert "this topic has 1" in csent[-1] and "/www/x" in csent[-1], csent[-1]
            assert len(csent) == n_ + 1
            out = nightmux.consult_start(cfg2, {}, "9", "how should we shard this?")
            assert "round 1" in out and len(cprompts) == 2, out
            assert "how should we shard this?" in cprompts[0][1]
            assert "already running" in nightmux.consult_start(cfg2, {}, "9", "again?")
            c = nightmux._consult["9"]
            # round 1 lands: the drafts are captured, not posted to the topic
            assert nightmux.consult_capture("9", "box", "codex draft") is True
            assert nightmux.consult_capture("9", "box", "twice") is False   # one per round
            assert nightmux.consult_capture("9", "somebody-else", "x") is False
            assert nightmux.consult_capture("9", "box-agy", "agy draft") is True
            n = len(cprompts)
            nightmux.consult_tick(cfg2, {})
            assert len(cprompts) == n + 2, "round 2 did not go out"
            assert "agy draft" in cprompts[-1][1] or "agy draft" in cprompts[-2][1]
            assert c["round"] == 2 and c["got"] == {}
            # round 2 lands with a fenced prompt from each
            nightmux.consult_capture("9", "box", "I agree.\n```\nDO THE THING\n```")
            nightmux.consult_capture("9", "box-agy", "Mostly.\n```\nDO IT DIFFERENTLY\n```")
            nightmux.consult_tick(cfg2, {})
            assert "9" not in nightmux._consult, "consult did not finish"
            assert any("they differ" in x for x in csent), csent[-3:]
            assert any("DO THE THING" in x for x in csent), csent[-3:]
            assert any("DO IT DIFFERENTLY" in x for x in csent), csent[-3:]
            # ...and the verdict is runnable without anyone retyping it
            assert nightmux._verdict["9"] == {"codex": "DO THE THING",
                                     "agy": "DO IT DIFFERENTLY"}, nightmux._verdict["9"]
            assert "which one?" in nightmux.use_prompt(cfg2, {}, "9", "")   # two: say which
            ran = []
            with nightmux.stubbed(send_prompt=lambda c, st, t, se, tx, mid=None: ran.append((se, tx))):
                out = nightmux.use_prompt(cfg2, {}, "9", "agy")
                assert ran == [(cfg2["topics"]["9"], "DO IT DIFFERENTLY")], ran
                assert out.startswith("▶️ running agy's prompt"), out
            assert "no consult result" in nightmux.use_prompt(cfg2, {}, "404", "")
            # agreement is reported as agreement, and said once
            nightmux._consult.clear(), csent.clear(), cprompts.clear()
            nightmux.consult_start(cfg2, {}, "9", "same?")
            nightmux.consult_capture("9", "box", "a"), nightmux.consult_capture("9", "box-agy", "b")
            nightmux.consult_tick(cfg2, {})
            nightmux.consult_capture("9", "box", "```\nSAME\n```")
            nightmux.consult_capture("9", "box-agy", "```\nSAME\n```")
            nightmux.consult_tick(cfg2, {})
            assert any("same prompt" in x for x in csent), csent[-2:]
            assert sum("SAME" in x for x in csent) == 1, "agreed prompt sent twice"
            # a participant whose session dies is dropped, not waited on
            nightmux._consult.clear(), csent.clear()
            nightmux.consult_start(cfg2, {}, "9", "one dies?")
            with nightmux.stubbed(has_session=lambda s: s != "box-agy", agentless=lambda s: False):
                nightmux.consult_capture("9", "box", "the survivor's draft")
                nightmux.consult_tick(cfg2, {})
            assert any("box-agy is gone" in x for x in csent), csent
            assert "9" not in nightmux._consult, "a lone survivor should report, not wait"
            # a round nobody answers is given up on, not left hanging
            nightmux._consult.clear(), csent.clear()
            nightmux.consult_start(cfg2, {}, "9", "silence?")
            nightmux._consult["9"]["at"] = time.time() - nightmux.CONSULT_TIMEOUT - 1
            nightmux.consult_tick(cfg2, {})
            assert "9" not in nightmux._consult and any("nobody answered" in x for x in csent)

            # plan: one big task -> the agent's own breakdown, run like !shift.
            # Still inside topic 9's "box" window above, before it is put back below.
            assert nightmux.parse_plan("1. first step\n2. second step\n") == ["first step", "second step"]
            assert nightmux.parse_plan("Sure, here:\n- do a\n* do b\nthanks") == ["do a", "do b"]
            assert nightmux.parse_plan("no list here") == []
            nightmux._plan.clear()
            pstate, pprompts = {}, []
        with nightmux.stubbed(send=lambda c, t, x, mode="mono", buttons=None, quiet=False: csent.append(x),
                     send_prompt=lambda c, st, t, se, tx, mid=None: pprompts.append((se, tx))):
            assert "no live session" in nightmux.plan_start(cfg2, pstate, "404", "do the thing")
            out = nightmux.plan_start(cfg2, pstate, "9", "ship the feature")
            assert "asking" in out, out
            assert pprompts[-1][0] == "box" and "ship the feature" in pprompts[-1][1]
            assert "already out" in nightmux.plan_start(cfg2, pstate, "9", "again")
            assert nightmux.plan_capture(cfg2, pstate, "9", "somebody-else", "1. x") is False
            assert nightmux.plan_capture(cfg2, pstate, "9", "box",
                                 "Sure:\n1. write the tests\n2. wire it up\n") is True
            assert "9" not in nightmux._plan
            assert pstate["box"]["shift"] == ["write the tests", "wire it up"]
            assert pstate["box"]["shift_total"] == 2
            assert any("plan set: 2 step" in x for x in csent), csent
            # a reply with no numbered list is reported, not silently dropped
            nightmux.plan_start(cfg2, pstate, "9", "another one")
            csent.clear()
            assert nightmux.plan_capture(cfg2, pstate, "9", "box", "sure, working on it") is True
            assert any("no numbered list" in x for x in csent), csent
            # !relay: another agent on the bench plans, this topic's agent builds
            with nightmux.stubbed(pair_reviewer=lambda c, t, k: ("box-codex", "started codex"),
                         bench_of=lambda c, t: {"claude": "box"}):
                assert "usage" in nightmux.relay_cmd(cfg2, pstate, threading.Lock(), "9", "box", "nobody do it")
                out = nightmux.relay_cmd(cfg2, pstate, threading.Lock(), "9", "box", "codex add CSV export")
                assert "codex plans → claude builds" in out and "started codex" in out, out
                assert pprompts[-1][0] == "box-codex" and "add CSV export" in pprompts[-1][1]
                assert nightmux.plan_capture(cfg2, pstate, "9", "box-codex", "1. a\n2. b") is True
                assert pstate["box"]["shift"] == ["a", "b"] and "box-codex" not in pstate, pstate
                assert "plan from box-codex → box: 2 step" in csent[-1], csent[-1]
            # !fan: parallel tasks, each a worktree + topic + agent + check, after "go"
            assert nightmux.parse_fan("Sure:\n1. @codex add tests || pytest -q\n2. @nobody x\n3. doc it",
                             {"codex"}) == [("codex", "add tests", "pytest -q"),
                                            (None, "@nobody x", None), (None, "doc it", None)]
            assert "usage" in nightmux.fan_cmd(cfg2, pstate, threading.Lock(), "9", "")
            assert "nothing waiting" in nightmux.fan_cmd(cfg2, pstate, threading.Lock(), "9", "go")
            assert "asking" in nightmux.fan_cmd(cfg2, pstate, threading.Lock(), "9", "ship v2")
            assert "INDEPENDENT" in pprompts[-1][1] and nightmux._plan["9"]["fan"]
            csent.clear()
            assert nightmux.plan_capture(cfg2, pstate, "9", "box", "1. @codex add tests || true\n2. docs") is True
            assert "2 parallel task" in csent[-1] and "9" in nightmux._fan and "9" not in nightmux._plan, csent
            import tempfile as tf_
            with tf_.TemporaryDirectory() as fr_:
                fr_ = os.path.realpath(fr_)
                repo_ = os.path.join(fr_, "app")
                nightmux.run("git", "init", "-q", repo_)
                nightmux.run("git", "-C", repo_, "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-q", "--allow-empty", "-m", "init")
                fcfg_, fgoals_, fnew_ = dict(cfg2, dirs={"9": repo_}), [], []

                def fake_new(c, st, lk, title, name, folder, key, idea="", server=""):
                    fnew_.append((name, folder, key))
                    return True, "ok", str(300 + len(fnew_))
                with nightmux.stubbed(topic_new=fake_new, save_queue=lambda s: None,
                             goal_cmd=lambda c, lk, t, a: fgoals_.append((t, a))):
                    out = nightmux.fan_go(fcfg_, pstate, threading.Lock(), "9")
                assert out.count("✅") == 2 and "9" not in nightmux._fan, out
                assert [n for n, _, _ in fnew_] == ["add-tests", "docs"] and fnew_[0][2] == "codex"
                assert all(os.path.isdir(f) for _, f, _ in fnew_) and fgoals_ == [("301", "true")]
                assert "do not merge" in pstate["add-tests"]["queue"][0]
                assert "fan/docs" in nightmux.run("git", "-C", repo_, "branch")
                assert fcfg_["fan_kids"] == {"301": "9", "302": "9"}
                assert fnew_[0][0] == "add-tests" and "no fan topics" in nightmux.fan_clean(fcfg_, pstate, threading.Lock(), "5")
                with nightmux.stubbed(topic_close=lambda c, st, lk, t: (True, "closed"), save_cfg=lambda c: None):
                    out = nightmux.fan_clean(fcfg_, pstate, threading.Lock(), "9")
                assert out.count("✅ closed") == 2 and not fcfg_["fan_kids"], out
            csent.clear()
            nightmux.fan_cmd(cfg2, pstate, threading.Lock(), "9", "again")
            assert "fan cancelled" == nightmux.fan_cmd(cfg2, pstate, threading.Lock(), "9", "cancel")


def test_plugin_names_restricted_and_only_run():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        cfg2 = {"topics": {}, "agents": {"opencode": ["opencode", "--resume"]}}
        spawned, lk = [], threading.Lock()
        nightmux.spawn = lambda n, cwd, line, cfg=None: spawned.append((n, cwd, line))
        nightmux.has_session = lambda n: False
        nightmux.start_session(cfg2, {}, lk, "9", "box ~ --sandbox", "codex")
        cfg2.setdefault("bench", {})["9"] = {"codex": "box", "agy": "box-agy"}
        cfg2["topics"]["9"], cfg2["started"]["9"] = "box", "codex"
        cfg2["dirs"]["9"] = "/tmp"
        live = {"box"}
        nightmux.has_session = lambda s: s in live
        was9 = (cfg2["topics"].get("9"), cfg2["started"].get("9"),
                dict((cfg2.get("bench") or {}).get("9") or {}))

        # plugins: a name is a filesystem path, so it is restricted before it
        # becomes one, and only ever run — never typed into a session. Still
        # inside topic 9's "box" window above, before it is put back below.
        assert nightmux.run_plugin("/tmp", "../etc/passwd", "") is None       # not a bare name
        assert nightmux.run_plugin("/tmp", "no-such-plugin", "") is None      # nothing there
        plugdir = tempfile.mkdtemp(prefix="nightmux-selfcheck-plugins-")
        with open(os.path.join(plugdir, "echoarg"), "w") as f:
            f.write("#!/bin/sh\necho \"got: $1\"\n")
        os.chmod(os.path.join(plugdir, "echoarg"), 0o755)
        with open(os.path.join(plugdir, "notexec"), "w") as f:
            f.write("#!/bin/sh\necho nope\n")               # left without +x: must not run
        with nightmux.stubbed(PLUGIN_DIR=plugdir):
            assert nightmux.run_plugin("/tmp", "echoarg", "hello") == "got: hello"
            assert nightmux.run_plugin("/tmp", "notexec", "") is None
            assert "echoarg" in nightmux.handle(cfg2, {}, lk, "9", "!plugins")
            # sess_cwd is globally faked to a nonexistent path from the daemon-
            # restart tests onward (see "/nonexistent-nightmux-selfcheck" above) —
            # give handle() a real cwd here so this checks the plugin wiring, not
            # subprocess's own cwd validation.
            with nightmux.stubbed(sess_cwd=lambda s: "/tmp"):
                assert nightmux.handle(cfg2, {}, lk, "9", "!echoarg hello there") == "got: hello there"
                # a name with no matching plugin still falls through to typing it in
                with nightmux.stubbed(send_prompt=lambda c, st, t, se, tx, mid=None: "typed:" + tx):
                    assert nightmux.handle(cfg2, {}, lk, "9", "!not-a-plugin hi") == "typed:!not-a-plugin hi"
                    assert "did you mean !budget" in nightmux.handle(cfg2, {}, lk, "9", "!budjet 5M")
                    assert "!saved" in nightmux.handle(cfg2, {}, lk, "9", "!savings")
        shutil.rmtree(plugdir, ignore_errors=True)
        with nightmux.stubbed(PLUGIN_DIR="/no/such/dir"):
            assert "no plugins in" in nightmux.handle(cfg2, {}, lk, "9", "!plugins")

        nightmux._plan.clear(), nightmux._consult.clear()
        cfg2["topics"]["9"], cfg2["started"]["9"], cfg2["bench"]["9"] = was9


def test_watcher_reads_every_bench_agent():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        # The watcher has to read every agent a topic can be written to, or a
        # benched one takes prompts and its answers go nowhere.
        wcfg = {"topics": {"5": "a", "6": "b"},
                "bench": {"5": {"claude": "a", "agy": "a-agy"}},
                "started": {"5": "claude", "6": "claude"}}
        assert nightmux.watched(wcfg) == [("5", "a"), ("5", "a-agy"), ("6", "b")], nightmux.watched(wcfg)
        assert len(nightmux.watched(wcfg)) == len(set(nightmux.watched(wcfg))), "a session watched twice"


def test_one_session_is_never_two_topics():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        cfg2 = {"topics": {}, "agents": {"opencode": ["opencode", "--resume"]}}
        spawned, lk = [], threading.Lock()
        nightmux.spawn = lambda n, cwd, line, cfg=None: spawned.append((n, cwd, line))
        nightmux.has_session = lambda n: False
        nightmux.start_session(cfg2, {}, lk, "9", "box ~ --sandbox", "codex")
        cfg2["bench"] = {"9": {}}

        assert nightmux.bound_to(cfg2, "box", "9") is None
        cfg2["topics"]["94"] = "box"
        assert nightmux.bound_to(cfg2, "box", "9") == "94"
        cfg2["bench"]["9"]["aider"] = "box"           # a bench entry another topic owns
        assert "topic 94's session" in nightmux.handle(cfg2, {}, lk, "9", "!aider")
        del cfg2["bench"]["9"]["aider"]
        with nightmux.stubbed(real_session=lambda a: "box"):
            assert "one session, one topic" in nightmux.handle(cfg2, {}, lk, "95", "!bind box")
        assert "95" not in cfg2["topics"], cfg2["topics"]
        cfg2["topics"].pop("94")
        nightmux.has_session = lambda s: False
