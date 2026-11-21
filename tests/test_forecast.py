"""test_forecast: cut from the old monolithic selfcheck() (the last part)."""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_forecast_warns_once_per_window():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        # Forecast: a rising window is projected to 100% before it resets; a new
        # window starts a new line; warned once, to topics actually on that agent.
        nightmux._fc.clear(); nightmux._fc_told.clear()
        t0_ = 1_700_000_000
        nightmux.fc_sample({"claude:5h": (40, t0_ + 18000)}, t0_)
        nightmux.fc_sample({"claude:5h": (60, t0_ + 18000)}, t0_ + 1800)          # +40%/h
        assert nightmux.forecast("claude:5h", t0_ + 1800) == t0_ + 1800 + 3600     # 40% more: an hour
        nightmux.fc_sample({"claude:5h": (5, t0_ + 36000)}, t0_ + 1900)            # reset: new window
        assert len(nightmux._fc["claude:5h"]["pts"]) == 1 and nightmux.forecast("claude:5h") is None
        fsaid_ = []
        with nightmux.stubbed(windows_now=lambda st: {"claude:5h": (80, None)}, installed_agents=lambda c: ["claude", "codex"],
                     send=lambda c, t, x, mode="mono", buttons=None, quiet=False: fsaid_.append((t, x, buttons))):
            nightmux._fc.clear()
            nightmux._fc["claude:5h"] = {"resets": None, "pts": [(time.time() - 1800, 60)]}
            fcfg_ = {"topics": {"1": "a", "2": "b"}, "started": {"1": "claude", "2": "codex"}}
            nightmux._fc_at[0] = 0
            nightmux.forecast_tick(fcfg_, {"a": {"mode": "busy"}, "b": {"mode": "busy"}})
            assert [t for t, _, _ in fsaid_] == ["1"] and "+40%/h" in fsaid_[0][1] and "!codex" in fsaid_[0][2]
            nightmux._fc_at[0] = 0
            nightmux.forecast_tick(fcfg_, {"a": {"mode": "busy"}})
            assert len(fsaid_) == 1                                       # once per window
        nightmux._fc.clear(); nightmux._fc_told.clear()
