"""Core gRPC server implementation for MCP."""

import asyncio
import grpc
from concurrent import futures
from typing import Dict, List, Optional, Any
import logging
import time

from ..proto import mcp_pb2, mcp_pb2_grpc
from .registry import ToolRegistry
from .types import MCPToolResult, ExecutionContext
from ..utils.errors import MCPError, ErrorCode
from ..auth.base import AuthHandler, NoAuthHandler
from ..auth.middleware import AuthMiddleware

logger = logging.getLogger(__name__)


class MCPServicer(mcp_pb2_grpc.MCPServiceServicer):
    """Main gRPC service implementation for MCP."""
    
    def __init__(
        self, 
        server_name: str = "gRPC-MCP-Server", 
        version: str = "1.0.0",
        auth_handler: Optional[AuthHandler] = None
    ):
        self.server_name = server_name
        self.version = version
        self.registry = ToolRegistry.global_registry()
        self.auth_middleware = AuthMiddleware(auth_handler or NoAuthHandler())
        self.capabilities = {
            "tools": "true",
            "streaming": "true",
            "auth": "true" if auth_handler else "false",
            "rate_limiting": "true"
        }
    
    async def Initialize(self, request, context):
        """Handle MCP initialization handshake."""
        logger.info(f"Client initialization: {request.client_info.name} v{request.client_info.version}")
        
        # Validate protocol version
        if not request.protocol_version.startswith("1."):
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, 
                         f"Unsupported protocol version: {request.protocol_version}")
        
        return mcp_pb2.InitializeResponse(
            protocol_version="1.0",
            server_info=mcp_pb2.ServerInfo(
                name=self.server_name,
                version=self.version
            ),
            capabilities=self.capabilities
        )
    
    async def ListTools(self, request, context):
        """List available tools with optional filtering."""
        try:
            tools = self.registry.list_tools(filter_str=request.filter)
            
            tool_definitions = []
            for tool in tools:
                params = []
                for param_name, param_info in tool.parameters.items():
                    params.append(mcp_pb2.Parameter(
                        name=param_name,
                        type=param_info["type"],
                        required=param_info.get("required", False),
                        description=param_info.get("description", "")
                    ))
                
                tool_definitions.append(mcp_pb2.ToolDefinition(
                    name=tool.name,
                    description=tool.description,
                    parameters=params,
                    supports_streaming=tool.supports_streaming,
                    metadata=tool.metadata
                ))
            
            return mcp_pb2.ListToolsResponse(tools=tool_definitions)
            
        except Exception as e:
            logger.exception("Error listing tools")
            context.abort(grpc.StatusCode.INTERNAL, str(e))
    
    async def ExecuteTool(self, request, context):
        """Execute a tool and return the result."""
        start_time = time.time()
        
        try:
            # Authenticate request
            auth_context = await self.auth_middleware.authenticate_request(context)
            
            # Check tool permissions
            tool = self.registry.get_tool(request.tool_name)
            if tool and tool.requires_auth:
                if not self.auth_middleware.check_tool_permissions(
                    auth_context, request.tool_name, tool.metadata.get('required_permissions', [])
                ):
                    raise MCPError(
                        ErrorCode.AUTH_REQUIRED,
                        "Insufficient permissions for this tool"
                    )
            
            # Convert protobuf Struct to dict
            arguments = self._struct_to_dict(request.arguments)
            
            # Create execution context
            exec_context = ExecutionContext(
                request_id=request.request_id,
                user_id=auth_context.user_id,
                metadata=dict(request.context)
            )
            
            # Execute tool
            result = await self.registry.execute_tool(
                request.tool_name,
                arguments,
                exec_context
            )
            
            execution_time = int((time.time() - start_time) * 1000)
            
            # Convert result to protobuf
            pb_result = self._convert_result_to_pb(result)
            
            return mcp_pb2.ExecuteToolResponse(
                success=pb_result,
                request_id=request.request_id,
                execution_time_ms=execution_time
            )
            
        except MCPError as e:
            execution_time = int((time.time() - start_time) * 1000)
            return mcp_pb2.ExecuteToolResponse(
                error=mcp_pb2.ToolError(
                    code=e.code,
                    message=e.message,
                    details=self._dict_to_struct(e.details)
                ),
                request_id=request.request_id,
                execution_time_ms=execution_time
            )
        except Exception as e:
            logger.exception(f"Tool execution failed: {request.tool_name}")
            execution_time = int((time.time() - start_time) * 1000)
            return mcp_pb2.ExecuteToolResponse(
                error=mcp_pb2.ToolError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=str(e)
                ),
                request_id=request.request_id,
                execution_time_ms=execution_time
            )
    
    async def StreamTool(self, request, context):
        """Execute a streaming tool and yield results."""
        try:
            # Authenticate request
            auth_context = await self.auth_middleware.authenticate_request(context)
            
            # Check tool permissions
            tool = self.registry.get_tool(request.tool_name)
            if tool and tool.requires_auth:
                if not self.auth_middleware.check_tool_permissions(
                    auth_context, request.tool_name, tool.metadata.get('required_permissions', [])
                ):
                    raise MCPError(
                        ErrorCode.AUTH_REQUIRED,
                        "Insufficient permissions for this tool"
                    )
            
            # Convert protobuf Struct to dict
            arguments = self._struct_to_dict(request.arguments)
            
            # Create execution context
            exec_context = ExecutionContext(
                request_id=request.request_id,
                user_id=auth_context.user_id,
                metadata=dict(request.context)
            )
            
            # Stream from tool
            async for update in self.registry.stream_tool(
                request.tool_name,
                arguments,
                exec_context
            ):
                if isinstance(update, MCPToolResult):
                    # It's a result
                    yield mcp_pb2.StreamToolResponse(
                        partial_result=self._convert_result_to_pb(update),
                        request_id=request.request_id
                    )
                elif isinstance(update, dict) and "progress" in update:
                    # It's a progress update
                    yield mcp_pb2.StreamToolResponse(
                        progress=mcp_pb2.ToolProgress(
                            progress=update["progress"],
                            message=update.get("message", "")
                        ),
                        request_id=request.request_id
                    )
                elif isinstance(update, str):
                    # Simple text update
                    result = MCPToolResult()
                    result.add_text(update)
                    yield mcp_pb2.StreamToolResponse(
                        partial_result=self._convert_result_to_pb(result),
                        request_id=request.request_id
                    )
                else:
                    # Try to convert to MCPToolResult
                    result = MCPToolResult()
                    if isinstance(update, dict):
                        result.add_json(update)
                    else:
                        result.add_text(str(update))
                    yield mcp_pb2.StreamToolResponse(
                        partial_result=self._convert_result_to_pb(result),
                        request_id=request.request_id
                    )
                
        except Exception as e:
            logger.exception(f"Streaming tool failed: {request.tool_name}")
            yield mcp_pb2.StreamToolResponse(
                error=mcp_pb2.ToolError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=str(e)
                ),
                request_id=request.request_id
            )
    
    async def HealthCheck(self, request, context):
        """Health check endpoint."""
        try:
            component_health = {
                "registry": self.registry.is_healthy(),
                "server": True
            }
            
            return mcp_pb2.HealthCheckResponse(
                healthy=all(component_health.values()),
                component_health=component_health
            )
        except Exception as e:
            logger.exception("Health check failed")
            return mcp_pb2.HealthCheckResponse(
                healthy=False,
                component_health={"server": False, "registry": False}
            )
    
    def _struct_to_dict(self, struct):
        """Convert protobuf Struct to Python dict."""
        from google.protobuf.json_format import MessageToDict
        return MessageToDict(struct)
    
    def _dict_to_struct(self, d):
        """Convert Python dict to protobuf Struct."""
        from google.protobuf.struct_pb2 import Struct
        from google.protobuf.json_format import ParseDict
        struct = Struct()
        if d:
            ParseDict(d, struct)
        return struct
    
    def _convert_result_to_pb(self, result: MCPToolResult):
        """Convert MCPToolResult to protobuf ToolResult."""
        pb_contents = []
        
        for content in result.content:
            if content["type"] == "text":
                pb_contents.append(mcp_pb2.Content(
                    text=mcp_pb2.TextContent(text=content["text"])
                ))
            elif content["type"] == "json":
                pb_contents.append(mcp_pb2.Content(
                    json=mcp_pb2.JsonContent(
                        data=self._dict_to_struct(content["data"])
                    )
                ))
            elif content["type"] == "binary":
                pb_contents.append(mcp_pb2.Content(
                    binary=mcp_pb2.BinaryContent(
                        data=content["data"],
                        mime_type=content.get("mime_type", "application/octet-stream")
                    )
                ))
        
        return mcp_pb2.ToolResult(
            content=pb_contents,
            metadata=result.metadata
        )


async def create_server(
    host: str = "0.0.0.0",
    port: int = 50051,
    max_workers: int = 10,
    server_name: str = "gRPC-MCP-Server",
    version: str = "1.0.0",
    auth_handler: Optional[AuthHandler] = None
) -> tuple[grpc.aio.Server, MCPServicer]:
    """Create and configure the gRPC server."""
    server = grpc.aio.server(
        futures.ThreadPoolExecutor(max_workers=max_workers),
        options=[
            ('grpc.max_receive_message_length', 100 * 1024 * 1024),  # 100MB
            ('grpc.max_send_message_length', 100 * 1024 * 1024),
            ('grpc.keepalive_time_ms', 30000),
            ('grpc.keepalive_timeout_ms', 10000),
        ]
    )
    
    servicer = MCPServicer(server_name=server_name, version=version, auth_handler=auth_handler)
    mcp_pb2_grpc.add_MCPServiceServicer_to_server(servicer, server)
    
    server.add_insecure_port(f"{host}:{port}")
    
    return server, servicer


async def run_server(
    host: str = "0.0.0.0",
    port: int = 50051,
    server_name: str = "gRPC-MCP-Server",
    version: str = "1.0.0",
    auth_handler: Optional[AuthHandler] = None
):
    """Run the gRPC server."""
    server, servicer = await create_server(host, port, server_name=server_name, version=version, auth_handler=auth_handler)
    
    await server.start()
    logger.info(f"gRPC-MCP server started on {host}:{port}")
    logger.info(f"Registered tools: {len(servicer.registry.tools)}")
    
    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        await server.stop(grace_period=5)
        logger.info("Server stopped")