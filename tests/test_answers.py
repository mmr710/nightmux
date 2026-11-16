"""test_answers: cut from tests/selfcheck.py (pre-stub part)."""
import json
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402

def test_menu_buttons():
    with isolated(nightmux) as iso:
        menu = nightmux.menu_buttons(["Do you want to proceed?", "❯ 1. Yes",
                             "│   2. Yes, and don't ask again │", "  3. No (esc)"])
        assert json.loads(menu)["inline_keyboard"][:3] == [
            [{"text": "1. Yes", "callback_data": "!1"}],
            [{"text": "2. Yes, and don't ask again", "callback_data": "!2"}],
            [{"text": "3. No (esc)", "callback_data": "!3"}]], menu


def test_menu_session_suffix():
    with isolated(nightmux) as iso:
        # A session suffix on every button: a mirrored copy in the command center
        # has no topic binding to resolve a bare "!1" against.
        qmenu = nightmux.menu_buttons(["Do you want to proceed?", "❯ 1. Yes", "  2. No"], "api")
        picks_q = json.loads(qmenu)["inline_keyboard"]
        assert picks_q[0][0]["callback_data"] == "!1 api", picks_q
        assert picks_q[-1][0]["callback_data"] == "!esc api", picks_q


def test_always_allow():
    with isolated(nightmux) as iso:
        # ♾ always: a pinned yes/no menu offers it, the tap saves that exact request,
        # and autoyes then answers that request (and no other) with !autoyes off.
        dlg = ["Bash command", "  npm test", "Do you want to proceed?", "❯ 1. Yes", "  2. No"]
        texts_ = lambda m: [b["text"] for r in json.loads(m)["inline_keyboard"] for b in r]
        assert "♾ always" in texts_(nightmux.menu_buttons(dlg, bind=True))
        assert "♾ always" not in texts_(nightmux.menu_buttons(dlg))
        acfg, ast_, alk, said_ = {"topics": {"1": "s"}, "chat_id": -1}, {}, threading.Lock(), []
        scr_ = list(dlg)
        with nightmux.stubbed(has_session=lambda x: True, visible=lambda x: list(scr_), pane=lambda x: list(scr_),
                     pane_state=lambda l: "waiting", press=lambda *a, **k: None,
                     pick=lambda s_, d: "", resolve_ask=lambda *a: None, save_cfg=lambda c: None,
                     send=lambda c, t, x, **k: said_.append(x)):
            assert nightmux.handle(acfg, ast_, alk, "1", "!always") is None
            assert "npm test" in list(acfg["always"]["s"].values())[0], acfg
            nightmux.autoyes(acfg, ast_, "1", "s")
            assert said_ and said_[-1].startswith("♾ always s → 1"), said_
            scr_[1], ast_["s"]["autoyes_at"] = "  make deploy", 0
            n_ = len(said_)
            nightmux.autoyes(acfg, ast_, "1", "s")
            assert len(said_) == n_, said_            # a different request: left to you
            scr_[1] = "  rm -rf build"
            assert "risky" in nightmux.handle(acfg, ast_, alk, "1", "!always")
            assert "1. " in nightmux.rules_cmd(acfg, alk, "s", "") and "no ♾" in nightmux.rules_cmd(acfg, alk, "s", "1 off")


def test_quiet_window():
    with isolated(nightmux) as iso:
        alk = threading.Lock()
        # !quiet: silent inside the window (wrapping midnight or not), phone time
        qcfg = {"tz_offset": 0}
        with nightmux.stubbed(save_cfg=lambda c: None):
            assert "usage" in nightmux.quiet_cmd(qcfg, alk, "late")
            nightmux.quiet_cmd(qcfg, alk, "23:00-07:00")
        assert qcfg["quiet"] == ["23:00", "07:00"] and nightmux.quiet_now(qcfg, 3600) and not nightmux.quiet_now(qcfg, 43200)
        qcfg["quiet"] = ["09:00", "17:00"]
        assert nightmux.quiet_now(qcfg, 43200) and not nightmux.quiet_now(qcfg, 3600) and not nightmux.quiet_now({}, 3600)


def test_answer_key_needs_a_question():
    with isolated(nightmux) as iso:
        # An answer key sent to a pane that is not asking is typed in as text and
        # queued by the agent, which is how five taps became "33333" in a prompt box.
        kcfg, klk = {"topics": {"1": "s"}, "chat_id": -1}, threading.Lock()
        with nightmux.stubbed(has_session=lambda x: True, visible=lambda x: ["working…"],
                     pane_state=lambda l: "busy", press=lambda *a, **k: None,
                     resolve_ask=lambda *a: None):
            assert "nothing is asking" in nightmux.handle(kcfg, {}, klk, "1", "!3")
            assert "nothing is asking" in nightmux.handle(kcfg, {}, klk, "1", "!y")
            assert nightmux.handle(kcfg, {}, klk, "1", "!esc") is None    # not an answer key
            assert nightmux.handle(kcfg, {}, klk, "1", "!int") is None    # nor is C-c
        with nightmux.stubbed(has_session=lambda x: True, visible=lambda x: ["❯ 1. Yes"],
                     pane_state=lambda l: "waiting", press=lambda *a, **k: None,
                     pick=lambda s, w: None, resolve_ask=lambda *a: None):
            assert nightmux.handle(kcfg, {}, klk, "1", "!3") is None      # a real menu: answered
