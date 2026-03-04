"""Input validation utilities for gRPC MCP SDK."""

import re
from typing import Any, Dict, List, Optional, Union
from .errors import ValidationError


def validate_tool_name(name: str) -> str:
    """Validate tool name format."""
    if not name:
        raise ValidationError("Tool name cannot be empty")
    
    if not isinstance(name, str):
        raise ValidationError("Tool name must be a string")
    
    # Tool names should be alphanumeric with underscores and hyphens
    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        raise ValidationError(
            "Tool name must contain only alphanumeric characters, underscores, and hyphens",
            field="name"
        )
    
    if len(name) > 100:
        raise ValidationError("Tool name must be 100 characters or less", field="name")
    
    return name


def validate_parameters(
    parameters: Dict[str, Any],
    schema: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """Validate parameters against schema."""
    validated = {}
    
    # Check required parameters
    for param_name, param_info in schema.items():
        if param_info.get("required", False) and param_name not in parameters:
            raise ValidationError(
                f"Missing required parameter: {param_name}",
                field=param_name
            )
    
    # Validate each parameter
    for param_name, value in parameters.items():
        if param_name not in schema:
            raise ValidationError(
                f"Unknown parameter: {param_name}",
                field=param_name
            )
        
        param_info = schema[param_name]
        validated[param_name] = _validate_parameter_value(
            param_name, value, param_info
        )
    
    return validated


def _validate_parameter_value(
    param_name: str,
    value: Any,
    param_info: Dict[str, Any]
) -> Any:
    """Validate a single parameter value."""
    param_type = param_info.get("type", "string")
    
    if param_type == "string":
        if not isinstance(value, str):
            raise ValidationError(
                f"Parameter '{param_name}' must be a string",
                field=param_name
            )
    elif param_type == "number":
        if not isinstance(value, (int, float)):
            raise ValidationError(
                f"Parameter '{param_name}' must be a number",
                field=param_name
            )
    elif param_type == "boolean":
        if not isinstance(value, bool):
            raise ValidationError(
                f"Parameter '{param_name}' must be a boolean",
                field=param_name
            )
    elif param_type == "object":
        if not isinstance(value, dict):
            raise ValidationError(
                f"Parameter '{param_name}' must be an object",
                field=param_name
            )
    elif param_type == "array":
        if not isinstance(value, list):
            raise ValidationError(
                f"Parameter '{param_name}' must be an array",
                field=param_name
            )
    
    return value


def validate_context(context: Dict[str, str]) -> Dict[str, str]:
    """Validate context metadata."""
    if not isinstance(context, dict):
        raise ValidationError("Context must be a dictionary")
    
    # Validate that all keys and values are strings
    for key, value in context.items():
        if not isinstance(key, str):
            raise ValidationError("Context keys must be strings")
        if not isinstance(value, str):
            raise ValidationError("Context values must be strings")
        if len(key) > 100:
            raise ValidationError("Context keys must be 100 characters or less")
        if len(value) > 1000:
            raise ValidationError("Context values must be 1000 characters or less")
    
    return context


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """Sanitize string input."""
    if not isinstance(value, str):
        raise ValidationError("Value must be a string")
    
    # Remove null bytes and control characters
    value = value.replace('\x00', '')
    value = ''.join(char for char in value if ord(char) >= 32 or char in '\t\n\r')
    
    if len(value) > max_length:
        raise ValidationError(f"String must be {max_length} characters or less")
    
    return value