"""
Example MCP server with authentication demonstrating different auth methods.
"""
import asyncio
import logging
from grpc_mcp_sdk import (
    mcp_tool, streaming_tool, MCPToolResult, run_server,
    create_token_auth, create_api_key_auth, create_jwt_auth,
    requires_auth, requires_permission
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@mcp_tool(description="Public tool - no authentication required")
def public_info() -> MCPToolResult:
    """Get public server information"""
    return MCPToolResult().add_json({
        "server": "Authenticated MCP Server",
        "version": "1.0.0",
        "public": True
    })


@mcp_tool(description="Basic authenticated tool")
@requires_auth()
def user_info() -> MCPToolResult:
    """Get user information - requires authentication"""
    return MCPToolResult().add_json({
        "message": "You are authenticated!",
        "access_level": "user"
    })


@mcp_tool(description="Tool requiring admin permissions")
@requires_permission("admin")
def admin_info() -> MCPToolResult:
    """Get admin information - requires admin permission"""
    return MCPToolResult().add_json({
        "message": "Admin access granted",
        "access_level": "admin",
        "sensitive_data": "This is admin-only information"
    })


@mcp_tool(description="Tool requiring read permissions")
@requires_permission("read")
def read_data() -> MCPToolResult:
    """Read data - requires read permission"""
    return MCPToolResult().add_json({
        "data": [1, 2, 3, 4, 5],
        "message": "Data read successfully"
    })


@mcp_tool(description="Tool requiring write permissions")
@requires_permission("write")
def write_data(data: str) -> MCPToolResult:
    """Write data - requires write permission"""
    return MCPToolResult().add_json({
        "message": f"Data written: {data}",
        "success": True
    })


@streaming_tool(description="Streaming tool requiring authentication")
@requires_auth()
async def authenticated_stream(count: int = 5):
    """Streaming tool that requires authentication"""
    for i in range(1, count + 1):
        yield MCPToolResult().add_json({
            "step": i,
            "message": f"Authenticated streaming step {i}/{count}",
            "authenticated": True
        })
        await asyncio.sleep(0.2)


def create_demo_auth_handler():
    """Create a demo authentication handler with multiple methods."""
    
    # Method 1: Token Authentication
    token_auth = create_token_auth(
        tokens=["demo-token-123", "admin-token-456"],
        permissions_map={
            "demo-token-123": ["read", "user"],
            "admin-token-456": ["read", "write", "admin", "user"]
        },
        user_map={
            "demo-token-123": "demo_user",
            "admin-token-456": "admin_user"
        }
    )
    
    # Method 2: API Key Authentication
    api_key_auth = create_api_key_auth({
        "mcp_demo_key_123": {
            "user_id": "api_user",
            "permissions": ["read", "write", "user"],
            "name": "Demo API Key"
        },
        "mcp_admin_key_456": {
            "user_id": "api_admin",
            "permissions": ["read", "write", "admin", "user"],
            "name": "Admin API Key"
        }
    })
    
    # Method 3: JWT Authentication
    jwt_auth = create_jwt_auth(
        secret_key="demo-secret-key-12345",
        verify_exp=True
    )
    
    # For demo purposes, we'll use token auth
    # In production, you might use MultiAuthHandler to support multiple methods
    return token_auth


async def main():
    """Main server function."""
    logger.info("Starting authenticated gRPC MCP server...")
    
    # Create authentication handler
    auth_handler = create_demo_auth_handler()
    
    logger.info("Available tools:")
    logger.info("  Public tools:")
    logger.info("    - public_info: Get public server info (no auth)")
    logger.info("  Authenticated tools:")
    logger.info("    - user_info: User info (requires auth)")
    logger.info("    - authenticated_stream: Streaming tool (requires auth)")
    logger.info("  Permission-based tools:")
    logger.info("    - read_data: Read data (requires 'read' permission)")
    logger.info("    - write_data: Write data (requires 'write' permission)")
    logger.info("    - admin_info: Admin info (requires 'admin' permission)")
    
    logger.info("\nAuthentication methods:")
    logger.info("  1. Token Auth:")
    logger.info("     - Header: 'authorization: Bearer demo-token-123' (user permissions)")
    logger.info("     - Header: 'authorization: Bearer admin-token-456' (admin permissions)")
    logger.info("  2. API Key Auth:")
    logger.info("     - Header: 'x-api-key: mcp_demo_key_123' (user permissions)")
    logger.info("     - Header: 'x-api-key: mcp_admin_key_456' (admin permissions)")
    
    # Start server with authentication
    await run_server(
        host="0.0.0.0",
        port=50051,
        server_name="Authenticated-MCP-Server",
        version="1.0.0",
        auth_handler=auth_handler
    )


if __name__ == "__main__":
    asyncio.run(main())