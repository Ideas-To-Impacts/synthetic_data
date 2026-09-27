"""
Long runs always live in tmux.

A generation run on a remote machine (RunPod) takes hours, and a process
started from an SSH terminal dies with the connection - a closed laptop is
enough. So a command that can run long calls :func:`ensure` once its
arguments are read: outside tmux it starts itself again in a new, detached
tmux session - same interpreter, arguments, directory and FIDEON_*/CUDA
settings - logs to ``logs/<session>-<time>.log``, says how to watch it, and
returns. Inside tmux it does nothing, and the run goes on.

    FIDEON_NO_TMUX=1   run in the foreground anyway (tests, CI, a quick look)

On Windows there is no tmux and nothing changes.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

#: environment a run depends on, handed to the tmux session explicitly: a
#: session started by an existing tmux server gets the server's environment,
#: not the calling shell's
PASS = re.compile(r"^(FIDEON_|CUDA_|PYTHON|OMP_|HF_|VIRTUAL_ENV$|PATH$|LD_LIBRARY_PATH$)")
WINDOWS = os.name == "nt"


def ensure(command, name):
    """Continue only inside tmux. ``command`` is the argv that runs this
    program again (``[sys.executable, "-m", "fideon_synth.cli", ...]``);
    ``name`` the session name. Returns only when the caller should go on
    running here; otherwise exits after starting the tmux session."""
    if WINDOWS or os.environ.get("TMUX") or os.environ.get("FIDEON_NO_TMUX"):
        return
    if not shutil.which("tmux"):
        sys.exit("  This run needs tmux so it survives a closed terminal. Install it:\n"
                 "      apt-get update && apt-get install -y tmux\n"
                 "  or run in the foreground on purpose with FIDEON_NO_TMUX=1")

    session = _free_name(name)
    logs = Path.cwd() / "logs"
    logs.mkdir(exist_ok=True)
    log = logs / ("%s-%s.log" % (session, datetime.now().strftime("%Y%m%d-%H%M%S")))
    env = ["%s=%s" % (k, v) for k, v in sorted(os.environ.items()) if PASS.match(k)]
    run = shlex.join(["env"] + env + list(command))
    # the window stays open when the run ends, so its last lines and exit
    # code can still be read after reattaching
    script = ("set -o pipefail; %s 2>&1 | tee -a %s; code=$?; echo; "
              "echo \"[finished with exit code $code - log: %s]\"; exec bash"
              % (run, shlex.quote(str(log)), log))
    subprocess.run(["tmux", "new-session", "-d", "-s", session, "-c", str(Path.cwd()),
                    "bash", "-c", script], check=True)
    print("  Running in tmux session '%s' - it keeps going if this terminal closes." % session)
    print("    watch:   tmux attach -t %s    (detach again: Ctrl+B, then D)" % session)
    print("    log:     tail -f %s" % log)
    sys.exit(0)


def _free_name(name):
    taken = subprocess.run(["tmux", "list-sessions", "-F", "#{session_name}"],
                           capture_output=True, text=True).stdout.split()
    if name not in taken:
        return name
    n = 2
    while "%s-%d" % (name, n) in taken:
        n += 1
    return "%s-%d" % (name, n)
