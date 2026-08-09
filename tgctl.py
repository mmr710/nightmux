#!/usr/bin/env python3
"""Telegram controller for Claude Code sessions running in tmux.

One forum topic per project -> one tmux session. Text in a topic is typed into
that session's Claude Code prompt; new terminal scrollback is sent back to the
topic. Stdlib only.

Config: ~/.tgctl.json
{
  "token": "<bot token from @BotFather>",
  "chat_id": -1001234567890,
  "allow_users": [123456789],
  "topics": {"12": "projectA"},
  "poll": 2
}
"""
import calendar
import html
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

VERSION = "1.0.0"
CFG_PATH = os.path.expanduser(os.environ.get("TGCTL_CONFIG", "~/.tgctl.json"))
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
    # tgctl can type into. The temp file is created under the umask, so the mode
    # has to be set here or each save quietly re-widens it.
    os.chmod(tmp, 0o600)
    os.replace(tmp, CFG_PATH)


OFFSET_PATH = os.path.expanduser(os.environ.get("TGCTL_OFFSET", "~/.tgctl.offset"))


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
    b = "----tgctl-" + str(int(time.time() * 1000))

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


FILE_DIR = os.path.expanduser("~/.tgctl-files")


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


def tmux_git(cwd, *args):
    return run("git", "-C", cwd, *args, timeout=30).strip()


def has_session(sess):
    try:
        return subprocess.run(("tmux", "has-session", "-t", sess),
                              capture_output=True, timeout=10).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def pane(sess):
    """Everything the pane holds: scrollback history plus the live screen."""
    return tmux("capture-pane", "-p", "-J", "-t", sess, "-S", "-").split("\n")


def visible(sess):
    """Just the on-screen rows: the cheap check before the full capture."""
    return tmux("capture-pane", "-p", "-J", "-t", sess).split("\n")


def sess_cwd(sess):
    return tmux("display-message", "-p", "-t", sess, "#{pane_current_path}")


def live_sessions():
    """{name: pane_id} for every tmux session, in one call instead of one per topic."""
    out = tmux("list-sessions", "-F", "#{session_name}\t#{pane_id}")
    return dict(l.split("\t", 1) for l in out.split("\n") if "\t" in l)


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
    """Type text into the Claude Code prompt and submit.

    One tmux invocation for the whole prompt — chained with ';' arguments —
    instead of one process spawn per line, then wait for the text to land
    rather than sleeping a fixed guess. The old fixed sleep submitted a
    truncated prompt whenever the TUI redrew slower than 0.4s.
    """
    args = []
    for i, line in enumerate(text.split("\n")):
        if i:  # newline inside the prompt box, not a submit
            args += [";", "send-keys", "-t", sess, "M-Enter"]
        if line:
            args += [";", "send-keys", "-t", sess, "-l", "--", line]
    if not args:
        return
    tmux(*args[1:])
    if not settle(sess, text.split("\n")[-1]):
        print(f"inject {sess}: text not on screen after 2s, sending Enter anyway",
              file=sys.stderr)
    tmux("send-keys", "-t", sess, "Enter")


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
WAITING = re.compile(r"[❯>]\s*\d[.)]|\b\d\.\s*(?:Yes|No)\b|Do you want|\(y/n\)"
                     r"|Press Enter to continue|Continue\?"
                     r"|Navigate ·|enter Confirm|Requesting permission|Do you trust")
# Mid-turn: these footers only render while the agent is working.
BUSY = re.compile(r"esc to (?:interrupt|cancel)|Brewing|Thinking…|Running…|Running\.\.\.")
# A pick in whatever numbered menu the pane is showing, boxed or bare.
MENU = re.compile(r"^\s*[│┃]?\s*[❯>]?\s*(\d)[.)]\s+(\S.*?)\s*[│┃]?$")
# The usage-limit banner. Phrasing lifted from Claude Code's own detector, so it
# tracks what the CLI actually prints rather than what a changelog once said.
LIMIT_HIT = re.compile(
    r"You've (?:hit|reached) your|You're out of (?:usage credits|extra usage)"
    r"|usage limit reached|Your org is out of usage"
    r"|Your (?:seat type doesn't include|usage allocation has been disabled)")
RESET_IN = re.compile(r"resets? in\s+((?:\d+\s*(?:d|hr?|min|m)\b\s*)+)", re.I)
RESET_AT = re.compile(r"resets?\s+(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:[ap]m)?)", re.I)
HOOK_DIR = os.path.expanduser("~/.tgctl-hooked")
HOOK_FRESH = 900  # a Stop hook seen this recently owns delivery for that session
STATE_DIR = os.path.expanduser("~/.tgctl-state")
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


def snapshot(pane):
    """Freshest status-line snapshot written from this tmux pane, or None.

    Matched on pane id, never on cwd: a directory says nothing about which
    process is living in it, so cwd would happily hand an agy session the
    transcript of a Claude that worked there hours ago.
    """
    best, now = None, time.time()
    if not pane:
        return None
    try:
        names = os.listdir(STATE_DIR)
    except OSError:
        return None
    for n in names:
        if not n.endswith(".json"):
            continue
        try:
            with open(os.path.join(STATE_DIR, n)) as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
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
    with open(path, "rb") as f:
        f.seek(pos)
        buf = f.read()
    cut = buf.rfind(b"\n") + 1
    if not cut:
        return []                              # a record still being written
    st["tpos"] = pos + cut
    out = []
    for line in buf[:cut].decode("utf8", "replace").split("\n"):
        if line.strip():
            try:
                out += render(json.loads(line))
            except ValueError:
                continue
    return out


def pane_state(lines):
    """waiting | busy | idle, from the live screen only.

    Detail lines are excluded from the busy test on purpose: a backgrounded
    shell prints "⎿ Running… (7m · timeout 10m)" while the prompt is free.
    """
    tail = lines[-25:]
    if WAITING.search("\n".join(tail)):
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


def menu_buttons(lines):
    """One tap-button per option of the menu the pane is waiting on."""
    opts = {}
    for l in lines[-25:]:
        m = MENU.match(l)
        if m:
            label = m.group(2)
            opts[m.group(1)] = label[:28] + ("…" if len(label) > 28 else "")
    # No numbers means an arrow-driven selector (agy's trust prompt, /model):
    # the nav row alone drives it, exactly as you would in the terminal.
    rows = [[(f"{d}. {opts[d]}", f"!{d}")] for d in sorted(opts)]
    rows.append([("esc", "!esc"), ("↑", "!up"), ("↓", "!down"), ("⏎", "!enter")])
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


def check_limit(cfg, st, topic, sess, scr, fresh):
    """Hold prompts until the usage window resets.

    The status-line snapshot carries the exact percentage and reset epoch, and
    outranks the screen: a pane keeps showing a banner long after it stopped
    being true, and one that merely scrolled past was never a live state at all.
    """
    snap = st.get("snap") or {}
    fh = snap.get("five_hour") or {}
    # resets_at in the past means the window already turned over and this reading
    # describes the one before it — a resumed session redraws its status line
    # with the last figures it knew before the first API call refreshes them.
    if (time.time() - snap.get("ts", 0) < USAGE_FRESH
            and (fh.get("resets_at") or 0) > time.time()):
        if (fh.get("used_percentage") or 0) < 100:
            st.pop("limit_line", None)   # sidecar says there is room; screen cannot argue
            return
        hit, at = "5-hour window spent", fh["resets_at"]
    elif fresh:
        return  # a restart sees the whole scrollback as new; old banners are not news
    else:
        # DETAIL lines are quoted output — "⎿ Error during compaction: You've hit
        # your monthly spend limit" is a report of a past failure, not the banner.
        hit = next((l for l in scr[-12:]
                    if not DETAIL.match(l) and LIMIT_HIT.search(l)), None)
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
    st["limit_until"] = until = at + LIMIT_SLACK
    send(cfg, topic, f"⏸ {sess} hit the usage limit\n{hit}\n"
         f"resumes {clock(cfg, until)} "
         f"(in {left(until - time.time())}) — anything you send is queued",
         mode="plain")


WARN_AT = (80, 90)   # say something before the wall, not at it
CTX_WARN = 75        # a context this full costs double for the same work
# Account-wide: every session shares the same 5-hour and weekly windows, so six
# bound topics must not mean six warnings. First one to notice speaks.
_warned = {}


def warn_usage(cfg, st, topic, sess):
    """Warn as a usage window fills, once per threshold, once per account."""
    snap = st.get("snap") or {}
    if time.time() - snap.get("ts", 0) > USAGE_FRESH:
        return  # stale numbers describe a window that may already have reset
    for key, label in (("five_hour", "5-hour"), ("seven_day", "weekly")):
        w = snap.get(key) or {}
        pct, at = w.get("used_percentage"), w.get("resets_at")
        if pct is None or not at:
            continue
        window, done = _warned.get(key, (None, 0))
        if window != at:          # a new window: last time's warnings do not carry
            window, done = at, 0
        step = max((t for t in WARN_AT if pct >= t), default=0)
        _warned[key] = (window, max(step, done))
        if step > done:
            send(cfg, topic, f"🔶 {label} limit {pct:.0f}% used\n"
                 f"resets {clock(cfg, at)} (in {left(at - time.time())})",
                 mode="plain")


def warn_ctx(cfg, st, topic, sess):
    """Warn once when a session's context window gets expensive to carry."""
    pct = (st.get("snap") or {}).get("ctx_pct")
    if pct is None:
        return
    if pct < CTX_WARN:
        st.pop("ctx_warned", None)   # compacted or cleared: arm again
    elif not st.get("ctx_warned"):
        st["ctx_warned"] = True
        send(cfg, topic, f"🧠 {sess} context {pct:.0f}% full\n"
             "every turn re-reads all of it — /compact, or !ctx to see what is in it",
             mode="plain")


def ctx_report(path, top=8):
    """What is actually occupying the context window, biggest first.

    Tool results are the bulk of it and they are attributed to the tool that
    produced them, so the answer is actionable: it names what to stop doing.
    """
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
    return "\n".join(out)


PROJECTS = os.path.expanduser("~/.claude/projects")
# Anthropic's published ratios against one input token. Cache reads are a tenth
# of fresh input, which is exactly why a large context is expensive to merely
# carry: cheap per token, ruinous at a quarter million of them every turn.
WEIGHT = {"in": 1.0, "write": 1.25, "read": 0.1, "out": 5.0}


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
    if pct < at:
        st.pop("compacted", None)      # back under: arm again for the next climb
        return
    if st.get("compacted") or st.get("mode") != "idle" or st.get("queue"):
        return
    st["compacted"] = True
    send(cfg, topic, f"🧹 {sess} context {pct:.0f}% ≥ {at}% — running /compact\n"
         "!autocompact off to stop this", mode="plain")
    inject(sess, "/compact")
    remember(state, sess, "/compact")


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
        held = {k: st[k] for k in ("queue", "limit_until") if st.get(k)}
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
    return {s: h for s, h in blob.items() if h.get("queue")}


def drain(cfg, state, topic, sess):
    """Once the window resets, feed the queue back one prompt per idle turn."""
    st = state.setdefault(sess, {})
    until = st.get("limit_until", 0)
    if until and time.time() >= until:
        # Clear the hold here rather than on the way out with a prompt. A window
        # that reset with an empty queue would otherwise leave the session
        # flagged as limited for good, and leave the topic with no word at the
        # time tgctl promised one — which reads as a hold that never lifted.
        st.pop("limit_until", None)
        if st.get("queue"):
            st["resumed"] = True     # the send below says "resumed", not "sending"
        else:
            send(cfg, topic, f"▶️ {sess} usage window reset · nothing was queued",
                 mode="plain")
    q = st.get("queue")
    if not q or st.get("mode") != "idle" or time.time() < st.get("limit_until", 0):
        return
    held = st.pop("resumed", None)
    text = q.pop(0)
    send(cfg, topic, f"▶️ {sess} {'resumed · sending' if held else 'sending'} queued "
         f"prompt{f' ({len(q)} left)' if q else ''}\n{text[:500]}", mode="plain")
    inject(sess, spill(sess, text))
    remember(state, sess, text)
    started(cfg, state, topic, sess, None)


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
    scr = visible(sess)
    if not fresh and not gained and scr == st.get("scr") and st["prev"] == st["sent"]:
        return  # nothing moved anywhere and nothing is pending: skip the big capture
    st["scr"] = scr
    lines = pane(sess)
    for k, v in (("sent", lines), ("prev", lines), ("changed", time.time())):
        st.setdefault(k, v)  # watchdog gets here first and seeds an empty dict
    stable, changed = lines == st["prev"], lines != st["sent"]
    if not stable:
        st["prev"], st["changed"] = lines, time.time()
    st["mode"] = pane_state(scr)
    check_limit(cfg, st, topic, sess, scr, fresh)
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


def ask(cfg, st, topic, sess, body, lines, key=None):
    """Announce a prompt once. The pane redraws constantly; the question doesn't.

    Deduped on `key` — the question itself — not on the whole message, because
    the text above it arrives as a diff that keeps shifting while the menu sits
    still. Without this the same menu is resent every few seconds, forever.
    """
    key = key or body
    if not body or key == st.get("asked") or notified(sess):
        return False
    st["asked"] = key
    send(cfg, topic, f"🟠 needs input {sess}\n{body}", buttons=menu_buttons(lines))
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
            if d == STATE_DIR and n.startswith("queue.json"):
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
        st["dead"] = False
        state.pop(sess, None)  # rebuilt session: rebaseline instead of dumping it
        send(cfg, topic, f"↩️ '{sess}' is back", mode="plain")
    return alive


def watcher(cfg, state, lock):
    pruned = 0.0
    bound = []
    while True:
        # Anything thrown here would take the thread with it, and a dead watcher
        # is a tgctl that answers commands while quietly monitoring nothing.
        try:
            with lock:
                bound = list(cfg["topics"].items())
            alive = live_sessions()   # one tmux call for every topic's liveness
            pruned = prune(time.time(), pruned)
            for topic, sess in bound:
                try:
                    if watchdog(cfg, state, topic, sess, sess in alive):
                        flush_new(cfg, state, topic, sess, alive.get(sess))
                        nudge(cfg, state, topic, sess)
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
# Numbered menu picks: the dialog acts on the digit alone, no Enter.
KEYS.update({f"!{d}": str(d) for d in range(1, 10)})

# Telegram autocompletes registered bot commands when you type "/", which is
# the only autocomplete a bot can offer. Two registers share that one menu:
#
#   TG_SLASH  — tgctl's own, aliased to their ! form. Every name here is one
#               Claude Code does NOT own, so nothing shadows a real slash command.
#   PASSTHRU  — Claude Code's commands, registered purely so they autocomplete;
#               they are typed into the session like any other text.
TG_SLASH = {"ctl": "!ctl", "topics": "!status", "sessions": "!sessions",
            "pane": "!pane", "git": "!git", "diff": "!diff", "get": "!get",
            "bind": "!bind", "unbind": "!unbind", "kill": "!kill",
            "verbose": "!verbose", "queue": "!queue", "keys": "!keys",
            "raw": "!raw", "reload": "!reload", "tglog": "!log",
            "tghelp": "!help", "tgversion": "!version",
            "limits": "!usage", "tz": "!tz", "ctx": "!ctx", "spend": "!cost",
            "grep": "!grep", "autocompact": "!autocompact", "idlectx": "!idlectx"}
TG_DESC = {"ctl": "button panel for this session", "topics": "every topic and its state",
           "sessions": "list tmux sessions", "pane": "dump the pane [lines]",
           "git": "status + last commits", "diff": "unstaged diff",
           "get": "upload a file from the session's cwd", "queue": "held prompts [clear|now]",
           "kill": "kill this topic's session", "verbose": "toggle tool detail",
           "raw": "type text even with a menu open", "reload": "re-read ~/.tgctl.json",
           "tglog": "tgctl daemon journal", "tghelp": "tgctl command list",
           "tgversion": "tgctl version, and which hooks are wired",
           "limits": "5h/7d window and context use, every topic",
           "tz": "show times in your timezone, e.g. /tz Africa/Cairo",
           "ctx": "what is filling this session's context window",
           "spend": "token spend: this chat, or /spend 7 for all projects",
           "grep": "search every transcript, e.g. /grep rate limit",
           "autocompact": "auto /compact at N% context, or off",
           "idlectx": "flag parked sessions above N% context, or off"}
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
    st["changed"] = time.time()


# Any CLI that runs in a terminal works here: tgctl types into tmux and reads the
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
    "gemini": ["gemini", ""],   # no resume flag; /chat resume from inside instead
}


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


def start_session(cfg, state, lock, topic, arg, key):
    """New session running agent `key`, bound to this topic. Flags pass through."""
    prog, _ = agent(cfg, key)
    name, _, rest = arg.partition(" ")
    rest = rest.strip()
    if not name:
        return f"usage: !{key} <name> [dir] [flags]"
    if has_session(name):
        return f"'{name}' exists; use !bind {name}"
    if rest.startswith(("~", "/", ".")):        # dir first, anything after is flags
        cwd, _, flags = rest.partition(" ")
    else:
        cwd, flags = "", rest
    cwd = os.path.expanduser(cwd or "~")
    if not os.path.isdir(cwd):
        return f"no dir {cwd}"
    spawn(name, cwd, f"{prog} {flags}".strip())
    with lock:
        cfg["topics"][topic] = name
        cfg.setdefault("dirs", {})[topic] = cwd   # !resume needs it after a crash
        cfg.setdefault("started", {})[topic] = key   # ...and which agent it was
        save_cfg(cfg)
    state.pop(name, None)
    return f"started {prog} {flags} '{name}' in {cwd}, topic bound".replace("  ", " ")


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
    for cand in (name, slug, slug.lower()):
        if os.path.isdir(os.path.join(root, cand)):
            return start_session(cfg, state, lock, topic,
                                 f"{slug} {os.path.join(root, cand)}", "claude")
    return None


def usage_line(cfg, snap, sep="  "):
    """5-hour and weekly windows, straight from what the status line was told."""
    out = []
    for key, label in (("five_hour", "5h"), ("seven_day", "7d")):
        w = (snap or {}).get(key) or {}
        if w.get("used_percentage") is None:
            continue
        at = w.get("resets_at")
        out.append(f"{label} {w['used_percentage']:.0f}%" + (
            f"→{clock(cfg, at)}" if at else ""))
    ctx = (snap or {}).get("ctx_pct")
    if ctx is not None:
        out.append(f"ctx {ctx:.0f}%")
    return sep + sep.join(out) if out else ""


def status_report(cfg, state):
    if not cfg["topics"]:
        return "no topics bound"
    now, rows, alive = time.time(), [], live_sessions()
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
        q = len(st.get("queue") or [])
        rows.append(f"{icon} {sess:<14} topic {topic}  {mode}  {age}s quiet{tag}"
                    + (f"  📥{q}" if q else "") + usage_line(cfg, snap))
    return "\n".join(rows)


def handle(cfg, state, lock, topic, text, mid=None):
    """Return reply text, or None when the message was typed into the session."""
    sess = cfg["topics"].get(topic)
    # Telegram rewrites "/compact" as "/compact@thebot" in groups; Claude wants
    # the bare slash command.
    text = re.sub(r"^(/[\w:-]+)@\w+", r"\1", text)
    cmd, _, arg = text.partition(" ")
    cmd, arg = cmd.lower(), arg.strip()
    # Registered slash aliases so Telegram's "/" menu can drive tgctl too. Names
    # that Claude Code also owns are deliberately absent: those pass through.
    if cmd[1:] in TG_SLASH:
        cmd = TG_SLASH[cmd[1:]]
        text = f"{cmd} {arg}".strip()

    if cmd == "!version":
        return version_report()
    if cmd == "!help":
        return ("!bind <session> | !unbind | !sessions\n"
                f"!new <name> [dir] [flags], or !<agent>: "
                f"{', '.join(agents(cfg))}\n"
                "!resume [agy] = relaunch this topic's dir with --continue\n"
                "!status (all topics) | !pane [lines] | !verbose | !kill | !ctl\n"
                "!git | !diff (session's cwd) | !get <path> | !log (daemon journal)\n"
                "!queue [clear|now] | !usage | !ctx | !cost [days] | !tz | !reload\n"
                "!version = build, python, and which hooks are wired\n"
                "!grep <text> [days] searches every transcript\n"
                "!autocompact <pct|off> | !idlectx <pct|off>\n"
                "type / for the same commands with autocomplete\n"
                "!model <name> | !effort <low|medium|high>\n"
                "!1..!9 menu pick | !y !n !esc !int !enter !up !down !tab !mode\n"
                "!keys <tmux keys> | !raw <text> (type even with a menu open)\n"
                "photo/file -> saved, path typed in\n"
                "/slash and anything else -> typed into Claude")
    if cmd == "!log":
        return run("journalctl", "--user", "-u", "tgctl", "-n", "40", "--no-pager")
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
        if not has_session(arg):
            return f"no tmux session '{arg}'"
        with lock:
            cfg["topics"][topic] = arg
            save_cfg(cfg)
        state.pop(arg, None)
        return f"topic bound to '{arg}'"
    if cmd == "!unbind":
        with lock:
            old = cfg["topics"].pop(topic, None)
            save_cfg(cfg)
        return f"unbound '{old}'" if old else "not bound"
    if cmd == "!new" or cmd[1:] in agents(cfg):
        return start_session(cfg, state, lock, topic, arg,
                             default_agent(cfg) if cmd == "!new" else cmd[1:])
    if cmd == "!resume":
        # Whatever started this topic, unless told otherwise: resuming a codex
        # session with claude's flag would quietly open a fresh conversation.
        key = arg if arg in agents(cfg) else (
            (cfg.get("started") or {}).get(topic) or default_agent(cfg))
        name = sess or f"topic{topic}"
        if has_session(name):
            return f"'{name}' is alive; type /resume in it to pick a conversation"
        cwd = (cfg.get("dirs") or {}).get(topic, "~")
        return start_session(cfg, state, lock, topic,
                             f"{name} {cwd} {agent(cfg, key)[1]}".rstrip(), key)

    if not sess:
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
        tmux("send-keys", "-t", sess, *arg.split())
        return None
    if cmd in KEYS:
        tmux("send-keys", "-t", sess, KEYS[cmd])
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
    if cmd == "!raw":  # deliberate override of the menu guard below
        inject(sess, arg)
        remember(state, sess, arg)
        started(cfg, state, topic, sess, mid)
        return None
    if cmd in ("!model", "!effort"):  # sugar: type the slash command for you
        text = f"/{cmd[1:]} {arg}".strip()

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
    inject(sess, text)
    remember(state, sess, text)
    started(cfg, state, topic, sess, mid)
    return None


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
UNIT_PATH = os.path.expanduser("~/.config/systemd/user/tgctl.service")

SIDECAR_SH = """#!/bin/bash
# tgctl status line. The pipe below is the point: it parks the context
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

[Install]
WantedBy=default.target
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
    return [n for n, p in (("stop", "tg-stop.py"), ("notify", "tg-notify.py"),
                           ("sidecar", "tg-state.py")) if p in blob]


def version_report():
    rev = tmux_git(HERE, "rev-parse", "--short", "HEAD")
    on = wired()
    return (f"tgctl {VERSION}" + (f" ({rev})" if rev and " " not in rev else "")
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
    for event, script in (("Stop", "tg-stop.py"), ("Notification", "tg-notify.py")):
        groups = settings.setdefault("hooks", {}).setdefault(event, [])
        if any(script in h.get("command", "")
               for g in groups for h in g.get("hooks") or []):
            continue
        groups.append({"hooks": [{"type": "command", "timeout": 20, "command":
                                  f"{sys.executable} {os.path.join(HERE, script)}"}]})
        notes.append(f"hook {event} -> {script}")
    sidecar = os.path.join(HERE, "tg-state.py")
    line = f'printf \'%s\' "$input" | {sys.executable} {sidecar} >/dev/null 2>&1 &'
    if not settings.get("statusLine"):
        sh = os.path.join(os.path.dirname(path), "tgctl-statusline.sh")
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
    os.makedirs(os.path.dirname(UNIT_PATH), exist_ok=True)
    with open(UNIT_PATH, "w") as f:
        f.write(UNIT.format(py=sys.executable,
                            script=os.path.join(HERE, "tgctl.py")))
    # Without linger a user service stops at logout and never starts at boot,
    # which is exactly when a phone-driven controller needs to be up.
    subprocess.run(("loginctl", "enable-linger"), capture_output=True)
    subprocess.run(("systemctl", "--user", "daemon-reload"), capture_output=True)
    return run("systemctl", "--user", "enable", "--now", "tgctl")


def setup():
    """Interactive first run: token, group, allowlist, hooks, service."""
    if not sys.stdin.isatty():
        sys.exit("--setup needs a terminal")
    try:
        cfg = load_cfg()
    except (OSError, ValueError):
        cfg = {}
    print("tgctl setup\n\n"
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
    if input("Install and start the systemd user service? [Y/n] ").strip().lower() \
            not in ("", "y", "yes"):
        print(f"skipped. Run it yourself with: {sys.executable} {__file__}")
        return
    print(wire_unit() or f"   started, unit at {UNIT_PATH}")
    print("\nDone. In the group: create a topic, then send\n"
          "   !new myproj ~/code/myproj\n"
          "and type to it. !help lists the rest.")


def main():
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
    for sess, held in load_queue(state).items():
        topic = next((t for t, s in cfg["topics"].items() if s == sess), None)
        until = held.get("limit_until", 0)
        print(f"restored {len(held['queue'])} queued prompt(s) for {sess}", flush=True)
        if topic:
            send(cfg, topic, f"↩️ tgctl restarted · {len(held['queue'])} queued "
                 f"prompt(s) kept" + (f", still holding until {clock(cfg, until)}"
                                      if until > time.time() else ""), mode="plain")
    threading.Thread(target=watcher, args=(cfg, state, lock), daemon=True).start()

    # Resume where we stopped: a restart loses nothing. Kept out of the config
    # file, which is hand-edited and must not churn once per message.
    offset = load_offset() or cfg.pop("offset", None)  # migrate the old in-config one
    if offset is None:          # first ever run: skip whatever piled up
        res = (api(cfg, "getUpdates", offset=-1, timeout=0).get("result")) or []
        offset = res[-1]["update_id"] + 1 if res else None
    allow = {int(u) for u in cfg["allow_users"]}
    acks = Acks()
    print(f"tgctl up. chat={cfg['chat_id']} topics={cfg['topics']} offset={offset}",
          flush=True)

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
    named = (msg.get("forum_topic_created") or {}).get("name")
    print(f"upd chat={chat} user={user} topic={topic} text={text[:40]!r}"
          f"{' [cb]' if cq else ''}{' [file]' if att or doc else ''}"
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
    if not (text or att or doc):
        return
    if user not in allow:
        print(f"  drop: user {user} not in allow_users", flush=True)
        return
    if att or doc:  # hand Claude the path; it reads images and files itself
        path = fetch_file(cfg, doc.get("file_id") or att, doc.get("file_name"))
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


def selfcheck():
    assert chunks("a\nb") == ["a\nb"]
    assert chunks("x" * 10, 4) == ["xxxx", "xxxx", "xx"]
    big = "\n".join("y" * 100 for _ in range(100))
    assert all(len(c) <= LIMIT for c in chunks(big))
    assert "\n".join(chunks(big)) == big

    assert common_prefix(["a", "b", "c"], ["a", "b", "z"]) == 2

    assert "timed out after 1s" in run("tmux", "wait-for", "tgctl-selfcheck", timeout=1)
    assert run("echo", "hi") == "hi"

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
    os.remove(tp)

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
    assert pane_state(["Do you want to proceed?", "❯ 1. Yes", "  2. No"]) == "waiting"

    menu = menu_buttons(["Do you want to proceed?", "❯ 1. Yes",
                         "│   2. Yes, and don't ask again │", "  3. No (esc)"])
    assert json.loads(menu)["inline_keyboard"][:3] == [
        [{"text": "1. Yes", "callback_data": "!1"}],
        [{"text": "2. Yes, and don't ask again", "callback_data": "!2"}],
        [{"text": "3. No (esc)", "callback_data": "!3"}]], menu

    cfg, state, screen = {"topics": {}, "chat_id": -1}, {}, []
    sent = []
    globals()["send"] = lambda c, t, x, mode="mono", buttons=None, quiet=False: (
        sent.append(x), 77)[1]
    globals()["has_session"] = lambda s: True
    globals()["pane"] = lambda s: list(screen)
    globals()["visible"] = lambda s: list(screen)
    globals()["hooked"] = lambda s: False
    twice = lambda: (flush_new(cfg, state, "1", "s"), flush_new(cfg, state, "1", "s"))

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
    globals()["inject"] = lambda s, t: typed.append(t)
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
    state.pop("other"), _warned.clear()

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
    n = len(sent)                                 # quoted output is not the banner
    screen[:] = ["● done",
                 "  ⎿  Error during compaction: You've hit your monthly limit"] + box
    flush_new(cfg, state, "1", "s")
    assert len(sent) == n and "limit_line" not in st, sent[-1]
    screen[:] = ["● done", "You've hit your 5-hour limit · resets in 1h 0m"] + box
    st["snap"] = {"ts": time.time(),              # sidecar outranks a stale screen
                  "five_hour": {"used_percentage": 40, "resets_at": time.time() + 99}}
    check_limit(cfg, st, "1", "s", screen, False)
    assert len(sent) == n and "limit_until" not in st, sent[-1]
    st["snap"]["five_hour"]["used_percentage"] = 100   # ... and when it is spent
    check_limit(cfg, st, "1", "s", screen, False)
    assert sent[-1].startswith("⏸ s hit the usage limit") and st["limit_until"]
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
    st.pop("prog_msg"), st.pop("limit_line")

    # A window that resets with nothing queued must still clear the hold and say
    # so. The silent version left the session flagged as limited for good, and
    # left the topic with no word at the time tgctl had promised one.
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
    # An unhandled !command is typed into the session as text, so the cancel
    # button has to be a real command or declining would inject "!cancel".
    assert len(sent) == n + 1 and len(typed) == t, (sent[n:], typed[t:])
    screen[:] = ["● done"] + box
    assert handle(cfg, state, threading.Lock(), "1", "next task") is None
    assert typed[-1] == "next task", typed

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
    assert "5h 12%" in status_report({"topics": {"1": "s"}}, state)
    os.remove(tp)

    cfg["topics"] = {"1": "s"}                    # status + watchdog
    assert "✅ s" in status_report(cfg, state) and "topic 1" in status_report(cfg, state)
    assert watchdog(cfg, state, "1", "s", False) is False and "💀" in sent[-1]
    n = len(sent)
    watchdog(cfg, state, "1", "s", False)         # dead stays quiet after the first
    assert len(sent) == n
    watchdog(cfg, state, "1", "s", True)
    assert "↩️" in sent[-1] and "s" not in state   # rebaselined, no history dump
    globals()["live_sessions"] = lambda: {}
    assert "💀 gone" in status_report({"topics": {"2": "gone"}}, {})

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
    assert stop[0] == "mine.sh" and stop[1].endswith("tg-stop.py"), stop
    got["statusLine"] = {"type": "command", "command": "bash /nope/theirs.sh"}
    with open(sfile, "w") as f:
        json.dump(got, f)
    assert "add this line" in wire_claude(sfile)[0]  # theirs: instructions, not a rewrite
    with open(sfile) as f:
        assert "theirs.sh" in json.load(f)["statusLine"]["command"]
    assert sorted(wired(sfile)) == ["notify", "stop"]   # their status line: no sidecar
    assert wired(os.path.join(STATE_DIR, "nope.json")) == []

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

    for n_ in os.listdir(STATE_DIR):
        os.remove(os.path.join(STATE_DIR, n_))
    os.rmdir(STATE_DIR)
    print("selfcheck ok")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        selfcheck()
    elif "--setup" in sys.argv:
        setup()
    elif "--version" in sys.argv:
        print(version_report())
    else:
        main()
