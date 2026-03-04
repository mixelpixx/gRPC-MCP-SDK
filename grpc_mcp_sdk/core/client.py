"""gRPC MCP Client implementation."""

import grpc
from typing import Dict, Any, Optional, AsyncGenerator, List
import logging
import asyncio

from ..proto import mcp_pb2, mcp_pb2_grpc
from .types import MCPToolResult, ToolDefinition, ToolParameter
from ..utils.errors import MCPError, ErrorCode

logger = logging.getLogger(__name__)


class MCPClient:
    """gRPC MCP Client for connecting to MCP servers."""
    
    def __init__(self, server_address: str, secure: bool = False):
        self.server_address = server_address
        self.secure = secure
        self.channel = None
        self.stub = None
        self.connected = False
        
    async def connect(self) -> None:
        """Connect to the MCP server."""
        if self.secure:
            self.channel = grpc.aio.secure_channel(
                self.server_address,
                grpc.ssl_channel_credentials()
            )
        else:
            self.channel = grpc.aio.insecure_channel(self.server_address)
        
        self.stub = mcp_pb2_grpc.MCPServiceStub(self.channel)
        
        # Initialize connection
        await self._initialize()
        self.connected = True
        logger.info(f"Connected to MCP server at {self.server_address}")
    
    async def _initialize(self) -> None:
        """Initialize connection with server."""
        request = mcp_pb2.InitializeRequest(
            protocol_version="1.0",
            client_info=mcp_pb2.ClientInfo(
                name="gRPC-MCP-Client",
                version="1.0.0"
            ),
            capabilities={
                "tools": "true",
                "streaming": "true"
            }
        )
        
        try:
            response = await self.stub.Initialize(request)
            logger.info(f"Server: {response.server_info.name} v{response.server_info.version}")
            logger.info(f"Server capabilities: {dict(response.capabilities)}")
        except grpc.RpcError as e:
            raise MCPError(ErrorCode.INTERNAL_ERROR, f"Failed to initialize: {e}")
    
    async def list_tools(self, filter_str: Optional[str] = None) -> List[ToolDefinition]:
        """List available tools on the server."""
        if not self.connected:
            raise MCPError(ErrorCode.INVALID_REQUEST, "Not connected to server")
        
        request = mcp_pb2.ListToolsRequest(filter=filter_str or "")
        
        try:
            response = await self.stub.ListTools(request)
            tools = []
            
            for tool_def in response.tools:
                parameters = []
                for param in tool_def.parameters:
                    parameters.append(ToolParameter(
                        name=param.name,
                        type=param.type,
                        required=param.required,
                        description=param.description
                    ))
                
                tools.append(ToolDefinition(
                    name=tool_def.name,
                    description=tool_def.description,
                    parameters=parameters,
                    supports_streaming=tool_def.supports_streaming,
                    metadata=dict(tool_def.metadata)
                ))
            
            return tools
            
        except grpc.RpcError as e:
            raise MCPError(ErrorCode.INTERNAL_ERROR, f"Failed to list tools: {e}")
    
    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Optional[Dict[str, str]] = None,
        request_id: Optional[str] = None
    ) -> MCPToolResult:
        """Execute a tool on the server."""
        if not self.connected:
            raise MCPError(ErrorCode.INVALID_REQUEST, "Not connected to server")
        
        # Convert arguments to protobuf Struct
        from google.protobuf.struct_pb2 import Struct
        from google.protobuf.json_format import ParseDict
        
        args_struct = Struct()
        ParseDict(arguments, args_struct)
        
        request = mcp_pb2.ExecuteToolRequest(
            tool_name=tool_name,
            arguments=args_struct,
            context=context or {},
            request_id=request_id or f"req_{asyncio.current_task().get_name()}"
        )
        
        try:
            response = await self.stub.ExecuteTool(request)
            
            if response.HasField("error"):
                error = response.error
                raise MCPError(error.code, error.message)
            
            return self._convert_pb_to_result(response.success)
            
        except grpc.RpcError as e:
            raise MCPError(ErrorCode.INTERNAL_ERROR, f"Failed to execute tool: {e}")
    
    async def stream_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Optional[Dict[str, str]] = None,
        request_id: Optional[str] = None
    ) -> AsyncGenerator[Any, None]:
        """Stream results from a tool."""
        if not self.connected:
            raise MCPError(ErrorCode.INVALID_REQUEST, "Not connected to server")
        
        # Convert arguments to protobuf Struct
        from google.protobuf.struct_pb2 import Struct
        from google.protobuf.json_format import ParseDict
        
        args_struct = Struct()
        ParseDict(arguments, args_struct)
        
        request = mcp_pb2.ExecuteToolRequest(
            tool_name=tool_name,
            arguments=args_struct,
            context=context or {},
            request_id=request_id or f"stream_{asyncio.current_task().get_name()}"
        )
        
        try:
            async for response in self.stub.StreamTool(request):
                if response.HasField("error"):
                    error = response.error
                    raise MCPError(error.code, error.message)
                elif response.HasField("progress"):
                    progress = response.progress
                    yield {
                        "type": "progress",
                        "progress": progress.progress,
                        "message": progress.message,
                        "request_id": response.request_id
                    }
                elif response.HasField("partial_result"):
                    result = self._convert_pb_to_result(response.partial_result)
                    yield {
                        "type": "partial_result",
                        "result": result,
                        "request_id": response.request_id
                    }
                elif response.HasField("final_result"):
                    result = self._convert_pb_to_result(response.final_result)
                    yield {
                        "type": "final_result",
                        "result": result,
                        "request_id": response.request_id
                    }
                    
        except grpc.RpcError as e:
            raise MCPError(ErrorCode.INTERNAL_ERROR, f"Failed to stream tool: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check server health."""
        if not self.connected:
            raise MCPError(ErrorCode.INVALID_REQUEST, "Not connected to server")
        
        request = mcp_pb2.HealthCheckRequest()
        
        try:
            response = await self.stub.HealthCheck(request)
            return {
                "healthy": response.healthy,
                "components": dict(response.component_health)
            }
        except grpc.RpcError as e:
            raise MCPError(ErrorCode.INTERNAL_ERROR, f"Health check failed: {e}")
    
    def _convert_pb_to_result(self, pb_result) -> MCPToolResult:
        """Convert protobuf ToolResult to MCPToolResult."""
        result = MCPToolResult()
        
        for content in pb_result.content:
            if content.HasField("text"):
                result.add_text(content.text.text)
            elif content.HasField("json"):
                from google.protobuf.json_format import MessageToDict
                data = MessageToDict(content.json.data)
                result.add_json(data)
            elif content.HasField("binary"):
                result.add_binary(content.binary.data, content.binary.mime_type)
        
        # Add metadata
        for key, value in pb_result.metadata.items():
            result.set_metadata(key, value)
        
        return result
    
    async def close(self) -> None:
        """Close the connection."""
        if self.channel:
            await self.channel.close()
            self.connected = False
            logger.info("Disconnected from MCP server")


def create_client(server_address: str, secure: bool = False) -> MCPClient:
    """Create a new MCP client."""
    return MCPClient(server_address, secure)