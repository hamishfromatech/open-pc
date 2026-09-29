"""
Pytest configuration for Open-PC SDK tests.
"""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.fixture
def mock_session():
    """Mock aiohttp session for testing."""
    mock = AsyncMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    return mock


@pytest.fixture
async def client(mock_session):
    """Create client with mocked session."""
    from openpc_sdk import OpenPCClient

    client = OpenPCClient()
    client._session = mock_session
    return client
