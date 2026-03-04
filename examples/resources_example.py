"""
MCP Resources example demonstrating static and template resources.

Resources are data that clients can read. They have URIs and can be:
- Static: Fixed URI, returns data from a function
- Templates: URI with placeholders, parameters extracted from URI

Run with:
    python examples/resources_example.py

Or use stdio for Claude Desktop:
    grpc-mcp stdio --module examples.resources_example
"""
import asyncio
import json
import logging
import os
from datetime import datetime

from grpc_mcp_sdk import run_server
from grpc_mcp_sdk.core import mcp_resource, mcp_resource_template, ResourceRegistry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Static resource: Application configuration
@mcp_resource(
    uri="config://app/settings",
    name="Application Settings",
    description="Current application configuration",
    mime_type="application/json"
)
def get_settings():
    """Return application settings as JSON."""
    return {
        "app_name": "MCP Resources Demo",
        "version": "1.0.0",
        "debug": True,
        "max_connections": 100,
        "timeout_seconds": 30
    }


# Static resource: System status
@mcp_resource(
    uri="status://system/health",
    name="System Health",
    description="Current system health metrics",
    mime_type="application/json"
)
def get_system_health():
    """Return system health metrics."""
    import platform
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "uptime_seconds": 3600  # Example value
    }


# Static resource: Text file
@mcp_resource(
    uri="file:///readme",
    name="README",
    description="Application readme text",
    mime_type="text/plain"
)
def get_readme():
    """Return readme text."""
    return """
MCP Resources Example
=====================

This example demonstrates how to create MCP resources using the gRPC MCP SDK.

Resources can expose:
- Configuration data
- System status
- File contents
- Database records
- API responses

Clients can read resources and subscribe to updates.
"""


# Async static resource: External data
@mcp_resource(
    uri="data://external/api",
    name="External API Data",
    description="Data fetched from external source",
    mime_type="application/json"
)
async def get_external_data():
    """Simulate fetching data from an external API."""
    await asyncio.sleep(0.1)  # Simulate network delay
    return {
        "source": "external_api",
        "data": [
            {"id": 1, "value": "item_1"},
            {"id": 2, "value": "item_2"},
            {"id": 3, "value": "item_3"}
        ],
        "fetched_at": datetime.now().isoformat()
    }


# Resource template: User by ID
@mcp_resource_template(
    uri_template="db://users/{user_id}",
    name="User Record",
    description="Fetch user record by ID",
    mime_type="application/json"
)
def get_user(user_id: str):
    """Return user data for the given ID."""
    # Simulated user database
    users = {
        "1": {"id": "1", "name": "Alice", "email": "alice@example.com", "role": "admin"},
        "2": {"id": "2", "name": "Bob", "email": "bob@example.com", "role": "user"},
        "3": {"id": "3", "name": "Charlie", "email": "charlie@example.com", "role": "user"}
    }

    if user_id in users:
        return users[user_id]
    else:
        return {"error": "User not found", "user_id": user_id}


# Resource template: File by path
@mcp_resource_template(
    uri_template="file:///{path}",
    name="File Reader",
    description="Read file contents by path",
    mime_type="text/plain"
)
def read_file(path: str):
    """Read and return file contents."""
    # Security: Only allow reading from specific directories
    allowed_dirs = ["/tmp", os.path.expanduser("~")]

    full_path = os.path.abspath(path)
    is_allowed = any(full_path.startswith(d) for d in allowed_dirs)

    if not is_allowed:
        return f"Access denied: {path}"

    try:
        with open(full_path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return f"File not found: {path}"
    except Exception as e:
        return f"Error reading file: {e}"


# Resource template: Configuration by key
@mcp_resource_template(
    uri_template="config://app/{key}",
    name="Configuration Value",
    description="Get specific configuration value",
    mime_type="application/json"
)
def get_config_value(key: str):
    """Return a specific configuration value."""
    config = {
        "database": {
            "host": "localhost",
            "port": 5432,
            "name": "myapp"
        },
        "cache": {
            "enabled": True,
            "ttl_seconds": 300
        },
        "logging": {
            "level": "INFO",
            "format": "json"
        }
    }

    if key in config:
        return config[key]
    else:
        return {"error": f"Unknown config key: {key}", "available": list(config.keys())}


# Resource template: Log entries by date
@mcp_resource_template(
    uri_template="logs://{date}/{level}",
    name="Log Entries",
    description="Fetch log entries by date and level",
    mime_type="application/json"
)
def get_logs(date: str, level: str):
    """Return log entries for the specified date and level."""
    # Simulated log data
    sample_logs = [
        {"timestamp": f"{date}T10:00:00Z", "level": level.upper(), "message": "Application started"},
        {"timestamp": f"{date}T10:05:00Z", "level": level.upper(), "message": "Database connected"},
        {"timestamp": f"{date}T10:10:00Z", "level": level.upper(), "message": "Ready to serve requests"}
    ]

    return {
        "date": date,
        "level": level,
        "entries": sample_logs,
        "count": len(sample_logs)
    }


def print_registered_resources():
    """Print all registered resources for reference."""
    registry = ResourceRegistry.global_registry()

    logger.info("Registered static resources:")
    for resource in registry.list_resources():
        logger.info(f"  - {resource.uri}: {resource.name}")

    logger.info("Registered resource templates:")
    for template in registry.list_templates():
        logger.info(f"  - {template.uriTemplate}: {template.name}")


if __name__ == "__main__":
    print_registered_resources()

    logger.info("Starting gRPC MCP server with resources...")
    logger.info("Connect a client and use resources/list to see available resources")
    logger.info("Use resources/read with a URI to fetch resource contents")

    asyncio.run(run_server(
        host="0.0.0.0",
        port=50051,
        server_name="Resources-Example-Server",
        version="1.0.0"
    ))
