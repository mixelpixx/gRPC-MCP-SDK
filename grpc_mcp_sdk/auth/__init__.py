"""Authentication and authorization framework for gRPC MCP SDK."""

from .base import AuthHandler, AuthResult, AuthContext
from .token_auth import TokenAuthHandler, create_token_auth
from .api_key_auth import APIKeyAuthHandler, create_api_key_auth
from .jwt_auth import JWTAuthHandler, create_jwt_auth
from .decorators import requires_auth, requires_permission
from .middleware import AuthMiddleware

__all__ = [
    # Base classes
    'AuthHandler',
    'AuthResult',
    'AuthContext',
    
    # Token authentication
    'TokenAuthHandler',
    'create_token_auth',
    
    # API key authentication
    'APIKeyAuthHandler',
    'create_api_key_auth',
    
    # JWT authentication
    'JWTAuthHandler',
    'create_jwt_auth',
    
    # Decorators
    'requires_auth',
    'requires_permission',
    
    # Middleware
    'AuthMiddleware',
]