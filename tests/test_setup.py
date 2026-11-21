"""test_setup: cut from the old monolithic selfcheck() (stubbed part)."""
import json
import os
import subprocess
import sys
import tempfile
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_starter_templates():
    with isolated(nightmux):
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # 5 Starter templates
        assert len(nightmux.STARTER_TEMPLATES) == 5
        for t_k in ("landing-page", "crud-app", "telegram-bot", "chrome-extension", "cli-tool"):
            assert t_k in nightmux.STARTER_TEMPLATES
            assert len(nightmux.STARTER_TEMPLATES[t_k]["spec"]) > 50
            assert "set -euo pipefail" in nightmux.STARTER_TEMPLATES[t_k]["check_sh"]

        with tempfile.TemporaryDirectory() as tpl_dir_, nightmux.stubbed(
                spawn=lambda n, *a: None, save_cfg=lambda c: None,
                has_session=lambda n: False, send=lambda *a, **k: None):
            tcfg_ = {"projects_root": tpl_dir_, "chat_id": "local", "allow_users": [0], "topics": {}}
            tok_, tmsg_, ttop_ = nightmux.create_starter_project(tcfg_, {}, threading.Lock(), "cli-tool",
                                                        title="My CLI", name="my-cli",
                                                        folder=os.path.join(tpl_dir_, "my-cli"),
                                                        agent="claude")
            assert tok_ is True, tmsg_
            assert os.path.isfile(os.path.join(tpl_dir_, "my-cli", "SPEC.md"))
            check_file_ = os.path.join(tpl_dir_, "my-cli", "check.sh")
            assert os.path.isfile(check_file_)
            assert os.access(check_file_, os.X_OK)
            assert os.path.isdir(os.path.join(tpl_dir_, "my-cli", ".git"))


def test_daemon_path_grows_by_user_bin_dirs():
    with isolated(nightmux):
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # The daemon's PATH grows by the user bin dirs that exist, never duplicates.
        with tempfile.TemporaryDirectory() as hp_:
            os.makedirs(os.path.join(hp_, ".local", "bin"))
            env_ = {"PATH": "/usr/bin", "SHELL": "/nonexistent-shell", "HOME": hp_}
            old_home_ = os.environ.get("HOME")
            os.environ["HOME"] = hp_
            try:
                nightmux.widen_path(env_)
                nightmux.widen_path(env_)
            finally:
                os.environ["HOME"] = old_home_
            parts_ = env_["PATH"].split(os.pathsep)
            assert parts_[0] == "/usr/bin" and os.path.join(hp_, ".local", "bin") in parts_
            assert len(parts_) == len(set(parts_)), parts_


def test_tools_mcp_add_per_agent():
    with isolated(nightmux):
        cfg, state, screen, sent = legacy_stubs(nightmux)
        # !tools: each agent's own `mcp add`, project-local for Claude; opencode's
        # missing remove edits its project file; the agent is told it has the tool.
        assert nightmux.mcp_argv("claude", "add", "pw", ["npx", "x"]) == \
            ["claude", "mcp", "add", "-s", "local", "pw", "--", "npx", "x"]
        assert nightmux.mcp_argv("agy", "add", "pw", ["npx", "x"]) == ["agy", "mcp", "add", "pw", "npx", "x"]
        assert nightmux.mcp_argv("opencode", "remove", "pw") is None and nightmux.mcp_argv("aider", "add", "pw") is None
        assert "--no-sandbox" in nightmux.tool_cmd({}, "browser")
        ran_ = []
        with tempfile.TemporaryDirectory() as td_, nightmux.stubbed(
                save_cfg=lambda c: None, send=lambda *a, **k: None,
                subprocess=type("S", (), {"run": staticmethod(lambda a, **k: ran_.append(a) or
                                           type("P", (), {"returncode": 0, "stdout": "", "stderr": ""})()),
                                           "DEVNULL": subprocess.DEVNULL,
                                           "TimeoutExpired": subprocess.TimeoutExpired})):
            tc_ = {"topics": {"5": "t"}, "dirs": {"5": td_}, "started": {"5": "claude"},
                   "bench": {"5": {"claude": "t", "opencode": "t-oc"}}}
            tst_ = {}
            nightmux.tools_cmd(tc_, tst_, threading.Lock(), "5", "t", "add browser all")
            assert [a[0] for a in ran_] == ["claude", "opencode"] and tc_["tools"]["5"] == ["browser"]
            assert "browser" in tst_["t"]["queue"][0]
            with open(os.path.join(td_, "opencode.json"), "w") as f:
                json.dump({"mcp": {"playwright": {}, "other": {}}}, f)
            nightmux.tools_cmd(tc_, tst_, threading.Lock(), "5", "t", "rm browser all")
            with open(os.path.join(td_, "opencode.json")) as f:
                assert json.load(f)["mcp"] == {"other": {}}
            assert ran_[-1][:3] == ["claude", "mcp", "remove"] and tc_["tools"]["5"] == []


def test_setup_chat_binds_forum_and_ignores_others():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        forum = {"message": {"chat": {"id": -100, "type": "supergroup",
                                      "is_forum": True, "title": "work"},
                             "from": {"id": 7}}}
        assert nightmux.setup_chat(forum) == (-100, 7, "work")
        added = {"my_chat_member": {"chat": forum["message"]["chat"], "from": {"id": 7},
                                     "new_chat_member": {"status": "administrator"}}}
        assert nightmux.setup_chat(added) == (-100, 7, "work")      # bot added: bound before anyone types
        for bad in ({"message": {"chat": {"id": 5, "type": "private"}}},   # DM: no topics
                    {"message": {"chat": {"id": -1, "type": "supergroup"}}},  # topics off
                    {"edited_message": {"chat": {"id": -1, "type": "supergroup"}}}):
            assert nightmux.setup_chat(bad) is None, bad


def test_wire_claude_settings_idempotent_and_theirs():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        sfile = os.path.join(nightmux.STATE_DIR, "settings.json")
        os.makedirs(nightmux.STATE_DIR, exist_ok=True)
        with open(sfile, "w") as f:                    # an existing settings file
            json.dump({"model": "opus", "hooks": {"Stop": [{"hooks": [
                {"type": "command", "command": "mine.sh"}]}]}}, f)
        assert len(nightmux.wire_claude(sfile)) == 3            # Stop, Notification, status line
        with tempfile.TemporaryDirectory() as h_:     # new box: no ~/.claude yet
            fresh_ = os.path.join(h_, ".claude", "settings.json")
            assert len(nightmux.wire_claude(fresh_)) == 3
            assert os.path.exists(os.path.join(h_, ".claude", "nightmux-statusline.sh"))
        assert nightmux.wire_claude(sfile) == [], "re-running setup duplicated a hook"
        with open(sfile) as f:
            got = json.load(f)
        assert got["model"] == "opus"                  # unrelated settings survive
        stop = [h["command"] for g in got["hooks"]["Stop"] for h in g["hooks"]]
        assert stop[0] == "mine.sh" and stop[1].endswith("nightmux_stop.py"), stop
        got["statusLine"] = {"type": "command", "command": "bash /nope/theirs.sh"}
        with open(sfile, "w") as f:
            json.dump(got, f)
        assert "add this line" in nightmux.wire_claude(sfile)[0]  # theirs: instructions, not a rewrite
        with open(sfile) as f:
            assert "theirs.sh" in json.load(f)["statusLine"]["command"]
        assert sorted(nightmux.wired(sfile)) == ["notify", "stop"]   # their status line: no sidecar
        assert nightmux.wired(os.path.join(nightmux.STATE_DIR, "nope.json")) == []


def test_migrate_adopts_every_old_name():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        scratch = os.path.join(os.path.dirname(nightmux.FILE_DIR), ".mig-selfcheck")
        os.makedirs(scratch, exist_ok=True)
        newer = os.path.join(scratch, "nightmux.json")
        for was in nightmux.WAS:                   # every old name is adopted, not just the last
            older = newer.replace("nightmux", was)
            open(older, "w").close()
            nightmux.migrate([newer])
            assert os.path.exists(newer) and not os.path.exists(older), was
            os.remove(newer)
        older = newer.replace("nightmux", nightmux.WAS[0])
        open(older, "w").close()
        open(newer, "w").close()          # a current file already there wins
        nightmux.migrate([newer])
        assert os.path.exists(older), "migrate clobbered the current file"
        os.remove(older), os.remove(newer)
        nightmux.migrate([newer])                  # nothing to adopt: a fresh install
        os.rmdir(scratch)
