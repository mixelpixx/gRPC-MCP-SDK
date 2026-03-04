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
        self.is_error: bool = False
    
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
        """Add an error to the result. Sets isError flag to True."""
        self.is_error = True
        self.content.append({
            "type": "text",
            "text": f"Error [{code}]: {message}"
        })
        if data:
            self.metadata["error_data"] = json.dumps(data)
        return self

    def add_image(
        self,
        data: Union[bytes, str],
        mime_type: str = "image/png",
        annotations: Optional[Dict[str, Any]] = None
    ) -> "MCPToolResult":
        """Add image content to the result.

        Args:
            data: Image data as bytes or base64-encoded string
            mime_type: MIME type of the image (e.g., "image/png", "image/jpeg")
            annotations: Optional annotations (audience, priority, etc.)
        """
        if isinstance(data, bytes):
            encoded_data = base64.b64encode(data).decode("utf-8")
        else:
            encoded_data = data

        content_item = {
            "type": "image",
            "data": encoded_data,
            "mimeType": mime_type
        }
        if annotations:
            content_item["annotations"] = annotations

        self.content.append(content_item)
        return self

    def add_audio(
        self,
        data: Union[bytes, str],
        mime_type: str = "audio/wav"
    ) -> "MCPToolResult":
        """Add audio content to the result.

        Args:
            data: Audio data as bytes or base64-encoded string
            mime_type: MIME type of the audio (e.g., "audio/wav", "audio/mp3")
        """
        if isinstance(data, bytes):
            encoded_data = base64.b64encode(data).decode("utf-8")
        else:
            encoded_data = data

        self.content.append({
            "type": "audio",
            "data": encoded_data,
            "mimeType": mime_type
        })
        return self

    def add_resource(
        self,
        uri: str,
        text: Optional[str] = None,
        blob: Optional[bytes] = None,
        mime_type: Optional[str] = None,
        annotations: Optional[Dict[str, Any]] = None
    ) -> "MCPToolResult":
        """Add an embedded resource to the result.

        Args:
            uri: Resource URI
            text: Text content (for text resources)
            blob: Binary content (for binary resources)
            mime_type: MIME type of the resource
            annotations: Optional annotations
        """
        resource = {"uri": uri}
        if text is not None:
            resource["text"] = text
        if blob is not None:
            resource["blob"] = base64.b64encode(blob).decode("utf-8")
        if mime_type:
            resource["mimeType"] = mime_type
        if annotations:
            resource["annotations"] = annotations

        self.content.append({
            "type": "resource",
            "resource": resource
        })
        return self

    def add_resource_link(
        self,
        uri: str,
        name: str,
        description: Optional[str] = None,
        mime_type: Optional[str] = None
    ) -> "MCPToolResult":
        """Add a resource link to the result.

        Args:
            uri: Resource URI that can be fetched
            name: Human-readable name
            description: Optional description
            mime_type: MIME type of the linked resource
        """
        content_item = {
            "type": "resource_link",
            "uri": uri,
            "name": name
        }
        if description:
            content_item["description"] = description
        if mime_type:
            content_item["mimeType"] = mime_type

        self.content.append(content_item)
        return self
    
    def set_metadata(self, key: str, value: str) -> "MCPToolResult":
        """Set metadata for the result."""
        self.metadata[key] = value
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation (MCP-compliant)."""
        result = {
            "content": self.content,
            "isError": self.is_error
        }
        if self.metadata:
            result["_meta"] = self.metadata
        return result
    
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
    """Represents a tool definition (MCP-compliant)."""
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {},
        "required": []
    })
    supports_streaming: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)
    annotations: Optional[Dict[str, Any]] = None  # Tool behavior hints

    # Deprecated: use input_schema instead
    parameters: List[ToolParameter] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to MCP-compliant dictionary representation."""
        result = {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema
        }
        if self.annotations:
            result["annotations"] = self.annotations
        return result

    def to_mcp_tool(self) -> Dict[str, Any]:
        """Convert to full MCP tool format."""
        return self.to_dict()

    @classmethod
    def from_parameters(
        cls,
        name: str,
        description: str,
        parameters: Dict[str, Dict[str, Any]],
        supports_streaming: bool = False,
        metadata: Optional[Dict[str, str]] = None,
        annotations: Optional[Dict[str, Any]] = None
    ) -> "ToolDefinition":
        """Create ToolDefinition from a parameters dict (internal format).

        Converts internal parameter format to JSON Schema inputSchema.
        """
        properties = {}
        required = []

        for param_name, param_info in parameters.items():
            param_type = param_info.get("type", "string")
            prop = {"type": _python_type_to_json_schema_type(param_type)}

            if param_info.get("description"):
                prop["description"] = param_info["description"]

            properties[param_name] = prop

            if param_info.get("required", False):
                required.append(param_name)

        input_schema = {
            "type": "object",
            "properties": properties
        }
        if required:
            input_schema["required"] = required

        return cls(
            name=name,
            description=description,
            input_schema=input_schema,
            supports_streaming=supports_streaming,
            metadata=metadata or {},
            annotations=annotations
        )


def _python_type_to_json_schema_type(py_type: str) -> str:
    """Map Python/internal type names to JSON Schema types."""
    mapping = {
        "string": "string",
        "str": "string",
        "number": "number",
        "int": "integer",
        "integer": "integer",
        "float": "number",
        "boolean": "boolean",
        "bool": "boolean",
        "object": "object",
        "dict": "object",
        "array": "array",
        "list": "array",
    }
    return mapping.get(py_type.lower(), "string")


# =============================================================================
# MCP Capabilities (structured format per spec)
# =============================================================================

@dataclass
class ToolsCapability:
    """Tools capability configuration."""
    listChanged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {"listChanged": self.listChanged}


@dataclass
class ResourcesCapability:
    """Resources capability configuration."""
    subscribe: bool = False
    listChanged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subscribe": self.subscribe,
            "listChanged": self.listChanged
        }


@dataclass
class PromptsCapability:
    """Prompts capability configuration."""
    listChanged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {"listChanged": self.listChanged}


@dataclass
class LoggingCapability:
    """Logging capability configuration."""

    def to_dict(self) -> Dict[str, Any]:
        return {}


@dataclass
class ServerCapabilities:
    """MCP server capabilities (structured format)."""
    tools: Optional[ToolsCapability] = None
    resources: Optional[ResourcesCapability] = None
    prompts: Optional[PromptsCapability] = None
    logging: Optional[LoggingCapability] = None
    experimental: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to MCP-compliant capabilities object."""
        result = {}
        if self.tools:
            result["tools"] = self.tools.to_dict()
        if self.resources:
            result["resources"] = self.resources.to_dict()
        if self.prompts:
            result["prompts"] = self.prompts.to_dict()
        if self.logging:
            result["logging"] = self.logging.to_dict()
        if self.experimental:
            result["experimental"] = self.experimental
        return result

    @classmethod
    def default(cls) -> "ServerCapabilities":
        """Create default server capabilities."""
        return cls(
            tools=ToolsCapability(listChanged=True)
        )


@dataclass
class ClientCapabilities:
    """MCP client capabilities."""
    roots: Optional[Dict[str, Any]] = None
    sampling: Optional[Dict[str, Any]] = None
    experimental: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        if self.roots:
            result["roots"] = self.roots
        if self.sampling:
            result["sampling"] = self.sampling
        if self.experimental:
            result["experimental"] = self.experimental
        return result


@dataclass
class ServerInfo:
    """MCP server information."""
    name: str
    version: str

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "version": self.version}


@dataclass
class ClientInfo:
    """MCP client information."""
    name: str
    version: str

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "version": self.version}


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