#!/usr/bin/env python3
"""`nightmux run`: what must hold when the agent misbehaves. Fake shell agents only.

Run:  python3 tests/test_run.py
"""
import os
import shutil
import stat
import subprocess
import sys
import time

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
    except subprocess.TimeoutExpired:
        raise AssertionError("nightmux run did not finish in 90s")
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


def tmx(home, *args):
    return subprocess.run(["tmux"] + list(args), capture_output=True, text=True,
                          env={"PATH": os.environ["PATH"], "TMUX_TMPDIR": home})


def bystanders(home, *names):
    for n in names:
        assert tmx(home, "new-session", "-d", "-s", n, "-x", "100", "sh").returncode == 0


def untouched(home, names, *needles):
    for n in names:
        assert tmx(home, "has-session", "-t", "=" + n).returncode == 0, f"{n} was killed"
        pane = tmx(home, "capture-pane", "-p", "-t", "=" + n + ":").stdout
        for x in needles:
            assert x not in pane, f"keys were typed into {n}:\n{pane}"


def test_existing_sessions_are_left_alone():
    home, work = setup(a=GOOD)
    names = ("proj", "proj-a", "proj-api")    # the plain name, the old fallback name, a prefix
    bystanders(home, *names)
    try:
        r = cli("run", "do the thing", "--agents", "a", home=home, cwd=work, env=FAST, timeout=90)
        assert r.returncode == 0, out(r)
        untouched(home, names, "do the thing", "fake ready", "did:")
    finally:
        tmx(home, "kill-server")


EXITS = "#!/bin/sh\nstty -echo\nprintf 'fake ready\\n❯ '\nread -r line\nsleep 0.5\nexit 0\n"


# A tmux that kills run's own session just before the first send-keys: the moment the
# session "dies between a check and an action", made exact instead of a race.
SHIM = """#!/bin/sh
if [ "$1" = send-keys ] && [ ! -f "$SHIMDIR/fired" ]; then
  touch "$SHIMDIR/fired"; "$REALTMUX" kill-session -t =proj
fi
exec "$REALTMUX" "$@"
"""


def test_prefix_session_is_never_targeted():
    home, work = setup(a=GOOD)
    shim = os.path.join(home, "shim")
    os.makedirs(shim)
    with open(os.path.join(shim, "tmux"), "w") as f:
        f.write(SHIM)
    os.chmod(os.path.join(shim, "tmux"), 0o755)
    bystanders(home, "proj-api")
    try:
        r = cli("run", "do the thing", "--agents", "a", home=home, cwd=work, timeout=90,
                env=dict(FAST, PATH=shim + ":" + os.environ["PATH"], SHIMDIR=shim,
                         REALTMUX=shutil.which("tmux")))
        assert os.path.exists(os.path.join(shim, "fired")), "shim never fired\n" + out(r)
        assert r.returncode == 3, out(r)
        untouched(home, ("proj-api",), "do the thing", "fake ready")
    finally:
        tmx(home, "kill-server")


WRAPPED = "#!/bin/sh\nexport PS1='user@host:~/proj$ '\n%s\nexec bash --norc\n"


def test_shell_left_behind_is_not_the_agent():
    home, work = setup(inner=EXITS.replace("sleep 0.5", "sleep 1"))
    wrap = os.path.join(home, "wrap")
    with open(wrap, "w") as f:
        f.write(WRAPPED % os.path.join(home, "inner"))
    os.chmod(wrap, 0o755)
    with open(os.path.join(home, ".nightmux.json"), "w") as f:
        f.write('{"agents": {"w": ["%s", ""]}}' % wrap)
    # The first run of the check leaves seen.flag; a second run (a shell executing the
    # typed feedback) is the only thing that can create MARK.
    r = go(home, work, "do the thing", "--agents", "w", "--max-turns", "3",
           "--until", "test -f seen.flag && touch MARK; touch seen.flag; false")
    assert not os.path.exists(os.path.join(work, "MARK")), "feedback was typed into a shell\n" + out(r)
    assert r.returncode != 0, out(r)


TICKING = """#!/bin/sh
stty -echo
( while :; do printf '\\0337\\033[24;1H\\033[Kclock %s\\0338' "$(date +%s%N)"; sleep 0.2; done ) &
trap 'kill $!' EXIT
printf 'fake ready\\n❯ '
while IFS= read -r line; do
  [ -n "$line" ] && touch done.flag && printf 'did: %s\\n' "$line"
  printf '❯ '
done
"""


def test_ticking_footer_does_not_stall_the_turn():
    home, work = setup(a=TICKING)
    t = time.time()
    r = go(home, work, "make the flag", "--agents", "a", "--until", "test -f done.flag")
    assert r.returncode == 0, out(r)
    assert time.time() - t < 40, "took %ds" % (time.time() - t)


ECHO = """#!/bin/sh
printf 'fake-agent ready\\n❯ '
while IFS= read -r line; do
  [ -n "$line" ] && touch done.flag && printf 'did: %s\\n' "$line"
  printf '❯ '
done
"""


def test_echo_only_agent_finishes():
    home, work = setup(a=ECHO)
    r = go(home, work, "make the flag", "--agents", "a", "--until", "test -f done.flag")
    assert r.returncode == 0, out(r)


DOCKER = """#!/bin/sh
printf '%s\\n' "$@" > "$(dirname "$0")/docker.log"
for a; do last=$a; done
exec sh -c "$last"
"""


def test_sandboxed_config_launches_through_docker():
    home, work = setup(a=GOOD)
    os.makedirs(os.path.join(home, "bin"))
    dk = os.path.join(home, "bin", "docker")
    with open(dk, "w") as f:
        f.write(DOCKER)
    os.chmod(dk, 0o755)
    with open(os.path.join(home, ".nightmux.json"), "w") as f:
        f.write('{"agents": {"a": ["%s", ""]}, "sandbox": {"all": true}}' % os.path.join(home, "a"))
    r = go(home, work, "carry on", "--agents", "a", "--until", "test -f b.flag",
           env={"PATH": os.path.join(home, "bin") + ":" + os.environ["PATH"]})
    assert r.returncode == 0, out(r)
    assert os.path.exists(os.path.join(home, "bin", "docker.log")), "run never called docker\n" + out(r)
    with open(os.path.join(home, "bin", "docker.log")) as f:
        argv = f.read().split("\n")
    assert argv[0] == "run" and "nm-proj" in argv and os.path.join(home, "a") in argv, argv


def test_brief_after_an_exit_says_exited():
    home, work = setup(a=EXITS, b=GOOD)
    r = go(home, work, "do the thing", "--agents", "a,b", "--until", "test -f b.flag")
    assert r.returncode == 0, out(r)
    with open(os.path.join(work, "got.log")) as f:
        brief = f.read()
    assert "exited" in brief and "usage limit" not in brief, brief


def test_survivor_is_named_with_attach_and_kill():
    home, work = setup(a=GOOD)
    r = go(home, work, "do the thing", "--agents", "a")
    assert r.returncode == 0, out(r)
    assert "tmux attach -t =proj" in r.stdout and "tmux kill-session -t =proj" in r.stdout, out(r)


if __name__ == "__main__":
    if not shutil.which("tmux"):
        print("skipped: no tmux")
        sys.exit(0)
    sys.exit(run([test_exited_agent_never_gets_the_task, test_task_text_is_not_a_limit_banner,
                  test_check_waits_for_idle_and_feedback_arrives, test_limit_fails_over_with_a_brief,
                  test_usage_errors_exit_2, test_existing_sessions_are_left_alone,
                  test_survivor_is_named_with_attach_and_kill, test_prefix_session_is_never_targeted,
                  test_shell_left_behind_is_not_the_agent, test_ticking_footer_does_not_stall_the_turn,
                  test_echo_only_agent_finishes, test_sandboxed_config_launches_through_docker,
                  test_brief_after_an_exit_says_exited]))
