# Roadmap

nightmux keeps AI coding agents working while you are away: it runs them in tmux, resumes them when a usage limit resets, hands work from one agent to another, and lets you steer from Telegram, the dashboard or the Android app. This page says what comes next and where help is most welcome. The order is the plan; there are no dates.

Everything released so far is in the [changelog](CHANGELOG.md).

## Just shipped (1.5.0)

- `nightmux wrapped`: your Wrapped report and a dollar estimate at API list prices, from the logs your agents already keep. No bot or config needed.
- `nightmux handoff`: hands the work in a repo to another agent from the terminal, with a brief of what was done.
- A Claude Code plugin: `/nightmux:wrapped` and `/nightmux:handoff` from inside Claude Code.
- `nightmux up`: a first run with the dashboard alone, no Telegram bot.
- Safer dashboard pairing, an office that stays up when a peer is down, and `--doctor` checks for a dead office link or a service still running old code.

## Next

1. **Code that is easy to read and change.** Split `nightmux.py` into modules and generate the single file from them, so installs do not change; move the self-check into `tests/`; add ruff, coverage and a macOS CI run.
2. **Agent compatibility table.** Every night the drift guard starts the newest Claude Code, Codex, Gemini CLI, Qwen Code, OpenCode and Aider and records how nightmux reads each first screen (`tests/live_agents.py`); its first run found Gemini CLI's folder trust dialog unread. Next: that table in the README, kept current by the job, and the screens after the first one.
3. **Rails for unattended nights.** A dollar cap next to the token `!budget`, and one command that stops every session at once.

## Later

- The Stop and Notification hooks from the plugin instead of `--setup` editing `~/.claude/settings.json`, once the plugin and the daemon can agree on a version.
- A voice note turned into a written plan you approve before an agent starts (voice notes are already transcribed with `transcribe_cmd`).
- Reviewing a night's changes on the phone, one change at a time.
- Installs that follow tagged releases instead of `main`.

## How to help

- Try nightmux with the agent you use, and [open an issue](https://github.com/mmr710/nightmux/issues/new/choose) when something does not work.
- Issues labelled [good first issue](https://github.com/mmr710/nightmux/labels/good%20first%20issue) are a way in. [CONTRIBUTING.md](CONTRIBUTING.md) explains how to run it while you work and how to send a pull request.
- Ideas and questions go to [Discussions](https://github.com/mmr710/nightmux/discussions).
