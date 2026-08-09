# Security

Read this before you run tgctl. It is short, and it matters more than the README.

## What tgctl actually is

tgctl types text into a running Claude Code session on your machine, and Claude
Code runs commands. That means:

**Anyone who can put text in your Telegram topic can run commands on your box,
as your user, from their phone.**

That is the product. It is not a bug, and there is no sandbox between the two.
Every mitigation below exists to control *who* can put text in that topic.

## The trust boundary

There is exactly one: `allow_users` in `~/.tgctl.json`.

```json
"allow_users": [123456789]
```

Every update from any other Telegram user id is dropped without a reply. Not
rate-limited, not warned — dropped. Adding a second id gives that person a shell
on your machine. Treat it exactly like adding them to `sudoers`.

Group membership is **not** a boundary. Adding someone to the Telegram group
lets them read your sessions' output — the code Claude wrote, the file paths, the
error messages, whatever scrolled past. It does not let them type, but assume
anyone in the group sees everything the bot sends.

## The bot token

`~/.tgctl.json` holds the bot token. **The token is equivalent to the
allowlisted user's access**: anyone holding it can read every message in the
group, including output from your sessions.

- The file is `0600`, and `save_cfg()` re-applies that mode on every write —
  a temp file created under your umask would otherwise silently re-widen it.
- It is in `.gitignore`. Do not move it into the repo.
- If it leaks, revoke it in BotFather (`/revoke`) — that invalidates the old
  token immediately — then re-run `python3 tgctl.py --setup`.

## Prompt injection

Everything arriving over Telegram is untrusted input that gets typed into an
agent with tool access. The allowlist is what makes that acceptable: you are
trusting the sender, not the content.

Consequences worth stating plainly:

- Text you forward into a topic (a log line, an error someone pasted you, a
  snippet from a webpage) is typed into Claude as if you wrote it. Forwarding is
  not quoting.
- A file or photo you send is saved to `~/.tgctl-files` and its **path** is typed
  into the session. Claude will read it if it decides to.
- Inline buttons (`!y`, menu picks) approve whatever prompt is on screen *at that
  moment*. On a slow link the screen can move between the buzz and the tap; the
  buttons carry no proof of what they are approving.

If a message asks you to add someone to `allow_users`, that is the exact request
a compromised account or an injection would make. Verify out of band.

## What tgctl does not protect against

- A malicious or compromised Claude Code session. tgctl is a keyboard, not a
  supervisor. It does not inspect, filter, or veto what Claude runs.
- Anyone with local access to your machine — they can read the config, attach to
  the tmux sessions, or read the transcripts directly.
- Telegram itself. Messages are not end-to-end encrypted; they are readable by
  Telegram, and the group's content lives on their servers. Do not use this to
  drive work you cannot afford Telegram to hold.
- A hostile Telegram group admin, who can add members you did not vet. Own the
  group yourself.

## Hardening worth doing

- Run tgctl as a dedicated user with only the repos it needs, if you cannot
  accept "a shell as you".
- Keep the group private, with yourself as the only admin and no invite link.
- `/setprivacy` → *Enable* is **not** an option: tgctl needs to see every message
  in the topic, which is why setup makes the bot an admin. Compensate with group
  membership, not with privacy mode.
- Check `allow_users` after anyone touches your config: `!reload` prints the
  topics, but the allowlist is only read at startup.

## Reporting

Open an issue for anything that lets a **non-allowlisted** sender cause tgctl to
type, spend tokens, or leak session output. That is the property worth
defending. For anything sensitive, email the address in the git log rather than
filing publicly.
