"""Tool registry for gRPC MCP SDK."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, AsyncGenerator
import asyncio
import threading
import time
from collections import defaultdict

from .types import MCPToolResult, ToolDefinition, ToolParameter, ExecutionContext
from ..utils.errors import ToolNotFoundError, RateLimitError, ValidationError
from ..utils.validation import validate_tool_name


@dataclass
class Tool:
    """Represents a registered MCP tool."""
    name: str
    description: str
    execute: Callable
    parameters: Dict[str, Dict[str, Any]]
    requires_auth: bool = False
    rate_limit: Optional[int] = None
    metadata: Dict[str, str] = field(default_factory=dict)
    supports_streaming: bool = False
    stream: Optional[Callable] = None
    
    def __post_init__(self):
        """Validate tool after initialization."""
        validate_tool_name(self.name)
        
        if self.supports_streaming and self.stream is None:
            raise ValidationError(f"Streaming tool '{self.name}' must have a stream function")
    
    def to_definition(self) -> ToolDefinition:
        """Convert to ToolDefinition."""
        parameters = []
        for param_name, param_info in self.parameters.items():
            parameters.append(ToolParameter(
                name=param_name,
                type=param_info.get("type", "string"),
                required=param_info.get("required", False),
                description=param_info.get("description", ""),
                default_value=param_info.get("default_value")
            ))
        
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=parameters,
            supports_streaming=self.supports_streaming,
            metadata=self.metadata
        )


class RateLimiter:
    """Simple rate limiter implementation."""
    
    def __init__(self):
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self.lock = threading.Lock()
    
    def check_rate_limit(self, tool_name: str, limit: int, window: int = 60) -> bool:
        """Check if request is within rate limit."""
        current_time = time.time()
        
        with self.lock:
            # Clean old requests
            self.requests[tool_name] = [
                req_time for req_time in self.requests[tool_name]
                if current_time - req_time < window
            ]
            
            # Check if within limit
            if len(self.requests[tool_name]) >= limit:
                return False
            
            # Add current request
            self.requests[tool_name].append(current_time)
            return True


class ToolRegistry:
    """Registry for MCP tools."""
    
    _global_instance = None
    _lock = threading.Lock()
    
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self.rate_limiter = RateLimiter()
        self._healthy = True
    
    @classmethod
    def global_registry(cls) -> "ToolRegistry":
        """Get the global tool registry instance."""
        if cls._global_instance is None:
            with cls._lock:
                if cls._global_instance is None:
                    cls._global_instance = cls()
        return cls._global_instance
    
    def register(self, tool: Tool) -> None:
        """Register a tool."""
        if tool.name in self.tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        
        self.tools[tool.name] = tool
    
    def unregister(self, tool_name: str) -> None:
        """Unregister a tool."""
        if tool_name in self.tools:
            del self.tools[tool_name]
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self.tools.get(name)
    
    def list_tools(self, filter_str: Optional[str] = None) -> List[Tool]:
        """List all tools with optional filtering."""
        tools = list(self.tools.values())
        
        if filter_str:
            filter_lower = filter_str.lower()
            tools = [
                tool for tool in tools
                if filter_lower in tool.name.lower() or 
                   filter_lower in tool.description.lower()
            ]
        
        return tools
    
    def get_tool_definitions(self, filter_str: Optional[str] = None) -> List[ToolDefinition]:
        """Get tool definitions with optional filtering."""
        tools = self.list_tools(filter_str)
        return [tool.to_definition() for tool in tools]
    
    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: ExecutionContext
    ) -> MCPToolResult:
        """Execute a tool with rate limiting and validation."""
        tool = self.get_tool(tool_name)
        if not tool:
            raise ToolNotFoundError(tool_name)
        
        # Check rate limit
        if tool.rate_limit:
            if not self.rate_limiter.check_rate_limit(tool_name, tool.rate_limit):
                raise RateLimitError(tool.rate_limit, 60)
        
        # Execute tool
        try:
            result = await tool.execute(arguments, context.to_dict())
            return result
        except Exception as e:
            # Wrap in MCPToolResult if not already
            if isinstance(e, Exception) and not isinstance(result, MCPToolResult):
                error_result = MCPToolResult()
                error_result.add_error("TOOL_EXECUTION_ERROR", str(e))
                return error_result
            raise
    
    async def stream_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: ExecutionContext
    ) -> AsyncGenerator[Any, None]:
        """Stream results from a tool."""
        tool = self.get_tool(tool_name)
        if not tool:
            raise ToolNotFoundError(tool_name)
        
        if not tool.supports_streaming:
            raise ValidationError(f"Tool '{tool_name}' does not support streaming")
        
        # Check rate limit
        if tool.rate_limit:
            if not self.rate_limiter.check_rate_limit(tool_name, tool.rate_limit):
                raise RateLimitError(tool.rate_limit, 60)
        
        # Stream from tool
        try:
            async for update in tool.stream(arguments, context.to_dict()):
                yield update
        except Exception as e:
            # Yield error as final result
            error_result = MCPToolResult()
            error_result.add_error("TOOL_STREAMING_ERROR", str(e))
            yield error_result
    
    def is_healthy(self) -> bool:
        """Check if registry is healthy."""
        return self._healthy and len(self.tools) > 0
    
    def set_healthy(self, healthy: bool) -> None:
        """Set registry health status."""
        self._healthy = healthy
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        streaming_tools = sum(1 for tool in self.tools.values() if tool.supports_streaming)
        auth_tools = sum(1 for tool in self.tools.values() if tool.requires_auth)
        rate_limited_tools = sum(1 for tool in self.tools.values() if tool.rate_limit)
        
        return {
            "total_tools": len(self.tools),
            "streaming_tools": streaming_tools,
            "auth_tools": auth_tools,
            "rate_limited_tools": rate_limited_tools,
            "healthy": self.is_healthy()
        }
    
    def clear(self) -> None:
        """Clear all registered tools."""
        self.tools.clear()
    
    def __len__(self) -> int:
        """Return number of registered tools."""
        return len(self.tools)
    
    def __contains__(self, tool_name: str) -> bool:
        """Check if tool is registered."""
        return tool_name in self.tools
    
    def __iter__(self):
        """Iterate over registered tools."""
        return iter(self.tools.values())