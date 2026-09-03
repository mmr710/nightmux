# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
versions follow [semver](https://semver.org/). The public surface is the command
names and the shape of `~/.nightmux.json` — those are what a major bump protects.

## [Unreleased]

### Added

- `@claude <text>` / `@agy <text>` — send one prompt to one agent on the topic's
  bench without switching the topic to it. Switching is the wrong verb when a
  project keeps two agents side by side and you want to put one question to one
  of them.
- `!consult <question>` — ask every agent on the bench separately, then have each
  read the other's answer and return one self-contained prompt. Round one is
  blind on purpose: two independent reads are worth more than an agreement
  reached after they have seen each other.

### Added

- `!autocompact 150k` — compact on what a turn actually carries, not on a share
  of the context window. Measured on one box: windows of 530k–700k tokens, so
  `autocompact: 70` would not have fired until a turn carried ~490k tokens,
  while the sessions sat at 264k–319k and re-read every one of those tokens on
  every turn. The percentage form is unchanged, so existing configs keep their
  meaning.

### Fixed

- Keeping a snapshot for as long as its pane lives kept *every* snapshot for
  that pane. Claude Code names them after its own session id, so a pane collects
  another file each time a conversation starts, and `snapshot()` rescanned the
  pile on every look. Only the newest per live pane is kept now; the rest go
  back to ageing out.


## [1.2.0] — 2026-09-02

### Added

- **One topic, several agents.** A bare `!<agent>` in a bound topic switches that
  topic between claude, agy, codex, opencode and anything in `agents` — same
  directory, a tmux session per agent, the one you left still running. `!agents`
  lists the bench. Stored as `bench` in the config; `topics`, `dirs` and
  `started` are unchanged, so an existing config needs no edit.

- `!spendcap` can cap what the turns cost, not how many there were: a suffixed
  value (`!spendcap 500k`, `!spendcap 2M`) counts base-equivalent tokens over 5
  minutes and interrupts past it. A bare number is still turns, so an existing
  config means exactly what it did. Tokens come out of the transcript, so that
  form only bites on Claude Code sessions.
- `!agents` marks a session with no context figure, and the context warning says
  so once per session when `autocompact` is on: `ctx_pct` comes from Claude
  Code's status line, so on agy, codex or opencode the whole context brain was
  off and silent about it.
- macOS service install. `--setup` now writes a launchd agent
  (`~/Library/LaunchAgents/com.nightmux.plist`) on Darwin instead of stopping at
  "the service install is systemd". Everything else was already portable; this
  was the last Linux-only piece.
- An animated demo (`docs/demo.svg`) in the README showing the overnight
  ⏸ / ▶️ resume and a tap-button approval — the recording the README had a TODO
  for, minus the phone.

- A turn the usage limit cuts off now resumes itself. The prompt that started it
  was already consumed, so the queue was empty at reset time and the session sat
  idle until someone typed `continue` — which, for a limit that lands at 2am, was
  the whole night. When the pane was working as the hold went on, nightmux queues
  the continuation itself and the existing drain sends it when the window
  reopens. `"auto_continue": false` waits for a human; any other string replaces
  `continue`.
- `!at 03:00 <prompt>`, `!at +90m <prompt>`, `!every 4h <prompt>`, `!sched
  [clear]` — work that starts while you are asleep. A scheduled prompt is put on
  the queue rather than into the pane, so it inherits everything the queue
  already knows: it waits behind a usage-limit hold, it waits for a busy pane,
  and it survives a restart. A recurring job rearms from when it fired, not from
  when it was due, so a daemon that was off overnight does not wake up and run
  six hours of backlog at once.
- `"modes": {"<topic>": "readonly"}` — a topic that reports, greps, shows usage
  and pane output, and never reaches the keyboard of the session it watches.
  Every bound topic was writable by anyone on the allowlist, which is the right
  default for a session you are driving and the wrong one for a topic bound to
  something you only want to watch from a phone.
- `!shift` — a sequential overnight plan: one prompt per line in the same
  message, fired one at a time as each turn finishes. It rides the existing
  queue/drain machinery rather than a second wait-for-idle loop, so a
  usage-limit lockout pauses a shift exactly like it pauses a held prompt, and
  the plan survives a restart the same way the queue does. Progress posts as
  "shift 2/4 → <prompt>", with "shift done" at the end.
- A git snapshot before every prompt nightmux sends unattended — a queued
  prompt replayed after a lockout, an `!at`/`!every` firing, a `!shift` step —
  via `git stash create`, which builds the snapshot without ever touching the
  worktree. The branch is `nightmux/pre-<UTC timestamp>`, and only the last 5
  per repo are kept. A prompt typed live gets none: nobody needs a snapshot for
  work they watched happen. `!undo` lists a topic's snapshots newest-first with
  the exact `git restore`/`git diff` commands — it never runs them, on purpose.
- `!digest` — turns completed, a gist of the last answer, commits since the
  digest period started, token spend and current state, squeezed onto a phone
  screen. `!digest 08:00` schedules it daily (the same epoch math as `!every`,
  reporting instead of typing "!digest" into the agent); `!digest off` cancels.
  No automatic digest by default.
- `nightmux --doctor` — tmux found, config complete, token accepted by
  Telegram, the bot reachable in the configured chat, hooks wired, service
  active. One ✓/✗ line each, exit 1 if anything is off. Triage only; nothing
  gets fixed.
- Voice messages, audio and video notes are now saved and typed in like a photo
  or file — the same download path, just three more Telegram update fields
  feeding it. No transcription; the agent gets the path and decides.
- Auto-restore after a reboot. A reboot kills every tmux session; nightmux now
  checks each bound topic against tmux at startup and either relaunches with
  `"auto_restore": true` or posts a "machine restarted?" message with a Restore
  button, instead of a topic that quietly never comes back. `!restore` runs the
  same relaunch on demand — it was already what `!resume` did for a dead
  session, just under the name people actually look for.
- Git worktrees for running more than one agent on the same project without
  them fighting over the same files: `!new api ~/code/api @refactor-auth`
  checks out (or reuses) a worktree for that branch under `~/code/api-wt/` and
  starts the session there. `!worktrees` lists a repo's worktrees and which
  session is sitting in each.
- A command-center topic: `!center` binds the topic it's typed in to watch and
  control every session instead of one — it never gets an entry in `topics`,
  and plain text there points at `!board` instead of going nowhere. `!board`
  (usable from any topic) reuses `!status`'s own state classification for a
  one-glance summary of every session, with a cheap cost figure where a
  transcript is already known. A pending approval now mirrors into the command
  center alongside its own topic, and whichever copy is tapped first resolves
  it for both — the loser's buttons are pulled rather than left able to send a
  second, conflicting keystroke into the same pane. `!all <targets|--all>
  <prompt>` sends one prompt to several sessions at once, through the same
  hold/queue/type path a single topic already used, echoing exactly who it is
  about to hit before the first prompt goes anywhere; a `readonly` topic is
  never among them. `!digest` run from the command center loops every bound
  session instead of needing one run per topic.

### Fixed

- The status-line snapshot of a parked session was swept after a day, taking
  its context figure, its usage windows and its transcript path with it. Claude
  Code rewrites that file when it redraws its status line, and an idle session
  does not redraw — so age measured how long the agent had been quiet, not how
  wrong the file was, and the sessions pruned first were the parked ones
  `idle_hint` and `!ctx` exist to talk about. One box was down to five snapshots
  for twelve panes. A snapshot whose pane is still alive is now kept however
  old, and `STATE_FRESH` covers a session parked over a holiday.


- A session whose name matched a *window* name elsewhere was reported gone by
  every command typed at it. `real_session` asked `tmux display -t <name>`, and
  `-t` there is a target-**pane**, a grammar in which a bare word is a window
  name — so a session called `claude` resolved to whichever session held one of
  the windows every Claude Code pane is called, and the topic bound to it got
  "tmux session 'claude' is gone" for everything it typed while the watcher saw
  the session alive. The target is now `<name>:`, which addresses a session and
  still resolves the abbreviation `!bind` accepts.


- A tmux call that timed out was read as "no sessions are running". `run()`
  reports a timeout by returning `[tmux timed out after 10s]` — text, which
  `live_sessions()` then parsed as an empty pane list, so every bound topic was
  told its session had died and was rebaselined on the way back. Rebaselining
  drops the transcript byte offset, so whatever the agents produced during the
  gap was skipped silently. One box logged 209 of these timeouts and 72 false
  deaths in three days. `live_sessions()` now returns None when tmux did not
  answer and the watcher skips the tick, keeping the panes it already knows.
- A tmux server that stops answering is announced once, and its return once,
  instead of nine topics' worth of 💀 and ↩️ per outage.
- `track_cwd` spawned one `display-message` per session per tick to read a
  working directory the tick's own `list-panes` call could have returned. That
  is nine fewer processes per tick against the single-threaded tmux server these
  timeouts come from.


- Two topics could be bound to one tmux session. `state` is keyed by session
  name, so they shared a scrape cursor: whichever topic the watcher reached
  first consumed the new output and the other was told nothing, which reads
  exactly like output landing in the wrong topic. `!bind` refuses it, `!status`
  flags any pair already in the config.
- `!ctx` re-read the whole transcript every time it was typed. The report is
  cached on the file's size, which for an append-only transcript is the same
  thing as its contents.
- The context warning fired *after* the compaction it warns about. `CTX_WARN`
  was a fixed 75 while `autocompact` commonly sits at 70, so the warning was
  dead code; it now lands 10 points ahead of whatever `autocompact` is set to.
- A `/compact` that never landed — keystrokes eaten by an open menu, a turn
  starting on the same tick — was never retried. `compacted` stayed set, the
  `pct < at` re-arm never fired, and the session carried a full context for the
  rest of its life in silence. Retried once after a grace period, then reported.
- The directory-collision guard refused a topic a second agent on its own tree.
  Another topic's session in that directory is a collision; the topic's own is
  not.


- Without a status-line snapshot, a session now resolves to the pane running a
  known agent binary before falling back to the focused one — so a split window
  no longer sends keys into whichever pane happens to hold the focus on the
  sessions the sidecar does not cover. Two agent panes in one session with no
  snapshot between them is still a guess, and an agent added through the config
  still falls back to the active pane.
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
- A turn cut off in a session driven from its own terminal is now noticed. All
  three signals for "work was in flight" — a live trace, the previous tick, the
  pane's mode — assume nightmux either started the turn or caught the pane
  rendering while it ran, and neither holds when you type into the session
  yourself and the window is found spent between two polls. Three consecutive
  real limits were missed that way, each followed seconds later by kilobytes of
  delivered output. A transcript that grew within the last two minutes is now
  evidence in its own right.
- A prompt refused before it ever got a turn now goes back on the queue. The
  recovery existed but was reachable only when something was already running,
  which is the one state a refusal rules out — so the case it was written for
  could not reach it. Whether a turn ran is now tracked directly (the pane went
  busy, the transcript grew, or output arrived), which also keeps a prompt whose
  turn finished inside one poll interval from being sent a second time.
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
