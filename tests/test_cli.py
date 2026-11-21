"""test_cli: cut from the old monolithic selfcheck() (the last part)."""
import contextlib
import io
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def cli_(*args):
    old_argv_, sys.argv = sys.argv, ["nightmux", *args]
    out_, err_, code_ = io.StringIO(), io.StringIO(), None
    try:
        with contextlib.redirect_stdout(out_), contextlib.redirect_stderr(err_):
            nightmux.cli()
    except SystemExit as e:
        code_ = e.code
    finally:
        sys.argv = old_argv_
    return code_, out_.getvalue(), err_.getvalue()


def test_cli_help_and_unknown_option():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        # The CLI: -h prints usage, and an unknown option stops. `nightmux --help`
        # used to fall through to main() and start a daemon on the live config.
        ran_ = []
        with nightmux.stubbed(main=lambda: ran_.append("daemon")):
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


def test_cli_wrapped_cards_private_and_share():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        ran_ = []
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
        with nightmux.stubbed(main=lambda: ran_.append("daemon")):
            with nightmux.stubbed(analyze_chats=lambda d: {"agents": {}, "when": {}}, sav_data=lambda: {"tokens": 0, "model_tokens": 0}):
                code_, out_, err_ = cli_("wrapped", "3")
                assert isinstance(code_, str) and code_.startswith("no agent transcripts") and not ran_, code_
            with tempfile.TemporaryDirectory() as wo_, nightmux.stubbed(
                    analyze_chats=lambda d: r2_, sav_data=lambda: {"tokens": 0, "model_tokens": 0},
                    browser_bin=lambda cfg: None):
                so_, se_ = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(so_), contextlib.redirect_stderr(se_):
                    nightmux.wrapped_cli(["7"], out=os.path.join(wo_, "cards"))
                priv_, pub_ = (open(os.path.join(wo_, "cards", f"nightmux-wrapped{s}.html"), encoding="utf-8").read()
                               for s in ("", "-share"))
                assert "shop" in priv_ and "shop" not in pub_ and "project 1" in pub_, (priv_, pub_)
                assert "SECRETPROMPT" not in so_.getvalue() + priv_ + pub_
                assert "$8.40 at API list prices" in so_.getvalue() and "last 7 days" in so_.getvalue(), so_.getvalue()
                assert "not counted: " in so_.getvalue() and "gpt-x" in so_.getvalue(), so_.getvalue()
                assert "Nothing was uploaded" in so_.getvalue() and "last 7 days" in se_.getvalue(), (so_.getvalue(), se_.getvalue())


def test_cli_handoff_brief_and_next_agent():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        ran_ = []
        with nightmux.stubbed(main=lambda: ran_.append("daemon")):
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
                assert nightmux.latest_chat(repo_, home=hh_) == ("claude", cl_, "add retry to the uploader")
                os.utime(cx_, (time.time() - 50,) * 2)     # newest in the repo, from its sub folder
                assert nightmux.latest_chat(repo_, home=hh_) == ("codex", cx_, "codex ask")
                assert nightmux.latest_chat(os.path.join(hh_, "nowhere"), home=hh_) == (None, None, "")
                os.utime(cx_, (time.time() - 200,) * 2)
                execs_, real_latest_ = [], nightmux.latest_chat

                def hand_(*a_, where=repo_):
                    old_cwd_ = os.getcwd()
                    os.chdir(where)
                    try:
                        with nightmux.stubbed(load_cfg=lambda: {"agents": {"codex": ["/bin/sh", ""], "opencode": ["/bin/sh", ""],
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


def test_cli_up_tmux_second_copy_phone_line():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        ran_ = []
        with nightmux.stubbed(main=lambda: ran_.append("daemon")):
            # `up`: tmux first, then no second copy, then the daemon
            from types import SimpleNamespace
            has_ = SimpleNamespace(which=lambda c: "/usr/bin/" + c)
            with nightmux.stubbed(shutil=SimpleNamespace(which=lambda c: None if c == "tmux" else "/usr/bin/" + c)):
                code_, out_, err_ = cli_("up")
            assert "tmux is not installed" in code_ and "brew install tmux" in code_ and not ran_, code_
            busy_ = socket.socket()
            busy_.bind(("127.0.0.1", 0))
            busy_.listen(1)
            uport_ = busy_.getsockname()[1]
            with nightmux.stubbed(shutil=has_, load_cfg=lambda: {"webhook_port": uport_}):
                code_, out_, err_ = cli_("up")
            assert "already in use" in code_ and "second copy" in code_ and not ran_, code_
            busy_.close()
            with nightmux.stubbed(shutil=has_, load_cfg=lambda: {"webhook_port": uport_}):
                code_, out_, err_ = cli_("up")
            assert code_ is None and ran_ == ["daemon"] and "agents found:" in out_ and "claude" in out_, (code_, out_, ran_)
            ran_.clear()
            code_, out_, err_ = cli_("up", "now")
            assert code_ == 2 and "usage: nightmux up" in err_ and not out_ and not ran_, (code_, err_)
            # ...and the phone line: no route, no QR; a route, a QR whose code is still good
            n_ = len(nightmux._pairing_codes)
            with nightmux.stubbed(phone_url=lambda cfg, status=None: None):
                msg_ = nightmux.phone_pairing({"webhook_host": "127.0.0.1", "webhook_port": 7070})
            assert "tailscale serve --bg 7070" in msg_ and "pair?code" not in msg_ and len(nightmux._pairing_codes) == n_, msg_
            with nightmux.stubbed(phone_url=lambda cfg, status=None: "https://box.ts.net"):
                msg_ = nightmux.phone_pairing({"webhook_host": "127.0.0.1"})
            code_ = re.search(r"https://box\.ts\.net/pair\?code=([\w-]+)", msg_).group(1)
            assert code_ in nightmux._pairing_codes and ("▄" in msg_ or "█" in msg_), msg_
            with nightmux.stubbed(phone_url=lambda cfg, status=None: None, get_local_ip=lambda: "192.168.1.5"):
                msg_ = nightmux.phone_pairing({"webhook_host": "0.0.0.0", "webhook_port": 7070})
            assert "http://192.168.1.5:7070/pair?code=" in msg_, msg_
            assert cli_() == (None, "", "") and ran_ == ["daemon"], ran_
