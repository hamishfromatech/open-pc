#!/usr/bin/env python3
"""
Open-PC Health Check Script
Used by Docker HEALTHCHECK
"""

import sys
import os

# Add to path
sys.path.insert(0, '/opt/openpc')

def check_display():
    """Check if X11 display is available"""
    try:
        import subprocess
        result = subprocess.run(
            ['xset', 'q'],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False

def check_agent():
    """Check if agent server is responding"""
    try:
        import urllib.request
        import urllib.error

        host = os.environ.get('AGENT_HOST', 'localhost')
        port = os.environ.get('AGENT_PORT', '8080')

        url = f"http://{host}:{port}/health"
        req = urllib.request.Request(url, method='GET')

        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                return True
    except Exception:
        pass
    return False

def main():
    """Run health checks"""
    checks = []

    # Check display
    display_ok = check_display()
    checks.append(('display', display_ok))

    # Check agent
    agent_ok = check_agent()
    checks.append(('agent', agent_ok))

    # All checks must pass
    all_ok = all(ok for _, ok in checks)

    if all_ok:
        print("Health check passed")
        return 0
    else:
        print("Health check failed:")
        for name, ok in checks:
            status = "OK" if ok else "FAILED"
            print(f"  {name}: {status}")
        return 1

if __name__ == '__main__':
    sys.exit(main())