"""test_goals: cut from the old monolithic selfcheck() (stubbed part)."""
import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_goal_red_check_returns_to_agent():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # !goal: a red check goes back to the agent as its next prompt, the same
        # failure three times stops and says so, green is reported once.
        gsaid_ = []
        with tempfile.TemporaryDirectory() as gd_, nightmux.stubbed(
                save_cfg=lambda c: None,
                send=lambda c, t, x, mode="mono", buttons=None, quiet=False: gsaid_.append(x)):
            gcfg_, gst_, glk_ = {"topics": {"4": "g"}, "dirs": {"4": gd_}}, {"g": {"mode": "idle"}}, threading.Lock()

            def goal_round():
                gst_["g"]["queue"] = []             # the agent took the last fix prompt
                nightmux.goal_capture(gcfg_, "4", "g")
                nightmux.goal_tick(gcfg_, gst_)
                for _ in range(200):
                    if "rc" in (nightmux._goal_run.get("4") or {}):
                        break
                    time.sleep(0.02)
                nightmux.goal_tick(gcfg_, gst_)
            assert "set" in nightmux.goal_cmd(gcfg_, glk_, "4", "5 echo boom-$RANDOM-12; exit 3")
            goal_round()
            q_ = gst_["g"]["queue"]
            assert len(q_) == 1 and "exit 3" in q_[0] and "boom" in q_[0] and "1/5" in q_[0], q_
            gst_["g"]["queue"] = ["yours"]          # your queued prompt goes first
            nightmux.goal_capture(gcfg_, "4", "g")
            nightmux.goal_tick(gcfg_, gst_)
            assert "4" not in nightmux._goal_run and "4" in nightmux._goal_due
            gst_["g"]["queue"] = []
            goal_round()
            goal_round()
            assert "same failure 3 times" in gsaid_[-1], gsaid_[-1]
            nightmux.goal_capture(gcfg_, "4", "g")           # paused: turns end, nothing runs
            assert "4" not in nightmux._goal_due
            nightmux.goal_cmd(gcfg_, glk_, "4", "true")
            goal_round()
            assert "✅ goal green: true" in gsaid_ and "/clear" in gst_["g"]["queue"], gsaid_[-2:]
            assert nightmux.goal_cmd(gcfg_, glk_, "4", "off") == "goal off" and not gcfg_["goals"]


def test_brain_next_repeat_done_ask():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        glk_ = threading.Lock()
        # !brain: NEXT queues the step, a repeat or DONE or ASK pauses and tells you.
        bsaid_, bcfg_, bst_ = [], {"topics": {"5": "b"}}, {"b": {"mode": "idle"}}
        with nightmux.stubbed(save_cfg=lambda c: None, brain_decide=lambda p: BRAIN_ANS_[0],
                     send=lambda c, t, x, mode="mono", buttons=None, quiet=False: bsaid_.append(x)):
            BRAIN_ANS_ = ["NEXT: write the tests"]
            assert nightmux.brain_cmd(bcfg_, glk_, "5", "3 ship it").startswith("🧠 brain set")

            def brain_round():
                nightmux.brain_capture(bcfg_, "5", "b", "did a thing")
                for _ in range(200):
                    if "out" in (nightmux._brain_run.get("5") or {}):
                        break
                    time.sleep(0.02)
                nightmux.brain_tick(bcfg_, bst_)
            brain_round()
            assert bst_["b"]["queue"] == ["write the tests"] and "step 1/3" in bsaid_[-1], bsaid_
            bst_["b"]["queue"] = []
            brain_round()                                   # same step again: it is looping
            assert "repeating itself" in bsaid_[-1] and nightmux._brain["5"]["paused"] and not bst_["b"]["queue"]
            nightmux.brain_capture(bcfg_, "5", "b", "x")             # paused: nothing runs
            assert "5" not in nightmux._brain_run
            assert "resumed" in nightmux.brain_cmd(bcfg_, glk_, "5", "resume")
            BRAIN_ANS_[0] = "DONE: login page shipped"
            brain_round()
            assert "mission done: login page shipped" in bsaid_[-1]
            assert nightmux.brain_cmd(bcfg_, glk_, "5", "off") == "brain off" and not bcfg_["brains"]


def test_po_roadmap_one_topic_per_item():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        glk_ = threading.Lock()
        # !po: roadmap parsed from the model's lines, approved, one topic+brain per item.
        psaid_, pcfg_, pst_ = [], {"topics": {"6": "p"}, "agents": {}}, {}
        ROAD_ = ("noise\n- Add login | claude | build login with tests\n"
                 "- Dark mode | nope | add a theme toggle\n")
        with tempfile.TemporaryDirectory() as pd_, nightmux.stubbed(
                save_cfg=lambda c: None, claude_once=lambda p, model="haiku", timeout=120: ROAD_,
                send=lambda c, t, x, mode="mono", buttons=None, quiet=False: psaid_.append(x),
                fan_go=lambda c, st, lk, t: (c.setdefault("fan_kids", {}).update({"k%d" % len(c.get("fan_kids", {})): t}),
                                             "ok")[1]):
            nightmux.po_draft(pcfg_, "6", pd_, "a todo app", "", glk_)
            its_ = pcfg_["po"]["6"]["items"]
            assert [i["title"] for i in its_] == ["Add login", "Dark mode"], its_
            assert its_[1]["agent"] == nightmux.default_agent(pcfg_) and "roadmap for: a todo app" in psaid_[-1]
            assert "started" in nightmux.po_go(pcfg_, pst_, glk_, "6", "1") and its_[0]["topic"] and not its_[1].get("topic")
            assert pcfg_["brains"][its_[0]["topic"]]["mission"].startswith("Add login:")
            assert "step 0" in nightmux.po_status(pcfg_, "6") and "not started" in nightmux.po_status(pcfg_, "6")
            assert nightmux.po_cmd(pcfg_, pst_, glk_, "6", "p", "off") == "roadmap dropped"
