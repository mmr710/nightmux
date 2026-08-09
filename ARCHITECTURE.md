# Architecture

Why telemux is shaped the way it is. The code carries the same notes as
docstrings; this is the map.

## Shape

```
  Telegram  ──getUpdates(25s)──►  poll loop  ──►  per-topic worker threads
     ▲                             (main)              │  handle(), inject()
     │                                                 ▼
     │                                        tmux send-keys ──► claude
     │                                                            │
     │                                                            ├─ Stop hook ──┐
     │                                                            └─ Notify hook ┤
     │                                                                           │
     └────────  send() ◄──  watcher thread  ◄── capture-pane / transcript JSONL ◄─┘
                            (one, for every session)
```

Two long-lived threads plus one worker per topic. No event loop, no framework,
no broker: the only shared mutable state is a `cfg` dict behind a lock, and a
`state` dict that only the watcher writes structurally.

## The four files

| | |
|---|---|
| `telemux.py` | the daemon. Polling, commands, tmux injection, scraping, spend accounting, setup |
| `tm-state.py` | `statusLine` sidecar. Parks context %, 5h/7d windows, model, transcript path, `$TMUX_PANE` |
| `tm-stop.py` | `Stop` hook. Sends the final assistant message as exact text |
| `tm-notify.py` | `Notification` hook. Sends permission prompts the instant they appear |

The three small ones import `telemux` for its config and send helpers, and every
one of their failure paths exits 0. A hook that fails must never block the
session it is reporting on.

## Threads

**Poll loop (main).** `getUpdates` with `timeout=25` and
`allowed_updates=["message","callback_query"]`. It does no work itself: each
update goes to `dispatch()`, which routes by `message_thread_id` to that topic's
worker, creating the worker on first use.

**Workers (one per topic).** A `queue.Queue` per topic keeps that topic's
messages in order, while a slow command — `!grep` over every transcript, a large
`!get` upload — stops blocking other topics and the poll loop behind them.

**Watcher (one, for all sessions).** Every tick: one `tmux list-sessions` for
liveness, then per session `watchdog → flush_new → nudge → drain → autocompact →
idle_hint`, then one `save_queue`. Each session is wrapped in its own
`try/except`, and the whole tick in another: an exception escaping here would
take the thread with it, leaving a daemon that answers commands while silently
monitoring nothing. Tick interval is `poll` (default 2s), dropping to 10s once
nothing has moved anywhere for 5 minutes.

**Offsets are acked, not counted.** Because topics run in parallel, updates
finish out of order, and the only safe restart point is the oldest update still
in flight. `Acks` tracks dispatched ids and persists the offset only past a
contiguous run of finished ones. It walks the ids actually dispatched rather than
incrementing, because **Telegram skips update ids for filtered-out update
types** — a `+1` walk would wait forever on an id that never arrives.

## State

| Where | What | Survives restart |
|---|---|---|
| `cfg` (memory + `~/.telemux.json`) | token, chat, allowlist, topic→session bindings | yes |
| `~/.telemux.offset` | polling offset | yes |
| `~/.telemux-state/queue.json` | prompts held for a rate-limit reset | yes |
| `~/.telemux-state/<session_id>.json` | sidecar snapshots: context %, limits, transcript path | as a cache |
| `~/.telemux-hooked/<session>` | "the Stop hook owns delivery for this session" | as a cache |
| `~/.telemux-files/` | inbound photos and documents | 7 days |
| `state` (memory) | screen offsets, warning flags, mode, echo suppression | **no, deliberately** |

That last row is the important one. Everything in `state` except the queue is a
cache that rebaselines against a live session on the next tick; restoring it
stale would resend old output or suppress new output. Only what the user is
*owed* — held prompts and their reset time — is written to disk.

`save_cfg` merges onto what is on disk, so a hand edit between saves survives,
and re-applies mode `0600` on every write: the temp file is created under the
umask, so without that each save quietly re-widens the file holding the token.

`prune` sweeps `~/.telemux-files` at 7 days and sidecar snapshots at 1 day, and
skips `queue.json` explicitly — that file is only rewritten when its contents
change, so mtime says nothing about whether it is live. Without the skip, a
prompt queued behind a session that had been busy for a day would be swept.

## Getting output back

Three paths, in order of preference:

1. **Transcript tail.** When the sidecar is installed, telemux knows the JSONL
   path and reads it incrementally by byte offset. Exact text, a real tool trace,
   no terminal chrome.
2. **Stop hook.** Delivers the final message directly. Touching
   `~/.telemux-hooked/<session>` claims delivery, so the scraper stands down for
   `HOOK_FRESH` (15 min) and nothing arrives twice.
3. **Pane scrape.** `tmux capture-pane`, diffed against the last capture by
   common prefix. Always available, and the reason telemux works with no hooks at
   all — just noisier, and without usage numbers.

Regexes do the rest: strip box-drawing chrome and spinner lines, detect a waiting
prompt, detect a busy session, pull numbered menu options into inline buttons,
recognise a rate-limit banner and the reset time inside it. What telemux just typed
is remembered per session and filtered out, so the TUI's echo of your own message
is not sent back to you.

## Sending

Telegram allows roughly 20 messages a minute to a group and **edits count**, so
sends are serialised behind a 1.1s gap. `getUpdates` and `answerCallbackQuery`
bypass it — one is a long poll, the other has its own limit. A 429 is retried
once if `retry_after` is small enough; beyond that the message is dropped rather
than freezing every other session behind it. Sends time out at 15s for the same
reason: one watcher thread serves every topic.

Messages are chunked at 3500 characters (the cap is 4096, and the `<pre>` wrapper
needs room). More than two chunks and it goes up as a file attachment instead.
Live progress edits one message on a timer rather than posting a stream.

## Rate limits and the queue

When a session hits its usage limit, telemux parses the reset time from the banner
(both "resets in 2h 14m" and "resets at 3pm" forms), and holds anything typed
until then plus a minute of slack. Held prompts go to disk immediately, so a
restart, a reboot or a crash mid-wait loses nothing — a five-hour hold outlives
many daemon restarts. On resume the queue drains in order and the topic is told
what happened.

`save_queue` is behind its own lock. The watcher and every topic worker call it,
and two threads sharing one temp path can replace a half-written file over a good
one — after which `load_queue` reads a truncated file, returns nothing, and
silently loses exactly what the feature exists to keep.

## Decisions

**tmux, not a subprocess.** telemux attaches to sessions instead of owning them, so
you can SSH in and type directly mid-conversation. A wrapper process would have
to reproduce the TUI, own the lifecycle, and stay in sync with a terminal it
cannot see. The cost is that some output is scraped rather than structured, and
the hooks exist to buy most of that back.

**Forum topics, not one chat.** The thread-per-project model is native to
Telegram, needs no client, and gives every session its own scrollback and
notification setting for free.

**No dependencies.** The value of "clone it and run it on the box you already
have" is higher here than any library would buy. CI enforces it.

**JSON files, not a database.** Total state is a few kilobytes and it must be
hand-editable — `!reload` exists precisely so you can fix the config with an
editor over SSH.

**No web UI.** It would be a second surface to secure, and Telegram already
provides auth, push notification, file transfer, and a client on every platform.

**Rejected:** a relay server (adds a machine that can read everything), an
`asyncio` rewrite (three threads and a queue are smaller than the reasons to),
per-image cost warnings (`!ctx` already surfaces them), and systemd sandboxing
(it breaks access to the user's tmux socket for marginal gain — the daemon can
type into Claude anyway, so confining it is theatre).

**No timezone library.** Python 3.8 has no `zoneinfo`, so telemux scopes `TZ` and
calls `time.tzset()`. A fixed UTC offset would silently go an hour wrong for half
the year, so `!tz` takes zone names.

## Failure model

- Daemon killed mid-handling → the update replays; the offset was never acked.
- Daemon killed while a prompt is held → the prompt is on disk and comes back.
- Telegram down → poll retries; the watcher keeps running and buffers nothing
  (the pane is the buffer).
- tmux session dies → `watchdog` reports it once, then stays quiet; a session
  that comes back is rebaselined rather than replayed.
- Hook not installed → scrape fallback; everything works, less prettily.
- A malformed transcript line → skipped, not fatal.

## Extending

**A new command.** Add a branch to `handle()` returning reply text, or `None` if
it typed into the session. Note there is **no unknown-`!command` guard**: an
unmatched `!foo` falls through and is typed into Claude. If a command is
referenced by an inline button, it must have a real branch — `!cancel` exists for
exactly that reason.

**A new `/` alias.** Add it to `TG_SLASH` and `TG_DESC`. Only use names Claude
Code does not own, or the alias will shadow a real slash command; the `tg` prefix
(`tglog`, `tghelp`, `tgversion`) is the convention for collisions. `PASSTHRU`
holds Claude's own commands, registered purely so Telegram autocompletes them.

**A new agent.** Add `key: [command, resume-flags]` to `AGENTS`, or to
`cfg["agents"]` to do it without touching the code — `!<key>` then starts it and
`!resume` uses its flags. An unknown key is treated as its own command, so
`!opencode foo` works before anyone declares it. Keys are matched *after* the
named commands, so an agent called `git` or `queue` would never be reachable;
pick something else.

What is Claude Code specific is the transcript format, the two hooks and the TUI
regexes. An agent without those still works over the pane scrape — that path
came first and is still the fallback.

**Tests.** `selfcheck()` at the bottom of each file, plain `assert`s, no
framework. Anything with a branch gets one, and it runs in CI on 3.8 → 3.13.
