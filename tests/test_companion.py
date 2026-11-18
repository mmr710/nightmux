"""test_companion: cut from the old monolithic selfcheck() (the last part)."""
import http
import io
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_companion_seeds_folder_night_and_prompt():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        with tempfile.TemporaryDirectory() as cd_:
            ran, cd_ = [], os.path.join(cd_, "comp")
            fake_sp = type("SP", (), {"TimeoutExpired": subprocess.TimeoutExpired, "DEVNULL": None,
                                      "run": staticmethod(lambda a, **k: ran.append(a) or
                                                          type("P", (), {"returncode": 0})())})
            st_ = {}
            with nightmux.stubbed(COMPANION_DIR=cd_, subprocess=fake_sp,
                                  start_session=lambda c, s, l, t, a, k: f"started {k} '{a.split()[0]}'"):
                cfgc_ = {"agents": {}}
                out = nightmux.companion_cmd(cfgc_, st_, threading.Lock(), "7", "claude")
                assert cfgc_["memory"]["7"] == "off"         # no project-notes turns for it
                assert out.startswith("started claude 'companion'"), out
                assert ran[-1][:4] == ["claude", "mcp", "add", "-s"] and ran[-1][-2:] == ["--mcp", "--companion"]
                with open(os.path.join(cd_, "CLAUDE.md")) as f:
                    assert "@PERSONA.md" in f.read()       # persona survives compaction
                assert oct(os.stat(cd_).st_mode & 0o777) == "0o700"
                with open(os.path.join(cd_, "PERSONA.md"), "w") as f:
                    f.write("mine")
                nightmux.companion_cmd({"agents": {}}, {}, threading.Lock(), "7", "")
                with open(os.path.join(cd_, "PERSONA.md")) as f:
                    assert f.read() == "mine"            # never overwrites the owner's edits
                assert "usage" in nightmux.companion_cmd({"agents": {}}, {}, threading.Lock(), "7", "nope")
                # night: 2h rounds from the night time to the morning, then the summary;
                # off drops only the companion's jobs.
                cfgn = {"companion": {"topic": "7", "session": "companion"}, "tz_offset": 0}
                stn = {"companion": {"sched": [{"at": 1, "every": 60, "text": "mine"}]}}
                with nightmux.stubbed(save_queue=lambda s: None):
                    out = nightmux.companion_night(cfgn, stn, "night 01:00 07:30")
                    jobs = stn["companion"]["sched"]
                    assert [time.strftime("%H:%M", time.gmtime(j["at"])) for j in jobs[1:]] == \
                        ["01:00", "03:00", "05:00", "07:30"], out
                    assert jobs[-1]["text"] == nightmux.COMPANION_MORNING and jobs[0]["text"] == "mine"
                    nightmux.companion_night(cfgn, stn, "night off")
                    assert stn["companion"]["sched"] == [{"at": 1, "every": 60, "text": "mine"}]
                    assert "start the companion" in nightmux.companion_night({}, {}, "night")
                cfg_ = {"budgets": {"5": {"tokens": 1000, "per": "day"}}}
                for t_ in ("6", ""):
                    try:
                        nightmux.companion_prompt(cfg_, t_, "x")
                        assert False, "sent without a budget"
                    except ValueError as e:
                        assert "!budget" in str(e)
                assert nightmux.companion_prompt(cfg_, "6", "x", companion=False) == "x"
                cfg_["companion"] = {"topic": "5"}
                try:
                    nightmux.companion_prompt(cfg_, "5", "x")
                    assert False, "sent to itself"
                except ValueError as e:
                    assert "own topic" in str(e)
                cfg_.pop("companion")


def test_companion_read_chat_clips_and_budget_line():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        with tempfile.TemporaryDirectory() as cd_:
            cd_ = os.path.join(cd_, "comp")
            os.makedirs(cd_)
            with nightmux.stubbed(COMPANION_DIR=cd_):
                # read_chat in companion mode: only unseen messages, at most 15, clipped.
                got = []
                msgs = [{"id": i, "who": "agent", "text": "y" * 3000} for i in range(1, 21)]

                def fake_open(url, timeout=10):
                    got.append(url)
                    after = int(url.rsplit("after=", 1)[1])
                    return io.BytesIO(json.dumps({"items": [m for m in msgs if m["id"] > after]}).encode())
                fake_ul = type("U", (), {"parse": urllib.parse, "request": type("R", (), {
                    "urlopen": staticmethod(fake_open), "Request": urllib.request.Request})})
                def fake_open2(url, timeout=10):
                    got.append(getattr(url, "full_url", url))
                    return io.BytesIO(json.dumps([{"topic": "5", "mode": "waiting"}]).encode())
                fake_ul2 = type("U", (), {"parse": urllib.parse, "request": type("R", (), {
                    "urlopen": staticmethod(fake_open2), "Request": urllib.request.Request})})
                with nightmux.stubbed(urllib=fake_ul2):
                    try:
                        nightmux.nm_call("send_prompt", {"topic": "5", "text": "yes"}, "http://x")
                        assert False, "typed into an open menu"
                    except ValueError as e:
                        assert "menu is open" in str(e) and not any("/topic/" in u for u in got)
                with nightmux.stubbed(urllib=fake_ul):
                    nightmux._nm_seen.clear()
                    text = nightmux.nm_call("read_chat", {"topic": "5"}, base="http://x", companion=True)[0]["text"]
                    assert text.count("agent:") == 15 and "#20 " in text and len(text) < 15 * 1600
                    assert nightmux.nm_call("read_chat", {"topic": "5"}, "http://x", True)[0]["text"] == "nothing new"
                    assert got[-1].endswith("after=20")
                    assert nightmux.nm_call("read_chat", {"topic": "5"}, "http://x")[0]["text"].count("agent:") == 20
                with nightmux.stubbed(budget_used=lambda c, t, s: 1_200_000):
                    assert nightmux.budget_line({"budgets": {"5": {"tokens": 5_000_000, "per": "day"}}}, "5") \
                        == f"{nightmux._k(1_200_000)} of {nightmux._k(5_000_000)} this day"
                    assert nightmux.budget_line({}, "5") is None


def test_companion_progress_report():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        with tempfile.TemporaryDirectory() as cd_:
            cd_ = os.path.join(cd_, "comp")
            os.makedirs(cd_)
            with nightmux.stubbed(COMPANION_DIR=cd_):
                # progress: moved projects with flags, quiet ones on one line, never itself.
                now_ = time.time()
                rows_ = [{"topic": "5", "session": "shop", "mode": "idle", "budget": "1M of 5M this day"},
                         {"topic": "6", "session": "blog", "mode": "waiting"},
                         {"topic": "8", "session": "old", "mode": "idle"},
                         {"topic": "9", "session": "comp", "mode": "idle"}]
                chat_ = {"5": [{"id": i, "t": now_, "who": "bot", "text": f"✅ shop\nstep {i}\nmore"} for i in range(1, 8)]
                         + [{"id": 20 + i, "t": now_, "who": "bot", "text": f"🧠 memory {i}"} for i in range(9)],
                         "9": [{"id": 50, "t": now_, "who": "bot", "text": "me"}]}
                stp = {"blog": {"asked": "Use postgres or sqlite?"}}
                with nightmux.stubbed(topics_status=lambda c, s: rows_, _chat=chat_, tmux_git=lambda *a: ""):
                    cfgp = {"companion": {"topic": "9"}, "dirs": {"5": cd_}}
                    rep_ = nightmux.progress_report(cfgp, stp, now_ - 60)
                    assert "▸ shop (topic 5) [idle] · 7 replies · 0 commits · budget 1M of 5M" in rep_, rep_
                    # status lines are not replies: nine 🧠 lines alone are no circle
                    chat_["5"] = chat_["5"][7:]
                    rep2 = nightmux.progress_report(cfgp, stp, now_ - 60)
                    assert "0 replies" in rep2 and "circles" not in rep2 and "last:" not in rep2, rep2
                    chat_["5"] = [{"id": i, "t": now_, "who": "bot", "text": f"✅ shop\nstep {i}\nmore"}
                                  for i in range(1, 8)]
                    assert "last: step 7" in rep_ and "going in circles" in rep_
                    assert "✋ waiting on you: Use postgres or sqlite?" in rep_ and "quiet: old" in rep_
                    assert "comp" not in rep_
                    # a question at the end of an answer, unanswered: flagged with its wait
                    chat_["8"] = [{"id": 30, "t": now_ - 7200, "who": "bot",
                                   "text": "✅ old\nDone.\nShould I also add dark mode?"}]
                    assert "✋ waiting on you: Should I also add dark mode? (2h" in \
                        nightmux.progress_report(cfgp, stp, now_ - 60)
                    chat_["8"].append({"id": 31, "t": now_ - 3600, "who": "you", "text": "no"})
                    assert "quiet: old" in nightmux.progress_report(cfgp, stp, now_ - 60)
                    chat_.pop("8")
                # commits made in the terminal show even with no chat (empty after a restart)
                with nightmux.stubbed(topics_status=lambda c, s: rows_[2:3], _chat=chat_,
                             tmux_git=lambda cwd, *a: "true" if a[0] == "rev-parse" else "abc123 fix login\n"):
                    rep3 = nightmux.progress_report({"dirs": {"8": cd_}}, {}, now_ - 60)
                    assert "▸ old (topic 8) [idle] · 0 replies · 1 commits" in rep3, rep3


def test_companion_focus_targets_reports():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        with tempfile.TemporaryDirectory() as cd_:
            cd_ = os.path.join(cd_, "comp")
            os.makedirs(cd_)
            with nightmux.stubbed(COMPANION_DIR=cd_):
                now_ = time.time()
                rows_ = [{"topic": "5", "session": "shop", "mode": "idle", "budget": "1M of 5M this day"},
                         {"topic": "6", "session": "blog", "mode": "waiting"},
                         {"topic": "8", "session": "old", "mode": "idle"},
                         {"topic": "9", "session": "comp", "mode": "idle"}]
                # !companion focus, said in the project's topic: reports carry only targeted
                # projects, idle ones too, so a quiet night still has work toward the target.
                lk_ = threading.Lock()
                cff = {"topics": {"5": "shop", "6": "blog", "9": "companion"},
                       "companion": {"topic": "9", "session": "companion"}}
                with nightmux.stubbed(save_cfg=lambda c: None, save_queue=lambda s: None):
                    assert "start the companion" in nightmux.companion_focus({}, lk_, "5", "focus x")
                    out = nightmux.companion_focus(cff, lk_, 5, "focus ship checkout v2")
                    assert "suggest until" in out and cff["companion"]["focus"] == {"5": "ship checkout v2"}
                    assert nightmux.companion_focus(cff, lk_, "9", "focus") == "📌 5: ship checkout v2"
                    assert nightmux.companion_focus(cff, lk_, "5", "focus") == "📌 ship checkout v2"
                    with nightmux.stubbed(topics_status=lambda c, s: rows_[:3], _chat={}, tmux_git=lambda *a: ""):
                        rep5 = nightmux.progress_report(cff, {}, now_ - 60)
                    assert rep5.startswith("▸ shop (topic 5)") and "📌 target: ship checkout v2 — idle" in rep5 \
                        and "blog" not in rep5 and "quiet" not in rep5, rep5
                    nightmux.companion_focus(cff, lk_, "5", "focus off")
                    assert cff["companion"]["focus"] == {}
                    nightmux.companion_focus(cff, lk_, "5", "focus a")
                    nightmux.companion_focus(cff, lk_, "9", "focus off")
                    assert "focus" not in cff["companion"]
                    # never in a project's own topic: it would unbind the project
                    assert "runs 'shop'" in nightmux.companion_cmd(cff, {}, lk_, "5", "")
                    # night rounds leave the day watch alone
                    stw_ = {"companion": {"sched": [{"at": 1, "every": 60, "text": "w",
                                                     "companion": True, "watch": True}]}}
                    nightmux.companion_night(dict(cff, tz_offset=0), stw_, "night 01:00 07:30")
                    nightmux.companion_night(dict(cff, tz_offset=0), stw_, "night off")
                    assert [j["text"] for j in stw_["companion"]["sched"]] == ["w"]


def test_companion_gated_rounds():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        with tempfile.TemporaryDirectory() as cd_:
            cd_ = os.path.join(cd_, "comp")
            os.makedirs(cd_)
            with nightmux.stubbed(COMPANION_DIR=cd_):
                now_ = time.time()
                rows_ = [{"topic": "5", "session": "shop", "mode": "idle", "budget": "1M of 5M this day"},
                         {"topic": "6", "session": "blog", "mode": "waiting"},
                         {"topic": "8", "session": "old", "mode": "idle"},
                         {"topic": "9", "session": "comp", "mode": "idle"}]
                chat_ = {"5": [{"id": i, "t": now_, "who": "bot", "text": f"✅ shop\nstep {i}\nmore"} for i in range(1, 8)],
                         "9": [{"id": 50, "t": now_, "who": "bot", "text": "me"}]}
                cfgp = {"companion": {"topic": "9"}, "dirs": {"5": cd_}}
                # Gated rounds: the report rides in the prompt; nothing new, no model call;
                # a big thread is cleared first unless the owner spoke within the hour.
                with nightmux.stubbed(topics_status=lambda c, s: rows_[0:1], _chat=chat_, tmux_git=lambda *a: "",
                             agent_key=lambda c, t, s: "claude"):
                    stw = {"comp": {"ctx_tok": 200000, "sched": [
                        {"at": 0, "every": 3600, "text": "w", "watch": True, "companion": True,
                         "progress": True, "gate": True, "since": now_ - 60}]}}
                    sent_ = []
                    with nightmux.stubbed(send=lambda *a, **k: sent_.append(a)):
                        nightmux.due(cfgp, stw, "9", "comp")
                        q_ = stw["comp"]["queue"]
                        # a saved round runs today's prompt, not the "w" it was saved with
                        assert q_[0] == "/clear" and q_[1].startswith(nightmux.COMPANION_WATCH + "\n\nProgress since "), q_
                        assert "▸ shop (topic 5)" in q_[1] and not sent_        # no ⏰ ping
                        stw["comp"]["queue"], stw["comp"]["sched"][0]["at"] = [], 0
                        nightmux.due(cfgp, stw, "9", "comp")                 # nothing new since
                        assert not stw["comp"]["queue"] and stw["comp"]["sched"][0]["at"] > now_
                        chat_["5"].append({"id": 9, "t": time.time() + 1, "who": "bot", "text": "✅ shop\nadded tests"})
                        chat_["9"] = [{"id": 10, "t": time.time(), "who": "you", "text": "hi"}]
                        stw["comp"]["sched"][0]["at"] = 0
                        nightmux.due(cfgp, stw, "9", "comp")
                        q_ = stw["comp"]["queue"]
                        assert len(q_) == 1 and "added tests" in q_[0], q_   # owner just spoke: no /clear


def test_suggest_ledger_limits_signals_log_and_roles():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        with tempfile.TemporaryDirectory() as cd_:
            cd_ = os.path.join(cd_, "comp")
            os.makedirs(cd_)
            with nightmux.stubbed(COMPANION_DIR=cd_):
                os.makedirs(os.path.join(cd_, "roles"))
                for rel_, text_ in nightmux.COMPANION_SEED.items():
                    with open(os.path.join(cd_, rel_), "w") as f:
                        f.write(text_)
                now_ = time.time()
                rows_ = [{"topic": "5", "session": "shop", "mode": "idle", "budget": "1M of 5M this day"},
                         {"topic": "6", "session": "blog", "mode": "waiting"},
                         {"topic": "8", "session": "old", "mode": "idle"},
                         {"topic": "9", "session": "comp", "mode": "idle"}]
                cfg_ = {"budgets": {"5": {"tokens": 1000, "per": "day"}}}
                # suggest: a ledger on disk, so ▶ works after a restart and taps teach it;
                # 3 waiting per topic, 6 an hour, a dropped idea never comes back.
                sent_ = []
                with nightmux.stubbed(send=lambda c, t, x, **k: sent_.append((t, x, k.get("buttons")))):
                    del nightmux._idea_times[:]
                    cfgs = {"topics": {"5": "shop", "6": "blog"}}
                    p1 = "[role: tester] b\n\nTask: add a test for cart totals"
                    assert "posted" in nightmux.suggest_post(cfgs, "5", p1)
                    t_, x_, btn = sent_[-1]
                    assert t_ == "5" and x_.endswith("add a test for cart totals") and "!suggest run" in btn
                    sid1 = re.search(r"!suggest run (\w+)", btn).group(1)
                    assert "no project" in nightmux.suggest_post(cfgs, "7", "x")
                    nightmux.suggest_post(cfgs, "5", "idea 0")
                    sid2 = re.search(r"!suggest drop (\w+)", sent_[-1][2]).group(1)
                    nightmux.suggest_post(cfgs, "5", "idea 1")
                    assert "3 ideas already wait" in nightmux.suggest_post(cfgs, "5", "idea 2")
                    got_p = []
                    with nightmux.stubbed(send_prompt=lambda c, s, t, se, p, mid=None: got_p.append((t, p)) or "sent"):
                        nightmux.handle(dict(cfgs), {}, threading.Lock(), "5", f"!suggest run {sid1}")
                        assert got_p == [("5", p1)]
                        assert "already taken" in nightmux.handle(dict(cfgs), {}, threading.Lock(), "5", f"!suggest run {sid1}")
                        assert "dropped" in nightmux.handle(dict(cfgs), {}, threading.Lock(), "5", f"!suggest drop {sid2}")
                        assert "already taken" in nightmux.handle(dict(cfgs), {}, threading.Lock(), "6", f"!suggest run {sid2}")
                    assert "dropped this exact idea" in nightmux.suggest_post(cfgs, "5", "idea 0")
                    stats_ = nightmux.idea_stats()
                    assert "▶ 1 sent · ✕ 1 dropped · 0 ignored · 1 waiting" in stats_ and "idea 0" in stats_, stats_
                    assert "1 ignored" in nightmux.idea_stats(time.time() + nightmux.IDEA_STALE + 60)
                    for i in range(3):
                        nightmux.suggest_post(cfgs, "6", f"blog idea {i}")
                    assert "6 ideas" in nightmux.suggest_post(cfgs, "6", "one more")
                # the signals an expert scans for: goal state, errors, uncommitted work, the plan
                os.makedirs(os.path.join(cd_, ".nightmux"), exist_ok=True)
                with open(os.path.join(cd_, ".nightmux", "memory.md"), "w") as f:
                    f.write("# x\n## Decisions\n- a\n## In progress / next\n- ship checkout\n- add coupons\n")
                with nightmux.stubbed(topics_status=lambda c, s: rows_[0:1], _err_log=[(time.time(), "5", "KeyError: cart")],
                             _chat={"5": [{"id": 1, "t": time.time(), "who": "bot", "text": "🛑 goal stuck — x"}]},
                             tmux_git=lambda cwd, *a: " 2 files changed, 10 insertions(+)" if a[0] == "diff" else "true" if a[0] == "rev-parse" else ""):
                    rep4 = nightmux.progress_report({"dirs": {"5": cd_}}, {}, time.time() - 60)
                    for want in ("🎯 🛑 goal stuck", "🚨 1 production error: KeyError: cart",
                                 "uncommitted: 2 files changed", "next: ship checkout", "next: add coupons",
                                 "ideas, 7 days:"):
                        assert want in rep4, (want, rep4)
                assert {"progress", "suggest"} <= {t["name"] for t in nightmux.NM_TOOLS}
                nightmux.companion_log({"topic": "5", "role": "tester"}, "[role: tester] brief\n\nTask: add tests\nmore")
                with open(os.path.join(cd_, "actions.log")) as f:
                    assert f.read().endswith("topic=5 role=tester add tests\n")
                out = nightmux.companion_prompt(cfg_, "5", "fix it", "reviewer")
                assert out.startswith("[role: reviewer] You are the reviewer") and out.endswith("Task: fix it")
                for bad in ("../PERSONA", "nope"):
                    try:
                        nightmux.companion_prompt(cfg_, "5", "x", bad)
                        assert False, bad
                    except ValueError:
                        pass


def test_companion_priorities_and_allowance():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        # Companion revamp: priorities from PERSONA.md, an allowance for unbudgeted
        # projects, projects with no session, and talking to it through !companion.
        cdir_, pdir_ = tempfile.mkdtemp(), tempfile.mkdtemp()
        os.makedirs(os.path.join(pdir_, ".nightmux"))
        with open(os.path.join(pdir_, ".nightmux", "memory.md"), "w") as f:
            f.write("# x\n## In progress / next\n- ask the owner for sample SMS\n")
        with open(os.path.join(cdir_, "PERSONA.md"), "w") as f:
            f.write("# P\n## Priorities\n1. nightmux (x) — a\n2. Pennywise — b\n3. (project)\n## Tone\n")
        ccf_ = {"topics": {"0": "companion", "7": "work"}, "topic_names": {"9": "Pennywise"},
                "dirs": {"7": "/srv/nightmux", "9": pdir_}, "companion": {"topic": "0", "session": "companion"}}
        with nightmux.stubbed(COMPANION_DIR=cdir_, sav_path=lambda: os.path.join(cdir_, "sav.json")):
            assert nightmux.persona_priorities(ccf_) == ["7", "9"], nightmux.persona_priorities(ccf_)
            try:
                nightmux.companion_prompt(ccf_, "9", "go")
                raise AssertionError("no budget and no allowance must refuse")
            except ValueError as e:
                assert "no allowance" in str(e), e
            ccf_["budgets"] = {"0": {"tokens": 1000, "per": "day"}}
            assert nightmux.companion_prompt(ccf_, "9", "go") == "go"          # the allowance covers it
            nightmux.companion_log({"topic": "7"}, "go")
            hr_ = int(time.time() // 3600)
            with open(os.path.join(cdir_, "sav.json"), "w") as f:
                json.dump({"spent": {"work": {str(hr_): 1500}}}, f)
            assert nightmux.companion_allowance(ccf_)[:2] == (1500, 1000)
            try:
                nightmux.companion_prompt(ccf_, "9", "go")
                raise AssertionError("a spent allowance must refuse")
            except ValueError as e:
                assert "allowance is spent" in str(e), e
            with nightmux.stubbed(topics_status=lambda c, st: [], tmux_git=lambda *a: ""):
                rep_ = nightmux.progress_report(ccf_, {}, time.time() - 3600)
            assert "Pennywise (topic 9) [no session]" in rep_ and "⭐ priority 2" in rep_, rep_
            assert "next: ask the owner for sample SMS" in rep_, rep_
            cst_ = {}
            with nightmux.stubbed(has_session=lambda n: True, save_queue=lambda st: None):
                assert "passed" in nightmux.companion_cmd(ccf_, cst_, threading.Lock(), "0", "work on pennywise")
            assert cst_["companion"]["queue"] == ["work on pennywise"], cst_
            with nightmux.stubbed(save_queue=lambda st: None):
                nightmux.companion_watch(ccf_, cst_, "watch 3h")
            job_ = cst_["companion"]["sched"][-1]
            assert job_["at"] - time.time() < 120 and time.time() - job_["since"] > 3 * 3600 - 60, job_
        shutil.rmtree(cdir_, ignore_errors=True)
        shutil.rmtree(pdir_, ignore_errors=True)


def test_peer_priority_not_woken_here():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        # A priority on a peer is never woken here, where its folder is empty.
        try:
            nightmux.companion_wake("http://127.0.0.1:1", {"dirs": {"9": "/tmp"}, "remote": {"9": "vps2"}}, "9")
            raise AssertionError("woke a remote topic locally")
        except ValueError as e_:
            assert "vps2" in str(e_), e_
