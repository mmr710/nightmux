"""test_watch: cut from tests/selfcheck.py (stubbed part)."""
import json
import os
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
