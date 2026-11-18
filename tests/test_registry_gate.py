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


def test_one_decorator_feeds_help_docs_and_gate():
    cfg = {"agents": {}}
    names = ("!regw", "!regr", "!regc")
    try:
        nightmux.command("!regw", section="talk", help="w line", writes=True)(lambda ctx, arg: "")
        nightmux.command("!regr", section="talk", help="r line")(lambda ctx, arg: "")
        nightmux.command("!regc", section="talk", help="c line", writes=lambda a: a == "now")(lambda ctx, arg: "")
        for n in names:
            assert f"- `{n}` c line".replace("c line", nightmux.COMMANDS[n].help) in nightmux.commands_md()
            assert f"• {n} " in nightmux.help_text(cfg, "talk")[0]
        w = nightmux.writes
        assert w(cfg, "!regw") and not w(cfg, "!regr")
        assert w(cfg, "!regc", "now") and not w(cfg, "!regc", "")
    finally:
        for n in names:
            nightmux.COMMANDS.pop(n, None)


if __name__ == "__main__":
    test_session_commands_pass_the_gate()
    test_one_decorator_feeds_help_docs_and_gate()
    print("ok")
