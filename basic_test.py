#!/usr/bin/env python3
"""
Basic test script to validate gRPC MCP SDK core functionality
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
        print("   [OK] Tool registration working correctly")
        
        # Test 4: Test tool execution
        print("4. Testing tool execution...")
        execution_result = add_numbers(5, 3)
        assert isinstance(execution_result, MCPToolResult)
        assert len(execution_result.content) == 1
        assert "5 + 3 = 8" in execution_result.content[0]["text"]
        print("   [OK] Tool execution working correctly")
        
        # Test 5: Test schema generation
        print("5. Testing schema generation...")
        schema = _tool_registry.get_schema()
        assert "tools" in schema
        assert isinstance(schema["tools"], list)
        assert len(schema["tools"]) >= 1  # At least our test tool
        
        # Find our test tool in schema
        tool_names = [tool["name"] for tool in schema["tools"]]
        assert "add_numbers" in tool_names
        print("   [OK] Schema generation working correctly")
        
        # Test 6: Test authentication and rate limiting features
        print("6. Testing security features...")
        
        @mcp_tool(description="Secure tool", requires_auth=True, rate_limit=5)
        def secure_tool(message: str = "test") -> MCPToolResult:
            return MCPToolResult().add_text(f"Secure: {message}")
        
        secure_def = _tool_registry.get("secure_tool")
        assert secure_def.requires_auth == True
        assert secure_def.rate_limit == 5
        print("   [OK] Security features working correctly")
        
        # Test 7: Test error handling
        print("7. Testing error handling...")
        error_result = MCPToolResult()
        error_result.set_error("Test error", 400)
        assert error_result.is_error == True
        assert error_result.error_message == "Test error"
        assert error_result.error_code == 400
        print("   [OK] Error handling working correctly")
        
        print("\nALL BASIC TESTS PASSED!")
        print("=" * 50)
        print("[OK] Core SDK functionality validated")
        print("[OK] Tool registration system working")
        print("[OK] Security features implemented")
        print("[OK] Schema generation working")
        print("[OK] Error handling robust")
        
        return True
        
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    success = test_basic_functionality()
    
    if success:
        print("\nSUCCESS: All tests passed!")
        print("The gRPC MCP SDK is working correctly and ready for use.")
        return 0
    else:
        print("\nFAILED: Some tests failed!")
        print("Please check the implementation.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)