"""
Basic tests for gRPC MCP SDK

This test suite validates the core functionality of the gRPC MCP SDK
including tool registration, execution, and bridge compatibility.
"""

import asyncio
import json
import pytest
import time
from unittest.mock import Mock, patch

# Import our SDK components
from grpc_mcp_sdk import (
    mcp_tool, streaming_tool, MCPToolResult, MCPToolContext,
    MCPToolRegistry, create_server, create_client
)
from mcp_grpc_bridge import MCPBridge

# Test fixtures and utilities
@pytest.fixture
def sample_tool_registry():
    """Create a clean tool registry for testing"""
    registry = MCPToolRegistry()
    return registry

@pytest.fixture
def sample_tools():
    """Register sample tools for testing"""
    
    @mcp_tool(description="Add two numbers")
    def add_numbers(a: int, b: int) -> MCPToolResult:
        result = a + b
        return MCPToolResult().add_text(f"{a} + {b} = {result}")
    
    @mcp_tool(description="Get current time", rate_limit=10)
    def get_current_time() -> MCPToolResult:
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        return MCPToolResult().add_json({
            "timestamp": current_time,
            "unix_time": time.time()
        })
    
    @streaming_tool(description="Count to number")
    async def count_to_number(target: int = 5):
        for i in range(1, target + 1):
            yield f"Counting: {i}"
            await asyncio.sleep(0.01)
        
        result = MCPToolResult()
        result.add_text(f"Finished counting to {target}")
        result.add_json({"final_count": target})
        yield result
    
    @mcp_tool(description="Secure function", requires_auth=True)
    def secure_function(message: str = "default") -> MCPToolResult:
        return MCPToolResult().add_text(f"Secure: {message}")
    
    return {
        "add_numbers": add_numbers,
        "get_current_time": get_current_time,
        "count_to_number": count_to_number,
        "secure_function": secure_function
    }

class TestMCPToolResult:
    """Test MCPToolResult functionality"""
    
    def test_create_empty_result(self):
        result = MCPToolResult()
        assert result.content == []
        assert result.metadata == {}
        assert result.is_error == False
    
    def test_add_text_content(self):
        result = MCPToolResult()
        result.add_text("Hello, World!")
        
        assert len(result.content) == 1
        assert result.content[0]["type"] == "text"
        assert result.content[0]["text"] == "Hello, World!"
    
    def test_add_json_content(self):
        result = MCPToolResult()
        data = {"key": "value", "number": 42}
        result.add_json(data)
        
        assert len(result.content) == 1
        assert result.content[0]["type"] == "json"
        assert json.loads(result.content[0]["text"]) == data
    
    def test_add_multiple_content(self):
        result = MCPToolResult()
        result.add_text("Text content")
        result.add_json({"json": "content"})
        
        assert len(result.content) == 2
        assert result.content[0]["type"] == "text"
        assert result.content[1]["type"] == "json"
    
    def test_set_error(self):
        result = MCPToolResult()
        result.set_error("Something went wrong", 500)
        
        assert result.is_error == True
        assert result.error_message == "Something went wrong"
        assert result.error_code == 500
    
    def test_metadata(self):
        result = MCPToolResult()
        result.metadata["source"] = "test"
        result.metadata["version"] = "1.0"
        
        assert result.metadata["source"] == "test"
        assert result.metadata["version"] == "1.0"

class TestMCPToolContext:
    """Test MCPToolContext functionality"""
    
    def test_create_context(self):
        context = MCPToolContext("session-123", {"auth": "token"})
        
        assert context.session_id == "session-123"
        assert context.metadata["auth"] == "token"
        assert context.streaming == False
        assert context.cancelled == False
    
    def test_cancel_context(self):
        context = MCPToolContext("session-123", {})
        
        assert context.is_cancelled() == False
        context.cancel()
        assert context.is_cancelled() == True

class TestToolDecorators:
    """Test tool decorator functionality"""
    
    def test_basic_tool_registration(self, sample_tool_registry):
        @mcp_tool(description="Test tool")
        def test_tool(x: int) -> MCPToolResult:
            return MCPToolResult().add_text(str(x))
        
        # Tool should be registered
        from grpc_mcp_sdk import _tool_registry
        tool_def = _tool_registry.get("test_tool")
        
        assert tool_def is not None
        assert tool_def.name == "test_tool"
        assert tool_def.description == "Test tool"
        assert "x" in tool_def.parameters
    
    def test_streaming_tool_registration(self):
        @streaming_tool(description="Streaming test")
        async def streaming_test():
            yield "test"
        
        from grpc_mcp_sdk import _tool_registry
        tool_def = _tool_registry.get("streaming_test")
        
        assert tool_def is not None
        assert tool_def.streaming == True
    
    def test_tool_with_auth_and_rate_limit(self):
        @mcp_tool(description="Secure tool", requires_auth=True, rate_limit=5)
        def secure_tool():
            return MCPToolResult().add_text("secure")
        
        from grpc_mcp_sdk import _tool_registry
        tool_def = _tool_registry.get("secure_tool")
        
        assert tool_def is not None
        assert tool_def.requires_auth == True
        assert tool_def.rate_limit == 5

class TestToolExecution:
    """Test tool execution functionality"""
    
    @pytest.mark.asyncio
    async def test_basic_tool_execution(self, sample_tools):
        # Test synchronous tool
        result = sample_tools["add_numbers"](5, 3)
        
        assert isinstance(result, MCPToolResult)
        assert len(result.content) == 1
        assert "5 + 3 = 8" in result.content[0]["text"]
    
    @pytest.mark.asyncio
    async def test_streaming_tool_execution(self, sample_tools):
        # Test asynchronous streaming tool
        results = []
        async for result in sample_tools["count_to_number"](3):
            results.append(result)
        
        # Should have progress messages plus final result
        assert len(results) >= 3  # At least 3 count messages
        
        # Last result should be MCPToolResult
        final_result = results[-1]
        assert isinstance(final_result, MCPToolResult)
        assert "Finished counting to 3" in final_result.content[0]["text"]

class TestMCPBridge:
    """Test MCP Bridge functionality"""
    
    def test_jsonrpc_validation(self):
        bridge = MCPBridge()
        
        # Valid request
        valid_request = {
            "jsonrpc": "2.0",
            "method": "test",
            "id": 1
        }
        assert bridge._validate_jsonrpc_request(valid_request) == True
        
        # Invalid requests
        invalid_requests = [
            {"method": "test", "id": 1},  # Missing jsonrpc
            {"jsonrpc": "1.0", "method": "test", "id": 1},  # Wrong version
            {"jsonrpc": "2.0", "id": 1},  # Missing method
        ]
        
        for invalid_request in invalid_requests:
            assert bridge._validate_jsonrpc_request(invalid_request) == False
    
    def test_grpc_to_mcp_conversion(self):
        bridge = MCPBridge()
        
        # Sample gRPC result
        grpc_result = {
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": "Hello, World!",
                        "annotations": {"source": "test"}
                    },
                    {
                        "type": "json",
                        "text": '{"key": "value"}'
                    }
                ],
                "metadata": {
                    "execution_time": "10ms"
                }
            }
        }
        
        mcp_result = bridge._convert_grpc_result_to_mcp(grpc_result)
        
        assert "content" in mcp_result
        assert "metadata" in mcp_result
        assert len(mcp_result["content"]) == 2
        assert mcp_result["content"][0]["type"] == "text"
        assert mcp_result["content"][0]["text"] == "Hello, World!"
        assert mcp_result["metadata"]["execution_time"] == "10ms"

class TestSchemaGeneration:
    """Test schema generation functionality"""
    
    def test_tool_schema_generation(self, sample_tools):
        from grpc_mcp_sdk import _tool_registry
        
        schema = _tool_registry.get_schema()
        
        assert "tools" in schema
        assert isinstance(schema["tools"], list)
        
        # Find our add_numbers tool
        add_tool = None
        for tool in schema["tools"]:
            if tool["name"] == "add_numbers":
                add_tool = tool
                break
        
        assert add_tool is not None
        assert add_tool["description"] == "Add two numbers"
        assert "inputSchema" in add_tool
        assert "properties" in add_tool["inputSchema"]
        assert "a" in add_tool["inputSchema"]["properties"]
        assert "b" in add_tool["inputSchema"]["properties"]

class TestPerformance:
    """Basic performance tests"""
    
    @pytest.mark.asyncio
    async def test_tool_execution_performance(self, sample_tools):
        """Test that tool execution is reasonably fast"""
        start_time = time.time()
        
        # Execute tool 100 times
        for _ in range(100):
            result = sample_tools["add_numbers"](1, 2)
            assert isinstance(result, MCPToolResult)
        
        end_time = time.time()
        total_time = end_time - start_time
        avg_time = total_time / 100
        
        # Should average less than 1ms per execution
        assert avg_time < 0.001, f"Tool execution too slow: {avg_time:.4f}s average"
    
    @pytest.mark.asyncio
    async def test_json_serialization_performance(self):
        """Test JSON serialization performance"""
        large_data = {"items": [{"id": i, "value": f"item_{i}"} for i in range(1000)]}
        
        start_time = time.time()
        
        # Serialize 100 times
        for _ in range(100):
            result = MCPToolResult()
            result.add_json(large_data)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Should complete in reasonable time
        assert total_time < 1.0, f"JSON serialization too slow: {total_time:.4f}s total"

class TestErrorHandling:
    """Test error handling scenarios"""
    
    def test_tool_execution_error(self):
        @mcp_tool(description="Error tool")
        def error_tool():
            raise ValueError("Test error")
        
        # Tool should be registered but execution should handle error
        from grpc_mcp_sdk import _tool_registry
        tool_def = _tool_registry.get("error_tool")
        assert tool_def is not None
    
    def test_invalid_tool_parameters(self):
        @mcp_tool(description="Param tool")
        def param_tool(required_param: str) -> MCPToolResult:
            return MCPToolResult().add_text(required_param)
        
        # This would typically be handled by the gRPC layer
        # but we can test the tool definition
        from grpc_mcp_sdk import _tool_registry
        tool_def = _tool_registry.get("param_tool")
        assert "required_param" in tool_def.parameters

def run_basic_tests():
    """Run a subset of tests without pytest"""
    print("🧪 Running basic gRPC MCP SDK tests...")
    
    # Test MCPToolResult
    print("  ✓ Testing MCPToolResult...")
    result = MCPToolResult()
    result.add_text("Test message")
    assert len(result.content) == 1
    
    # Test tool registration
    print("  ✓ Testing tool registration...")
    @mcp_tool(description="Test tool")
    def basic_test_tool(x: int) -> MCPToolResult:
        return MCPToolResult().add_text(f"Input: {x}")
    
    from grpc_mcp_sdk import _tool_registry
    tool_def = _tool_registry.get("basic_test_tool")
    assert tool_def is not None
    
    # Test tool execution
    print("  ✓ Testing tool execution...")
    result = basic_test_tool(42)
    assert isinstance(result, MCPToolResult)
    assert "Input: 42" in result.content[0]["text"]
    
    # Test bridge validation
    print("  ✓ Testing bridge validation...")
    bridge = MCPBridge()
    valid_request = {"jsonrpc": "2.0", "method": "test", "id": 1}
    assert bridge._validate_jsonrpc_request(valid_request) == True
    
    print("✅ All basic tests passed!")

if __name__ == "__main__":
    # Run basic tests if executed directly
    run_basic_tests()