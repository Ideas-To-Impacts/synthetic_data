"""
A long run started from a terminal moves itself into tmux (fideon_synth.tmux).
tmux itself is not run here: the calls it would get are recorded instead.
"""

from __future__ import annotations

import subprocess

import pytest

from fideon_synth import tmux


@pytest.fixture
def linux(monkeypatch, tmp_path):
    """A Linux shell outside tmux, with tmux installed; returns the tmux calls."""
    monkeypatch.setattr(tmux, "WINDOWS", False)
    monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.delenv("FIDEON_NO_TMUX", raising=False)
    monkeypatch.setattr(tmux.shutil, "which", lambda name: "/usr/bin/tmux")
    monkeypatch.chdir(tmp_path)
    calls, sessions = [], []

    def run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "\n".join(sessions), "")
    monkeypatch.setattr(tmux.subprocess, "run", run)
    return calls, sessions


def test_outside_tmux_the_run_moves_into_a_detached_session(linux, monkeypatch, tmp_path):
    calls, _ = linux
    monkeypatch.setenv("FIDEON_OCR_GPU", "cuda")
    with pytest.raises(SystemExit) as done:
        tmux.ensure(["/venv/bin/python", "-m", "fideon_synth.cli", "--source", "Data/x y"],
                    "fideon-synth")
    assert done.value.code == 0
    new = calls[-1]
    assert new[:5] == ["tmux", "new-session", "-d", "-s", "fideon-synth"]
    assert new[5:7] == ["-c", str(tmp_path)]                  # same working directory
    script = new[-1]
    assert "/venv/bin/python -m fideon_synth.cli --source 'Data/x y'" in script
    assert "FIDEON_OCR_GPU=cuda" in script                    # the settings go with it
    assert "| tee -a" in script and "exec bash" in script      # logged; window stays open
    assert (tmp_path / "logs").is_dir()


def test_a_taken_session_name_gets_a_number(linux):
    calls, sessions = linux
    sessions += ["fideon-synth", "fideon-synth-2"]
    with pytest.raises(SystemExit):
        tmux.ensure(["python"], "fideon-synth")
    assert calls[-1][4] == "fideon-synth-3"


@pytest.mark.parametrize("env", ["TMUX", "FIDEON_NO_TMUX"])
def test_inside_tmux_or_opted_out_the_run_goes_on_here(linux, monkeypatch, env):
    calls, _ = linux
    monkeypatch.setenv(env, "1")
    assert tmux.ensure(["python"], "fideon-synth") is None
    assert calls == []


def test_without_tmux_installed_it_says_how_to_get_it(linux, monkeypatch):
    monkeypatch.setattr(tmux.shutil, "which", lambda name: None)
    with pytest.raises(SystemExit) as done:
        tmux.ensure(["python"], "fideon-synth")
    assert "apt-get install -y tmux" in str(done.value.code)


def test_windows_runs_in_the_foreground(linux, monkeypatch):
    calls, _ = linux
    monkeypatch.setattr(tmux, "WINDOWS", True)
    assert tmux.ensure(["python"], "fideon-synth") is None and calls == []
