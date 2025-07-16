"""Decorators for creating MCP tools."""

import functools
import inspect
import asyncio
from typing import Callable, Optional, Dict, Any, Union

from .registry import ToolRegistry, Tool
from .types import MCPToolResult
from ..utils.validation import validate_parameters


def mcp_tool(
    description: str,
    name: Optional[str] = None,
    requires_auth: bool = False,
    rate_limit: Optional[int] = None,
    metadata: Optional[Dict[str, str]] = None
):
    """
    Decorator to register a function as an MCP tool.
    
    Args:
        description: Human-readable description of the tool
        name: Tool name (defaults to function name)
        requires_auth: Whether the tool requires authentication
        rate_limit: Maximum calls per minute (None for unlimited)
        metadata: Additional metadata for the tool
    
    Example:
        @mcp_tool(description="Calculate square of a number")
        def square(x: float) -> MCPToolResult:
            result = x * x
            return MCPToolResult().add_text(f"{x}² = {result}")
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        
        # Extract parameters from function signature
        sig = inspect.signature(func)
        parameters = {}
        
        for param_name, param in sig.parameters.items():
            if param_name in ['self', 'cls']:
                continue
                
            param_type = "string"  # Default type
            if param.annotation != inspect.Parameter.empty:
                # Map Python types to MCP types
                type_mapping = {
                    str: "string",
                    int: "number",
                    float: "number",
                    bool: "boolean",
                    dict: "object",
                    list: "array"
                }
                param_type = type_mapping.get(param.annotation, "string")
            
            parameters[param_name] = {
                "type": param_type,
                "required": param.default == inspect.Parameter.empty,
                "description": ""  # Could be extracted from docstring
            }
        
        # Create tool wrapper
        is_async = inspect.iscoroutinefunction(func)
        
        async def async_wrapper(arguments: Dict[str, Any], context: Dict[str, Any]) -> MCPToolResult:
            """Async wrapper for tool execution."""
            # Validate parameters
            validate_parameters(arguments, parameters)
            
            # Call the original function
            try:
                if is_async:
                    result = await func(**arguments)
                else:
                    result = func(**arguments)
                
                # Ensure result is MCPToolResult
                if not isinstance(result, MCPToolResult):
                    # Auto-wrap non-MCPToolResult returns
                    wrapped_result = MCPToolResult()
                    if isinstance(result, str):
                        wrapped_result.add_text(result)
                    elif isinstance(result, dict):
                        wrapped_result.add_json(result)
                    elif isinstance(result, (list, tuple)):
                        wrapped_result.add_json({"data": result})
                    else:
                        wrapped_result.add_text(str(result))
                    result = wrapped_result
                
                return result
                
            except Exception as e:
                # Return error as MCPToolResult
                error_result = MCPToolResult()
                error_result.add_error("TOOL_EXECUTION_ERROR", str(e))
                return error_result
        
        # Create and register tool
        tool = Tool(
            name=tool_name,
            description=description,
            execute=async_wrapper,
            parameters=parameters,
            requires_auth=requires_auth,
            rate_limit=rate_limit,
            metadata=metadata or {},
            supports_streaming=False
        )
        
        # Register with global registry
        ToolRegistry.global_registry().register(tool)
        
        # Return original function unchanged
        return func
    
    return decorator


def streaming_tool(
    description: str,
    name: Optional[str] = None,
    requires_auth: bool = False,
    rate_limit: Optional[int] = None,
    metadata: Optional[Dict[str, str]] = None
):
    """
    Decorator for streaming tools that yield results over time.
    
    Args:
        description: Human-readable description of the tool
        name: Tool name (defaults to function name)
        requires_auth: Whether the tool requires authentication
        rate_limit: Maximum calls per minute (None for unlimited)
        metadata: Additional metadata for the tool
    
    Example:
        @streaming_tool(description="Process data with progress updates")
        async def process_data(items: int = 100):
            for i in range(items):
                yield f"Processing item {i+1}/{items}"
                await asyncio.sleep(0.01)
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        
        # Extract parameters (similar to mcp_tool)
        sig = inspect.signature(func)
        parameters = {}
        
        for param_name, param in sig.parameters.items():
            if param_name in ['self', 'cls']:
                continue
                
            param_type = "string"
            if param.annotation != inspect.Parameter.empty:
                type_mapping = {
                    str: "string",
                    int: "number",
                    float: "number",
                    bool: "boolean",
                    dict: "object",
                    list: "array"
                }
                param_type = type_mapping.get(param.annotation, "string")
            
            parameters[param_name] = {
                "type": param_type,
                "required": param.default == inspect.Parameter.empty,
                "description": ""
            }
        
        # Streaming wrapper
        async def stream_wrapper(arguments: Dict[str, Any], context: Dict[str, Any]):
            """Async generator wrapper for streaming tools."""
            # Validate parameters
            validate_parameters(arguments, parameters)
            
            try:
                # Call the generator function
                if inspect.isasyncgenfunction(func):
                    # Async generator
                    async for update in func(**arguments):
                        yield update
                elif inspect.isgeneratorfunction(func):
                    # Regular generator - wrap in async
                    for update in func(**arguments):
                        yield update
                else:
                    # Regular function - call once and yield result
                    result = func(**arguments)
                    if inspect.iscoroutine(result):
                        result = await result
                    yield result
                        
            except Exception as e:
                # Yield error as final result
                error_result = MCPToolResult()
                error_result.add_error("TOOL_STREAMING_ERROR", str(e))
                yield error_result
        
        # Dummy execute function for non-streaming calls
        async def execute_wrapper(arguments: Dict[str, Any], context: Dict[str, Any]) -> MCPToolResult:
            """Non-streaming execution wrapper."""
            result = MCPToolResult()
            result.add_text("This is a streaming tool. Use StreamTool RPC for streaming results.")
            return result
        
        # Create and register streaming tool
        tool = Tool(
            name=tool_name,
            description=description,
            execute=execute_wrapper,
            stream=stream_wrapper,
            parameters=parameters,
            requires_auth=requires_auth,
            rate_limit=rate_limit,
            metadata=metadata or {},
            supports_streaming=True
        )
        
        # Register with global registry
        ToolRegistry.global_registry().register(tool)
        
        # Return original function unchanged
        return func
    
    return decorator


# Convenience aliases
tool = mcp_tool
streaming = streaming_tool