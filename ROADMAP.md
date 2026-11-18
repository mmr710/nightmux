# 🌙 nightmux roadmap

**Where this is going:** your coding agents should not stop when you close the laptop. nightmux already drives Claude Code, Codex, Gemini / agy, OpenCode and other terminal agents in `tmux`, loops until your test command passes, hands the work to another vendor's agent when one hits its usage limit, and lets you steer all of it from a phone (Telegram, Discord, Slack, the web dashboard or the Android app). The goal from here is that every agent is as well supported as Claude Code is today, that you always know how much quota each of your accounts has left, and that the code is easy enough to change that adding an agent or a command is an afternoon's pull request. It stays one stdlib-only Python file that runs on your own machine.

The order below is the plan. There are no dates and no promises; a nightly CI run against the newest agent releases decides what is urgent.

**Jump to:** [Shipped](#-shipped) · [Now](#-now) · [Next](#-next) · [Later](#-later) · [Not planned](#not-planned) · [How to help](#-how-to-help)

## ✅ Shipped

Seven releases since August 2026. The highlights; everything else is in the [changelog](CHANGELOG.md).

| Version | Date | What you got |
|---|---|---|
| **1.6.0** | 2026-11-11 | `nightmux run "<task>" --until "<check>"`: one task from a terminal with no bot, daemon or config, with failover to the next agent · `!kanban` and `/board` · `!review` and `/review/<topic>` per-file diffs with PR checks · `!sandbox` (agent in a locked-down Docker container) · `nightmux wrapped --json` · installs pinned to release tags |
| **1.5.0** | 2026-10-22 | `nightmux wrapped` share cards with API-list dollar estimates · `nightmux handoff` · `nightmux up` (dashboard-only first run) · Claude Code plugin (`/nightmux:wrapped`, `/nightmux:handoff`) · `!budget $20` spend caps · `!stopall` emergency brake · nightly drift guard that starts six agent CLIs in CI |
| **1.4.0** | 2026-10-22 | Android app with alerts and several servers · Discord and Slack (experimental) · `!team` roles and an audit log · `nightmux --mcp` server · `!relay` planner / builder / reviewer · `!events` webhooks · `/term/<topic>` full terminal page · `!upgrade` · one adapter registry for every agent |
| **1.3.0** | 2026-10-08 | `!race` agents in parallel worktrees · morning `!briefing` · usage-limit forecast · per-project memory · dashboard chat · `--demo` · `!qa`, `!deps`, `!saved` · built-in Cursor, Amp, Goose and Qwen Code |
| **1.2.0** | 2026-09-02 | Several agents in one topic (`!claude`, `!codex`, `!agy`, `!opencode` switch in place) · token-based `!spendcap` |
| **1.0.0** | 2026-08-09 | First public release: the Telegram bridge to agents in `tmux`, with stable command names and config keys |

## 🔨 Now

In progress on `main`. Nothing here is released until it appears in the changelog.

| What you get | Status |
|---|---|
| **Quota per account, for agy and OpenCode too.** `!quota` shows what each account has left, so you know which agent to send the next task to. | in progress |
| **Several agy / OpenCode accounts side by side.** Sign in to more than one account through profiles and pick which one a session uses. | in progress |
| **A test suite you can run one file at a time.** The single long `--selfcheck` is being cut into `tests/test_<area>.py` files, so a contributor runs only the tests for the code they touched and a failure names its area. | in progress, part merged |
| **Adding a chat command is one small function.** Commands are moving out of one long `handle()` into a registry, so a command, its help line and its entry in [`docs/COMMANDS.md`](docs/COMMANDS.md) cannot drift apart. [`tests/acceptance/test_registry.py`](tests/acceptance/test_registry.py) counts what is left to move. | in progress, part merged |

## ⏭ Next

1. **Every agent's dialogs and limit banners become buttons, not only Claude Code's.** The drift guard checks each agent's first screen every night. The screens after sign-in (permission menus and usage-limit banners for Codex, Gemini CLI, OpenCode, Qwen Code and Aider) come from real terminal captures in [`tests/panes/`](tests/panes). The gaps are the `–` and "not yet" cells in the [README agent table](README.md#agents).
2. **Code that is easy to read and change.** Split `nightmux.py` into source modules and build the single-file `nightmux.py` from them, so zero-dependency one-file installs stay identical. Add ruff, coverage and a macOS CI run.
3. **`nightmux run` that is safe to start anywhere.** Refuse to start `run` in a folder where a daemon session is already active, recognise the shell prompt behind custom agent wrappers, and cover older `tmux` versions end to end.

## 🔭 Later

Wanted, not started. Order is not fixed; reactions on issues move things up.

- **Claude Code hooks from the plugin.** Installing the Claude Code plugin also delivers the `Stop` and `Notification` hooks, once plugin and daemon versions are released together.
- **Reasoning effort per agent.** `!effort <low|medium|high>` passes a level to the current agent today; the plan is controls that know which levels each agent and model accept.
- **Talk, then approve a plan.** A voice note becomes a written plan you approve before the agent edits code. Local transcription through `transcribe_cmd` already works.

## Not planned

These follow from the design rules in [CONTRIBUTING.md](CONTRIBUTING.md) and [ARCHITECTURE.md](ARCHITECTURE.md), and they are why nightmux installs in one command:

- Third-party Python dependencies. Standard library only, Python 3.8+.
- A hosted relay or cloud account between your phone and your machine.
- Replacing the agents. nightmux types into their `tmux` panes and reads the screen back; it does not call model APIs itself.

## 🙌 How to help

Small, self-contained ways in, roughly easiest first:

| If you have | Do this |
|---|---|
| **5 minutes** and an agent whose dialog or limit banner nightmux missed | Run `tmux capture-pane -p` on that pane and paste it into a [new issue](https://github.com/mmr710/nightmux/issues/new/choose). Each capture becomes a file in [`tests/panes/`](tests/panes) and a permanent regression test in [`tests/test_panes.py`](tests/test_panes.py). Check the capture for anything private first. |
| **An agent CLI that is not in the table** | Open an issue with its start command and a capture of its idle screen and one dialog. |
| **An evening** | Pick an issue labelled [`good first issue`](https://github.com/mmr710/nightmux/labels/good%20first%20issue), or move one command into the registry (see [Now](#-now)). |
| **A bigger idea** | Open an issue before writing code. [CONTRIBUTING.md](CONTRIBUTING.md) explains why, and how to run the tests and the `--demo` office with no bot or keys. |

**Vote:** add a 👍 reaction to the [issue](https://github.com/mmr710/nightmux/issues?q=is%3Aissue+is%3Aopen+sort%3Areactions-%2B1-desc) for what you want next; that link sorts open issues by reactions. If it is not there, file it with the "Idea" template: it asks what you want to do from your phone or overnight that you cannot do today. Open questions and early ideas go to [Discussions](https://github.com/mmr710/nightmux/discussions).

**Follow:** watch [releases](https://github.com/mmr710/nightmux/releases) on GitHub, or join the [Telegram community](https://t.me/+SGmmExdMHTQ3OWVk). Found a security problem? Follow [SECURITY.md](SECURITY.md).
