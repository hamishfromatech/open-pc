"""
Open-PC SDK - Python client for Open-PC Desktop API

A comprehensive SDK for controlling Open-PC desktop environments programmatically.
"""

__version__ = "0.1.0"
__author__ = "The A-Tech Corporation"

from .client import OpenPCClient, OpenPCError
from .batch import BatchExecutor

__all__ = ["OpenPCClient", "OpenPCError", "BatchExecutor"]
