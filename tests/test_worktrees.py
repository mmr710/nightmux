"""test_worktrees: cut from the old monolithic selfcheck() (the last part)."""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_worktrees_and_snapshot_before_prompt():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        # git worktrees + snapshot-before-unattended-prompt, against a real throwaway repo.
        repo = os.path.realpath(tempfile.mkdtemp(prefix="nightmux-selfcheck-"))
        subprocess.run(["git", "init", "-q", repo], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.email", "t@t"], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.name", "t"], check=True)
        with open(os.path.join(repo, "f"), "w") as f:
            f.write("one")
        subprocess.run(["git", "-C", repo, "add", "f"], check=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "init"], check=True)

        assert nightmux.worktree_path("/no/such/dir", "x") is None    # not a repo: nothing to attach to
        wt = nightmux.worktree_path(repo, "feature-a")
        assert wt == os.path.join(f"{repo}-wt", "feature-a") and os.path.isdir(wt), wt
        assert nightmux.tmux_git(repo, "rev-parse", "--verify", "--quiet", "refs/heads/feature-a")
        assert nightmux.worktree_path(repo, "feature-a") == wt        # already there: reused, not redone


def test_sandbox_cmd_shape():
    with isolated(nightmux):
        legacy_stubs(nightmux)
        repo = os.path.realpath(tempfile.mkdtemp(prefix="nightmux-selfcheck-"))
        subprocess.run(["git", "init", "-q", repo], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.email", "t@t"], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.name", "t"], check=True)
        with open(os.path.join(repo, "f"), "w") as f:
            f.write("one")
        subprocess.run(["git", "-C", repo, "add", "f"], check=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "init"], check=True)
        nightmux.worktree_path(repo, "feature-a")

        # sandbox_cmd: shape of the docker line, mounts only what exists, off by default
        sbc_ = {"sandbox": {"names": ["box"], "mounts": ["~/.claude", "/no/such/thing"], "network": "none", "image": "img"}}
        assert nightmux.sandboxed(sbc_, "box") and not nightmux.sandboxed(sbc_, "other") and nightmux.sandboxed({"sandbox": {"all": 1}}, "x")
        line_ = nightmux.sandbox_cmd(sbc_, "bo.x", repo, "claude --foo", tty=False)
        assert line_.startswith("docker run --rm --name nm-bo.x -u ") and "--cap-drop ALL" in line_, line_
        assert "--network none" in line_ and "no/such" not in line_ and line_.endswith("img sh -c 'claude --foo'"), line_
        assert f"-v {repo}:{repo} -w {repo}" in line_ and "-it" not in line_.split(), line_
        assert "docker run --rm -it " in nightmux.sandbox_cmd(sbc_, "b", repo, "x") or "-it" in nightmux.sandbox_cmd(sbc_, "b", repo, "x")
