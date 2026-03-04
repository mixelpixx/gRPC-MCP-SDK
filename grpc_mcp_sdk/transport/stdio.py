"""Stdio transport for MCP servers.

Implements JSON-RPC 2.0 over stdin/stdout for local MCP clients
like Claude Desktop. This enables the gRPC MCP SDK to work with
standard MCP clients that use stdio transport.
"""

import asyncio
import json
import logging
import sys
from typing import Any, Dict, Optional, Callable, Awaitable

from ..core.types import ServerCapabilities, ServerInfo
from ..core.registry import ToolRegistry
from ..core.resource_registry import ResourceRegistry
from ..core.prompt_registry import PromptRegistry
from ..core.notifications import NotificationManager, Notification

logger = logging.getLogger(__name__)


class StdioTransport:
    """JSON-RPC 2.0 transport over stdin/stdout.

    This transport allows MCP servers to communicate with local clients
    like Claude Desktop using the standard stdio transport method.

    Usage:
        transport = StdioTransport()
        await transport.run()
    """

    def __init__(
        self,
        server_name: str = "grpc-mcp-server",
        server_version: str = "1.0.0",
        tool_registry: Optional[ToolRegistry] = None,
        resource_registry: Optional[ResourceRegistry] = None,
        prompt_registry: Optional[PromptRegistry] = None,
        notification_manager: Optional[NotificationManager] = None
    ):
        self.server_name = server_name
        self.server_version = server_version
        self.tool_registry = tool_registry or ToolRegistry.global_registry()
        self.resource_registry = resource_registry or ResourceRegistry.global_registry()
        self.prompt_registry = prompt_registry or PromptRegistry.global_registry()
        self.notification_manager = notification_manager or NotificationManager.global_manager()

        self._initialized = False
        self._client_capabilities: Dict[str, Any] = {}
        self._running = False
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

        # Request handlers
        self._handlers: Dict[str, Callable[[Dict], Awaitable[Dict]]] = {
            "initialize": self._handle_initialize,
            "initialized": self._handle_initialized,
            "ping": self._handle_ping,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
            "resources/templates/list": self._handle_resources_templates_list,
            "resources/subscribe": self._handle_resources_subscribe,
            "resources/unsubscribe": self._handle_resources_unsubscribe,
            "prompts/list": self._handle_prompts_list,
            "prompts/get": self._handle_prompts_get,
        }

    async def run(self) -> None:
        """Run the stdio transport, processing messages until shutdown."""
        self._running = True

        # Set up async stdin/stdout
        loop = asyncio.get_event_loop()
        self._reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(self._reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        # Write directly to stdout
        transport, _ = await loop.connect_write_pipe(
            asyncio.streams.FlowControlMixin,
            sys.stdout
        )
        self._writer = asyncio.StreamWriter(transport, protocol, self._reader, loop)

        logger.info(f"Stdio transport started for {self.server_name}")

        try:
            while self._running:
                line = await self._reader.readline()
                if not line:
                    break

                line = line.decode('utf-8').strip()
                if not line:
                    continue

                try:
                    request = json.loads(line)
                    response = await self._handle_message(request)
                    if response:
                        await self._write_response(response)
                except json.JSONDecodeError as e:
                    error_response = self._make_error(-32700, f"Parse error: {e}", None)
                    await self._write_response(error_response)
                except Exception as e:
                    logger.exception("Error handling message")
                    error_response = self._make_error(-32603, str(e), None)
                    await self._write_response(error_response)

        finally:
            self._running = False
            logger.info("Stdio transport stopped")

    async def stop(self) -> None:
        """Stop the stdio transport."""
        self._running = False

    async def _write_response(self, response: Dict[str, Any]) -> None:
        """Write a JSON-RPC response to stdout."""
        if self._writer:
            line = json.dumps(response) + "\n"
            self._writer.write(line.encode('utf-8'))
            await self._writer.drain()

    async def send_notification(self, notification: Notification) -> None:
        """Send a notification to the client."""
        msg = notification.to_jsonrpc()
        await self._write_response(msg)

    async def _handle_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle an incoming JSON-RPC message."""
        # Validate JSON-RPC 2.0 structure
        if message.get("jsonrpc") != "2.0":
            return self._make_error(-32600, "Invalid JSON-RPC version", message.get("id"))

        method = message.get("method")
        params = message.get("params", {})
        msg_id = message.get("id")

        # Handle notification (no id)
        if msg_id is None:
            if method in self._handlers:
                try:
                    await self._handlers[method](params)
                except Exception as e:
                    logger.warning(f"Notification handler error: {e}")
            return None

        # Handle request
        if method not in self._handlers:
            return self._make_error(-32601, f"Method not found: {method}", msg_id)

        try:
            result = await self._handlers[method](params)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": result
            }
        except Exception as e:
            logger.exception(f"Handler error for {method}")
            return self._make_error(-32603, str(e), msg_id)

    def _make_error(self, code: int, message: str, msg_id: Any) -> Dict[str, Any]:
        """Create a JSON-RPC error response."""
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": code,
                "message": message
            }
        }

    # =========================================================================
    # MCP Protocol Handlers
    # =========================================================================

    async def _handle_initialize(self, params: Dict) -> Dict:
        """Handle initialize request."""
        self._client_capabilities = params.get("capabilities", {})

        # Build server capabilities
        capabilities = ServerCapabilities(
            tools={"listChanged": True} if len(self.tool_registry) > 0 else None,
            resources={"subscribe": True, "listChanged": True} if len(self.resource_registry) > 0 else None,
            prompts={"listChanged": True} if len(self.prompt_registry) > 0 else None
        )

        server_info = ServerInfo(
            name=self.server_name,
            version=self.server_version
        )

        return {
            "protocolVersion": "2024-11-05",
            "capabilities": capabilities.to_dict(),
            "serverInfo": server_info.to_dict()
        }

    async def _handle_initialized(self, params: Dict) -> Dict:
        """Handle initialized notification."""
        self._initialized = True
        logger.info("Client initialized")
        return {}

    async def _handle_ping(self, params: Dict) -> Dict:
        """Handle ping request."""
        return {}

    async def _handle_tools_list(self, params: Dict) -> Dict:
        """Handle tools/list request."""
        tools = self.tool_registry.get_tool_definitions()
        return {
            "tools": [t.to_dict() for t in tools]
        }

    async def _handle_tools_call(self, params: Dict) -> Dict:
        """Handle tools/call request."""
        from ..core.types import ExecutionContext

        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name:
            raise ValueError("Tool name is required")

        tool = self.tool_registry.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")

        # Create execution context
        context = ExecutionContext(
            tool_name=tool_name,
            session_id="stdio",
            request_id=None
        )

        # Execute tool
        result = await self.tool_registry.execute_tool(tool_name, arguments, context)

        return {
            "content": result.content,
            "isError": result.is_error,
            "_meta": result.metadata if result.metadata else None
        }

    async def _handle_resources_list(self, params: Dict) -> Dict:
        """Handle resources/list request."""
        resources = self.resource_registry.list_resources()
        return {
            "resources": [r.to_dict() for r in resources]
        }

    async def _handle_resources_read(self, params: Dict) -> Dict:
        """Handle resources/read request."""
        uri = params.get("uri")
        if not uri:
            raise ValueError("Resource URI is required")

        contents = await self.resource_registry.read_resource(uri)
        return {
            "contents": [contents.to_dict()]
        }

    async def _handle_resources_templates_list(self, params: Dict) -> Dict:
        """Handle resources/templates/list request."""
        templates = self.resource_registry.list_templates()
        return {
            "resourceTemplates": [t.to_dict() for t in templates]
        }

    async def _handle_resources_subscribe(self, params: Dict) -> Dict:
        """Handle resources/subscribe request."""
        uri = params.get("uri")
        if not uri:
            raise ValueError("Resource URI is required")

        self.resource_registry.subscribe(uri, "stdio")
        self.notification_manager.subscribe_resource("stdio", uri)
        return {}

    async def _handle_resources_unsubscribe(self, params: Dict) -> Dict:
        """Handle resources/unsubscribe request."""
        uri = params.get("uri")
        if not uri:
            raise ValueError("Resource URI is required")

        self.resource_registry.unsubscribe(uri, "stdio")
        self.notification_manager.unsubscribe_resource("stdio", uri)
        return {}

    async def _handle_prompts_list(self, params: Dict) -> Dict:
        """Handle prompts/list request."""
        prompts = self.prompt_registry.list_prompts()
        return {
            "prompts": [p.to_dict() for p in prompts]
        }

    async def _handle_prompts_get(self, params: Dict) -> Dict:
        """Handle prompts/get request."""
        name = params.get("name")
        arguments = params.get("arguments", {})

        if not name:
            raise ValueError("Prompt name is required")

        result = await self.prompt_registry.execute_prompt(name, arguments)
        return result.to_dict()


def create_stdio_server(
    server_name: str = "grpc-mcp-server",
    server_version: str = "1.0.0"
) -> StdioTransport:
    """Create a stdio transport server.

    Args:
        server_name: Name of the server
        server_version: Version of the server

    Returns:
        StdioTransport instance ready to run
    """
    return StdioTransport(
        server_name=server_name,
        server_version=server_version
    )


async def run_stdio_server(
    server_name: str = "grpc-mcp-server",
    server_version: str = "1.0.0"
) -> None:
    """Run a stdio transport server.

    This is a convenience function that creates and runs a stdio server.

    Args:
        server_name: Name of the server
        server_version: Version of the server
    """
    transport = create_stdio_server(server_name, server_version)
    await transport.run()


# CLI entry point
def main():
    """CLI entry point for running a stdio server."""
    import argparse

    parser = argparse.ArgumentParser(description="Run MCP stdio server")
    parser.add_argument("--name", default="grpc-mcp-server", help="Server name")
    parser.add_argument("--version", default="1.0.0", help="Server version")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    asyncio.run(run_stdio_server(args.name, args.version))


if __name__ == "__main__":
    main()
