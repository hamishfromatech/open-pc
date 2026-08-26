"""Tests for the pure shell command runner.

Verifies sanitization delegation, normal execution, and the process-group kill
on timeout (SmolVM's setsid + kill(-pid) pattern). Runs on the CI runner's real
shell; no display or pyautogui required.
"""
import contextlib
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'docker'))

from command_runner import run_shell_command


def test_empty_command_actionable():
    r = run_shell_command("   ")
    assert r["success"] is False
    assert "empty" in r["error"].lower()


def test_blocked_command_is_actionable():
    r = run_shell_command("ls; rm -rf /")
    assert r["success"] is False
    assert "blocked" in r["error"].lower()
    # names the recovery, not just the problem
    assert "separately" in r["error"].lower()


def test_safe_command_runs():
    r = run_shell_command("echo openpc", timeout=5)
    assert r["success"] is True
    assert "openpc" in r["stdout"]
    assert r["return_code"] == 0


def test_nonzero_exit_reported():
    r = run_shell_command("false", timeout=5)
    assert r["success"] is False
    assert r["return_code"] != 0


def test_timeout_returns_quickly_and_is_actionable():
    start = time.monotonic()
    r = run_shell_command("sleep 60", timeout=1)
    elapsed = time.monotonic() - start
    # killed well before the 60s sleep would finish
    assert elapsed < 5, f"timeout took too long: {elapsed}s"
    assert r["success"] is False
    assert "timed out" in r["error"].lower()


def test_timeout_kills_whole_process_group():
    # A child `sh -c` records its own PID, then execs a long sleep. Without a
    # process-group kill the child would survive the parent shell being killed.
    # We assert the child is reaped after the timeout.
    pidfile = os.path.join(tempfile.gettempdir(), f"openpc_test_child_{os.getpid()}.pid")
    with contextlib.suppress(FileNotFoundError):
        os.unlink(pidfile)
    cmd = f"sh -c 'echo $$ > {pidfile}; exec sleep 30' & wait"
    r = run_shell_command(cmd, timeout=1)
    assert r["success"] is False
    # Give the kernel a moment to reap the killed group.
    time.sleep(0.2)
    try:
        with open(pidfile) as f:
            child_pid = int(f.read().strip())
    except FileNotFoundError:
        # The group was killed before the child could even write its pid — fine.
        return
    try:
        os.kill(child_pid, 0)
        alive = True
    except ProcessLookupError:
        alive = False
    assert not alive, f"child process {child_pid} survived the timeout (process group not killed)"
