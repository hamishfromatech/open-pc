"""Tests for shell command sanitization (detect_dangerous_chars).

These tests import the pure, dependency-free sanitization module so they can
run in CI without pyautogui/X11.
"""
import os
import sys

# Make the docker/ directory importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'docker'))

from sanitization import detect_dangerous_chars


def test_empty_command_returns_empty():
    assert detect_dangerous_chars('') == []
    assert detect_dangerous_chars(None) == []  # type: ignore[arg-type]


def test_safe_command_has_no_findings():
    assert detect_dangerous_chars('echo hello') == []
    assert detect_dangerous_chars('ls -la /tmp') == []
    assert detect_dangerous_chars('python3 script.py') == []


def test_single_dangerous_chars_detected():
    assert ';' in detect_dangerous_chars('ls; rm -rf /')
    assert '|' in detect_dangerous_chars('ls | wc -l')
    assert '&' in detect_dangerous_chars('bg &')
    assert '`' in detect_dangerous_chars('echo `id`')
    assert '>' in detect_dangerous_chars('echo hi > /tmp/x')
    assert '<' in detect_dangerous_chars('cat < /etc/passwd')


def test_compound_constructs_detected():
    found = detect_dangerous_chars('ls && echo hi')
    assert '&&' in found
    found = detect_dangerous_chars('false || echo recovered')
    assert '||' in found


def test_command_substitution_detected():
    assert '$(' in detect_dangerous_chars('echo $(id)')
    assert '${' in detect_dangerous_chars('echo ${PATH}')
    assert '$' in detect_dangerous_chars('echo $HOME')


def test_multiline_command_detected():
    found = detect_dangerous_chars('echo a\necho b')
    assert 'newline' in found


def test_safe_commands_not_flagged_as_dangerous():
    # These should NOT trigger any dangerous-char detection
    assert detect_dangerous_chars('git status') == []
    assert detect_dangerous_chars('docker ps') == []
