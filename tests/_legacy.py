"""The stub trap that the old selfcheck() set up once and everything after it relied on.

    with isolated(nightmux) as iso:
        cfg, state, screen, sent = legacy_stubs(nightmux)

`screen` is what pane()/visible() return; `sent` collects the text of every send().
Call it inside isolated(): that is what puts the module's globals back afterwards.
"""


def legacy_stubs(mod):
    cfg, state, screen, sent = {"topics": {}, "chat_id": -1}, {}, [], []
    mod.send = lambda c, t, x, mode="mono", buttons=None, quiet=False: (sent.append(x), 77)[1]
    mod.has_session = lambda s: True
    mod.pane = lambda s: list(screen)
    mod.visible = lambda s: list(screen)
    mod.hooked = lambda s: False
    # A path that is never a directory, so snapshot_repo's git check is skipped
    # without shelling out: the real sess_cwd would block on a tmux pane that was
    # never created here.
    mod.sess_cwd = lambda s: "/nonexistent-nightmux-selfcheck"
    return cfg, state, screen, sent
