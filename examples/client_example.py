"""
Example client that connects to the basic server and tests all functionality.
"""
import asyncio
import logging
from grpc_mcp_sdk import create_client, MCPError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Main client example."""
    # Create and connect to client
    client = create_client("localhost:50051")
    
    try:
        await client.connect()
        
        # Test 1: Health check
        print("=== Health Check ===")
        health = await client.health_check()
        print(f"Server health: {health}")
        
        # Test 2: List tools
        print("\n=== List Tools ===")
        tools = await client.list_tools()
        for tool in tools:
            print(f"Tool: {tool.name}")
            print(f"  Description: {tool.description}")
            print(f"  Streaming: {tool.supports_streaming}")
            print(f"  Parameters: {len(tool.parameters)}")
            for param in tool.parameters:
                print(f"    {param.name} ({param.type}): {param.description}")
        
        # Test 3: Execute simple tool
        print("\n=== Execute square_number ===")
        result = await client.execute_tool("square_number", {"x": 5})
        print(f"Result: {result}")
        
        # Test 4: Execute tool with multiple parameters
        print("\n=== Execute add_numbers ===")
        result = await client.execute_tool("add_numbers", {"a": 10, "b": 20})
        print(f"Result: {result}")
        
        # Test 5: Execute tool with optional parameters
        print("\n=== Execute get_person_info ===")
        result = await client.execute_tool("get_person_info", {"name": "Alice", "age": 30})
        print(f"Result: {result}")
        
        # Test 6: Stream tool results
        print("\n=== Stream count_to_n ===")
        stream_count = 0
        async for update in client.stream_tool("count_to_n", {"n": 5}):
            stream_count += 1
            print(f"Stream {stream_count}: {update}")
        
        # Test 7: Stream tool with list processing
        print("\n=== Stream process_items ===")
        items = ["apple", "banana", "cherry"]
        stream_count = 0
        async for update in client.stream_tool("process_items", {"items": items}):
            stream_count += 1
            print(f"Stream {stream_count}: {update}")
        
        # Test 8: Error handling - non-existent tool
        print("\n=== Error Handling ===")
        try:
            await client.execute_tool("non_existent_tool", {})
        except MCPError as e:
            print(f"Expected error: {e.code} - {e.message}")
        
        # Test 9: Error handling - invalid parameters
        try:
            await client.execute_tool("square_number", {})  # Missing required parameter
        except MCPError as e:
            print(f"Expected error: {e.code} - {e.message}")
        
        print("\n=== All tests completed successfully! ===")
        
    except Exception as e:
        logger.error(f"Client error: {e}")
        raise
    finally:
        await client.close()


if __name__ == "__main__":
    print("Starting MCP client example...")
    print("Make sure the basic server is running: python examples/basic_server.py")
    asyncio.run(main())