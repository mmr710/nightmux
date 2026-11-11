#!/usr/bin/env python3
"""T1.2  install.sh follows the newest release tag, not `main`.

A stranger piping curl into sh should get what was released and tested, and
NIGHTMUX_REF=<ref> stays as the way to ask for something else.
"""
import os
import stat
import subprocess
import sys
import tempfile

from _h import ROOT, run

FAKE_GIT = """#!/bin/sh
echo "$@" >> "$GIT_LOG"
case "$1 $2" in
  "ls-remote --tags"*|"ls-remote "*) printf 'xxx\\trefs/tags/vps-test\\nyyy\\trefs/tags/v9.9.10-rc1\\naaa\\trefs/tags/v9.9.9\\nbbb\\trefs/tags/v9.9.8\\n' ;;
esac
for a in "$@"; do last="$a"; done
[ "$1" = clone ] && mkdir -p "$last/.git"
exit 0
"""


def _install(env_extra=None):
    d = tempfile.mkdtemp(prefix="nm-acc-")
    binp = os.path.join(d, "bin")
    os.makedirs(binp)
    for name, body in (("git", FAKE_GIT), ("tmux", "#!/bin/sh\nexit 0\n"),
                       ("python3", "#!/bin/sh\nexit 0\n")):
        p = os.path.join(binp, name)
        with open(p, "w") as f:
            f.write(body)
        os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR)
    log = os.path.join(d, "git.log")
    env = {"HOME": d, "PATH": binp + ":/usr/bin:/bin", "GIT_LOG": log}
    env.update(env_extra or {})
    subprocess.run(["sh", os.path.join(ROOT, "install.sh")], env=env, stdin=subprocess.DEVNULL,
                   capture_output=True, text=True, timeout=30)   # exit code: no tty here, ignored
    return open(log).read() if os.path.exists(log) else ""


def test_default_is_newest_tag():
    log = _install()
    assert "ls-remote" in log, f"never asked for the release tags:\n{log}"
    assert "v9.9.9" in log, f"did not install the newest tag v9.9.9:\n{log}"
    assert "v9.9.8" not in log, "installed an older tag"


def test_ref_override():
    log = _install({"NIGHTMUX_REF": "main"})
    assert "v9.9.9" not in log, "NIGHTMUX_REF=main was ignored"
    assert any("main" in l for l in log.splitlines() if l.split()[:1] in (["clone"], ["checkout"], ["fetch"])), log


def test_existing_checkout_is_not_pulled_blind():
    src = open(os.path.join(ROOT, "install.sh")).read()
    assert "pull -q\n" not in src and "pull -q;" not in src, \
        "a bare `git pull` moves an install to whatever main is: fetch the ref and check it out"


if __name__ == "__main__":
    sys.exit(run([test_default_is_newest_tag, test_ref_override,
                  test_existing_checkout_is_not_pulled_blind]))
