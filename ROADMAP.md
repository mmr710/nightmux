# Roadmap

nightmux keeps AI coding agents working while you are away: it drives them in `tmux`, loops until your test command passes, fails over across vendors when one hits a usage limit, and lets you steer from a single terminal (`nightmux run`) or from Telegram, Discord, Slack, the web dashboard and the Android app. This page says what shipped recently, what comes next, and where help is most welcome. The order is the plan; there are no dates.

Everything released so far is in the [changelog](CHANGELOG.md).

## Just shipped (1.6.0)

- `nightmux run "<task>" --until "<check>"`: one task from a terminal with no bot, daemon or config. Runs your check after every turn, feeds failures back, and writes `.nightmux/HANDOFF.md` to hand the work to the next agent on a Claude Code usage limit, an exit, or a turn over an hour.
- `nightmux wrapped [days] --json [--projects]`: machine-readable token, prompt and API-list dollar totals per agent for scripts, badges and dashboards (plus the visual share cards from 1.5.0).
- `!kanban` and `/board`: every topic across every server as a live card in state columns (*needs you, running, queued, waiting for a limit, idle, offline*).
- `!review` and `/review/<topic>`: per-file diffs against `main` alongside the PR's check status.
- `!sandbox on|off` (`--nm-sandbox`): runs an agent inside a rootless Docker container (`docker/agent.Dockerfile`) that sees only its project folder and login files, with all capabilities dropped.
- Release-tag installs: `install.sh` now installs and upgrades to the newest `vX.Y.Z` release tag instead of `main` (`NIGHTMUX_REF` overrides).
- Extracted test suite (`tests/selfcheck.py`, `tests/acceptance/`) and honest tool comparison ([`docs/COMPARE.md`](docs/COMPARE.md)).

## Previously shipped (1.5.0)

- `nightmux wrapped` share cards and API-list dollar estimates, `nightmux handoff`, `nightmux up` (dashboard-only first run), and the Claude Code plugin (`/nightmux:wrapped`, `/nightmux:handoff`).
- Nightly [drift guard](https://github.com/mmr710/nightmux/actions/workflows/drift-guard.yml) in CI starting the newest Claude Code, Codex, Gemini CLI, Qwen Code, OpenCode and Aider in `tmux`.
- `!budget $20` dollar spend caps, `!stopall` emergency brake, and `--doctor` checks for stale service code and office reachability.

## Next

1. **Agent screens past the first one (usage limits and dialogs across vendors).** Every night the drift guard verifies how nightmux reads each agent's first screen. Screens after sign-in — permission menus and usage-limit banners for Codex, Gemini CLI, OpenCode, Qwen Code and Aider — come from real terminal captures (`tests/panes/`). A pasted pane capture or screenshot in an issue is enough to add a fixture and test.
2. **Code that is easy to read and change.** Split `nightmux.py` into source modules and build the single-file `nightmux.py` from them so zero-dependency, one-file installs stay identical; add ruff, coverage and a macOS CI run.
3. **Hardening `nightmux run` in the wild.** Guard against starting `run` in a folder where a daemon session is already active, tighten shell-prompt detection for custom agent wrappers, and expand end-to-end coverage across older `tmux` versions.

## Later

- Delivering Claude Code `Stop` and `Notification` hooks directly from the Claude Code plugin once plugin and daemon versioning are unified.
- Per-agent reasoning effort controls (`!effort`).
- Voice note → written plan approval flow before an agent edits code (local transcription via `transcribe_cmd` already works).

## How to help

- **Add a terminal screen fixture (`tests/panes/`):** If an agent CLI's permission dialog or usage-limit message was not recognised, capture the pane (`tmux capture-pane -p`) and [open an issue](https://github.com/mmr710/nightmux/issues/new/choose) — each screen becomes a permanent regression test in `tests/test_panes.py`.
- Pick up an issue labelled [`good first issue`](https://github.com/mmr710/nightmux/labels/good%20first%20issue). [CONTRIBUTING.md](CONTRIBUTING.md) explains how to run the isolated test suites and open a pull request.
- Share ideas, workflows and questions in [Discussions](https://github.com/mmr710/nightmux/discussions).
