#!/usr/bin/env python3
"""
openpc — a noun-verb CLI for Open-PC.

Wraps `docker compose` and the REST API so operators don't have to remember
service names, ports, and curl incantations. Mirrors SmolVM's `smolvm` CLI
discipline: noun-verb commands, one short help line each, exact recovery in
error messages.

Usage:
    python3 openpc.py <command> [args]
    ./openpc.py <command>            # after: chmod +x openpc.py

Commands:
    Docker mode (default):
        start [--build]    Start all Open-PC containers
        stop               Stop and remove containers
        restart            Restart containers
        status             Show running containers (alias: ps, list)
        logs [service]     Tail logs (service: desktop|dashboard|mcp; add -f to follow)
        shell              Open a shell in the desktop container
        exec -- <cmd...>   Run a command in the desktop container
        screenshot [path]  Save a desktop screenshot (default: screen.png)
        open-url <url>     Open a URL in the sandbox browser
        run -- <cmd...>    Run a shell command in the sandbox (via REST /apps/run)
        desktop            Print the noVNC web URL
        doctor             Diagnose docker, compose, and the REST API

    Bare-metal mode:
        start --mode bare-metal [--backend cua-driver|native]
                           Start Open-PC on the host OS (no Docker)
        stop               Stop bare-metal server too
        status             Shows whichever is running

    Guardrails:
        configure --permission bounded|standard|unrestricted
        configure --whitelist strict|moderate|permissive
        guard status       Show active guardrails config
        guard audit [-n N] Print last N actions from log
        guard reset        Clear audit log

    version            Print the CLI version
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Sequence

APP_VERSION = "0.1.0"
COMPOSE_FILE = "docker-compose.yml"

DEFAULT_REST_PORT = 8090
DESKTOP_SERVICE = "open-pc-desktop"
DASHBOARD_SERVICE = "open-pc-dashboard"
MCP_SERVICE = "open-pc-mcp"
NOVNC_PORT = 6080
BARE_METAL_PORT = 8093

ALL_SERVICES = (DESKTOP_SERVICE, DASHBOARD_SERVICE, MCP_SERVICE)
SERVICE_ALIASES = {
    "desktop": DESKTOP_SERVICE,
    "dashboard": DASHBOARD_SERVICE,
    "mcp": MCP_SERVICE,
}


# --------------------------------------------------------------------------- #
# Pure helpers (no subprocess / no network) — unit-testable in CI.
# --------------------------------------------------------------------------- #

def rest_url(port: int, path: str) -> str:
    """Build a REST URL against the host-mapped agent port."""
    if not path.startswith("/"):
        path = "/" + path
    return f"http://localhost:{port}{path}"


def build_compose_args(compose_bin: str, *args: str) -> list[str]:
    """Build the argv for a `docker compose` invocation (pure)."""
    return [compose_bin, "-f", COMPOSE_FILE, *args]


def build_arg_parser() -> argparse.ArgumentParser:
    """Construct the CLI parser (pure; no I/O)."""
    parser = argparse.ArgumentParser(
        prog="openpc",
        description="Open-PC: give AI its own computer.",
    )
    parser.add_argument(
        "--version", action="version", version=f"openpc {APP_VERSION}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("start", help="Start all Open-PC containers")
    p.add_argument("--build", action="store_true", help="Rebuild images before starting")
    p.add_argument("--mode", choices=["docker", "bare-metal"], default="docker",
                   help="Run mode: docker (default) or bare-metal on host OS")
    p.add_argument("--backend", choices=["cua-driver", "native"], default="cua-driver",
                   help="Backend for bare-metal mode (requires cua-driver installed)")

    sub.add_parser("stop", help="Stop and remove containers")
    sub.add_parser("restart", help="Restart containers")

    p = sub.add_parser("status", help="Show running containers")
    sub.add_parser("ps", help="Alias of status")
    sub.add_parser("list", help="Alias of status")

    p = sub.add_parser("logs", help="Tail logs")
    p.add_argument("service", nargs="?", default=DESKTOP_SERVICE, help="desktop|dashboard|mcp")
    p.add_argument("-f", "--follow", action="store_true", help="Follow log output")

    sub.add_parser("shell", help="Open a shell in the desktop container")

    p = sub.add_parser("exec", help="Run a command in the desktop container")
    p.add_argument("cmd", nargs=argparse.REMAINDER, help="Command (after --) to run")

    p = sub.add_parser("screenshot", help="Save a desktop screenshot")
    p.add_argument("path", nargs="?", default="screen.png", help="Output file path")
    p.add_argument("--port", type=int, default=None, help="Host REST port (default: auto-detect 8093 then 8090)")

    p = sub.add_parser("open-url", help="Open a URL in the sandbox browser")
    p.add_argument("url", help="URL to open")
    p.add_argument("--port", type=int, default=None, help="Host REST port (default: auto-detect 8093 then 8090)")

    p = sub.add_parser("run", help="Run a shell command in the sandbox via REST")
    p.add_argument("cmd", nargs=argparse.REMAINDER, help="Command (after --) to run")
    p.add_argument("--port", type=int, default=None, help="Host REST port (default: auto-detect 8093 then 8090)")
    p.add_argument("--timeout", type=int, default=30, help="Command timeout (seconds)")

    sub.add_parser("desktop", help="Print the noVNC web URL")
    sub.add_parser("doctor", help="Diagnose docker, compose, and the REST API")

    # ── Configure (guardrails settings) ──────────────────────────────
    p = sub.add_parser("configure", help="Configure guardrails settings")
    p.add_argument("--permission", choices=["bounded", "standard", "unrestricted"],
                   help="Permission mode for agent actions")
    p.add_argument("--whitelist", choices=["strict", "moderate", "permissive"],
                   help="Command whitelist granularity")
    p.add_argument("--max-actions", type=int, help="Max actions per minute")
    p.add_argument("--timeout", type=int, help="Command timeout in seconds")
    p.add_argument("--workspace", help="Restrict commands to this directory")

    # ── Guard (guardrails status/audit) ──────────────────────────────
    p = sub.add_parser("guard", help="Manage guardrails")
    p.add_argument("action", choices=["status", "audit", "reset"], nargs="?",
                   default="status", help="Action to perform")
    p.add_argument("-n", type=int, default=50, help="Number of audit entries to show")
    return parser


def _ensure_openpc_core_importable() -> None:
    """Make `import openpc_core` work without a pip install (adds openpc-core/ to path)."""
    import sys
    core_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "openpc-core")
    if core_src not in sys.path:
        sys.path.insert(0, core_src)


# --------------------------------------------------------------------------- #
# Runtime helpers (subprocess / network).
# --------------------------------------------------------------------------- #

def _detect_compose_bin() -> str:
    """Return a working compose invocation (prefers `docker compose` v2)."""
    for candidate in (("docker", "compose"), ("docker-compose",)):
        try:
            subprocess.run(
                [*candidate, "version"], capture_output=True, timeout=10,
            )
            return " ".join(candidate)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    raise SystemExit(
        "docker compose not found. Install Docker (with Compose v2) and retry."
    )


def run_compose(*args: str, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a `docker compose` subcommand, streaming output to the terminal."""
    compose_bin = _detect_compose_bin()
    argv = build_compose_args(compose_bin, *args)
    return subprocess.run(argv, check=False, capture_output=capture, text=not capture)


def _rest_token() -> str:
    return os.environ.get("OPENPC_TOKEN", os.environ.get("REST_AUTH_TOKEN", ""))


def _rest_headers() -> dict[str, str]:
    token = _rest_token()
    return {"X-OpenPC-Token": token} if token else {}


def rest_get(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(url, headers=_rest_headers(), method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _resolve_rest_port(explicit: int | None) -> int:
    """Return the port of a healthy agent server.

    Explicit ``--port`` wins; otherwise probe bare-metal (8093) first, then
    the Docker-mapped REST port (8090).
    """
    if explicit:
        return explicit
    for port in (BARE_METAL_PORT, DEFAULT_REST_PORT):
        try:
            body = rest_get(rest_url(port, "/health"), timeout=3)
            if json.loads(body).get("status") == "healthy":
                return port
        except Exception:  # noqa: BLE001
            continue
    raise SystemExit(
        f"No Open-PC agent responding on port {BARE_METAL_PORT} or {DEFAULT_REST_PORT}. "
        "Start one first (openpc.py start)."
    )


def rest_post_json(url: str, body: dict, timeout: int = 15) -> dict:
    data = json.dumps(body).encode()
    headers = {**_rest_headers(), "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise SystemExit(f"REST request failed ({e.code}): {detail}") from e


def _resolve_service(name: str) -> str:
    if name in SERVICE_ALIASES:
        return SERVICE_ALIASES[name]
    if name in ALL_SERVICES:
        return name
    raise SystemExit(f"Unknown service '{name}'. Choose from: desktop, dashboard, mcp.")


# --------------------------------------------------------------------------- #
# Commands.
# --------------------------------------------------------------------------- #

def cmd_start(args) -> int:
    extra = ["--build"] if args.build else []
    run_compose("up", "-d", *extra)
    print("Open-PC starting. Dashboard: http://localhost:8092  noVNC: http://localhost:6080")
    return 0


def cmd_stop(args) -> int:
    run_compose("down")
    return 0


def cmd_restart(args) -> int:
    run_compose("restart")
    return 0


def cmd_status(args) -> int:
    run_compose("ps")
    return 0


def cmd_logs(args) -> int:
    svc = _resolve_service(args.service)
    extra = ["--follow"] if args.follow else []
    run_compose("logs", svc, *extra)
    return 0


def cmd_shell(args) -> int:
    # Interactive: inherit the TTY.
    compose_bin = _detect_compose_bin()
    argv = build_compose_args(compose_bin, "exec", DESKTOP_SERVICE, "bash")
    return subprocess.run(argv).returncode


def cmd_exec(args) -> int:
    cmd = [c for c in args.cmd if c != "--"]
    if not cmd:
        raise SystemExit("No command given. Usage: openpc exec -- <command...>")
    compose_bin = _detect_compose_bin()
    argv = build_compose_args(compose_bin, "exec", DESKTOP_SERVICE, *cmd)
    return subprocess.run(argv).returncode


def cmd_screenshot(args) -> int:
    port = _resolve_rest_port(args.port)
    url = rest_url(port, "/screenshot")
    png = rest_get(url, timeout=30)
    with open(args.path, "wb") as f:
        f.write(png)
    print(f"Saved screenshot to {args.path} ({len(png)} bytes)")
    return 0


def cmd_open_url(args) -> int:
    port = _resolve_rest_port(args.port)
    url = rest_url(port, "/apps/open-url")
    result = rest_post_json(url, {"url": args.url}, timeout=15)
    if not result.get("success"):
        raise SystemExit(f"Failed to open URL: {result.get('error', 'unknown error')}")
    print(f"Opened {args.url}")
    return 0


def cmd_run(args) -> int:
    cmd = [c for c in args.cmd if c != "--"]
    if not cmd:
        raise SystemExit("No command given. Usage: openpc run -- <command...>")
    port = _resolve_rest_port(args.port)
    url = rest_url(port, "/apps/run")
    result = rest_post_json(url, {"command": " ".join(cmd), "timeout": args.timeout}, timeout=args.timeout + 10)
    if result.get("stdout"):
        sys.stdout.write(result["stdout"])
    if result.get("stderr"):
        sys.stderr.write(result["stderr"])
    return int(result.get("return_code", 1)) if result.get("success") is False else 0


def cmd_desktop(args) -> int:
    print(f"noVNC web URL: http://localhost:{NOVNC_PORT}")
    print("Dashboard:     http://localhost:8092")
    return 0


# ── Bare-metal commands ─────────────────────────────────────────────

def cmd_start_baremetal(args) -> int:
    """Start Open-PC in bare-metal mode on the host OS."""
    if sys.version_info < (3, 10):
        raise SystemExit(
            f"Bare-metal mode needs Python 3.10+ (this interpreter is {sys.version_info[0]}.{sys.version_info[1]}). "
            "Use a newer python3 to run openpc.py (e.g. Homebrew's python3.11)."
        )
    print("Starting Open-PC in bare-metal mode...")
    print(f"  Backend: {args.backend}")
    print(f"  Port:    {BARE_METAL_PORT}")
    print()

    # Build environment for the subprocess
    env = os.environ.copy()
    env["OPENPC_MODE"] = "bare-metal"
    env["AGENT_HOST"] = "0.0.0.0"
    env["AGENT_PORT"] = str(BARE_METAL_PORT)
    env["VNC_PASSWORD"] = os.environ.get("VNC_PASSWORD", "openpc")
    env["OPENPC_BACKEND"] = args.backend

    # Make openpc_core importable without a pip install
    script_dir = os.path.dirname(os.path.abspath(__file__))
    core_src = os.path.join(script_dir, "openpc-core")
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = ":".join(p for p in (core_src, script_dir, existing_pp) if p)

    agent_script = os.path.join(script_dir, "docker", "agent_server.py")

    try:
        proc = subprocess.Popen(
            [sys.executable, agent_script],
            env=env,
            cwd=os.path.join(script_dir, "docker"),
        )
        print(f"Agent server started (PID {proc.pid}) on port {BARE_METAL_PORT}")
        print(f"REST API:      http://localhost:{BARE_METAL_PORT}")
        print()
        print("Press Ctrl+C to stop.")

        # Keep running until interrupted
        proc.wait()
        return 0
    except FileNotFoundError:
        raise SystemExit(f"Agent server not found at {agent_script}")
    except KeyboardInterrupt:
        print("\nStopping...")
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            pass
        return 0


def cmd_start(args) -> int:
    """Start Open-PC — Docker or bare-metal."""
    if args.mode == "bare-metal":
        return cmd_start_baremetal(args)

    # Docker mode (existing behavior)
    extra = ["--build"] if args.build else []
    run_compose("up", "-d", *extra)
    print("Open-PC starting. Dashboard: http://localhost:8092  noVNC: http://localhost:6080")
    return 0


def cmd_stop(args) -> int:
    """Stop Open-PC — Docker or bare-metal."""
    # Stop Docker containers
    run_compose("down")
    print("Docker containers stopped.")

    # Check whether a bare-metal server is still running
    try:
        rest_get(rest_url(BARE_METAL_PORT, "/health"), timeout=3)
        print(f"Bare-metal agent still running on port {BARE_METAL_PORT} — stop it with Ctrl+C in its terminal.")
    except Exception:
        pass  # nothing on the bare-metal port

    return 0


def cmd_doctor(args) -> int:
    failures = 0

    def check(name, ok, detail=""):
        nonlocal failures
        status = "OK" if ok else "FAIL"
        print(f"  {name}: {status}{(' — ' + detail) if detail else ''}")
        if not ok:
            failures += 1

    print("Open-PC doctor")
    docker = shutil.which("docker")
    check("docker", bool(docker), docker or "not on PATH")
    compose_bin = _detect_compose_bin() if docker else ""
    check("docker compose", bool(compose_bin), compose_bin or "compose unavailable")
    # REST health
    try:
        body = rest_get(rest_url(DEFAULT_REST_PORT, "/health"), timeout=5)
        health = json.loads(body)
        check("agent REST /health", health.get("status") == "healthy", str(health))
    except Exception as e:  # noqa: BLE001
        check("agent REST /health", False, str(e))
    print("Done." if not failures else f"{failures} check(s) failed.")
    return 1 if failures else 0


# ── Guardrails commands ─────────────────────────────────────────────

def cmd_configure(args) -> int:
    """Configure guardrails settings."""
    try:
        _ensure_openpc_core_importable()
        from openpc_core.guardrails.engine import GuardrailsEngine
    except ImportError:
        raise SystemExit(
            "Guardrails not available. Install openpc-core: "
            "cd openpc-core && pip install -e ."
        )

    config = GuardrailsEngine.configure(
        permission=args.permission,
        whitelist_mode=args.whitelist,
        max_actions_per_minute=args.max_actions,
        command_timeout=args.timeout,
        workspace_dir=args.workspace,
    )
    print("Guardrails configured:")
    for key, value in config.model_dump().items():
        print(f"  {key}: {value}")
    return 0


def _guard_port() -> int:
    """Find which port serves /guard/status (bare-metal 8093 first, then docker).

    Returns the port and whether guard endpoints exist. Raises SystemExit
    with a clear message when no agent is reachable at all.
    """
    for port in (BARE_METAL_PORT, DEFAULT_REST_PORT):
        try:
            body = rest_get(rest_url(port, "/health"), timeout=3)
            if not json.loads(body).get("status") == "healthy":
                continue
        except Exception:  # noqa: BLE001
            continue
        # Agent is up on this port — does it expose guard endpoints?
        try:
            body = rest_get(rest_url(port, "/guard/status"), timeout=3)
            return port
        except Exception:  # noqa: BLE001
            raise SystemExit(
                f"Agent is running on port {port} but has no guardrails endpoints. "
                "Guardrails only run in bare-metal mode with openpc-core installed."
            )
    raise SystemExit(
        f"No Open-PC agent responding on port {BARE_METAL_PORT} or {DEFAULT_REST_PORT}. "
        "Start one first (openpc.py start)."
    )


def cmd_guard(args) -> int:
    """Manage guardrails: status, audit log, reset."""
    action = args.action or "status"
    port = _guard_port()

    if action == "status":
        data = json.loads(rest_get(rest_url(port, "/guard/status"), timeout=5))
        if not data.get("enabled"):
            print("Guardrails: not enabled (Docker mode or openpc-core not installed)")
            return 0
        print("Guardrails status:")
        print(f"  Mode:          {data['mode']}")
        for key, value in data["config"].items():
            print(f"  {key}: {value}")
        print(f"  Log entries:   {data['log_entries']}")
        print(f"  Rate limit:    {data['rate_limit_per_minute']} actions/min")

    elif action == "audit":
        entries = json.loads(rest_get(rest_url(port, f"/guard/audit?limit={args.n}"), timeout=5))
        if isinstance(entries, dict) or not entries:
            print("No audit entries.")
            return 0
        print(f"Last {min(args.n, len(entries))} audit entries:")
        for entry in entries:
            status = "BLOCKED" if entry.get("blocked") else "OK"
            print(f"  [{entry['timestamp']}] {status}: {entry['action']} ({entry.get('target', '')})")
            if entry.get("reason"):
                print(f"           Reason: {entry['reason']}")

    elif action == "reset":
        rest_post_json(rest_url(port, "/guard/reset"), {}, timeout=5)
        print("Audit log cleared.")

    return 0


COMMANDS = {
    # Docker commands
    "start": cmd_start,
    "stop": cmd_stop,
    "restart": cmd_restart,
    "status": cmd_status,
    "ps": cmd_status,
    "list": cmd_status,
    "logs": cmd_logs,
    "shell": cmd_shell,
    "exec": cmd_exec,
    "screenshot": cmd_screenshot,
    "open-url": cmd_open_url,
    "run": cmd_run,
    "desktop": cmd_desktop,
    "doctor": cmd_doctor,
    # Guardrails commands
    "configure": cmd_configure,
    "guard": cmd_guard,
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    handler = COMMANDS.get(args.command)
    if handler is None:  # pragma: no cover - argparse enforces required subcommand
        parser.print_help()
        return 2
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
