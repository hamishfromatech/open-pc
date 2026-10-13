"""Guardrails engine: permission gates, command validation, audit logging, rate limiting.

All methods are pure (no network, no display) so they can be unit-tested in CI.
"""

from __future__ import annotations

import fnmatch
import hashlib
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone


from .config import GuardrailsConfig, load_guardrails_config, save_guardrails_config


# ── Rate limiter (simple sliding window) ─────────────────────────────

class RateLimiter:
    """Token-bucket rate limiter."""

    def __init__(self, max_per_minute: int = 30):
        self.max_per_minute = max_per_minute
        self._tokens: list[float] = []

    def allow(self) -> bool:
        now = time.monotonic()
        # Remove tokens older than 60s
        self._tokens = [t for t in self._tokens if now - t < 60.0]
        if len(self._tokens) >= self.max_per_minute:
            return False
        self._tokens.append(now)
        return True


# ── Audit entry ──────────────────────────────────────────────────────

@dataclass
class AuditEntry:
    timestamp: str
    action: str          # "click", "type", "command", "screenshot", etc.
    target: str = ""     # what was acted on (e.g. "/bin/ls -la")
    result: str = ""     # success/failure summary
    blocked: bool = False
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "action": self.action,
            "target": self.target,
            "result": self.result,
            "blocked": self.blocked,
            "reason": self.reason,
        }


# ── Guardrails Engine ────────────────────────────────────────────────

_SHARED_ENGINE: "GuardrailsEngine | None" = None


def get_shared_engine() -> "GuardrailsEngine":
    """Return the process-wide guardrails engine (created on first use).

    The agent server's HTTP middleware and the CUA backend's run_command
    both audit through this instance so every layer lands in one stream.
    """
    global _SHARED_ENGINE
    if _SHARED_ENGINE is None:
        _SHARED_ENGINE = GuardrailsEngine()
    return _SHARED_ENGINE


class GuardrailsEngine:
    """Wraps agent actions with permission gates, command validation, and audit logging."""

    def __init__(self, config: GuardrailsConfig | None = None):
        self.config = config or load_guardrails_config()
        self.rate_limiter = RateLimiter(self.config.max_actions_per_minute)
        # Ring buffer: last 1000 entries
        self._audit_log: deque[AuditEntry] = deque(maxlen=1000)

    # ── Permission gate ────────────────────────────────────────────────

    def check_permission(self, action: str) -> bool:
        """Return True if the action is allowed under current permission mode.

        Modes:
          - **bounded**: only explicitly allowed actions (see _BOUNDED_ACTIONS).
          - **standard**: all actions except those in the blocked set.
          - **unrestricted**: everything passes.
        """
        if self.config.permission == "unrestricted":
            return True

        bounded_actions = {
            "screenshot", "screen_info", "mouse_move", "mouse_click",
            "mouse_scroll", "keyboard_type", "keyboard_press",
            "list_windows", "get_active_window", "run_command",
            "ocr_screenshot", "locate_on_screen",
        }

        if self.config.permission == "bounded":
            return action in bounded_actions

        # standard mode — block only dangerous actions
        dangerous = {
            "close_window", "maximize_window", "minimize_window",
            "launch_application", "open_url", "focus_window",
        }
        return action not in dangerous

    # ── Command validation ─────────────────────────────────────────────

    def validate_command(self, command: str) -> dict:
        """Validate a shell command against whitelist + blacklist.

        Returns:
            {"allowed": True} on success, or
            {"allowed": False, "reason": "..."} on rejection.
        """
        cmd = command.strip()
        if not cmd:
            return {"allowed": False, "reason": "Empty command."}

        # Always-blocked check (substring match)
        for blocked in self.config.blocked_commands:
            if blocked.lower() in cmd.lower():
                return {
                    "allowed": False,
                    "reason": f"Command blocked: '{blocked}' is not allowed.",
                }

        # Whitelist check (permissive mode skips the whitelist entirely)
        if self.config.whitelist_mode == "permissive":
            return {"allowed": True}

        whitelist = self.config.get_whitelist()
        # Check if command starts with an allowed prefix
        cmd_prefix = cmd.split()[0] if cmd.split() else cmd
        for allowed in whitelist:
            allowed_prefix = allowed.split()[0] if allowed.split() else allowed
            if fnmatch.fnmatch(cmd_prefix, allowed_prefix) or cmd.startswith(allowed):
                return {"allowed": True}

        return {
            "allowed": False,
            "reason": f"Command not in whitelist: '{cmd_prefix}'. Use a safe command like 'ls', 'cat', 'grep', or 'python -c'.",
        }

    # ── Rate limiting ──────────────────────────────────────────────────

    def rate_limit_check(self) -> bool:
        """Return True if the next action is allowed, False if throttled."""
        return self.rate_limiter.allow()

    # ── Audit logging ──────────────────────────────────────────────────

    def audit_log_action(
        self,
        action: str,
        target: str = "",
        result: str = "",
        blocked: bool = False,
        reason: str = "",
    ) -> None:
        """Append an entry to the in-memory ring buffer and persist to disk."""
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            action=action,
            target=target,
            result=result,
            blocked=blocked,
            reason=reason,
        )
        self._audit_log.append(entry)

    def get_audit_log(self, limit: int = 50) -> list[dict]:
        """Return the last N audit entries as dicts."""
        return [e.to_dict() for e in list(self._audit_log)[-limit:]]

    def clear_audit_log(self) -> None:
        """Clear the in-memory ring buffer."""
        self._audit_log.clear()

    def save_audit_log(self, path: str | None = None) -> str:
        """Persist audit log to a JSON file. Returns the file path written."""
        import json
        target = path or str(__import__("pathlib").Path.home() / ".openpc" / "audit.json")
        __import__("pathlib").Path(target).parent.mkdir(parents=True, exist_ok=True)
        __import__("pathlib").Path(target).write_text(
            json.dumps(self.get_audit_log(limit=1000), indent=2)
        )
        return target

    # ── Config management ──────────────────────────────────────────────

    def reload_from_env(self) -> None:
        """Reload config from environment variables."""
        import os
        self.config = GuardrailsConfig(
            permission=os.environ.get("OPENPC_PERMISSION", self.config.permission),
            whitelist_mode=os.environ.get("OPENPC_WHITELIST_MODE", self.config.whitelist_mode),
            max_actions_per_minute=int(
                os.environ.get("OPENPC_MAX_ACTIONS_PER_MINUTE", str(self.config.max_actions_per_minute))
            ),
            command_timeout=int(
                os.environ.get("OPENPC_COMMAND_TIMEOUT", str(self.config.command_timeout))
            ),
            workspace_dir=os.environ.get("OPENPC_WORKSPACE_DIR", self.config.workspace_dir),
        )
        self.rate_limiter = RateLimiter(self.config.max_actions_per_minute)

    def save_config(self) -> None:
        """Persist current config to disk."""
        save_guardrails_config(self.config)

    @classmethod
    def configure(
        cls,
        permission: str | None = None,
        whitelist_mode: str | None = None,
        max_actions_per_minute: int | None = None,
        command_timeout: int | None = None,
        workspace_dir: str | None = None,
    ) -> GuardrailsConfig:
        """Update config and save to disk. Returns the updated config."""
        import os
        config = load_guardrails_config()
        if permission is not None:
            config.permission = permission
        if whitelist_mode is not None:
            config.whitelist_mode = whitelist_mode
        if max_actions_per_minute is not None:
            config.max_actions_per_minute = max_actions_per_minute
        if command_timeout is not None:
            config.command_timeout = command_timeout
        if workspace_dir is not None:
            config.workspace_dir = workspace_dir
        save_guardrails_config(config)
        return config

    @classmethod
    def load_status(cls) -> dict:
        """Return current guardrails status as a dict (for /guard/status endpoint)."""
        config = load_guardrails_config()
        engine = cls(config)
        return {
            "config": config.model_dump(),
            "log_entries": len(engine._audit_log),
            "rate_limit_per_minute": engine.rate_limiter.max_per_minute,
        }
