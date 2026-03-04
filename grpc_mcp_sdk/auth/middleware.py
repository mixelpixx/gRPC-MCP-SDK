"""Authentication middleware for gRPC MCP SDK."""

import grpc
from typing import Optional, Dict, Any, Callable
import logging
from .base import AuthHandler, AuthResult, AuthContext, NoAuthHandler
from ..utils.errors import AuthenticationError, ErrorCode

logger = logging.getLogger(__name__)


class AuthMiddleware:
    """Authentication middleware for gRPC services."""
    
    def __init__(self, auth_handler: Optional[AuthHandler] = None):
        """
        Initialize authentication middleware.
        
        Args:
            auth_handler: Authentication handler to use
        """
        self.auth_handler = auth_handler or NoAuthHandler()
    
    async def authenticate_request(self, context: grpc.ServicerContext) -> AuthContext:
        """
        Authenticate an incoming request.
        
        Args:
            context: gRPC service context
            
        Returns:
            AuthContext for the authenticated user
            
        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            result = await self.auth_handler.authenticate(context)
            
            if not result.success:
                logger.warning(f"Authentication failed: {result.error_message}")
                raise AuthenticationError(
                    result.error_message or "Authentication failed"
                )
            
            if result.context.is_expired():
                logger.warning("Authentication token expired")
                raise AuthenticationError("Authentication token expired")
            
            logger.debug(f"Authentication successful for user: {result.context.user_id}")
            return result.context
            
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise AuthenticationError(f"Authentication error: {str(e)}")
    
    def check_tool_permissions(self, auth_context: AuthContext, tool_name: str, required_permissions: list) -> bool:
        """
        Check if user has required permissions for a tool.
        
        Args:
            auth_context: User's authentication context
            tool_name: Name of the tool being accessed
            required_permissions: List of required permissions
            
        Returns:
            True if user has required permissions
        """
        if not required_permissions:
            return True
        
        # Check if user has all required permissions
        has_permissions = all(
            auth_context.has_permission(perm) for perm in required_permissions
        )
        
        if not has_permissions:
            logger.warning(
                f"User {auth_context.user_id} lacks permissions {required_permissions} for tool {tool_name}"
            )
        
        return has_permissions
    
    def create_auth_interceptor(self):
        """Create a gRPC interceptor for authentication."""
        return AuthInterceptor(self)


class AuthInterceptor(grpc.aio.ServerInterceptor):
    """gRPC server interceptor for authentication."""
    
    def __init__(self, auth_middleware: AuthMiddleware):
        self.auth_middleware = auth_middleware
    
    async def intercept_service(self, continuation, handler_call_details):
        """Intercept service calls for authentication."""
        # Skip authentication for certain methods
        method_name = handler_call_details.method
        
        if method_name.endswith('HealthCheck') or method_name.endswith('Initialize'):
            # Skip auth for health checks and initialization
            return await continuation(handler_call_details)
        
        # Create a wrapper handler that includes authentication
        def auth_wrapper(original_handler):
            async def wrapper(request, context):
                try:
                    # Authenticate the request
                    auth_context = await self.auth_middleware.authenticate_request(context)
                    
                    # Add auth context to gRPC context
                    context.auth_context = auth_context
                    
                    # Call the original handler
                    return await original_handler(request, context)
                    
                except AuthenticationError as e:
                    context.abort(grpc.StatusCode.UNAUTHENTICATED, str(e))
                except Exception as e:
                    logger.error(f"Authentication interceptor error: {e}")
                    context.abort(grpc.StatusCode.INTERNAL, "Authentication error")
            
            return wrapper
        
        # Get the original handler
        handler = await continuation(handler_call_details)
        
        # Wrap the handler with authentication
        if hasattr(handler, 'unary_unary'):
            # Unary-unary method
            original_method = handler.unary_unary
            handler.unary_unary = auth_wrapper(original_method)
        elif hasattr(handler, 'unary_stream'):
            # Unary-stream method
            original_method = handler.unary_stream
            handler.unary_stream = auth_wrapper(original_method)
        
        return handler


def create_auth_middleware(auth_handler: Optional[AuthHandler] = None) -> AuthMiddleware:
    """
    Create authentication middleware.
    
    Args:
        auth_handler: Authentication handler to use
        
    Returns:
        AuthMiddleware instance
    """
    return AuthMiddleware(auth_handler)