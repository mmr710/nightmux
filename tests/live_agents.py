#!/usr/bin/env python3
"""Start each agent CLI installed here in tmux, from an empty home folder, and
read its first screen the way nightmux does.

The pane tests replay screens recorded once. This one checks the release of
today: with no login, an agent opens on a sign-in or setup screen, and
nightmux has to read it as it did before, a dialog as "waiting" with its
options listed. An agent that redraws it as something nightmux reads another
way has drifted where the recorded panes cannot show it. The drift guard
installs the newest releases and runs this every night; every screen is saved
to the output folder, one copy away from being a fixture in tests/panes.

    python3 tests/live_agents.py [outdir]    # exit 1 when a reading changed
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

HOME = tempfile.mkdtemp(prefix="agents-home-")
# Before nightmux is imported, since its state lives under the home folder.
# Nothing reads or writes the real one, and no agent finds a login or a key;
# without the CLAUDE* variables, a Claude Code run from Claude Code is not
# tied to the session that ran it.
os.environ.update(HOME=HOME, XDG_CONFIG_HOME=os.path.join(HOME, ".config"),
                  XDG_DATA_HOME=os.path.join(HOME, ".local", "share"),
                  XDG_STATE_HOME=os.path.join(HOME, ".local", "state"),
                  XDG_CACHE_HOME=os.path.join(HOME, ".cache"))
for k in [k for k in os.environ if k.endswith("_API_KEY") or k.startswith(("TMUX", "CLAUDE"))]:
    del os.environ[k]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402

SOCKET = "agents-check"   # a tmux server of its own: a running nightmux never sees it
# How each first screen reads today. A different reading is drift, either way.
EXPECT = {
    "agy": "waiting",       # sign-in method
    "claude": "idle",       # a first run's theme picker, read as a prompt; a session nightmux drives is past it
    "codex": "waiting",     # sign in with ChatGPT, a device code or a key
    "gemini": "waiting",    # trust this folder?
    "opencode": "idle",     # starts on a free model, at its prompt
    "qwen": "unknown",      # sign-in: a line under each option, not read yet (a prompt there gets the !raw hint)
}


def tmux(*args):
    return subprocess.run(("tmux", "-u", "-L", SOCKET) + args,
                          capture_output=True, text=True).stdout


def first_screen(key, launch, limit=60):
    """Started as spawn() starts it; the screen once it has held still for 3 s."""
    tmux("new-session", "-d", "-s", key, "-c", HOME)
    tmux("send-keys", "-t", key, "-l", "--", launch)
    tmux("send-keys", "-t", key, "Enter")
    start, last, still = time.time(), None, 0
    while time.time() < start + limit:
        time.sleep(1)
        lines = tmux("capture-pane", "-p", "-J", "-t", key).split("\n")
        still = still + 1 if lines == last else 0
        last = lines
        # Not before 8 s: a CLI still loading leaves the shell line standing.
        if still >= 3 and time.time() > start + 8 and nightmux.pane_state(lines) != "busy":
            break
    tmux("kill-session", "-t", key)
    return last


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "agent-screens"
    os.makedirs(out, exist_ok=True)
    rows, drift = [], []
    for key, (launch, _resume) in nightmux.AGENTS.items():
        binary = launch.split()[0]
        if not shutil.which(binary):
            continue
        lines = first_screen(key, launch)
        with open(os.path.join(out, key + ".txt"), "w") as f:
            f.write("\n".join(lines).rstrip("\n") + "\n")
        got = nightmux.pane_state(lines)
        opts = [label[:30].replace("|", "/") for _, label in nightmux.menu_items(lines)] if got == "waiting" else []
        want = EXPECT.get(key)
        if want and got != want:
            drift.append(key)
        rows.append("| %s | `%s` | %s | %s | %s |" % (
            key, nightmux.agent_version(binary), got, ", ".join(opts[:4]) or "–",
            "✓" if got == want else "✗ was " + want if want else "new"))
    tmux("kill-server")
    shutil.rmtree(HOME, ignore_errors=True)
    table = "\n".join(["| Agent | Version | First screen | Options read | |",
                       "|---|---|---|---|---|"] + rows)
    print(table)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write("### Agents' first screens, read by nightmux\n\n" + table + "\n")
    if drift:
        print("drift: " + ", ".join(drift) + ". The screens are in " + out)
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
