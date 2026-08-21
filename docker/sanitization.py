"""
Open-PC Shell Command Sanitization Helpers

Pure functions with no heavy dependencies (no pyautogui/X11) so they can be
unit-tested in CI without a display. Imported by desktop_manager.py.
"""

from typing import List

# Shell metacharacters/constructs that enable command chaining or injection.
_DANGEROUS_CHARS: List[str] = [';', '|', '&', '`', '$(', '${', '>', '<', '||', '&&', '$']


def detect_dangerous_chars(command: str) -> List[str]:
    """Return the list of dangerous shell constructs found in command.

    Returns an empty list if the command is considered safe.

    Args:
        command: The raw shell command string to inspect.

    Returns:
        List of offending constructs (e.g. [';', '&&', 'newline']).
    """
    if not command:
        return []
    found = [c for c in _DANGEROUS_CHARS if c in command]
    if '\n' in command:
        found.append('newline')
    return found