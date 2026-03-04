# gRPC MCP SDK

A Python framework for building Model Context Protocol (MCP) servers with gRPC transport.

## Overview

The gRPC MCP SDK implements the full MCP specification using gRPC for transport instead of JSON-RPC over HTTP. This provides performance improvements through Protocol Buffers serialization and HTTP/2 multiplexing, while maintaining compatibility with standard MCP clients through a bridge layer and stdio transport.

### Transport Options

| Transport | Use Case | Client Compatibility |
|-----------|----------|---------------------|
| gRPC | High-performance server deployments | gRPC clients, bridge |
| Stdio | Local clients like Claude Desktop | All MCP clients |
| HTTP Bridge | Backward compatibility | JSON-RPC clients |

## Installation

```bash
pip install grpc-mcp-sdk
```

## Core Concepts

The MCP specification defines three primitives that servers can expose:

- **Tools** - Functions that can be called by the client
- **Resources** - Data that can be read by the client
- **Prompts** - Reusable prompt templates

This SDK provides decorators and registries for each primitive, plus a notification system for server-initiated messages.

## Tools

Tools are functions that clients can discover and execute.

### Basic Tool

```python
from grpc_mcp_sdk import mcp_tool, MCPToolResult, run_server
import asyncio

@mcp_tool(description="Calculate the square of a number")
def square(x: float) -> MCPToolResult:
    result = x * x
    return MCPToolResult().add_text(f"{x} squared is {result}")

@mcp_tool(description="Fetch weather data for a location")
async def get_weather(location: str, units: str = "celsius") -> MCPToolResult:
    # Your weather API logic here
    return MCPToolResult().add_json({
        "location": location,
        "temperature": 22,
        "units": units
    })

if __name__ == "__main__":
    asyncio.run(run_server(port=50051))
```

### Tool Results

`MCPToolResult` supports multiple content types:

```python
@mcp_tool(description="Demonstrate result types")
def demo_results() -> MCPToolResult:
    result = MCPToolResult()

    # Text content
    result.add_text("Plain text message")

    # JSON content
    result.add_json({"key": "value", "numbers": [1, 2, 3]})

    # Binary content
    result.add_binary(b"\x89PNG...", "image/png")

    # Base64-encoded image
    result.add_image(image_bytes, mime_type="image/jpeg")

    # Error (sets is_error flag automatically)
    result.add_error("ERROR_CODE", "Description of what went wrong")

    return result
```

### Streaming Tools

For long-running operations that need to report progress:

```python
from grpc_mcp_sdk import streaming_tool

@streaming_tool(description="Process items with progress updates")
async def process_items(count: int = 100):
    for i in range(count):
        # Yield progress messages
        yield f"Processing item {i + 1} of {count}"
        await asyncio.sleep(0.1)

        # Yield intermediate results
        if (i + 1) % 10 == 0:
            yield MCPToolResult().add_json({
                "completed": i + 1,
                "remaining": count - i - 1
            })

    # Final result
    yield MCPToolResult().add_text(f"Processed {count} items")
```

### Rate-Limited Tools

```python
@mcp_tool(description="API call with rate limiting", rate_limit=10)
async def rate_limited_api_call(query: str) -> MCPToolResult:
    # Limited to 10 calls per minute
    response = await external_api.search(query)
    return MCPToolResult().add_json(response)
```

## Resources

Resources expose data that clients can read. They have URIs and can be static or dynamic.

### Static Resources

```python
from grpc_mcp_sdk.core import mcp_resource

@mcp_resource(
    uri="config://app/settings",
    name="Application Settings",
    description="Current application configuration",
    mime_type="application/json"
)
def get_settings():
    return {
        "theme": "dark",
        "language": "en",
        "debug": False
    }

@mcp_resource(
    uri="file:///var/log/app.log",
    name="Application Log",
    mime_type="text/plain"
)
async def get_log():
    with open("/var/log/app.log") as f:
        return f.read()
```

### Resource Templates

For dynamic resources with parameters in the URI:

```python
from grpc_mcp_sdk.core import mcp_resource_template

@mcp_resource_template(
    uri_template="db://users/{user_id}",
    name="User Record",
    description="Fetch user by ID",
    mime_type="application/json"
)
async def get_user(user_id: str):
    user = await database.get_user(user_id)
    return {
        "id": user_id,
        "name": user.name,
        "email": user.email
    }

@mcp_resource_template(
    uri_template="file:///{path}",
    name="File Reader",
    description="Read file contents by path"
)
def read_file(path: str):
    with open(path) as f:
        return f.read()
```

### Resource Subscriptions

Clients can subscribe to resource updates. When data changes, notify subscribers:

```python
from grpc_mcp_sdk.core import ResourceRegistry

registry = ResourceRegistry.global_registry()

# When data changes, notify subscribers
async def on_config_change():
    registry.notify_resource_updated("config://app/settings")
```

## Prompts

Prompts are reusable templates for LLM interactions.

### Basic Prompts

```python
from grpc_mcp_sdk.core import mcp_prompt

@mcp_prompt(
    description="Generate a code review prompt",
    arguments=[
        {"name": "code", "description": "Code to review", "required": True},
        {"name": "language", "description": "Programming language", "required": False}
    ]
)
def code_review(code: str, language: str = "python"):
    return [
        {
            "role": "user",
            "content": {"type": "text", "text": f"Review this {language} code:\n\n{code}"}
        }
    ]

@mcp_prompt(description="Summarize a document")
def summarize(document: str, max_length: int = 500):
    return f"Summarize the following document in {max_length} words or less:\n\n{document}"
```

### Prompt Return Types

Prompts can return:
- A string (converted to a single user message)
- A list of message dictionaries
- A `GetPromptResult` object for full control

```python
from grpc_mcp_sdk.core import GetPromptResult, PromptMessage

@mcp_prompt(description="Multi-turn conversation starter")
def conversation_starter(topic: str):
    return GetPromptResult(
        description=f"Conversation about {topic}",
        messages=[
            PromptMessage(
                role="user",
                content={"type": "text", "text": f"Let's discuss {topic}"}
            ),
            PromptMessage(
                role="assistant",
                content={"type": "text", "text": f"I'd be happy to discuss {topic}. What aspect interests you most?"}
            )
        ]
    )
```

## Running Servers

### gRPC Server

For high-performance deployments:

```bash
# Using the CLI
grpc-mcp serve --module my_tools --host 0.0.0.0 --port 50051

# Or programmatically
python -c "
import asyncio
from grpc_mcp_sdk import run_server
import my_tools  # Import to register tools
asyncio.run(run_server(port=50051))
"
```

### Stdio Server (Claude Desktop)

For local clients like Claude Desktop:

```bash
# Using the CLI
grpc-mcp stdio --module my_tools

# Or programmatically
python -c "
import asyncio
from grpc_mcp_sdk import run_stdio_server
import my_tools
asyncio.run(run_stdio_server())
"
```

Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "my-server": {
      "command": "grpc-mcp",
      "args": ["stdio", "--module", "my_tools"]
    }
  }
}
```

### HTTP Bridge

For JSON-RPC clients that need HTTP transport:

```python
from grpc_mcp_sdk.bridge import MCPBridge
import asyncio

async def main():
    bridge = MCPBridge(
        grpc_server_addr="localhost:50051",
        http_port=8080
    )
    await bridge.start()

asyncio.run(main())
```

Endpoints:
- `POST /mcp` - JSON-RPC requests
- `GET /mcp/notifications` - SSE notification stream
- `GET /health` - Health check
- `GET /tools` - List available tools

## Notifications

The SDK implements MCP notifications for server-initiated messages.

### Automatic Notifications

The SDK automatically sends notifications when:
- Tools are added or removed (`notifications/tools/list_changed`)
- Resources are added or removed (`notifications/resources/list_changed`)
- Prompts are added or removed (`notifications/prompts/list_changed`)

### Manual Notifications

```python
from grpc_mcp_sdk.core import NotificationManager

manager = NotificationManager.global_manager()

# Notify that a resource was updated
await manager.notify_resource_updated("config://app/settings")

# Send progress updates
token = manager.create_progress_token()
await manager.report_progress(token, progress=0.5, message="Halfway done")
await manager.report_progress(token, progress=1.0, message="Complete")
manager.complete_progress(token)

# Send log messages
await manager.log_info("Operation completed successfully")
await manager.log_error("Something went wrong")
```

## Authentication

### Token Authentication

```python
from grpc_mcp_sdk import create_token_auth, requires_auth

auth = create_token_auth(["secret-token-123", "admin-token-456"])

@mcp_tool(description="Protected operation", requires_auth=True)
@requires_auth()
def protected_operation():
    return MCPToolResult().add_text("Access granted")
```

### API Key Authentication

```python
from grpc_mcp_sdk import create_api_key_auth

auth = create_api_key_auth({
    "key-123": {"user": "alice", "permissions": ["read", "write"]},
    "key-456": {"user": "bob", "permissions": ["read"]}
})
```

### JWT Authentication

```python
from grpc_mcp_sdk import create_jwt_auth

auth = create_jwt_auth(
    secret="your-secret-key",
    algorithm="HS256"
)
```

### Permission-Based Access

```python
from grpc_mcp_sdk import requires_permission

@mcp_tool(description="Admin function")
@requires_permission("admin")
def admin_function():
    return MCPToolResult().add_text("Admin access")
```

## Client Usage

### gRPC Client

```python
from grpc_mcp_sdk import create_client
import asyncio

async def main():
    client = create_client("localhost:50051")
    await client.connect()

    # List available tools
    tools = await client.list_tools()
    for tool in tools:
        print(f"Tool: {tool.name} - {tool.description}")

    # Execute a tool
    result = await client.execute_tool("square", {"x": 5})
    print(result)

    await client.close()

asyncio.run(main())
```

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │           MCP Clients               │
                    │  (Claude Desktop, AI Assistants)    │
                    └──────────────┬──────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
    ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
    │  Stdio Transport │  │  HTTP Bridge    │  │  gRPC Direct    │
    │  (JSON-RPC)      │  │  (JSON-RPC/SSE) │  │  (Protobuf)     │
    └────────┬────────┘  └────────┬────────┘  └────────┬────────┘
              │                    │                    │
              └────────────────────┼────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │       Core Registries       │
                    ├─────────────────────────────┤
                    │  ToolRegistry               │
                    │  ResourceRegistry           │
                    │  PromptRegistry             │
                    │  NotificationManager        │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │      Your Tools/Resources   │
                    │      @mcp_tool              │
                    │      @mcp_resource          │
                    │      @mcp_prompt            │
                    └─────────────────────────────┘
```

### Component Overview

| Component | Description |
|-----------|-------------|
| `ToolRegistry` | Manages tool registration, discovery, and execution |
| `ResourceRegistry` | Manages resource registration and subscription |
| `PromptRegistry` | Manages prompt templates |
| `NotificationManager` | Handles server-initiated notifications |
| `StdioTransport` | JSON-RPC over stdin/stdout for local clients |
| `MCPBridge` | HTTP bridge for JSON-RPC clients |
| `MCPServicer` | gRPC service implementation |

## Project Structure

```
grpc_mcp_sdk/
├── __init__.py           # Package exports and CLI
├── core/
│   ├── types.py          # Data types (MCPToolResult, ToolDefinition, etc.)
│   ├── registry.py       # ToolRegistry
│   ├── resource_registry.py  # ResourceRegistry
│   ├── prompt_registry.py    # PromptRegistry
│   ├── notifications.py  # NotificationManager
│   ├── decorators.py     # @mcp_tool, @streaming_tool
│   ├── server.py         # gRPC server
│   └── client.py         # gRPC client
├── transport/
│   └── stdio.py          # Stdio transport for Claude Desktop
├── bridge.py             # HTTP/JSON-RPC bridge
├── auth/                 # Authentication handlers
├── security/             # Rate limiting, input sanitization
├── proto/                # Protocol buffer definitions
└── utils/                # Validation, error handling
```

## MCP Protocol Compliance

This SDK implements the MCP specification (2024-11-05):

| Feature | Status | Notes |
|---------|--------|-------|
| Tools (list, call) | Supported | Full JSON Schema inputSchema |
| Resources (list, read, subscribe) | Supported | Static and template resources |
| Prompts (list, get) | Supported | Multiple return formats |
| Notifications | Supported | All standard notification types |
| Capabilities negotiation | Supported | listChanged flags |
| Progress reporting | Supported | Via notification manager |
| Logging | Supported | Via notification manager |

## Examples

See the `examples/` directory for complete working examples:

- `basic_server.py` - Simple server with tools
- `resources_example.py` - Resource registration and templates
- `prompts_example.py` - Prompt templates
- `authenticated_server.py` - Server with authentication
- `client_example.py` - Client usage

## Development

```bash
# Clone and setup
git clone https://github.com/mixelpixx/gRPC-MCP-SDK.git
cd gRPC-MCP-SDK
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Type checking
mypy grpc_mcp_sdk/

# Linting
flake8 grpc_mcp_sdk/
black grpc_mcp_sdk/
```

## License

MIT License - see [LICENSE](LICENSE) file.

## Links

- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [Issue Tracker](https://github.com/mixelpixx/gRPC-MCP-SDK/issues)
