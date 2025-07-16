# gRPC MCP SDK - Quick Start Guide

## Installation

```bash
pip install grpc-mcp-sdk
```

## Basic Usage

### 1. Create Your First Tool

```python
from grpc_mcp_sdk import mcp_tool, MCPToolResult, run_server
import asyncio

@mcp_tool(description="Calculate the square of a number")
def square_number(x: float) -> MCPToolResult:
    result = x * x
    return MCPToolResult().add_text(f"{x}² = {result}")

if __name__ == "__main__":
    asyncio.run(run_server(port=50051))
```

### 2. Run the Server

```bash
python my_tools.py
```

### 3. Use the Client

```python
from grpc_mcp_sdk import create_client
import asyncio

async def main():
    client = create_client('localhost:50051')
    await client.connect()
    
    result = await client.execute_tool('square_number', {'x': 5})
    print(result)  # 5² = 25
    
    await client.close()

asyncio.run(main())
```

## Advanced Features

### Streaming Tools

```python
from grpc_mcp_sdk import streaming_tool

@streaming_tool(description="Count with progress")
async def count_to_n(n: int = 10):
    for i in range(1, n + 1):
        yield f"Count: {i}"
        await asyncio.sleep(0.1)
```

### Authentication

```python
from grpc_mcp_sdk import create_token_auth, requires_auth

# Create auth handler
auth_handler = create_token_auth(['secret-token'])

# Secure tool
@mcp_tool(description="Secure tool")
@requires_auth()
def secure_tool():
    return MCPToolResult().add_text("Authenticated access!")

# Run with authentication
await run_server(port=50051, auth_handler=auth_handler)
```

### Rate Limiting & Security

```python
from grpc_mcp_sdk.security import create_rate_limiter
from grpc_mcp_sdk import requires_permission

# Rate limiting
rate_limiter = create_rate_limiter(requests_per_minute=60)

@mcp_tool(description="Rate limited tool")
@requires_permission("read")
def protected_tool():
    return MCPToolResult().add_text("Protected data")
```

## Examples

Check the `examples/` directory for complete examples:

- `basic_server.py` - Basic server with multiple tools
- `authenticated_server.py` - Server with authentication
- `secure_server.py` - Production-ready secure server
- `client_example.py` - Client usage examples

## Development

### Install Development Dependencies

```bash
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest
```

### Format Code

```bash
black grpc_mcp_sdk/
isort grpc_mcp_sdk/
```

## Performance Benefits

- **5-10x faster** than JSON-RPC over HTTP
- **Binary serialization** with Protocol Buffers
- **HTTP/2 multiplexing** for efficient connection usage
- **Streaming support** for real-time applications
- **Built-in security** with authentication and rate limiting

## Documentation

For complete documentation, visit: https://grpc-mcp-sdk.readthedocs.io/