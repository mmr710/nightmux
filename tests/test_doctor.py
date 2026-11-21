"""test_doctor: cut from the old monolithic selfcheck() (the last part)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_doctor_lines_and_overall():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        # --doctor: one ✓/✗ line per check, and the overall result is their AND.
        def _boom():
            raise OSError("no config")

        class _FakeShutil:
            which = staticmethod(lambda n: "/usr/bin/tmux")

        with nightmux.stubbed(load_cfg=_boom):
            assert nightmux.doctor() is False               # no config at all: nothing else to check
        with nightmux.stubbed(load_cfg=lambda: {"token": "t", "chat_id": 1, "allow_users": [1]}, reader_drift=lambda: [],
                    api=lambda c, m, **kw: {"ok": True}, wired=lambda: ["stop"],
                    run=lambda *a, **kw: "process" if "KillMode" in a else "com.nightmux" if a[0] == "launchctl" else "active",
                    shutil=_FakeShutil(), installed_agents=lambda c: ["claude"]):
            assert nightmux.doctor() is True                # every check stubbed healthy
        with nightmux.stubbed(load_cfg=lambda: {"token": "t", "chat_id": 1, "allow_users": [1]},
                    api=lambda c, m, **kw: {"ok": False, "description": "bad token"},
                    wired=lambda: [], run=lambda *a, **kw: "inactive", shutil=_FakeShutil()):
            assert nightmux.doctor() is False               # one ✗ (token rejected) fails the whole thing
