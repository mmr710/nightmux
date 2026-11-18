"""test_watch: cut from the old monolithic selfcheck() (stubbed part)."""
import concurrent
import json
import os
import queue
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_preview_finds_session_http_servers():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # !preview finds what the session's own processes serve over HTTP — by
        # process tree, not port guessing — and links it on the tailnet.
        if shutil.which("ss"):
            sk_ = socket.socket()
            sk_.bind(("127.0.0.1", 0))
            dport_ = sk_.getsockname()[1]
            sk_.close()
            dev_ = subprocess.Popen([sys.executable, "-m", "http.server", str(dport_),
                                     "--bind", "127.0.0.1"], stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            try:
                for _ in range(100):
                    if nightmux.answers_http(dport_):
                        break
                    time.sleep(0.05)
                assert (dport_, True) in [p[:2] for p in nightmux.dev_ports("x", {dev_.pid})]
                assert nightmux.dev_ports("x", {os.getpid() + 999999}) == []       # not ours
            finally:
                dev_.kill()
        served_ = []
        with nightmux.stubbed(run=lambda *a, **k: served_.append(a) or "Available within your tailnet"):
            pcfg2_ = {"office_url": "https://box.ts.net/office"}
            assert nightmux.preview_link(pcfg2_, 5173, True) == ("https://box.ts.net:5173/", "")
            assert served_[-1][:4] == ("tailscale", "serve", "--bg", "--https=5173"), served_
            assert nightmux.preview_link(pcfg2_, 3000, False) == ("http://box.ts.net:3000/", "")
            assert len(served_) == 1                  # already on the tailnet: no serve


def test_watch_pr_queues_failures_once():
    # slow
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # !watch pr: a failed check's log and new review comments are queued to the
        # agent once each; the gh account's own comments and pre-existing ones are
        # not; green pings once per commit; merged stops the watch.
        prv_ = {"state": "OPEN", "url": "u", "headRefOid": "abc123def4567",
                "statusCheckRollup": [{"name": "selfcheck", "conclusion": "FAILURE",
                                       "detailsUrl": "https://github.com/o/r/actions/runs/42/job/1"}],
                "reviews": [], "comments": [{"id": "c1", "author": {"login": "rev"}, "body": "old"}]}
        inl_, wsaid_ = [], []

        def fake_gh(cwd, *a, timeout=60):
            if a[:2] == ("api", "user"):
                return "me\n"
            if a[:2] == ("pr", "view"):
                return json.dumps(prv_)
            if a[:2] == ("run", "view"):
                return "setup\nE   assert 1 == 2\n"
            return json.dumps(inl_)
        nightmux._gh_me.clear()
        with nightmux.stubbed(gh=fake_gh, save_cfg=lambda c: None,
                     send=lambda c, t, x, mode="mono", buttons=None, quiet=False: wsaid_.append(x)):
            wcfg_, wst_, wlk_ = {"topics": {"3": "w"}, "dirs": {"3": "/"},
                                 "watch": {"3": {"pr": 7}}}, {}, threading.Lock()

            def wround():
                nightmux._watch_at.clear()
                nightmux.watch_tick(wcfg_, wst_, wlk_)
                for _ in range(200):
                    if nightmux._watch_run.get("3"):
                        break
                    time.sleep(0.02)
                nightmux.watch_tick(wcfg_, wst_, wlk_)
            wround()
            wq_ = wst_["w"]["queue"]
            assert len(wq_) == 1 and "assert 1 == 2" in wq_[0] and "old" not in wq_[0], wq_
            wround()
            assert len(wq_) == 1                                   # not resent
            prv_["comments"] += [{"id": "c2", "author": {"login": "rev"}, "body": "rename foo"},
                                 {"id": "c3", "author": {"login": "me"}, "body": "agent reply"}]
            inl_.append({"id": 5, "user": {"login": "rev"}, "path": "a.py", "line": 3,
                         "body": "off by one"})
            wround()
            assert len(wq_) == 2 and "rename foo" in wq_[1] and "a.py:3" in wq_[1], wq_
            assert "agent reply" not in wq_[1]
            prv_["statusCheckRollup"][0]["conclusion"], prv_["headRefOid"] = "SUCCESS", "fff000111222"
            wround()
            wround()
            assert sum("every check green" in x for x in wsaid_) == 1, wsaid_
            prv_["state"] = "MERGED"
            wround()
            assert "3" not in wcfg_["watch"] and "stopped watching" in wsaid_[-1], wsaid_


def test_saved_prompts_args_filled():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # !p: saved prompts, {{args}} filled, config overrides and hides built-ins.
        assert nightmux.fill("Explain {{args}}: short.", "auth.py") == "Explain auth.py: short."
        assert nightmux.fill("Review the diff. {{args}}", "") == "Review the diff."
        assert nightmux.fill("Do it", "now") == "Do it now"
        psent2_ = []
        with nightmux.stubbed(save_cfg=lambda c: None,
                     send_prompt=lambda c, st, t, ss, x, mid=None: psent2_.append(x) or "sent"):
            pc_, plk_ = {"topics": {"8": "p"}}, threading.Lock()
            assert "saved" in nightmux.prompt_cmd(pc_, {}, plk_, "8", "p", "save hi Say hi to {{args}} please")
            nightmux.prompt_cmd(pc_, {}, plk_, "8", "p", "hi Bob")
            assert psent2_[-1] == "Say hi to Bob please", psent2_
            nightmux.prompt_cmd(pc_, {}, plk_, "8", "p", "rm review")
            assert "review" not in nightmux.prompts(pc_) and "no prompt" in nightmux.prompt_cmd(pc_, {}, plk_, "8", "p", "review")


def test_idea_gets_own_folder_and_build_prompt():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # !idea: its own folder under projects_root (never on top of another), git,
        # the agent started with the build prompt queued, and the check loop on.
        assert nightmux.slugify("A habit tracker, with streaks & charts!") == "a-habit-tracker-with"
        with tempfile.TemporaryDirectory() as ir_, nightmux.stubbed(
                spawn=lambda *a: None, has_session=lambda n: False, save_cfg=lambda c: None):
            os.makedirs(os.path.join(ir_, "habits"))          # taken: must not reuse it
            icfg_, ist_ = {"topics": {}, "projects_root": ir_,
                           "topic_names": {"12": "Habits"}}, {}
            out_ = nightmux.idea_cmd(icfg_, ist_, threading.Lock(), "12", "@codex a habit tracker")
            idir_ = os.path.join(ir_, "habits-2")
            assert icfg_["topics"]["12"] == "habits-2" and icfg_["started"]["12"] == "codex", out_
            assert os.path.isdir(os.path.join(idir_, ".git")), out_
            assert "a habit tracker" in ist_["habits-2"]["queue"][0]
            assert icfg_["goals"]["12"]["cmd"] == "sh ./check.sh"
            assert "already runs" in nightmux.idea_cmd(icfg_, ist_, threading.Lock(), "12", "more")
            icfg_["goals"].clear()


def test_transcript_fed_delivery_and_held_work_dropped():
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

        # transcript-fed delivery: the pane stops being the source of truth
        state.clear(), sent.clear(), edits.clear()
        tp = os.path.join(nightmux.FILE_DIR, "live.jsonl")
        open(tp, "w").close()
        with open(os.path.join(nightmux.STATE_DIR, "live.json"), "w") as f:
            json.dump({"ts": time.time(), "pane": "%5", "transcript": tp,
                       "five_hour": {"used_percentage": 12, "resets_at": None}}, f)
        screen[:] = ["● Read(x.py)", "✻ Brewing… (3s · esc to interrupt)"]
        nightmux.flush_new(cfg, state, "1", "s", "%5")      # baseline the transcript
        with open(tp, "a") as f:
            f.write(json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "x.py"}}]}}) + "\n")
        st = state["s"]
        st["prog_at"] = nightmux._prog_at[0] = 0
        nightmux.flush_new(cfg, state, "1", "s", "%5")      # busy: trace comes from the file
        assert sent[-1] == "⚙️ s\n● Read(x.py)", sent[-1]
        with open(tp, "a") as f:
            f.write(json.dumps({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "**done** at last"}]}}) + "\n")
        screen[:] = ["● Read(x.py)", "● and some chrome the pane shows"] + box
        twice_p = lambda: [nightmux.flush_new(cfg, state, "1", "s", "%5") for _ in range(2)]
        twice_p()
        assert sent[-1] == "✅ s\n● Read(x.py)\n**done** at last", sent[-1]
        assert "s" in state and not state["s"].get("tbuf")
        twice_p()                                     # nothing new in the file: silence
        assert sent[-1].startswith("✅ s\n● Read")
        nightmux.live_sessions = lambda: {"s": "%5"}
        report = nightmux.status_report({"topics": {"1": "s"}}, state)
        assert "5h 12%" in report and "no status line" not in report, report
        held, state["s"]["snap"] = state["s"]["snap"], None    # watched through the
        assert "[no status line]" in nightmux.status_report({"topics": {"1": "s"}}, state)
        state["s"]["snap"] = held                             # keyhole, and saying so
        os.remove(tp)

        cfg["topics"] = {"1": "s"}                    # status + watchdog
        assert "✅ s" in nightmux.status_report(cfg, state) and "topic 1" in nightmux.status_report(cfg, state)
        n = len(sent)                                 # gone before this run ever saw it:
        assert nightmux.watchdog(cfg, state, "1", "ghost", False) is False and len(sent) == n
        assert state.pop("ghost")["dead"]             # marked, not announced
        state["s"]["seen"] = True                     # "s" was alive earlier this run
        assert nightmux.watchdog(cfg, state, "1", "s", False) is False and "💀" in sent[-1]
        n = len(sent)
        nightmux.watchdog(cfg, state, "1", "s", False)         # dead stays quiet after the first
        assert len(sent) == n

        # Held work for a session no topic watches is dropped, not "restored" on
        # every restart forever; a benched agent's is its topic's, and kept.
        rcfg = {"topics": {"1": "s"}, "started": {"1": "claude"},
                "bench": {"1": {"claude": "s", "agy": "s-agy"}}}
        rstate = {}

        def fake_load(st):
            held = {"orphan": {"queue": ["lost"]}, "s-agy": {"queue": ["kept"]}}
            st.update({k: dict(v) for k, v in held.items()})
            return held
        with nightmux.stubbed(load_queue=fake_load):
            nightmux.restore_held(rcfg, rstate)
        assert "orphan" not in rstate and rstate["s-agy"]["queue"] == ["kept"], rstate
        assert len(sent) == n + 1 and "1 queued prompt(s) kept" in sent[-1], sent[n:]
        state["s"].update(queue=["held"], limit_until=time.time() + 60, scr=["junk"])
        nightmux.watchdog(cfg, state, "1", "s", True)
        assert "↩️" in sent[-1] and "scr" not in state["s"]   # rebaselined, no dump
        assert state["s"]["queue"] == ["held"]        # ...but the hold is not a cache
        state.pop("s")
        nightmux.live_sessions = lambda: {}
        assert "💀 gone" in nightmux.status_report({"topics": {"2": "gone"}}, {})


def test_watch_pool_overlaps_slow_session():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        # watcher()'s per-session tick runs through a pool now (see watch_one) so
        # that one laggy tmux round-trip cannot stall every other session's update
        # behind it. Prove the overlap directly: stub watchdog() to sleep for one
        # session and return at once for the other, submit the slow one FIRST — a
        # regressed-to-serial loop would finish it, and only then start the fast
        # one — and check the fast one still lands almost immediately.
        order, marks = [], {}

        def _slow_watchdog(cfg, state, topic, sess, alive):
            if sess == "slow":
                time.sleep(0.3)
            marks[sess] = time.time()
            order.append(sess)
            return False   # skip watch_one's body; only the overlap matters here

        with nightmux.stubbed(watchdog=_slow_watchdog):
            conc_state, conc_lock, t0 = {}, threading.Lock(), time.time()
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                futs = [pool.submit(nightmux.watch_one, {}, conc_state, conc_lock, "1", s, {})
                        for s in ("slow", "fast")]   # slow submitted first, on purpose
                for fut in concurrent.futures.as_completed(futs):
                    fut.result()
        assert order == ["fast", "slow"], order          # fast finished first despite going in second
        assert marks["fast"] - t0 < 0.15, marks           # not stuck queued behind slow's 0.3s
