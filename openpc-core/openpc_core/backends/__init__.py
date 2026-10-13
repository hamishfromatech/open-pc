"""Desktop backend abstraction for Open-PC.

All backends implement the `DesktopBackend` Protocol defined in this package.
The Docker path uses `docker/backends.py`; bare-metal mode routes through
`openpc_core.backends.cua_driver`.
"""

from .base import DesktopBackend

__all__ = ["DesktopBackend"]
