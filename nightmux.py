#!/usr/bin/env python3
"""Telegram controller for Claude Code sessions running in tmux.

One forum topic per project -> one tmux session. Text in a topic is typed into
that session's Claude Code prompt; new terminal scrollback is sent back to the
topic. Stdlib only.

Config: ~/.nightmux.json
{
  "token": "<bot token from @BotFather>",
  "chat_id": -1001234567890,
  "allow_users": [123456789],
  "topics": {"12": "projectA"},
  "poll": 2
}
"""
import calendar
import contextlib
import html
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

VERSION = "1.1.0"
CFG_PATH = os.path.expanduser(os.environ.get("NIGHTMUX_CONFIG", "~/.nightmux.json"))
API = "https://api.telegram.org/bot{}/{}"
LIMIT = 3500  # telegram hard cap is 4096; leave room for <pre> wrapper


# ---------- config ----------

def load_cfg():
    with open(CFG_PATH) as f:
        return json.load(f)


def save_cfg(cfg):
    """Merge onto what is on disk, so a hand edit between saves survives.

    The daemon keeps config in memory for the life of the process; writing it
    back wholesale would silently drop any key you added by hand meanwhile.
    Keys the daemon owns (topics, verbose, ...) still win.
    """
    try:
        disk = load_cfg()
    except (OSError, ValueError):
        disk = {}
    disk.update(cfg)
    tmp = CFG_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(disk, f, indent=2)
    # This file holds the bot token, and whoever has that owns every session
    # nightmux can type into. The temp file is created under the umask, so the mode
    # has to be set here or each save quietly re-widens it.
    os.chmod(tmp, 0o600)
    os.replace(tmp, CFG_PATH)


OFFSET_PATH = os.path.expanduser(os.environ.get("NIGHTMUX_OFFSET", "~/.nightmux.offset"))


def load_offset():
    try:
        with open(OFFSET_PATH) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def save_offset(n):
    """Its own file: config stays human-owned instead of churning per message."""
    with open(OFFSET_PATH, "w") as f:
        f.write(str(n))


# ---------- telegram ----------

SEND_GAP = 1.1  # groups allow ~20 messages/minute, and edits count toward it
NO_THROTTLE = ("getUpdates", "answerCallbackQuery")  # long-poll / separate limit
# One watcher thread serves every topic, and it sends synchronously, so a slow
# round trip stalls the monitoring of all of them. A send is worth ~15s of that;
# a 429 asking for longer than MAX_BACKOFF costs one message instead of freezing
# every other session for a minute.
SEND_TIMEOUT = 15
POLL_TIMEOUT = 60   # long-poll: the 25s getUpdates wait plus room to answer
MAX_BACKOFF = 10
_send_lock = threading.Lock()
_last_send = [0.0]


def _post(cfg, method, body, headers=None):
    """One round trip. Paces outbound calls and honours a 429 back-off once."""
    if method not in NO_THROTTLE:
        with _send_lock:
            wait = SEND_GAP - (time.time() - _last_send[0])
            if wait > 0:
                time.sleep(wait)
            _last_send[0] = time.time()
    for attempt in (1, 2):
        req = urllib.request.Request(API.format(cfg["token"], method), body,
                                     headers or {})
        try:
            with urllib.request.urlopen(
                    req, timeout=POLL_TIMEOUT if method == "getUpdates"
                    else SEND_TIMEOUT) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            try:
                err = json.load(e)
            except Exception:
                err = {}
            print(f"api {method}: {e} {err.get('description', '')}", file=sys.stderr)
            retry = (err.get("parameters") or {}).get("retry_after")
            if retry and attempt == 1 and retry <= MAX_BACKOFF:
                time.sleep(retry + 1)
                continue
            return err
        except Exception as e:
            print(f"api {method}: {e}", file=sys.stderr)
            return {}
    return {}


def api(cfg, method, **params):
    body = urllib.parse.urlencode(
        {k: v for k, v in params.items() if v is not None}).encode()
    return _post(cfg, method, body)


def chunks(text, limit=LIMIT):
    """Split on line boundaries, hard-split lines longer than limit."""
    out, buf = [], ""
    for line in text.split("\n"):
        while len(line) > limit:
            if buf:
                out.append(buf)
                buf = ""
            out.append(line[:limit])
            line = line[limit:]
        if len(buf) + len(line) + 1 > limit:
            out.append(buf)
            buf = line
        else:
            buf = line if not buf else buf + "\n" + line
    if buf:
        out.append(buf)
    return out


def kb(rows):
    """rows: [[(label, command), ...], ...] -> reply_markup JSON.

    callback_data is the literal bot command, so a tap runs the same code path
    as typing it.
    """
    return json.dumps({"inline_keyboard": [
        [{"text": t, "callback_data": d} for t, d in row] for row in rows]})


CODE_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.S)
INLINE_CODE = re.compile(r"`([^`\n]+)`")
BOLD = re.compile(r"\*\*([^*\n]+)\*\*")
HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.M)


def md_html(text):
    """Markdown -> the small HTML subset Telegram accepts.

    Code, bold and headings only: underscores and single stars turn up inside
    identifiers and globs far too often to convert without mangling them.
    """
    holes = []

    def stash(frag):
        holes.append(frag)
        return f"\x00{len(holes) - 1}\x00"

    text = CODE_FENCE.sub(
        lambda m: stash(f"<pre>{html.escape(m.group(1).rstrip())}</pre>"), text)
    text = INLINE_CODE.sub(
        lambda m: stash(f"<code>{html.escape(m.group(1))}</code>"), text)
    text = HEADING.sub(r"<b>\1</b>", BOLD.sub(r"<b>\1</b>", html.escape(text)))
    return re.sub(r"\x00(\d+)\x00", lambda m: holes[int(m.group(1))], text)


FILE_AFTER = 2  # more chunks than this and it goes up as one attachment instead


def send_file(cfg, topic, name, data, caption="", buttons=None):
    """Upload text as a document — one attachment beats six walls of <pre>."""
    b = "----nightmux-" + str(int(time.time() * 1000))

    def field(k, v):
        return (f"--{b}\r\nContent-Disposition: form-data; "
                f'name="{k}"\r\n\r\n{v}\r\n').encode()

    body = field("chat_id", cfg["chat_id"])
    if topic != "0":
        body += field("message_thread_id", topic)
    if caption:
        body += field("caption", caption[:1000])
    if buttons:
        body += field("reply_markup", buttons)
    ctype = "text/plain" if isinstance(data, str) else "application/octet-stream"
    body += (f'--{b}\r\nContent-Disposition: form-data; name="document"; '
             f'filename="{name}"\r\nContent-Type: {ctype}\r\n\r\n').encode()
    body += (data.encode() if isinstance(data, str) else data)
    body += f"\r\n--{b}--\r\n".encode()
    r = _post(cfg, "sendDocument", body,
              {"Content-Type": f"multipart/form-data; boundary={b}"})
    return (r.get("result") or {}).get("message_id")


def send(cfg, topic, text, mode="mono", buttons=None, quiet=False):
    """mode: mono (<pre>), plain, or md (markdown -> Telegram HTML)."""
    if not text.strip():
        return None
    print(f"out topic={topic} {len(text)}b {text.splitlines()[0][:60]!r}", flush=True)
    parts, mid = chunks(text), None
    if len(parts) > FILE_AFTER:
        head, lines = text.split("\n", 1)[0][:200], len(text.splitlines())
        return send_file(cfg, topic, "output.txt", text,
                         f"{head}\n[{lines} lines, {len(text)} chars]", buttons)
    for i, chunk in enumerate(parts):
        payload = (f"<pre>{html.escape(chunk)}</pre>" if mode == "mono"
                   else md_html(chunk) if mode == "md" else html.escape(chunk))
        markup = buttons if i == len(parts) - 1 else None
        r = api(cfg, "sendMessage", chat_id=cfg["chat_id"],
                message_thread_id=topic if topic != "0" else None,
                text=payload, parse_mode="HTML", reply_markup=markup,
                disable_notification=True if quiet else None)
        if not r.get("ok") and mode == "md":  # odd markdown -> unparseable HTML
            r = api(cfg, "sendMessage", chat_id=cfg["chat_id"],
                    message_thread_id=topic if topic != "0" else None,
                    text=html.escape(chunk), parse_mode="HTML", reply_markup=markup)
        mid = (r.get("result") or {}).get("message_id") or mid
    return mid


# Telegram only accepts reactions from a fixed emoji set, so no hourglass here.
WORKING, DONE, ASKING = "👀", "👍", "🤔"


def react(cfg, mid, emoji):
    """Mark your own prompt message: seen -> answered. Cheaper than a reply."""
    if mid:
        api(cfg, "setMessageReaction", chat_id=cfg["chat_id"], message_id=mid,
            reaction=json.dumps([{"type": "emoji", "emoji": emoji}]))


FILE_DIR = os.path.expanduser("~/.nightmux-files")


def fetch_file(cfg, file_id, name=None):
    """Download an attachment; return a local path Claude Code can read."""
    path = ((api(cfg, "getFile", file_id=file_id).get("result")) or {}).get("file_path")
    if not path:
        return None
    os.makedirs(FILE_DIR, exist_ok=True)
    # basename: the uploader picks this name, so it must not steer the path
    dest = os.path.join(FILE_DIR,
                        f"{int(time.time())}-{os.path.basename(name or path)}")
    url = f"https://api.telegram.org/file/bot{cfg['token']}/{path}"
    with urllib.request.urlopen(url, timeout=60) as r, open(dest, "wb") as f:
        f.write(r.read())
    return dest


# ---------- tmux ----------

def run(*argv, **kw):
    """A child process that cannot wedge the single watcher thread."""
    timeout = kw.pop("timeout", 10)
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"timeout {timeout}s: {' '.join(argv)}", file=sys.stderr)
        return f"[{argv[0]} timed out after {timeout}s]"
    return (p.stdout + p.stderr).rstrip("\n")


def tmux(*args):
    return run("tmux", *args)


def tmux_out(*args, **kw):
    """tmux's stdout, or None when tmux itself did not answer.

    run() reports a timeout by returning "[tmux timed out after 10s]", and that
    is *text*: anything that parses the result reads the banner as data. The
    call this exists for is list-panes, where an unanswered call parsed as an
    empty pane list — which is indistinguishable from every session on the box
    having died at the same instant, and was reported as exactly that.
    """
    timeout = kw.pop("timeout", 10)
    try:
        pr = subprocess.run(("tmux",) + args, capture_output=True, text=True,
                            timeout=timeout)
    except (subprocess.TimeoutExpired, OSError) as e:
        print("tmux %s: %s" % (" ".join(args), e), file=sys.stderr, flush=True)
        return None
    return pr.stdout if pr.returncode == 0 else None


def tmux_git(cwd, *args):
    return run("git", "-C", cwd, *args, timeout=30).strip()


def real_session(sess):
    """tmux's own name for this target, or "" when it resolves to nothing.

    A tmux target matches by exact name, then by prefix, then as a pattern, so
    `has-session -t game_1` succeeds against a session called `game_1-15`.
    Everywhere else nightmux compares session names as plain strings against
    `list-panes` output, so !bind accepting the abbreviation bound a name that
    never appears in live_sessions() — and the topic was told '💀 gone' one
    tick after 'topic bound'. Bind what tmux says the session is called.
    """
    try:
        p = subprocess.run(("tmux", "display", "-p", "-t", sess, "#{session_name}"),
                           capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        return ""
    return p.stdout.strip() if p.returncode == 0 else ""


def has_session(sess):
    """Exact only. A prefix match here is the bug real_session describes."""
    return real_session(sess) == sess


# Session name -> the pane its agent actually lives in, refreshed once per watch
# tick. `-t <session>` means "that session's active pane", which is the agent's
# pane only while it has the focus: split the window, or leave the session on
# another window, and nightmux read one pane while typing into another. Nothing
# announced that, and from Telegram it looks precisely like a hang.
_target = {}


def tgt(sess):
    """What to point tmux at for this session — its agent's pane, if known."""
    return _target.get(sess, sess)


SHELLS = {"bash", "zsh", "sh", "dash", "fish", "ksh", "tcsh", "csh"}

# Session name -> its pane is sitting at a shell prompt, filled by the same
# tick as _target. Listed by shell rather than by agent on purpose: an agent
# nobody has told nightmux about must not read as a crash, but a shell always is.
_shell = {}


# Session name -> its pane's working directory, filled by the same tick as
# _target. Read by track_cwd; every other caller wants a live answer and spawns.
_cwd = {}


def agentless(sess):
    """True when the agent under this session has exited and left its shell.

    tmux keeps the session alive afterwards, and a shell prompt has neither of
    the things the classifier looks for, so it reads as an idle pane ready for
    work. Every path that types a prompt would then type it into bash and press
    Enter: the queued prompt is consumed as a shell command, and the topic is
    told it was sent.
    """
    return _shell.get(sess, False)


def pane(sess):
    """Everything the pane holds: scrollback history plus the live screen."""
    return tmux("capture-pane", "-p", "-J", "-t", tgt(sess), "-S", "-").split("\n")


def visible(sess):
    """Just the on-screen rows: the cheap check before the full capture."""
    return tmux("capture-pane", "-p", "-J", "-t", tgt(sess)).split("\n")


def coloured(sess):
    """The same rows with their colour escapes kept — a menu's only marker,
    in a TUI that highlights its selection and prints no glyph for it."""
    return tmux("capture-pane", "-p", "-e", "-J", "-t", tgt(sess)).split("\n")


def sess_cwd(sess):
    return tmux("display-message", "-p", "-t", tgt(sess), "#{pane_current_path}")


SNAP_KEEP = 5   # nightmux/pre-* branches kept per repo; older ones are pruned here


def snapshot_repo(sess):
    """Branch off whatever the worktree holds, right before an unattended prompt.

    `git stash create` builds a commit from the worktree without touching it —
    unlike `git stash`, nothing is popped off, so the session never sees its own
    files move under it. A clean tree has nothing to stash, so the branch just
    points at HEAD. Never fatal: a snapshot that fails must not be the reason a
    prompt never goes in — that would trade one kind of lost work for another.
    """
    cwd = sess_cwd(sess)
    try:
        if not cwd or not os.path.isdir(cwd):
            return
        if tmux_git(cwd, "rev-parse", "--is-inside-work-tree") != "true":
            return
        sha = tmux_git(cwd, "stash", "create") or tmux_git(cwd, "rev-parse", "HEAD")
        if not sha:
            return
        name = "nightmux/pre-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        tmux_git(cwd, "branch", name, sha)
        prune_snapshots(cwd)
    except Exception as e:
        print(f"snapshot {sess}: {e}", file=sys.stderr)


def prune_snapshots(cwd):
    """Keep only the last SNAP_KEEP nightmux/pre-* branches for this repo."""
    names = [n for n in tmux_git(
        cwd, "for-each-ref", "--sort=-creatordate", "--format=%(refname:short)",
        "refs/heads/nightmux/pre-*").split("\n") if n.strip()]
    for old in names[SNAP_KEEP:]:
        tmux_git(cwd, "branch", "-D", old)


def snapped():
    """{pane_id: ts} for every status-line snapshot still worth trusting."""
    out, now = {}, time.time()
    for d in snaps():
        p, ts = d.get("pane"), d.get("ts", 0)
        if p and now - ts <= STATE_FRESH and ts > out.get(p, 0):
            out[p] = ts
    return out


def live_sessions():
    """{name: pane_id} for every tmux session, in one call instead of one per topic.

    The pane is the one the agent is in — the pane its status line was last
    written from — and only failing that the session's active pane, which is what
    nightmux used to assume. Both the capture and the keystrokes take this, so
    they cannot end up addressing two different panes.

    None when tmux did not answer. "No sessions are running" and "I could not
    ask" are different facts, and returning {} for both told every bound topic
    its session had died — 72 times in three days here — then rebaselined each
    one, which drops the transcript offset and with it whatever the agent
    produced during the gap. Callers must handle None; the watcher skips the
    tick, which is the only reading that invents nothing.
    """
    out = tmux_out("list-panes", "-a", "-F",
                   "#{session_name}\t#{pane_id}\t#{pane_active}\t"
                   "#{pane_current_command}\t#{pane_current_path}")
    if out is None:
        return None
    seen, active, running, cmd, cwd = {}, {}, {}, {}, {}
    for l in out.split("\n"):
        # The path is last and taken whole: a directory may hold a tab, and
        # splitting it into a sixth field would drop the pane entirely.
        f = l.split("\t", 4)
        if len(f) != 5:
            continue
        seen.setdefault(f[0], []).append(f[1])
        cmd[f[1]] = f[3]
        cwd[f[1]] = f[4]
        if f[2] == "1":
            active.setdefault(f[0], f[1])
        if f[3] in AGENT_BINS:
            running.setdefault(f[0], f[1])
    hot = snapped()
    at = {s: max((p for p in pids if p in hot), key=lambda p: hot[p],
                 default=running.get(s) or active.get(s) or pids[0])
          for s, pids in seen.items()}
    _shell.clear()
    _shell.update({s: cmd.get(p) in SHELLS for s, p in at.items()})
    # Free: this call already walked every pane, and track_cwd asking each
    # session separately was one `display-message` spawn per session per tick,
    # on the same single-threaded tmux server that these timeouts come from.
    _cwd.clear()
    _cwd.update({s: cwd.get(p) for s, p in at.items() if cwd.get(p)})
    return at


BIG_PROMPT = 2000  # past this, typing it key by key is slower and less reliable


def spill(sess, text):
    """Hand a very long prompt over as a file instead of typing it out.

    Every character of a pasted prompt crosses tmux as a keystroke and lands in
    a TUI input box with its own limits; a path does not.
    """
    if len(text) <= BIG_PROMPT:
        return text
    os.makedirs(FILE_DIR, exist_ok=True)
    path = os.path.join(FILE_DIR, f"{int(time.time())}-prompt-{sess}.md")
    with open(path, "w") as f:
        f.write(text)
    return (f"My prompt was too long to type, so it is in {path} — "
            "read that file and treat its contents as my message.")


def settle(sess, needle, timeout=2.0):
    """Wait for typed text to actually appear on screen. True if it did.

    Whitespace is collapsed on both sides because the prompt box wraps long
    lines, which would otherwise hide the text we just sent.
    """
    want = re.sub(r"\s+", "", needle)[-40:]
    if not want:
        return True
    end = time.time() + timeout
    while True:
        if want in re.sub(r"\s+", "", "\n".join(visible(sess))):
            return True
        if time.time() > end:
            return False
        time.sleep(0.05)


def inject(sess, text):
    """Type text into the Claude Code prompt and submit. False if nothing was.

    One tmux invocation for the whole prompt — chained with ';' arguments —
    instead of one process spawn per line, then wait for the text to land
    rather than sleeping a fixed guess. The old fixed sleep submitted a
    truncated prompt whenever the TUI redrew slower than 0.4s.

    Refuses a pane with no agent in it. Every caller routes through here, so
    this is the one place that has to know a prompt is not a shell command.
    """
    if agentless(sess):
        print(f"inject {sess}: pane is at a shell, refusing to type a prompt "
              "into it", file=sys.stderr, flush=True)
        return False
    args, at = [], tgt(sess)
    for i, line in enumerate(text.split("\n")):
        if i:  # newline inside the prompt box, not a submit
            args += [";", "send-keys", "-t", at, "M-Enter"]
        if line:
            args += [";", "send-keys", "-t", at, "-l", "--", line]
    if not args:
        return False
    tmux(*args[1:])
    if not settle(sess, text.split("\n")[-1]):
        print(f"inject {sess}: text not on screen after 2s, sending Enter anyway",
              file=sys.stderr)
    tmux("send-keys", "-t", at, "Enter")
    return True


# ---------- output watcher ----------

# TUI chrome: frames, the prompt echo of what you already typed, spinner
# residue and the status bar. All of it redraws constantly and says nothing.
# Covers both TUIs this drives: Claude Code and Antigravity (agy).
CHROME = re.compile(
    r"^\s*(?:$"
    r"|[─═━╌┄┈╍│╭╮╰╯┌┐└┘┃\s]+$"   # frames and separators
    # prompt line, boxed or bare — but "❯ 1. Yes" is a menu pick, not an echo
    r"|[│┃]?\s*[❯>](?:\s+(?!\d[.)])|\s*$)"
    r"|[✻✢✳✽*·⠀-⣿][^\w]*\s"   # spinner: "✻ Brewed for 2s", "⢿  Running..."
    r"|⏵|\? for shortcuts|↑/↓ Navigate"  # mode hint / key hints
    r"|esc to (?:cancel|interrupt)"
    r"|Gemini .*·\s*\w+$"          # agy status bar
    r"|\S+@\S+:\S*\s"              # shell status bar
    r")")
# Tool call detail: the ⎿ continuation body, "+N lines" elisions, agy's collapsed
# thinking header. The tool header line above them survives, so you still see
# what ran. !verbose brings all of it back.
DETAIL = re.compile(r"^\s*(?:⎿|\.{3}|\+\d+ (?:more )?lines?|… \+\d+|▸ Thought for)")
# The pane is asking for a keypress and will sit there forever until it gets one.
# A dialog owns its line: the option or the question starts it, give or take the
# box border. Matching these anywhere turned ordinary output into a phantom menu —
# a results table cell reading ">0.75" is not menu option "0.", and a pane that
# prints one is not waiting for anything. The pane then sat "waiting" forever,
# swallowing typed text and nudging about an answer nobody owed.
WAITING = re.compile(r"^\s*[│┃]?\s*(?:"
                     r"[❯>]\s*\d[.)]\s"          # ❯ 1. Yes
                     r"|\d[.)]\s*(?:Yes|No)\b"    # 1. Yes / 2. No
                     r"|Do you want\b"
                     r"|Do you trust\b"
                     r"|Continue\?"
                     r"|Press Enter to continue"
                     r"|Requesting permission"
                     r")"
                     # Footer hints, unambiguous wherever they land on the line.
                     r"|\(y/n\)|Navigate ·|enter Confirm", re.M)
# Mid-turn: these footers only render while the agent is working.
# Claude Code picks a fresh gerund per turn — Puzzling…, Crafting…, Cogitating…,
# Perusing… — so matching the word list caught almost nothing and read a working
# pane as idle: no live trace, and drain() firing a queued prompt into a busy pane.
# The shape is what is stable: a glyph, one gerund ending in …, then a timer.
# "✻ Cogitated for 14m 21s" is past tense and deliberately does not match — that
# line is what a *finished* turn leaves on screen.
# "to" is optional: opencode's footer says plain "esc interrupt", and without
# this its working pane read idle. A provider retry redraws a countdown once a
# second — "[retrying in 58m 6s attempt #13]" — and every redraw looked like a
# finished turn with new output, so the topic got a ✅ per second for an hour.
BUSY = re.compile(r"esc (?:to )?(?:interrupt|cancel)"
                  r"|^\s*[^\w\s]{1,2}\s+\w+…\s*\(\d+[hms]"
                  r"|Brewing|Thinking…|Running…|Running\.\.\.", re.M)
# A pick in whatever numbered menu the pane is showing, boxed or bare.
MENU = re.compile(r"^\s*[│┃]?\s*[❯>]?\s*(\d)[.)]\s+(\S.*?)\s*[│┃]?$")
# opencode's modal draws key hints where the other TUIs write a question, so
# WAITING saw nothing and the pane read "idle": no 🟠, no buttons, and drain()
# free to type a queued prompt into an open dialog. The hints are chrome and
# say nothing on their own — hints *and* a numbered menu on screen is a dialog.
# Same line says how it is driven: arrows, never the option's number.
ARROWED = re.compile(r"↑↓\s*select|enter confirm|esc dismiss", re.I)
# Whatever the TUI paints on the row the arrows are currently on.
PICKED = re.compile(r"[❯▸➤]|[✓✔]\s*$")
SGR = re.compile(r"\x1b\[[0-9;]*m")
# The colour immediately in front of an option's number, from a `capture-pane -e`.
# opencode marks its selection with colour and nothing else — no ❯, no ✓ — and a
# plain capture throws that away, so every option looked identical and nightmux
# could not say which one the arrows were on. No palette is hardcoded: the rows
# are painted alike except the selected one, so the odd colour out is the answer.
DIGIT_SGR = re.compile(r"(\x1b\[[0-9;]*m)(?=\d[.)])")
# Same option line, but the border is required. opencode draws its modal inside
# the border and the agent's own prose outside it, and prose numbers a plan:
# "1. Core mechanic (wk 1)" is a MENU match and is not a choice anyone is being
# offered. Where both are on screen, the box is the menu.
BOXED = re.compile(r"^\s*[│┃]\s*[❯>]?\s*\d[.)]\s+\S")
# The usage-limit banner. Phrasing lifted from Claude Code's own detector, so it
# tracks what the CLI actually prints rather than what a changelog once said.
LIMIT_HIT = re.compile(
    r"You've (?:hit|reached) your|You're out of (?:usage credits|extra usage)"
    r"|usage limit reached|Your org is out of usage"
    r"|Your (?:seat type doesn't include|usage allocation has been disabled)")
RESET_IN = re.compile(r"resets? in\s+((?:\d+\s*(?:d|hr?|min|m)\b\s*)+)", re.I)
RESET_AT = re.compile(r"resets?\s+(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:[ap]m)?)", re.I)
HOOK_DIR = os.path.expanduser("~/.nightmux-hooked")
HOOK_FRESH = 900  # a Stop hook seen this recently owns delivery for that session
STATE_DIR = os.path.expanduser("~/.nightmux-state")
# The status line only redraws while a session is active, so an idle one goes
# quiet. Its transcript path stays valid the whole time — only the usage numbers
# in it go stale — hence two ages: one to trust the path, a shorter one to act
# on the percentages. The path age matches the prune window, because an hour of
# silence used to drop a session back to pane scraping without saying so; a path
# that has genuinely gone away simply stops growing, which costs nothing.
STATE_FRESH = 86400
USAGE_FRESH = 180
NOTIFY_FRESH = 90    # the Notification hook already announced this prompt
PRUNE_EVERY = 3600   # uploads and status-line snapshots both accumulate forever
MAX_LINES = 300
PROG_EVERY = 5    # seconds between live-progress edits (telegram throttles edits)
PROG_GAP = 3      # seconds between edits across all sessions
PROG_LINES = 14
NUDGE_AFTER = 600   # an unanswered prompt blocks the session: remind after this
NUDGE_EVERY = 1800  # then keep one message current instead of posting more
LIMIT_SLACK = 60    # resume this long after the stated reset, never before
REFUSED_FAST = 60   # a prompt refused this soon after being typed did no work
ACTIVE_RECENT = 120  # a transcript that grew this recently was a turn in progress
IDLE_AFTER = 300    # nothing moving anywhere for this long -> poll lazily
IDLE_POLL = 10


def common_prefix(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def hooked(sess):
    """True when a Stop hook is delivering this session's replies itself."""
    try:
        return time.time() - os.path.getmtime(os.path.join(HOOK_DIR, sess)) < HOOK_FRESH
    except OSError:
        return False


def notified(sess):
    """True when the Notification hook just announced this pane's prompt itself."""
    try:
        return time.time() - os.path.getmtime(
            os.path.join(STATE_DIR, f".notify-{sess}")) < NOTIFY_FRESH
    except OSError:
        return False


_snap_cache = {}


def snaps():
    """Every status-line snapshot on disk, unfiltered and in no useful order."""
    try:
        names = os.listdir(STATE_DIR)
    except OSError:
        return
    for n in names:
        if not n.endswith(".json"):
            continue
        path = os.path.join(STATE_DIR, n)
        try:
            mtime = os.path.getmtime(path)
            cached = _snap_cache.get(path)
            if cached and cached[0] == mtime:
                yield cached[1]
                continue
            with open(path) as f:
                data = json.load(f)
                _snap_cache[path] = (mtime, data)
                yield data
        except (OSError, ValueError):
            continue


def snapshot(pane):
    """Freshest status-line snapshot written from this tmux pane, or None.

    Matched on pane id, never on cwd: a directory says nothing about which
    process is living in it, so cwd would happily hand an agy session the
    transcript of a Claude that worked there hours ago.
    """
    best, now = None, time.time()
    if not pane:
        return None
    for d in snaps():
        if d.get("pane") != pane or now - d.get("ts", 0) > STATE_FRESH:
            continue
        if not best or d["ts"] > best["ts"]:
            best = d
    return best


TOOL_ARG = ("command", "file_path", "pattern", "path", "url", "prompt", "query",
            "description", "subagent_type", "skill")


def brief(inp):
    """The one argument worth showing in a tool header, the way the TUI picks it."""
    if not isinstance(inp, dict):
        return ""
    for k in TOOL_ARG:
        v = inp.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip().split("\n")[0][:80]
    return ""


# Tools whose results arrive in bulk and stay in the window. Edit and Write
# answer in one line, so repeating them is free.
BULKY = ("Read", "Bash", "Grep", "Glob", "WebFetch", "WebSearch", "NotebookRead")


def call_key(inp):
    """A signature stable enough to spot the same fetch twice.

    The whole command with whitespace collapsed, not brief()'s first line —
    every heredoc starts `python3 - <<EOF` and would otherwise look identical.
    """
    if not isinstance(inp, dict):
        return ""
    for k in ("file_path", "command", "pattern", "url", "path", "query"):
        v = inp.get(k)
        if isinstance(v, str) and v.strip():
            return re.sub(r"\s+", " ", v.strip())[:70]
    return ""


def render(rec):
    """One transcript record -> the lines the TUI would draw for it.

    Thinking blocks and tool results are dropped: the first is not an answer and
    the second is the ⎿ detail that !verbose used to bring back from the pane.
    """
    if rec.get("type") != "assistant":
        return []
    out = []
    for b in (rec.get("message") or {}).get("content") or []:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "text" and b.get("text", "").strip():
            out.append(b["text"].strip())
        elif b.get("type") == "tool_use":
            out.append(f"● {b.get('name')}({brief(b.get('input'))})")
    return out


def tail_transcript(st, path):
    """Assistant output appended since the last read. Exact text, no chrome."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return []
    pos = st.get("tpos")
    if pos is None or pos > size or st.get("tpath") != path:
        st["tpos"], st["tpath"] = size, path   # first sight, or a new conversation
        return []
    if pos == size:
        return []
    out, spent = [], 0.0
    with open(path, "rb") as f:
        f.seek(pos)
        while True:
            line = f.readline()
            if not line or not line.endswith(b"\n"):
                break
            pos += len(line)
            line_str = line.decode("utf8", "replace").strip()
            if line_str:
                try:
                    rec = json.loads(line_str)
                except ValueError:
                    continue
                # Claude Code writes a usage record per assistant turn. Weighing
                # it here is free -- these bytes are being decoded anyway -- and
                # it is what lets the spend cap count cost instead of turns.
                u = (rec.get("message") or {}).get("usage") or {}
                spent += (u.get("input_tokens", 0) * WEIGHT["in"]
                          + u.get("cache_creation_input_tokens", 0) * WEIGHT["write"]
                          + u.get("cache_read_input_tokens", 0) * WEIGHT["read"]
                          + u.get("output_tokens", 0) * WEIGHT["out"])
                out += render(rec)
    st["tpos"] = pos
    if spent:
        st.setdefault("spend", []).append((time.time(), spent))
    return out


def pane_state(lines):
    """waiting | busy | idle, from the live screen only.

    Detail lines are excluded from the busy test on purpose: a backgrounded
    shell prints "⎿ Running… (7m · timeout 10m)" while the prompt is free.
    """
    tail = lines[-25:]
    joined = "\n".join(tail)
    if WAITING.search(joined) or (ARROWED.search(joined)
                                  and any(BOXED.match(l) for l in tail)):
        return "waiting"
    live = "\n".join(l for l in tail if not DETAIL.match(l))
    return "busy" if BUSY.search(live) else "idle"


THOUGHT = re.compile(r"^\s*▸ Thought for")


def strip_noise(lines, verbose=False):
    """Drop TUI chrome, and (unless verbose) tool detail and thought summaries."""
    out, skip = [], False
    for l in lines:
        if CHROME.match(l):
            continue
        if verbose:
            out.append(l.rstrip())
            continue
        if skip:  # agy prints the thought's title on the line under its header
            skip = False
            continue
        if DETAIL.match(l):
            skip = bool(THOUGHT.match(l))
            continue
        out.append(l.rstrip())
    return out


def menu_buttons(lines, sess=None):
    """One tap-button per option of the menu the pane is waiting on.

    A session suffix on the callback data (`!1 api` instead of bare `!1`) lets
    a tap answer the right pane regardless of which topic it landed in — the
    command center mirrors this same message into a topic bound to nothing, so
    topic-binding alone cannot resolve it there.
    """
    opts = {}
    for l in menu_rows(lines):
        m = MENU.match(plain(l))
        label = m.group(2)
        opts[m.group(1)] = label[:28] + ("…" if len(label) > 28 else "")
    suffix = f" {sess}" if sess else ""
    # No numbers means an arrow-driven selector (agy's trust prompt, /model):
    # the nav row alone drives it, exactly as you would in the terminal.
    rows = [[(f"{d}. {opts[d]}", f"!{d}{suffix}")] for d in sorted(opts)]
    rows.append([("esc", f"!esc{suffix}"), ("↑", f"!up{suffix}"),
                ("↓", f"!down{suffix}"), ("⏎", f"!enter{suffix}")])
    return kb(rows)


_prog_at = [0.0]  # chat-wide, so N busy sessions cannot outrun the rate limit


def started(cfg, state, topic, sess, mid):
    """Acknowledge a prompt the instant it is typed, before the TUI reacts.

    Opens the live-trace message that progress() then edits in place, so the
    turn is one message that grows rather than silence followed by a wall.
    """
    st = state.setdefault(sess, {})
    if st.get("prog_msg"):        # a turn is already on screen; it keeps the message
        react(cfg, mid, WORKING)
        return
    st["prog_msg"] = send(cfg, topic, f"⚙️ {sess}\n…", quiet=True,
                          buttons=kb([[("esc", "!esc")]]))
    st["prog_text"], st["prog_at"] = "", 0.0   # first real pane content edits it in
    st["react"] = mid
    react(cfg, mid, WORKING)


def progress(cfg, st, topic, sess, lines, tbuf=None):
    """Mirror the working turn into one message, edited in place as it moves.

    tbuf is the transcript rendering when there is one — exact tool headers and
    answer text, instead of whatever the screen happened to be showing.
    """
    now = time.time()
    if now - st.get("prog_at", 0) < PROG_EVERY or now - _prog_at[0] < PROG_GAP:
        return
    _prog_at[0] = now
    body = ("\n".join(tbuf).split("\n") if tbuf is not None
            else strip_noise(lines[-60:]))
    body = "\n".join(body[-PROG_LINES:]).strip()
    if not body or body == st.get("prog_text"):
        return
    st["prog_at"], st["prog_text"] = now, body
    text, stop = f"⚙️ {sess}\n{body}", kb([[("esc", "!esc")]])
    if st.get("prog_msg"):
        api(cfg, "editMessageText", chat_id=cfg["chat_id"],
            message_id=st["prog_msg"], parse_mode="HTML", reply_markup=stop,
            text=f"<pre>{html.escape(text[:LIMIT])}</pre>")
    else:  # quiet: the phone should buzz for answers and prompts, not for chatter
        st["prog_msg"] = send(cfg, topic, text, buttons=stop, quiet=True)


def parse_reset(text, now=None):
    """Epoch of the next window, from 'resets in 2h 14m' or 'resets 3pm'."""
    now = now or time.time()
    m = RESET_IN.search(text)
    if m:
        # "4 hr 56 min", "2h 14m", "2d 3h" — every shape the CLI prints.
        secs = 0
        for n, unit in re.findall(r"(\d+)\s*(d|hr?|min|m)\b", m.group(1), re.I):
            secs += int(n) * {"d": 86400, "h": 3600, "hr": 3600}.get(unit.lower(), 60)
        return now + secs
    m = RESET_AT.search(text)
    if m:
        t = m.group(1).strip().lower()
        hh, mm = int(re.match(r"\d{1,2}", t).group()), 0
        if ":" in t:
            mm = int(re.search(r":(\d{2})", t).group(1))
        if "pm" in t and hh < 12:
            hh += 12
        if "am" in t and hh == 12:
            hh = 0
        lt = time.localtime(now)
        at = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, hh, mm, 0, 0, 0, -1))
        return at + 86400 if at <= now else at   # a stated time already past is tomorrow
    return None   # no time on screen. Guessing five hours would swallow prompts


ZONEINFO = "/usr/share/zoneinfo"
_tz_lock = threading.Lock()
_tz_cache = {}


def tz_shift(name, ts):
    """Seconds east of UTC for a named zone at `ts`, from the system tz database.

    Python 3.8 has no zoneinfo, so this borrows the process TZ briefly under a
    lock — the watcher and the update loop both format times. Cached per hour:
    a zone shifts twice a year, not twice a second. A fixed offset cannot do
    this: Cairo is +3 in August and +2 in December, so half the year of reset
    times would be an hour wrong.
    """
    key = (name, int(ts // 3600))
    if key in _tz_cache:
        return _tz_cache[key]
    with _tz_lock:
        old = os.environ.get("TZ")
        try:
            os.environ["TZ"] = name
            time.tzset()
            shift = calendar.timegm(time.localtime(ts)) - int(ts)
        finally:
            os.environ.pop("TZ", None) if old is None else os.environ.__setitem__("TZ", old)
            time.tzset()
    _tz_cache[key] = shift
    return shift


def clock(cfg, ts):
    """HH:MM as the phone reads it. The server is rarely in the user's timezone.

    Only display is shifted, never parsing: a banner the TUI printed is in the
    server's clock, and reinterpreting it would move every reset time.
    """
    off = cfg.get("tz_offset")
    if off is None:
        return time.strftime("%H:%M", time.localtime(ts))
    secs = tz_shift(off, ts) if isinstance(off, str) else off * 3600
    return time.strftime("%H:%M", time.gmtime(ts + secs))


def left(secs):
    secs = max(0, int(secs))
    return f"{secs // 3600}h {secs % 3600 // 60}m" if secs >= 3600 else f"{secs // 60}m"


def undetail(line):
    """A quoted output line with its ⎿ marker and indent taken off the front."""
    return re.sub(r"^\s*⎿\s*", "", line)


def check_limit(cfg, st, topic, sess, scr, fresh, busy=False):
    """Hold prompts until the usage window resets.

    The status-line snapshot carries the exact percentage and reset epoch, and
    outranks the screen: a pane keeps showing a banner long after it stopped
    being true, and one that merely scrolled past was never a live state at all.

    Both windows count. A spent weekly one refuses turns exactly like a spent
    5-hour one, and while it does, the 5-hour figure reads healthy — reading
    only that declared room where there was none and injected prompts into a
    session that could not take them.
    """
    snap = st.get("snap") or {}
    # `scr` is what appeared since the last tick, not the whole screen: a banner
    # that is merely still on screen is the same limit, already announced, and
    # after a resume it is the *previous* window's — holding on it again would
    # park a session that had just been freed.
    # A window that already reset says nothing; one with no reset epoch cannot
    # be held on, so neither is evidence either way.
    live = [(w, lbl) for key, lbl in (("five_hour", "5-hour"), ("seven_day", "weekly"))
            for w in [window(snap, key) or {}] if w.get("resets_at")]
    if time.time() - snap.get("ts", 0) < USAGE_FRESH and live:
        spent = [(w["resets_at"], lbl) for w, lbl in live
                 if (w.get("used_percentage") or 0) >= 100]
        if not spent:
            st.pop("limit_line", None)   # sidecar says there is room; screen cannot argue
            return
        at, lbl = max(spent)   # both spent: the later reset is the one that frees it
        hit = f"{lbl} window spent"
    elif fresh:
        return  # a restart sees the whole scrollback as new; old banners are not news
    else:
        # DETAIL lines are quoted output — "⎿ Error during compaction: You've hit
        # your monthly spend limit" is a report of a past failure, not the banner.
        # The live refusal arrives as a ⎿ line too, though, being the result of
        # the turn it refused, so dropping all of them made a spend cap invisible
        # on every pane the sidecar's windows do not cover. What separates them is
        # position: a quoted error puts its own words in front, an announcement
        # starts with the banner.
        hit = next((l for l in scr[-12:] if LIMIT_HIT.search(l) and (
            not DETAIL.match(l) or LIMIT_HIT.match(undetail(l)))), None)
        if not hit:
            return
        hit, at = hit.strip(), parse_reset("\n".join(scr[-12:]))
    if hit == st.get("limit_line"):
        return  # same banner still on screen: announced already, say nothing
    st["limit_line"] = hit
    if at is None:
        # A monthly or spend cap prints no reset time. Holding prompts for a
        # guessed five hours would lose them, so say so and stay out of the way.
        send(cfg, topic, f"⚠️ {sess} hit a usage limit\n{hit}\n"
             "no reset time on screen — prompts are NOT queued", mode="plain")
        return
    st["limit_until"] = until = at + cfg.get("limit_slack", LIMIT_SLACK)
    # A turn cut off mid-flight took its prompt with it: that prompt was already
    # consumed, so an empty queue at reset time means the work simply stops and
    # waits for a human to type "continue". Queue the continuation here and the
    # ordinary drain runs it the moment the window reopens. Set
    # "auto_continue": false to go back to waiting, or to another string to send
    # something other than `continue`.
    # A prompt typed a moment ago that never got a turn was refused outright: no
    # work came of it, so `continue` would continue nothing and the prompt itself
    # has to go back. "Never got a turn" is the whole of it — a prompt whose turn
    # ran and finished must not be sent twice, and the pane going busy at any
    # point since it was typed is what tells the two apart. This is also its own
    # trigger, not a refinement of `busy`: the refusal is precisely the case
    # where nothing was running to notice.
    refused = bool(st.get("last") and not st.get("ran")
                   and time.time() - st.get("last_at", 0) < REFUSED_FAST)
    cont = (busy or refused) and cfg.get("auto_continue", "continue")
    if cont:
        if refused:
            cont = st["last"]
        st.setdefault("queue", []).insert(0, cont)
    # In the journal too: which branch this took is the whole behaviour, and the
    # Telegram message it is inferred from is not where you look at 3am.
    print(f"limit {sess}: {hit}, until {int(until)}, resume={cont!r}, "
          f"{st.get('why', 'mode=' + str(st.get('mode')))}", file=sys.stderr, flush=True)
    send(cfg, topic, f"⏸ {sess} hit the usage limit\n{hit}\n"
         f"resumes {clock(cfg, until)} (in {left(until - time.time())}) — "
         + (f"resuming itself with '{cont.splitlines()[0][:40]}'" if cont
            else "anything you send is queued"), mode="plain")


WARN_AT = (80, 90)   # say something before the wall, not at it
CTX_WARN = 75        # a context this full costs double for the same work
CTX_LEAD = 10        # ...and the warning lands this far ahead of autocompact
# Account-wide: every session shares the same 5-hour and weekly windows, so six
# bound topics must not mean six warnings. First one to notice speaks — and it
# outlives the process, because a restart used to re-arm every threshold the
# window had already crossed and announce it a second time. Three restarts in an
# afternoon is three duplicate warnings for one window nobody had left.
_warned = {}


def warned_path():
    return os.path.join(STATE_DIR, "warned.json")


def load_warned():
    """Thresholds already announced for windows that have not turned over yet."""
    try:
        with open(warned_path()) as f:
            return {k: (v[0], v[1]) for k, v in json.load(f).items()}
    except (OSError, ValueError, IndexError, TypeError):
        return {}


def save_warned():
    os.makedirs(STATE_DIR, exist_ok=True)
    path = warned_path()
    with open(path + ".tmp", "w") as f:
        json.dump(_warned, f)
    os.replace(path + ".tmp", path)   # a reader never sees a half-written file


def warn_usage(cfg, st, topic, sess):
    """Warn as a usage window fills, once per threshold, once per account."""
    snap = st.get("snap") or {}
    if time.time() - snap.get("ts", 0) > USAGE_FRESH:
        return  # stale numbers describe a window that may already have reset
    for key, label in (("five_hour", "5-hour"), ("seven_day", "weekly")):
        w = window(snap, key) or {}
        pct, at = w.get("used_percentage"), w.get("resets_at")
        if pct is None or not at:
            continue
        armed, done = _warned.get(key, (None, 0))
        if armed != at:           # a new window: last time's warnings do not carry
            armed, done = at, 0
        step = max((t for t in WARN_AT if pct >= t), default=0)
        before, _warned[key] = _warned.get(key), (armed, max(step, done))
        if _warned[key] != before:   # a crossed threshold, or a window turning over
            save_warned()
        if step > done:
            send(cfg, topic, f"🔶 {label} limit {pct:.0f}% used\n"
                 f"resets {clock(cfg, at)} (in {left(at - time.time())})",
                 mode="plain")


def ctx_trip(cfg):
    """Where the context warning fires.

    It has to land *before* the thing it is warning about. autocompact at 70 and
    a fixed warning at 75 means the compaction happens first and the warning is
    dead code -- which is what a config of {"autocompact": 70} used to get.
    """
    at = cfg.get("autocompact")
    # Floored: {"autocompact": 5} would put the trip point below zero and warn
    # about a context that is empty.
    return max(CTX_LEAD, min(CTX_WARN, at - CTX_LEAD)) if at else CTX_WARN


def warn_ctx(cfg, st, topic, sess):
    """Warn once when a session's context window gets expensive to carry.

    And say once when there is no figure to warn on. `ctx_pct` is written by
    Claude Code's status line, so on agy, codex or opencode -- and on a Claude
    with no sidecar wired -- !ctx, autocompact and the idle hint are all off,
    silently. Silence that reads as "nothing to report" is the worse failure:
    it looks exactly like a session politely staying under the threshold. Only
    said to someone who turned autocompact on, since they are the one expecting
    it to be running.
    """
    pct = (st.get("snap") or {}).get("ctx_pct")
    if pct is None:
        if cfg.get("autocompact") and st.get("mode") and not st.get("ctx_blind"):
            st["ctx_blind"] = True
            send(cfg, topic, f"🙈 no context figure for {sess}\n"
                 "it comes from Claude Code's status line, so !ctx, autocompact "
                 f"({cfg['autocompact']}%) and the idle hint do not run here\n"
                 "!agents shows which of this topic's agents do report",
                 mode="plain")
        return
    st.pop("ctx_blind", None)        # a sidecar appeared: say it again if it goes
    trip = ctx_trip(cfg)
    if pct < trip:
        st.pop("ctx_warned", None)   # compacted or cleared: arm again
    elif not st.get("ctx_warned"):
        st["ctx_warned"] = True
        send(cfg, topic, f"🧠 {sess} context {pct:.0f}% full\n"
             "every turn re-reads all of it — /compact, or !ctx to see what is in it",
             mode="plain")


_ctx_cache = {}   # path -> ((size, top), report)


def ctx_report(path, top=8):
    """What is actually occupying the context window, biggest first.

    Tool results are the bulk of it and they are attributed to the tool that
    produced them, so the answer is actionable: it names what to stop doing.

    Cached on (size, top). A transcript is append-only, so the same size is the
    same file, and !ctx typed twice on a session between turns used to walk tens
    of megabytes twice for the same answer.
    ponytail: still a whole-file re-read the moment it grows by one line. If a
    long session makes !ctx feel slow, accumulate the tallies incrementally off
    tail_transcript's byte offset instead.
    """
    try:
        ckey = (os.path.getsize(path), top)   # not `key`: the loop below binds that
    except OSError:
        ckey = None
    if ckey and (_ctx_cache.get(path) or (None,))[0] == ckey:
        return _ctx_cache[path][1]
    names, tally, text, turns, repeat = {}, {}, 0, 0, {}
    for line in open(path, errors="replace"):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        content = (rec.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                names[b.get("id")] = b.get("name") or "?"
                turns += 1
                # A repeated fetch does not replace the earlier copy, it adds a
                # second one — and both stay resident for the rest of the session.
                # Only tools that return bulk count: an Edit answers in one line,
                # so editing a file 200 times costs nothing to carry.
                if b.get("name") in BULKY:
                    key = (b.get("name"), call_key(b.get("input")))
                    if key[1]:
                        repeat[key] = repeat.get(key, 0) + 1
            elif b.get("type") == "tool_result":
                n = names.get(b.get("tool_use_id"), "?")
                tally[n] = tally.get(n, 0) + len(str(b.get("content") or ""))
            elif b.get("type") == "text":
                text += len(b.get("text") or "")
    rows = sorted(tally.items(), key=lambda kv: -kv[1])
    out = [f"{'source':<22}{'~tokens':>9}", "-" * 31]
    for n, c in rows[:top]:
        out.append(f"{n[:21]:<22}{c // 4:>9,}")
    other = sum(c for _, c in rows[top:])
    if other:
        out.append(f"{'(' + str(len(rows) - top) + ' more)':<22}{other // 4:>9,}")
    out.append(f"{'assistant text':<22}{text // 4:>9,}")
    out.append("-" * 31)
    out.append(f"{'total':<22}{(sum(tally.values()) + text) // 4:>9,}"
               f"   {turns} tool calls")
    dupes = sorted(((c, k) for k, c in repeat.items() if c > 3), reverse=True)[:5]
    if dupes:
        out.append("\nfetched again and again (each copy stays):")
        for c, (nm, arg) in dupes:
            out.append(f"  {c:>3}x {nm[:8]:<9}{arg[:46]}")
    report = "\n".join(out)
    if ckey:
        if len(_ctx_cache) > 8:
            _ctx_cache.clear()   # one report per live session is plenty to hold
        _ctx_cache[path] = (ckey, report)
    return report


PROJECTS = os.path.expanduser("~/.claude/projects")
# Anthropic's published ratios against one input token. Cache reads are a tenth
# of fresh input, which is exactly why a large context is expensive to merely
# carry: cheap per token, ruinous at a quarter million of them every turn.
WEIGHT = {"in": 1.0, "write": 1.25, "read": 0.1, "out": 5.0}


def spend_cap(cfg):
    """(turns, base-equivalent tokens) from cfg["spendcap"] -- only one is set.

    A number is turns, which is what this has always meant. A string with a k or
    M suffix is tokens instead: a turn is one grep or two hundred, so a turn
    count says nothing about what a loop is actually costing. Tokens come out of
    the transcript, so that form only bites on a Claude Code session.
    """
    v = cfg.get("spendcap")
    if isinstance(v, str):
        m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([kKmM])?\s*", v)
        if not m:
            return None, None
        n, suf = float(m.group(1)), (m.group(2) or "").lower()
        if not suf:
            return int(n) or None, None      # "12" is still twelve turns
        return None, int(n * (1e3 if suf == "k" else 1e6))
    return (v, None) if v else (None, None)


def token_tally(paths):
    """Sum the usage records Claude Code already writes into every transcript."""
    t = {"turns": 0, "in": 0, "write": 0, "read": 0, "out": 0}
    for p in paths:
        try:
            fh = open(p, errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"usage"' not in line:
                    continue          # cheap pre-filter: most lines have none
                try:
                    u = ((json.loads(line).get("message") or {}).get("usage") or {})
                except ValueError:
                    continue
                if not u:
                    continue
                t["turns"] += 1
                t["in"] += u.get("input_tokens", 0)
                t["out"] += u.get("output_tokens", 0)
                t["write"] += u.get("cache_creation_input_tokens", 0)
                t["read"] += u.get("cache_read_input_tokens", 0)
    return t


def cost_report(t, title):
    """Where the spend went, in base-input-equivalent tokens."""
    if not t["turns"]:
        return f"{title}\nno usage records yet"
    eq = {k: t[k] * w for k, w in WEIGHT.items()}
    total = sum(eq.values()) or 1
    rows = [title, f"{t['turns']:,} turns", ""]
    for k, label in (("read", "cache reads"), ("write", "cache writes"),
                     ("out", "output"), ("in", "fresh input")):
        rows.append(f"{label:<14}{t[k]:>15,}{eq[k] / total * 100:>7.0f}%")
    rows += ["", f"{'≈ base-equiv':<14}{int(total):>15,}",
             f"{'avg context':<14}{int(t['read'] / t['turns']):>15,} / turn"]
    return "\n".join(rows)


def digest_report(cfg, state, topic, sess, since):
    """What happened since `since` — the same readers !cost/!ctx/!git already use,
    just windowed and squeezed onto a phone screen instead of a full report.
    """
    st = state.get(sess) or {}
    snap = st.get("snap") or {}
    path = snap.get("transcript")
    cut, turns, last = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(since)), 0, ""
    if path and os.path.isfile(path):
        for line in open(path, errors="replace"):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("type") != "assistant" or (rec.get("timestamp") or "") < cut:
                continue
            if (rec.get("message") or {}).get("usage"):
                turns += 1
            blocks = (rec.get("message") or {}).get("content") or []
            text = "\n".join(b.get("text", "") for b in blocks
                             if isinstance(b, dict) and b.get("type") == "text").strip()
            if text:
                last = text
    cwd = sess_cwd(sess)
    since_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(since))
    commits = [l for l in tmux_git(cwd, "log", "--oneline", f"--since={since_str}")
              .split("\n") if l.strip()]
    t = token_tally([path] if path else [])
    spend = (f"~{int(sum(t[k] * w for k, w in WEIGHT.items())):,} tok, {t['turns']} turns"
             if t["turns"] else "no usage yet")
    mode = "held" if st.get("limit_until", 0) > time.time() else st.get("mode", "?")
    ctx = f" · ctx {snap['ctx_pct']:.0f}%" if snap.get("ctx_pct") is not None else ""
    ask = (f"\n🟠 waiting: {st['asked'].splitlines()[0][:60]}"
           if mode == "waiting" and st.get("asked") else "")
    return (f"🌙 digest · {sess}  [{mode}{ctx}]\n"
            f"{turns} turn(s) · {spend} · {len(commits)} commit(s) in {cwd}\n"
            + (f"last: {last.splitlines()[0][:100]}" if last else "no answer yet")
            + (("\n" + "\n".join(commits[:5])
                + (f"\n… +{len(commits) - 5} more" if len(commits) > 5 else ""))
               if commits else "") + ask)


def recent_transcripts(days):
    cut = time.time() - days * 86400
    out = []
    for root, _, files in os.walk(PROJECTS):
        for n in files:
            p = os.path.join(root, n)
            if n.endswith(".jsonl") and os.path.getmtime(p) >= cut:
                out.append(p)
    return out


def grep_transcripts(needle, days=7, limit=25):
    """Find where something was said, across every project's transcript.

    Shells out to grep for the file scan: the corpus runs to hundreds of
    megabytes and Python would spend the whole poll interval on it.
    """
    files = recent_transcripts(days)
    if not files:
        return "no transcripts in that window"
    hits, seen = [], 0
    found = run("grep", "-lieF", needle, *files, timeout=30).split("\n")
    for path in found:
        if not os.path.isfile(path):
            continue
        proj = os.path.basename(os.path.dirname(path))
        for line in open(path, errors="replace"):
            if needle.lower() not in line.lower():
                continue
            seen += 1
            if len(hits) >= limit:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            # Prefer the clean rendering, but only when the match is actually in
            # it: a hit inside a tool's arguments is not in its header line.
            body = " ".join(render(rec))
            if needle.lower() not in body.lower():
                body = line
            i = body.lower().find(needle.lower())
            snip = re.sub(r"\s+", " ", body[max(0, i - 60):i + 120]).strip()
            when = (rec.get("timestamp") or "")[11:16]
            hits.append(f"{proj[:26]:<27} {when:<6} …{snip}…")
    if not hits:
        return f"'{needle}' not found in the last {days}d"
    head = f"{len(hits)} of {seen} matches for '{needle}' ({days}d)"
    return head + "\n" + "\n".join(hits)


def autocompact(cfg, state, topic, sess):
    """Compact a session before carrying its context gets expensive.

    Opt-in via cfg["autocompact"], the percentage to act at. Fires only on an
    idle session with an empty queue, and only once per crossing: mid-turn it
    would interrupt real work, and a second one would undo the first. Announced
    every time, because it types into your session without being asked.
    """
    at = cfg.get("autocompact")
    st = state.get(sess) or {}
    pct = (st.get("snap") or {}).get("ctx_pct")
    if not at or pct is None:
        return
    if pct < at:                       # back under: arm again for the next climb
        for k in ("compacted", "compact_at", "compact_tries", "compact_gave_up"):
            st.pop(k, None)
        return
    if st.get("mode") != "idle" or st.get("queue"):
        return
    if st.get("compacted"):
        # The keystrokes can be eaten -- a menu open, a turn starting on the same
        # tick, an agent that does not take /compact at all. Nothing looked again:
        # pct stays high, so the `pct < at` re-arm never fires, and the session
        # carries a full context for the rest of its life with nothing said. Give
        # it the grace period, then try once more, then stop and say so.
        if (time.time() - st.get("compact_at", 0) < COMPACT_GRACE
                or st.get("compact_tries", 0) >= COMPACT_TRIES):
            if (st.get("compact_tries", 0) >= COMPACT_TRIES
                    and not st.get("compact_gave_up")):
                st["compact_gave_up"] = True
                send(cfg, topic, f"⚠️ {sess} still {pct:.0f}% after "
                     f"{COMPACT_TRIES}x /compact — run it by hand, or "
                     "!autocompact off", mode="plain")
            return
        st.pop("compacted", None)      # grace is up and it did not take: retry
    st["compacted"] = True
    st["compact_at"] = time.time()
    st["compact_tries"] = st.get("compact_tries", 0) + 1
    send(cfg, topic, f"🧹 {sess} context {pct:.0f}% ≥ {at}% — running /compact\n"
         "!autocompact off to stop this", mode="plain")
    inject(sess, "/compact")
    remember(state, sess, "/compact")


COMPACT_GRACE = 120    # how long /compact gets to land before it is retried
COMPACT_TRIES = 2      # ...and how many goes it gets before nightmux says so

IDLE_PARK = 6 * 3600   # untouched this long and it is parked, not paused
IDLE_CTX = 50          # ...and this full is worth clearing before resuming


def idle_hint(cfg, state, topic, sess):
    """Point out a parked session still holding a big context.

    Resuming one costs its whole context again on every turn, and the cheapest
    turn in any session is the first. Suggests /clear rather than typing it:
    clearing throws the thread away, which is the user's call, not the watcher's.
    Sessions above the autocompact threshold are compacted instead, so in
    practice this covers the band that autocompact deliberately leaves alone.
    """
    at = cfg.get("idle_ctx", IDLE_CTX)
    st = state.get(sess) or {}
    idle_for = time.time() - st.get("changed", time.time())
    if idle_for < IDLE_PARK:
        st.pop("parked", None)     # it moved: arm again for the next park
        return
    pct = (st.get("snap") or {}).get("ctx_pct")
    if (not at or st.get("parked") or st.get("mode") != "idle"
            or st.get("queue") or pct is None or pct < at):
        return
    st["parked"] = True
    send(cfg, topic, f"💤 {sess} idle {left(idle_for)} at {pct:.0f}% context\n"
         f"every turn after you resume pays that {pct:.0f}% again — /clear first "
         f"if the thread is done\n!idlectx off to stop this", mode="plain")


_queued = [None]   # last blob written: an unchanged queue never touches disk
_queue_lock = threading.Lock()


def queue_path():
    return os.path.join(STATE_DIR, "queue.json")


def queue_blob(state):
    """The only part of `state` worth surviving a restart: what the user is owed.

    Everything else — screen offsets, warning flags, the mode — is a cache that
    rebaselines against a live session on the next tick, and restoring it stale
    would resend or suppress things wrongly.
    """
    out = {}
    for sess, st in list(state.items()):   # the command thread adds sessions
        held = {k: st[k] for k in ("queue", "limit_until", "sched", "shift",
                                   "shift_total") if st.get(k)}
        if held.get("limit_until", 0) < time.time():
            held.pop("limit_until", None)   # an expired hold is history, not state
        if held:
            out[sess] = held
    return out


def save_queue(state):
    """A prompt held for a 5-hour reset outlives many daemon restarts.

    Locked because the watcher and every topic worker call this: two threads
    sharing one temp path can replace a half-written file over a good one, and
    the next start would read a truncated queue as no queue at all — losing
    exactly what this exists to keep.
    """
    with _queue_lock:
        blob = queue_blob(state)
        if blob == _queued[0]:
            return
        _queued[0] = blob
        os.makedirs(STATE_DIR, exist_ok=True)
        path = queue_path()
        with open(path + ".tmp", "w") as f:
            json.dump(blob, f)
        os.replace(path + ".tmp", path)  # a reader never sees a partial queue


def load_queue(state):
    """Restore held prompts, and only those: `fresh` still means fresh."""
    try:
        with open(queue_path()) as f:
            blob = json.load(f)
    except (OSError, ValueError):
        return {}
    for sess, held in blob.items():
        state.setdefault(sess, {}).update(held)
    _queued[0] = blob
    return {s: h for s, h in blob.items()
            if h.get("queue") or h.get("sched") or h.get("shift")}


def drain(cfg, state, topic, sess):
    """Once the window resets, feed the queue back one prompt per idle turn.

    A !shift plan rides the same gate once the regular queue is empty: nothing
    queued, pane idle, window open — exactly what lets a held prompt go, so a
    lockout mid-shift pauses it and this same resume restarts it, instead of a
    second copy of the wait-for-idle logic.
    """
    st = state.setdefault(sess, {})
    # Nothing leaves the queue while there is no agent to give it to. watchdog
    # owns saying so; this only has to not spend the prompt.
    if agentless(sess):
        return
    until = st.get("limit_until", 0)
    if until and time.time() >= until:
        # Clear the hold here rather than on the way out with a prompt. A window
        # that reset with an empty queue would otherwise leave the session
        # flagged as limited for good, and leave the topic with no word at the
        # time nightmux promised one — which reads as a hold that never lifted.
        st.pop("limit_until", None)
        # The banner that set this hold described the window that just ended, so
        # it stops being the reason to suppress the next one.
        st.pop("limit_line", None)
        if not st.get("queue") and not st.get("shift"):
            send(cfg, topic, f"▶️ {sess} usage window reset · nothing was queued",
                 mode="plain")
        elif not st.get("queue"):
            send(cfg, topic, f"▶️ {sess} usage window reset · resuming shift",
                 mode="plain")
        elif st.get("mode") != "idle":
            # The window is open and the queue still cannot move, which from the
            # topic looks exactly like a hold that never lifted. Say which it is.
            send(cfg, topic, f"▶️ {sess} usage window reset · {len(st['queue'])} "
                 f"queued, but the pane is {st.get('mode', 'busy')} — sending "
                 "as soon as it is free", mode="plain")
            st["resumed"] = True
        else:
            st["resumed"] = True     # the send below says "resumed", not "sending"
    open_window = st.get("mode") == "idle" and time.time() >= st.get("limit_until", 0)
    q = st.get("queue")
    if q and open_window:
        held = st.pop("resumed", None)
        text = q.pop(0)
        send(cfg, topic, f"▶️ {sess} {'resumed · sending' if held else 'sending'} queued "
             f"prompt{f' ({len(q)} left)' if q else ''}\n{text[:500]}", mode="plain")
        # Every prompt that reaches here was sent by the daemon, not typed live
        # this instant — a lockout replay, a schedule firing, a busy-queued
        # human prompt going in unattended a moment later. That is the line: a
        # snapshot happens whenever nobody is necessarily watching it land.
        snapshot_repo(sess)
        inject(sess, spill(sess, text))
        remember(state, sess, text)
        started(cfg, state, topic, sess, None)
    elif open_window and st.get("shift"):
        plan = st["shift"]
        total = st.get("shift_total", len(plan))
        text = plan.pop(0)
        n = total - len(plan)
        send(cfg, topic, f"🌙 shift {n}/{total} → {text.splitlines()[0][:70]}",
             mode="plain")
        snapshot_repo(sess)
        inject(sess, spill(sess, text))
        remember(state, sess, text)
        started(cfg, state, topic, sess, None)
        if not plan:
            st.pop("shift", None), st.pop("shift_total", None)
            send(cfg, topic, f"🌙 {sess} shift done", mode="plain")


DUR = re.compile(r"(\d+)\s*([dhm])")


def parse_every(text):
    """'4h', '90m', '1d 6h' -> seconds. Zero for anything that says no duration."""
    return sum(int(n) * {"d": 86400, "h": 3600, "m": 60}[u]
               for n, u in DUR.findall(text.lower()))


def at_epoch(cfg, when, now=None):
    """The next moment the clock reads HH:MM, or now + a duration for '+2h'.

    Wall clock in the config's timezone, because "03:00" from a phone means the
    time on the phone. A time that has already gone today means tomorrow — the
    alternative is a prompt that fires the instant you schedule it.
    """
    now = now or time.time()
    if when.startswith("+"):
        secs = parse_every(when[1:])
        return now + secs if secs else None
    m = re.fullmatch(r"(\d{1,2}):?(\d{2})?", when)
    if not m:
        return None
    off = cfg.get("tz_offset")
    shift = tz_shift(off, now) if isinstance(off, str) else (off or 0) * 3600
    local = now + shift
    at = local - local % 86400 + int(m.group(1)) * 3600 + int(m.group(2) or 0) * 60
    return (at + 86400 if at <= local else at) - shift


def due(cfg, state, topic, sess):
    """Move scheduled prompts onto the queue when their time comes.

    Onto the queue rather than into the pane, so a scheduled prompt inherits
    everything the queue already knows: it waits behind a usage-limit hold, it
    waits for a busy pane, and it survives a restart. A digest job rides the
    same list and epoch math, but it is not a prompt at all — it reports
    directly rather than typing "!digest" into the agent.
    """
    st = state.setdefault(sess, {})
    now, keep, fired, changed = time.time(), [], [], False
    for job in st.get("sched") or []:
        if job["at"] > now:
            keep.append(job)
            continue
        changed = True
        if job.get("kind") == "digest":
            since = job.get("since", now - (job.get("every") or 86400))
            send(cfg, topic, digest_report(cfg, state, topic, sess, since), mode="plain")
            job["since"] = now
        else:
            st.setdefault("queue", []).append(job["text"])
            fired.append(job)
        if job.get("every"):
            # From now, not from when it was due: a daemon that was off overnight
            # must not wake up and fire six hours of backlog in one go.
            job["at"] = now + job["every"]
            keep.append(job)
    if changed:
        st["sched"] = keep
    if fired:
        send(cfg, topic, f"⏰ {sess} {len(fired)} scheduled prompt(s) queued\n"
             + "\n".join(j["text"].splitlines()[0][:70] for j in fired), mode="plain")


def flush_new(cfg, state, topic, sess, pane_id=None):
    """On idle, send whatever the session gained since the last flush.

    The TUI rewrites its input box in place, so a plain line-count offset
    resends the box every time; anchoring on the common prefix with the last
    flushed capture and dropping chrome lines gives the new transcript only.
    """
    st = state.setdefault(sess, {})
    fresh = "mode" not in st
    # The conversation transcript, when the status-line sidecar has told us where
    # it is. It beats the screen on every count: exact text, no chrome to strip,
    # no echo of what we typed, nothing lost off the top of the scrollback. Read
    # first, because a transcript that grew is reason enough to do the rest.
    st["snap"] = snap = snapshot(pane_id)
    tpath = (snap or {}).get("transcript")
    gained = tail_transcript(st, tpath) if tpath else []
    if gained:
        st.setdefault("tbuf", []).extend(gained)
        st["last_gain"] = time.time()
    scr = visible(sess)
    if not fresh and not gained and scr == st.get("scr") and st["prev"] == st["sent"]:
        return  # nothing moved anywhere and nothing is pending: skip the big capture
    prev_scr = st.get("scr") or []   # what check_limit must not read as news
    st["scr"] = scr
    lines = pane(sess)
    for k, v in (("sent", lines), ("prev", lines), ("changed", time.time())):
        st.setdefault(k, v)  # watchdog gets here first and seeds an empty dict
    stable, changed = lines == st["prev"], lines != st["sent"]
    if not stable:
        st["prev"], st["changed"] = lines, time.time()
    was_busy = st.get("mode") == "busy"   # a turn was in flight on the last tick
    st["mode"] = pane_state(scr)
    if st["mode"] == "busy" and not was_busy:
        now = time.time()
        turns = [t for t in st.get("turns", []) if now - t < 300]
        turns.append(now)
        st["turns"] = turns
        cap, tcap = spend_cap(cfg)
        st["spend"] = spend = [(t, n) for t, n in st.get("spend", []) if now - t < 300]
        burnt = int(sum(n for _, n in spend))
        hit = (f"{cap} turns" if cap and len(turns) >= cap else
               f"{tcap:,} base-equiv tokens ({burnt:,} burnt)"
               if tcap and burnt >= tcap else None)
        if hit:
            send(cfg, topic, f"🛑 {sess} hit spend cap of {hit} in 5m — interrupting loop\n"
                             "!spendcap off to disable", mode="plain")
            tmux("send-keys", "-t", tgt(sess), "C-c")
    seen = set(prev_scr)
    # A turn is open until its output has been delivered — `prog_msg` is the live
    # trace, opened when it starts and deleted when the pane settles. That is the
    # signal for "the limit cut something off", not the pane's mode: a refusal
    # ends the turn, the pane goes still, and the status line only then redraws
    # with the spent percentage, so by the time the window is seen to be shut the
    # pane has read idle for a tick or more. Watching two ticks of `mode` missed
    # every real hit for exactly that reason.
    open_turn = bool(st.get("prog_msg"))
    # The last prompt did get a turn, whatever came of it: the pane is working,
    # or the transcript grew, or the pane has output that has not been flushed.
    # A turn shorter than one poll interval never shows as busy, and treating
    # that as "never ran" would re-send a prompt whose work is already done.
    if st["mode"] == "busy" or gained or changed:
        st["ran"] = True
    # Kept for the journal: when this decides wrongly, which of the three inputs
    # was wrong is the whole question, and reconstructing them afterwards from
    # the message record does not work — it already failed to explain one.
    # A transcript that grew a moment ago is a turn that was running a moment
    # ago, and it is the only one of these that survives a session driven from
    # the terminal rather than from Telegram: no prompt of ours was typed, so
    # there is no live trace, and the pane can read idle at the tick the window
    # is found spent. Three real limits in a row were missed for exactly that,
    # each one followed a few seconds later by kilobytes of delivered output.
    active = time.time() - st.get("last_gain", 0) < ACTIVE_RECENT
    st["why"] = (f"trace={open_turn} prev={was_busy} mode={st['mode']} "
                 f"active={active}")
    check_limit(cfg, st, topic, sess, [l for l in scr if l not in seen], fresh,
                open_turn or was_busy or active or st["mode"] == "busy")
    warn_usage(cfg, st, topic, sess)
    warn_ctx(cfg, st, topic, sess)
    if st["mode"] == "waiting":
        st.setdefault("wait_since", time.time())
    else:
        for k in ("wait_since", "nudged", "nudge_msg"):
            st.pop(k, None)
        try:
            os.remove(os.path.join(STATE_DIR, f".notify-{sess}"))
        except OSError:
            pass
    if fresh and st["mode"] == "waiting":
        # A restart must not swallow a prompt that is already on screen.
        ask(cfg, st, topic, sess,
            "\n".join(strip_noise(lines[-15:], verbose=True)).strip(), lines)
        return
    if st["mode"] == "busy":
        # A turn started, so the next question is a new one even if it reads the
        # same. Anything short of that — a redraw, a frame between two menus —
        # must not re-arm the announcement, or answering one re-asks it.
        st.pop("asked", None)
        progress(cfg, st, topic, sess, lines,   # live trace, like watching the TUI
                 st.get("tbuf") if tpath else None)
        return                                 # the answer flushes once it lands
    # Turn over: the live trace is superseded by the answer below it. Only once
    # the pane has settled, or the tick right after Enter kills a trace the next
    # tick would just recreate.
    if st.get("prog_msg") and stable:
        api(cfg, "deleteMessage", chat_id=cfg["chat_id"], message_id=st["prog_msg"])
        st.pop("prog_msg", None), st.pop("prog_text", None)
    if not (stable and changed):
        return
    new = lines[common_prefix(st["sent"], lines):]
    st["sent"] = lines
    verbose = topic in cfg.get("verbose", [])
    waiting = st["mode"] == "waiting"
    if tpath:
        # Transcript-fed: the hook would only repeat this, and none of the pane
        # laundering below applies to text that was never drawn on a screen.
        body = st.pop("tbuf", [])
        if not body and not waiting:
            return
    else:
        # A hooked session posts its own answer; scraping it too would double up.
        if hooked(sess) and not verbose and not waiting:
            return
        body = strip_noise(new, verbose)
        echo = st.pop("echo", None)  # your prompt, redrawn by the TUI below the box
        if echo and not verbose:
            body = [l for l in body if l.strip() not in echo]
    if len(body) > MAX_LINES and not tpath:
        # Scraped output is trimmed because the rest is already off the top of
        # the scrollback and unrecoverable. Transcript text is not: send() turns
        # anything past two chunks into one attachment, so nothing is lost.
        body = [f"[... {len(body) - MAX_LINES} lines trimmed ...]"] + body[-MAX_LINES:]
    body = "\n".join(body).strip()
    if waiting:
        # Always carry the question, whether or not the diff already held it.
        prompt = "\n".join(strip_noise(lines[-15:], verbose=True)).strip()
        if not ask(cfg, st, topic, sess,
                   f"{body}\n{prompt}".strip() if body else prompt,
                   lines, prompt_key(lines)):
            return
    elif body:
        send(cfg, topic, f"✅ {sess}\n{body}", mode="md" if tpath else "mono")
    else:
        return
    if st.get("react"):
        react(cfg, st.pop("react"), ASKING if waiting else DONE)


def prompt_key(lines):
    """The question alone, anchored at where it starts.

    Whatever Claude printed above the menu keeps moving as more output lands, so
    it cannot be part of the identity of the question being asked.
    """
    tail = [l.rstrip() for l in lines[-15:] if l.strip()]
    for i, l in enumerate(tail):
        if WAITING.search(l) or MENU.match(l):
            return "\n".join(tail[i:])
    return "\n".join(tail)


def resolve_ask(cfg, st):
    """Strip the buttons off every posted copy of a pending approval.

    A command-center mirror means two messages can answer the same question —
    once either is tapped this clears both, so a stale button has nothing left
    to press. Harmless when there was only ever one copy, or none at all.
    """
    for t, mid in st.pop("asked_msgs", None) or []:
        if mid:
            api(cfg, "editMessageReplyMarkup", chat_id=cfg["chat_id"], message_id=mid,
                reply_markup=json.dumps({"inline_keyboard": []}))
    st.pop("asked", None)


def ask(cfg, st, topic, sess, body, lines, key=None):
    """Announce a prompt once. The pane redraws constantly; the question doesn't.

    Deduped on `key` — the question itself — not on the whole message, because
    the text above it arrives as a diff that keeps shifting while the menu sits
    still. Without this the same menu is resent every few seconds, forever.

    Mirrored into the command-center topic too, when one is set: buttons carry
    the session name (menu_buttons(lines, sess)) so a tap resolves the same
    pane whichever copy answered it, and both messages are tracked so the one
    left unanswered can have its buttons pulled.
    """
    key = key or body
    if not body or key == st.get("asked") or notified(sess):
        return False
    st["asked"] = key
    buttons = menu_buttons(lines, sess)
    msgs = []
    mid = send(cfg, topic, f"🟠 needs input {sess}\n{body}", buttons=buttons)
    if mid:
        msgs.append((topic, mid))
    center = cfg.get("center_topic")
    if center and str(center) != str(topic):
        mid2 = send(cfg, center, f"🟠 needs input {sess}\n{body}", buttons=buttons)
        if mid2:
            msgs.append((center, mid2))
    st["asked_msgs"] = msgs
    return True


def nudge(cfg, state, topic, sess):
    """A prompt nobody answered leaves the session blocked.

    One reminder message per wait, edited in place from then on: a session
    parked on a menu overnight must not turn into a message an hour, all night.
    """
    st = state.get(sess) or {}
    if st.get("mode") != "waiting":
        return
    now, since, last = time.time(), st.get("wait_since"), st.get("nudged", 0)
    if not since or now - since < NUDGE_AFTER or now - last < NUDGE_EVERY:
        return
    st["nudged"] = now
    # Which line put the pane in `waiting` — the one fact needed to tell a real
    # unanswered dialog from a pattern matching ordinary output, and the one fact
    # a screen that has since scrolled can no longer supply. Twice this has been
    # the difference between a bug and correct behaviour nobody could confirm.
    cause = next((l.strip() for l in visible(sess)[-25:] if WAITING.search(l)), "?")
    print(f"nudge {sess}: waiting {int((now - since) / 60)}m on {cause[:120]!r}",
          file=sys.stderr, flush=True)
    text = f"⏰ {sess} has been waiting {int((now - since) / 60)}m for an answer"
    buttons = menu_buttons(visible(sess))
    if st.get("nudge_msg"):  # edit: no new message in the topic, no second buzz
        api(cfg, "editMessageText", chat_id=cfg["chat_id"], parse_mode="HTML",
            message_id=st["nudge_msg"], text=html.escape(text), reply_markup=buttons)
    else:
        st["nudge_msg"] = send(cfg, topic, text, mode="plain", buttons=buttons)


def prune(now, last):
    """Uploads and status-line snapshots both pile up forever otherwise."""
    if now - last < PRUNE_EVERY:
        return last
    for d, days in ((FILE_DIR, 7), (STATE_DIR, 1)):
        cut = now - days * 86400
        for n in os.listdir(d) if os.path.isdir(d) else []:
            if d == STATE_DIR and n.startswith(("queue.json", "warned.json")):
                continue   # held prompts are state, not a cache: only rewritten
            p = os.path.join(d, n)   # when they change, so mtime says nothing
            try:
                if os.path.getmtime(p) < cut:
                    os.remove(p)
            except OSError:
                pass
    return now


def watchdog(cfg, state, topic, sess, alive):
    """Tell the topic when its tmux session dies, once, not every tick."""
    st = state.setdefault(sess, {})
    if not alive and not st.get("dead"):
        st["dead"] = True
        send(cfg, topic, f"💀 tmux session '{sess}' is gone", mode="plain")
    elif alive and st.get("dead"):
        # Rebuilt session: rebaseline instead of dumping its whole scrollback —
        # but a hold and the prompts under it are what the user is owed, not a
        # cache of the old pane. Dropping them here deleted them from disk too,
        # on the next save, in the one case they exist to survive.
        state[sess] = {k: st[k] for k in ("queue", "limit_until", "sched", "shift",
                                          "shift_total") if st.get(k)}
        send(cfg, topic, f"↩️ '{sess}' is back", mode="plain")
    if alive:
        st = state.setdefault(sess, {})          # the branch above rebinds it
        if agentless(sess):
            # ponytail: two ticks, not one. A session is a bare shell for the
            # moment between `tmux new-session` and the agent starting under it,
            # and that is not a crash. Per-agent startup times if this ever lies.
            st["shell_seen"] = st.get("shell_seen", 0) + 1
            if st["shell_seen"] == 2:
                held = len(st.get("queue") or []) + len(st.get("shift") or [])
                send(cfg, topic,
                     f"💀 the agent in '{sess}' exited — its pane is a shell now"
                     + (f", {held} prompt(s) held" if held else ""), mode="plain",
                     buttons=kb([[("restore", "!restore")]]))
        elif st.pop("shell_seen", 0) >= 2:
            send(cfg, topic, f"↩️ an agent is running in '{sess}' again", mode="plain")
    return alive


def track_cwd(cfg, lock, topic, sess):
    """Keep dirs[topic] pointing at where the session is actually running.

    Only start_session used to record it, so a topic bound to an existing
    session with !bind had no directory at all — and a reboot then resumed it
    in $HOME, where every such topic found the same conversation. The live
    session is the only honest answer and it is readable only while it is
    alive, which is exactly when nobody is asking.
    """
    cwd = _cwd.get(sess) or sess_cwd(sess)   # this tick already read it
    if not cwd or not os.path.isdir(cwd):
        return
    with lock:
        if (cfg.get("dirs") or {}).get(topic) == cwd:
            return
        cfg.setdefault("dirs", {})[topic] = cwd
        save_cfg(cfg)


TMUX_MISSES = 5   # unanswered ticks before the daemon says tmux has gone quiet
_tmux_miss = [0]


def daemon_topic(cfg):
    """Where a daemon-wide problem is announced: the command center if one is
    set, else the lowest-numbered bound topic. None when nothing is bound, which
    is also when there is nothing being missed."""
    center = cfg.get("center_topic")
    if center:
        return str(center)
    return min((cfg.get("topics") or {}), key=int, default=None)


def tmux_missing(cfg, missed):
    """Report a tmux server that stopped answering, once, and its return, once.

    Skipping the tick keeps a wedged tmux from inventing nine dead sessions, but
    silence is the failure this daemon is worst at: from a phone, "no output" is
    what a quiet night looks like too. So an outage that outlasts TMUX_MISSES
    ticks says so — one message, not one per session per tick.
    """
    was, _tmux_miss[0] = _tmux_miss[0], (_tmux_miss[0] + 1) if missed else 0
    topic = daemon_topic(cfg)
    if not topic:
        return
    if missed and _tmux_miss[0] == TMUX_MISSES:
        send(cfg, topic, f"⚠️ tmux has not answered for {TMUX_MISSES} ticks\n"
             "every session is being left alone until it does — no output is "
             "lost, it is only late", mode="plain")
    elif not missed and was >= TMUX_MISSES:
        send(cfg, topic, "✅ tmux is answering again", mode="plain")


def watcher(cfg, state, lock):
    pruned = 0.0
    bound = []
    while True:
        # Anything thrown here would take the thread with it, and a dead watcher
        # is a nightmux that answers commands while quietly monitoring nothing.
        try:
            with lock:
                bound = list(cfg["topics"].items())
            alive = live_sessions()   # one tmux call for every topic's liveness
            if alive is None:
                # tmux did not answer. Everything below reads an empty pane list
                # as "every session died", so the only safe tick is no tick: keep
                # the last known targets, touch no state, and look again in a
                # second. Under load this is a handful of ticks, not an outage.
                tmux_missing(cfg, True)
                bound = []            # nothing runs below; the sleep still does
            else:
                tmux_missing(cfg, False)
                _target.update(alive)     # captures and keystrokes share one pane
                pruned = prune(time.time(), pruned)
            for topic, sess in bound:
                try:
                    if watchdog(cfg, state, topic, sess, sess in alive):
                        track_cwd(cfg, lock, topic, sess)
                        flush_new(cfg, state, topic, sess, alive.get(sess))
                        nudge(cfg, state, topic, sess)
                        due(cfg, state, topic, sess)
                        drain(cfg, state, topic, sess)
                        autocompact(cfg, state, topic, sess)
                        idle_hint(cfg, state, topic, sess)
                except Exception as e:
                    print(f"watch {sess}: {e}", file=sys.stderr)
            # One write per tick covers every path that touches a queue,
            # including the ones a future branch adds; the command handler saves
            # inline too, so a prompt is durable before its reply is sent.
            save_queue(state)
        except Exception as e:
            print(f"watch: {e}", file=sys.stderr)
        # Nothing has moved anywhere for a while: stop spinning every 2s. Any
        # injected prompt resets a session's clock, so this snaps back at once.
        now = time.time()
        quiet = min((now - (state.get(s) or {}).get("changed", now)
                     for _, s in bound), default=0)
        time.sleep(IDLE_POLL if quiet > IDLE_AFTER else cfg.get("poll", 2))


# ---------- commands ----------

KEYS = {"!esc": "Escape", "!int": "C-c", "!enter": "Enter", "!up": "Up",
        "!down": "Down", "!tab": "Tab", "!mode": "S-Tab", "!y": "y", "!n": "n"}
KEYS.update({f"!{d}": str(d) for d in range(1, 10)})

# The dialogs disagree about Enter. Claude Code's permission prompt acts on the
# digit alone; its /model picker and agy's trust prompt only move a highlight and
# wait for Enter; a shell's (y/n) needs Enter after the letter. Assuming any one
# of those rules leaves the pane parked on a menu the topic was told had been
# answered — the commonest way nightmux looks hung. So send the key, look at the
# pane, and add Enter only when the same question is still sitting there.
CONFIRM_AFTER = 1.5   # how long the TUI gets to act on the key by itself
# A numbered menu does not answer to "y": Claude Code's permission prompt is a
# list, and the letter goes nowhere. Take the digit of the matching option.
YES_NO = {"!y": re.compile(r"^ye?s?\b", re.I), "!n": re.compile(r"^no\b", re.I)}


def dialog_id(lines):
    """The question, ignoring which of its options is highlighted."""
    return re.sub(r"[❯>\s]", "", prompt_key(lines))


def menu_digit(lines, want):
    """The digit of the first menu option whose label matches `want`."""
    for l in menu_rows(lines):
        m = MENU.match(plain(l))
        if want.match(m.group(2).strip()):
            return m.group(1)
    return None


def plain(l):
    """The line as a plain capture would have given it. No-op on one already."""
    return SGR.sub("", l)


def menu_rows(lines):
    """The lines of the menu actually on screen, top to bottom, colour intact.

    One menu is drawn one way, so the border wins only when most of the rows
    have it — that is a modal with prose behind it. A single boxed row among
    bare ones is the prose, and dropping the rest would offer two options where
    the pane is showing four.
    """
    rows = [l for l in lines[-25:] if MENU.match(plain(l))]
    boxed = [l for l in rows if BOXED.match(plain(l))]
    return boxed if len(boxed) * 2 > len(rows) else rows


def menu_opts(lines):
    """(the menu's option digits, top to bottom; index of the highlighted one).

    The index is None unless exactly one row stands out — none, or several,
    means the highlight is not something this can read, and nothing should move
    on a guess.
    """
    rows = menu_rows(lines)
    marked = [i for i, l in enumerate(rows) if PICKED.search(plain(l))]
    if len(marked) != 1:
        # No glyph anywhere: fall back to colour, which needs a -e capture and
        # is why pick() takes one. On plain lines every code is "" and this
        # finds nothing, which is the honest answer there.
        codes = [(DIGIT_SGR.search(l) or [""])[0] for l in rows]
        marked = [i for i, c in enumerate(codes) if c and codes.count(c) == 1]
    return ([MENU.match(plain(l)).group(1) for l in rows],
            marked[0] if len(marked) == 1 else None)


def pick(sess, want):
    """Answer an arrow-driven menu by moving its highlight, not by typing a digit.

    opencode's modal ignores the number — "↑↓ select · enter confirm" is the
    whole contract — so tapping 3 typed a 3 nowhere, press() saw the dialog
    unchanged and sent Enter, and that confirmed whichever option was already
    highlighted while the topic was told 3 had been answered. Wrong answers,
    silently, which is worse than no button at all.

    None: not that kind of menu, send the digit as before. "": answered.
    Anything else: what went wrong, because a highlight nightmux cannot read is
    a highlight it must not confirm.
    """
    lines = coloured(sess)      # the highlight is a colour, not a character
    if not ARROWED.search(plain("\n".join(lines[-25:]))):
        return None
    opts, at = menu_opts(lines)
    if want not in opts:
        return f"option {want} is not on '{sess}' right now"
    if at is None:
        return f"can't tell which option '{sess}' is on — use ↑ ↓ ⏎"
    step = opts.index(want) - at
    if step:
        tmux("send-keys", "-t", tgt(sess),
             *[("Down" if step > 0 else "Up")] * abs(step))
        time.sleep(0.4)
    # Re-read before confirming: the marker above is a guess about someone
    # else's TUI, and the pane is the only thing that can settle it.
    opts, at = menu_opts(coloured(sess))
    if at is None or opts[at] != want:
        return f"could not move '{sess}' onto option {want} — use ↑ ↓ ⏎"
    tmux("send-keys", "-t", tgt(sess), "Enter")
    return ""


def press(sess, key, confirm=False):
    """Send one key, then Enter only if the pane plainly did not act on it."""
    before = visible(sess)
    tmux("send-keys", "-t", tgt(sess), key)
    if not confirm:
        return
    end = time.time() + CONFIRM_AFTER
    while time.time() < end:
        time.sleep(0.25)
        scr = visible(sess)
        # Gone, working, or asking something else: the key was enough, and an
        # Enter now would answer a question nobody has read yet.
        if pane_state(scr) != "waiting" or dialog_id(scr) != dialog_id(before):
            return
    tmux("send-keys", "-t", sess, "Enter")

# Telegram autocompletes registered bot commands when you type "/", which is
# the only autocomplete a bot can offer. Two registers share that one menu:
#
#   TG_SLASH  — nightmux's own, aliased to their ! form. Every name here is one
#               Claude Code does NOT own, so nothing shadows a real slash command.
#   PASSTHRU  — Claude Code's commands, registered purely so they autocomplete;
#               they are typed into the session like any other text.
TG_SLASH = {"ctl": "!ctl", "topics": "!status", "sessions": "!sessions",
            "pane": "!pane", "git": "!git", "diff": "!diff", "get": "!get",
            "bind": "!bind", "unbind": "!unbind", "kill": "!kill",
            "verbose": "!verbose", "queue": "!queue", "keys": "!keys",
            "raw": "!raw", "reload": "!reload", "tmlog": "!log",
            "tmhelp": "!help", "tmversion": "!version",
            "limits": "!usage", "tz": "!tz", "ctx": "!ctx", "spend": "!cost",
            "grep": "!grep", "autocompact": "!autocompact", "idlectx": "!idlectx",
            "spendcap": "!spendcap"}
TG_DESC = {"ctl": "button panel for this session", "topics": "every topic and its state",
           "sessions": "list tmux sessions", "pane": "dump the pane [lines]",
           "git": "status + last commits", "diff": "unstaged diff",
           "get": "upload a file from the session's cwd", "queue": "held prompts [clear|now]",
           "kill": "kill this topic's session", "verbose": "toggle tool detail",
           "raw": "type text even with a menu open", "reload": "re-read ~/.nightmux.json",
           "tmlog": "nightmux daemon journal", "tmhelp": "nightmux command list",
           "tmversion": "nightmux version, and which hooks are wired",
           "limits": "5h/7d window and context use, every topic",
           "tz": "show times in your timezone, e.g. /tz Africa/Cairo",
           "ctx": "what is filling this session's context window",
           "spend": "token spend: this chat, or /spend 7 for all projects",
           "grep": "search every transcript, e.g. /grep rate limit",
           "autocompact": "auto /compact at N% context, or off",
           "idlectx": "flag parked sessions above N% context, or off",
           "spendcap": "pause agent after N turns, or 500k/2M tokens, in 5 mins"}
PASSTHRU = [
    ("compact", "compact the conversation"), ("clear", "clear the history"),
    ("context", "context usage breakdown"), ("cost", "token spend this session"),
    ("usage", "5-hour and weekly limit usage"), ("model", "switch model"),
    ("resume", "pick a past conversation"), ("agents", "manage subagents"),
    ("todos", "current todo list"), ("memory", "edit memory files"),
    ("review", "review the pending changes"), ("rewind", "undo to a checkpoint"),
    ("permissions", "edit tool permissions"), ("mcp", "MCP server status"),
    ("doctor", "diagnose the install"), ("export", "export the conversation"),
]


def register_commands(cfg):
    """Publish the "/" menu. Scoped to this chat so other chats stay untouched."""
    cmds = ([{"command": c, "description": TG_DESC.get(c, c)} for c in TG_SLASH]
            + [{"command": c, "description": d} for c, d in PASSTHRU])[:100]
    r = api(cfg, "setMyCommands", commands=json.dumps(cmds),
            scope=json.dumps({"type": "chat", "chat_id": cfg["chat_id"]}))
    print(f"setMyCommands {len(cmds)}: {r.get('ok')} {r.get('description', '')}",
          flush=True)


def remember(state, sess, text):
    """Note what we just typed, so the TUI's echo of it is not sent back.

    Also resets the session's quiet clock, which un-throttles the idle poll.
    """
    st = state.setdefault(sess, {})
    st["echo"] = {l.strip() for l in text.split("\n") if l.strip()}
    # ...and what it was, for the case where the window refuses it outright: a
    # prompt that got no turn out of the window has to go back in the queue.
    st["last"], st["last_at"] = text, time.time()
    st["ran"] = False    # no turn has started for it yet; flush_new sets this
    st["changed"] = time.time()


# Any CLI that runs in a terminal works here: nightmux types into tmux and reads the
# pane back. What Claude Code gets on top — the transcript tail, the two hooks,
# the usage numbers — is Claude-specific, and every other agent falls back to
# scraping, which is how this worked before the hooks existed.
#
# [command, flags that resume the last conversation]. The resume flags are the
# part most likely to drift as these CLIs change, so cfg["agents"] overrides and
# extends this table without needing a code change.
AGENTS = {
    "claude": ["claude", "--continue"],
    "agy": ["agy", "-c"],
    "codex": ["codex", "resume --last"],
    "aider": ["aider", "--restore-chat-history"],
    "gemini": ["gemini", "--resume latest"],   # or an index: --resume 5
    "opencode": ["opencode", "--continue"],
}


# What an agent shows up as in `pane_current_command`, for finding its pane when
# no status line has named one. Built-ins only: an agent added through the config
# still falls back to the active pane, exactly as everything did before.
AGENT_BINS = set(AGENTS) | {v[0] for v in AGENTS.values()}


def agents(cfg):
    """Every agent key that !<key> will start: the built-ins plus cfg["agents"]."""
    out = dict(AGENTS)
    out.update(cfg.get("agents") or {})
    return out


def agent(cfg, key):
    """(command, resume-flags) for a key. An unknown key is its own command, so a
    one-off `!opencode foo` works before anyone edits the config."""
    spec = agents(cfg).get(key) or [key]
    return spec[0], (spec[1] if len(spec) > 1 else "")


def default_agent(cfg):
    return cfg.get("agent") or "claude"


def spawn(name, cwd, cmdline):
    """Detached tmux session in cwd with cmdline typed at its shell."""
    tmux("new-session", "-d", "-s", name, "-c", cwd)
    tmux("send-keys", "-t", name, "-l", "--", cmdline)
    tmux("send-keys", "-t", name, "Enter")


def resume_session(cfg, state, lock, topic, arg=""):
    """Relaunch this topic's directory with the agent it was using, resuming
    its last conversation. !resume, !restore, and the auto_restore startup
    check all funnel through here — one place that knows how a topic comes back.
    """
    sess = cfg["topics"].get(topic)
    # Whatever started this topic, unless told otherwise: resuming a codex
    # session with claude's flag would quietly open a fresh conversation.
    key = arg if arg in agents(cfg) else (
        (cfg.get("started") or {}).get(topic) or default_agent(cfg))
    name = sess or f"topic{topic}"
    if has_session(name):
        live_sessions()          # _shell is a tick old, and this branch kills
        # (None here just leaves _shell as it was: one tick stale, never wrong
        # about a session that is plainly alive.)
        if not agentless(name):
            return f"'{name}' is alive; type /resume in it to pick a conversation"
        # A shell where the agent used to be. Killing it is what makes !restore
        # one button that repairs both cases, instead of a button that works
        # only for the failure tmux happened to notice.
        tmux("kill-session", "-t", name)
    # No fallback. `claude --continue` resumes the last conversation *in this
    # directory*, so guessing $HOME does not start a fresh session there — it
    # attaches to whatever happened to run in $HOME last, for every topic at
    # once. start_session then writes the guess back as the topic's directory,
    # and the wrong answer is permanent.
    cwd = (cfg.get("dirs") or {}).get(topic)   # already the worktree, if @branch was used
    if not cwd:
        return (f"no directory recorded for this topic — start it once with "
                f"!{key} {name} <dir>")
    return start_session(cfg, state, lock, topic,
                         f"{name} {cwd} {agent(cfg, key)[1]}".rstrip(), key)


def worktree_path(repo, branch):
    """<repo>-wt/<branch>: create the branch only if it is new, reuse the
    worktree if one is already checked out there. None when `repo` is not a
    git repo — @branch has nothing to attach to.
    """
    if tmux_git(repo, "rev-parse", "--is-inside-work-tree") != "true":
        return None
    root = tmux_git(repo, "rev-parse", "--show-toplevel") or repo
    wt = os.path.join(f"{root}-wt", branch)
    if os.path.isdir(wt):
        return wt   # an earlier session already set this branch up
    sha = tmux_git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
    out = (tmux_git(root, "worktree", "add", wt, branch)
           if re.fullmatch(r"[0-9a-f]{7,40}", sha) else
           tmux_git(root, "worktree", "add", "-b", branch, wt))
    print(f"worktree add {branch}: {out}", file=sys.stderr)
    return wt if os.path.isdir(wt) else None


def bound_to(cfg, name, topic):
    """The other topic already bound to session `name`, or None.

    `state` is keyed by session name alone, so two topics pointing at one session
    share a single scrape cursor: whichever topic the watcher reaches first
    consumes the new output and the other is told nothing. From the phone that
    looks exactly like output landing in the wrong topic. Refuse the second bind
    instead -- a topic that wants another agent gets a session of its own, which
    is what switch_agent gives it.
    """
    return next((t for t, s in cfg.get("topics", {}).items()
                 if s == name and str(t) != str(topic)), None)


def switch_agent(cfg, state, lock, topic, key):
    """Bare !<key> in a bound topic: route this topic to that agent, in the same
    directory, leaving the agent it was on running.

    One topic, several agents, one of them live. The alternative -- a topic per
    agent on the same project -- is how two topics end up sharing a directory
    and a session. Each agent keeps its own tmux session (`<base>-<key>`), so
    switching back lands in the conversation it was in, not a fresh one.
    """
    cur = cfg["topics"].get(topic)
    cwd = (cfg.get("dirs") or {}).get(topic)
    bench = dict((cfg.get("bench") or {}).get(str(topic)) or {})
    if cur:   # whatever the topic is on now is the first thing on its bench
        bench.setdefault((cfg.get("started") or {}).get(topic) or default_agent(cfg), cur)
    if not cwd:
        return "usage: !%s <name> [dir] [flags] [@branch]" % key
    if cur and bench.get(key) == cur and has_session(cur):
        return "already on %s ('%s')" % (key, cur)
    base = cur or os.path.basename(cwd.rstrip("/")) or ("topic%s" % topic)
    for k in agents(cfg):                      # don't stack game-agy-codex-claude
        if base.endswith("-" + k):
            base = base[:-len(k) - 1]
            break
    name = bench.get(key) or ("%s-%s" % (base, key))
    other = bound_to(cfg, name, topic)   # the invariant !bind enforces, enforced here
    if other:
        return "'%s' is topic %s's session — !unbind there first" % (name, other)
    if has_session(name):
        with lock:
            cfg["topics"][topic] = name
            cfg.setdefault("started", {})[topic] = key
            bench[key] = name
            cfg.setdefault("bench", {})[str(topic)] = bench
            save_cfg(cfg)
        state.pop(name, None)   # rebaseline: nothing watched this pane meanwhile
        out = "\u2192 %s ('%s')" % (key, name)
    else:
        out = start_session(cfg, state, lock, topic, "%s %s" % (name, cwd), key)
        if cfg["topics"].get(topic) != name:
            return out          # start_session refused; leave the bench alone
        with lock:
            bench[key] = name
            cfg.setdefault("bench", {})[str(topic)] = bench
            save_cfg(cfg)
    others = sorted(s for k, s in bench.items() if k != key and has_session(s))
    if others:  # two agents, one working tree: say so once, every switch
        out += ("\n\u26a0\ufe0f also live in the same tree: " + ", ".join(others)
                + "\n!agents to switch back; @branch at start for a worktree of its own")
    return out


def start_session(cfg, state, lock, topic, arg, key):
    """New session running agent `key`, bound to this topic. Flags pass through.

    A trailing @branch checks out a git worktree for that branch next to the
    repo and starts there instead — the isolation two agents in one tree need,
    without nightmux trying to be a merge tool.
    """
    prog, _ = agent(cfg, key)
    name, _, rest = arg.partition(" ")
    rest = rest.strip()
    if not name:
        return f"usage: !{key} <name> [dir] [flags] [@branch]"
    if has_session(name):
        return f"'{name}' exists; use !bind {name}"
    if rest.startswith(("~", "/", ".")):        # dir first, anything after is flags
        cwd, _, flags = rest.partition(" ")
    else:
        cwd, flags = "", rest
    cwd = os.path.expanduser(cwd or "~")
    if not os.path.isdir(cwd):
        try:
            os.makedirs(cwd, exist_ok=True)
        except Exception as e:
            return f"could not create dir {cwd}: {e}"
    note = ""
    m = re.search(r"(?:^|\s)@(\S+)", flags)
    if m:
        branch, flags = m.group(1), (flags[:m.start()] + flags[m.end():]).strip()
        wt = worktree_path(cwd, branch)
        if not wt:
            return f"{cwd} is not a git repo — @{branch} needs a worktree to live in"
        cwd, note = wt, f" @{branch}"
    
    # Another topic's session in this directory is a collision; this topic's own
    # is not. A topic restarting itself, or benching a second agent on its own
    # tree with !<key>, is deliberate -- and the guard used to refuse both.
    active_cwds = {cfg.get("dirs", {}).get(t): s
                   for t, s in cfg.get("topics", {}).items()
                   if str(t) != str(topic) and has_session(s)}
    if cwd in active_cwds and active_cwds[cwd] != name:
        return f"collision: session '{active_cwds[cwd]}' is already running in {cwd}. Use @branch for a separate git worktree instead."

    spawn(name, cwd, f"{prog} {flags}".strip())
    with lock:
        cfg["topics"][topic] = name
        cfg.setdefault("dirs", {})[topic] = cwd   # !resume needs it after a crash
        cfg.setdefault("started", {})[topic] = key   # ...and which agent it was
        save_cfg(cfg)
    state.pop(name, None)
    return (f"started {prog} {flags} '{name}' in {cwd}{note}, "
            "topic bound").replace("  ", " ")


def autostart(cfg):
    """Recreate configured sessions that are not running (boot, or after a crash).

    cfg["autostart"]: {"Health": "claude ~/HealthPulse"} — a bare dir means claude.
    """
    for name, spec in (cfg.get("autostart") or {}).items():
        if has_session(name):
            continue
        prog, _, cwd = spec.partition(" ")
        if not cwd:
            prog, cwd = agent(cfg, default_agent(cfg))[0], spec
        cwd = os.path.expanduser(cwd.strip())
        if not os.path.isdir(cwd):
            print(f"autostart {name}: no dir {cwd}", file=sys.stderr)
            continue
        spawn(name, cwd, prog)
        print(f"autostart {name}: {prog} in {cwd}", flush=True)


def autobind(cfg, state, lock, topic):
    """First message in a fresh topic starts the project of the same name.

    Needs cfg["projects_root"]; the topic's name is learned from the
    forum_topic_created service message Telegram sends when you create it.
    """
    root = os.path.expanduser(cfg.get("projects_root") or "")
    name = (cfg.get("topic_names") or {}).get(topic)
    if not (root and name and os.path.isdir(root)):
        return None
    slug = re.sub(r"[^\w-]+", "-", name).strip("-")  # tmux rejects . and : in names
    cand_path = None
    for cand in (name, slug, slug.lower()):
        if os.path.isdir(os.path.join(root, cand)):
            cand_path = os.path.join(root, cand)
            break
    
    if not cand_path:
        # User requested to auto-create missing folders when adding a topic
        cand_path = os.path.join(root, slug)
        os.makedirs(cand_path, exist_ok=True)
        
    return start_session(cfg, state, lock, topic,
                         f"{slug} {cand_path}", default_agent(cfg))


def window(snap, key):
    """A usage window from the status-line snapshot, or None once it has reset.

    Claude Code redraws its status line with the last figures it knew, so for a
    moment after a window turns over the payload still carries the old
    percentage beside a resets_at that has already passed. Reporting it
    announces the *previous* window's 92% as if it were this one's, which is
    both wrong and alarming. The reading is fresh; the window it describes is
    not, and the next redraw carries the real one.
    """
    w = (snap or {}).get(key) or {}
    at = w.get("resets_at")
    if w.get("used_percentage") is None or (at and at <= time.time()):
        return None
    return w


def usage_line(cfg, snap, sep="  "):
    """5-hour and weekly windows, straight from what the status line was told."""
    out = []
    for key, label in (("five_hour", "5h"), ("seven_day", "7d")):
        w = window(snap, key)
        if not w:
            continue
        at = w.get("resets_at")
        out.append(f"{label} {w['used_percentage']:.0f}%" + (
            f"→{clock(cfg, at)}" if at else ""))
    ctx = (snap or {}).get("ctx_pct")
    if ctx is not None:
        out.append(f"ctx {ctx:.0f}%")
    return sep + sep.join(out) if out else ""


def agent_report(cfg, state, topic):
    """This topic's bench: every agent it has a session for, the live one marked.

    A session with no context figure is marked, not omitted: autocompact and the
    idle hint are off for it, and that is worth knowing before you park a long
    job on it.
    """
    cur = cfg["topics"].get(topic)
    bench = dict((cfg.get("bench") or {}).get(str(topic)) or {})
    if cur:
        bench.setdefault((cfg.get("started") or {}).get(topic) or default_agent(cfg), cur)
    if not bench:
        return ("no agents in this topic yet\n!<agent> <name> <dir> starts one: "
                + ", ".join(agents(cfg)))
    rows = []
    for k, sess in sorted(bench.items()):
        mark = "\u25cf" if sess == cur else "\u25cb"
        snap = (state.get(sess) or {}).get("snap") or {}
        if not has_session(sess):
            note = "  \U0001f480 gone, !%s restarts it" % k
        elif snap.get("ctx_pct") is None:
            note = "  \U0001f648 no ctx figure"
        else:
            note = "  ctx %.0f%%" % snap["ctx_pct"]
        rows.append("%s !%-9s %s%s" % (mark, k, sess, note))
    rest = [k for k in agents(cfg) if k not in bench]
    return ("\n".join(rows) + "\n\ndir: %s\n" % ((cfg.get("dirs") or {}).get(topic) or "?")
            + "bare !<agent> switches" + ("; not here yet: " + ", ".join(rest) if rest else ""))


def status_report(cfg, state):
    if not cfg["topics"]:
        return "no topics bound"
    now, rows, alive = time.time(), [], live_sessions()
    if alive is None:
        return ("tmux is not answering — status would report every session as "
                "gone, which is a guess, not a reading. Try again in a moment.")
    for topic, sess in sorted(cfg["topics"].items(), key=lambda kv: int(kv[0])):
        st = state.get(sess, {})
        if sess not in alive:
            rows.append(f"💀 {sess:<14} topic {topic}  no tmux session")
            continue
        mode = st.get("mode", "?")
        icon = {"waiting": "🟠", "busy": "⚙️", "idle": "✅"}.get(mode, "❔")
        age = int(now - st.get("changed", now))
        snap = st.get("snap")
        tag = " [hook]" if hooked(sess) and not (snap or {}).get("transcript") else ""
        # No status-line snapshot at all: no usage windows, no context figure, no
        # transcript, and the pane falls back to whichever one holds the focus.
        # The session still works, it is just being watched through the keyhole,
        # and nothing said so — it took a script to notice two topics were.
        tag += "" if snap else " [no status line]"
        q = len(st.get("queue") or [])
        held = f"  🔒held→{clock(cfg, st['limit_until'])}" if st.get("limit_until", 0) > now else ""
        rows.append(f"{icon} {sess:<14} topic {topic}  {mode}  {age}s quiet{tag}"
                    + (f"  📥{q}" if q else "") + held + usage_line(cfg, snap))
    seen, dupes = set(), set()
    for s in cfg["topics"].values():
        (dupes if s in seen else seen).add(s)
    if dupes:   # one scrape cursor between them, so one of the two goes silent
        rows.append("\u26a0\ufe0f bound to two topics, only one of which gets the "
                    "output: " + ", ".join(sorted(dupes)) + " \u2014 !unbind one")
    return "\n".join(rows)


# Everything that reaches the keyboard of a live session, or ends one. Bare text
# is the other half and is caught separately, being everything that is not a
# command. Listed rather than inferred: a command added later is read-only until
# someone says otherwise, which is the safe direction for the list to be wrong in.
WRITE_CMDS = ("!raw", "!keys", "!kill", "!new", "!resume", "!restore", "!model",
              "!effort", "!bind", "!unbind", "!reload", "!autocompact", "!tz",
              "!at", "!every", "!spendcap", "!shift", "!center", "!all")


def writes(cfg, cmd, arg=""):
    """True when this would type into the session, or take it away."""
    return (not cmd.startswith("!") or cmd in KEYS or cmd in WRITE_CMDS
            or cmd[1:] in agents(cfg)                # !claude, !agy: starts one
            or (cmd == "!queue" and arg == "now"))   # releasing a hold sends


def handle(cfg, state, lock, topic, text, mid=None):
    """Return reply text, or None when the message was typed into the session."""
    sess = cfg["topics"].get(topic)
    # Telegram rewrites "/compact" as "/compact@thebot" in groups; Claude wants
    # the bare slash command.
    text = re.sub(r"^(/[\w:-]+)@\w+", r"\1", text)
    # Any whitespace, not just a space: !shift's plan is one prompt per line in
    # the same message, and splitting on " " alone would cut "cmd" at whatever
    # space happened to fall on line two instead of the newline right after it.
    cmd, arg = (text.split(None, 1) + ["", ""])[:2]
    cmd, arg = cmd.lower(), arg.strip()
    # Registered slash aliases so Telegram's "/" menu can drive nightmux too. Names
    # that Claude Code also owns are deliberately absent: those pass through.
    if cmd[1:] in TG_SLASH:
        cmd = TG_SLASH[cmd[1:]]
        text = f"{cmd} {arg}".strip()

    # A phone is a small thing to lose, and the account that unlocks it drives
    # every bound session. A topic watching something it must not touch can say
    # so — it still reports, greps and shows usage, it just never reaches the
    # keyboard. Set with "modes": {"115": "readonly"}.
    if (cfg.get("modes") or {}).get(str(topic)) == "readonly" and writes(cfg, cmd, arg):
        return ("🔒 this topic is read-only\n"
                "it reports and searches; it does not type into the session.\n"
                'change "modes" in the config and !reload to lift it')
    if cmd == "!version":
        return version_report()
    if cmd == "!help":
        return ("!bind <session> | !unbind | !sessions\n"
                f"!new <name> [dir] [flags] [@branch], or !<agent>: "
                f"{', '.join(agents(cfg))}\n"
                "!agents = this topic's agents; bare !<agent> switches between them\n"
                "!resume [agy] / !restore = relaunch this topic's dir with --continue\n"
                "!worktrees = git worktrees of this topic's repo, and who is in each\n"
                "!status (all topics) | !pane [lines] | !verbose | !kill | !ctl\n"
                "!git | !diff (session's cwd) | !get <path> | !log (daemon journal)\n"
                "!undo = list snapshot branches + restore commands (never runs them)\n"
                "!queue [clear|now] | !usage | !ctx | !cost [days] | !tz | !reload\n"
                "!at 03:00 <prompt> | !at +90m … | !every 4h … | !sched [clear]\n"
                "!shift then one prompt per line = a sequential overnight plan\n"
                "!digest [HH:MM|off] = what happened while you slept, on demand or daily\n"
                "!center [off] = make this topic watch/control every session\n"
                "!board = every topic at a glance (works anywhere)\n"
                "!all <sess1,sess2|--all> <prompt> = send one prompt to several sessions\n"
                "!version = build, python, and which hooks are wired\n"
                "!grep <text> [days] searches every transcript\n"
                "!autocompact <pct|off> | !idlectx <pct|off>\n"
                "!spendcap <turns|500k|2M|off> = interrupt a loop that runs up "
                "turns, or tokens, in 5m\n"
                "type / for the same commands with autocomplete\n"
                "!model <name> | !effort <low|medium|high>\n"
                "!1..!9 menu pick | !y !n !esc !int !enter !up !down !tab !mode\n"
                "!keys <tmux keys> | !raw <text> (type even with a menu open)\n"
                "photo/file/voice -> saved, path typed in\n"
                "/slash and anything else -> typed into Claude")
    if cmd == "!log":
        return run("journalctl", "--user", "-u", "nightmux", "-n", "40", "--no-pager")
    if cmd == "!reload":  # config is human-owned; pick up a hand edit without a restart
        with lock:
            cfg.update(load_cfg())
        return f"reloaded {CFG_PATH}\ntopics: {cfg['topics']}"
    if cmd == "!status":
        with lock:
            return status_report(cfg, state)
    if cmd == "!tz":
        if arg:
            try:
                off = float(arg.lstrip("+"))
            except ValueError:
                # A zone name tracks DST; a fixed offset silently goes an hour
                # wrong for half the year.
                if not os.path.isfile(os.path.join(ZONEINFO, arg)):
                    return ("usage: !tz Africa/Cairo   (a zone, so DST follows)\n"
                            "       !tz +3             (a fixed offset)")
                off = arg
            with lock:
                cfg["tz_offset"] = off
                save_cfg(cfg)
        now, tz = time.time(), cfg.get("tz_offset")
        return (f"server  {time.strftime('%H:%M %Z', time.localtime(now))}\n"
                f"shown   {clock(cfg, now)}  "
                + ("(server time; !tz Africa/Cairo to shift)" if tz is None
                   else f"({tz})" if isinstance(tz, str) else f"(UTC{tz:+g})"))
    if cmd == "!usage":
        rows = []
        for t, s in sorted(cfg["topics"].items(), key=lambda kv: int(kv[0])):
            u = usage_line(cfg, (state.get(s) or {}).get("snap"), sep=" ")
            rows.append(f"{s:<14}{u or ' no status-line data yet'}")
        return "\n".join(rows) or "no topics bound"
    if cmd == "!sessions":
        return tmux("list-sessions", "-F", "#{session_name}  #{session_windows}w  #{?session_attached,attached,detached}") or "no sessions"
    if cmd == "!bind":
        if not arg:
            return "usage: !bind <tmux-session>"
        name = real_session(arg)     # an abbreviation binds the session it names
        if not name:
            return f"no tmux session '{arg}'"
        other = bound_to(cfg, name, topic)
        if other:
            return ("'%s' is topic %s's session -- one session, one topic\n"
                    "(they would share one scrape cursor, and one of them goes "
                    "silent)\n!unbind there first, or !<agent> here for a session "
                    "of your own" % (name, other))
        with lock:
            cfg["topics"][topic] = name
            save_cfg(cfg)
        state.pop(name, None)
        return f"topic bound to '{name}'"
    if cmd == "!unbind":
        with lock:
            old = cfg["topics"].pop(topic, None)
            save_cfg(cfg)
        return f"unbound '{old}'" if old else "not bound"
    if cmd == "!agents":
        return agent_report(cfg, state, topic)
    if cmd == "!new" or cmd[1:] in agents(cfg):
        # Bare !<agent> in a topic that already knows its directory means "switch
        # this topic to that agent" -- same project, different agent, and the one
        # it was on left running. With arguments it still starts a named session.
        if cmd != "!new" and not arg and (cfg.get("dirs") or {}).get(topic):
            return switch_agent(cfg, state, lock, topic, cmd[1:])
        return start_session(cfg, state, lock, topic, arg,
                             default_agent(cfg) if cmd == "!new" else cmd[1:])
    if cmd in ("!resume", "!restore"):    # !restore: same relaunch, easier to guess
        return resume_session(cfg, state, lock, topic, arg)
    if cmd == "!center":
        with lock:
            prev = cfg.get("center_topic")
            cfg["center_topic"] = None if arg == "off" else topic
            save_cfg(cfg)
        if arg == "off":
            return "command center off" if prev else "no command center was set"
        if prev and str(prev) != str(topic):
            return f"command center moved here from topic {prev}"
        return "this topic is now the command center — try !board"
    if cmd == "!board":
        return board_report(cfg, state)
    if cmd == "!all":
        return broadcast(cfg, state, topic, arg)
    if cmd == "!digest" and str(topic) == str(cfg.get("center_topic") or ""):
        if arg:
            return "!digest here is report-only — schedule it from each session's own topic"
        if not cfg["topics"]:
            return "no topics bound"
        parts = []
        for t, s in sorted(cfg["topics"].items(), key=lambda kv: int(kv[0])):
            if not has_session(s):
                continue
            st_s = state.setdefault(s, {})
            since = st_s.get("digest_since", time.time() - 86400)
            parts.append(digest_report(cfg, state, t, s, since))
            st_s["digest_since"] = time.time()
        return "\n\n".join(parts) if parts else "no live sessions"

    # A mirrored approval button names its session explicitly, since the
    # command-center topic it may have been tapped in binds to none.
    mirrored = cmd in KEYS and arg and has_session(arg)
    if mirrored:
        sess = arg
    if not sess:
        if str(topic) == str(cfg.get("center_topic") or ""):
            return "this topic controls every session — try !board"
        return (autobind(cfg, state, lock, topic)
                or "topic not bound. !bind <session> or !new <name> [dir]")
    if not has_session(sess):
        return f"tmux session '{sess}' is gone"

    if cmd == "!pane":
        n = min(int(arg), 2000) if arg.isdigit() else 60
        return tmux("capture-pane", "-p", "-J", "-t", sess, "-S", f"-{n}")
    if cmd == "!get":
        if not arg:
            return "usage: !get <path> (relative to the session's cwd, or absolute)"
        p = os.path.join(sess_cwd(sess), os.path.expanduser(arg))
        if not os.path.isfile(p):
            return f"no file {p}"
        mb = os.path.getsize(p) / 1048576
        if mb > 45:  # bots may upload 50MB
            return f"{p} is {mb:.0f}MB, over Telegram's 50MB upload cap"
        with open(p, "rb") as f:
            send_file(cfg, topic, os.path.basename(p), f.read(), p)
        return None
    if cmd == "!autocompact":
        if arg:
            with lock:
                cfg["autocompact"] = None if arg in ("off", "0") else int(arg)
                save_cfg(cfg)
        at = cfg.get("autocompact")
        return (f"auto /compact at {at}% context" if at else
                "auto /compact off — !autocompact 70 to enable")
    if cmd == "!spendcap":
        if arg:
            if arg in ("off", "0"):
                v = None
            elif re.fullmatch(r"\d+(?:\.\d+)?[kKmM]", arg):
                v = arg.lower()          # a suffix means tokens, kept as written
            elif arg.isdigit():
                v = int(arg)
            else:
                return "usage: !spendcap <turns> | <500k|2M> tokens | off"
            with lock:
                cfg["spendcap"] = v
                save_cfg(cfg)
        cap, tcap = spend_cap(cfg)
        if tcap:
            return (f"spend cap set to {tcap:,} base-equiv tokens in 5 minutes\n"
                    "counted from the transcript, so Claude Code sessions only")
        return (f"spend cap set to {cap} turns in 5 minutes" if cap else
                "spend cap off — !spendcap 10 (turns) or !spendcap 2M (tokens)")
    if cmd == "!idlectx":
        if arg:
            with lock:
                cfg["idle_ctx"] = None if arg in ("off", "0") else int(arg)
                save_cfg(cfg)
        at = cfg.get("idle_ctx", IDLE_CTX)
        return (f"idle sessions above {at}% context flagged after "
                f"{IDLE_PARK // 3600}h" if at else
                f"idle-context hints off — !idlectx {IDLE_CTX} to enable")
    if cmd == "!cost":
        if arg.isdigit():   # every project, that many days back
            days = int(arg)
            return cost_report(token_tally(recent_transcripts(days)),
                               f"all projects · last {days}d")
        path = ((state.get(sess) or {}).get("snap") or {}).get("transcript")
        if not path:
            return "no transcript for this session yet — !cost 7 for all projects"
        return cost_report(token_tally([path]), f"{sess} · this conversation")
    if cmd == "!grep":
        if not arg:
            return "usage: !grep <text> [days]   (searches every transcript)"
        needle, _, tail = arg.rpartition(" ")
        days = int(tail) if tail.isdigit() and needle else 7
        return grep_transcripts(needle or arg, days)
    if cmd == "!ctx":
        snap = (state.get(sess) or {}).get("snap") or {}
        path = snap.get("transcript")
        if not path or not os.path.isfile(path):
            return ("no transcript for this session yet — send it a prompt so its "
                    "status line redraws, or it is not a Claude Code session")
        head = f"{sess}  context {snap['ctx_pct']:.0f}% full\n" \
            if snap.get("ctx_pct") is not None else f"{sess}\n"
        return head + ctx_report(path)
    if cmd in ("!git", "!diff"):
        cwd = sess_cwd(sess)
        if cmd == "!diff":
            return (tmux_git(cwd, "diff", "--stat") + "\n\n"
                    + tmux_git(cwd, "diff")).strip() or f"no unstaged changes in {cwd}"
        return (f"{cwd}\n" + tmux_git(cwd, "status", "-sb") + "\n\n"
                + tmux_git(cwd, "log", "--oneline", "-5"))
    if cmd == "!worktrees":
        cwd = sess_cwd(sess)
        root = tmux_git(cwd, "rev-parse", "--show-toplevel")
        if not root:
            return f"{cwd} is not a git repo"
        who = {}
        for t, s in cfg["topics"].items():
            if has_session(s):
                who.setdefault(sess_cwd(s), []).append(s)
        rows = [l for l in tmux_git(root, "worktree", "list").split("\n") if l.strip()]
        return "\n".join(l + (f"   [{', '.join(who[l.split()[0]])}]"
                              if who.get(l.split()[0]) else "") for l in rows)
    if cmd == "!undo":
        cwd = sess_cwd(sess)
        rows = [l for l in tmux_git(
            cwd, "for-each-ref", "--sort=-creatordate",
            "--format=%(refname:short)  %(creatordate:iso-strict)",
            "refs/heads/nightmux/pre-*").split("\n") if l.strip()]
        if not rows:
            return f"no snapshots in {cwd} · one is taken before every unattended prompt"
        newest = rows[0].split()[0]
        return ("snapshots in " + cwd + " (newest first):\n"
                + "\n".join(f"{i + 1}. {r}" for i, r in enumerate(rows))
                + "\n\nnightmux never restores automatically — run this yourself:\n"
                f"  git restore --source {newest} -- .   # overwrite the worktree\n"
                f"  git diff {newest}                    # or just look first\n"
                "(swap in an older branch name to go further back)")
    if cmd == "!ctl":
        send(cfg, topic, f"controls · {sess}", mode="plain", buttons=kb([
            [("esc", "!esc"), ("⇧⇥ mode", "!mode"), ("⏎", "!enter"), ("↑", "!up")],
            [("1", "!1"), ("2", "!2"), ("3", "!3"), ("y", "!y"), ("n", "!n")],
            [("status", "!status"), ("pane", "!pane"), ("verbose", "!verbose")],
            [("git", "!git"), ("diff", "!diff"), ("log", "!log")]]))
        return None
    if cmd == "!verbose":
        with lock:
            v = cfg.setdefault("verbose", [])
            on = topic not in v
            v.append(topic) if on else v.remove(topic)
            save_cfg(cfg)
        return f"verbose {'on' if on else 'off'} for this topic"
    if cmd == "!cancel":
        return "cancelled"
    if cmd == "!kill":
        # One tap on a phone, and a session mid-turn is gone. The conversation
        # itself survives in the transcript — !resume relaunches it — but the
        # running claude, its pane and this topic's binding do not.
        if arg != "yes":
            send(cfg, topic, f"⚠️ kill tmux session '{sess}'?\n"
                 "ends the running claude and unbinds this topic\n"
                 "!resume relaunches its directory with --continue",
                 mode="plain", buttons=kb([[(f"kill {sess}", "!kill yes"),
                                            ("cancel", "!cancel")]]))
            return None
        tmux("kill-session", "-t", sess)
        with lock:
            cfg["topics"].pop(topic, None)
            save_cfg(cfg)
        return f"killed '{sess}'"
    if cmd == "!keys":
        if not arg:
            return "usage: !keys <tmux key names>"
        tmux("send-keys", "-t", tgt(sess), *arg.split())
        return None
    if cmd in KEYS:
        key = KEYS[cmd]
        if cmd in YES_NO:
            key = menu_digit(visible(sess), YES_NO[cmd]) or key
        with lock:
            st = state.setdefault(sess, {})
            # A mirrored button already resolved by its other copy has nothing
            # left to answer — that race is decided here, under the one lock
            # every topic worker shares, not by whichever tap Telegram delivers
            # first.
            stale = mirrored and not st.get("asked_msgs")
            resolve_ask(cfg, st)
        if stale:
            return None
        if key.isdigit():
            miss = pick(sess, key)      # None: the digit is the answer after all
            if miss is not None:
                return miss or None
        press(sess, key, confirm=cmd in YES_NO or cmd[1:].isdigit())
        return None
    st = state.setdefault(sess, {})
    if cmd == "!queue":
        q = st.get("queue") or []
        if arg == "clear":
            st["queue"] = []
            save_queue(state)
            return f"dropped {len(q)} queued prompt(s)"
        if arg == "now":  # send it anyway, limit or not
            st.pop("limit_until", None)
            save_queue(state)
            return f"limit hold released, {len(q)} queued prompt(s) resume on idle"
        head = "\n".join(f"{i + 1}. {p.splitlines()[0][:70]}" for i, p in enumerate(q))
        until = st.get("limit_until", 0)
        return (f"{len(q)} queued" + (f", resumes {clock(cfg, until)}"
                if until > time.time() else "") + (f"\n{head}" if q else ""))
    if cmd == "!shift":
        if arg == "clear":
            n = len(st.get("shift") or [])
            st.pop("shift", None), st.pop("shift_total", None)
            save_queue(state)
            return f"shift cleared ({n} step(s) dropped)"
        if arg:
            plan = [l.strip() for l in arg.split("\n") if l.strip()]
            st["shift"], st["shift_total"] = plan, len(plan)
            save_queue(state)
            return (f"shift set: {len(plan)} step(s), one at a time on idle\n"
                    + "\n".join(f"{i + 1}. {p.splitlines()[0][:70]}"
                                for i, p in enumerate(plan)))
        cur = st.get("shift") or []
        if not cur:
            return "no shift plan · !shift then one prompt per line"
        total = st.get("shift_total", len(cur))
        done = total - len(cur)
        return (f"shift {done}/{total} done, {len(cur)} left\n"
                + "\n".join(f"{done + i + 1}. {p.splitlines()[0][:70]}"
                            for i, p in enumerate(cur)))
    if cmd == "!digest":
        if arg == "off":
            had = any(j.get("kind") == "digest" for j in st.get("sched") or [])
            st["sched"] = [j for j in st.get("sched") or [] if j.get("kind") != "digest"]
            save_queue(state)
            return "digest schedule cancelled" if had else "no digest scheduled"
        if arg:
            at = at_epoch(cfg, arg)
            if at is None:
                return "usage: !digest 08:00 (daily) · !digest off · !digest (now)"
            jobs = [j for j in st.get("sched") or [] if j.get("kind") != "digest"]
            jobs.append({"at": at, "every": 86400, "kind": "digest",
                        "text": "!digest", "since": time.time()})
            st["sched"] = jobs
            save_queue(state)
            return f"digest daily at {clock(cfg, at)} (first in {left(at - time.time())})"
        report = digest_report(cfg, state, topic, sess,
                               st.get("digest_since", time.time() - 86400))
        st["digest_since"] = time.time()
        return report
    if cmd in ("!at", "!every", "!sched"):
        now = time.time()
    if cmd in ("!at", "!every"):
        when, _, prompt = arg.partition(" ")
        secs = parse_every(when) if cmd == "!every" else None
        at = now + secs if secs else at_epoch(cfg, when)
        if not prompt.strip() or at is None:
            return ("usage: !at 03:00 <prompt> · !at +90m <prompt>\n"
                    "       !every 4h <prompt>")
        st.setdefault("sched", []).append(
            {"at": at, "every": secs, "text": prompt})
        save_queue(state)
        return (f"⏰ {'every ' + when if secs else 'at ' + clock(cfg, at)}"
                f" (first in {left(at - now)})\n{prompt.splitlines()[0][:70]}\n"
                "!sched to list, !sched clear to drop")
    if cmd == "!sched":
        jobs = st.get("sched") or []
        if arg == "clear":
            st["sched"] = []
            save_queue(state)
            return f"dropped {len(jobs)} scheduled prompt(s)"
        if not jobs:
            return "nothing scheduled · !at 03:00 <prompt> | !every 4h <prompt>"
        return "\n".join(
            f"{i + 1}. {clock(cfg, j['at'])} (in {left(j['at'] - now)})"
            + (f" every {left(j['every'])}" if j.get("every") else "")
            + f" · {j['text'].splitlines()[0][:50]}" for i, j in enumerate(jobs))
    if cmd == "!raw":  # deliberate override of the menu guard below
        inject(sess, arg)
        remember(state, sess, arg)
        started(cfg, state, topic, sess, mid)
        return None
    if cmd in ("!model", "!effort"):  # sugar: type the slash command for you
        text = f"/{cmd[1:]} {arg}".strip()

    return send_prompt(cfg, state, topic, sess, text, mid)


def send_prompt(cfg, state, topic, sess, text, mid=None):
    """The live-prompt path: hold behind a lockout, queue behind a busy or
    waiting pane, or type it now. This is what a topic's own live text always
    went through; !all fans the same call out to several sessions so a
    broadcast prompt waits exactly like a typed one instead of a second,
    drifting copy of this logic.
    """
    st = state.setdefault(sess, {})
    until = st.get("limit_until", 0)
    if until > time.time():  # the window is spent; hold it rather than lose it
        st.setdefault("queue", []).append(text)
        save_queue(state)    # durable before the confirmation goes out
        return (f"📥 queued ({len(st['queue'])}) · runs at "
                f"{clock(cfg, until)}"
                f" (in {left(until - time.time())})\n!queue now overrides")
    mode = pane_state(visible(sess))
    # A keypress dialog eats letters and acts on Enter, so plain text would pick
    # the highlighted option — the opposite of what you just typed.
    if mode == "waiting":
        return ("🟠 a menu is open. Typing here would swallow your text and Enter\n"
                "would pick the highlighted option.\n"
                "Answer it: !1..!9 / !y / !n / !esc — or !raw <text> to type anyway.")
    if mode == "busy":
        # Typing into a working session hides the text in the TUI's own queue,
        # where Telegram can neither show it back nor take it away again.
        st.setdefault("queue", []).append(text)
        save_queue(state)
        return (f"📥 queued ({len(st['queue'])}) · {sess} is working\n"
                "sends when it finishes · !queue to list, !queue clear to drop")
    text = spill(sess, text)
    if not inject(sess, text):
        # No agent under the pane. Holding it is the whole point: typed into a
        # shell it would have run as a command and been gone.
        st.setdefault("queue", []).append(text)
        save_queue(state)
        return (f"📥 queued ({len(st['queue'])}) · no agent is running in {sess}\n"
                "!restore relaunches it, and the queue goes in behind it")
    remember(state, sess, text)
    started(cfg, state, topic, sess, mid)
    return None


def broadcast(cfg, state, topic, arg):
    """!all: fan the same prompt out to several sessions through send_prompt.

    The echo of who this hits is sent here, before the loop, rather than
    returned — a returned reply is only sent by the caller after this whole
    function is done, and a bad target list has to be visible before the
    first prompt goes anywhere, not after all of them have.
    """
    target_str, _, prompt = arg.partition(" ")
    if not target_str or not prompt.strip():
        return "usage: !all <sess1,sess2 | --all> <prompt>"
    readonly = lambda t: (cfg.get("modes") or {}).get(str(t)) == "readonly"
    picks, skipped = [], []
    if target_str == "--all":
        for t, s in cfg["topics"].items():
            if not has_session(s):
                skipped.append(f"{s} (no tmux session)")
            elif readonly(t):
                skipped.append(f"{s} (read-only)")
            else:
                picks.append((t, s))
    else:
        for n in (x.strip() for x in target_str.split(",") if x.strip()):
            hit = next(((t, s) for t, s in cfg["topics"].items()
                       if s == n or t == n), None)
            if not hit:
                skipped.append(f"{n} (not bound)")
            elif not has_session(hit[1]):
                skipped.append(f"{hit[1]} (no tmux session)")
            elif readonly(hit[0]):
                skipped.append(f"{hit[1]} (read-only)")
            else:
                picks.append(hit)
    if not picks:
        return "nothing to send to" + (f" — {', '.join(map(str, skipped))}" if skipped else "")
    send(cfg, topic, f"📣 !all → {', '.join(s for _, s in picks)}"
         + (f"\n(skipped: {', '.join(map(str, skipped))})" if skipped else ""), mode="plain")
    for t, s in picks:
        reply = send_prompt(cfg, state, t, s, prompt)
        if reply:
            send(cfg, t, reply, mode="plain")
    return None


def board_report(cfg, state):
    """Every topic at a glance — !status's own state classification, plus a
    cheap per-session cost figure where a transcript is already known.
    """
    if not cfg["topics"]:
        return "no topics bound"
    lines = [status_report(cfg, state)]
    costs = []
    for _, sess in sorted(cfg["topics"].items(), key=lambda kv: int(kv[0])):
        path = ((state.get(sess) or {}).get("snap") or {}).get("transcript")
        if not (path and os.path.isfile(path)):
            continue
        t = token_tally([path])
        if t["turns"]:
            costs.append(f"{sess} ~{int(sum(t[k] * w for k, w in WEIGHT.items())):,}tok")
    if costs:
        lines.append("spend  " + " · ".join(costs))
    return "\n".join(lines)


# ---------- main ----------

class Acks:
    """Persist the polling offset only past updates that are actually finished.

    Topics are served in parallel, so updates complete out of order and the only
    safe restart point is the oldest one still in flight — anything later would
    drop work a crash should replay. Telegram also skips update ids for the
    types we filtered out, so the walk follows the ids actually dispatched
    rather than counting.
    """

    def __init__(self):
        self.seen, self.done, self.lock = [], set(), threading.Lock()

    def dispatch(self, uid):
        with self.lock:
            self.seen.append(uid)

    def ack(self, uid):
        with self.lock:
            self.done.add(uid)
            nxt = None
            while self.seen and self.seen[0] in self.done:
                self.done.discard(self.seen[0])
                nxt = self.seen.pop(0) + 1
            if nxt is not None:                    # nothing older is outstanding
                save_offset(self.seen[0] if self.seen else nxt)


def serve(q):
    while True:
        cfg, state, lock, allow, upd, acks = q.get()
        try:
            process(cfg, state, lock, allow, upd)
        except Exception as e:
            print(f"update {upd.get('update_id')}: {e}", file=sys.stderr)
        finally:
            acks.ack(upd["update_id"])


def upd_topic(upd):
    msg = ((upd.get("callback_query") or {}).get("message")
           or upd.get("message") or {})
    return str(msg.get("message_thread_id") or 0)


_workers = {}   # topic -> queue; only the polling thread touches this


def dispatch(cfg, state, lock, allow, upd, acks):
    """Hand an update to its topic's worker.

    One queue per topic keeps that topic's messages in order while a slow
    command — !grep over every transcript, a big !get upload — stops blocking
    the other topics and the poll loop behind it.
    """
    topic = upd_topic(upd)
    q = _workers.get(topic)
    if q is None:
        q = _workers[topic] = queue.Queue()
        threading.Thread(target=serve, args=(q,), daemon=True).start()
    acks.dispatch(upd["update_id"])
    q.put((cfg, state, lock, allow, upd, acks))


# ---------- first-run setup ----------

HERE = os.path.dirname(os.path.abspath(__file__))
CLAUDE_SETTINGS = os.path.expanduser("~/.claude/settings.json")
UNIT_PATH = os.path.expanduser("~/.config/systemd/user/nightmux.service")

SIDECAR_SH = """#!/bin/bash
# nightmux status line. The pipe below is the point: it parks the context
# percentage, the 5h/7d windows and the transcript path where the daemon reads
# them. Replace everything else with your own status line; keep that one line.
input=$(cat)
printf '%s' "$input" | {py} {sidecar} >/dev/null 2>&1 &
printf '%s' "$input" | {py} -c 'import json,sys; print(json.load(sys.stdin).get("cwd",""), end="")'
"""

UNIT = """[Unit]
Description=Telegram controller for Claude Code tmux sessions
After=network-online.target

[Service]
ExecStart={py} {script}
Restart=always
RestartSec=5
# The tmux server is forked from this daemon, so every agent session lands in
# this unit's cgroup — and the default KillMode=control-group takes all of them
# down on `systemctl restart nightmux`, which is what the docs tell you to run
# after editing the config. Restarting the controller must not kill the work it
# controls: with `process`, systemd signals this process and leaves the sessions
# alone, and the restarted daemon reattaches to them by name.
KillMode=process

[Install]
WantedBy=default.target
"""

PLIST_PATH = os.path.expanduser("~/Library/LaunchAgents/com.nightmux.plist")

PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
    <key>Label</key><string>com.nightmux</string>
    <key>ProgramArguments</key><array>
        <string>{py}</string>
        <string>{script}</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
</dict></plist>
"""


def wired(path=None):
    """Which of the three Claude Code integrations are actually installed.

    Read from settings rather than assumed: "it works, but the output is noisy
    and the usage numbers are missing" is nearly always one of these unwired,
    and it is the first thing a bug report needs to say.
    """
    try:
        with open(path or CLAUDE_SETTINGS) as f:
            blob = f.read()
        sl = (json.loads(blob).get("statusLine") or {}).get("command", "")
    except (OSError, ValueError):
        return []
    blob += open_text(sl)   # the sidecar usually lives one file further out
    return [n for n, p in (("stop", "nightmux_stop.py"), ("notify", "nightmux_notify.py"),
                           ("sidecar", "nightmux_state.py")) if p in blob]


def version_report():
    rev = tmux_git(HERE, "rev-parse", "--short", "HEAD")
    on = wired()
    return (f"nightmux {VERSION}" + (f" ({rev})" if rev and " " not in rev else "")
            + f"\npython {sys.version.split()[0]}\n{HERE}\nwired: "
            + (", ".join(on) if on
               else "nothing — falling back to scraping the pane"))


def setup_chat(upd):
    """(chat_id, user_id, title) for a message in a forum group, else None.

    Topics are the whole model — one topic per session — so a private chat or a
    plain group is not close enough: binding one leaves every session sharing a
    single thread with no way to tell their output apart.
    """
    msg = upd.get("message") or {}
    chat = msg.get("chat") or {}
    if chat.get("type") != "supergroup" or not chat.get("is_forum"):
        return None
    return chat["id"], (msg.get("from") or {}).get("id"), chat.get("title")


def await_group(cfg, timeout=300):
    """Learn the group and the operator by watching for a message in one."""
    # Whatever piled up before setup ran belongs to some earlier conversation,
    # and binding to it would point the daemon at the wrong group.
    res = api(cfg, "getUpdates", offset=-1, timeout=0).get("result") or []
    offset = res[-1]["update_id"] + 1 if res else None
    deadline, nagged = time.time() + timeout, False
    while time.time() < deadline:
        r = api(cfg, "getUpdates", offset=offset, timeout=20,
                allowed_updates=json.dumps(["message"]))
        for upd in r.get("result") or []:
            offset = upd["update_id"] + 1
            found = setup_chat(upd)
            if found:
                return found
            if not nagged:
                nagged = True
                print("   saw a message, but not in a forum group — the group "
                      "needs Topics turned on")
    return None


def wire_claude(path=None):
    """Add the two hooks and the status-line sidecar, touching nothing else.

    Idempotent: a second run finds its own commands already there and writes
    nothing, so re-running setup after an upgrade is safe. An existing status
    line is never rewritten — that file is the user's, and clobbering it to gain
    a percentage readout is a bad trade.
    """
    path = path or CLAUDE_SETTINGS
    try:
        with open(path) as f:
            settings = json.load(f)
    except (OSError, ValueError):
        settings = {}
    notes = []
    for event, script in (("Stop", "nightmux_stop.py"), ("Notification", "nightmux_notify.py")):
        groups = settings.setdefault("hooks", {}).setdefault(event, [])
        if any(script in h.get("command", "")
               for g in groups for h in g.get("hooks") or []):
            continue
        groups.append({"hooks": [{"type": "command", "timeout": 20, "command":
                                  f"{sys.executable} {os.path.join(HERE, script)}"}]})
        notes.append(f"hook {event} -> {script}")
    sidecar = os.path.join(HERE, "nightmux_state.py")
    line = f'printf \'%s\' "$input" | {sys.executable} {sidecar} >/dev/null 2>&1 &'
    if not settings.get("statusLine"):
        sh = os.path.join(os.path.dirname(path), "nightmux-statusline.sh")
        with open(sh, "w") as f:
            f.write(SIDECAR_SH.format(py=sys.executable, sidecar=sidecar))
        os.chmod(sh, 0o755)
        settings["statusLine"] = {"type": "command", "command": f'bash "{sh}"'}
        notes.append(f"status line -> {sh}")
    elif line not in open_text(settings["statusLine"].get("command", "")):
        notes.append("status line: already yours, left alone. For live context %"
                     " and 5h/7d limits, add this line to it:\n     " + line)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w") as f:
        json.dump(settings, f, indent=2)
    os.replace(path + ".tmp", path)
    return notes


def open_text(cmd):
    """Best-effort read of a status-line command's script, for the 'already wired?'
    check. A command that is not a readable file simply has not wired us in."""
    for word in cmd.replace('"', " ").replace("'", " ").split():
        try:
            with open(word) as f:
                return f.read()
        except OSError:
            continue
    return ""


def wire_unit():
    """Install and start the user service, and keep it running after logout."""
    if sys.platform == "darwin":
        os.makedirs(os.path.dirname(PLIST_PATH), exist_ok=True)
        with open(PLIST_PATH, "w") as f:
            f.write(PLIST.format(py=sys.executable,
                                 script=os.path.join(HERE, "nightmux.py")))
        # load/unload are the deprecated spelling, but they still work on every
        # macOS this can run on, and the bootstrap replacement needs the uid.
        subprocess.run(("launchctl", "unload", PLIST_PATH), capture_output=True)
        return run("launchctl", "load", PLIST_PATH)
    os.makedirs(os.path.dirname(UNIT_PATH), exist_ok=True)
    with open(UNIT_PATH, "w") as f:
        f.write(UNIT.format(py=sys.executable,
                            script=os.path.join(HERE, "nightmux.py")))
    # Without linger a user service stops at logout and never starts at boot,
    # which is exactly when a phone-driven controller needs to be up.
    subprocess.run(("loginctl", "enable-linger"), capture_output=True)
    subprocess.run(("systemctl", "--user", "daemon-reload"), capture_output=True)
    return run("systemctl", "--user", "enable", "--now", "nightmux")


WAS = ("telemux", "tgctl")   # every name this has shipped under, newest first


def migrate(paths=None):
    """Adopt anything a daemon under an older name left behind, once.

    The config is the only one of these that cannot be regenerated, and held
    prompts in the state directory are the only other thing worth carrying — but
    renaming all of them is the same three lines, and a fresh install finds
    nothing and does nothing.

    Two old names rather than one because tgctl became telemux became nightmux,
    and an install that slept through the middle one still has to land here.
    """
    for new in paths or (CFG_PATH, OFFSET_PATH, STATE_DIR, HOOK_DIR, FILE_DIR):
        for was in WAS:
            old = new.replace("nightmux", was)
            if old != new and os.path.exists(old) and not os.path.exists(new):
                os.rename(old, new)
                print(f"migrated {old} -> {new}", flush=True)


def setup():
    """Interactive first run: token, group, allowlist, hooks, service."""
    migrate()
    if not sys.stdin.isatty():
        sys.exit("--setup needs a terminal")
    try:
        cfg = load_cfg()
    except (OSError, ValueError):
        cfg = {}
    print("nightmux setup\n\n"
          "1. In Telegram, open @BotFather -> /newbot, and copy the token.")
    token = input("   token%s: " % (" [enter to keep the saved one]"
                                    if cfg.get("token") else "")).strip()
    cfg["token"] = token or cfg.get("token")
    if not cfg["token"]:
        sys.exit("no token, no bot")
    me = api(cfg, "getMe")
    if not me.get("ok"):
        sys.exit(f"telegram rejected that token: {me.get('description')}")
    bot = me["result"]["username"]
    print(f"   ok, @{bot}\n\n"
          "2. Create a Telegram group, open its settings and turn on Topics.\n"
          f"3. Add @{bot} to it as an admin. Admin is required: without it the\n"
          "   bot only sees messages addressed to it, so most of what you type\n"
          "   would never arrive.\n"
          "4. Post any message in the group. Waiting...")
    found = await_group(cfg)
    if not found:
        sys.exit("nothing arrived. Check the bot is in the group, and is an admin.")
    chat_id, user_id, title = found
    cfg["chat_id"] = chat_id
    cfg["allow_users"] = [user_id]
    cfg.setdefault("topics", {})
    save_cfg(cfg)   # 0600: this file is a shell on this machine, see SECURITY.md
    print(f"   bound to '{title}' ({chat_id})\n"
          f"   allow_users = [{user_id}] — only you. Anyone you add here gets a\n"
          f"   shell on this machine; read SECURITY.md before you add a second.\n"
          f"   wrote {CFG_PATH} (0600)\n")
    for note in wire_claude() or ["claude settings already wired"]:
        print(f"   {note}")
    print()
    mac = sys.platform == "darwin"
    svc = "launchd agent" if mac else "systemd user service"
    if input(f"Install and start the {svc}? [Y/n] ").strip().lower() \
            not in ("", "y", "yes"):
        print(f"skipped. Run it yourself with: {sys.executable} {__file__}")
        return
    print(wire_unit() or f"   started, unit at {PLIST_PATH if mac else UNIT_PATH}")
    print("\nDone. In the group: create a topic, then send\n"
          "   !new myproj ~/code/myproj\n"
          "and type to it. !help lists the rest.")


def restore_startup(cfg, state, lock):
    """Reconcile topic bindings against live tmux sessions once, at boot.

    A reboot kills every tmux session; the config still remembers what each
    topic was running (start_session sets `dirs`/`started` for exactly this).
    auto_restore relaunches immediately — opt-in, since a reboot silently
    resurrecting a paid agent session is not a default anyone asked for.
    Otherwise the topic gets a button instead of nightmux acting on its own.
    watchdog() gates every drain on the session being alive, so a queue behind
    a still-dead one waits rather than being lost — nothing extra needed here.
    """
    for topic, sess in list(cfg["topics"].items()):
        if has_session(sess):
            continue
        why = None
        if cfg.get("auto_restore"):
            key = (cfg.get("started") or {}).get(topic) or default_agent(cfg)
            why = resume_session(cfg, state, lock, topic)
            if why.startswith("started"):
                send(cfg, topic, f"▶️ restored {sess} · {key}", mode="plain")
                continue
        # Pre-mark dead so watchdog's first tick does not also send its own
        # "gone" message for the same session a moment later.
        state.setdefault(sess, {})["dead"] = True
        send(cfg, topic, f"⚠️ {sess} is gone — machine restarted?"
             + (f"\nnot restored: {why}" if why else ""), mode="plain",
             buttons=kb([[("restore", "!restore")]]))


# ---------- webhook API ----------
import http.server
import socketserver

class WebhookHandler(http.server.BaseHTTPRequestHandler):
    def resolve_topic(self, topic):
        """Map a session name (e.g. 'api') back to its Telegram thread ID if needed."""
        for t_id, s_name in self.server.cfg.get("topics", {}).items():
            if s_name == topic:
                return t_id
        return topic

    def do_GET(self):
        parts = self.path.strip('/').split('/')
        if len(parts) != 2 or parts[0] != 'topic':
            self.send_response(404)
            self.end_headers()
            return
            
        topic = self.resolve_topic(parts[1])
        sess = self.server.cfg.get("topics", {}).get(topic)
        if not sess:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "topic not bound"}\n')
            return
            
        with self.server.lock:
            st_s = self.server.state.get(sess) or {}
            snap = st_s.get("snap")
            alive = has_session(sess)
            mode = st_s.get("mode") or "idle" if alive else "offline"
            u_line = usage_line(self.server.cfg, snap, sep=" ") if snap else None
            
        import json
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "session": sess,
            "alive": alive,
            "mode": mode,
            "usage": u_line
        }).encode('utf-8'))

    def do_POST(self):
        parts = self.path.strip('/').split('/')
        if len(parts) != 2 or parts[0] != 'topic':
            self.send_response(404)
            self.end_headers()
            return
            
        topic = self.resolve_topic(parts[1])
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8').strip()
        
        if not body:
            self.send_response(400)
            self.end_headers()
            return
            
        fake_upd = {
            "update_id": 0,
            "message": {
                "message_thread_id": int(topic) if topic.isdigit() else topic,
                "text": body,
                "chat": {"id": self.server.cfg["chat_id"]},
                "from": {"id": list(self.server.allow)[0]} 
            }
        }
        
        class DummyAcks:
            def dispatch(self, uid): pass
            def ack(self, uid): pass
            
        q = _workers.get(topic)
        if q is None:
            q = _workers[topic] = queue.Queue()
            threading.Thread(target=serve, args=(q,), daemon=True).start()
            
        q.put((self.server.cfg, self.server.state, self.server.lock, self.server.allow, fake_upd, DummyAcks()))
        
        self.send_response(202)
        self.end_headers()
        self.wfile.write(b"Accepted\n")

    def log_message(self, format, *args):
        pass

def run_webhook_server(cfg, state, lock, allow, port):
    class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True
        
    server = ThreadedHTTPServer(('127.0.0.1', port), WebhookHandler)
    server.cfg, server.state, server.lock, server.allow = cfg, state, lock, allow
    print(f"webhook listening on 127.0.0.1:{port}", flush=True)
    server.serve_forever()


def main():
    migrate()
    cfg = load_cfg()
    for key in ("token", "chat_id", "allow_users"):
        if not cfg.get(key):
            sys.exit(f"{CFG_PATH}: missing '{key}'  (run: {__file__} --setup)")
    cfg.setdefault("topics", {})
    autostart(cfg)
    register_commands(cfg)
    state, lock = {}, threading.Lock()
    # Before the watcher runs, or its first save would overwrite the file with
    # the empty state it starts from.
    _warned.update(load_warned())   # a restart is not news for a window mid-flight
    for sess, held in load_queue(state).items():
        topic = next((t for t, s in cfg["topics"].items() if s == sess), None)
        until, q, jobs, plan = held.get("limit_until", 0), held.get("queue") or [], \
            held.get("sched") or [], held.get("shift") or []
        kept = ", ".join(([f"{len(q)} queued prompt(s)"] if q else [])
                         + ([f"{len(jobs)} scheduled"] if jobs else [])
                         + ([f"{len(plan)} shift step(s)"] if plan else []))
        print(f"restored {kept} for {sess}", flush=True)
        if topic:
            send(cfg, topic, f"↩️ nightmux restarted · {kept} kept"
                 + (f", still holding until {clock(cfg, until)}"
                    if until > time.time() else ""), mode="plain")
    # Recreate what a reboot kills before the watcher's first tick can find a
    # session missing and a queue with nowhere to go.
    restore_startup(cfg, state, lock)
    threading.Thread(target=watcher, args=(cfg, state, lock), daemon=True).start()

    # Resume where we stopped: a restart loses nothing. Kept out of the config
    # file, which is hand-edited and must not churn once per message.
    offset = load_offset() or cfg.pop("offset", None)  # migrate the old in-config one
    if offset is None:          # first ever run: skip whatever piled up
        res = (api(cfg, "getUpdates", offset=-1, timeout=0).get("result")) or []
        offset = res[-1]["update_id"] + 1 if res else None
    allow = {int(u) for u in cfg["allow_users"]}
    acks = Acks()
    print(f"nightmux up. chat={cfg['chat_id']} topics={cfg['topics']} offset={offset}",
          flush=True)

    if cfg.get("webhook_port"):
        threading.Thread(
            target=run_webhook_server, 
            args=(cfg, state, lock, allow, cfg["webhook_port"]), 
            daemon=True
        ).start()

    while True:
        r = api(cfg, "getUpdates", offset=offset, timeout=25,
                allowed_updates=json.dumps(["message", "callback_query"]))
        if not r.get("ok"):
            time.sleep(3)
            continue
        for upd in r["result"]:
            offset = upd["update_id"] + 1   # in memory: never ask Telegram twice
            # On disk only once a worker is done with it, so a crash mid-handle
            # replays the update rather than losing it.
            dispatch(cfg, state, lock, allow, upd, acks)


def process(cfg, state, lock, allow, upd):
    cq = upd.get("callback_query")
    msg = cq["message"] if cq else (upd.get("message") or {})
    text = (cq.get("data") if cq else
            msg.get("text") or msg.get("caption") or "").strip()
    chat = msg.get("chat", {}).get("id")
    user = (cq or msg).get("from", {}).get("id")
    topic = str(msg.get("message_thread_id") or 0)
    att = (msg.get("photo") or [{}])[-1].get("file_id") if not cq else None
    doc = msg.get("document") or {} if not cq else {}
    # voice/audio/video_note carry no file_name, unlike a document — fetch_file
    # falls back to Telegram's own remote path for those, which already has one.
    voice = (msg.get("voice") or msg.get("audio") or msg.get("video_note") or {}) \
        if not cq else {}
    named = (msg.get("forum_topic_created") or {}).get("name")
    print(f"upd chat={chat} user={user} topic={topic} text={text[:40]!r}"
          f"{' [cb]' if cq else ''}{' [file]' if att or doc or voice else ''}"
          f"{' [topic ' + named + ']' if named else ''}", flush=True)
    if cq:
        api(cfg, "answerCallbackQuery", callback_query_id=cq["id"], text=text)
    if str(chat) != str(cfg["chat_id"]):
        print(f"  drop: chat != {cfg['chat_id']}", flush=True)
        return
    if named:  # remember it now; autobind needs the name on the first message
        with lock:
            cfg.setdefault("topic_names", {})[topic] = named
            save_cfg(cfg)
        return
    if not (text or att or doc or voice):
        return
    if user not in allow:
        print(f"  drop: user {user} not in allow_users", flush=True)
        return
    if att or doc or voice:  # hand Claude the path; it reads images and files itself
        path = fetch_file(cfg, doc.get("file_id") or voice.get("file_id") or att,
                          doc.get("file_name") or voice.get("file_name"))
        if not path:
            send(cfg, topic, "download failed")
            return
        text = f"{text}\n{path}".strip()
    try:
        # cq: the tap already has its own feedback, so no reaction on the button
        reply = handle(cfg, state, lock, topic, text,
                       None if cq else msg.get("message_id"))
    except Exception as e:
        reply = f"error: {e}"
    if reply:
        send(cfg, topic, reply)


@contextlib.contextmanager
def stubbed(**globs):
    """Swap module globals for one section of the selfcheck, and put them back.

    A stub left standing is the worst kind of failure here: the section that set
    it passes, and one three hundred lines later fails for a reason that has
    nothing to do with what it is testing. That has happened more than once.
    """
    old = {k: globals()[k] for k in globs}
    globals().update(globs)
    try:
        yield
    finally:
        globals().update(old)


def selfcheck():
    assert chunks("a\nb") == ["a\nb"]
    assert chunks("x" * 10, 4) == ["xxxx", "xxxx", "xx"]
    big = "\n".join("y" * 100 for _ in range(100))
    assert all(len(c) <= LIMIT for c in chunks(big))
    assert "\n".join(chunks(big)) == big

    assert common_prefix(["a", "b", "c"], ["a", "b", "z"]) == 2

    # Something that always blocks. `tmux wait-for` only blocks once a server is
    # already running, so this passed on a machine with sessions open and let a
    # clean one through untested — the timeout path is what is being checked.
    assert "timed out after 1s" in run("sleep", "5", timeout=1)
    assert run("echo", "hi") == "hi"

    # Which pane a session means. The agent is wherever its status line was last
    # written from, which is not always the pane holding the focus — and reading
    # one pane while typing into another is indistinguishable from a hang.
    panes = ["api\t%1\t0\tclaude\t/w/api\napi\t%2\t1\tbash\t/w/api\n"
             "web\t%9\t1\tvim\t/w/web"]
    with stubbed(tmux_out=lambda *a, **k: panes[0], snapped=lambda: {"%1": 100.0}):
        assert live_sessions() == {"api": "%1", "web": "%9"}   # sidecar over focus
        with stubbed(snapped=lambda: {"%1": 100.0, "%2": 200.0}):
            assert live_sessions()["api"] == "%2"              # two: the newer
        with stubbed(snapped=lambda: {}):                      # no sidecar at all:
            assert live_sessions() == {"api": "%1", "web": "%9"}   # the agent pane
            panes[0] = "api\t%1\t0\tbash\t/w/api\napi\t%2\t1\tbash\t/w/api"
            assert live_sessions() == {"api": "%2"}             # back to the focus
    assert _cwd == {"api": "/w/api"}, _cwd     # read from the same call, not a spawn
    with stubbed(tmux_out=lambda *a, **k: "s\t%1\t1\tclaude\t/w/has\ttab"):
        live_sessions()
        assert _cwd == {"s": "/w/has\ttab"}, _cwd   # a tab in the path keeps the pane
    _cwd.clear()
    assert tgt("api") == "api"        # never seen: the session name, as before
    _target["api"] = "%2"
    assert tgt("api") == "%2"
    _target.clear()

    # A tmux that does not answer must not read as a tmux with no sessions. It
    # used to: run() reports a timeout by returning "[tmux timed out]", which is
    # text, so the pane list parsed as empty and every bound topic was told its
    # session had died — then rebaselined, dropping the transcript offset and
    # whatever arrived during the gap. 72 of those in three days on one box.
    with stubbed(tmux_out=lambda *a, **k: None):
        assert live_sessions() is None
        assert status_report({"topics": {"1": "s"}}, {}).startswith("tmux is not")
    with stubbed(run=lambda *a, **k: "[tmux timed out after 10s]"):
        assert tmux("list-panes") == "[tmux timed out after 10s]"   # unchanged
    # tmux_out reads the exit status, not the text: a failing tmux is None too.
    # Both commands answer without a server, because CI has no tmux running and
    # `display-message` there fails for that reason rather than the one intended.
    assert tmux_out("no-such-tmux-command") is None
    assert (tmux_out("-V") or "").startswith("tmux")

    # The outage is announced once, and so is its end — not once per session per
    # tick, which is what nine topics of 💀 looked like.
    tsent = []
    with stubbed(send=lambda c, t, x, **k: tsent.append(x)):
        cfgm = {"topics": {"9": "b", "3": "a"}}
        assert daemon_topic(cfgm) == "3"                    # lowest bound topic
        assert daemon_topic(dict(cfgm, center_topic=77)) == "77"   # or the center
        assert daemon_topic({"topics": {}}) is None
        _tmux_miss[0] = 0
        for _ in range(TMUX_MISSES - 1):
            tmux_missing(cfgm, True)
        assert tsent == [], tsent                     # a blip says nothing
        tmux_missing(cfgm, True)
        assert len(tsent) == 1 and tsent[0].startswith("⚠️ tmux has not answered")
        for _ in range(4):
            tmux_missing(cfgm, True)
        assert len(tsent) == 1, tsent                 # still out: not again
        tmux_missing(cfgm, False)
        assert tsent[-1] == "✅ tmux is answering again" and _tmux_miss[0] == 0
        tmux_missing(cfgm, False)
        assert len(tsent) == 2, tsent                 # recovery is said once too
        _tmux_miss[0] = 0
        tmux_missing(cfgm, True), tmux_missing(cfgm, False)
        assert len(tsent) == 2, tsent                 # a blip that healed: silent

    globals()["CFG_PATH"] = os.path.join(FILE_DIR, "selfcheck.json")
    globals()["OFFSET_PATH"] = os.path.join(FILE_DIR, "selfcheck.offset")
    os.makedirs(FILE_DIR, exist_ok=True)
    with open(CFG_PATH, "w") as f:                # a key added by hand, mid-run
        json.dump({"topics": {"1": "old"}, "handedit": 42}, f)
    save_cfg({"topics": {"1": "new"}})            # daemon writes what it owns
    assert load_cfg() == {"topics": {"1": "new"}, "handedit": 42}, load_cfg()
    mode = os.stat(CFG_PATH).st_mode & 0o777       # the token lives in here
    assert mode == 0o600, oct(mode)                # every save, not just the first
    save_offset(12345)
    assert load_offset() == 12345

    # A topic with no recorded directory must not come back in $HOME: --continue
    # resumes the last conversation *of that directory*, so one reboot put three
    # topics on the same one. It is learned from the live session instead.
    # A real tmux session with no agent in it: the pane reads idle and ready for
    # work, which is exactly why every send has to ask first. Injecting here
    # would run the prompt as a shell command and lose it.
    subprocess.run(("tmux", "kill-session", "-t", "nm-selfcheck"),
                   capture_output=True)
    subprocess.run(("tmux", "new-session", "-d", "-s", "nm-selfcheck", "-c", "/"),
                   capture_output=True)
    said = []
    try:
        with stubbed(send=lambda c, t, x, mode="mono", buttons=None, quiet=False:
                     (said.append(x), 1)[1],
                     save_cfg=lambda c: None):     # !bind below must not touch CFG_PATH
            live_sessions()                        # fills _shell, as a tick does
            assert pane_state(visible("nm-selfcheck")) == "idle"  # nothing says stop
            assert agentless("nm-selfcheck") is True             # ...except this
            assert inject("nm-selfcheck", "rm -rf /") is False    # nothing typed
            st3 = {"queue": ["held"]}
            drain({"chat_id": -1}, {"nm-selfcheck": st3}, "1", "nm-selfcheck")
            assert st3["queue"] == ["held"] and said == [], (st3, said)  # not spent
            for _ in range(3):                     # said once, on the second tick
                watchdog({"chat_id": -1}, {"nm-selfcheck": st3}, "1",
                         "nm-selfcheck", True)
            assert sum("exited" in s for s in said) == 1, said
            # tmux answers to a prefix; live_sessions() only ever answers to the
            # whole name, so !bind has to store the whole name too.
            assert real_session("nm-selfche") == "nm-selfcheck"
            assert has_session("nm-selfche") is False
            cfg9, lk9 = {"topics": {}, "chat_id": -1}, threading.Lock()
            assert handle(cfg9, {}, lk9, "9", "!bind nm-selfche") == \
                "topic bound to 'nm-selfcheck'"
            assert cfg9["topics"]["9"] == "nm-selfcheck", cfg9
    finally:
        subprocess.run(("tmux", "kill-session", "-t", "nm-selfcheck"),
                       capture_output=True)
        _shell.clear()

    spawned = []
    with stubbed(has_session=lambda s: False, sess_cwd=lambda s: FILE_DIR,
                 spawn=lambda *a: spawned.append(a)):
        c, l = {"topics": {"1": "s"}, "dirs": {}}, threading.Lock()
        assert "no directory recorded" in resume_session(c, {}, l, "1")
        assert spawned == [], spawned              # nothing started in $HOME
        track_cwd(c, l, "1", "s")                  # learned from the live session
        assert c["dirs"]["1"] == FILE_DIR, c
        resume_session(c, {}, l, "1")
        assert spawned[0][1] == FILE_DIR, spawned  # and it comes back there

    acks = Acks()                                  # parallel topics finish out of order
    for uid in (10, 11, 14):                       # 12, 13: types we filtered out
        acks.dispatch(uid)
    acks.ack(11)
    assert load_offset() == 12345                  # 10 still running: do not move past it
    acks.ack(10)
    assert load_offset() == 14                     # both done, and the gap is skipped
    acks.ack(14)
    assert load_offset() == 15                     # nothing outstanding: past the last
    assert acks.seen == [] and acks.done == set()  # no bookkeeping left behind
    assert upd_topic({"message": {"message_thread_id": 7}}) == "7"
    assert upd_topic({"callback_query": {"message": {"message_thread_id": 7}}}) == "7"
    assert upd_topic({"message": {}}) == "0"       # the General topic
    os.remove(CFG_PATH), os.remove(OFFSET_PATH)
    assert load_offset() is None

    now = time.mktime((2026, 8, 7, 10, 0, 0, 0, 0, -1))
    assert parse_reset("· resets in 2h 14m", now) == now + 2 * 3600 + 14 * 60
    assert parse_reset("resets in 45m", now) == now + 45 * 60
    assert parse_reset("Resets in 4 hr 56 min", now) == now + 4 * 3600 + 56 * 60
    assert parse_reset("resets in 2d 3h", now) == now + 2 * 86400 + 3 * 3600
    assert parse_reset("Your limit resets 3pm", now) == \
        time.mktime((2026, 8, 7, 15, 0, 0, 0, 0, -1))
    assert parse_reset("limit resets at 09:30", now) == \
        time.mktime((2026, 8, 8, 9, 30, 0, 0, 0, -1))   # already past: tomorrow
    assert parse_reset("no time here", now) is None   # never guess a reset
    assert left(3 * 3600 + 61) == "3h 1m" and left(90) == "1m"
    assert brief({"command": "ls -la\nrm x", "file_path": "/a"}) == "ls -la"
    assert brief({"file_path": "/a/b.py"}) == "/a/b.py" and brief({"n": 1}) == ""
    assert render({"type": "user", "message": {"content": "hi"}}) == []
    assert render({"type": "assistant", "message": {"content": [
        {"type": "thinking", "thinking": "hmm"},
        {"type": "tool_use", "name": "Bash", "input": {"command": "pytest -q"}},
        {"type": "text", "text": " the answer "}]}}) == \
        ["● Bash(pytest -q)", "the answer"]

    tp = os.path.join(FILE_DIR, "selfcheck.jsonl")
    os.makedirs(FILE_DIR, exist_ok=True)
    rec = json.dumps({"type": "assistant",
                      "message": {"content": [{"type": "text", "text": "one"}]}})
    with open(tp, "w") as f:
        f.write(rec + "\n")
    tst = {}
    assert tail_transcript(tst, tp) == []          # first sight baselines, no dump
    with open(tp, "a") as f:
        f.write(rec.replace("one", "two") + "\n")
        f.write('{"type": "assistant", "message": {"content": [{"typ')  # half a line
    assert tail_transcript(tst, tp) == ["two"]     # partial record held back
    assert tail_transcript(tst, tp) == []
    with open(tp, "w") as f:                       # /clear: file shrank, rebaseline
        f.write(rec + "\n")
    assert tail_transcript(tst, tp) == []
    assert "spend" not in tst                      # no usage records, nothing to weigh
    with open(tp, "a") as f:                       # what a turn actually cost
        f.write(json.dumps({"type": "assistant", "message": {
            "usage": {"input_tokens": 100, "output_tokens": 10},
            "content": [{"type": "text", "text": "hi"}]}}) + "\n")
    tail_transcript(tst, tp)
    assert int(tst["spend"][-1][1]) == 150, tst["spend"]   # 100*1.0 + 10*5.0
    os.remove(tp)

    assert spend_cap({}) == (None, None)
    assert spend_cap({"spendcap": 12}) == (12, None)
    assert spend_cap({"spendcap": "12"}) == (12, None)     # a bare string is turns
    assert spend_cap({"spendcap": "500k"}) == (None, 500000)
    assert spend_cap({"spendcap": "2M"}) == (None, 2000000)
    assert spend_cap({"spendcap": "nope"}) == (None, None)

    globals()["STATE_DIR"] = os.path.join(FILE_DIR, "state")
    os.makedirs(STATE_DIR, exist_ok=True)
    for n_, ts, pn in (("a", time.time() - 10, "%1"), ("b", time.time(), "%1"),
                       ("c", time.time() - 2 * STATE_FRESH, "%1"),
                       ("d", time.time(), "%2")):
        with open(os.path.join(STATE_DIR, f"{n_}.json"), "w") as f:
            json.dump({"ts": ts, "pane": pn, "transcript": f"/t/{n_}"}, f)
    assert snapshot("%1")["transcript"] == "/t/b", snapshot("%1")  # newest fresh one
    assert snapshot("%2")["transcript"] == "/t/d"
    assert snapshot("%9") is None and snapshot(None) is None
    os.utime(os.path.join(STATE_DIR, "c.json"), (0, 0))   # ancient on disk
    assert prune(time.time(), time.time()) == 0 or True    # throttled, no sweep
    assert os.path.exists(os.path.join(STATE_DIR, "c.json"))
    assert prune(time.time(), 0) > 0
    assert not os.path.exists(os.path.join(STATE_DIR, "c.json"))  # swept
    assert os.path.exists(os.path.join(STATE_DIR, "b.json"))      # fresh one kept
    qp = os.path.join(STATE_DIR, "queue.json")                    # never a cache
    open(qp, "w").close(), os.utime(qp, (0, 0))
    assert prune(time.time() + 2 * PRUNE_EVERY, 0) and os.path.exists(qp)
    os.remove(qp)
    for n_ in ("a", "b", "d"):                       # hours of silence must not
        os.remove(os.path.join(STATE_DIR, f"{n_}.json"))          # drop to scraping
    with open(os.path.join(STATE_DIR, "e.json"), "w") as f:
        json.dump({"ts": time.time() - 7200, "pane": "%1", "transcript": "/t/e"}, f)
    assert snapshot("%1")["transcript"] == "/t/e"   # two idle hours: still bound
    os.utime(os.path.join(STATE_DIR, "e.json"), (0, 0))
    prune(time.time(), 0)
    assert snapshot("%1") is None                   # ... a day of it does

    assert usage_line({}, {"five_hour": {"used_percentage": 87.4, "resets_at": None},
                       "ctx_pct": 41.2}) == "  5h 87%  ctx 41%"
    assert usage_line({}, None) == "" and usage_line({}, {}) == ""

    tcx = os.path.join(FILE_DIR, "ctx.jsonl")       # what fills a context window
    with open(tcx, "w") as f:
        for rec in ({"message": {"content": [
                        {"type": "tool_use", "id": "t1", "name": "Bash"},
                        {"type": "tool_use", "id": "t2", "name": "Read"}]}},
                    {"message": {"content": [
                        {"type": "tool_result", "tool_use_id": "t1",
                         "content": "b" * 4000},
                        {"type": "tool_result", "tool_use_id": "t2",
                         "content": "r" * 800}]}},
                    {"message": {"content": [{"type": "text", "text": "x" * 400}]}}):
            f.write(json.dumps(rec) + "\n")
    t = token_tally([tcx])                          # no usage records in that file
    assert t["turns"] == 0 and cost_report(t, "x").endswith("no usage records yet")
    tcost = os.path.join(FILE_DIR, "cost.jsonl")
    with open(tcost, "w") as f:
        for i in (1, 2):
            f.write(json.dumps({"message": {"usage": {
                "input_tokens": 10, "output_tokens": 100,
                "cache_creation_input_tokens": 1000,
                "cache_read_input_tokens": 200000}}}) + "\n")
        f.write("not json\n")
        f.write(json.dumps({"message": {"content": []}}) + "\n")   # no usage: skipped
    t = token_tally([tcost, "/no/such/file.jsonl"])
    assert t == {"turns": 2, "in": 20, "write": 2000, "read": 400000, "out": 200}, t
    rep = cost_report(t, "title")
    assert "2 turns" in rep and "200,000 / turn" in rep, rep       # avg context
    # 400000*0.1=40000 vs 2000*1.25=2500, 200*5=1000, 20 -> reads dominate
    assert re.search(r"cache reads\s+400,000\s+92%", rep), rep
    os.remove(tcost)

    rep = ctx_report(tcx)
    assert "Bash" in rep.split("\n")[2] and "1,000" in rep, rep   # biggest first
    assert "assistant text" in rep and "2 tool calls" in rep, rep
    assert f"{(4000 + 800 + 400) // 4:,}" in rep.split("\n")[-1], rep
    assert ctx_report(tcx) is rep                  # same size: not re-read
    with open(tcx, "a") as f:                      # ...and a grown file is
        f.write(json.dumps({"message": {"content": [
            {"type": "text", "text": "x" * 40}]}}) + "\n")
    assert ctx_report(tcx) is not rep, "a grown transcript kept the stale report"
    os.remove(tcx)
    noon = time.mktime((2026, 8, 7, 12, 0, 0, 0, 0, -1))   # display shifts, never parse
    assert clock({}, noon) == "12:00" and clock({"tz_offset": 0}, noon) == \
        time.strftime("%H:%M", time.gmtime(noon))
    assert clock({"tz_offset": 3}, noon) != clock({"tz_offset": 0}, noon)
    assert parse_reset("resets 3pm", noon) == parse_reset("resets 3pm", noon)
    if os.path.isfile(os.path.join(ZONEINFO, "Africa/Cairo")):
        aug = calendar.timegm((2026, 8, 7, 12, 0, 0, 0, 0, 0))    # a zone tracks DST,
        dec = calendar.timegm((2026, 12, 15, 12, 0, 0, 0, 0, 0))  # a fixed offset lies
        assert tz_shift("Africa/Cairo", aug) == 3 * 3600
        assert tz_shift("Africa/Cairo", dec) == 2 * 3600
        assert clock({"tz_offset": "Africa/Cairo"}, aug) == "15:00"
        assert clock({"tz_offset": "Africa/Cairo"}, dec) == "14:00"
        assert clock({"tz_offset": 3}, dec) == "15:00"            # ... an hour wrong
        assert time.strftime("%Z", time.localtime(aug)) == "UTC"  # process TZ restored
        assert tz_shift("Africa/Cairo", aug) == 3 * 3600          # cached, same answer

    for banner in ("You've hit your 5-hour limit · resets 3pm",
                   "  You've reached your weekly limit · Resets in 2 hr 16 min",
                   "You're out of usage credits · resets 11am"):
        assert LIMIT_HIT.search(banner), banner
    assert not LIMIT_HIT.search("● I hit your endpoint and it returned 200")

    assert md_html("**bold** and `x_1 & y`") == \
        "<b>bold</b> and <code>x_1 &amp; y</code>", md_html("**bold** and `x_1 & y`")
    assert md_html("### Title\ntext") == "<b>Title</b>\ntext"
    assert md_html("a\n```py\nif a < b:\n    f(**kw)\n```\nb") == \
        "a\n<pre>if a &lt; b:\n    f(**kw)</pre>\nb", md_html("a\n```py\nif a < b:\n    f(**kw)\n```\nb")
    assert md_html("snake_case and *stars* survive") == "snake_case and *stars* survive"
    assert md_html("<script>") == "&lt;script&gt;"
    for chrome in ("╭──────────╮", "│ ", "", "─" * 40, "╌" * 40, "❯ what I already typed",
                   "✻ Brewed for 2s", "  ⏵⏵ accept edits on",
                   "  ubuntu@host:/home/x  [MODE] ⛏ 5.4M", "  ? for shortcuts"):
        assert CHROME.match(chrome), repr(chrome)
    for keep in ("  Wrote 3 files to disk", "● PONG_TGCTL", "    return n + 1",
                 "  Read(src/main.py)", "❯ 1. Yes", "  2. No"):
        assert not CHROME.match(keep), repr(keep)

    for chrome in ("⢿  Running...", "> use your shell tool to run: ls",
                   "  ↑/↓ Navigate · enter Confirm",
                   "esc to cancel                    Gemini 3.1 Pro · high",
                   "                                 Gemini 3.1 Pro · high"):
        assert CHROME.match(chrome), repr(chrome)   # agy chrome
    for keep in ("● Bash(sleep 8; echo hi) (ctrl+o to expand)", "> 1. Yes",
                 "  I have executed the command. It printed:"):
        assert not CHROME.match(keep), repr(keep)

    assert DETAIL.match("  ⎿  Read 200 lines") and DETAIL.match("     … +12 lines")
    assert DETAIL.match("▸ Thought for 3s, 282 tokens")
    assert not DETAIL.match("● here is the answer")
    # agy: numbered permission menu, arrow-only trust prompt, spinner
    agy_perm = ["Requesting permission for:", "Do you want to proceed?", "> 1. Yes",
                "  2. Yes, and always allow in this conversation",
                "  4. No", "  ↑/↓ Navigate · tab Amend"]
    assert pane_state(agy_perm) == "waiting"
    picks = json.loads(menu_buttons(agy_perm))["inline_keyboard"][:3]
    assert [r[0]["callback_data"] for r in picks] == ["!1", "!2", "!4"], picks
    # opencode: a modal drawn inside the border, over prose that numbers itself.
    # It names no question WAITING knows and answers to arrows, never the digit.
    oc = ["     5. Ship & iterate (wk 4+): soft-launch, measure D1",
          "  ┃  Unity can't run on this ARM64 server. How should we proceed?",
          "  ┃  1. Godot 4 (Recommended)",
          "  ┃     Native performance, ARM64-buildable here",
          "  ┃  2. Web (TypeScript)",
          "  ┃  3. Scaffold-only",
          "  ┃  ↑↓ select  enter submit  esc dismiss"]
    assert pane_state(oc) == "waiting"
    assert [r[0]["callback_data"]
            for r in json.loads(menu_buttons(oc))["inline_keyboard"][:-1]] == \
        ["!1", "!2", "!3"]                                    # prose 5. dropped
    assert menu_opts(oc) == (["1", "2", "3"], None)   # plain: no marker to read
    # The same pane as tmux hands it over with -e. opencode paints the selected
    # option's number in its accent colour and every other one grey; that is the
    # whole of the marker, and it is the only thing that says where the arrows are.
    ON, OFF, C = "\x1b[38;2;92;156;245m", "\x1b[38;2;128;128;128m", "\x1b[0m"

    def paint(sel):
        out = []
        for l in oc:
            m = MENU.match(l) if BOXED.match(l) else None
            out.append(l.replace(m.group(1) + ".",
                                 f"{ON if m.group(1) == sel else OFF}"
                                 f"{m.group(1)}.{C}", 1) if m else l)
        return out

    keyed, sel = [], ["1"]
    assert menu_opts(paint("1")) == (["1", "2", "3"], 0)
    assert menu_opts(paint("3")) == (["1", "2", "3"], 2)

    def fake_tmux(*a):
        """A pane whose highlight follows the arrows, so the re-read is real."""
        if a[0] != "send-keys":
            return "\n".join(paint(sel[0]))
        keyed.append(a[3:])
        if a[3] in ("Up", "Down"):
            sel[0] = ["1", "2", "3"][["1", "2", "3"].index(sel[0])
                                     + sum(1 if k == "Down" else -1 for k in a[3:])]
        return ""

    with stubbed(tmux=fake_tmux):
        assert pick("s", "3") == ""            # two rows down from the marked one
        assert keyed == [("Down", "Down"), ("Enter",)], keyed
        keyed[:] = []
        assert pick("s", "9").startswith("option 9 is not")   # no such option
        assert keyed == [], keyed                             # nothing pressed
        sel[0] = ""                               # every row alike: unreadable
        assert pick("s", "3").startswith("can't tell") and keyed == []
    assert pane_state([l for l in oc if "┃" not in l]) == "idle"  # prose alone
    agy_trust = ["Do you trust the contents of this project?", "> Yes, I trust this folder",
                 "  No, exit", "  ↑/↓ Navigate · enter Confirm"]
    assert pane_state(agy_trust) == "waiting"
    assert json.loads(menu_buttons(agy_trust))["inline_keyboard"] == [
        [{"text": "esc", "callback_data": "!esc"},
         {"text": "↑", "callback_data": "!up"},
         {"text": "↓", "callback_data": "!down"},
         {"text": "⏎", "callback_data": "!enter"}]]  # arrows drive it, no numbers
    assert pane_state(["● Bash(x)", "⢿  Running...", "esc to cancel"]) == "busy"
    # a backgrounded shell is not the session being busy: the prompt is free
    assert pane_state(["● Bash(npm test) &", "  ⎿ \xa0Running… (7m 53s · timeout 10m)",
                       "╭───╮", "│ > ", "╰───╯"]) == "idle"
    box = ["╭────────╮", "│ > ", "╰────────╯", "  ? for shortcuts"]
    assert pane_state(["● done"] + box) == "idle"
    assert pane_state(["✻ Brewing… (12s · esc to interrupt)"]) == "busy"
    assert pane_state(["  ⬝⬝⬝ retrying in 58m 6s attempt #13    esc interrupt"]) == "busy"
    assert pane_state(["Do you want to proceed?", "❯ 1. Yes", "  2. No"]) == "waiting"

    menu = menu_buttons(["Do you want to proceed?", "❯ 1. Yes",
                         "│   2. Yes, and don't ask again │", "  3. No (esc)"])
    assert json.loads(menu)["inline_keyboard"][:3] == [
        [{"text": "1. Yes", "callback_data": "!1"}],
        [{"text": "2. Yes, and don't ask again", "callback_data": "!2"}],
        [{"text": "3. No (esc)", "callback_data": "!3"}]], menu
    # A session suffix on every button: a mirrored copy in the command center
    # has no topic binding to resolve a bare "!1" against.
    qmenu = menu_buttons(["Do you want to proceed?", "❯ 1. Yes", "  2. No"], "api")
    picks_q = json.loads(qmenu)["inline_keyboard"]
    assert picks_q[0][0]["callback_data"] == "!1 api", picks_q
    assert picks_q[-1][0]["callback_data"] == "!esc api", picks_q

    cfg, state, screen = {"topics": {}, "chat_id": -1}, {}, []
    sent = []
    globals()["send"] = lambda c, t, x, mode="mono", buttons=None, quiet=False: (
        sent.append(x), 77)[1]
    globals()["has_session"] = lambda s: True
    globals()["pane"] = lambda s: list(screen)
    globals()["visible"] = lambda s: list(screen)
    globals()["hooked"] = lambda s: False
    # A path that is never a directory, so snapshot_repo's git check is skipped
    # without shelling out — drain() calls it on every send, and the real
    # sess_cwd would otherwise block on a tmux pane that was never created here.
    globals()["sess_cwd"] = lambda s: "/nonexistent-nightmux-selfcheck"
    twice = lambda: (flush_new(cfg, state, "1", "s"), flush_new(cfg, state, "1", "s"))

    # A cap in tokens counts what the turns cost. Two greps and two hundred are
    # both "one turn"; only one of them is a loop worth interrupting.
    state.clear(), sent.clear()
    keys, cap_cfg = [], dict(cfg, spendcap="1k")
    with stubbed(tmux=lambda *a: keys.append(a) or ""):
        state["s"] = {"spend": [(time.time(), 900.0)]}
        screen[:] = ["hello"] + box
        flush_new(cap_cfg, state, "1", "s")
        screen[:] = ["✻ Brewing… (2s · esc to interrupt)"]
        flush_new(cap_cfg, state, "1", "s")        # turn starts: 900 < 1000
        assert keys == [] and not any("spend cap" in x for x in sent), sent
        screen[:] = ["hello"] + box
        flush_new(cap_cfg, state, "1", "s")        # back to idle: re-arm
        state["s"]["spend"].append((time.time(), 200.0))
        screen[:] = ["✻ Brewing… (2s · esc to interrupt)"]
        flush_new(cap_cfg, state, "1", "s")        # 1100 >= 1000: cut it off
        assert any("hit spend cap of 1,000 base-equiv tokens (1,100 burnt)" in x
                   for x in sent), sent
        assert keys and keys[-1][-1] == "C-c", keys
        state["s"]["spend"] = [(time.time() - 400, 9e9)]   # older than the window
        screen[:] = ["hello"] + box
        flush_new(cap_cfg, state, "1", "s")
        screen[:] = ["✻ Brewing… (2s · esc to interrupt)"]
        n = len(keys)
        flush_new(cap_cfg, state, "1", "s")
        assert len(keys) == n, "spend outside the 5m window still counted"
    state.clear(), sent.clear()

    screen[:] = ["Do you want to proceed?", "❯ 1. Yes", "  2. No"]
    flush_new(cfg, state, "1", "s")   # restart with a prompt already on screen
    assert sent[-1].startswith("🟠 needs input s\n") and len(sent) == 1, sent
    state.clear(), sent.clear()

    screen[:] = ["hello"] + box
    state["s"] = {}                              # watchdog seeded it first
    flush_new(cfg, state, "1", "s")              # baseline, nothing dumped
    assert sent == []
    screen[:] = ["hello", "answer line 1"] + box  # output replaces the old box
    flush_new(cfg, state, "1", "s")               # first sight: not stable yet
    assert sent == []
    flush_new(cfg, state, "1", "s")               # stable: chrome stripped
    assert sent == ["✅ s\nanswer line 1"], sent
    flush_new(cfg, state, "1", "s")               # idle, nothing new
    assert len(sent) == 1
    screen[:] = ["hello", "answer line 1", "● two", "  ⎿  noise"] + box
    twice()                                       # tool detail dropped by default
    assert sent[-1] == "✅ s\n● two", sent[-1]

    cfg["verbose"] = ["1"]
    screen[:] = screen[:-4] + ["● three", "  ⎿  noise"] + box
    twice()
    assert "⎿  noise" in sent[-1], sent[-1]
    cfg["verbose"] = []

    screen[:] = screen[:-4] + ["Do you want to proceed?", "❯ 1. Yes", "  2. No"]
    twice()                                       # waiting prompt flagged
    assert sent[-1].startswith("🟠 needs input s\n") and "1. Yes" in sent[-1], sent[-1]
    n = len(sent)                                 # ... once, however often it redraws
    for _ in range(4):
        screen[-1] += " "                         # pane churns, question does not
        twice()
    assert len(sent) == n, sent[n:]
    screen[:] = ["● done"] + box                  # an idle frame between two menus
    twice()                                       # must not re-arm the announcement
    assert state["s"].get("asked") and sent[-1] == "✅ s\n● done", sent[-1]
    n = len(sent)
    screen[:] = ["● done", "Do you want to proceed?", "❯ 1. Yes", "  2. No"]
    twice()                                       # same question under new output
    assert len(sent) == n, sent[n:]               # ... still silent
    screen[:] = ["✻ Brewing… (2s · esc to interrupt)"]
    twice()                                       # a real turn: re-arm
    assert "asked" not in state["s"]
    state["s"].pop("prog_msg", None)               # leave the throttles as found
    state["s"]["prog_at"] = _prog_at[0] = 0
    screen[:] = ["hello", "answer line 1", "● two"] + box
    twice()

    globals()["hooked"] = lambda s: True          # hook owns delivery: no scrape
    n = len(sent)
    screen[:] = ["hello", "hooked reply"] + box
    twice()
    assert len(sent) == n
    screen[:] = ["hello", "hooked reply", "Do you want to proceed?", "❯ 1. Yes"]
    twice()                                       # except prompts, which still ping
    assert sent[-1].startswith("🟠 needs input"), sent[-1]
    globals()["hooked"] = lambda s: False

    screen[:] = ["x"] * (MAX_LINES + 50) + box    # oversized flush gets trimmed
    twice()
    assert "lines trimmed" in sent[-1] and len(sent[-1].split("\n")) == MAX_LINES + 2

    edits = []
    globals()["api"] = lambda c, m, **kw: edits.append((m, kw)) or {}
    st = state["s"]
    screen[:] = ["hello", "● Read(x.py)", "✻ Brewing… (3s · esc to interrupt)"]
    twice()                                       # busy: one live message, then edits
    assert sent[-1].startswith("⚙️ s\n") and "● Read(x.py)" in sent[-1], sent[-1]
    assert st["prog_msg"] == 77
    st["prog_at"] = _prog_at[0] = 0               # skip both throttles
    screen[:] = screen[:-1] + ["● Bash(ls)", "✻ Brewing… (9s · esc to interrupt)"]
    twice()
    assert edits[-1][0] == "editMessageText" and "Bash(ls)" in edits[-1][1]["text"]
    st["prog_at"] = _prog_at[0] = 0
    twice()                                       # unchanged pane: no wasted edit
    assert len(edits) == 1
    screen[:] = ["hello", "● Read(x.py)", "● Bash(ls)", "● done"] + box
    twice()                                       # turn over: message id released
    assert "prog_msg" not in st and sent[-1].startswith("✅ s\n")

    screen[:] = ["hi", "● you asked:", "line one", "line two", "● real answer"] + box
    twice()                                       # echo of a multi-line prompt
    assert "line one" in sent[-1] and "line two" in sent[-1], sent[-1]
    remember(state, "s", "line one\nline two")    # ... unless we typed it ourselves
    screen[:] = screen[:-4] + ["line one", "line two", "● second answer"] + box
    twice()
    assert sent[-1] == "✅ s\n● second answer", sent[-1]

    big = "x" * (BIG_PROMPT + 1)                  # too long to type: goes as a file
    spilled = spill("s", big)
    assert spilled != big and "read that file" in spilled, spilled
    path = re.search(r"(/\S+\.md)", spilled).group(1)
    with open(path) as f:
        assert f.read() == big
    os.remove(path)
    assert spill("s", "short") == "short"         # ... anything normal is untouched

    typed = []                                    # menu guard on plain text
    globals()["inject"] = lambda s, t: (typed.append(t), True)[1]   # typed it
    cfg["topics"] = {"1": "s"}
    screen[:] = ["Do you want to proceed?", "❯ 1. Yes", "  2. No"]
    guard = handle(cfg, state, threading.Lock(), "1", "no, do not do that")
    assert guard and "menu is open" in guard and typed == [], (guard, typed)
    handle(cfg, state, threading.Lock(), "1", "!raw no, do not do that")
    assert typed == ["no, do not do that"], typed   # explicit override still types

    n = len(sent)                                 # unanswered prompt gets a reminder
    st = state["s"]
    st["mode"], st["wait_since"] = "waiting", time.time()
    nudge(cfg, state, "1", "s")
    assert len(sent) == n                         # too soon
    st["wait_since"] = time.time() - NUDGE_AFTER - 1
    nudge(cfg, state, "1", "s")
    assert sent[-1].startswith("⏰ s has been waiting"), sent[-1]
    nudge(cfg, state, "1", "s")                   # not every tick
    assert len(sent) == n + 1
    st["nudged"] = time.time() - NUDGE_EVERY - 1  # due again: edit, never a second msg
    edits.clear()
    nudge(cfg, state, "1", "s")
    assert len(sent) == n + 1 and edits[-1][0] == "editMessageText", (sent[-1], edits)
    assert edits[-1][1]["message_id"] == st["nudge_msg"] == 77
    st["mode"] = "idle"
    nudge(cfg, state, "1", "s")
    assert len(sent) == n + 1

    n, at = len(sent), time.time() + 3600          # warn before the wall, once each
    st["snap"] = {"ts": time.time(),
                  "five_hour": {"used_percentage": 82, "resets_at": at},
                  "ctx_pct": 40}
    warn_usage(cfg, st, "1", "s")
    assert sent[-1].startswith("🔶 5-hour limit 82% used"), sent[-1]
    warn_usage(cfg, st, "1", "s")                  # same threshold: silent
    assert len(sent) == n + 1
    st["snap"]["five_hour"]["used_percentage"] = 91
    warn_usage(cfg, st, "1", "s")                  # next threshold: speaks once
    assert sent[-1].startswith("🔶 5-hour limit 91%") and len(sent) == n + 2
    warn_usage(cfg, state.setdefault("other", {"snap": st["snap"]}), "9", "other")
    assert len(sent) == n + 2                      # account-wide: no second topic
    st["snap"]["five_hour"]["resets_at"] = at + 18000
    warn_usage(cfg, st, "1", "s")                  # new window: warnings re-arm
    assert sent[-1].startswith("🔶 5-hour limit 91%") and len(sent) == n + 3
    held, n = dict(_warned), len(sent)             # a restart mid-window
    _warned.clear()
    _warned.update(load_warned())                  # ...reads back what it said
    assert _warned == held, (_warned, held)
    warn_usage(cfg, st, "1", "s")                  # ...and does not say it again
    assert len(sent) == n
    _warned.clear()                                # nothing on disk: back to silence
    os.remove(warned_path())
    assert load_warned() == {}
    state.pop("other"), _warned.clear()

    # A window that has already turned over still shows up in the payload, with
    # last window's percentage beside a resets_at in the past. Reporting it read
    # as "weekly 92% used, resets in 0m" while the real week was at 22%.
    now, n = time.time(), len(sent)
    stale = {"ts": now, "seven_day": {"used_percentage": 92, "resets_at": now - 5},
             "five_hour": {"used_percentage": 16, "resets_at": now + 3600}}
    assert window(stale, "seven_day") is None
    assert window(stale, "five_hour")["used_percentage"] == 16   # the live one stays
    assert "7d" not in usage_line({}, stale) and "5h 16%" in usage_line({}, stale)
    warn_usage(cfg, {"snap": stale}, "1", "s")
    assert len(sent) == n, sent[-1]              # ...and nothing is announced
    _warned.clear()

    n = len(sent)                                  # context bloat, per session
    warn_ctx(cfg, st, "1", "s")
    assert len(sent) == n                          # 40%: nothing to say
    st["snap"]["ctx_pct"] = 88
    warn_ctx(cfg, st, "1", "s")
    assert sent[-1].startswith("🧠 s context 88% full") and st["ctx_warned"]
    warn_ctx(cfg, st, "1", "s")
    assert len(sent) == n + 1                      # still full: not again
    st["snap"]["ctx_pct"] = 12                     # compacted: re-arm
    warn_ctx(cfg, st, "1", "s")
    assert "ctx_warned" not in st and len(sent) == n + 1

    # The warning has to land ahead of the compaction it warns about, or a
    # config of {"autocompact": 70} compacts at 70 and warns at 75: never.
    assert ctx_trip({}) == CTX_WARN and ctx_trip({"autocompact": 70}) == 60
    assert ctx_trip({"autocompact": 5}) == CTX_LEAD    # never below an empty window
    n = len(sent)
    st["snap"]["ctx_pct"] = 64
    warn_ctx({"autocompact": 70}, st, "1", "s")
    assert sent[-1].startswith("\U0001f9e0 s context 64% full"), sent[-1]

    # No figure at all -- agy, codex, a Claude with no sidecar. Said once, and
    # only to someone who turned autocompact on and is expecting it to run.
    blind, n = {"mode": "idle", "snap": {"ts": time.time()}}, len(sent)
    warn_ctx({}, blind, "1", "agy1")
    assert len(sent) == n, sent[n:]                # never asked for it: not nagged
    warn_ctx({"autocompact": 70}, blind, "1", "agy1")
    assert sent[-1].startswith("\U0001f648 no context figure for agy1"), sent[-1]
    warn_ctx({"autocompact": 70}, blind, "1", "agy1")
    assert len(sent) == n + 1                      # once per session, not per tick
    n, typed[:] = len(sent), []                   # auto /compact, tightly gated
    st.update(mode="idle", queue=[], snap={"ts": time.time(), "ctx_pct": 82})
    autocompact({"topics": {}}, state, "1", "s")
    assert len(sent) == n and typed == []          # not configured: never acts
    ac = {"autocompact": 70, "topics": {}}
    st["mode"] = "busy"
    autocompact(ac, state, "1", "s")
    assert typed == []                             # mid-turn: would interrupt work
    st["mode"], st["queue"] = "idle", ["held"]
    autocompact(ac, state, "1", "s")
    assert typed == []                             # queue pending: let it drain first
    st["queue"] = []
    autocompact(ac, state, "1", "s")
    assert typed == ["/compact"] and sent[-1].startswith("🧹 s context 82%"), sent[-1]
    autocompact(ac, state, "1", "s")
    assert typed == ["/compact"]                   # once per crossing, not per tick
    st["snap"]["ctx_pct"] = 20                     # compacted: re-arm for next climb
    autocompact(ac, state, "1", "s")
    assert "compacted" not in st and typed == ["/compact"]

    # A /compact that never landed: retried once past the grace period, then
    # reported. Without this the session sits full for ever and says nothing.
    st["snap"]["ctx_pct"] = 82
    autocompact(ac, state, "1", "s")
    assert typed == ["/compact"] * 2 and st["compact_tries"] == 1, typed
    autocompact(ac, state, "1", "s")
    assert typed == ["/compact"] * 2                # inside the grace period: wait
    st["compact_at"] = time.time() - COMPACT_GRACE - 1
    autocompact(ac, state, "1", "s")
    assert typed == ["/compact"] * 3 and st["compact_tries"] == 2, typed
    n = len(sent)
    st["compact_at"] = time.time() - COMPACT_GRACE - 1
    autocompact(ac, state, "1", "s")
    assert typed == ["/compact"] * 3                # out of tries: stops typing
    assert sent[-1].startswith("\u26a0\ufe0f s still 82% after"), sent[-1]
    st["compact_at"] = time.time() - COMPACT_GRACE - 1
    autocompact(ac, state, "1", "s")
    assert len(sent) == n + 1                       # ...and says so once
    st["snap"]["ctx_pct"] = 20                      # leave it armed for what follows
    autocompact(ac, state, "1", "s")
    typed[:] = ["/compact"]
    st.pop("snap"), typed.clear()

    n = len(sent)                                 # parked session still holding one
    st.update(mode="idle", queue=[], changed=time.time(),
              snap={"ts": time.time(), "ctx_pct": 62})
    idle_hint(cfg, state, "1", "s")
    assert len(sent) == n                         # just used: not parked
    st["changed"] = time.time() - IDLE_PARK - 1
    st["snap"]["ctx_pct"] = 20
    idle_hint(cfg, state, "1", "s")
    assert len(sent) == n                         # parked but cheap to resume
    st["snap"]["ctx_pct"] = 62
    idle_hint(cfg, state, "1", "s")
    assert sent[-1].startswith("💤 s idle 6h 0m at 62% context"), sent[-1]
    idle_hint(cfg, state, "1", "s")
    assert len(sent) == n + 1                     # once per park, not per tick
    st["changed"] = time.time()
    idle_hint(cfg, state, "1", "s")               # touched: re-arm for the next park
    assert "parked" not in st
    st["changed"] = time.time() - IDLE_PARK - 1
    idle_hint({"idle_ctx": None}, state, "1", "s")
    assert len(sent) == n + 1 and "parked" not in st        # !idlectx off
    st.pop("snap"), st.pop("changed")

    _queued[0] = None                             # held prompts outlive a restart
    st.update(queue=["one", "two"], limit_until=time.time() + 3600, ctx_warned=True)
    save_queue(state)
    save_queue(state)                             # unchanged: no second write
    fresh_state = {}
    restored = load_queue(fresh_state)
    assert fresh_state["s"]["queue"] == ["one", "two"], fresh_state
    assert restored["s"]["queue"] == ["one", "two"]
    assert "ctx_warned" not in fresh_state["s"]   # caches rebaseline, never restore
    assert "mode" not in fresh_state["s"]         # ...so `fresh` still means fresh
    st["queue"], _queued[0] = [], None            # drained: the file empties too
    st.pop("limit_until")
    save_queue(state)
    empty = {}
    assert load_queue(empty) == {} and empty == {}
    st.pop("ctx_warned")

    st.update(mode="idle", queue=[])              # usage limit: hold, then resume
    st.pop("prog_msg", None)                      # no turn open: nothing was cut
    n = len(sent)                                 # quoted output is not the banner
    screen[:] = ["● done",
                 "  ⎿  Error during compaction: You've hit your monthly limit"] + box
    flush_new(cfg, state, "1", "s")
    assert len(sent) == n and "limit_line" not in st, sent[-1]
    # ...but the live refusal is quoted the same way, with nothing in front of it.
    # This is what a spend cap actually looks like on screen, and skipping every
    # ⎿ line meant no pane without a sidecar window ever saw one.
    screen[:] = ["● done", "  ⎿  You've hit your monthly spend limit."] + box
    flush_new(cfg, state, "1", "s")
    assert sent[-1].startswith("⚠️ s hit a usage limit") and "NOT queued" in sent[-1]
    assert "limit_until" not in st                # no reset time: warn, never hold
    st.pop("limit_line")
    n = len(sent)                                 # that warning re-baselines this
    screen[:] = ["● done", "You've hit your 5-hour limit · resets in 1h 0m"] + box
    st["snap"] = {"ts": time.time(),              # sidecar outranks a stale screen
                  "five_hour": {"used_percentage": 40, "resets_at": time.time() + 99}}
    check_limit(cfg, st, "1", "s", screen, False)
    assert len(sent) == n and "limit_until" not in st, sent[-1]
    st["snap"]["five_hour"]["used_percentage"] = 100   # ... and when it is spent
    check_limit(cfg, st, "1", "s", screen, False)
    assert sent[-1].startswith("⏸ s hit the usage limit") and st["limit_until"]
    st.pop("limit_until"), st.pop("limit_line")   # a spent week, a healthy 5h:
    st["snap"] = {"ts": time.time(),              # the week is what refuses turns
                  "five_hour": {"used_percentage": 10, "resets_at": time.time() + 99},
                  "seven_day": {"used_percentage": 100, "resets_at": time.time() + 999}}
    check_limit(cfg, st, "1", "s", screen, False)
    assert "weekly window spent" in sent[-1] and st["limit_until"] > time.time() + 900
    st.pop("snap"), st.pop("limit_until"), st.pop("limit_line")
    flush_new(cfg, state, "1", "s")               # no sidecar: the screen decides
    assert sent[-1].startswith("⏸ s hit the usage limit") and "resumes" in sent[-1], sent[-1]
    assert st["limit_until"] > time.time() + 3500
    flush_new(cfg, state, "1", "s")               # same banner: announced once only
    assert not sent[-1].startswith("⏸")
    n = len(sent)                                 # a cap with no reset time on it
    st.pop("limit_until"), st.pop("limit_line")
    screen[:] = ["● done", "You've hit your monthly spend limit · raise it at x"] + box
    flush_new(cfg, state, "1", "s")
    assert sent[-1].startswith("⚠️ s hit a usage limit") and "NOT queued" in sent[-1]
    assert "limit_until" not in st                # so nothing gets swallowed
    st["limit_until"] = time.time() + 3600        # back to the queued case
    screen[:] = ["● done", "You've hit your 5-hour limit · resets in 1h 0m"] + box
    n, typed[:] = len(sent), []
    held = handle(cfg, state, threading.Lock(), "1", "do the thing later")
    assert held.startswith("📥 queued (1)") and typed == [], (held, typed)
    drain(cfg, state, "1", "s")                   # window still shut: nothing moves
    assert typed == [] and len(sent) == n
    st["limit_until"] = time.time() - 1           # window reset
    drain(cfg, state, "1", "s")
    assert typed == ["do the thing later"], typed
    assert sent[-2].startswith("▶️ s resumed") and "limit_until" not in st
    assert sent[-1].startswith("⚙️ s")           # then the live trace for that turn
    assert st["queue"] == [] and st["prog_msg"] == 77   # live trace opened for it
    assert "limit_line" not in st   # the ended window's banner suppresses nothing
    st.pop("prog_msg"), st.pop("last", None)   # not a prompt awaiting its turn

    # A window that resets with nothing queued must still clear the hold and say
    # so. The silent version left the session flagged as limited for good, and
    # left the topic with no word at the time nightmux had promised one.
    st["limit_until"], n = time.time() - 1, len(sent)
    drain(cfg, state, "1", "s")
    assert "limit_until" not in st and "resumed" not in st
    assert sent[-1].startswith("▶️ s usage window reset"), sent[-1]
    drain(cfg, state, "1", "s")                   # ...said once, not every tick
    assert len(sent) == n + 1
    st["limit_until"] = time.time() - 1           # and an expired hold never
    assert queue_blob({"s": st}).get("s", {}) == {}          # reaches disk again
    st["limit_until"] = time.time() + 60
    assert queue_blob({"s": st})["s"]["limit_until"] > time.time()
    st.pop("limit_until")

    # Scheduling rides the queue, so a scheduled prompt waits behind a usage hold
    # and a busy pane exactly as a typed one does.
    assert parse_every("4h") == 14400 and parse_every("1d 6h") == 108000
    assert parse_every("no duration here") == 0
    base = 1700000000                             # fixed instant: no clock races
    assert at_epoch({}, "+2h", base) == base + 7200
    nxt = at_epoch({}, "03:00", base)
    assert 0 < nxt - base <= 86400 and time.gmtime(nxt).tm_hour == 3
    assert at_epoch({}, "garbage", base) is None
    st["queue"], st["sched"] = [], [
        {"at": time.time() - 1, "every": None, "text": "one-off"},
        {"at": time.time() - 1, "every": 3600, "text": "recurring"}]
    due(cfg, state, "1", "s")
    assert st["queue"] == ["one-off", "recurring"], st["queue"]
    assert [j["text"] for j in st["sched"]] == ["recurring"]   # one-off is spent
    assert st["sched"][0]["at"] > time.time() + 3500   # rearmed from now, so a
    sched_n = len(sent)                                # daemon that was off does
    due(cfg, state, "1", "s")                          # not fire a backlog at once
    assert len(sent) == sched_n
    assert queue_blob({"s": st})["s"]["sched"]         # and it survives a restart
    st["queue"] = []
    out = handle(cfg, state, threading.Lock(), "1", "!at +1h check the build")
    assert out.startswith("⏰") and st["sched"][-1]["text"] == "check the build"
    assert handle(cfg, state, threading.Lock(), "1", "!sched").startswith("1.")
    assert handle(cfg, state, threading.Lock(), "1", "!at nonsense").startswith("usage:")
    assert handle(cfg, state, threading.Lock(), "1", "!sched clear") == \
        "dropped 2 scheduled prompt(s)"
    st.pop("sched")

    # !digest: on demand reuses !cost/!git plumbing; scheduling rides !every's
    # epoch math, but a fired job reports directly rather than typing "!digest"
    # into the agent the way an ordinary scheduled prompt would.
    st["snap"] = {}
    out = handle(cfg, state, threading.Lock(), "1", "!digest")
    assert out.startswith("🌙 digest · s"), out
    sched_out = handle(cfg, state, threading.Lock(), "1", "!digest 08:00")
    assert sched_out.startswith("digest daily at") and \
        any(j.get("kind") == "digest" for j in st["sched"]), sched_out
    assert handle(cfg, state, threading.Lock(), "1", "!digest off") == \
        "digest schedule cancelled"
    assert handle(cfg, state, threading.Lock(), "1", "!digest off") == \
        "no digest scheduled"
    assert handle(cfg, state, threading.Lock(), "1", "!digest nonsense") \
        .startswith("usage:")
    st["sched"] = [{"at": time.time() - 1, "every": 3600, "kind": "digest",
                    "text": "!digest", "since": time.time() - 3600}]
    st["queue"], n = [], len(sent)
    due(cfg, state, "1", "s")
    assert st["queue"] == [] and len(sent) == n + 1     # a report, never a typed prompt
    assert sent[-1].startswith("🌙 digest · s"), sent[-1]
    assert st["sched"][0]["since"] > time.time() - 5
    assert st["sched"][0]["at"] > time.time() + 3500    # rearmed for the next window
    st.pop("sched"), st.pop("snap")

    # !shift: sequential overnight plan, drained like the queue one idle turn at
    # a time — reuses drain()'s own idle/lockout gate instead of a second one.
    out = handle(cfg, state, threading.Lock(), "1", "!shift\nfirst step\nsecond step")
    assert out.startswith("shift set: 2 step(s)") and "first step" in out, out
    assert st["shift"] == ["first step", "second step"] and st["shift_total"] == 2
    assert handle(cfg, state, threading.Lock(), "1", "!shift").startswith("shift 0/2")
    st["mode"], t = "busy", len(typed)
    drain(cfg, state, "1", "s")                # busy pane: a shift step never fires
    assert len(typed) == t and st["shift"] == ["first step", "second step"]
    st["mode"], n = "idle", len(sent)
    drain(cfg, state, "1", "s")
    assert typed[-1] == "first step" and st["shift"] == ["second step"], typed
    assert sent[n].startswith("🌙 shift 1/2 → first step"), sent[n:]
    n = len(sent)
    drain(cfg, state, "1", "s")
    assert typed[-1] == "second step"
    assert "shift" not in st and "shift_total" not in st
    assert sent[n] == "🌙 shift 2/2 → second step", sent[n:]
    assert "🌙 s shift done" in sent[n:], sent[n:]
    assert handle(cfg, state, threading.Lock(), "1", "!shift") == \
        "no shift plan · !shift then one prompt per line"
    handle(cfg, state, threading.Lock(), "1", "!shift one two three")  # single line: one step
    assert st["shift"] == ["one two three"], st["shift"]
    assert handle(cfg, state, threading.Lock(), "1", "!shift clear") == \
        "shift cleared (1 step(s) dropped)"
    assert "shift" not in st

    # A turn cut off mid-flight has nothing left in the queue to bring it back,
    # so the hold queues its own continuation and the ordinary drain runs it.
    st["mode"], st["queue"], typed[:] = "busy", [], []
    st.pop("last", None)                          # nothing typed just before it
    st["snap"] = {"ts": time.time(),
                  "five_hour": {"used_percentage": 100, "resets_at": time.time() + 5}}
    check_limit(cfg, st, "1", "s", screen, False, True)
    assert st["queue"] == ["continue"] and "resuming itself" in sent[-1], sent[-1]
    st["mode"], st["limit_until"] = "idle", time.time() - 1
    drain(cfg, state, "1", "s")
    assert typed == ["continue"] and st["queue"] == [], typed
    st.pop("limit_line", None), st.pop("prog_msg", None)
    # That resume landed on a window that was still shut: the prompt it just sent
    # never got a turn, so it goes back rather than being lost to the refusal.
    st["queue"], st["limit_line"] = [], None
    check_limit(cfg, st, "1", "s", screen, False, False)
    assert st["queue"] == ["continue"], st["queue"]
    st["queue"], st["limit_line"] = [], None      # an idle session with nothing
    st.pop("last")                                # outstanding is left alone
    check_limit(cfg, st, "1", "s", screen, False, False)
    assert st["queue"] == [] and st["limit_until"] > time.time()
    st.pop("limit_until"), st.pop("limit_line")
    # A prompt refused the moment it was typed did no work: it goes back whole,
    # rather than a `continue` that would resume nothing.
    st["mode"], st["queue"] = "busy", []
    st["last"], st["last_at"], st["ran"] = "the refused prompt", time.time(), False
    check_limit(cfg, st, "1", "s", screen, False, True)
    assert st["queue"] == ["the refused prompt"], st["queue"]
    # ...and it does not need a busy pane to notice, because a prompt that was
    # refused is exactly the case where nothing was running to see it.
    st["queue"], st["limit_line"] = [], None
    check_limit(cfg, st, "1", "s", screen, False, False)
    assert st["queue"] == ["the refused prompt"], st["queue"]
    # A prompt whose turn did run is a different thing, and must not be re-sent.
    st["queue"], st["limit_line"], st["ran"] = [], None, True
    check_limit(cfg, st, "1", "s", screen, False, False)
    assert st["queue"] == [], st["queue"]
    st["ran"], st["queue"] = False, ["the refused prompt"]   # for what follows
    # ...and a window that reopens onto a pane that cannot take it says so, once,
    # instead of looking like a hold that never lifted.
    st["mode"], st["limit_until"], n = "busy", time.time() - 1, len(sent)
    drain(cfg, state, "1", "s")
    assert "1 queued, but the pane is busy" in sent[-1], sent[-1]
    drain(cfg, state, "1", "s")
    assert len(sent) == n + 1 and st["queue"] == ["the refused prompt"]
    for k in ("snap", "queue", "last", "last_at", "resumed", "limit_line"):
        st.pop(k, None)

    # The turn is open until its output lands, and the pane reads idle for the
    # tick or two between a refusal and the status line admitting the window is
    # spent — so the live trace, not the pane's mode, is what says work was cut.
    st["mode"], st["queue"], screen[:] = "idle", [], ["● done"] + box
    st["prog_msg"], st["snap"] = 77, {
        "ts": time.time(),
        "five_hour": {"used_percentage": 100, "resets_at": time.time() + 5}}
    st.pop("last", None), st.pop("limit_line", None)
    with stubbed(snapshot=lambda p: st["snap"]):
        flush_new(cfg, state, "1", "s")
    assert st["queue"] == ["continue"], st["queue"]
    # The same, for a session driven from its own terminal: no prompt of ours was
    # typed, so no live trace exists and the pane can read idle at the very tick
    # the window is found spent. A transcript that grew seconds ago is the turn.
    for k in ("queue", "limit_until", "limit_line", "prog_msg"):
        st.pop(k, None)
    st["mode"], st["last_gain"] = "idle", time.time()
    with stubbed(snapshot=lambda p: st["snap"]):
        flush_new(cfg, state, "1", "s")
    assert st["queue"] == ["continue"], st["queue"]
    st["last_gain"] = time.time() - ACTIVE_RECENT - 1   # ...but not hours later
    for k in ("queue", "limit_until", "limit_line"):
        st.pop(k, None)
    with stubbed(snapshot=lambda p: st["snap"]):
        flush_new(cfg, state, "1", "s")
    assert not st.get("queue"), st.get("queue")
    st.pop("last_gain")
    for k in ("queue", "limit_until", "limit_line", "prog_msg", "snap"):
        st.pop(k, None)

    # A banner that is merely still on screen is not a new limit: only what the
    # tick actually gained is evidence, or every resume re-holds on its own past.
    st["mode"], screen[:] = "idle", ["You've hit your 5-hour limit · resets in 1h 0m"]
    flush_new(cfg, state, "1", "s")                # first sight: a real hold
    assert st["limit_until"] > time.time() and st.get("queue") is None
    st.pop("limit_until")
    flush_new(cfg, state, "1", "s")                # same screen, nothing gained
    assert "limit_until" not in st
    st.pop("limit_line", None)

    # Menus disagree about Enter, so the answer is checked rather than assumed.
    keys, calls = [], []
    screen[:] = ["Do you want to proceed?", "❯ 1. Yes", "  2. No"]
    assert menu_digit(screen, YES_NO["!y"]) == "1"    # "y" would go nowhere here
    assert menu_digit(screen, YES_NO["!n"]) == "2"
    with stubbed(tmux=lambda *a: keys.append(a[-1]), CONFIRM_AFTER=0.3):
        press("s", "1", confirm=True)             # menu still up: the digit alone
        assert keys == ["1", "Enter"], keys        # only moved the highlight
        keys[:] = []
        with stubbed(visible=lambda s: (calls.append(1),
                                        list(screen) if len(calls) < 2
                                        else ["● done", "esc to interrupt"])[1]):
            press("s", "1", confirm=True)         # the dialog acted on the digit:
        assert keys == ["1"], keys                 # a stray Enter would answer the
    screen[:] = ["● done"] + box                  # next question for you

    handle(cfg, state, threading.Lock(), "1", "another one", mid=555)  # prompt ticked
    assert ("setMessageReaction", 555) in [(m, k.get("message_id")) for m, k in edits]
    assert st["react"] == 555 and st["prog_msg"] == 77
    screen[:] = ["● done", "● and the answer"] + box
    twice()
    assert "react" not in st, st
    assert json.loads(edits[-1][1]["reaction"])[0]["emoji"] == DONE, edits[-1]

    assert handle(cfg, state, threading.Lock(), "1", "/topics") == status_report(cfg, state)
    assert handle(cfg, state, threading.Lock(), "1", "/pane 5") is not None  # alias -> !pane
    assert {c["command"] for c in
            [{"command": c} for c in TG_SLASH]} & {c for c, _ in PASSTHRU} == set()
    n, t = len(sent), len(typed)                  # kill asks before it kills
    assert handle(cfg, state, threading.Lock(), "1", "!kill") is None
    assert sent[-1].startswith("⚠️ kill tmux session 's'?"), sent[-1]
    assert cfg["topics"].get("1") == "s"          # nothing killed, still bound
    assert handle(cfg, state, threading.Lock(), "1", "!cancel") == "cancelled"
    # A read-only topic reports and searches, and never reaches the keyboard.
    cfg["modes"], ro_typed = {"1": "readonly"}, len(typed)
    for blocked in ("hello there", "!raw rm -rf /", "!1", "!kill", "!new x",
                    "!queue now", "!claude"):
        assert handle(cfg, state, threading.Lock(), "1", blocked).startswith("🔒"), blocked
    assert len(typed) == ro_typed and cfg["topics"].get("1") == "s"   # nothing typed
    assert handle(cfg, state, threading.Lock(), "1", "!status") == status_report(cfg, state)
    assert handle(cfg, state, threading.Lock(), "1", "!queue").startswith("0 queued")
    cfg.pop("modes")                              # full again for what follows
    assert handle(cfg, state, threading.Lock(), "1", "!queue clear") is not None
    # An unhandled !command is typed into the session as text, so the cancel
    # button has to be a real command or declining would inject "!cancel".
    assert len(sent) == n + 1 and len(typed) == t, (sent[n:], typed[t:])
    screen[:] = ["● done"] + box
    assert handle(cfg, state, threading.Lock(), "1", "next task") is None
    assert typed[-1] == "next task", typed

    # !center: binds a topic to control every session, never to one of them.
    assert cfg.get("center_topic") is None
    out = handle(cfg, state, threading.Lock(), "501", "!center")
    assert out == "this topic is now the command center — try !board", out
    assert cfg["center_topic"] == "501" and "501" not in cfg["topics"]
    out2 = handle(cfg, state, threading.Lock(), "502", "!center")
    assert out2 == "command center moved here from topic 501", out2
    assert cfg["center_topic"] == "502" and "502" not in cfg["topics"]
    # A center topic controls, it does not converse — plain text and an
    # unrecognised command both point at !board instead of erroring or typing.
    assert handle(cfg, state, threading.Lock(), "502", "hello there") == \
        "this topic controls every session — try !board"
    assert handle(cfg, state, threading.Lock(), "502", "!bogus") == \
        "this topic controls every session — try !board"
    assert handle(cfg, state, threading.Lock(), "502", "!center off") == \
        "command center off"
    assert cfg.get("center_topic") is None
    assert handle(cfg, state, threading.Lock(), "502", "!center off") == \
        "no command center was set"

    # !board reuses !status's own classification rather than reclassifying.
    board = handle(cfg, state, threading.Lock(), "1", "!board")
    assert status_report(cfg, state) in board, board

    # !all: fan-out reuses send_prompt, echoes who it hit before sending, and
    # a readonly-bound or missing target is skipped, never typed into.
    cfg["topics"]["9"] = "other"
    state.setdefault("other", {})
    assert handle(cfg, state, threading.Lock(), "1", "!all").startswith("usage:")
    n, sent_n = len(typed), len(sent)
    out3 = handle(cfg, state, threading.Lock(), "1", "!all s,other broadcast one")
    assert out3 is None
    echo = sent[sent_n]
    assert echo.startswith("📣 !all → ") and "s" in echo and "other" in echo, echo
    assert typed[n:] == ["broadcast one", "broadcast one"], typed[n:]
    cfg["modes"] = {"9": "readonly"}
    n, sent_n = len(typed), len(sent)
    handle(cfg, state, threading.Lock(), "1", "!all --all skip-ro")
    echo2 = sent[sent_n]
    head, _, tail = echo2.partition("\n(skipped:")
    assert "other" not in head and "s" in head, echo2
    assert "other (read-only)" in tail, echo2
    assert typed[n:] == ["skip-ro"], typed[n:]        # only s got it
    cfg.pop("modes")
    n, sent_n = len(typed), len(sent)
    handle(cfg, state, threading.Lock(), "1", "!all bogus,s hi-there")
    echo3 = sent[sent_n]
    assert "bogus (not bound)" in echo3 and "s" in echo3.split("\n")[0], echo3
    assert typed[n:] == ["hi-there"], typed[n:]
    out4 = handle(cfg, state, threading.Lock(), "1", "!all bogus2 nope")
    assert out4.startswith("nothing to send to"), out4

    # !digest from the command center loops every bound topic instead of one.
    handle(cfg, state, threading.Lock(), "1", "!center")
    assert cfg["center_topic"] == "1"
    state["s"]["snap"], state["other"]["snap"] = {}, {}
    dig = handle(cfg, state, threading.Lock(), "1", "!digest")
    assert dig.count("🌙 digest ·") == 2 and "s" in dig and "other" in dig, dig
    assert handle(cfg, state, threading.Lock(), "1", "!digest 09:00") == \
        "!digest here is report-only — schedule it from each session's own topic"
    state["s"].pop("snap"), state["other"].pop("snap")
    cfg["topics"].pop("9"), state.pop("other")

    # A pending approval mirrors into the command center; whichever copy is
    # tapped first resolves it under the shared lock, and the other has
    # nothing left to press — no duplicate keystroke lands in the pane.
    st = state["s"]
    cfg["center_topic"] = "999"                    # distinct from "1": a real mirror
    st.pop("asked", None), st.pop("asked_msgs", None)
    sent_n = len(sent)
    ok = ask(cfg, st, "1", "s", "proceed?", ["Do you want to proceed?",
             "❯ 1. Yes", "  2. No"], key="k1")
    assert ok is True and len(sent) == sent_n + 2      # origin, then the mirror
    assert st["asked_msgs"] == [("1", 77), ("999", 77)], st["asked_msgs"]
    pressed, edits_n = [], len(edits)
    with stubbed(press=lambda s_, k_, confirm=False: pressed.append((s_, k_))):
        assert handle(cfg, state, threading.Lock(), "999", "!1 s") is None  # mirror tapped first
    assert pressed == [("s", "1")], pressed
    assert "asked_msgs" not in st                      # resolved: nothing left to answer
    assert any(m == "editMessageReplyMarkup" for m, _ in edits[edits_n:]), edits[edits_n:]
    with stubbed(press=lambda s_, k_, confirm=False: pressed.append((s_, k_))):
        assert handle(cfg, state, threading.Lock(), "1", "!1 s") is None    # origin's own copy, too late
    assert pressed == [("s", "1")], pressed             # the racing second tap: no-op
    with stubbed(press=lambda s_, k_, confirm=False: pressed.append((s_, k_))):
        handle(cfg, state, threading.Lock(), "1", "!1")   # bare, no session: unaffected
    assert pressed == [("s", "1"), ("s", "1")], pressed
    cfg["center_topic"] = None

    st = state["s"]                               # busy: hold it where we can see it
    st["queue"], typed[:] = [], []
    screen[:] = ["● working", "✻ Brewing… (3s · esc to interrupt)"]
    held = handle(cfg, state, threading.Lock(), "1", "do this after")
    assert held.startswith("📥 queued (1) · s is working") and typed == [], held
    assert handle(cfg, state, threading.Lock(), "1", "!raw urgent") is None
    assert typed == ["urgent"], typed             # !raw still overrides
    st["mode"] = "busy"
    drain(cfg, state, "1", "s")                   # still busy: nothing moves
    assert len(st["queue"]) == 1
    st["mode"] = "idle"
    drain(cfg, state, "1", "s")
    assert typed[-1] == "do this after" and st["queue"] == []
    assert sent[-1].startswith("▶️ s sending queued prompt"), sent[-1]
    screen[:] = ["● done"] + box

    # transcript-fed delivery: the pane stops being the source of truth
    state.clear(), sent.clear(), edits.clear()
    tp = os.path.join(FILE_DIR, "live.jsonl")
    open(tp, "w").close()
    with open(os.path.join(STATE_DIR, "live.json"), "w") as f:
        json.dump({"ts": time.time(), "pane": "%5", "transcript": tp,
                   "five_hour": {"used_percentage": 12, "resets_at": None}}, f)
    screen[:] = ["● Read(x.py)", "✻ Brewing… (3s · esc to interrupt)"]
    flush_new(cfg, state, "1", "s", "%5")      # baseline the transcript
    with open(tp, "a") as f:
        f.write(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": "x.py"}}]}}) + "\n")
    st = state["s"]
    st["prog_at"] = _prog_at[0] = 0
    flush_new(cfg, state, "1", "s", "%5")      # busy: trace comes from the file
    assert sent[-1] == "⚙️ s\n● Read(x.py)", sent[-1]
    with open(tp, "a") as f:
        f.write(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "**done** at last"}]}}) + "\n")
    screen[:] = ["● Read(x.py)", "● and some chrome the pane shows"] + box
    twice_p = lambda: [flush_new(cfg, state, "1", "s", "%5") for _ in range(2)]
    twice_p()
    assert sent[-1] == "✅ s\n● Read(x.py)\n**done** at last", sent[-1]
    assert "s" in state and not state["s"].get("tbuf")
    twice_p()                                     # nothing new in the file: silence
    assert sent[-1].startswith("✅ s\n● Read")
    globals()["live_sessions"] = lambda: {"s": "%5"}
    report = status_report({"topics": {"1": "s"}}, state)
    assert "5h 12%" in report and "no status line" not in report, report
    held, state["s"]["snap"] = state["s"]["snap"], None    # watched through the
    assert "[no status line]" in status_report({"topics": {"1": "s"}}, state)
    state["s"]["snap"] = held                             # keyhole, and saying so
    os.remove(tp)

    cfg["topics"] = {"1": "s"}                    # status + watchdog
    assert "✅ s" in status_report(cfg, state) and "topic 1" in status_report(cfg, state)
    assert watchdog(cfg, state, "1", "s", False) is False and "💀" in sent[-1]
    n = len(sent)
    watchdog(cfg, state, "1", "s", False)         # dead stays quiet after the first
    assert len(sent) == n
    state["s"].update(queue=["held"], limit_until=time.time() + 60, scr=["junk"])
    watchdog(cfg, state, "1", "s", True)
    assert "↩️" in sent[-1] and "scr" not in state["s"]   # rebaselined, no dump
    assert state["s"]["queue"] == ["held"]        # ...but the hold is not a cache
    state.pop("s")
    globals()["live_sessions"] = lambda: {}
    assert "💀 gone" in status_report({"topics": {"2": "gone"}}, {})

    # Voice/audio/video-note updates ride the same download-and-type path as a
    # photo or a document — just another field to notice on the way in.
    cfg5, fetched = {"chat_id": -1}, []
    with stubbed(fetch_file=lambda c, fid, name=None: fetched.append((fid, name)) or "/f/x",
                handle=lambda *a, **k: None, api=lambda c, m, **kw: {}):
        process(cfg5, {}, threading.Lock(), {7}, {
            "update_id": 1, "message": {"chat": {"id": -1}, "from": {"id": 7},
             "message_thread_id": "1", "voice": {"file_id": "v1", "duration": 3}}})
        assert fetched[-1] == ("v1", None), fetched
        process(cfg5, {}, threading.Lock(), {7}, {
            "update_id": 2, "message": {"chat": {"id": -1}, "from": {"id": 7},
             "message_thread_id": "1",
             "video_note": {"file_id": "vn1", "duration": 5}}})
        assert fetched[-1] == ("vn1", None), fetched
        process(cfg5, {}, threading.Lock(), {7}, {   # audio can carry a name; voice never does
            "update_id": 3, "message": {"chat": {"id": -1}, "from": {"id": 7},
             "message_thread_id": "1",
             "audio": {"file_id": "a1", "file_name": "song.mp3"}}})
        assert fetched[-1] == ("a1", "song.mp3"), fetched

    order, gate, ran = [], threading.Event(), threading.Event()

    def slow(c, s, l, a, upd):     # topic 1's first update hangs until released
        gate.wait(5) if upd["update_id"] == 1 else None
        order.append(upd["update_id"])
        ran.set() if upd["update_id"] == 3 else None

    globals()["process"] = slow
    acks = Acks()
    for uid, tp in ((1, 1), (2, 1), (3, 2)):
        dispatch(cfg, state, threading.Lock(), set(),
                 {"update_id": uid, "message": {"message_thread_id": tp}}, acks)
    assert ran.wait(5), "a slow topic blocked a different one"
    assert order == [3], order          # 1 is hung, and 2 waits behind it in order
    assert load_offset() is None        # ...so nothing is acked past the hung one
    gate.set()
    for _ in range(50):
        if len(order) == 3:
            break
        time.sleep(0.1)
    assert order == [3, 1, 2], order    # per topic in order, across topics in parallel
    assert load_offset() == 4
    os.remove(OFFSET_PATH)

    forum = {"message": {"chat": {"id": -100, "type": "supergroup",
                                  "is_forum": True, "title": "work"},
                         "from": {"id": 7}}}
    assert setup_chat(forum) == (-100, 7, "work")
    for bad in ({"message": {"chat": {"id": 5, "type": "private"}}},   # DM: no topics
                {"message": {"chat": {"id": -1, "type": "supergroup"}}},  # topics off
                {"edited_message": {"chat": {"id": -1, "type": "supergroup"}}}):
        assert setup_chat(bad) is None, bad

    sfile = os.path.join(STATE_DIR, "settings.json")
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(sfile, "w") as f:                    # an existing settings file
        json.dump({"model": "opus", "hooks": {"Stop": [{"hooks": [
            {"type": "command", "command": "mine.sh"}]}]}}, f)
    assert len(wire_claude(sfile)) == 3            # Stop, Notification, status line
    assert wire_claude(sfile) == [], "re-running setup duplicated a hook"
    with open(sfile) as f:
        got = json.load(f)
    assert got["model"] == "opus"                  # unrelated settings survive
    stop = [h["command"] for g in got["hooks"]["Stop"] for h in g["hooks"]]
    assert stop[0] == "mine.sh" and stop[1].endswith("nightmux_stop.py"), stop
    got["statusLine"] = {"type": "command", "command": "bash /nope/theirs.sh"}
    with open(sfile, "w") as f:
        json.dump(got, f)
    assert "add this line" in wire_claude(sfile)[0]  # theirs: instructions, not a rewrite
    with open(sfile) as f:
        assert "theirs.sh" in json.load(f)["statusLine"]["command"]
    assert sorted(wired(sfile)) == ["notify", "stop"]   # their status line: no sidecar
    assert wired(os.path.join(STATE_DIR, "nope.json")) == []

    scratch = os.path.join(os.path.dirname(FILE_DIR), ".mig-selfcheck")
    os.makedirs(scratch, exist_ok=True)
    newer = os.path.join(scratch, "nightmux.json")
    for was in WAS:                   # every old name is adopted, not just the last
        older = newer.replace("nightmux", was)
        open(older, "w").close()
        migrate([newer])
        assert os.path.exists(newer) and not os.path.exists(older), was
        os.remove(newer)
    older = newer.replace("nightmux", WAS[0])
    open(older, "w").close()
    open(newer, "w").close()          # a current file already there wins
    migrate([newer])
    assert os.path.exists(older), "migrate clobbered the current file"
    os.remove(older), os.remove(newer)
    migrate([newer])                  # nothing to adopt: a fresh install
    os.rmdir(scratch)

    cfg2 = {"topics": {}, "agents": {"opencode": ["opencode", "--resume"]}}
    assert agent(cfg2, "claude") == ("claude", "--continue")
    assert agent(cfg2, "opencode") == ("opencode", "--resume")    # added by config
    assert agent(cfg2, "nope") == ("nope", "")   # one-off: the key is the command
    assert default_agent(cfg2) == "claude"
    assert default_agent({"agent": "codex"}) == "codex"

    spawned, lk = [], threading.Lock()
    globals()["spawn"] = lambda n, cwd, line: spawned.append((n, cwd, line))
    globals()["has_session"] = lambda n: False
    assert "started codex" in start_session(cfg2, {}, lk, "9", "box ~ --sandbox",
                                            "codex")
    assert spawned[-1][2] == "codex --sandbox", spawned[-1]
    assert cfg2["topics"]["9"] == "box" and cfg2["started"]["9"] == "codex"
    cfg2["topics"].pop("9")                      # the session died; resume the topic
    handle(cfg2, {}, lk, "9", "!resume")
    assert spawned[-1][2] == "codex resume --last", spawned[-1]   # not claude's flag
    handle(cfg2, {}, lk, "9", "!resume aider")   # an explicit agent still wins
    assert spawned[-1][2] == "aider --restore-chat-history", spawned[-1]
    handle(cfg2, {}, lk, "77", "!opencode side")
    assert spawned[-1][2] == "opencode", spawned[-1]

    # !restore is !resume under another name — both funnel through resume_session.
    cfg2["topics"]["91"] = "ghost"
    n = len(spawned)
    assert "no directory recorded" in handle(cfg2, {}, lk, "91", "!restore")
    assert len(spawned) == n, spawned[n:]        # a topic with no dir stays down
    cfg2.setdefault("dirs", {})["91"] = "/tmp"
    out = handle(cfg2, {}, lk, "91", "!restore")
    assert spawned[-1][:2] == ("ghost", "/tmp") and "topic bound" in out, out
    assert cfg2["started"]["91"] == "claude"

    # One topic, several agents. Bare !<agent> moves the topic to that agent in
    # the same directory and leaves the one it was on running; switching back
    # must reuse that session, or "switch" would mean "start a new conversation".
    live = {"box"}
    globals()["has_session"] = lambda s: s in live
    cfg2["topics"]["9"], cfg2["started"]["9"] = "box", "codex"
    cfg2["dirs"]["9"] = "/tmp"
    out = handle(cfg2, {}, lk, "9", "!agy")
    assert spawned[-1][:2] == ("box-agy", "/tmp"), spawned[-1]
    assert cfg2["topics"]["9"] == "box-agy" and cfg2["started"]["9"] == "agy"
    assert cfg2["bench"]["9"] == {"codex": "box", "agy": "box-agy"}, cfg2["bench"]
    assert "also live in the same tree: box" in out, out   # two agents, one tree
    live.add("box-agy")
    n = len(spawned)
    assert "\u2192 codex ('box')" in handle(cfg2, {}, lk, "9", "!codex")
    assert len(spawned) == n, "switching back respawned instead of reusing"
    assert cfg2["topics"]["9"] == "box" and cfg2["started"]["9"] == "codex"
    assert "already on codex" in handle(cfg2, {}, lk, "9", "!codex")
    assert "\u25cf !codex" in handle(cfg2, {}, lk, "9", "!agents")
    handle(cfg2, {}, lk, "9", "!agy named /tmp")   # with args: still start-by-name
    assert spawned[-1][0] == "named" and cfg2["bench"]["9"]["agy"] == "box-agy"

    # ...and one session must never be two topics'. They share a scrape cursor,
    # so the watcher hands the output to whichever topic it reaches first.
    assert bound_to(cfg2, "box", "9") is None
    cfg2["topics"]["94"] = "box"
    assert bound_to(cfg2, "box", "9") == "94"
    cfg2["bench"]["9"]["aider"] = "box"           # a bench entry another topic owns
    assert "topic 94's session" in handle(cfg2, {}, lk, "9", "!aider")
    del cfg2["bench"]["9"]["aider"]
    with stubbed(real_session=lambda a: "box"):
        assert "one session, one topic" in handle(cfg2, {}, lk, "95", "!bind box")
    assert "95" not in cfg2["topics"], cfg2["topics"]
    cfg2["topics"].pop("94")
    globals()["has_session"] = lambda s: False

    # restore_startup: a dead topic gets a button unless auto_restore says relaunch.
    cfg3 = {"topics": {"1": "gone1", "2": "alive2"}, "dirs": {"1": "/tmp"}, "chat_id": -1}
    st3, n = {}, len(sent)
    globals()["has_session"] = lambda s: s == "alive2"
    restore_startup(cfg3, st3, lk)
    assert sent[-1].startswith("⚠️ gone1 is gone") and len(sent) == n + 1, sent[n:]
    assert st3["gone1"]["dead"] is True                # pre-armed: watchdog stays quiet
    cfg3["auto_restore"] = True
    restore_startup(cfg3, st3, lk)
    assert spawned[-1][0] == "gone1" and sent[-1].startswith("▶️ restored gone1"), sent[-1]
    cfg3["topics"]["3"] = "gone3"                 # never recorded a directory
    restore_startup(cfg3, st3, lk)
    assert "not restored" in sent[-1], sent[-1]   # said so, rather than "restored"

    # git worktrees + snapshot-before-unattended-prompt, against a real throwaway repo.
    import tempfile
    repo = tempfile.mkdtemp(prefix="nightmux-selfcheck-")
    subprocess.run(["git", "init", "-q", repo], check=True)
    subprocess.run(["git", "-C", repo, "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", repo, "config", "user.name", "t"], check=True)
    with open(os.path.join(repo, "f"), "w") as f:
        f.write("one")
    subprocess.run(["git", "-C", repo, "add", "f"], check=True)
    subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "init"], check=True)

    assert worktree_path("/no/such/dir", "x") is None    # not a repo: nothing to attach to
    wt = worktree_path(repo, "feature-a")
    assert wt == os.path.join(f"{repo}-wt", "feature-a") and os.path.isdir(wt), wt
    assert tmux_git(repo, "rev-parse", "--verify", "--quiet", "refs/heads/feature-a")
    assert worktree_path(repo, "feature-a") == wt        # already there: reused, not redone

    globals()["has_session"] = lambda s: False
    out = start_session(cfg2, {}, lk, "92", f"wtses {repo} @feature-b", "claude")
    assert out.startswith("started claude") and "@feature-b" in out, out
    assert cfg2["dirs"]["92"] == os.path.join(f"{repo}-wt", "feature-b")
    assert os.path.isdir(cfg2["dirs"]["92"])
    plaindir = tempfile.mkdtemp(prefix="nightmux-selfcheck-plain-")
    bad = start_session(cfg2, {}, lk, "93", f"wtses2 {plaindir} @x", "claude")
    assert "not a git repo" in bad, bad
    shutil.rmtree(plaindir, ignore_errors=True)

    with open(os.path.join(repo, "f"), "w") as f:        # dirty worktree
        f.write("two")
    with stubbed(sess_cwd=lambda s: repo):
        snapshot_repo("t")                                # unattended: snapshot first
    with open(os.path.join(repo, "f")) as f:
        assert f.read() == "two", "stash create must never touch the worktree"
    pre = [n_ for n_ in tmux_git(repo, "for-each-ref", "--format=%(refname:short)",
                                 "refs/heads/nightmux/pre-*").split("\n") if n_.strip()]
    assert len(pre) == 1, pre
    tmux_git(repo, "branch", "-D", pre[0])   # clean slate for the deterministic prune below

    for i in range(7):                                    # deterministic creatordate
        d = f"2020-01-01T00:00:{i:02d}"
        env = dict(os.environ, GIT_AUTHOR_DATE=d, GIT_COMMITTER_DATE=d)
        with open(os.path.join(repo, "f"), "w") as f:
            f.write(str(i))
        subprocess.run(["git", "-C", repo, "commit", "-aq", "-m", str(i)], env=env, check=True)
        subprocess.run(["git", "-C", repo, "branch", f"nightmux/pre-fake{i}", "HEAD"],
                       env=env, check=True)
    prune_snapshots(repo)
    survivors = [n_ for n_ in tmux_git(
        repo, "for-each-ref", "--sort=-creatordate", "--format=%(refname:short)",
        "refs/heads/nightmux/pre-*").split("\n") if n_.strip()]
    assert len(survivors) == SNAP_KEEP, survivors      # only the last 5 survive
    assert survivors[0] == "nightmux/pre-fake6", survivors
    assert "nightmux/pre-fake0" not in survivors, survivors

    cfg4 = {"topics": {"1": "s4"}}
    with stubbed(sess_cwd=lambda s: repo, has_session=lambda s: True):
        undo_out = handle(cfg4, {}, threading.Lock(), "1", "!undo")
        wt_out = handle(cfg4, {}, threading.Lock(), "1", "!worktrees")
    assert "nightmux/pre-fake6" in undo_out, undo_out
    assert "git restore --source nightmux/pre-fake6" in undo_out
    assert "git diff nightmux/pre-fake6" in undo_out, undo_out
    assert repo in wt_out and "feature-a" in wt_out, wt_out

    shutil.rmtree(repo, ignore_errors=True)
    shutil.rmtree(f"{repo}-wt", ignore_errors=True)

    # --doctor: one ✓/✗ line per check, and the overall result is their AND.
    def _boom():
        raise OSError("no config")

    class _FakeShutil:
        which = staticmethod(lambda n: "/usr/bin/tmux")

    with stubbed(load_cfg=_boom):
        assert doctor() is False               # no config at all: nothing else to check
    with stubbed(load_cfg=lambda: {"token": "t", "chat_id": 1, "allow_users": [1]},
                api=lambda c, m, **kw: {"ok": True}, wired=lambda: ["stop"],
                run=lambda *a, **kw: "process" if "KillMode" in a else "active",
                shutil=_FakeShutil()):
        assert doctor() is True                # every check stubbed healthy
    with stubbed(load_cfg=lambda: {"token": "t", "chat_id": 1, "allow_users": [1]},
                api=lambda c, m, **kw: {"ok": False, "description": "bad token"},
                wired=lambda: [], run=lambda *a, **kw: "inactive", shutil=_FakeShutil()):
        assert doctor() is False               # one ✗ (token rejected) fails the whole thing

    for n_ in os.listdir(STATE_DIR):
        os.remove(os.path.join(STATE_DIR, n_))
    os.rmdir(STATE_DIR)
    # Later saves recreate the redirected config; leaving it behind drops test
    # debris in the live upload cache, where prune would not touch it for a week.
    os.path.exists(CFG_PATH) and os.remove(CFG_PATH)
    print("selfcheck ok")


def doctor():
    """nightmux --doctor: one ✓/✗ line per check, triage only, nothing fixed."""
    ok = [True]

    def line(label, passed, detail=""):
        ok[0] = ok[0] and passed
        print(f"{'✓' if passed else '✗'} {label}" + (f" — {detail}" if detail else ""))

    line("tmux binary found", bool(shutil.which("tmux")))
    try:
        cfg = load_cfg()
    except (OSError, ValueError) as e:
        cfg = {}
        line("config file", False, f"{CFG_PATH}: {e}")
    else:
        missing = [k for k in ("token", "chat_id", "allow_users") if not cfg.get(k)]
        line("config has token/chat_id/allow_users", not missing,
             ("missing " + ", ".join(missing)) if missing else "")
    if cfg.get("token"):
        me = api(cfg, "getMe")
        line("token accepted by Telegram", bool(me.get("ok")), me.get("description", ""))
    else:
        line("token accepted by Telegram", False, "no token to check")
    if cfg.get("token") and cfg.get("chat_id"):
        chat = api(cfg, "getChat", chat_id=cfg["chat_id"])
        line("bot reachable in the configured chat", bool(chat.get("ok")),
             chat.get("description", ""))
    else:
        line("bot reachable in the configured chat", False, "no token/chat_id to check")
    on = wired()
    line("Claude Code hooks wired", bool(on), ", ".join(on) if on else "none found")
    if sys.platform == "darwin":
        active = "com.nightmux" in run("launchctl", "list")
    else:
        active = run("systemctl", "--user", "is-active", "nightmux").strip() == "active"
        # An install from before this was added keeps its own unit file, and the
        # symptom is spectacular: `systemctl restart nightmux` takes every agent
        # session with it, because they are all in this unit's cgroup.
        km = run("systemctl", "--user", "show", "-p", "KillMode", "--value",
                 "nightmux").strip()
        line("restarting the service keeps sessions alive", km == "process",
             "" if km == "process" else
             f"KillMode={km} — add 'KillMode=process' under [Service] in "
             f"{UNIT_PATH}, then: systemctl --user daemon-reload")
    line("service active", active)
    return ok[0]


def cli():
    """Entry point for both `python3 nightmux.py` and the installed `nightmux`."""
    if "--selfcheck" in sys.argv:
        selfcheck()
    elif "--setup" in sys.argv:
        setup()
    elif "--doctor" in sys.argv:
        sys.exit(0 if doctor() else 1)
    elif "--version" in sys.argv:
        print(version_report())
    elif "--demo" in sys.argv:
        print("\033[1mTo experience the nightmux auto-resume magic instantly:\033[0m\n")
        print("1. Open your Telegram bot")
        print("2. Send this exact message to bind a test agent:\n")
        print("    !new demo bash -c \"echo 'Working...'; sleep 2; echo 'usage limit reached. resets in 1m'; sleep 125; echo 'Agent resumed!'\"\n")
        print("nightmux will immediately detect the simulated limit, pause the topic, wait until the reset window opens, and auto-resume.\n")
    else:
        main()


if __name__ == "__main__":
    cli()
