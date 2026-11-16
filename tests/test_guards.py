"""test_guards: cut from tests/selfcheck.py (stubbed part)."""
import os
import shutil
import subprocess
import sys
import tempfile
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_ghost_pair_reviewer():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # Ghost pair: a turn that changed the tree goes to the reviewer (in the same
        # folder, by diff range); its findings go to the coder, LGTM is a 👍, a turn
        # that changed nothing is not reviewed.
        psaid3_ = []
        with tempfile.TemporaryDirectory() as pg_, nightmux.stubbed(
                spawn=lambda *a: None, has_session=lambda n: n == "c", save_cfg=lambda c: None,
                send=lambda c, t, x, mode="mono", buttons=None, quiet=False: psaid3_.append(x)):
            for a_ in (("init", "-q"), ("-c", "user.email=a@b", "-c", "user.name=a", "commit",
                                        "-q", "--allow-empty", "-m", "init")):
                subprocess.run(("git", "-C", pg_) + a_, check=True)
            pcfg3_ = {"topics": {"9": "c"}, "dirs": {"9": pg_}, "started": {"9": "claude"}}
            pst3_ = {"c": {"mode": "idle"}}
            nightmux._pair.clear()
            assert "now reviews" in nightmux.pair_cmd(pcfg3_, pst3_, threading.Lock(), "9", "c", "codex")
            assert pcfg3_["bench"]["9"]["codex"] == "c-codex"
            nightmux.pair_capture(pcfg3_, "9", "c", "renamed nothing")
            nightmux.pair_tick(pcfg3_, pst3_, threading.Lock())
            assert not pst3_.get("c-codex")                      # no change, no review
            with open(os.path.join(pg_, "a.py"), "w") as f:
                f.write("x = 1\n")
            subprocess.run(("git", "-C", pg_, "add", "a.py"), check=True)
            nightmux.pair_capture(pcfg3_, "9", "c", "added a.py")
            nightmux.pair_tick(pcfg3_, pst3_, threading.Lock())
            assert "git diff" in pst3_["c-codex"]["queue"][0] and "added a.py" in pst3_["c-codex"]["queue"][0]
            assert nightmux.pair_review_capture("9", "c-codex", "a.py:1 — x is unused — drop it")
            nightmux.pair_tick(pcfg3_, pst3_, threading.Lock())
            assert "x is unused" in pst3_["c"]["queue"][0] and "found issues" in psaid3_[-1]
            pst3_["c"]["queue"] = []
            nightmux.pair_capture(pcfg3_, "9", "c", "fixed")
            with open(os.path.join(pg_, "a.py"), "w") as f:
                f.write("y = 2\n")
            nightmux.pair_tick(pcfg3_, pst3_, threading.Lock())
            assert nightmux.pair_review_capture("9", "c-codex", "LGTM")
            nightmux.pair_tick(pcfg3_, pst3_, threading.Lock())
            assert psaid3_[-1].endswith("LGTM 👍") and not pst3_["c"]["queue"], psaid3_
            assert "different agent" in nightmux.pair_cmd(pcfg3_, pst3_, threading.Lock(), "9", "c", "claude")
            nightmux._pair.clear()


def test_loop_guard_two_signs():
    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # Loop guard: two independent signs of circling ping once, with a cooldown;
        # one sign alone (a long refactor of one file) does not.
        lsaid_ = []
        with nightmux.stubbed(numstat=lambda cwd: dict(lfiles_), save_cfg=lambda c: None,
                     send=lambda c, t, x, mode="mono", buttons=None, quiet=False: lsaid_.append((x, buttons))):
            lgit_ = tempfile.mkdtemp()
            os.makedirs(os.path.join(lgit_, ".git"))
            lcfg_, lst_ = {"topics": {"6": "l"}, "dirs": {"6": lgit_}, "started": {"6": "claude"},
                           "loopguard": "auto"}, {"l": {}}
            nightmux._loop.clear()
            lfiles_ = {"a.py": 10}
            for i_ in range(5):                      # one file churned, diff flat: one sign
                lfiles_["a.py"] = 10 + (i_ % 2)
                nightmux.loop_capture(lcfg_, "6", "l", "refactored a.py")
                nightmux.loop_tick(lcfg_, lst_, threading.Lock())
            assert not lsaid_
            for i_ in range(3):                      # plus the same error every turn: two
                lfiles_["a.py"] = 10 + (i_ % 2) + 2
                nightmux.loop_capture(lcfg_, "6", "l", f"Ran tests\nE   AssertionError: got {i_}")
                nightmux.loop_tick(lcfg_, lst_, threading.Lock())
            assert len(lsaid_) == 1 and "looks stuck" in lsaid_[0][0], lsaid_
            assert "same error" in lsaid_[0][0] and "a.py edited" in lsaid_[0][0], lsaid_[0][0]
            assert "circling" in lst_["l"]["queue"][0] and "hand to codex" in lsaid_[0][1]
            nightmux.loop_capture(lcfg_, "6", "l", "E   AssertionError: got 9")
            nightmux.loop_tick(lcfg_, lst_, threading.Lock())
            assert len(lsaid_) == 1                  # cooldown
            nightmux._loop.clear()
            shutil.rmtree(lgit_)
