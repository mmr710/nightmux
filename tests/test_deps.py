"""test_deps: cut from the old monolithic selfcheck() (the last part)."""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_deps_report_and_clean_run():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        # !deps: findings sorted worst first, reported with the fix button; a clean
        # nightly run says nothing.
        r_ = {"vulns": [("moderate", "a", "x"), ("critical", "b", "RCE")],
              "outdated": [("phaser", "3.90.0", "4.2.1")], "notes": []}
        r_["vulns"].sort(key=lambda v: nightmux.SEV.index(v[0]))
        rep_ = nightmux.deps_report(r_)
        assert rep_.startswith("🩺 1 critical, 1 moderate vulnerabilities") and "phaser 3.90.0 → 4.2.1" in rep_, rep_
        assert "critical: b (RCE)" in nightmux.deps_prompt(r_)
        dsaid_ = []
        with tempfile.TemporaryDirectory() as dd_, nightmux.stubbed(
                deps_scan=lambda cwd: {"vulns": [], "outdated": [], "notes": []},
                send=lambda c, t, x, mode="mono", buttons=None, quiet=False: dsaid_.append(x)):
            nightmux.deps_start({"dirs": {"4": dd_}}, "4", quiet=True)
            for _ in range(100):
                if "4" not in nightmux._deps_busy:
                    break
                time.sleep(0.02)
            assert dsaid_ == []
