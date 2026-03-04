"""Core gRPC MCP SDK components."""

from .server import MCPServicer, create_server, run_server
from .registry import ToolRegistry, Tool
from .resource_registry import ResourceRegistry, mcp_resource, mcp_resource_template, resource, resource_template
from .decorators import mcp_tool, streaming_tool, tool, streaming
from .client import MCPClient, create_client
from .types import (
    MCPToolResult,
    ToolParameter,
    ToolDefinition,
    ExecutionContext,
    ToolProgress,
    StreamingResponse,
    ProgressResponse,
    PartialResultResponse,
    FinalResultResponse,
    ErrorResponse,
    # MCP Capabilities
    ServerCapabilities,
    ClientCapabilities,
    ToolsCapability,
    ResourcesCapability,
    PromptsCapability,
    LoggingCapability,
    ServerInfo,
    ClientInfo,
    # MCP Resources
    Resource,
    ResourceTemplate,
    ResourceContents,
    ResourceAnnotations,
    # MCP Prompts
    Prompt,
    PromptArgument,
    PromptMessage,
    GetPromptResult,
)

__all__ = [
    'MCPServicer',
    'create_server',
    'run_server',
    'ToolRegistry',
    'Tool',
    'ResourceRegistry',
    'mcp_resource',
    'mcp_resource_template',
    'resource',
    'resource_template',
    'mcp_tool',
    'streaming_tool',
    'tool',
    'streaming',
    'MCPClient',
    'create_client',
    'MCPToolResult',
    'ToolParameter',
    'ToolDefinition',
    'ExecutionContext',
    'ToolProgress',
    'StreamingResponse',
    'ProgressResponse',
    'PartialResultResponse',
    'FinalResultResponse',
    'ErrorResponse',
    # MCP Capabilities
    'ServerCapabilities',
    'ClientCapabilities',
    'ToolsCapability',
    'ResourcesCapability',
    'PromptsCapability',
    'LoggingCapability',
    'ServerInfo',
    'ClientInfo',
    # MCP Resources
    'Resource',
    'ResourceTemplate',
    'ResourceContents',
    'ResourceAnnotations',
    # MCP Prompts
    'Prompt',
    'PromptArgument',
    'PromptMessage',
    'GetPromptResult',
]