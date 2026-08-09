# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
versions follow [semver](https://semver.org/). The public surface is the command
names and the shape of `~/.tgctl.json` — those are what a major bump protects.

## [Unreleased]

## [1.0.0] — 2026-08-09

First public release. tgctl had been running as the author's daily driver for a
while before this; 1.0.0 marks the point where the command names and the config
keys are considered stable, not the point where the code started working.

### Added

**Sessions.** One forum topic per tmux session. `!new` / `!agy` start one and
bind it, `!resume` relaunches a topic's directory with `--continue`, `!bind` and
`!unbind` attach to sessions started elsewhere, `!kill` stops one behind a
confirmation. `autostart` recreates configured sessions after a reboot;
`projects_root` lets a topic named after a directory start that project on its
first message.

**Output.** A `Stop` hook delivers the final answer as exact text; the daemon
tails the session's JSONL transcript for the tool trace, and falls back to
scraping `tmux capture-pane` when the hooks are not installed. Live progress is
one edited message rather than a stream of new ones.

**Approvals.** A `Notification` hook pushes permission prompts the moment Claude
Code asks, with the on-screen options as inline buttons. `!1`–`!9`, `!y`, `!n`,
`!esc`, `!int` and the rest send keys directly; `!raw` types text past an open
menu. An unanswered prompt is re-raised on a timer instead of silently blocking.

**Spend and limits.** A status-line sidecar supplies the real context percentage
and the 5-hour / 7-day windows. `!ctx` breaks down what is filling the window,
`!cost` weighs token spend by type for a session or every project, `!usage`
reports the limit windows for every topic. `!autocompact` runs `/compact` at a
threshold; `!idlectx` flags parked sessions still holding a large context.

**Rate limits.** A prompt sent while a session is rate-limited is held rather
than lost, and replayed after the stated reset. Held prompts persist to disk, so
they survive a daemon restart or a reboot. `!queue` inspects, clears or forces
them.

**Everything else.** `!status`, `!sessions`, `!pane`, `!ctl`, `!git`, `!diff`,
`!get`, `!grep` over every transcript, `!verbose`, `!tz` (zone names, so DST
follows), `!reload`, `!log`, `!version`, `!help`. Photos and files are saved with
their path typed into the session. Common commands are registered as `/`
commands so Telegram autocompletes them, alongside Claude Code's own.

**Setup.** `tgctl.py --setup` does the token, the group, the allowlist, the two
hooks, the status-line sidecar and the systemd user service, and is safe to
re-run.

### Notes

- Python 3.8+, stdlib only, no dependencies and no relay server.
- Tests are assert-based selfchecks: `--selfcheck` on each of the four scripts,
  run in CI against 3.8 through 3.13.
- `~/.tgctl.json` is written `0600` on every save. The bot token is a shell on
  the machine — see [SECURITY.md](SECURITY.md).
