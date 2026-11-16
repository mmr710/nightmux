"""test_dialogs: cut from tests/selfcheck.py (pre-stub part)."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402


def test_agy_permission_menu():
    with isolated(nightmux) as iso:
        # agy: numbered permission menu, arrow-only trust prompt, spinner
        agy_perm = ["Requesting permission for:", "Do you want to proceed?", "> 1. Yes",
                    "  2. Yes, and always allow in this conversation",
                    "  4. No", "  ↑/↓ Navigate · tab Amend"]
        assert nightmux.pane_state(agy_perm) == "waiting"
        picks = json.loads(nightmux.menu_buttons(agy_perm))["inline_keyboard"][:3]
        assert [r[0]["callback_data"] for r in picks] == ["!1", "!2", "!4"], picks


def test_opencode_modal_and_form():
    with isolated(nightmux) as iso:
        # opencode: a modal drawn inside the border, over prose that numbers itself.
        # It names no question WAITING knows and answers to arrows, never the digit.
        oc = ["     5. Ship & iterate (wk 4+): soft-launch, measure D1",
              "  ┃  Unity can't run on this ARM64 server. How should we proceed?",
              "  ┃  1. Godot 4 (Recommended)",
              "  ┃     Native performance, ARM64-buildable here",
              "  ┃  2. Web (TypeScript)",
              "  ┃  3. Scaffold-only",
              "  ┃  ↑↓ select  enter submit  esc dismiss"]
        assert nightmux.pane_state(oc) == "waiting"
        form = ["  ┃  Questions", "  ┃  Symptom  APK type  Phone side  Setup  Submit",
                "  ┃  Symptom: Icon not in AA launcher", "  ┃  APK type: Not sure",
                "  ┃  ⇆ tab  enter submit  esc dismiss", "", "  ╹▀▀▀▀▀▀▀▀▀▀▀▀"]
        assert nightmux.pane_state(form) == "waiting"
        assert [b["text"] for b in json.loads(nightmux.menu_buttons(form))["inline_keyboard"][-1]] == \
            ["esc", "⇆", "↑", "↓", "⏎"]
        assert [r[0]["callback_data"]
                for r in json.loads(nightmux.menu_buttons(oc))["inline_keyboard"][:-1]] == \
            ["!1", "!2", "!3"]                                    # prose 5. dropped
        assert nightmux.menu_opts(oc) == (["1", "2", "3"], None)   # plain: no marker to read


def test_opencode_colour_marker_and_pick():
    with isolated(nightmux) as iso:
        oc = ["     5. Ship & iterate (wk 4+): soft-launch, measure D1",
              "  ┃  Unity can't run on this ARM64 server. How should we proceed?",
              "  ┃  1. Godot 4 (Recommended)",
              "  ┃     Native performance, ARM64-buildable here",
              "  ┃  2. Web (TypeScript)",
              "  ┃  3. Scaffold-only",
              "  ┃  ↑↓ select  enter submit  esc dismiss"]
        # The same pane as tmux hands it over with -e. opencode paints the selected
        # option's number in its accent colour and every other one grey; that is the
        # whole of the marker, and it is the only thing that says where the arrows are.
        ON, OFF, C = "\x1b[38;2;92;156;245m", "\x1b[38;2;128;128;128m", "\x1b[0m"

        def paint(sel):
            out = []
            for l in oc:
                m = nightmux.MENU.match(l) if nightmux.BOXED.match(l) else None
                out.append(l.replace(m.group(1) + ".",
                                     f"{ON if m.group(1) == sel else OFF}"
                                     f"{m.group(1)}.{C}", 1) if m else l)
            return out

        keyed, sel = [], ["1"]
        assert nightmux.menu_opts(paint("1")) == (["1", "2", "3"], 0)
        assert nightmux.menu_opts(paint("3")) == (["1", "2", "3"], 2)

        def fake_tmux(*a):
            """A pane whose highlight follows the arrows, so the re-read is real."""
            if a[0] != "send-keys":
                return "\n".join(paint(sel[0]))
            keyed.append(a[3:])
            if a[3] in ("Up", "Down"):
                sel[0] = ["1", "2", "3"][["1", "2", "3"].index(sel[0])
                                         + sum(1 if k == "Down" else -1 for k in a[3:])]
            return ""

        with nightmux.stubbed(tmux=fake_tmux):
            assert nightmux.pick("s", "3") == ""            # two rows down from the marked one
            assert keyed == [("Down", "Down"), ("Enter",)], keyed
            keyed[:] = []
            assert nightmux.pick("s", "9").startswith("option 9 is not")   # no such option
            assert keyed == [], keyed                             # nothing pressed
            sel[0] = ""                               # every row alike: unreadable
            assert nightmux.pick("s", "3").startswith("can't tell") and keyed == []
        assert nightmux.pane_state([l for l in oc if "┃" not in l]) == "unknown"  # prose alone


def test_opencode_button_bar():
    with isolated(nightmux) as iso:
        oc = ["     5. Ship & iterate (wk 4+): soft-launch, measure D1",
              "  ┃  Unity can't run on this ARM64 server. How should we proceed?",
              "  ┃  1. Godot 4 (Recommended)",
              "  ┃     Native performance, ARM64-buildable here",
              "  ┃  2. Web (TypeScript)",
              "  ┃  3. Scaffold-only",
              "  ┃  ↑↓ select  enter submit  esc dismiss"]
        # opencode 2.x: the permission dialog is one row of buttons, the highlight a
        # background colour (captured from opencode v2.0.24, cut off at the pane edge).
        E = "\x1b[%sm".__mod__
        ocbar = lambda on: [
            "  ┃  △ Permission required", "  ┃    ← Access external directory ~/x", "  ┃",
            "  " + E("38;5;216") + E("48;5;233") + "┃" + E("38;5;15") + E("48;5;234") + "  "
            + "".join((E("48;5;216") if i == on else E("48;5;234")) + " " + E("38;5;232") + lab
                      + E("38;5;15") + " " + E("48;5;234") + " " for i, lab in
                      enumerate(["Allow once", "Always allow", "Reject"]))
            + " " + E("38;5;255") + "ctrl+f " + E("38;5;8") + "fullscreen  " + E("38;5;255")
            + "⇆ " + E("38;5;8") + "select" + E("38;5;15") + "  enter con"]
        assert nightmux.bar_opts(ocbar(0)) == (["Allow once", "Always allow", "Reject"], 0)
        assert nightmux.bar_opts(ocbar(2))[1] == 2
        flat = [nightmux.plain(l) for l in ocbar(0)]
        assert nightmux.bar_opts(flat) == (["Allow once", "Always allow", "Reject"], None)
        assert nightmux.pane_state(flat) == "waiting"
        assert nightmux.menu_digit(flat, nightmux.YES_NO["!y"]) == "1" and nightmux.menu_digit(flat, nightmux.YES_NO["!n"]) == "3"
        assert [r[0]["callback_data"] for r in json.loads(nightmux.menu_buttons(flat, "o"))["inline_keyboard"]] \
            == ["!1 o", "!2 o", "!3 o", "!esc o"]
        bsel, bkeyed = [0], []

        def bar_tmux(*a):
            if a[0] != "send-keys":
                return "\n".join(ocbar(bsel[0]))
            bkeyed.append(a[3:])
            bsel[0] += sum({"Right": 1, "Left": -1}.get(k, 0) for k in a[3:])
            return ""
        with nightmux.stubbed(tmux=bar_tmux):
            assert nightmux.pick("o", "3") == "" and bkeyed == [("Right", "Right"), ("Enter",)], bkeyed
            assert bsel[0] == 2


def test_dialog_under_numbered_reply():
    with isolated(nightmux) as iso:
        # A dialog under a reply that ends in a numbered list: its options are the
        # last run numbered from 1, not every numbered line on screen.
        listed = ["  1. Merge the pull request.", "  2. Run the release command.", "",
                  " Bash command", "   gh pr checks 160", " Do you want to proceed?",
                  " ❯ 1. Yes", "   2. Yes, and don't ask again for gh commands", "   3. No"]
        assert nightmux.pane_state(listed) == "waiting" and nightmux.menu_digit(listed, nightmux.YES_NO["!y"]) == "1"
        assert [d for d, _ in nightmux.menu_items(listed)] == ["1", "2", "3"]


def test_gemini_trust_dialog():
    with isolated(nightmux) as iso:
        # Gemini CLI marks the chosen row of a boxed dialog with ●, and its folder
        # trust dialog has no other sign: it read as unknown, with no buttons.
        gem = [" ╭────────────────────────────────────────╮",
               " │ Do you trust the files in this folder? │", " │                                        │",
               " │ ● 1. Trust folder (app)                │", " │   2. Trust parent folder (code)        │",
               " │   3. Don't trust                       │", " ╰────────────────────────────────────────╯"]
        assert nightmux.pane_state(gem) == "waiting" and [d for d, _ in nightmux.menu_items(gem)] == ["1", "2", "3"]
        assert nightmux.menu_digit(gem, nightmux.YES_NO["!n"]) == "3" and not nightmux.menu_digit(gem, nightmux.YES_NO["!y"])  # auto-yes never trusts


def test_aider_asks_on_input_line():
    with isolated(nightmux) as iso:
        # Aider asks on its input line and read as unknown. It takes a line, so !y
        # is y and an Enter; answered, the line stays on screen and asks nothing.
        aid = ["No LLM model was specified and no API keys were provided.",
               "Login to OpenRouter or create a free account? (Y)es/(N)o [Yes]:      ", "", ""]
        assert nightmux.pane_state(aid) == "waiting"
        assert nightmux.pane_state(["Add a.py to the chat? (Y)es/(N)o/(D)on't ask again [Yes]: y", "Added a.py to the chat.", "> "]) != "waiting"
        assert nightmux.pane_state(["Add a.py to the chat? (Y)es/(N)o [Yes]: ", "Added a.py to the chat.", "> "]) != "waiting"
        akeys = []
        with nightmux.stubbed(visible=lambda s: aid, tmux=lambda *a: akeys.append(a[-1]) or ""):
            nightmux.press("a", "y", confirm=True)
        assert akeys == ["y", "Enter"], akeys


def test_agy_trust_prompt():
    with isolated(nightmux) as iso:
        agy_trust = ["Do you trust the contents of this project?", "> Yes, I trust this folder",
                     "  No, exit", "  ↑/↓ Navigate · enter Confirm"]
        assert nightmux.pane_state(agy_trust) == "waiting"
        assert [r[0]["callback_data"] for r in json.loads(nightmux.menu_buttons(agy_trust))
                ["inline_keyboard"][:2]] == ["!1", "!2"]   # no numbers: by position
        assert nightmux.menu_opts(agy_trust) == (["1", "2"], 0)


def test_claude_trust_prompt():
    with isolated(nightmux) as iso:
        # Claude Code's: only the pointed row is marked, and it is "No, exit"
        cc_trust = [" Claude Code'll be able to read, edit, and execute files here.", "",
                    " ❯ No, exit", "   Yes, I trust this folder", "",
                    " Enter to confirm · Esc to cancel"]
        assert nightmux.pane_state(cc_trust) == "waiting"
        assert nightmux.menu_items(cc_trust) == [("1", "No, exit"), ("2", "Yes, I trust this folder")]
        assert nightmux.menu_opts(cc_trust) == (["1", "2"], 0)
        assert nightmux.menu_digit(cc_trust, nightmux.YES_NO["!y"]) == "2"


def test_pane_state_busy_idle():
    with isolated(nightmux) as iso:
        assert nightmux.pane_state(["● Bash(x)", "⢿  Running...", "esc to cancel"]) == "busy"
        # a backgrounded shell is not the session being busy: the prompt is free
        assert nightmux.pane_state(["● Bash(npm test) &", "  ⎿ \xa0Running… (7m 53s · timeout 10m)",
                           "╭───╮", "│ > ", "╰───╯"]) == "idle"
        box = ["╭────────╮", "│ > ", "╰────────╯", "  ? for shortcuts"]
        assert nightmux.pane_state(["● done"] + box) == "idle"
        assert nightmux.pane_state(["✻ Brewing… (12s · esc to interrupt)"]) == "busy"
        assert nightmux.pane_state(["  ⬝⬝⬝ retrying in 58m 6s attempt #13    esc interrupt"]) == "busy"
        assert nightmux.pane_state(["Do you want to proceed?", "❯ 1. Yes", "  2. No"]) == "waiting"
        assert nightmux.pane_state(["● Twitter moved.", "", "  Do you want me to restart egx_scrape?", "",
                           "✻ Crunched for 13s", "─" * 9, "❯ ", "─" * 9]) == "idle"
