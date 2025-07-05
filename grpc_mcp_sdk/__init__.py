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
    MCPToolContext,
    MCPToolRegistry,
    MCPGrpcServer,
    MCPGrpcClient,
    ServerConfig,
    
    # Decorators
    mcp_tool,
    streaming_tool,
    
    # Server functions
    create_server,
    create_client,
    run_server,
    
    # Auth helpers
    create_token_auth,
    create_api_key_auth,
    
    # Utility classes
    MCPSecurity,
    MCPDeployment,
    MCPCLI,
    MCPUtils,
    MCPMetrics,
    
    # Registry instance
    _tool_registry,
)

# Import A2A extensions (optional - gracefully handle import errors)
try:
    from .a2a_extensions import (
        # A2A Core classes
        AgentCapabilityType,
        AgentProtocol,
        AgentStatus,
        AgentCapability,
        AgentEndpoint,
        AgentInfo,
        A2AAgentRegistry,
        
        # A2A Decorators
        agent_capability,
        register_local_agent,
        
        # A2A Communication
        A2AAgentClient,
        AgentCommunicationError,
        
        # A2A Workflow
        WorkflowStep,
        WorkflowResult,
        A2AWorkflowOrchestrator,
        
        # A2A Helpers
        get_a2a_registry,
        create_agent_client,
        create_workflow_orchestrator,
    )
    
    _A2A_AVAILABLE = True
    
except ImportError as e:
    # A2A extensions not available - this is fine for basic MCP usage
    _A2A_AVAILABLE = False
    import warnings
    warnings.warn(f"A2A extensions not available: {e}", ImportWarning)

# Version info
__version__ = "1.1.0"  # Bumped version for A2A support
__author__ = "gRPC MCP SDK Team"
__description__ = "A modern Python framework for building high-performance MCP tools with gRPC and A2A support"

# Public API
__all__ = [
    # Core classes
    'MCPToolResult',
    'MCPToolContext',
    'MCPToolRegistry',
    'MCPGrpcServer',
    'MCPGrpcClient',
    'ServerConfig',
    
    # Decorators
    'mcp_tool',
    'streaming_tool',
    
    # Server functions
    'create_server',
    'create_client',
    'run_server',
    
    # Auth helpers
    'create_token_auth',
    'create_api_key_auth',
    
    # Utility classes
    'MCPSecurity',
    'MCPDeployment',
    'MCPCLI',
    'MCPUtils',
    'MCPMetrics',
    
    # Registry
    '_tool_registry',
    
    # Metadata
    '__version__',
    '__author__',
    '__description__',
    
    # A2A Helper Functions
    'is_a2a_available',
]

# Add A2A exports if available
if _A2A_AVAILABLE:
    __all__.extend([
        # A2A Core classes
        'AgentCapabilityType',
        'AgentProtocol',
        'AgentStatus',
        'AgentCapability',
        'AgentEndpoint',
        'AgentInfo',
        'A2AAgentRegistry',
        
        # A2A Decorators
        'agent_capability',
        'register_local_agent',
        
        # A2A Communication
        'A2AAgentClient',
        'AgentCommunicationError',
        
        # A2A Workflow
        'WorkflowStep',
        'WorkflowResult',
        'A2AWorkflowOrchestrator',
        
        # A2A Helpers
        'get_a2a_registry',
        'create_agent_client',
        'create_workflow_orchestrator',
    ])

def is_a2a_available() -> bool:
    """Check if A2A extensions are available"""
    return _A2A_AVAILABLE

def main():
    """Main CLI entry point"""
    from .core import MCPCLI
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(
        description="gRPC MCP SDK - Command Line Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  grpc-mcp create my-tools
  grpc-mcp serve --module my_tools --port 50051
  grpc-mcp docker --output docker-compose.yml
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Create project command
    create_parser = subparsers.add_parser('create', help='Create a new MCP project')
    create_parser.add_argument('name', help='Project name')
    create_parser.add_argument('--path', default='.', help='Project path')
    
    # Serve command  
    serve_parser = subparsers.add_parser('serve', help='Start MCP gRPC server')
    serve_parser.add_argument('--module', help='Python module containing tools')
    serve_parser.add_argument('--host', default='localhost', help='Server host')
    serve_parser.add_argument('--port', type=int, default=50051, help='Server port')
    
    # Docker command
    docker_parser = subparsers.add_parser('docker', help='Generate Docker config')
    docker_parser.add_argument('--output', help='Output file')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if args.command == 'create':
        MCPCLI.create_project(args.name, args.path)
    elif args.command == 'serve':
        if args.module:
            import importlib
            importlib.import_module(args.module)
        
        import asyncio
        asyncio.run(run_server(host=args.host, port=args.port))
    elif args.command == 'docker':
        config = MCPDeployment.generate_docker_compose()
        if args.output:
            with open(args.output, 'w') as f:
                f.write(config)
            print(f"Docker configuration written to {args.output}")
        else:
            print(config)

if __name__ == "__main__":
    main()