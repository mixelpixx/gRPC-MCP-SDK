"""Test configuration for gRPC MCP SDK."""

import pytest
import asyncio
from grpc_mcp_sdk import create_server, create_client


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_server():
    """Create a test server."""
    server, servicer = await create_server(host="localhost", port=50052)
    await server.start()
    
    yield server, servicer
    
    await server.stop(grace_period=1)


@pytest.fixture
async def test_client():
    """Create a test client."""
    client = create_client("localhost:50052")
    await client.connect()
    
    yield client
    
    await client.close()