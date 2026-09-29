"""
Open-PC SDK Python Client Tests
"""
import pytest
from openpc_sdk import OpenPCClient
from openpc_sdk.batch import BatchExecutor


class TestOpenPCClient:
    """Test OpenPCClient initialization and basic functionality."""

    def test_init_default(self):
        """Test default host/port."""
        client = OpenPCClient()
        assert client._base_url == "http://localhost:8090"

    def test_init_custom(self):
        """Test custom host/port."""
        client = OpenPCClient(host="example.com", port=9000)
        assert client._base_url == "http://example.com:9000"

    def test_init_with_token(self):
        """Test token authentication."""
        client = OpenPCClient(token="test-token")
        assert client._token == "test-token"

    @pytest.mark.asyncio
    async def test_health_mocked(self):
        """Test health check endpoint structure (mocked)."""
        # This would require a running Open-PC server
        # For unit tests, we'd mock the _request method
        pass


class TestBatchExecutor:
    """Test BatchExecutor functionality."""

    def test_executor_init(self):
        """Test BatchExecutor initialization."""
        client = OpenPCClient()
        executor = BatchExecutor(client)
        assert executor._client == client

    @pytest.mark.asyncio
    async def test_batch_execute(self):
        """Test batch execute structure."""
        client = OpenPCClient()
        executor = BatchExecutor(client)
        # Would need mock server
        pass
