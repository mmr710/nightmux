# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
versions follow [semver](https://semver.org/). The public surface is the command
names and the shape of `~/.nightmux.json` — those are what a major bump protects.

## [Unreleased]

### Added

- A turn the usage limit cuts off now resumes itself. The prompt that started it
  was already consumed, so the queue was empty at reset time and the session sat
  idle until someone typed `continue` — which, for a limit that lands at 2am, was
  the whole night. When the pane was working as the hold went on, nightmux queues
  the continuation itself and the existing drain sends it when the window
  reopens. `"auto_continue": false` waits for a human; any other string replaces
  `continue`.
- `"modes": {"<topic>": "readonly"}` — a topic that reports, greps, shows usage
  and pane output, and never reaches the keyboard of the session it watches.
  Every bound topic was writable by anyone on the allowlist, which is the right
  default for a session you are driving and the wrong one for a topic bound to
  something you only want to watch from a phone.

### Fixed

- A session now resolves to the pane its agent is actually in, for reads and for
  keystrokes alike. `-t <session>` means that session's *active* pane, so a split
  window — or a session left looking at another window — had nightmux capturing
  one pane and typing into another: the menu never got its answer and the output
  never moved, with nothing to say why. The pane a status-line snapshot was last
  written from wins; without one, the active pane, as before.
- Menu picks no longer leave the pane sitting on the question. `!1`..`!9` sent
  the digit and assumed the dialog acted on it, which is true of Claude Code's
  permission prompt and false of its `/model` picker, agy's trust prompt and a
  shell's `(y/n)` — those move a highlight and wait for Enter, so the session
  stayed parked on a menu the topic had been told was answered. The digit is now
  followed by a look at the pane, and by Enter only if the same question is still
  on screen. `!y`/`!n` send the digit of the matching menu option, since a
  numbered list does not answer to the letter.
- A banner still sitting on screen is no longer read as a fresh limit. Only the
  lines a tick actually gained are scanned, so a resumed session cannot re-hold
  on the banner of the window it just came out of — and a second, identically
  worded limit is no longer swallowed by the dedup that existed for the first.
- A prompt refused within a minute of being typed goes back on the queue whole,
  instead of being replaced by a `continue` that would resume nothing. This is
  also what rescues a resume that lands early because the reset time on the
  banner was optimistic; `"limit_slack"` (default 60s) tunes how early that is.
- A window that reopens onto a busy or blocked pane now says so, with the queue
  depth, rather than going quiet and reading as a hold that never lifted.
- A restart no longer re-announces a usage threshold the window had already
  crossed. The "once per threshold, once per account" state lived only in the
  process, so every restart re-armed it: three restarts in one afternoon meant
  three 🔶 warnings for a window nobody had left. It is now kept beside the queue,
  and swept only when the window it describes is long gone.
- A spent **weekly** window is now held on. Only the 5-hour window was read from
  the status-line snapshot, and a fresh snapshot outranks the on-screen banner —
  so a week that had run out while the 5-hour figure read healthy was seen as
  room, and prompts were injected into a session that could only refuse them.
  Both windows are read, and the hold runs to the later reset of the two.
- Restarting a tmux session no longer eats the prompts held for it. The watchdog
  rebaselines a rebuilt session by dropping its state, which is right for the
  screen cache and wrong for the queue — the next `save_queue` then wrote the
  loss to disk. The hold and its prompts now survive the rebuild.

## [1.1.0] — 2026-08-11

### Changed

- The hook scripts are now `nightmux_stop.py`, `nightmux_notify.py` and
  `nightmux_state.py` (was `tm-stop.py`, `tm-notify.py`, `tm-state.py`). Hyphens
  are not legal in a module name, and that was the only thing standing between
  this and a `pip install`. Re-run `--setup` to repoint Claude Code at them.
- Renamed from `tgctl` to `nightmux`, briefly by way of `telemux` — which turned
  out to be another project's name on PyPI and six other repositories' on GitHub,
  including one bridging Telegram to tmux for the same three agents. Paths move
  to `~/.nightmux.json`, `~/.nightmux-state`, `~/.nightmux-files`,
  `~/.nightmux-hooked` and `~/.nightmux.offset`; the systemd unit and the `/tg*`
  command aliases follow. Both older names are adopted automatically on first
  run, so an existing install keeps its config and any held prompts.

### Fixed

- A rate-limit hold that expired with an empty queue was never cleared, so the
  session stayed flagged as limited across restarts and the topic heard nothing
  at the time it was promised a resume.

### Added

- Any terminal agent, not just Claude Code. `AGENTS` ships entries for `claude`,
  `agy`, `codex`, `aider` and `gemini`; `!<agent> <name> [dir]` starts one, and
  `cfg["agents"]` adds or overrides them as `[command, resume-flags]` without a
  code change. An unknown key is treated as its own command.
- `cfg["agent"]` sets what `!new` starts. `!resume` remembers which agent a topic
  was started with, so it no longer resumes a codex session with claude's flag.

## [1.0.0] — 2026-08-09

First public release. nightmux had been running as the author's daily driver for a
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

**Setup.** `nightmux.py --setup` does the token, the group, the allowlist, the two
hooks, the status-line sidecar and the systemd user service, and is safe to
re-run.

### Notes

- Python 3.8+, stdlib only, no dependencies and no relay server.
- Tests are assert-based selfchecks: `--selfcheck` on each of the four scripts,
  run in CI against 3.8 through 3.13.
- `~/.nightmux.json` is written `0600` on every save. The bot token is a shell on
  the machine — see [SECURITY.md](SECURITY.md).
