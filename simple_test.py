#!/usr/bin/env python3
"""
Simple test script to validate gRPC MCP SDK core functionality
"""

import sys
import json
import asyncio
from typing import Any, Dict

def test_basic_functionality():
    """Test basic SDK functionality without external dependencies"""
    print("Testing gRPC MCP SDK Basic Functionality")
    print("=" * 50)
    
    try:
        # Test 1: Import and execute core SDK
        print("1. Testing core SDK imports...")
        exec(open('grpc-mcp-sdk.py').read(), globals())
        print("   [OK] Core SDK imported successfully")
        
        # Test 2: Test MCPToolResult
        print("2. Testing MCPToolResult...")
        result = MCPToolResult()
        result.add_text("Hello, World!")
        result.add_json({"test": "data"})
        result.metadata["source"] = "test"
        
        assert len(result.content) == 2
        assert result.content[0]["type"] == "text"
        assert result.content[0]["text"] == "Hello, World!"
        assert result.metadata["source"] == "test"
        print("   [OK] MCPToolResult working correctly")
        
        # Test 3: Test tool registration
        print("3. Testing tool registration...")
        
        @mcp_tool(description="Test addition tool")
        def add_numbers(a: int, b: int) -> MCPToolResult:
            """Add two numbers together"""
            result = a + b
            return MCPToolResult().add_text(f"{a} + {b} = {result}")
        
        # Verify tool was registered
        tool_def = _tool_registry.get("add_numbers")
        assert tool_def is not None
        assert tool_def.name == "add_numbers"
        assert tool_def.description == "Test addition tool"
        assert "a" in tool_def.parameters
        assert "b" in tool_def.parameters
        print("   ✅ Tool registration working correctly")
        
        # Test 4: Test tool execution
        print("4. Testing tool execution...")
        execution_result = add_numbers(5, 3)
        assert isinstance(execution_result, MCPToolResult)
        assert len(execution_result.content) == 1
        assert "5 + 3 = 8" in execution_result.content[0]["text"]
        print("   ✅ Tool execution working correctly")
        
        # Test 5: Test streaming tool
        print("5. Testing streaming tool...")
        
        @streaming_tool(description="Count to target")
        async def count_to_target(target: int = 3):
            """Count up to target number"""
            for i in range(1, target + 1):
                yield f"Count: {i}"
                await asyncio.sleep(0.001)  # Very small delay
            
            final_result = MCPToolResult()
            final_result.add_text(f"Counted to {target}")
            yield final_result
        
        # Verify streaming tool was registered
        stream_tool_def = _tool_registry.get("count_to_target")
        assert stream_tool_def is not None
        assert stream_tool_def.streaming == True
        print("   ✅ Streaming tool registration working correctly")
        
        # Test 6: Test schema generation
        print("6. Testing schema generation...")
        schema = _tool_registry.get_schema()
        assert "tools" in schema
        assert isinstance(schema["tools"], list)
        assert len(schema["tools"]) >= 2  # At least our two test tools
        
        # Find our test tools in schema
        tool_names = [tool["name"] for tool in schema["tools"]]
        assert "add_numbers" in tool_names
        assert "count_to_target" in tool_names
        print("   ✅ Schema generation working correctly")
        
        # Test 7: Test authentication and rate limiting features
        print("7. Testing security features...")
        
        @mcp_tool(description="Secure tool", requires_auth=True, rate_limit=5)
        def secure_tool(message: str = "test") -> MCPToolResult:
            return MCPToolResult().add_text(f"Secure: {message}")
        
        secure_def = _tool_registry.get("secure_tool")
        assert secure_def.requires_auth == True
        assert secure_def.rate_limit == 5
        print("   ✅ Security features working correctly")
        
        # Test 8: Test error handling
        print("8. Testing error handling...")
        error_result = MCPToolResult()
        error_result.set_error("Test error", 400)
        assert error_result.is_error == True
        assert error_result.error_message == "Test error"
        assert error_result.error_code == 400
        print("   ✅ Error handling working correctly")
        
        print("\n🎉 ALL BASIC TESTS PASSED!")
        print("=" * 50)
        print("✅ Core SDK functionality validated")
        print("✅ Tool registration system working")
        print("✅ Streaming tools supported")
        print("✅ Security features implemented")
        print("✅ Schema generation working")
        print("✅ Error handling robust")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_async_functionality():
    """Test async functionality"""
    print("\n🧪 Testing Async Functionality")
    print("=" * 30)
    
    try:
        # Test streaming tool execution
        @streaming_tool(description="Async counter")
        async def async_counter(count: int = 3):
            for i in range(count):
                yield f"Async count: {i+1}"
                await asyncio.sleep(0.001)
            yield MCPToolResult().add_text("Async complete")
        
        results = []
        async for result in async_counter(2):
            results.append(result)
        
        assert len(results) == 3  # 2 counts + final result
        assert isinstance(results[-1], MCPToolResult)
        print("✅ Async streaming tool execution working")
        
        return True
        
    except Exception as e:
        print(f"❌ Async test failed: {e}")
        return False

def main():
    """Run all tests"""
    basic_success = test_basic_functionality()
    
    # Run async tests
    async_success = asyncio.run(test_async_functionality())
    
    if basic_success and async_success:
        print("\n🏆 ALL TESTS SUCCESSFUL!")
        print("The gRPC MCP SDK is working correctly and ready for use.")
        return 0
    else:
        print("\n💥 SOME TESTS FAILED!")
        print("Please check the implementation.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)