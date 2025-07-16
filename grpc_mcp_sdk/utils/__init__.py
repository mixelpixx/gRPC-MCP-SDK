"""Utility functions and classes for gRPC MCP SDK."""

from .errors import (
    ErrorCode,
    MCPError,
    ToolNotFoundError,
    ToolExecutionError,
    ValidationError,
    AuthenticationError,
    RateLimitError
)
from .validation import (
    validate_tool_name,
    validate_parameters,
    validate_context,
    sanitize_string
)

__all__ = [
    'ErrorCode',
    'MCPError',
    'ToolNotFoundError',
    'ToolExecutionError',
    'ValidationError',
    'AuthenticationError',
    'RateLimitError',
    'validate_tool_name',
    'validate_parameters',
    'validate_context',
    'sanitize_string'
]