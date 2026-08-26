"""
Open-PC Shell Command Runner

Executes a shell command safely: sanitizes first, then runs it in its own
process group so a timeout kills the whole tree (shell + children) instead of
orphaning child processes.

Pure of pyautogui/X11 (only stdlib imports) so it can be unit-tested in CI
without a display.

Inspired by SmolVM's guest-agent ``exec.rs``, which calls ``setsid()`` in
``pre_exec`` and ``kill(-pid, SIGKILL)`` on timeout to guarantee no orphaned
children are left running in the guest.
"""
from __future__ import annotations

import contextlib
import os
import signal
import subprocess
from typing import Any

from sanitization import detect_dangerous_chars


def run_shell_command(command: str, timeout: int = 30) -> dict[str, Any]:
    """Sanitize and run a shell command, killing the whole process group on timeout.

    Returns a dict with: ``success`` (bool), ``stdout``, ``stderr``, and on success
    ``return_code``. On timeout or a blocked command, returns ``success=False`` with
    an actionable one-sentence ``error`` message (SmolVM-style: name the problem and
    the recovery).
    """
    if not command or not command.strip():
        return {
            "success": False,
            "error": "Empty command. Pass a non-empty shell command.",
        }

    found = detect_dangerous_chars(command)
    if found:
        blocked = ", ".join(found)
        return {
            "success": False,
            "error": (
                f"Command blocked: it contains dangerous shell constructs ({blocked}). "
                f"Run the sub-commands separately instead of chaining them."
            ),
        }

    # Run the shell in its own session/process group (setsid) so that on timeout
    # we can kill the entire group, including any child processes the command
    # spawned. `subprocess.run(timeout=...)` alone only kills the immediate shell
    # and can orphan its children.
    proc = subprocess.Popen(
        command,
        shell=True,
        start_new_session=True,  # calls setsid() -> child leads a new process group
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return {
            "success": proc.returncode == 0,
            "stdout": stdout,
            "stderr": stderr,
            "return_code": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        _kill_process_group(proc.pid)
        # Drain any output the process produced before we killed it.
        try:
            stdout, stderr = proc.communicate(timeout=2)
        except Exception:
            stdout, stderr = "", ""
        return {
            "success": False,
            "stdout": stdout or "",
            "stderr": stderr or "",
            "error": (
                f"Command timed out after {timeout}s and was killed. "
                f"Increase the timeout or make the command terminate on its own."
            ),
        }


def _kill_process_group(pid: int) -> None:
    """SIGKILL the entire process group led by ``pid``, ignoring already-gone processes."""
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        os.killpg(os.getpgid(pid), signal.SIGKILL)
