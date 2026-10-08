# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
versions follow [semver](https://semver.org/). The public surface is the command
names and the shape of `~/.nightmux.json` — those are what a major bump protects.

## [Unreleased]

### Added

### Changed

### Fixed

## [1.3.0] — 2026-10-08

### Added

- `!qa HH:MM [url]|now|off` (nightly browser QA pass that files issues), `!leaderboard [post]` (opt-in counts on a public board), a GitHub Pages site (landing, live office demo, leaderboard), a Docker image on ghcr.io, a cloud-init for fresh VPSes, an installer that works with `curl | sh`, and a new README top.

- `!saved` counts what nightmux did for you (context not re-read, night turns, limit resumes, green checks); `!wrapped [days]` draws a shareable card with a tweet button; the night reel is signed and gets one too; `!public on|expose|off` serves a read-only office (states only) at /public/<token>.

- `!race [claude,codex] <task>`: several agents do the same task, each in its own git worktree; one card compares changes and `!goal` results, a 🏆 tap stages the winner. Voice notes are transcribed with your own `transcribe_cmd` (e.g. whisper.cpp) and shown back as 🎙.

- Built-in agents: `!cursor` (Cursor CLI), `!amp`, `!goose`, `!qwen` (Qwen Code) — start, resume, `!update` and their own look in the office.

- Dashboard-only mode: with no bot token nightmux runs on the dashboard and its chat view alone — `--setup` offers it at the token prompt, + project numbers topics locally, `--doctor` accepts it.

- `nightmux --demo [port]`: serves the office with a made-up night across three projects — working, asking, hitting limits — no Telegram bot, config or API keys needed.

- The office has a lounge: idle agents walk to the coffee machine, TV or toilet and back; an agent on a usage limit goes to bed until the window resets. Demo GIF re-recorded.

- Token savings and a prompt coach: auto-compact on by default (200k), `!fresh` (memory → /clear → re-read after a green `!goal`), `!lint` (holds vague prompts; ✨ improve rewrites them from your first-try prompts), correction detection feeding `!route stats` and learned routing, `!coach`, and `!ladder` (haiku/sonnet/opus by task class, stepping up when the agent struggles).
- `!briefing HH:MM|now|off`: one message each morning — done overnight, waiting for you (questions, open PRs with GitHub's merge verdict, production errors), usage windows with their forecast, and what is queued, held or stopped — with night reel and stats buttons.

- Dashboard: **💬** on each topic opens it as a live chat — messages both ways, working menu buttons, a composer, a working indicator, in-page notifications — at `/chat?t=<topic>`, peers included; the dashboard is installable as an app (manifest, service worker, icon).

- `!deps`: known vulnerabilities (npm audit, pip-audit, govulncheck) worst first and packages a major version behind, with an **upgrade with agent** button; `!deps nightly HH:MM` checks every night and reports only findings.

- Limit forecast: usage windows are sampled every minute; when one will fill before it resets (within 90 min) at the last hour's pace, topics working on that agent get one ⏳ warning with a switch button; `!forecast`, and the dashboard limit cards show the projected time.

- Project memory: `.nightmux/memory.md` per project (what it is, how to run/test, decisions, gotchas, in progress), rewritten by the live agent after 6 turns and 15 quiet minutes and read first by every session nightmux starts or switches to; `!memory [update|on|off]`.

- Office: a server strip with status dots, ⚙ dashboard / + project / + server links (deep-linking to the form and the add-server steps), and a banner when a server is not answering. Topics on a peer that is down no longer vanish from the office and dashboard: they show, marked, with where to fix it.

- Dashboard: **+ add server** gives the steps and a one-use, 30-minute `nightmux.py --join <code>` command; the new machine fetches the bot settings and a peer secret over the tailnet, configures itself as a peer and installs the service, and appears in the new **servers** section (status, agents, topics, remove). A **setup** panel lists what is missing on this machine with the fix — the same checks as `--doctor`, which gained bot topic rights, agents, projects folder, tailnet dashboard, gh and Chromium.

- Deploy previews: `!watch` posts the preview URL a host attaches to the PR's commit (GitHub deployment, deploy-preview status, or a bot comment) with open/screenshot buttons; bot comments are no longer fed to the agent as reviews. `!errors`: a per-topic webhook for Sentry (or any JSON) — new errors become 🛠 fix buttons or, on `auto`, prompts; `!errors expose` publishes only /hook on :8443 via Tailscale Funnel.

- `!desktop`: a virtual screen (Xvfb + openbox) with a password-protected noVNC link over the tailnet; `!tools add desktop` gives the agent nightmux's own computer-use MCP server (screenshot, click, type, key, scroll, open); `!desktop open|shot|off`.

- Android: `!apk` builds the project's debug APK (Gradle wrapper at the root or under `android/`, or Flutter) and sends it to the topic; `!apk install` puts it on your phone over wireless debugging (`!android pair|connect <ip:port>`); `!shot android` sends the phone's screen, and a photo after it is a bug report with the activity on screen and recent logcat errors. A failed build offers "send to agent".

- `!issues` / `!issue <n>`: open issues as buttons; the agent gets the issue, a branch and the PR recipe, nightmux finds the branch's PR and watches it (CI failures, reviews, merge button). `!issues auto [label]` takes labelled issues one at a time while the topic is quiet.

- `!tools add browser [all]`: registers Playwright's MCP server with the topic's agent(s) via each CLI's own `mcp add` (Claude Code at local scope), tells the agent to verify UI changes with it, and offers a restart to load it; `!tools rm browser`, `!tools restart`.

- Dashboard: **+ new project** creates the Telegram topic, folder and session (optionally with an idea brief and check loop, on a peer if chosen); topic cards gain agent chips (tap to make live), **+ agent** and **close** (stops agents, unbinds, closes the Telegram topic, keeps files).

- `!route auto|off`: a prompt that starts a new task is classed light/normal/heavy and the topic switches to the best live bench agent for that class; mid-task prompts never move; `!goal` green/stuck results adjust per-class scores.

- Point and fix: a photo sent within two hours of `!preview`/`!shot` reaches the agent with the page URL, that page's console errors and its rendered DOM (as a file), and an instruction to fix what is marked and recheck.

- `!reel [hours]` / `!reel daily HH:MM`: the office's desks are recorded once a minute; the busiest room is replayed as a GIF (the office page draws each moment in headless Chromium, a stdlib PNG/GIF encoder stitches them) with captions and per-project commit stats.

- `!pair <agent> [rounds]`: after every turn that changed the tree, a second agent on the bench reviews `git diff <since>` in the same folder; real findings go back to the coder (2 rounds by default, then to you), LGTM is a quiet 👍.

- Loop guard: two independent signs of an agent circling (same error 3×, one file churned while the diff stays flat, repeated apologies, `!goal` failing the same way) ping the topic with step back / hand to another agent / pause buttons; `!loopguard auto|ping|off`.

- `!idea [@agent] <what to build>` in a fresh topic: a new folder under
  `projects_root` (never reusing one), `git init`, the agent started with a
  spec → MVP → `./check.sh` prompt queued, and `!goal sh ./check.sh` on.

- `!p`: saved prompts as tap-to-send buttons — built-ins `review`,
  `fix-tests`, `spec`, `explain`, `tidy`, `ship`; `!p save <name> <text>`
  with `{{args}}` for what follows the name; config overrides and hides
  built-ins.

- `!watch pr [n]`: polls the topic's pull request; a failed check's log and
  new review comments (inline too) are queued to the agent once each, the gh
  account's own comments skipped; green pings once per commit with a merge
  button (`!watch merge`); a merged or closed PR ends the watch.

- `!preview`: finds what the session's own processes serve over HTTP (by
  process tree, agents' own sockets excluded) and sends tap-to-open links on
  the tailnet — `tailscale serve` for loopback-only dev servers, never public.
  `!shot [:port][/path|url]` sends a phone-size screenshot (headless Chromium).

- `!goal [rounds] <check>`: after every finished turn the check (tests, build,
  lint) runs in the project dir; a failure's tail goes back to the agent as
  its next prompt until it passes. Reports green once; stops and pings on the
  same failure three times or when out of rounds; your next message resumes.

- Two (or more) servers behind one bot: the primary forwards a topic's
  updates to the peer that runs it (`!server <peer>` / `!server local`), the
  peer (`"poll_telegram": false`) replies to Telegram directly. Peers talk on a
  secret-gated `/peer/` listener; the dashboard and office aggregate every
  machine's topics, metrics and limits.

- Dashboard (`/` on the webhook port): server metrics (CPU, memory, disk,
  load, uptime, tmux sessions) and limits per agent — sessions live/busy/held
  plus the usage windows Claude Code and Codex report themselves.
- Chat analysis — `!stats [days]` (also `/tmstats`) and the dashboard's
  *analyze* button read Claude Code, Codex, opencode and agy transcripts on
  this machine and report prompts, model calls, tokens, cache hit rate,
  context size, nudge prompts and model mix, with concrete tips on what to
  change. Counts only; no prompt text leaves the function.

### Fixed

- A hand-broken `~/.nightmux.json` now stops the daemon with one line naming the line/column and the usual cause, instead of a traceback; `--join` keeps an unreadable config as `.broken` rather than replacing it silently. `install.sh` clones/updates `~/nightmux` from GitHub instead of installing the (lagging) PyPI release.

- `!apk`: a build that runs past `apk_timeout` (default 60 min, was a fixed 30) now stops entirely — the Gradle client no longer keeps running after the wrapper shell is killed.

- The daemon now adds your login shell's PATH (and common per-user bin dirs) at startup: under systemd/launchd, per-user installs like ~/.local/bin/agy and ~/.opencode/bin/opencode were "not installed" to the dashboard, failover buttons and `!update`, though tmux sessions ran them.

- selfcheck no longer fails when `tmux -V` gets no answer on a loaded CI runner; it skips that one check.

- Projects splitting across two folders: `!<agent> name` with no dir now
  starts in `projects_root/name` (default `~/projects/name`) instead of bare
  `$HOME`, and the topic's recorded dir is only filled when missing — an
  agent `cd`-ing elsewhere no longer drags the topic (and the next agent
  switched in) with it.
- A session whose folder was deleted and recreated under it is reported once
  in its topic instead of silently writing into the unlinked copy.
- Peers: the "don't poll Telegram" switch is `"poll_telegram": false`;
  `"poll"` is already the watcher's tick interval.

- `--setup` on a fresh machine crashed with `FileNotFoundError:
  ~/.claude/nightmux-statusline.sh` — the status-line script was written
  before `~/.claude` was created.
- A topic's bench could file one agent's session under another (Claude's
  session listed as agy), so `!agy` switched into Claude. The agent running
  in the pane now decides; config-defined agent keys are left alone.
- Dashboard: the send box no longer clears and the page no longer jumps on
  every 4-second refresh — cards are updated in place instead of rebuilt.

- The office, redrawn: a night city through the window (moon, shooting
  stars, lit windows) that turns to dawn, a lamp over the live agent, monitor
  glow on faces, a look per agent (claude's hood, codex's cap, agy's headset,
  opencode's beanie), real screen content per state, and a 3×5 bitmap font
  for the clock and name labels. A finished turn sparkles and a hand-off flies
  a folder between desks — live, from state changes. `/office?demo` plays a
  scripted night shift deterministically; `docs/office-demo.gif` is made
  from it.

- The office: `/office` on the webhook port is a pixel-art page with a room
  per topic and a desk per agent on its bench. Every animation is a real state:
  typing (busy, with what it is doing), hand up (asking — the menu's real
  options as buttons), asleep with a countdown (usage limit, with hand-off
  buttons), puzzled (unread screen), empty chair (gone), sticky notes (queued).
  Tap an agent for its screen, answers, a prompt box, esc/failover/restore.
  Screen text is redacted before it leaves; it reads the watcher's own capture,
  no tmux call per viewer. `!office` posts the link; `office_url` is where your
  phone reaches it (`tailscale serve --bg <port>` keeps it on your tailnet).
- `!failover <agent>`: a topic held on a usage limit hands its work to another
  installed agent now instead of waiting hours for the reset. The limit message
  carries one-tap buttons for it. The next agent gets the working tree and the
  instruction that was cut off, not a summary — the limited agent can't write
  one. `"failover": "codex"` in the config does it unasked, once per hold.
- Secrets pasted into the chat (Telegram bot tokens, Anthropic/OpenAI/GitHub/
  AWS/Google/Slack keys, private keys) are never typed into the agent, queued
  or logged, and are deleted from the chat when the bot has the rights. The
  message log line is redacted. `!raw` is the deliberate override.
- `!update [agent]` runs each installed agent's own updater (`claude update`,
  `codex update`, `agy update`, `opencode upgrade`, npm for gemini, pip for
  aider) and reports versions before and after. `"auto_update": true` (daily)
  or an interval like `"12h"` does it on a schedule in the background and posts
  only what changed or failed. Off by default — it runs installers unattended.
  `update_cmds` overrides or adds an agent's updater; `""` disables one.

- `!plan <big task>` asks the topic's agent to break it into steps, then runs
  them one at a time on idle — the same queue `!shift` drains, just filled by
  the agent instead of typed in by hand. `!shift` still reports progress or
  stops it early; `!plan cancel` drops a request still waiting on an answer.
- A page at the webhook port's `/` (enabled the same way, `"webhook_port"` in
  the config): every bound topic at a glance, polling `/api/topics`, with a
  box to send a prompt through the same POST route the webhook API already
  had. No new port, no new dependency, no new way to reach a session.
- Plugins: any executable file dropped in `~/.nightmux-plugins/` becomes a
  command — its filename is the trigger, stdout is the reply, same shape as
  `!git`/`!grep`. Never reaches a session's keyboard, so it runs in a
  read-only topic same as any other read command. `!plugins` lists what's
  there.

### Fixed

- A usage window that reset while the pane read as `unknown` cleared its hold
  silently and never sent the queue — the drain only types into a pane it reads
  as idle. The topic is now told what's queued and why, with `!pane`/`!raw`.
- tmux's own `[tmux timed out after 10s]` was classified as pane content, so
  under load every session read `unknown` and held prompts. A timed-out capture
  is now no reading; the last mode stands.
- Claude Code's select menu (`Enter to select · ↑/↓ to navigate`) now reads
  as `waiting` instead of `unknown`.
- Held work for sessions no topic watches was "restored" on every restart and
  could never be released. It is dropped at startup, and logged.
- Sessions already gone when the daemon started were each announced as
  "💀 gone" in the same second — a 429 from Telegram on every restart. Only a
  death this run actually saw is announced now.
- `pane_state()` read anything that didn't match a known busy pattern as idle —
  including a screen it had never seen before, which is exactly the case a
  misread dialog comes from. It now checks for a recognised idle shape too
  (a bare prompt, a shell prompt, opencode's bottom bar) and returns `unknown`
  for neither, instead of guessing. `send_prompt()` holds a prompt on `unknown`
  the same as on `busy` rather than typing into a screen nobody has confirmed
  is safe; `!raw` still overrides. Unrecognised screens are logged to stderr
  as they happen, so a new dialog shape shows up as a log line before it shows
  up as a bug report.
- A session whose agent exited into a bare shell, and a session about to be
  killed by `!restore`, now carry the pane's last lines in the message —
  the crash context used to disappear at exactly the moment someone would
  want to read it.
- The "no context figure" warning fired for every agent, including ones that
  never had a context figure to begin with — only Claude Code's status line
  reports one. It's gated to Claude Code sessions now, and the "already
  warned" flag survives a daemon restart instead of re-nagging once per boot.

- `pane()` asked tmux for the entire scrollback (`-S -`) on every watch tick.
  It now asks for the last 2000 lines — tmux's own default `history-limit`, so
  on a default server the content is identical and the capture measures ~19%
  faster across nine sessions, while a server configured to keep more history no
  longer makes every tick proportionally slower.
- The watcher polled every bound session serially — one tmux round-trip at a
  time — so a single slow or hung session stalled every other session's state
  update behind it for the rest of that tick, up to that call's own 10s
  timeout. Each session's slice of a tick (`watch_one`) now runs in a small
  thread pool, `min(len(bound), 8)` workers (capped so a large bench doesn't
  open dozens of tmux client processes against the one tmux server at once),
  so N sessions' tmux round-trips overlap instead of queueing. Measured on this
  box, a healthy 14-session tick went from ~0.25s to ~0.15–0.20s; the point of
  it is the tail, not the average — one laggy session no longer costs every
  other session up to 10s of silence. Two writes in the per-session chain were
  not session-scoped and needed a lock now that sessions run concurrently: the
  account-wide usage-limit warning dedup (`_warned`, one 5-hour/weekly window
  shared by every session on the account) and the chat-wide progress-message
  throttle (`_prog_at`). Everything else in the chain already lived in that
  session's own `state[sess]` dict and needed nothing.

- A menu digit or `!y`/`!n` sent to a pane that was not asking anything was
  typed into the agent as text. Claude Code queues that as a message, so five
  taps of `!3` at a working agent left `33333` sitting in its prompt box waiting
  to be sent, and the topic was told nothing. Answer keys now require a waiting
  pane; `!esc`, `!int`, the arrows and tab are meant for a working pane and are
  unaffected.

- The watcher only read the session a topic was bound to, so a benched agent
  could be written to and never read. `@agy <prompt>` sent a prompt whose answer
  nobody would ever see, and `!consult` sat out its full timeout on an agent that
  had answered on screen minutes earlier. It now walks every session on a topic's
  bench.

- Claude Code's trust prompt stopped being recognised, and the session that
  showed it was killed by the next thing sent to it. The dialog changed from a
  boxed numbered list to a bare pointed one (`❯ No, exit` / `Yes, I trust this
  folder` / `Enter to confirm`), which matched none of the waiting patterns — so
  the pane read idle, the prompt was typed into it, and Enter took the
  highlighted option, which is "No, exit". `CHOICE` matches a pointed option
  that is neither numbered nor boxed, counted only alongside one of `ARROWED`'s
  footers, and `ARROWED` now accepts "enter to confirm" as well as "enter
  confirm". Both dialog shapes are in the pane corpus.
- `!consult` waited the full timeout on a participant whose session had died,
  and hung outright when only one agent answered round one.


### Added

- `!autoyes <agent|off>` — answer one agent's own permission menus for it, per
  topic, never global and never on by default. A permission dialog is the last
  gate before an agent acts on the machine, so it presses only an option it can
  positively identify as the affirmative one (a menu with no recognisable yes is
  left for a human), announces every answer, and stops after 25 in an hour so a
  dialog loop cannot run all night.

- `@claude <text>` / `@agy <text>` — send one prompt to one agent on the topic's
  bench without switching the topic to it. Switching is the wrong verb when a
  project keeps two agents side by side and you want to put one question to one
  of them.
- `!use [agent]` — run the prompt a consultation settled on, in the agent the
  topic is on. The report carries it as a button: a prompt you have to retype on
  a phone is a prompt that does not get run.
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

- Model ladder and auto routing switch only on threads under 30k tokens (a step up when the agent struggles is the one exception, once per task); `!route stats` shows what switches re-billed.

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
