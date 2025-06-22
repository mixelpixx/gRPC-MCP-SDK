"""
MCP-gRPC Bridge - Protocol bridge for backward compatibility

This bridge allows existing MCP clients (using JSON-RPC over HTTP) to connect
to our high-performance gRPC MCP servers seamlessly.
"""

import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Union

import grpc
from aiohttp import web, ClientSession, ClientTimeout
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf import struct_pb2

# Import our gRPC MCP SDK
from grpc_mcp_sdk import (
    MCPGrpcClient, MCPToolResult, _tool_registry
)

logger = logging.getLogger(__name__)

# MCP Protocol structures (JSON-RPC 2.0)
class MCPRequest:
    def __init__(self, jsonrpc: str, id: Any, method: str, params: Optional[Dict] = None):
        self.jsonrpc = jsonrpc
        self.id = id
        self.method = method
        self.params = params or {}

class MCPResponse:
    def __init__(self, jsonrpc: str, id: Any, result: Optional[Any] = None, error: Optional[Dict] = None):
        self.jsonrpc = jsonrpc
        self.id = id
        self.result = result
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        response = {
            "jsonrpc": self.jsonrpc,
            "id": self.id
        }
        if self.error:
            response["error"] = self.error
        else:
            response["result"] = self.result
        return response

class MCPError:
    # JSON-RPC 2.0 error codes
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    def __init__(self, code: int, message: str, data: Optional[Any] = None):
        self.code = code
        self.message = message
        self.data = data

    def to_dict(self) -> Dict[str, Any]:
        error = {
            "code": self.code,
            "message": self.message
        }
        if self.data is not None:
            error["data"] = self.data
        return error

class MCPBridge:
    """
    Bridge between MCP JSON-RPC protocol and gRPC MCP SDK
    
    This bridge:
    1. Accepts HTTP POST requests with JSON-RPC 2.0 messages
    2. Translates them to gRPC calls to our MCP server
    3. Converts gRPC responses back to JSON-RPC format
    4. Supports both request/response and streaming patterns
    """
    
    def __init__(self, grpc_server_addr: str = "localhost:50051", http_port: int = 8080):
        self.grpc_server_addr = grpc_server_addr
        self.http_port = http_port
        self.grpc_client: Optional[MCPGrpcClient] = None
        self.app = web.Application()
        self.active_sessions: Dict[str, Any] = {}
        
        # Setup routes
        self.app.router.add_post("/mcp", self.handle_mcp_request)
        self.app.router.add_get("/mcp/sse/{session_id}", self.handle_sse_stream)
        self.app.router.add_get("/health", self.health_check)
        self.app.router.add_get("/tools", self.list_tools)
        
        # CORS middleware for web clients
        self.app.middlewares.append(self.cors_middleware)

    async def start(self):
        """Start the bridge server"""
        # Connect to gRPC server
        self.grpc_client = MCPGrpcClient(self.grpc_server_addr)
        await self.grpc_client.connect()
        
        logger.info(f"MCP Bridge connected to gRPC server at {self.grpc_server_addr}")
        logger.info(f"Starting HTTP server on port {self.http_port}")
        
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self.http_port)
        await site.start()
        
        return runner

    async def stop(self):
        """Stop the bridge server"""
        if self.grpc_client:
            await self.grpc_client.close()

    @web.middleware
    async def cors_middleware(self, request: web.Request, handler):
        """CORS middleware for web clients"""
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Mcp-Session-Id'
        return response

    async def handle_mcp_request(self, request: web.Request) -> web.Response:
        """Handle MCP JSON-RPC requests"""
        try:
            # Parse JSON-RPC request
            body = await request.text()
            data = json.loads(body)
            
            # Validate JSON-RPC structure
            if not self._validate_jsonrpc_request(data):
                error = MCPError(MCPError.INVALID_REQUEST, "Invalid JSON-RPC request")
                response = MCPResponse("2.0", data.get("id"), error=error.to_dict())
                return web.json_response(response.to_dict(), status=400)
            
            mcp_request = MCPRequest(
                jsonrpc=data["jsonrpc"],
                id=data["id"],
                method=data["method"],
                params=data.get("params", {})
            )
            
            # Route to appropriate handler
            if mcp_request.method == "initialize":
                response = await self._handle_initialize(mcp_request)
            elif mcp_request.method == "tools/list":
                response = await self._handle_tools_list(mcp_request)
            elif mcp_request.method == "tools/call":
                response = await self._handle_tools_call(mcp_request)
            elif mcp_request.method == "resources/list":
                response = await self._handle_resources_list(mcp_request)
            elif mcp_request.method == "resources/read":
                response = await self._handle_resources_read(mcp_request)
            elif mcp_request.method == "ping":
                response = await self._handle_ping(mcp_request)
            else:
                error = MCPError(MCPError.METHOD_NOT_FOUND, f"Method not found: {mcp_request.method}")
                response = MCPResponse(mcp_request.jsonrpc, mcp_request.id, error=error.to_dict())
            
            return web.json_response(response.to_dict())
            
        except json.JSONDecodeError:
            error = MCPError(MCPError.PARSE_ERROR, "Parse error")
            response = MCPResponse("2.0", None, error=error.to_dict())
            return web.json_response(response.to_dict(), status=400)
        except Exception as e:
            logger.exception("Error handling MCP request")
            error = MCPError(MCPError.INTERNAL_ERROR, str(e))
            response = MCPResponse("2.0", data.get("id") if 'data' in locals() else None, error=error.to_dict())
            return web.json_response(response.to_dict(), status=500)

    async def _handle_initialize(self, request: MCPRequest) -> MCPResponse:
        """Handle MCP initialization"""
        result = {
            "protocolVersion": "2025-03-26",
            "capabilities": {
                "tools": {"supported": True},
                "resources": {"supported": True},
                "logging": {"supported": True}
            },
            "serverInfo": {
                "name": "gRPC-MCP-Bridge",
                "version": "1.0.0",
                "description": "High-performance gRPC MCP Bridge"
            },
            "instructions": "Connected to gRPC MCP server for enhanced performance"
        }
        return MCPResponse(request.jsonrpc, request.id, result=result)

    async def _handle_tools_list(self, request: MCPRequest) -> MCPResponse:
        """Handle tools/list request"""
        try:
            # Get tools from gRPC server
            tools_schema = await self.grpc_client.list_tools()
            
            # Convert to MCP format
            tools = []
            for tool_info in tools_schema.get("tools", []):
                tool = {
                    "name": tool_info["name"],
                    "description": tool_info["description"],
                    "inputSchema": tool_info.get("inputSchema", {
                        "type": "object",
                        "properties": {}
                    })
                }
                tools.append(tool)
            
            result = {"tools": tools}
            return MCPResponse(request.jsonrpc, request.id, result=result)
            
        except Exception as e:
            logger.exception("Error listing tools")
            error = MCPError(MCPError.INTERNAL_ERROR, f"Failed to list tools: {str(e)}")
            return MCPResponse(request.jsonrpc, request.id, error=error.to_dict())

    async def _handle_tools_call(self, request: MCPRequest) -> MCPResponse:
        """Handle tools/call request"""
        try:
            params = request.params
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if not tool_name:
                error = MCPError(MCPError.INVALID_PARAMS, "Tool name is required")
                return MCPResponse(request.jsonrpc, request.id, error=error.to_dict())
            
            # Check if tool supports streaming
            tools_schema = await self.grpc_client.list_tools()
            tool_info = None
            for tool in tools_schema.get("tools", []):
                if tool["name"] == tool_name:
                    tool_info = tool
                    break
            
            is_streaming = tool_info and tool_info.get("streaming", False)
            
            if is_streaming:
                # Handle streaming tool
                session_id = str(uuid.uuid4())
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Streaming tool {tool_name} started. Connect to /mcp/sse/{session_id} for real-time updates."
                        }
                    ],
                    "metadata": {
                        "streaming": "true",
                        "session_id": session_id
                    }
                }
                
                # Start streaming in background
                asyncio.create_task(self._handle_streaming_tool(session_id, tool_name, arguments))
                
            else:
                # Handle regular tool
                grpc_result = await self.grpc_client.execute_tool(tool_name, arguments)
                result = self._convert_grpc_result_to_mcp(grpc_result)
            
            return MCPResponse(request.jsonrpc, request.id, result=result)
            
        except Exception as e:
            logger.exception("Error calling tool")
            error = MCPError(MCPError.INTERNAL_ERROR, f"Tool execution failed: {str(e)}")
            return MCPResponse(request.jsonrpc, request.id, error=error.to_dict())

    async def _handle_streaming_tool(self, session_id: str, tool_name: str, arguments: Dict[str, Any]):
        """Handle streaming tool execution"""
        try:
            self.active_sessions[session_id] = {
                "status": "active",
                "tool_name": tool_name,
                "messages": []
            }
            
            # Execute streaming tool
            async for result in await self.grpc_client.execute_tool(tool_name, arguments, streaming=True):
                if session_id not in self.active_sessions:
                    break  # Session was cancelled
                
                mcp_result = self._convert_grpc_result_to_mcp(result)
                self.active_sessions[session_id]["messages"].append({
                    "timestamp": time.time(),
                    "data": mcp_result
                })
            
            # Mark session as complete
            if session_id in self.active_sessions:
                self.active_sessions[session_id]["status"] = "complete"
                
        except Exception as e:
            logger.exception(f"Error in streaming tool {tool_name}")
            if session_id in self.active_sessions:
                self.active_sessions[session_id]["status"] = "error"
                self.active_sessions[session_id]["error"] = str(e)

    async def handle_sse_stream(self, request: web.Request) -> web.StreamResponse:
        """Handle Server-Sent Events for streaming tools"""
        session_id = request.match_info["session_id"]
        
        if session_id not in self.active_sessions:
            return web.Response(status=404, text="Session not found")
        
        response = web.StreamResponse(
            status=200,
            reason='OK',
            headers={
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
            }
        )
        
        await response.prepare(request)
        
        try:
            last_message_index = 0
            
            while True:
                session = self.active_sessions.get(session_id)
                if not session:
                    break
                
                # Send new messages
                messages = session["messages"][last_message_index:]
                for message in messages:
                    data = json.dumps(message["data"])
                    await response.write(f"data: {data}\n\n".encode())
                    last_message_index += 1
                
                # Check if session is complete
                if session["status"] in ["complete", "error"]:
                    if session["status"] == "error":
                        error_data = {"error": session.get("error", "Unknown error")}
                        await response.write(f"data: {json.dumps(error_data)}\n\n".encode())
                    
                    await response.write("event: close\ndata: {}\n\n".encode())
                    break
                
                await asyncio.sleep(0.1)  # Poll interval
                
        except asyncio.CancelledError:
            pass
        finally:
            # Cleanup session
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
        
        return response

    async def _handle_resources_list(self, request: MCPRequest) -> MCPResponse:
        """Handle resources/list request"""
        # For now, return empty resources list
        # In the future, this could expose gRPC service reflection
        result = {"resources": []}
        return MCPResponse(request.jsonrpc, request.id, result=result)

    async def _handle_resources_read(self, request: MCPRequest) -> MCPResponse:
        """Handle resources/read request"""
        error = MCPError(MCPError.METHOD_NOT_FOUND, "Resources not implemented yet")
        return MCPResponse(request.jsonrpc, request.id, error=error.to_dict())

    async def _handle_ping(self, request: MCPRequest) -> MCPResponse:
        """Handle ping request"""
        result = {"pong": True, "timestamp": time.time()}
        return MCPResponse(request.jsonrpc, request.id, result=result)

    async def health_check(self, request: web.Request) -> web.Response:
        """Health check endpoint"""
        try:
            # Check gRPC connection
            if self.grpc_client:
                # Could add actual health check to gRPC server here
                status = {
                    "healthy": True,
                    "grpc_server": self.grpc_server_addr,
                    "active_sessions": len(self.active_sessions),
                    "timestamp": time.time()
                }
            else:
                status = {
                    "healthy": False,
                    "error": "gRPC client not connected"
                }
            
            return web.json_response(status)
            
        except Exception as e:
            return web.json_response({
                "healthy": False,
                "error": str(e)
            }, status=500)

    async def list_tools(self, request: web.Request) -> web.Response:
        """List available tools (convenience endpoint)"""
        try:
            tools_schema = await self.grpc_client.list_tools()
            return web.json_response(tools_schema)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    def _validate_jsonrpc_request(self, data: Dict[str, Any]) -> bool:
        """Validate JSON-RPC 2.0 request structure"""
        required_fields = ["jsonrpc", "method", "id"]
        return all(field in data for field in required_fields) and data["jsonrpc"] == "2.0"

    def _convert_grpc_result_to_mcp(self, grpc_result: Dict[str, Any]) -> Dict[str, Any]:
        """Convert gRPC result to MCP format"""
        if "error" in grpc_result:
            return grpc_result
        
        result = grpc_result.get("result", {})
        content = result.get("content", [])
        metadata = result.get("metadata", {})
        
        # Convert content format
        mcp_content = []
        for item in content:
            mcp_item = {
                "type": item.get("type", "text"),
                "text": item.get("text", "")
            }
            
            # Add additional fields if present
            if "data" in item:
                mcp_item["data"] = item["data"]
            if "annotations" in item:
                mcp_item["annotations"] = item["annotations"]
            
            mcp_content.append(mcp_item)
        
        return {
            "content": mcp_content,
            "metadata": metadata
        }

async def main():
    """Main function to run the bridge"""
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP-gRPC Bridge Server")
    parser.add_argument("--grpc-server", default="localhost:50051", help="gRPC server address")
    parser.add_argument("--http-port", type=int, default=8080, help="HTTP server port")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and start bridge
    bridge = MCPBridge(args.grpc_server, args.http_port)
    
    try:
        runner = await bridge.start()
        print(f"🌉 MCP-gRPC Bridge running:")
        print(f"   HTTP Server: http://0.0.0.0:{args.http_port}")
        print(f"   gRPC Backend: {args.grpc_server}")
        print(f"   Health Check: http://0.0.0.0:{args.http_port}/health")
        print(f"   Tools List: http://0.0.0.0:{args.http_port}/tools")
        print("\n   Use this bridge to connect existing MCP clients to gRPC servers!")
        
        # Keep running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Shutting down bridge...")
        await bridge.stop()
        await runner.cleanup()
        print("✅ Bridge stopped")

if __name__ == "__main__":
    asyncio.run(main())