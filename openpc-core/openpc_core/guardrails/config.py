"""Guardrails configuration models.

All settings default to the most conservative safe values.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


# ── Default command sets ─────────────────────────────────────────────

STRICT_WHITELIST = [
    # Read / inspect
    "ls", "cat", "grep", "find", "echo", "pwd", "whoami", "date",
    "uptime", "df", "free", "head", "tail", "wc", "sort", "uniq",
    "jq", "stat", "file", "tree", "less", "more", "readlink",
    # Safe tool invocations (substitute after the space)
    "python -c", "python3 -c", "node -e", "npx",
]

MODERATE_WHITELIST = [
    *STRICT_WHITELIST,
    # Write / modify files
    "mkdir", "touch", "cp", "mv", "tee", "sed", "awk",
    # Network fetch (read-only)
    "curl", "wget",
    # Package installs (user-scoped only)
    "pip install --user", "pip3 install --user",
    "npm install --no-save", "npx --yes",
]

PERMISSIVE_WHITELIST = MODERATE_WHITELIST  # everything except explicit blacklist

ALWAYS_BLOCKED = [
    # Mass deletion
    "rm -rf /", "rm -rf /*", "rm -rf ~/", "rm -rf $HOME",
    # Disk formatting
    "mkfs", "mkfs.", "dd if=",
    # Kernel modules
    "insmod ", "modprobe ", "mknod ",
    # Permission destruction
    "chmod 000", "chmod 777 /",
    # System disruption
    "swapoff -a", "shutdown", "reboot", "poweroff", "halt",
    # Root-level writes
    "> /etc/shadow", "> /etc/passwd", "/dev/sda", "/dev/sdb",
    # Shell injection via pipes
    "curl | sh", "curl | bash", "wget | sh", "wget | bash",
    # Dangerous pip upgrades
    "pip install --upgrade pip", "pip3 install --upgrade pip",
    "pip install setuptools --upgrade",
]


class GuardrailsConfig(BaseModel):
    """Runtime guardrail configuration."""

    permission: Literal["bounded", "standard", "unrestricted"] = Field(
        default="bounded",
        description="Permission mode for agent actions.",
    )
    whitelist_mode: Literal["strict", "moderate", "permissive"] = Field(
        default="strict",
        description="Command whitelist granularity.",
    )
    max_actions_per_minute: int = Field(
        default=30, ge=1, le=600,
        description="Max agent actions (clicks, types, commands) per minute.",
    )
    command_timeout: int = Field(
        default=30, ge=1, le=300,
        description="Max seconds for a shell command before timeout.",
    )
    workspace_dir: str = Field(
        default="",
        description="If set, commands are restricted to this directory.",
    )
    blocked_commands: list[str] = Field(
        default_factory=lambda: list(ALWAYS_BLOCKED),
        description="Commands blocked in all modes.",
    )

    def get_whitelist(self) -> list[str]:
        """Return the command whitelist for the current mode."""
        if self.whitelist_mode == "strict":
            return STRICT_WHITELIST
        if self.whitelist_mode == "moderate":
            return MODERATE_WHITELIST
        return PERMISSIVE_WHITELIST


# ── Config file I/O ─────────────────────────────────────────────────

_CONFIG_DIR = Path.home() / ".openpc"
_CONFIG_FILE = _CONFIG_DIR / "guardrails.json"


def load_guardrails_config() -> GuardrailsConfig:
    """Load guardrails config from disk or return defaults."""
    if _CONFIG_FILE.exists():
        try:
            data = _CONFIG_FILE.read_text()
            return GuardrailsConfig.model_validate_json(data)
        except Exception:
            pass
    return GuardrailsConfig()


def save_guardrails_config(config: GuardrailsConfig) -> None:
    """Persist guardrails config to disk."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(config.model_dump_json(indent=2))


def load_from_env() -> GuardrailsConfig:
    """Build config from environment variables (overrides file)."""
    return GuardrailsConfig(
        permission=os.environ.get("OPENPC_PERMISSION", "bounded"),
        whitelist_mode=os.environ.get("OPENPC_WHITELIST_MODE", "strict"),
        max_actions_per_minute=int(os.environ.get("OPENPC_MAX_ACTIONS_PER_MINUTE", "30")),
        command_timeout=int(os.environ.get("OPENPC_COMMAND_TIMEOUT", "30")),
        workspace_dir=os.environ.get("OPENPC_WORKSPACE_DIR", ""),
    )
