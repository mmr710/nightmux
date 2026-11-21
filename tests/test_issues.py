"""test_issues: cut from the old monolithic selfcheck() (stubbed part)."""
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_issues_become_prompt_and_branch():
    # slow
    with isolated(nightmux):
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # !issues: an issue becomes a prompt + branch; the watch finds the branch's PR
        # and from then on is a normal PR watch; auto takes the next labelled issue.
        br_, ip_ = nightmux.issue_prompt({"number": 12, "title": "Crash on empty cart!", "url": "u",
                                 "body": "steps", "comments": [{"author": {"login": "bo"}, "body": "me too"}]})
        assert br_ == "issue-12-crash-on-empty-cart" and "Fixes #12" in ip_ and "@bo: me too" in ip_
        isaid_, iprs_ = [], []

        def fake_gh2(cwd, *a, timeout=60):
            if a[:2] == ("api", "user"):
                return "me\n"
            if a[:2] == ("pr", "view"):
                return json.dumps({"state": "OPEN", "url": "u", "headRefOid": "0" * 40,
                                   "statusCheckRollup": [], "reviews": [], "comments": []})
            if a[:2] == ("pr", "list"):
                return json.dumps(iprs_)
            if a[:2] == ("issue", "list"):
                return json.dumps([{"number": 3}, {"number": 5}])
            if a[:2] == ("issue", "view"):
                return json.dumps({"number": int(a[2]), "title": "t" + a[2], "body": "", "url": "u",
                                   "comments": [], "state": "OPEN"})
            return "[]"
        with nightmux.stubbed(gh=fake_gh2, save_cfg=lambda c: None,
                     send=lambda c, t, x, mode="mono", buttons=None, quiet=False: isaid_.append(x)):
            icfg2_, ist2_, ilk_ = {"topics": {"7": "s"}, "dirs": {"7": "/"}}, {"s": {"mode": "idle"}}, threading.Lock()
            assert "watching for its PR" in nightmux.issues_cmd(icfg2_, ist2_, ilk_, "7", "s", "!issue", "#5")
            assert icfg2_["watch"]["7"] == {"branch": "issue-5-t5", "issue": 5}
            assert "issue-5-t5" in ist2_["s"]["queue"][0]

            def tick_watch():
                nightmux._watch_at.clear()
                nightmux.watch_tick(icfg2_, ist2_, ilk_)
                for _ in range(200):
                    if nightmux._watch_run.get("7"):
                        break
                    time.sleep(0.02)
                nightmux.watch_tick(icfg2_, ist2_, ilk_)
            tick_watch()
            assert "pr" not in icfg2_["watch"]["7"]            # not opened yet
            iprs_.append({"number": 44})
            tick_watch()
            assert icfg2_["watch"]["7"]["pr"] == 44 and "PR #44 opened for issue #5" in isaid_[-1]
            # auto: the topic is quiet and nothing is watched -> next labelled, not done
            icfg2_["watch"] = {}
            ist2_["s"] = {"mode": "idle", "changed": 0}
            icfg2_["issues_auto"] = {"7": "nightmux"}
            nightmux._issue_at.clear()
            nightmux.issues_tick(icfg2_, ist2_, ilk_, time.time())
            for _ in range(200):
                if nightmux._issue_run.get("7"):
                    break
                time.sleep(0.02)
            nightmux.issues_tick(icfg2_, ist2_, ilk_, time.time())
            assert icfg2_["watch"]["7"]["issue"] == 3 and "#3" in isaid_[-1], isaid_[-1]
            nightmux._watch_run.clear()
