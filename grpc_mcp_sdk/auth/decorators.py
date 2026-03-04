"""Authentication decorators for tools."""

import functools
import asyncio
from typing import List, Optional, Callable, Any
import grpc
from ..core.registry import ToolRegistry
from ..utils.errors import AuthenticationError
from .base import AuthHandler, AuthContext


def requires_auth(
    permissions: Optional[List[str]] = None,
    auth_handler: Optional[AuthHandler] = None
):
    """
    Decorator to require authentication for a tool.
    
    Args:
        permissions: List of required permissions
        auth_handler: Custom authentication handler
    """
    def decorator(func: Callable) -> Callable:
        # Store auth requirements in function metadata
        func._auth_required = True
        func._auth_permissions = permissions or []
        func._auth_handler = auth_handler
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # The actual authentication will be handled by the server
            # This decorator just marks the function as requiring auth
            return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
        
        # Copy auth metadata to wrapper
        wrapper._auth_required = True
        wrapper._auth_permissions = permissions or []
        wrapper._auth_handler = auth_handler
        
        return wrapper
    
    return decorator


def requires_permission(permission: str):
    """
    Decorator to require a specific permission for a tool.
    
    Args:
        permission: Required permission
    """
    return requires_auth(permissions=[permission])


def admin_only():
    """Decorator to require admin permissions."""
    return requires_auth(permissions=["admin"])


def authenticated_only():
    """Decorator to require any authentication."""
    return requires_auth()


# Helper function to check auth requirements
def check_auth_requirements(func: Callable, auth_context: Optional[AuthContext]) -> bool:
    """
    Check if a function's authentication requirements are met.
    
    Args:
        func: Function to check
        auth_context: Current authentication context
        
    Returns:
        True if requirements are met, False otherwise
    """
    # Check if auth is required
    if not getattr(func, '_auth_required', False):
        return True  # No auth required
    
    # Check if user is authenticated
    if not auth_context:
        return False
    
    # Check permissions
    required_permissions = getattr(func, '_auth_permissions', [])
    if required_permissions:
        return all(auth_context.has_permission(perm) for perm in required_permissions)
    
    return True  # Auth required but no specific permissions


def get_auth_requirements(func: Callable) -> dict:
    """
    Get authentication requirements for a function.
    
    Args:
        func: Function to inspect
        
    Returns:
        Dict with auth requirements
    """
    return {
        'required': getattr(func, '_auth_required', False),
        'permissions': getattr(func, '_auth_permissions', []),
        'handler': getattr(func, '_auth_handler', None)
    }