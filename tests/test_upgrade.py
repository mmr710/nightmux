"""test_upgrade: cut from the old monolithic selfcheck() (the last part)."""
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_upgrade_fast_forwards_and_rolls_back():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        # !upgrade: a git checkout fast-forwards, refuses over local edits, rolls
        # back code that does not compile; a branch and a detached deploy both move.
        with tempfile.TemporaryDirectory() as ud_:
            g_ = lambda d, *a: subprocess.run(("git", "-C", d) + a, capture_output=True, text=True)
            org_, wk_, dep_ = (os.path.join(ud_, x) for x in ("o", "w", "d"))
            subprocess.run(("git", "init", "-q", "-b", "main", org_), capture_output=True)
            for d_ in (org_,):
                g_(d_, "config", "user.email", "t@t")
                g_(d_, "config", "user.name", "t")
            with open(os.path.join(org_, "nightmux.py"), "w") as f:
                f.write("x = 1\n")
            g_(org_, "add", "-A")
            g_(org_, "commit", "-qm", "one")
            subprocess.run(("git", "clone", "-q", org_, wk_), capture_output=True)
            subprocess.run(("git", "clone", "-q", org_, dep_), capture_output=True)
            g_(dep_, "checkout", "-q", "--detach")
            assert nightmux.self_upgrade(wk_)[1].startswith("already up to date"), nightmux.self_upgrade(wk_)
            with open(os.path.join(org_, "nightmux.py"), "w") as f:
                f.write("x = 2\n")
            g_(org_, "commit", "-qam", "two")
            with open(os.path.join(wk_, "nightmux.py"), "w") as f:
                f.write("mine\n")
            assert "local edits" in nightmux.self_upgrade(wk_)[1]
            g_(wk_, "checkout", "-q", "--", ".")
            assert nightmux.self_upgrade(wk_)[0] and nightmux.self_upgrade(dep_)[0]
            assert open(os.path.join(dep_, "nightmux.py")).read() == "x = 2\n"
            with open(os.path.join(org_, "nightmux.py"), "w") as f:
                f.write("def (:\n")
            g_(org_, "commit", "-qam", "broken")
            ch_, msg_ = nightmux.self_upgrade(wk_)
            assert not ch_ and "does not compile" in msg_, msg_
            assert open(os.path.join(wk_, "nightmux.py")).read() == "x = 2\n"
        assert nightmux.latest_release_tag(["v1.9.0", "v1.10.0", "v1.11.0-rc1", "vps-test", "v1.10"]) == "v1.10.0"
        assert nightmux.latest_release_tag(["vps-test", "v2-rc"]) is None
        usaid_, ure_ = [], []
        with nightmux.stubbed(self_upgrade=lambda: (True, "a → b"), restart_self=lambda: ure_.append(1),
                     peer_call=lambda c, n, p, b=None, timeout=10: {"msg": "1.3 → 1.4 · restarting"} if n == "box" else None,
                     send=lambda c, t, x, mode="mono", buttons=None, quiet=False: usaid_.append(x)):
            assert "every peer" in nightmux.upgrade_cmd({"peers": {"box": {}, "old": {}}, "name": "me"}, "1", "all")
            for _ in range(100):
                if usaid_:
                    break
                time.sleep(0.02)
        assert ure_ and "me: a → b · restarting" in usaid_[0] and "box: 1.3 → 1.4" in usaid_[0], usaid_
        assert "old: no answer" in usaid_[0] and nightmux.writes({}, "!upgrade", ""), usaid_
