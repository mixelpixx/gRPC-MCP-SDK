"""Resource registry for gRPC MCP SDK.

Provides registration and management of MCP resources,
including static resources and dynamic resource templates.
"""

import re
import asyncio
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Set, Union
from functools import wraps

from .types import Resource, ResourceTemplate, ResourceContents, ResourceAnnotations
from ..utils.errors import ResourceNotFoundError, ValidationError


@dataclass
class RegisteredResource:
    """A registered resource with its reader function."""
    resource: Resource
    reader: Callable[[], Any]  # Returns content when called
    is_async: bool = False

    async def read(self) -> ResourceContents:
        """Read the resource contents."""
        if self.is_async:
            content = await self.reader()
        else:
            content = self.reader()

        # Convert to ResourceContents if not already
        if isinstance(content, ResourceContents):
            return content
        elif isinstance(content, str):
            return ResourceContents.from_text(self.resource.uri, content, self.resource.mimeType or "text/plain")
        elif isinstance(content, bytes):
            return ResourceContents.from_binary(self.resource.uri, content, self.resource.mimeType or "application/octet-stream")
        elif isinstance(content, dict):
            import json
            return ResourceContents.from_text(self.resource.uri, json.dumps(content), "application/json")
        else:
            return ResourceContents.from_text(self.resource.uri, str(content), "text/plain")


@dataclass
class RegisteredTemplate:
    """A registered resource template with its reader function."""
    template: ResourceTemplate
    reader: Callable[..., Any]  # Takes URI params, returns content
    is_async: bool = False
    param_names: List[str] = field(default_factory=list)

    def matches(self, uri: str) -> Optional[Dict[str, str]]:
        """Check if URI matches template and extract parameters."""
        # Convert URI template to regex pattern
        pattern = self.template.uriTemplate
        param_pattern = r'\{([^}]+)\}'

        # Extract parameter names
        params = re.findall(param_pattern, pattern)

        # Build regex to match URI
        regex_pattern = pattern
        for param in params:
            regex_pattern = regex_pattern.replace(f'{{{param}}}', r'([^/]+)')

        regex_pattern = f'^{regex_pattern}$'
        match = re.match(regex_pattern, uri)

        if match:
            return dict(zip(params, match.groups()))
        return None

    async def read(self, uri: str, params: Dict[str, str]) -> ResourceContents:
        """Read the resource contents with parameters."""
        if self.is_async:
            content = await self.reader(**params)
        else:
            content = self.reader(**params)

        # Convert to ResourceContents if not already
        if isinstance(content, ResourceContents):
            return content
        elif isinstance(content, str):
            return ResourceContents.from_text(uri, content, self.template.mimeType or "text/plain")
        elif isinstance(content, bytes):
            return ResourceContents.from_binary(uri, content, self.template.mimeType or "application/octet-stream")
        elif isinstance(content, dict):
            import json
            return ResourceContents.from_text(uri, json.dumps(content), "application/json")
        else:
            return ResourceContents.from_text(uri, str(content), "text/plain")


class ResourceRegistry:
    """Registry for MCP resources and resource templates."""

    _global_instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.resources: Dict[str, RegisteredResource] = {}
        self.templates: Dict[str, RegisteredTemplate] = {}
        self.subscriptions: Dict[str, Set[str]] = {}  # uri -> set of subscriber IDs
        self._healthy = True
        self._on_change_callback: Optional[Callable[[], None]] = None
        self._on_resource_updated_callback: Optional[Callable[[str], None]] = None

    def set_on_change_callback(self, callback: Callable[[], None]) -> None:
        """Set callback to be invoked when resources list changes."""
        self._on_change_callback = callback

    def set_on_resource_updated_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback to be invoked when a specific resource is updated."""
        self._on_resource_updated_callback = callback

    def _notify_change(self) -> None:
        """Notify that resources list has changed."""
        if self._on_change_callback:
            try:
                self._on_change_callback()
            except Exception:
                pass  # Silently ignore callback errors

    def notify_resource_updated(self, uri: str) -> None:
        """Notify that a specific resource has been updated."""
        if self._on_resource_updated_callback:
            try:
                self._on_resource_updated_callback(uri)
            except Exception:
                pass  # Silently ignore callback errors

    @classmethod
    def global_registry(cls) -> "ResourceRegistry":
        """Get the global resource registry instance."""
        if cls._global_instance is None:
            with cls._lock:
                if cls._global_instance is None:
                    cls._global_instance = cls()
        return cls._global_instance

    def register(self, resource: RegisteredResource) -> None:
        """Register a resource."""
        if resource.resource.uri in self.resources:
            raise ValueError(f"Resource already registered: {resource.resource.uri}")
        self.resources[resource.resource.uri] = resource
        self._notify_change()

    def register_template(self, template: RegisteredTemplate) -> None:
        """Register a resource template."""
        if template.template.uriTemplate in self.templates:
            raise ValueError(f"Template already registered: {template.template.uriTemplate}")
        self.templates[template.template.uriTemplate] = template
        self._notify_change()

    def unregister(self, uri: str) -> None:
        """Unregister a resource."""
        if uri in self.resources:
            del self.resources[uri]
            self._notify_change()

    def unregister_template(self, uri_template: str) -> None:
        """Unregister a resource template."""
        if uri_template in self.templates:
            del self.templates[uri_template]
            self._notify_change()

    def get_resource(self, uri: str) -> Optional[RegisteredResource]:
        """Get a resource by URI."""
        return self.resources.get(uri)

    def list_resources(self) -> List[Resource]:
        """List all registered resources."""
        return [reg.resource for reg in self.resources.values()]

    def list_templates(self) -> List[ResourceTemplate]:
        """List all registered resource templates."""
        return [reg.template for reg in self.templates.values()]

    async def read_resource(self, uri: str) -> ResourceContents:
        """Read a resource by URI.

        First checks static resources, then tries templates.
        """
        # Check static resources first
        if uri in self.resources:
            return await self.resources[uri].read()

        # Try templates
        for template in self.templates.values():
            params = template.matches(uri)
            if params is not None:
                return await template.read(uri, params)

        raise ResourceNotFoundError(uri)

    def subscribe(self, uri: str, subscriber_id: str) -> None:
        """Subscribe to resource updates."""
        if uri not in self.subscriptions:
            self.subscriptions[uri] = set()
        self.subscriptions[uri].add(subscriber_id)

    def unsubscribe(self, uri: str, subscriber_id: str) -> None:
        """Unsubscribe from resource updates."""
        if uri in self.subscriptions:
            self.subscriptions[uri].discard(subscriber_id)
            if not self.subscriptions[uri]:
                del self.subscriptions[uri]

    def get_subscribers(self, uri: str) -> Set[str]:
        """Get all subscribers for a resource."""
        return self.subscriptions.get(uri, set())

    def is_healthy(self) -> bool:
        """Check if registry is healthy."""
        return self._healthy

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        return {
            "total_resources": len(self.resources),
            "total_templates": len(self.templates),
            "total_subscriptions": sum(len(subs) for subs in self.subscriptions.values()),
            "healthy": self.is_healthy()
        }

    def clear(self) -> None:
        """Clear all registered resources and templates."""
        self.resources.clear()
        self.templates.clear()
        self.subscriptions.clear()

    def __len__(self) -> int:
        """Return number of registered resources."""
        return len(self.resources) + len(self.templates)

    def __contains__(self, uri: str) -> bool:
        """Check if resource or matching template exists."""
        if uri in self.resources:
            return True
        for template in self.templates.values():
            if template.matches(uri) is not None:
                return True
        return False


# =============================================================================
# Decorators
# =============================================================================

def mcp_resource(
    uri: str,
    name: str,
    description: Optional[str] = None,
    mime_type: Optional[str] = None,
    annotations: Optional[Dict[str, Any]] = None
):
    """Decorator to register a function as an MCP resource.

    Args:
        uri: Unique URI for the resource
        name: Human-readable name
        description: Optional description
        mime_type: MIME type of the resource content
        annotations: Optional annotations (audience, priority, etc.)

    Example:
        @mcp_resource(
            uri="config://app/settings",
            name="Application Settings",
            description="Current application configuration",
            mime_type="application/json"
        )
        def get_settings():
            return {"theme": "dark", "language": "en"}
    """
    def decorator(func: Callable) -> Callable:
        import inspect

        # Build annotations object
        annot = None
        if annotations:
            annot = ResourceAnnotations(
                audience=annotations.get("audience"),
                priority=annotations.get("priority"),
                lastModified=annotations.get("lastModified")
            )

        # Create resource
        resource = Resource(
            uri=uri,
            name=name,
            description=description,
            mimeType=mime_type,
            annotations=annot
        )

        # Create registered resource
        is_async = inspect.iscoroutinefunction(func)
        registered = RegisteredResource(
            resource=resource,
            reader=func,
            is_async=is_async
        )

        # Register globally
        ResourceRegistry.global_registry().register(registered)

        return func

    return decorator


def mcp_resource_template(
    uri_template: str,
    name: str,
    description: Optional[str] = None,
    mime_type: Optional[str] = None,
    annotations: Optional[Dict[str, Any]] = None
):
    """Decorator to register a function as an MCP resource template.

    The function parameters should match the URI template placeholders.

    Args:
        uri_template: URI template with {placeholders}
        name: Human-readable name
        description: Optional description
        mime_type: MIME type of the resource content
        annotations: Optional annotations

    Example:
        @mcp_resource_template(
            uri_template="file:///{path}",
            name="File Reader",
            description="Read files by path",
            mime_type="text/plain"
        )
        def read_file(path: str):
            with open(path) as f:
                return f.read()
    """
    def decorator(func: Callable) -> Callable:
        import inspect

        # Build annotations object
        annot = None
        if annotations:
            annot = ResourceAnnotations(
                audience=annotations.get("audience"),
                priority=annotations.get("priority"),
                lastModified=annotations.get("lastModified")
            )

        # Create template
        template = ResourceTemplate(
            uriTemplate=uri_template,
            name=name,
            description=description,
            mimeType=mime_type,
            annotations=annot
        )

        # Extract parameter names from function signature
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())

        # Create registered template
        is_async = inspect.iscoroutinefunction(func)
        registered = RegisteredTemplate(
            template=template,
            reader=func,
            is_async=is_async,
            param_names=param_names
        )

        # Register globally
        ResourceRegistry.global_registry().register_template(registered)

        return func

    return decorator


# Convenience aliases
resource = mcp_resource
resource_template = mcp_resource_template
