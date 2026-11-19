"""test_swallowed: _swallowed keeps the last 50 and --doctor shows them."""
import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402


def test_swallowed_ring_and_doctor():
    nightmux._SWALLOWED.clear()
    for i in range(60):
        nightmux._swallowed(f"site{i}", ValueError(f"bad {i}"))
    assert len(nightmux._SWALLOWED) == 50 and nightmux._SWALLOWED[0][1] == "site10"
    buf = io.StringIO()
    with nightmux.stubbed(setup_checks=lambda *a: []), contextlib.redirect_stdout(buf):
        nightmux.doctor()
    out = buf.getvalue()
    assert "site59: ValueError: bad 59" in out and "site49" not in out
    with nightmux.stubbed(setup_checks=lambda *a: []):
        rep = nightmux.doctor_report({})      # !doctor, in the daemon where they pile up
    assert "site59: ValueError: bad 59" in rep and "site49" not in rep
    nightmux._SWALLOWED.clear()
