"""test_setup: cut from tests/selfcheck.py (stubbed part)."""
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
    with isolated(nightmux) as iso:
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
    with isolated(nightmux) as iso:
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
    with isolated(nightmux) as iso:
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
