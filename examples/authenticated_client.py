"""
Example client demonstrating authentication with the MCP server.
"""
import asyncio
import logging
from grpc_mcp_sdk import create_client, MCPError, create_jwt_auth

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AuthenticatedClient:
    """Client wrapper that handles authentication."""
    
    def __init__(self, server_address: str):
        self.server_address = server_address
        self.client = create_client(server_address)
    
    async def connect(self):
        """Connect to the server."""
        await self.client.connect()
    
    async def close(self):
        """Close the connection."""
        await self.client.close()
    
    async def call_tool_with_auth(self, tool_name: str, arguments: dict, auth_header: dict):
        """Call a tool with authentication headers."""
        try:
            # Add authentication to context
            result = await self.client.execute_tool(
                tool_name,
                arguments,
                context=auth_header
            )
            return result
        except MCPError as e:
            logger.error(f"Tool execution failed: {e.code} - {e.message}")
            return None
    
    async def stream_tool_with_auth(self, tool_name: str, arguments: dict, auth_header: dict):
        """Stream from a tool with authentication headers."""
        try:
            results = []
            async for update in self.client.stream_tool(
                tool_name,
                arguments,
                context=auth_header
            ):
                results.append(update)
            return results
        except MCPError as e:
            logger.error(f"Tool streaming failed: {e.code} - {e.message}")
            return []


async def test_authentication_scenarios():
    """Test different authentication scenarios."""
    client = AuthenticatedClient("localhost:50051")
    
    try:
        await client.connect()
        
        print("=== Authentication Testing ===\n")
        
        # Test 1: Public tool (no authentication required)
        print("1. Testing public tool (no auth required):")
        result = await client.call_tool_with_auth("public_info", {}, {})
        if result:
            print(f"   Success: {result}")
        
        # Test 2: Authenticated tool with valid token
        print("\n2. Testing authenticated tool with valid user token:")
        user_auth = {"authorization": "Bearer demo-token-123"}
        result = await client.call_tool_with_auth("user_info", {}, user_auth)
        if result:
            print(f"   Success: {result}")
        
        # Test 3: Authenticated tool with invalid token
        print("\n3. Testing authenticated tool with invalid token:")
        invalid_auth = {"authorization": "Bearer invalid-token"}
        result = await client.call_tool_with_auth("user_info", {}, invalid_auth)
        if not result:
            print("   Expected failure: Invalid token rejected")
        
        # Test 4: Permission-based tool with sufficient permissions
        print("\n4. Testing read tool with read permissions:")
        result = await client.call_tool_with_auth("read_data", {}, user_auth)
        if result:
            print(f"   Success: {result}")
        
        # Test 5: Permission-based tool with insufficient permissions
        print("\n5. Testing admin tool with user permissions:")
        result = await client.call_tool_with_auth("admin_info", {}, user_auth)
        if not result:
            print("   Expected failure: Insufficient permissions")
        
        # Test 6: Admin tool with admin permissions
        print("\n6. Testing admin tool with admin token:")
        admin_auth = {"authorization": "Bearer admin-token-456"}
        result = await client.call_tool_with_auth("admin_info", {}, admin_auth)
        if result:
            print(f"   Success: {result}")
        
        # Test 7: API Key authentication
        print("\n7. Testing API Key authentication:")
        api_key_auth = {"x-api-key": "mcp_demo_key_123"}
        result = await client.call_tool_with_auth("user_info", {}, api_key_auth)
        if result:
            print(f"   Success: {result}")
        
        # Test 8: Write permission test
        print("\n8. Testing write tool with write permissions:")
        result = await client.call_tool_with_auth(
            "write_data",
            {"data": "test data"},
            admin_auth
        )
        if result:
            print(f"   Success: {result}")
        
        # Test 9: Streaming with authentication
        print("\n9. Testing streaming tool with authentication:")
        stream_results = await client.stream_tool_with_auth(
            "authenticated_stream",
            {"count": 3},
            user_auth
        )
        if stream_results:
            print(f"   Success: Received {len(stream_results)} stream updates")
            for i, update in enumerate(stream_results):
                print(f"     Update {i+1}: {update}")
        
        # Test 10: JWT Token generation and usage
        print("\n10. Testing JWT token generation:")
        jwt_auth = create_jwt_auth("demo-secret-key-12345")
        jwt_token = jwt_auth.generate_token(
            user_id="jwt_user",
            permissions=["read", "user"],
            expires_in=3600
        )
        print(f"   Generated JWT: {jwt_token[:50]}...")
        
        jwt_auth_header = {"authorization": f"Bearer {jwt_token}"}
        result = await client.call_tool_with_auth("user_info", {}, jwt_auth_header)
        if result:
            print(f"   JWT Auth Success: {result}")
        
        print("\n=== Authentication Testing Complete ===")
        
    except Exception as e:
        logger.error(f"Client error: {e}")
        raise
    finally:
        await client.close()


async def main():
    """Main client function."""
    print("Authentication Client Example")
    print("Make sure the authenticated server is running:")
    print("  python examples/authenticated_server.py")
    print()
    
    await test_authentication_scenarios()


if __name__ == "__main__":
    asyncio.run(main())