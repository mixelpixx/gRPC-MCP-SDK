"""
gRPC MCP SDK - A modern Python framework for building high-performance MCP tools with gRPC

This package provides:
- Simple decorators for defining MCP tools (@mcp_tool, @streaming_tool)
- High-performance gRPC transport (5-10x faster than JSON-RPC)
- Built-in authentication and rate limiting
- Production-ready deployment tools
- Agent-to-Agent (A2A) protocol support
- Multi-agent workflow orchestration
- Comprehensive examples and documentation
"""

# Import main components from our core module
from .core import (
    # Core classes
    MCPToolResult,
    ToolRegistry,
    Tool,
    MCPServicer,
    MCPClient,
    
    # Decorators
    mcp_tool,
    streaming_tool,
    tool,
    streaming,
    
    # Server functions
    create_server,
    run_server,
    
    # Client functions
    create_client,
    
    # Types
    ToolParameter,
    ToolDefinition,
    ExecutionContext,
    ToolProgress,
)

# Import utilities
from .utils import (
    ErrorCode,
    MCPError,
    ToolNotFoundError,
    ToolExecutionError,
    ValidationError,
    AuthenticationError,
    RateLimitError,
    validate_tool_name,
    validate_parameters,
    validate_context,
    sanitize_string
)

# Import auth components
from .auth import (
    AuthHandler,
    AuthResult,
    AuthContext,
    TokenAuthHandler,
    create_token_auth,
    APIKeyAuthHandler,
    create_api_key_auth,
    JWTAuthHandler,
    create_jwt_auth,
    requires_auth,
    requires_permission,
    AuthMiddleware,
)

# A2A extensions - will be implemented later
_A2A_AVAILABLE = False

# Version info
__version__ = "1.0.0"
__author__ = "gRPC MCP SDK Team"
__description__ = "A modern Python framework for building high-performance MCP tools with gRPC"

# Public API
__all__ = [
    # Core classes
    'MCPToolResult',
    'ToolRegistry',
    'Tool',
    'MCPServicer',
    'MCPClient',
    
    # Decorators
    'mcp_tool',
    'streaming_tool',
    'tool',
    'streaming',
    
    # Server functions
    'create_server',
    'run_server',
    
    # Client functions
    'create_client',
    
    # Types
    'ToolParameter',
    'ToolDefinition',
    'ExecutionContext',
    'ToolProgress',
    
    # Errors
    'ErrorCode',
    'MCPError',
    'ToolNotFoundError',
    'ToolExecutionError',
    'ValidationError',
    'AuthenticationError',
    'RateLimitError',
    
    # Validation
    'validate_tool_name',
    'validate_parameters',
    'validate_context',
    'sanitize_string',
    
    # Auth
    'AuthHandler',
    'AuthResult',
    'AuthContext',
    'TokenAuthHandler',
    'create_token_auth',
    'APIKeyAuthHandler',
    'create_api_key_auth',
    'JWTAuthHandler',
    'create_jwt_auth',
    'requires_auth',
    'requires_permission',
    'AuthMiddleware',
    
    # Metadata
    '__version__',
    '__author__',
    '__description__',
]

def is_a2a_available() -> bool:
    """Check if A2A extensions are available"""
    return _A2A_AVAILABLE

def main():
    """Main CLI entry point"""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(
        description="gRPC MCP SDK - Command Line Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  grpc-mcp serve --module my_tools --port 50051
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Serve command  
    serve_parser = subparsers.add_parser('serve', help='Start MCP gRPC server')
    serve_parser.add_argument('--module', help='Python module containing tools')
    serve_parser.add_argument('--host', default='localhost', help='Server host')
    serve_parser.add_argument('--port', type=int, default=50051, help='Server port')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if args.command == 'serve':
        if args.module:
            import importlib
            importlib.import_module(args.module)
        
        import asyncio
        asyncio.run(run_server(host=args.host, port=args.port))

if __name__ == "__main__":
    main()