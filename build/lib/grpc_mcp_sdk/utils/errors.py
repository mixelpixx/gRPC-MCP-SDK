"""Error handling utilities for gRPC MCP SDK."""

from typing import Dict, Any, Optional
from enum import Enum


class ErrorCode:
    """Standard error codes for MCP operations."""
    
    # Core MCP errors
    INVALID_REQUEST = "INVALID_REQUEST"
    METHOD_NOT_FOUND = "METHOD_NOT_FOUND"
    INVALID_PARAMS = "INVALID_PARAMS"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    PARSE_ERROR = "PARSE_ERROR"
    
    # Tool-specific errors
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    TOOL_EXECUTION_ERROR = "TOOL_EXECUTION_ERROR"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    
    # Authentication errors
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_INVALID = "AUTH_INVALID"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    
    # Rate limiting errors
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    
    # Resource errors
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    
    # Validation errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    SCHEMA_ERROR = "SCHEMA_ERROR"


class MCPError(Exception):
    """Base exception for MCP-related errors."""
    
    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary representation."""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details
        }


class ToolNotFoundError(MCPError):
    """Raised when a requested tool is not found."""
    
    def __init__(self, tool_name: str):
        super().__init__(
            ErrorCode.TOOL_NOT_FOUND,
            f"Tool not found: {tool_name}",
            {"tool_name": tool_name}
        )


class ToolExecutionError(MCPError):
    """Raised when tool execution fails."""
    
    def __init__(self, tool_name: str, error_message: str):
        super().__init__(
            ErrorCode.TOOL_EXECUTION_ERROR,
            f"Tool execution failed: {error_message}",
            {"tool_name": tool_name, "error_message": error_message}
        )


class ValidationError(MCPError):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None):
        details = {"field": field} if field else {}
        super().__init__(
            ErrorCode.VALIDATION_ERROR,
            message,
            details
        )


class AuthenticationError(MCPError):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            ErrorCode.AUTH_REQUIRED,
            message
        )


class RateLimitError(MCPError):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, limit: int, window: int):
        super().__init__(
            ErrorCode.RATE_LIMIT_EXCEEDED,
            f"Rate limit exceeded: {limit} requests per {window} seconds",
            {"limit": limit, "window": window}
        )