"""test_review: cut from the old monolithic selfcheck() (the last part)."""
import os
import subprocess
import sys
import tempfile
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_review_changed_untracked_clean():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        cfg2 = {"topics": {}, "agents": {"opencode": ["opencode", "--resume"]}}
        spawned, lk = [], threading.Lock()
        nightmux.spawn = lambda n, cwd, line, cfg=None: spawned.append((n, cwd, line))
        nightmux.has_session = lambda n: False
        nightmux.start_session(cfg2, {}, lk, "9", "box ~ --sandbox", "codex")
        repo = tempfile.mkdtemp(prefix="nightmux-selfcheck-")
        subprocess.run(["git", "init", "-q", repo], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.email", "t@t"], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.name", "t"], check=True)
        with open(os.path.join(repo, "f"), "w") as f:
            f.write("one")
        subprocess.run(["git", "-C", repo, "add", "f"], check=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "init"], check=True)
        wt = nightmux.worktree_path(repo, "feature-a")

        # !review / review_data: a changed file, an untracked one, a clean repo
        with open(os.path.join(repo, "f"), "w") as f:
            f.write("two\n")
        with open(os.path.join(repo, "new.txt"), "w") as f:
            f.write("x")
        with nightmux.stubbed(sess_cwd=lambda s: repo, has_session=lambda s: True, real_session=lambda s: s):
            rd_ = nightmux.review_data({"topics": {"9": "revs"}}, {}, "9")
            assert [(f["path"], f["add"], f["del"]) for f in rd_["files"]] == [("f", 1, 1)], rd_
            assert rd_["untracked"] == ["new.txt"] and rd_["session"] == "revs" and rd_["pr"] is None, rd_
            assert "+two" in rd_["files"][0]["diff"] and "-one" in rd_["files"][0]["diff"], rd_
            assert nightmux.review_data({"topics": {}}, {}, "9")["error"] == "topic not bound"
            sent_ = []
            with nightmux.stubbed(send=lambda *a, **k: sent_.append((a, k))):
                c9_ = dict(cfg2, topics={"9": "revs"}, office_url=None)
                txt_ = nightmux.handle(c9_, {}, lk, "9", "!review")
                assert "1 files +1 −1" in txt_ and "f  +1 −1" in txt_ and "new untracked" in txt_, txt_
                assert nightmux.handle(dict(c9_, office_url="https://b.ts.net:9090/office"), {}, lk, "9", "!review") is None
                assert "https://b.ts.net:9090/review/9" in sent_[-1][1]["buttons"], sent_
        subprocess.run(["git", "-C", repo, "checkout", "-q", "--", "f"], check=True)
        os.remove(os.path.join(repo, "new.txt"))
