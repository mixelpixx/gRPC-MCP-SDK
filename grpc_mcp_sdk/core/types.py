"""Core types for gRPC MCP SDK."""

from typing import List, Dict, Any, Optional, Union
import json
import base64
from dataclasses import dataclass, field


class MCPToolResult:
    """Result object returned by MCP tools."""
    
    def __init__(self):
        self.content: List[Dict[str, Any]] = []
        self.metadata: Dict[str, str] = {}
    
    def add_text(self, text: str) -> "MCPToolResult":
        """Add text content to the result."""
        self.content.append({
            "type": "text",
            "text": text
        })
        return self
    
    def add_json(self, data: Dict[str, Any]) -> "MCPToolResult":
        """Add JSON content to the result."""
        self.content.append({
            "type": "json",
            "data": data
        })
        return self
    
    def add_binary(self, data: bytes, mime_type: str = "application/octet-stream") -> "MCPToolResult":
        """Add binary content to the result."""
        self.content.append({
            "type": "binary",
            "data": data,
            "mime_type": mime_type
        })
        return self
    
    def add_error(self, code: str, message: str, data: Optional[Dict[str, Any]] = None) -> "MCPToolResult":
        """Add an error to the result."""
        self.content.append({
            "type": "error",
            "code": code,
            "message": message,
            "data": data or {}
        })
        return self
    
    def set_metadata(self, key: str, value: str) -> "MCPToolResult":
        """Set metadata for the result."""
        self.metadata[key] = value
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "content": self.content,
            "metadata": self.metadata
        }
    
    def __str__(self) -> str:
        """String representation of the result."""
        return json.dumps(self.to_dict(), indent=2)
    
    def __bool__(self) -> bool:
        """Check if result has content."""
        return len(self.content) > 0


@dataclass
class ToolParameter:
    """Represents a tool parameter definition."""
    name: str
    type: str  # "string", "number", "boolean", "object", "array"
    required: bool = False
    description: str = ""
    default_value: Any = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "description": self.description,
            "default_value": self.default_value
        }


@dataclass
class ToolDefinition:
    """Represents a tool definition."""
    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)
    supports_streaming: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": [p.to_dict() for p in self.parameters],
            "supports_streaming": self.supports_streaming,
            "metadata": self.metadata
        }


@dataclass
class ExecutionContext:
    """Context information for tool execution."""
    request_id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "metadata": self.metadata
        }


@dataclass
class ToolProgress:
    """Represents progress information for streaming tools."""
    progress: float  # 0.0 to 1.0
    message: str = ""
    timestamp: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "progress": self.progress,
            "message": self.message,
            "timestamp": self.timestamp
        }


class StreamingResponse:
    """Base class for streaming responses."""
    
    def __init__(self, request_id: str):
        self.request_id = request_id


class ProgressResponse(StreamingResponse):
    """Progress update response for streaming tools."""
    
    def __init__(self, request_id: str, progress: ToolProgress):
        super().__init__(request_id)
        self.progress = progress


class PartialResultResponse(StreamingResponse):
    """Partial result response for streaming tools."""
    
    def __init__(self, request_id: str, result: MCPToolResult):
        super().__init__(request_id)
        self.result = result


class FinalResultResponse(StreamingResponse):
    """Final result response for streaming tools."""
    
    def __init__(self, request_id: str, result: MCPToolResult):
        super().__init__(request_id)
        self.result = result


class ErrorResponse(StreamingResponse):
    """Error response for streaming tools."""
    
    def __init__(self, request_id: str, error: Dict[str, Any]):
        super().__init__(request_id)
        self.error = error