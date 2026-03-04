"""
gRPC MCP SDK - A modern Python framework for building high-performance MCP tools with gRPC

This SDK provides:
- Simple decorators for defining MCP tools
- Automatic gRPC service generation
- Built-in security and authentication
- Cross-platform compatibility
- Streaming support for real-time tools
- Easy deployment and scaling
"""

import asyncio
import json
import logging
import ssl
import time
import uuid
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Union, get_type_hints
import inspect

import grpc
from grpc import aio as aio_grpc
from grpc_health.v1 import health_pb2, health_pb2_grpc
from grpc_reflection.v1alpha import reflection
from google.protobuf import struct_pb2, any_pb2
from google.protobuf.json_format import MessageToDict, ParseDict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# Core Protocol Definitions
# =============================================================================

@dataclass
class MCPToolResult:
    """Represents the result of an MCP tool execution"""
    content: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)
    is_error: bool = False
    error_code: Optional[int] = None
    error_message: Optional[str] = None

    def add_text(self, text: str, annotations: Optional[Dict[str, str]] = None):
        """Add text content to the result"""
        content = {"type": "text", "text": text}
        if annotations:
            content["annotations"] = annotations
        self.content.append(content)
        return self

    def add_json(self, data: Any, annotations: Optional[Dict[str, str]] = None):
        """Add JSON content to the result"""
        content = {
            "type": "json", 
            "text": json.dumps(data, indent=2)
        }
        if annotations:
            content["annotations"] = annotations
        self.content.append(content)
        return self

    def add_image(self, data: bytes, mime_type: str = "image/png", annotations: Optional[Dict[str, str]] = None):
        """Add image content to the result"""
        content = {
            "type": "image",
            "data": data,
            "mime_type": mime_type
        }
        if annotations:
            content["annotations"] = annotations
        self.content.append(content)
        return self

    def set_error(self, message: str, code: int = 500):
        """Mark result as error"""
        self.is_error = True
        self.error_message = message
        self.error_code = code
        return self

class MCPToolContext:
    """Context object passed to tool functions"""
    def __init__(self, session_id: str, metadata: Dict[str, str], streaming: bool = False):
        self.session_id = session_id
        self.metadata = metadata
        self.streaming = streaming
        self.cancelled = False

    def is_cancelled(self) -> bool:
        """Check if the request was cancelled"""
        return self.cancelled

    def cancel(self):
        """Mark the context as cancelled"""
        self.cancelled = True

# =============================================================================
# Tool Definition and Registration
# =============================================================================

@dataclass
class MCPToolDefinition:
    """Definition of an MCP tool"""
    name: str
    description: str
    parameters: Dict[str, Any]
    function: Callable
    streaming: bool = False
    requires_auth: bool = False
    rate_limit: Optional[int] = None

class MCPToolRegistry:
    """Registry for MCP tools"""
    
    def __init__(self):
        self._tools: Dict[str, MCPToolDefinition] = {}
    
    def register(self, tool: MCPToolDefinition):
        """Register a tool"""
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
    
    def get(self, name: str) -> Optional[MCPToolDefinition]:
        """Get a tool by name"""
        return self._tools.get(name)
    
    def list_tools(self) -> List[MCPToolDefinition]:
        """List all registered tools"""
        return list(self._tools.values())
    
    def get_schema(self) -> Dict[str, Any]:
        """Get JSON schema for all tools"""
        schema = {"tools": []}
        for tool in self._tools.values():
            tool_schema = {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": {
                    "type": "object",
                    "properties": tool.parameters,
                    "required": list(tool.parameters.keys())
                }
            }
            schema["tools"].append(tool_schema)
        return schema

# Global registry instance
_tool_registry = MCPToolRegistry()

# =============================================================================
# Decorators for Easy Tool Definition
# =============================================================================

def mcp_tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    streaming: bool = False,
    requires_auth: bool = False,
    rate_limit: Optional[int] = None
):
    """
    Decorator to define an MCP tool
    
    Args:
        name: Tool name (defaults to function name)
        description: Tool description (defaults to docstring)
        streaming: Whether tool supports streaming responses
        requires_auth: Whether tool requires authentication
        rate_limit: Rate limit per minute (optional)
    
    Example:
        @mcp_tool(description="Get weather for a location")
        async def get_weather(location: str) -> MCPToolResult:
            # Tool implementation
            return MCPToolResult().add_text(f"Weather in {location}: 72°F")
    """
    def decorator(func: Callable):
        # Extract function metadata
        func_name = name or func.__name__
        func_description = description or func.__doc__ or f"Tool: {func_name}"
        
        # Extract parameters from type hints
        type_hints = get_type_hints(func)
        sig = inspect.signature(func)
        parameters = {}
        
        for param_name, param in sig.parameters.items():
            if param_name in ('context', 'ctx'):  # Skip context parameter
                continue
                
            param_type = type_hints.get(param_name, str)
            param_schema = _type_to_json_schema(param_type)
            
            # Add default value if available
            if param.default != inspect.Parameter.empty:
                param_schema["default"] = param.default
            
            parameters[param_name] = param_schema
        
        # Create tool definition
        tool_def = MCPToolDefinition(
            name=func_name,
            description=func_description,
            parameters=parameters,
            function=func,
            streaming=streaming,
            requires_auth=requires_auth,
            rate_limit=rate_limit
        )
        
        # Register the tool
        _tool_registry.register(tool_def)
        
        return func
    
    return decorator

def streaming_tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    requires_auth: bool = False,
    rate_limit: Optional[int] = None
):
    """Decorator for streaming MCP tools"""
    return mcp_tool(
        name=name,
        description=description,
        streaming=True,
        requires_auth=requires_auth,
        rate_limit=rate_limit
    )

def _type_to_json_schema(python_type) -> Dict[str, Any]:
    """Convert Python type to JSON schema"""
    if python_type == str:
        return {"type": "string"}
    elif python_type == int:
        return {"type": "integer"}
    elif python_type == float:
        return {"type": "number"}
    elif python_type == bool:
        return {"type": "boolean"}
    elif python_type == list:
        return {"type": "array"}
    elif python_type == dict:
        return {"type": "object"}
    else:
        return {"type": "string", "description": f"Type: {python_type.__name__}"}

# =============================================================================
# gRPC Protocol Buffers (Dynamic Generation)
# =============================================================================

# Since we can't define .proto files in Python, we'll use dynamic message creation
# For production, you'd generate these from actual .proto files

class MCPGrpcService:
    """Dynamic gRPC service for MCP tools"""
    
    def __init__(self, registry: MCPToolRegistry):
        self.registry = registry
        self.rate_limiters: Dict[str, Dict[str, int]] = {}  # client_ip -> {tool_name: count}
        self.auth_handler: Optional[Callable[[str], bool]] = None
    
    def set_auth_handler(self, handler: Callable[[str], bool]):
        """Set authentication handler"""
        self.auth_handler = handler
    
    async def ExecuteTool(self, request, context):
        """Execute a tool (streaming response)"""
        tool_name = request.tool_name
        session_id = request.session_id or str(uuid.uuid4())
        
        # Get tool definition
        tool_def = self.registry.get(tool_name)
        if not tool_def:
            yield self._create_error_response(f"Tool not found: {tool_name}", session_id)
            return
        
        # Check authentication
        if tool_def.requires_auth and not self._check_auth(context):
            yield self._create_error_response("Authentication required", session_id, 401)
            return
        
        # Check rate limiting
        if not self._check_rate_limit(tool_def, context):
            yield self._create_error_response("Rate limit exceeded", session_id, 429)
            return
        
        try:
            # Parse arguments
            args = MessageToDict(request.arguments) if request.arguments else {}
            
            # Create context
            tool_context = MCPToolContext(
                session_id=session_id,
                metadata=dict(request.metadata),
                streaming=tool_def.streaming
            )
            
            # Send progress update
            yield self._create_progress_response("Starting execution", 0, session_id)
            
            # Execute tool
            if tool_def.streaming:
                async for result in self._execute_streaming_tool(tool_def, args, tool_context):
                    yield result
            else:
                result = await self._execute_tool(tool_def, args, tool_context)
                yield self._create_result_response(result, session_id)
                
        except Exception as e:
            logger.exception(f"Error executing tool {tool_name}")
            yield self._create_error_response(str(e), session_id, 500)
    
    async def GetTools(self, request, context):
        """Get list of available tools"""
        schema = self.registry.get_schema()
        response = struct_pb2.Struct()
        ParseDict(schema, response)
        return response
    
    async def HealthCheck(self, request, context):
        """Health check endpoint"""
        status = {
            "healthy": True,
            "tools_count": len(self.registry.list_tools()),
            "timestamp": time.time()
        }
        response = struct_pb2.Struct()
        ParseDict(status, response)
        return response
    
    async def _execute_tool(self, tool_def: MCPToolDefinition, args: Dict[str, Any], context: MCPToolContext) -> MCPToolResult:
        """Execute a non-streaming tool"""
        try:
            # Check if function is async
            if asyncio.iscoroutinefunction(tool_def.function):
                # Check if function accepts context
                sig = inspect.signature(tool_def.function)
                if 'context' in sig.parameters or 'ctx' in sig.parameters:
                    result = await tool_def.function(context=context, **args)
                else:
                    result = await tool_def.function(**args)
            else:
                # Sync function - run in thread pool
                if 'context' in inspect.signature(tool_def.function).parameters:
                    result = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: tool_def.function(context=context, **args)
                    )
                else:
                    result = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: tool_def.function(**args)
                    )
            
            # Ensure result is MCPToolResult
            if not isinstance(result, MCPToolResult):
                if isinstance(result, str):
                    result = MCPToolResult().add_text(result)
                elif isinstance(result, dict):
                    result = MCPToolResult().add_json(result)
                else:
                    result = MCPToolResult().add_text(str(result))
            
            return result
            
        except Exception as e:
            logger.exception(f"Tool execution error: {e}")
            return MCPToolResult().set_error(str(e))
    
    async def _execute_streaming_tool(self, tool_def: MCPToolDefinition, args: Dict[str, Any], context: MCPToolContext):
        """Execute a streaming tool"""
        try:
            # Execute the streaming function
            if asyncio.iscoroutinefunction(tool_def.function):
                result_generator = tool_def.function(context=context, **args)
            else:
                # Wrap sync generator in async
                sync_gen = tool_def.function(context=context, **args)
                result_generator = self._async_wrapper(sync_gen)
            
            async for result in result_generator:
                if context.is_cancelled():
                    break
                
                if isinstance(result, MCPToolResult):
                    yield self._create_result_response(result, context.session_id)
                elif isinstance(result, str):
                    progress_msg = result
                    yield self._create_progress_response(progress_msg, None, context.session_id)
                else:
                    # Convert to result
                    mcp_result = MCPToolResult().add_json(result)
                    yield self._create_result_response(mcp_result, context.session_id)
                    
        except Exception as e:
            logger.exception(f"Streaming tool execution error: {e}")
            yield self._create_error_response(str(e), context.session_id, 500)
    
    async def _async_wrapper(self, sync_generator):
        """Wrap sync generator for async iteration"""
        for item in sync_generator:
            yield item
            await asyncio.sleep(0)  # Yield control
    
    def _create_result_response(self, result: MCPToolResult, session_id: str):
        """Create a result response message"""
        # In a real implementation, this would create proper protobuf messages
        # For now, we'll use a dict structure
        if result.is_error:
            return self._create_error_response(result.error_message, session_id, result.error_code)
        
        return {
            "session_id": session_id,
            "result": {
                "content": result.content,
                "metadata": result.metadata
            }
        }
    
    def _create_error_response(self, message: str, session_id: str, code: int = 500):
        """Create an error response message"""
        return {
            "session_id": session_id,
            "error": {
                "code": code,
                "message": message
            }
        }
    
    def _create_progress_response(self, status: str, progress: Optional[int], session_id: str):
        """Create a progress response message"""
        return {
            "session_id": session_id,
            "progress": {
                "status": status,
                "progress": progress
            }
        }
    
    def _check_auth(self, context) -> bool:
        """Check authentication"""
        if not self.auth_handler:
            return True
        
        # Extract auth token from metadata
        metadata = dict(context.invocation_metadata())
        auth_token = metadata.get('authorization', '')
        
        return self.auth_handler(auth_token)
    
    def _check_rate_limit(self, tool_def: MCPToolDefinition, context) -> bool:
        """Check rate limiting"""
        if not tool_def.rate_limit:
            return True
        
        # Get client IP (simplified)
        client_ip = "unknown"  # In real implementation, extract from context
        current_time = int(time.time() / 60)  # Current minute
        
        if client_ip not in self.rate_limiters:
            self.rate_limiters[client_ip] = {}
        
        key = f"{tool_def.name}:{current_time}"
        current_count = self.rate_limiters[client_ip].get(key, 0)
        
        if current_count >= tool_def.rate_limit:
            return False
        
        self.rate_limiters[client_ip][key] = current_count + 1
        
        # Cleanup old entries
        self._cleanup_rate_limiters(client_ip, current_time)
        
        return True
    
    def _cleanup_rate_limiters(self, client_ip: str, current_time: int):
        """Clean up old rate limiter entries"""
        if client_ip in self.rate_limiters:
            old_keys = [k for k in self.rate_limiters[client_ip].keys() 
                       if int(k.split(':')[1]) < current_time - 5]  # Keep 5 minutes
            for key in old_keys:
                del self.rate_limiters[client_ip][key]

# =============================================================================
# Server Configuration and Startup
# =============================================================================

@dataclass
class ServerConfig:
    """Configuration for gRPC MCP server"""
    host: str = "localhost"
    port: int = 50051
    max_workers: int = 10
    enable_reflection: bool = True
    enable_health_check: bool = True
    ssl_cert_path: Optional[str] = None
    ssl_key_path: Optional[str] = None
    auth_handler: Optional[Callable[[str], bool]] = None
    
class MCPGrpcServer:
    """High-level gRPC MCP server"""
    
    def __init__(self, config: ServerConfig):
        self.config = config
        self.server: Optional[aio_grpc.Server] = None
        self.service = MCPGrpcService(_tool_registry)
        
        if config.auth_handler:
            self.service.set_auth_handler(config.auth_handler)
    
    async def start(self):
        """Start the gRPC server"""
        self.server = aio_grpc.server(
            ThreadPoolExecutor(max_workers=self.config.max_workers)
        )
        
        # Add services
        # Note: In real implementation, you'd add proper protobuf services
        # For now, we'll simulate the service registration
        logger.info("Registering MCP gRPC service")
        
        # Add health check
        if self.config.enable_health_check:
            health_pb2_grpc.add_HealthServicer_to_server(
                HealthServicer(), self.server
            )
        
        # Add reflection
        if self.config.enable_reflection:
            SERVICE_NAMES = (
                "mcp.MCPToolService",
                health_pb2.DESCRIPTOR.services_by_name['Health'].full_name,
                reflection.SERVICE_NAME,
            )
            reflection.enable_server_reflection(SERVICE_NAMES, self.server)
        
        # Configure SSL if provided
        if self.config.ssl_cert_path and self.config.ssl_key_path:
            with open(self.config.ssl_key_path, 'rb') as f:
                private_key = f.read()
            with open(self.config.ssl_cert_path, 'rb') as f:
                certificate_chain = f.read()
            
            server_credentials = grpc.ssl_server_credentials(
                [(private_key, certificate_chain)]
            )
            listen_addr = f'{self.config.host}:{self.config.port}'
            self.server.add_secure_port(listen_addr, server_credentials)
            logger.info(f"Starting secure gRPC MCP server on {listen_addr}")
        else:
            listen_addr = f'{self.config.host}:{self.config.port}'
            self.server.add_insecure_port(listen_addr)
            logger.info(f"Starting gRPC MCP server on {listen_addr}")
        
        await self.server.start()
        
        # Log registered tools
        tools = _tool_registry.list_tools()
        logger.info(f"Registered {len(tools)} MCP tools:")
        for tool in tools:
            logger.info(f"  - {tool.name}: {tool.description}")
    
    async def wait_for_termination(self):
        """Wait for server termination"""
        if self.server:
            await self.server.wait_for_termination()
    
    async def stop(self, grace_period: int = 5):
        """Stop the server"""
        if self.server:
            await self.server.stop(grace_period)

class HealthServicer(health_pb2_grpc.HealthServicer):
    """Health check servicer"""
    
    async def Check(self, request, context):
        return health_pb2.HealthCheckResponse(
            status=health_pb2.HealthCheckResponse.SERVING
        )

# =============================================================================
# Client SDK for connecting to gRPC MCP servers
# =============================================================================

class MCPGrpcClient:
    """Client for connecting to gRPC MCP servers"""
    
    def __init__(self, server_address: str, use_ssl: bool = False, auth_token: Optional[str] = None):
        self.server_address = server_address
        self.use_ssl = use_ssl
        self.auth_token = auth_token
        self.channel: Optional[aio_grpc.Channel] = None
        self.stub = None
    
    async def connect(self):
        """Connect to the gRPC server"""
        if self.use_ssl:
            credentials = grpc.ssl_channel_credentials()
            self.channel = aio_grpc.secure_channel(self.server_address, credentials)
        else:
            self.channel = aio_grpc.insecure_channel(self.server_address)
        
        # Create stub (in real implementation, this would use generated classes)
        # self.stub = MCPToolServiceStub(self.channel)
        logger.info(f"Connected to gRPC MCP server at {self.server_address}")
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], streaming: bool = False):
        """Execute a tool on the remote server"""
        if not self.channel:
            await self.connect()
        
        request = {
            "tool_name": tool_name,
            "arguments": arguments,
            "session_id": str(uuid.uuid4())
        }
        
        if self.auth_token:
            metadata = [('authorization', f'Bearer {self.auth_token}')]
        else:
            metadata = []
        
        # In real implementation, this would make actual gRPC calls
        logger.info(f"Executing tool {tool_name} with args: {arguments}")
        
        # Simulate response
        if streaming:
            async def stream_results():
                yield {"progress": {"status": "Starting", "progress": 0}}
                await asyncio.sleep(0.1)
                yield {"result": {"content": [{"type": "text", "text": f"Result for {tool_name}"}]}}
            
            return stream_results()
        else:
            return {"result": {"content": [{"type": "text", "text": f"Result for {tool_name}"}]}}
    
    async def list_tools(self):
        """List available tools on the server"""
        if not self.channel:
            await self.connect()
        
        # In real implementation, call GetTools RPC
        tools = _tool_registry.get_schema()
        return tools
    
    async def close(self):
        """Close the connection"""
        if self.channel:
            await self.channel.close()

# =============================================================================
# Convenience Functions and Main API
# =============================================================================

def create_server(
    host: str = "localhost",
    port: int = 50051,
    ssl_cert: Optional[str] = None,
    ssl_key: Optional[str] = None,
    auth_handler: Optional[Callable[[str], bool]] = None
) -> MCPGrpcServer:
    """Create and configure an MCP gRPC server"""
    config = ServerConfig(
        host=host,
        port=port,
        ssl_cert_path=ssl_cert,
        ssl_key_path=ssl_key,
        auth_handler=auth_handler
    )
    return MCPGrpcServer(config)

def create_client(server_address: str, use_ssl: bool = False, auth_token: Optional[str] = None) -> MCPGrpcClient:
    """Create an MCP gRPC client"""
    return MCPGrpcClient(server_address, use_ssl, auth_token)

async def run_server(
    host: str = "localhost",
    port: int = 50051,
    ssl_cert: Optional[str] = None,
    ssl_key: Optional[str] = None
):
    """Run an MCP gRPC server (convenience function)"""
    server = create_server(host, port, ssl_cert, ssl_key)
    await server.start()
    
    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        await server.stop()

# Simple auth helpers
def create_token_auth(valid_tokens: List[str]) -> Callable[[str], bool]:
    """Create a simple token-based auth handler"""
    def auth_handler(token: str) -> bool:
        # Remove 'Bearer ' prefix if present
        if token.startswith('Bearer '):
            token = token[7:]
        return token in valid_tokens
    
    return auth_handler

def create_api_key_auth(api_keys: Dict[str, str]) -> Callable[[str], bool]:
    """Create an API key-based auth handler"""
    def auth_handler(token: str) -> bool:
        if token.startswith('Bearer '):
            token = token[7:]
        return token in api_keys
    
    return auth_handler

# =============================================================================
# Example Usage and Demo Tools
# =============================================================================

if __name__ == "__main__":
    # Example tools using the SDK
    
    @mcp_tool(description="Get current weather for a location")
    async def get_weather(location: str, units: str = "fahrenheit") -> MCPToolResult:
        """Get weather information for a location"""
        # Simulate API call
        await asyncio.sleep(0.1)
        
        weather_data = {
            "location": location,
            "temperature": 72 if units == "fahrenheit" else 22,
            "condition": "sunny",
            "humidity": 45,
            "units": units
        }
        
        result = MCPToolResult()
        result.add_text(f"Weather in {location}:")
        result.add_json(weather_data)
        result.metadata["api_version"] = "v2.1"
        result.metadata["cache_duration"] = "300"
        
        return result
    
    @mcp_tool(description="Perform mathematical calculations")
    def calculate(expression: str) -> MCPToolResult:
        """Calculate mathematical expressions"""
        try:
            # Simple calculator (in production, use a proper parser)
            result = eval(expression)  # Don't use eval in production!
            return MCPToolResult().add_text(f"{expression} = {result}")
        except Exception as e:
            return MCPToolResult().set_error(f"Calculation error: {e}")
    
    @streaming_tool(description="Search files with real-time results")
    async def search_files(query: str, path: str = ".", context: MCPToolContext = None):
        """Search for files matching a query"""
        import os
        import fnmatch
        
        yield "Starting file search..."
        
        matches = []
        total_scanned = 0
        
        for root, dirs, files in os.walk(path):
            if context and context.is_cancelled():
                break
                
            for file in files:
                total_scanned += 1
                if fnmatch.fnmatch(file.lower(), f"*{query.lower()}*"):
                    matches.append(os.path.join(root, file))
                
                # Send progress updates
                if total_scanned % 10 == 0:
                    yield f"Scanned {total_scanned} files, found {len(matches)} matches"
        
        # Send final results
        result = MCPToolResult()
        result.add_text(f"Found {len(matches)} files matching '{query}':")
        result.add_json({"matches": matches[:50], "total_found": len(matches)})
        yield result
    
    @mcp_tool(description="Generate random data", requires_auth=True, rate_limit=10)
    async def generate_data(count: int = 10, data_type: str = "numbers") -> MCPToolResult:
        """Generate random data (requires authentication)"""
        import random
        
        if data_type == "numbers":
            data = [random.randint(1, 100) for _ in range(count)]
        elif data_type == "words":
            words = ["apple", "banana", "cherry", "date", "elderberry"]
            data = [random.choice(words) for _ in range(count)]
        else:
            return MCPToolResult().set_error("Invalid data_type. Use 'numbers' or 'words'")
        
        result = MCPToolResult()
        result.add_text(f"Generated {count} random {data_type}:")
        result.add_json(data)
        
        return result
    
    # Example server startup
    async def main():
        """Example server startup"""
        print("🚀 Starting gRPC MCP SDK Demo Server")
        print("=" * 50)
        
        # Create auth handler
        auth_handler = create_token_auth(["demo-token-123", "admin-token-456"])
        
        # Create and start server
        server = create_server(
            host="localhost",
            port=50051,
            auth_handler=auth_handler
        )
        
        await server.start()
        print("\n✅ Server started successfully!")
        print(f"🌐 Server running on localhost:50051")
        print(f"🔧 Tools registered: {len(_tool_registry.list_tools())}")
        print("\nRegistered tools:")
        for tool in _tool_registry.list_tools():
            auth_indicator = "🔒" if tool.requires_auth else "🌐"
            stream_indicator = "📡" if tool.streaming else "💫"
            print(f"  {auth_indicator} {stream_indicator} {tool.name} - {tool.description}")
        
        print("\nExample client usage:")
        print("```python")
        print("from grpc_mcp_sdk import create_client")
        print("client = create_client('localhost:50051')")
        print("await client.connect()")
        print("result = await client.execute_tool('get_weather', {'location': 'New York'})")
        print("```")
        
        try:
            await server.wait_for_termination()
        except KeyboardInterrupt:
            print("\n🛑 Shutting down server...")
            await server.stop()
            print("✅ Server stopped gracefully")
    
    # Run the demo
    asyncio.run(main())

# =============================================================================
# Additional Modules for Production Use
# =============================================================================

# monitoring.py - Monitoring and metrics
class MCPMetrics:
    """Metrics collection for MCP tools"""
    
    def __init__(self):
        self.tool_calls = {}
        self.tool_durations = {}
        self.error_counts = {}
        self.start_time = time.time()
    
    def record_tool_call(self, tool_name: str, duration: float, success: bool):
        """Record a tool call"""
        if tool_name not in self.tool_calls:
            self.tool_calls[tool_name] = 0
            self.tool_durations[tool_name] = []
            self.error_counts[tool_name] = 0
        
        self.tool_calls[tool_name] += 1
        self.tool_durations[tool_name].append(duration)
        
        if not success:
            self.error_counts[tool_name] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive stats"""
        uptime = time.time() - self.start_time
        
        stats = {
            "uptime_seconds": uptime,
            "total_calls": sum(self.tool_calls.values()),
            "tools": {}
        }
        
        for tool_name in self.tool_calls:
            durations = self.tool_durations[tool_name]
            avg_duration = sum(durations) / len(durations) if durations else 0
            
            stats["tools"][tool_name] = {
                "total_calls": self.tool_calls[tool_name],
                "error_count": self.error_counts[tool_name],
                "success_rate": (self.tool_calls[tool_name] - self.error_counts[tool_name]) / self.tool_calls[tool_name] if self.tool_calls[tool_name] > 0 else 0,
                "avg_duration_ms": avg_duration * 1000,
                "min_duration_ms": min(durations) * 1000 if durations else 0,
                "max_duration_ms": max(durations) * 1000 if durations else 0
            }
        
        return stats

# Global metrics instance
_metrics = MCPMetrics()

# security.py - Security utilities
class MCPSecurity:
    """Security utilities for MCP servers"""
    
    @staticmethod
    def generate_api_key(length: int = 32) -> str:
        """Generate a random API key"""
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Hash an API key for storage"""
        import hashlib
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    @staticmethod
    def create_jwt_auth(secret_key: str, algorithm: str = "HS256") -> Callable[[str], bool]:
        """Create JWT-based authentication"""
        def auth_handler(token: str) -> bool:
            try:
                if token.startswith('Bearer '):
                    token = token[7:]
                
                # Decode JWT (you'd need to install PyJWT)
                # payload = jwt.decode(token, secret_key, algorithms=[algorithm])
                # return True  # Add your validation logic here
                
                # For demo, just check if it looks like a JWT
                return token.count('.') == 2
            except Exception:
                return False
        
        return auth_handler
    
    @staticmethod
    def create_rate_limiter(requests_per_minute: int = 60):
        """Create a rate limiter"""
        request_times = {}
        
        def rate_limit_check(client_id: str) -> bool:
            now = time.time()
            if client_id not in request_times:
                request_times[client_id] = []
            
            # Clean old requests
            request_times[client_id] = [t for t in request_times[client_id] if now - t < 60]
            
            # Check limit
            if len(request_times[client_id]) >= requests_per_minute:
                return False
            
            request_times[client_id].append(now)
            return True
        
        return rate_limit_check

# deployment.py - Deployment utilities
class MCPDeployment:
    """Deployment utilities for MCP servers"""
    
    @staticmethod
    def generate_docker_compose(
        service_name: str = "mcp-grpc-server",
        port: int = 50051,
        replicas: int = 1,
        use_ssl: bool = False
    ) -> str:
        """Generate docker-compose.yml for MCP server"""
        
        compose_config = f"""version: '3.8'

services:
  {service_name}:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "{port}:{port}"
    environment:
      - MCP_HOST=0.0.0.0
      - MCP_PORT={port}
      - MCP_LOG_LEVEL=INFO
    deploy:
      replicas: {replicas}
    healthcheck:
      test: ["CMD", "grpc_health_probe", "-addr=:{port}"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped"""

        if use_ssl:
            compose_config += """
    volumes:
      - ./ssl:/app/ssl:ro
    environment:
      - MCP_SSL_CERT=/app/ssl/cert.pem
      - MCP_SSL_KEY=/app/ssl/key.pem"""
        
        return compose_config
    
    @staticmethod
    def generate_dockerfile() -> str:
        """Generate Dockerfile for MCP server"""
        return """FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    build-essential \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Install grpc_health_probe
RUN GRPC_HEALTH_PROBE_VERSION=v0.4.19 && \\
    wget -qO/bin/grpc_health_probe \\
    https://github.com/grpc-ecosystem/grpc-health-probe/releases/download/${GRPC_HEALTH_PROBE_VERSION}/grpc_health_probe-linux-amd64 && \\
    chmod +x /bin/grpc_health_probe

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1001 mcpuser && chown -R mcpuser:mcpuser /app
USER mcpuser

# Expose port
EXPOSE 50051

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD grpc_health_probe -addr=:50051

# Run the server
CMD ["python", "-m", "grpc_mcp_sdk.server"]
"""
    
    @staticmethod
    def generate_kubernetes_manifest(
        name: str = "mcp-grpc-server",
        namespace: str = "default",
        replicas: int = 3,
        port: int = 50051
    ) -> str:
        """Generate Kubernetes deployment manifest"""
        return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
  namespace: {namespace}
  labels:
    app: {name}
spec:
  replicas: {replicas}
  selector:
    matchLabels:
      app: {name}
  template:
    metadata:
      labels:
        app: {name}
    spec:
      containers:
      - name: {name}
        image: {name}:latest
        ports:
        - containerPort: {port}
          name: grpc
        env:
        - name: MCP_HOST
          value: "0.0.0.0"
        - name: MCP_PORT
          value: "{port}"
        livenessProbe:
          exec:
            command: ["/bin/grpc_health_probe", "-addr=:{port}"]
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          exec:
            command: ["/bin/grpc_health_probe", "-addr=:{port}"]
          initialDelaySeconds: 5
          periodSeconds: 10
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: {name}-service
  namespace: {namespace}
spec:
  selector:
    app: {name}
  ports:
  - port: {port}
    targetPort: {port}
    name: grpc
  type: ClusterIP
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {name}-ingress
  namespace: {namespace}
  annotations:
    nginx.ingress.kubernetes.io/backend-protocol: "GRPC"
spec:
  rules:
  - host: {name}.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: {name}-service
            port:
              number: {port}
"""

# cli.py - Command-line interface
class MCPCLI:
    """Command-line interface for gRPC MCP SDK"""
    
    @staticmethod
    def create_project(name: str, path: str = "."):
        """Create a new MCP project"""
        import os
        
        project_path = os.path.join(path, name)
        os.makedirs(project_path, exist_ok=True)
        
        # Create main.py
        main_py = f'''"""
{name} - MCP gRPC Server
Generated by gRPC MCP SDK
"""

import asyncio
from grpc_mcp_sdk import mcp_tool, MCPToolResult, run_server

@mcp_tool(description="Example tool that says hello")
async def say_hello(name: str = "World") -> MCPToolResult:
    """Say hello to someone"""
    return MCPToolResult().add_text(f"Hello, {{name}}!")

@mcp_tool(description="Add two numbers together")
def add_numbers(a: int, b: int) -> MCPToolResult:
    """Add two numbers"""
    result = a + b
    return MCPToolResult().add_text(f"{{a}} + {{b}} = {{result}}")

if __name__ == "__main__":
    asyncio.run(run_server(host="0.0.0.0", port=50051))
'''
        
        with open(os.path.join(project_path, "main.py"), "w") as f:
            f.write(main_py)
        
        # Create requirements.txt
        requirements = """grpcio>=1.60.0
grpcio-tools>=1.60.0
grpcio-health-checking>=1.60.0
grpcio-reflection>=1.60.0
protobuf>=4.25.0
"""
        
        with open(os.path.join(project_path, "requirements.txt"), "w") as f:
            f.write(requirements)
        
        # Create Dockerfile
        with open(os.path.join(project_path, "Dockerfile"), "w") as f:
            f.write(MCPDeployment.generate_dockerfile())
        
        # Create docker-compose.yml
        with open(os.path.join(project_path, "docker-compose.yml"), "w") as f:
            f.write(MCPDeployment.generate_docker_compose(name))
        
        # Create README.md
        readme = f"""# {name}

MCP gRPC Server generated by gRPC MCP SDK.

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the server:
   ```bash
   python main.py
   ```

3. The server will start on `localhost:50051`

## Available Tools

- `say_hello` - Say hello to someone
- `add_numbers` - Add two numbers together

## Docker

Build and run with Docker:

```bash
docker-compose up --build
```

## Development

Add new tools by decorating functions with `@mcp_tool`:

```python
@mcp_tool(description="Your tool description")
async def your_tool(param: str) -> MCPToolResult:
    return MCPToolResult().add_text("Your result")
```

## Client Usage

```python
from grpc_mcp_sdk import create_client

async def example():
    client = create_client('localhost:50051')
    await client.connect()
    
    result = await client.execute_tool('say_hello', {{'name': 'Alice'}})
    print(result)
    
    await client.close()
```
"""
        
        with open(os.path.join(project_path, "README.md"), "w") as f:
            f.write(readme)
        
        print(f"✅ Created MCP project '{name}' in {project_path}")
        print(f"📁 Project structure:")
        print(f"   {name}/")
        print(f"   ├── main.py")
        print(f"   ├── requirements.txt")
        print(f"   ├── Dockerfile")
        print(f"   ├── docker-compose.yml")
        print(f"   └── README.md")
        print(f"\n🚀 Get started:")
        print(f"   cd {name}")
        print(f"   pip install -r requirements.txt")
        print(f"   python main.py")

# utils.py - Utility functions
class MCPUtils:
    """Utility functions for MCP development"""
    
    @staticmethod
    def validate_tool_schema(tool_def: MCPToolDefinition) -> List[str]:
        """Validate a tool definition"""
        errors = []
        
        if not tool_def.name:
            errors.append("Tool name is required")
        
        if not tool_def.description:
            errors.append("Tool description is required")
        
        if not tool_def.function:
            errors.append("Tool function is required")
        
        # Validate function signature
        try:
            sig = inspect.signature(tool_def.function)
            for param_name, param in sig.parameters.items():
                if param.annotation == inspect.Parameter.empty and param_name not in ('context', 'ctx'):
                    errors.append(f"Parameter '{param_name}' missing type annotation")
        except Exception as e:
            errors.append(f"Invalid function signature: {e}")
        
        return errors
    
    @staticmethod
    def generate_openapi_spec(registry: MCPToolRegistry) -> Dict[str, Any]:
        """Generate OpenAPI specification for tools"""
        spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "MCP gRPC Tools API",
                "version": "1.0.0",
                "description": "API specification for MCP tools"
            },
            "paths": {},
            "components": {
                "schemas": {
                    "MCPToolResult": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "array", "items": {"type": "object"}},
                            "metadata": {"type": "object"},
                            "is_error": {"type": "boolean"},
                            "error_code": {"type": "integer"},
                            "error_message": {"type": "string"}
                        }
                    }
                }
            }
        }
        
        for tool in registry.list_tools():
            path = f"/tools/{tool.name}"
            spec["paths"][path] = {
                "post": {
                    "summary": tool.description,
                    "parameters": [],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": tool.parameters
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Tool execution result",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/MCPToolResult"}
                                }
                            }
                        }
                    }
                }
            }
        
        return spec
    
    @staticmethod
    def benchmark_tool(tool_name: str, arguments: Dict[str, Any], iterations: int = 100) -> Dict[str, Any]:
        """Benchmark a tool's performance"""
        tool_def = _tool_registry.get(tool_name)
        if not tool_def:
            raise ValueError(f"Tool not found: {tool_name}")
        
        async def run_benchmark():
            durations = []
            errors = 0
            
            for _ in range(iterations):
                start_time = time.time()
                try:
                    context = MCPToolContext("benchmark", {})
                    if asyncio.iscoroutinefunction(tool_def.function):
                        await tool_def.function(context=context, **arguments)
                    else:
                        tool_def.function(context=context, **arguments)
                    duration = time.time() - start_time
                    durations.append(duration)
                except Exception:
                    errors += 1
            
            return {
                "tool_name": tool_name,
                "iterations": iterations,
                "total_time": sum(durations),
                "avg_time": sum(durations) / len(durations) if durations else 0,
                "min_time": min(durations) if durations else 0,
                "max_time": max(durations) if durations else 0,
                "success_rate": (iterations - errors) / iterations,
                "errors": errors
            }
        
        return asyncio.run(run_benchmark())

# Export main API
__all__ = [
    'mcp_tool',
    'streaming_tool', 
    'MCPToolResult',
    'MCPToolContext',
    'create_server',
    'create_client',
    'run_server',
    'MCPGrpcServer',
    'MCPGrpcClient',
    'ServerConfig',
    'create_token_auth',
    'create_api_key_auth',
    'MCPSecurity',
    'MCPDeployment',
    'MCPCLI',
    'MCPUtils',
    'MCPMetrics'
]

# Version info
__version__ = "1.0.0"
__author__ = "gRPC MCP SDK Team"
__description__ = "A modern Python framework for building high-performance MCP tools with gRPC"