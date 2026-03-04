"""Basic tests for gRPC MCP SDK."""

import pytest
from grpc_mcp_sdk import mcp_tool, MCPToolResult, ToolRegistry


@mcp_tool(description="Test tool")
def test_tool(x: int) -> MCPToolResult:
    """Test tool for unit tests."""
    return MCPToolResult().add_text(f"Result: {x}")


def test_tool_registration():
    """Test that tools are properly registered."""
    registry = ToolRegistry.global_registry()
    assert "test_tool" in registry.tools
    
    tool = registry.get_tool("test_tool")
    assert tool is not None
    assert tool.description == "Test tool"


@pytest.mark.asyncio
async def test_tool_execution():
    """Test tool execution."""
    registry = ToolRegistry.global_registry()
    tool = registry.get_tool("test_tool")
    
    from grpc_mcp_sdk.core.types import ExecutionContext
    context = ExecutionContext(request_id="test")
    
    result = await tool.execute({"x": 42}, context.to_dict())
    assert isinstance(result, MCPToolResult)
    assert len(result.content) > 0
    assert result.content[0]["text"] == "Result: 42"


def test_mcp_tool_result():
    """Test MCPToolResult functionality."""
    result = MCPToolResult()
    
    # Test text content
    result.add_text("Hello World")
    assert len(result.content) == 1
    assert result.content[0]["type"] == "text"
    assert result.content[0]["text"] == "Hello World"
    
    # Test JSON content
    result.add_json({"key": "value"})
    assert len(result.content) == 2
    assert result.content[1]["type"] == "json"
    assert result.content[1]["data"] == {"key": "value"}
    
    # Test metadata
    result.set_metadata("test", "value")
    assert result.metadata["test"] == "value"