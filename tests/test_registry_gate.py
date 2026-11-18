"""test_registry_gate: a session=True command runs after handle()'s session gate."""
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_session_commands_pass_the_gate():
    with isolated(nightmux):
        cfg, state, screen, sent = legacy_stubs(nightmux)
        nightmux.autobind = lambda *a: None
        seen = []
        nightmux.command("!gatetest", section="talk", help="x", session=True)(
            lambda ctx, arg: seen.append((ctx.sess, ctx.bound, arg)) or "ran")
        nightmux.KEYS["!gatetest"] = "x"     # so the ~fp peel and the mirrored arg apply
        lock = threading.Lock()
        try:
            nightmux.has_session = lambda s: False   # "hi" is not a session: not mirrored
            assert "topic not bound" in nightmux.handle(cfg, state, lock, "5", "!gatetest hi")
            cfg["topics"]["5"] = "s1"
            nightmux.has_session = lambda s: False
            assert "is gone" in nightmux.handle(cfg, state, lock, "5", "!gatetest hi")
            assert not seen, "the fn ran before the gate said yes"
            nightmux.has_session = lambda s: s in ("s1", "s2")
            assert nightmux.handle(cfg, state, lock, "5", "!gatetest hi ~abcdef") == "ran"
            assert seen[-1] == ("s1", "abcdef", "hi"), seen
            assert nightmux.handle(cfg, state, lock, "5", "!gatetest s2") == "ran"
            assert seen[-1] == ("s2", None, "s2"), seen
        finally:
            del nightmux.COMMANDS["!gatetest"], nightmux.KEYS["!gatetest"]


if __name__ == "__main__":
    test_session_commands_pass_the_gate()
    print("ok")
