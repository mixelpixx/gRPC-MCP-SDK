"""
Secure MCP server example demonstrating authentication, rate limiting, and input sanitization.
"""
import asyncio
import logging
from grpc_mcp_sdk import (
    mcp_tool, streaming_tool, MCPToolResult, run_server,
    create_token_auth, create_api_key_auth,
    requires_auth, requires_permission
)
from grpc_mcp_sdk.security import (
    create_rate_limiter, create_sanitizer, sanitize_input
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create security components
RATE_LIMITER = create_rate_limiter(
    requests_per_minute=30,  # Lower limit for demo
    burst_size=5,
    per_user=True,
    per_tool=True
)

INPUT_SANITIZER = create_sanitizer(
    max_string_length=1000,
    max_json_depth=5,
    allow_html=False,
    allow_scripts=False
)


def check_rate_limit(user_id: str, tool_name: str):
    """Check rate limit for a user and tool."""
    allowed, info = RATE_LIMITER.check_rate_limit(
        user_id=user_id,
        tool_name=tool_name
    )
    
    if not allowed:
        logger.warning(f"Rate limit exceeded for {user_id} on {tool_name}: {info}")
        from grpc_mcp_sdk.utils.errors import RateLimitError
        raise RateLimitError(info['limit'], info['window'])
    
    return True


@mcp_tool(description="Echo tool with input sanitization")
@requires_auth()
def secure_echo(message: str, user_context: dict = None) -> MCPToolResult:
    """Echo a message with security checks."""
    # Get user ID from context (this would be set by auth middleware)
    user_id = user_context.get('user_id', 'anonymous') if user_context else 'anonymous'
    
    # Check rate limit
    check_rate_limit(user_id, "secure_echo")
    
    # Sanitize input
    sanitized_message = INPUT_SANITIZER.sanitize_input(message)
    
    logger.info(f"Secure echo for user {user_id}: {sanitized_message[:50]}...")
    
    return MCPToolResult().add_json({
        "original_length": len(message),
        "sanitized_length": len(sanitized_message),
        "sanitized_message": sanitized_message,
        "user_id": user_id
    })


@mcp_tool(description="Process user data with strict validation")
@requires_permission("data_access")
def process_user_data(user_data: dict) -> MCPToolResult:
    """Process user data with comprehensive security checks."""
    try:
        # Sanitize the entire data structure
        sanitized_data = INPUT_SANITIZER.sanitize_input(user_data)
        
        # Validate required fields
        if not isinstance(sanitized_data, dict):
            raise ValueError("user_data must be a dictionary")
        
        required_fields = ['name', 'email']
        missing_fields = [field for field in required_fields if field not in sanitized_data]
        
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")
        
        # Process the data
        result = {
            "processed": True,
            "user_name": sanitized_data.get('name'),
            "user_email": sanitized_data.get('email'),
            "data_size": len(str(sanitized_data)),
            "fields_processed": len(sanitized_data)
        }
        
        logger.info(f"Processed user data: {result}")
        
        return MCPToolResult().add_json(result)
        
    except Exception as e:
        logger.error(f"Error processing user data: {e}")
        return MCPToolResult().add_error(
            "PROCESSING_ERROR",
            f"Failed to process user data: {str(e)}"
        )


@mcp_tool(description="File operations with path validation")
@requires_permission("file_access")
def secure_file_read(file_path: str) -> MCPToolResult:
    """Read file with security validation."""
    import os
    from pathlib import Path
    
    # Sanitize file path
    sanitized_path = INPUT_SANITIZER.sanitize_input(file_path)
    
    # Additional command injection protection
    sanitized_path = INPUT_SANITIZER.sanitize_command_injection(sanitized_path)
    
    # Validate path
    try:
        path = Path(sanitized_path).resolve()
        
        # Security: Only allow access to specific directories
        allowed_dirs = ['/tmp', '/var/tmp', './secure_files']
        
        if not any(str(path).startswith(allowed_dir) for allowed_dir in allowed_dirs):
            raise ValueError("Access to this path is not allowed")
        
        # Check if file exists and is readable
        if not path.exists():
            raise ValueError(f"File not found: {sanitized_path}")
        
        if not path.is_file():
            raise ValueError(f"Path is not a file: {sanitized_path}")
        
        # Read file with size limit
        max_size = 10 * 1024  # 10KB limit
        if path.stat().st_size > max_size:
            raise ValueError(f"File too large: {path.stat().st_size} > {max_size}")
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Sanitize file content
        sanitized_content = INPUT_SANITIZER.sanitize_input(content)
        
        return MCPToolResult().add_json({
            "file_path": str(path),
            "file_size": len(content),
            "content": sanitized_content[:500] + ("..." if len(sanitized_content) > 500 else "")
        })
        
    except Exception as e:
        logger.error(f"Secure file read error: {e}")
        return MCPToolResult().add_error(
            "FILE_ERROR",
            f"Failed to read file: {str(e)}"
        )


@streaming_tool(description="Secure streaming with rate limiting")
@requires_auth()
async def secure_stream(count: int = 10, delay: float = 0.5) -> MCPToolResult:
    """Streaming tool with security checks."""
    # Sanitize inputs
    count = int(INPUT_SANITIZER.sanitize_input(count))
    delay = float(INPUT_SANITIZER.sanitize_input(delay))
    
    # Validate ranges
    if count > 100:
        raise ValueError("Count too large, maximum is 100")
    
    if delay > 5.0:
        raise ValueError("Delay too large, maximum is 5.0 seconds")
    
    # Check rate limit for streaming
    check_rate_limit("stream_user", "secure_stream")
    
    for i in range(1, count + 1):
        # Check rate limit per iteration
        try:
            check_rate_limit("stream_user", "secure_stream")
        except:
            # If rate limited, stop streaming
            yield MCPToolResult().add_error(
                "RATE_LIMITED",
                f"Rate limit exceeded at step {i}"
            )
            break
        
        yield MCPToolResult().add_json({
            "step": i,
            "total": count,
            "message": f"Secure streaming step {i}/{count}",
            "timestamp": asyncio.get_event_loop().time()
        })
        
        await asyncio.sleep(delay)


@mcp_tool(description="Get rate limit status")
@requires_auth()
def get_rate_limit_status(user_id: str = None) -> MCPToolResult:
    """Get current rate limit status."""
    if not user_id:
        user_id = "anonymous"
    
    # Sanitize user ID
    user_id = INPUT_SANITIZER.sanitize_input(user_id)
    
    # Get rate limit status
    status = RATE_LIMITER.get_rate_limit_status(f"user:{user_id}")
    
    return MCPToolResult().add_json({
        "user_id": user_id,
        "rate_limit_status": status
    })


@mcp_tool(description="Admin tool to view all rate limits")
@requires_permission("admin")
def admin_rate_limits() -> MCPToolResult:
    """Admin tool to view all rate limit statuses."""
    all_limits = RATE_LIMITER.get_all_limits()
    
    return MCPToolResult().add_json({
        "all_rate_limits": all_limits,
        "total_keys": len(all_limits)
    })


def create_secure_auth_handler():
    """Create a secure authentication handler."""
    # Create multiple authentication methods
    
    # Token auth with different permission levels
    token_auth = create_token_auth(
        tokens=["secure-user-token", "secure-admin-token", "secure-data-token"],
        permissions_map={
            "secure-user-token": ["basic", "user"],
            "secure-admin-token": ["basic", "user", "admin", "data_access", "file_access"],
            "secure-data-token": ["basic", "user", "data_access"]
        },
        user_map={
            "secure-user-token": "secure_user",
            "secure-admin-token": "secure_admin",
            "secure-data-token": "data_user"
        }
    )
    
    return token_auth


async def main():
    """Main secure server function."""
    logger.info("Starting secure gRPC MCP server...")
    
    # Create secure authentication
    auth_handler = create_secure_auth_handler()
    
    logger.info("Security features enabled:")
    logger.info("  ✓ Authentication (Token-based)")
    logger.info("  ✓ Authorization (Permission-based)")
    logger.info("  ✓ Rate limiting (30 req/min, 5 burst)")
    logger.info("  ✓ Input sanitization")
    logger.info("  ✓ Path validation")
    logger.info("  ✓ SQL injection protection")
    logger.info("  ✓ Command injection protection")
    
    logger.info("\nAvailable tools:")
    logger.info("  - secure_echo: Echo with sanitization (requires auth)")
    logger.info("  - process_user_data: Process user data (requires data_access)")
    logger.info("  - secure_file_read: Read files securely (requires file_access)")
    logger.info("  - secure_stream: Secure streaming (requires auth)")
    logger.info("  - get_rate_limit_status: Check rate limits (requires auth)")
    logger.info("  - admin_rate_limits: View all rate limits (requires admin)")
    
    logger.info("\nAuthentication tokens:")
    logger.info("  - secure-user-token: Basic user access")
    logger.info("  - secure-data-token: Data access permissions")
    logger.info("  - secure-admin-token: Full admin access")
    
    # Start secure server
    await run_server(
        host="0.0.0.0",
        port=50051,
        server_name="Secure-MCP-Server",
        version="1.0.0",
        auth_handler=auth_handler
    )


if __name__ == "__main__":
    asyncio.run(main())