#!/usr/bin/env python3
"""`nightmux run`: what must hold when the agent misbehaves. Fake shell agents only.

Run:  python3 tests/test_run.py
"""
import os
import shutil
import stat
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "acceptance"))
from _h import cli, fake_home, run  # noqa: E402

FAST = {"NIGHTMUX_RUN_POLL": "0.3"}

# An idle prompt, and a "turn" for the lines it knows. Anything else is ignored.
# The busy footer is erased when the turn ends, as a real TUI does.
GOOD = """#!/bin/sh
stty -echo
printf 'fake ready\\n❯ '
while IFS= read -r line; do
  case "$line" in
  *"still fails"*)
    touch busy.flag; printf '✻ Working… (esc to interrupt)'; sleep 2; printf '\\r\\033[K'
    echo "$line" >> got.log; touch ok.flag; rm busy.flag; printf 'fixed it\\n' ;;
  *"usage limit"*"carry on"*|*"carry on"*)
    echo "$line" >> got.log; touch b.flag; printf 'carrying on\\n' ;;
  *"do the thing"*|*"usage limit reached"*)
    touch busy.flag; printf '✻ Working… (esc to interrupt)'; sleep 2; printf '\\r\\033[K'
    rm busy.flag; printf 'did: %s\\ntried\\n' "$line" ;;
  esac
  printf '❯ '
done
"""
LOGIN = "#!/bin/sh\necho 'please log in'\nexit 1\n"
LIMITED = """#!/bin/sh
stty -echo
printf 'fake ready\\n❯ '
while IFS= read -r line; do
  case "$line" in *"do the thing"*) printf "You've hit your 5-hour limit · resets 3pm\\n" ;; esac
  printf '❯ '
done
"""


def setup(**scripts):
    home = fake_home()
    work = os.path.join(home, "proj")
    os.makedirs(work)
    cfg = []
    for name, body in scripts.items():
        path = os.path.join(home, name)
        with open(path, "w") as f:
            f.write(body)
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
        cfg.append('"%s": ["%s", ""]' % (name, path))
    with open(os.path.join(home, ".nightmux.json"), "w") as f:
        f.write('{"agents": {%s}}' % ",".join(cfg))
    os.chmod(os.path.join(home, ".nightmux.json"), 0o600)
    return home, work


def go(home, work, *args, **kw):
    try:
        return cli("run", *args, home=home, cwd=work, env=dict(FAST, **kw.get("env", {})), timeout=90)
    finally:
        subprocess.run(["tmux", "kill-server"], capture_output=True,
                       env={"PATH": os.environ["PATH"], "TMUX_TMPDIR": home})


def out(r):
    return f"exit {r.returncode}\n{r.stdout[-700:]}\n{r.stderr[-400:]}"


def test_exited_agent_never_gets_the_task():
    home, work = setup(login=LOGIN)
    r = go(home, work, "touch PWNED", "--agents", "login")
    assert not os.path.exists(os.path.join(work, "PWNED")), "the task ran in a shell\n" + out(r)
    assert r.returncode == 3, out(r)
    assert "exited" in r.stdout, out(r)


def test_task_text_is_not_a_limit_banner():
    home, work = setup(a=GOOD, b=GOOD)
    r = go(home, work, "do the thing: make the client retry when the API says usage limit reached",
           "--agents", "a,b")
    assert r.returncode == 0 and "usage limit hit" not in r.stdout, out(r)


def test_check_waits_for_idle_and_feedback_arrives():
    home, work = setup(a=GOOD)
    r = go(home, work, "do the thing", "--agents", "a", "--max-turns", "3",
           "--until", "test ! -f busy.flag && echo x >> checks.log && test -f ok.flag")
    assert r.returncode == 0, out(r)
    assert "passed after 2 turns" in r.stdout, out(r)
    with open(os.path.join(work, "checks.log")) as f:
        assert len(f.read().split()) == 2, "the check ran while the agent was busy"
    with open(os.path.join(work, "got.log")) as f:
        assert "still fails" in f.read(), "feedback never reached the agent"


def test_limit_fails_over_with_a_brief():
    home, work = setup(a=LIMITED, b=GOOD)
    r = go(home, work, "do the thing", "--agents", "a,b", "--until", "test -f b.flag")
    assert r.returncode == 0, out(r)
    assert "a: usage limit hit" in r.stdout, out(r)
    with open(os.path.join(work, "got.log")) as f:
        assert "hit its usage limit" in f.read(), "the next agent got no brief"


def test_usage_errors_exit_2():
    home, work = setup(a=GOOD)
    assert go(home, work, "x", "--until").returncode == 2
    assert go(home, work, "x", "--until", "").returncode == 2
    r = go(home, work, "x", "--agents", "a", env={"PATH": "/nonexistent"})
    assert r.returncode == 2 and "tmux" in r.stderr, out(r)


def test_existing_session_is_left_alone():
    home, work = setup(a=GOOD)
    log = os.path.join(home, "typed.log")
    tenv = {"PATH": os.environ["PATH"], "TMUX_TMPDIR": home}
    subprocess.run(["tmux", "new-session", "-d", "-s", "proj", "cat > " + log], env=tenv, check=True)
    try:
        r = cli("run", "do the thing", "--agents", "a", home=home, cwd=work, env=FAST, timeout=90)
        assert r.returncode == 0, out(r)
        alive = subprocess.run(["tmux", "has-session", "-t", "proj:"], env=tenv).returncode == 0
        assert alive, "run killed a session it did not create"
        with open(log) as f:
            assert f.read() == "", "run typed into a session it did not create"
    finally:
        subprocess.run(["tmux", "kill-server"], capture_output=True, env=tenv)


def test_survivor_is_named_with_attach_and_kill():
    home, work = setup(a=GOOD)
    r = go(home, work, "do the thing", "--agents", "a")
    assert r.returncode == 0, out(r)
    assert "tmux attach -t proj" in r.stdout and "tmux kill-session -t proj" in r.stdout, out(r)


if __name__ == "__main__":
    if not shutil.which("tmux"):
        print("skipped: no tmux")
        sys.exit(0)
    sys.exit(run([test_exited_agent_never_gets_the_task, test_task_text_is_not_a_limit_banner,
                  test_check_waits_for_idle_and_feedback_arrives, test_limit_fails_over_with_a_brief,
                  test_usage_errors_exit_2, test_existing_session_is_left_alone,
                  test_survivor_is_named_with_attach_and_kill]))
