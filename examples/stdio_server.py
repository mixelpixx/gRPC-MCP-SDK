"""
Stdio MCP server example for Claude Desktop integration.

This example demonstrates how to create an MCP server that communicates
over stdin/stdout, which is the transport method used by Claude Desktop.

To use with Claude Desktop, add to your claude_desktop_config.json:

{
  "mcpServers": {
    "example-server": {
      "command": "python",
      "args": ["/path/to/examples/stdio_server.py"]
    }
  }
}

Or using the CLI:

{
  "mcpServers": {
    "example-server": {
      "command": "grpc-mcp",
      "args": ["stdio", "--module", "examples.stdio_server"]
    }
  }
}
"""
import asyncio
import logging
import os
import sys
from datetime import datetime

# Configure logging to stderr (stdout is used for MCP communication)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

from grpc_mcp_sdk import mcp_tool, MCPToolResult, run_stdio_server
from grpc_mcp_sdk.core import mcp_resource, mcp_prompt


# Tools
@mcp_tool(description="Get the current date and time")
def get_current_time(timezone: str = "UTC") -> MCPToolResult:
    """Return the current date and time."""
    now = datetime.now()
    return MCPToolResult().add_json({
        "datetime": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "timezone": timezone
    })


@mcp_tool(description="Calculate a mathematical expression")
def calculate(expression: str) -> MCPToolResult:
    """Evaluate a mathematical expression safely."""
    # Only allow safe math operations
    allowed_chars = set("0123456789+-*/.() ")
    if not all(c in allowed_chars for c in expression):
        result = MCPToolResult()
        result.add_error("INVALID_INPUT", "Expression contains invalid characters")
        return result

    try:
        # Evaluate the expression
        value = eval(expression)
        return MCPToolResult().add_json({
            "expression": expression,
            "result": value
        })
    except Exception as e:
        result = MCPToolResult()
        result.add_error("EVAL_ERROR", f"Failed to evaluate: {e}")
        return result


@mcp_tool(description="List files in a directory")
def list_files(path: str = ".", include_hidden: bool = False) -> MCPToolResult:
    """List files in the specified directory."""
    try:
        entries = os.listdir(path)
        if not include_hidden:
            entries = [e for e in entries if not e.startswith('.')]

        files = []
        dirs = []
        for entry in sorted(entries):
            full_path = os.path.join(path, entry)
            if os.path.isdir(full_path):
                dirs.append(entry)
            else:
                files.append(entry)

        return MCPToolResult().add_json({
            "path": os.path.abspath(path),
            "directories": dirs,
            "files": files,
            "total": len(entries)
        })
    except Exception as e:
        result = MCPToolResult()
        result.add_error("LIST_ERROR", str(e))
        return result


@mcp_tool(description="Read a text file")
def read_text_file(path: str, max_lines: int = 100) -> MCPToolResult:
    """Read contents of a text file."""
    try:
        with open(path, 'r') as f:
            lines = f.readlines()

        if len(lines) > max_lines:
            content = ''.join(lines[:max_lines])
            truncated = True
        else:
            content = ''.join(lines)
            truncated = False

        result = MCPToolResult()
        result.add_text(content)
        result.add_json({
            "path": os.path.abspath(path),
            "lines": len(lines),
            "truncated": truncated,
            "max_lines": max_lines if truncated else None
        })
        return result
    except Exception as e:
        result = MCPToolResult()
        result.add_error("READ_ERROR", str(e))
        return result


# Resources
@mcp_resource(
    uri="env://variables",
    name="Environment Variables",
    description="Current environment variables (filtered)",
    mime_type="application/json"
)
def get_env_vars():
    """Return safe environment variables."""
    safe_vars = {}
    for key, value in os.environ.items():
        # Filter out sensitive variables
        if any(s in key.lower() for s in ['secret', 'password', 'token', 'key', 'auth']):
            continue
        safe_vars[key] = value
    return safe_vars


@mcp_resource(
    uri="system://info",
    name="System Information",
    description="Basic system information",
    mime_type="application/json"
)
def get_system_info():
    """Return system information."""
    import platform
    return {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "hostname": platform.node(),
        "python_version": platform.python_version(),
        "cwd": os.getcwd()
    }


# Prompts
@mcp_prompt(description="Generate a file analysis prompt")
def analyze_file(filename: str, analysis_type: str = "general"):
    """Generate a prompt for analyzing a file."""
    types = {
        "general": "Provide a general analysis of the file contents.",
        "security": "Analyze for potential security issues.",
        "performance": "Identify performance concerns.",
        "documentation": "Suggest documentation improvements."
    }
    instruction = types.get(analysis_type, types["general"])

    return f"""Analyze the file '{filename}'.

{instruction}

Provide specific, actionable feedback with line references where applicable."""


@mcp_prompt(description="Generate a code explanation prompt")
def explain_code(code: str, detail_level: str = "medium"):
    """Generate a prompt for explaining code."""
    levels = {
        "brief": "Provide a brief one-paragraph explanation.",
        "medium": "Explain the code with moderate detail, covering main concepts.",
        "detailed": "Provide a detailed line-by-line explanation."
    }
    instruction = levels.get(detail_level, levels["medium"])

    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": f"Explain the following code:\n\n```\n{code}\n```\n\n{instruction}"
            }
        }
    ]


if __name__ == "__main__":
    logger.info("Starting stdio MCP server...")
    asyncio.run(run_stdio_server(
        server_name="stdio-example-server",
        server_version="1.0.0"
    ))
