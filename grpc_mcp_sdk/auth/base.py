"""Base authentication classes and interfaces."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import time
import grpc


@dataclass
class AuthContext:
    """Context information for authentication."""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    permissions: List[str] = None
    metadata: Dict[str, Any] = None
    authenticated_at: float = None
    expires_at: Optional[float] = None
    
    def __post_init__(self):
        if self.permissions is None:
            self.permissions = []
        if self.metadata is None:
            self.metadata = {}
        if self.authenticated_at is None:
            self.authenticated_at = time.time()
    
    def is_expired(self) -> bool:
        """Check if authentication is expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        return permission in self.permissions
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "permissions": self.permissions,
            "metadata": self.metadata,
            "authenticated_at": self.authenticated_at,
            "expires_at": self.expires_at
        }


@dataclass
class AuthResult:
    """Result of authentication attempt."""
    success: bool
    context: Optional[AuthContext] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    
    @classmethod
    def success_result(cls, context: AuthContext) -> "AuthResult":
        """Create a successful authentication result."""
        return cls(success=True, context=context)
    
    @classmethod
    def failure_result(cls, error_message: str, error_code: str = "AUTH_FAILED") -> "AuthResult":
        """Create a failed authentication result."""
        return cls(success=False, error_message=error_message, error_code=error_code)


class AuthHandler(ABC):
    """Abstract base class for authentication handlers."""
    
    @abstractmethod
    async def authenticate(self, context: grpc.ServicerContext) -> AuthResult:
        """
        Authenticate a request.
        
        Args:
            context: gRPC context containing metadata
            
        Returns:
            AuthResult with authentication outcome
        """
        pass
    
    @abstractmethod
    def get_auth_type(self) -> str:
        """Get the authentication type identifier."""
        pass
    
    def extract_credentials(self, context: grpc.ServicerContext) -> Optional[str]:
        """Extract credentials from gRPC context metadata."""
        metadata = dict(context.invocation_metadata())
        
        # Try different metadata keys
        for key in ['authorization', 'auth', 'token', 'api-key']:
            if key in metadata:
                return metadata[key]
        
        return None
    
    def validate_permissions(self, auth_context: AuthContext, required_permissions: List[str]) -> bool:
        """Validate if user has required permissions."""
        if not required_permissions:
            return True
        
        return all(auth_context.has_permission(perm) for perm in required_permissions)


class NoAuthHandler(AuthHandler):
    """No-op authentication handler that allows all requests."""
    
    async def authenticate(self, context: grpc.ServicerContext) -> AuthResult:
        """Always return successful authentication."""
        auth_context = AuthContext(
            user_id="anonymous",
            permissions=["*"]  # Allow all permissions
        )
        return AuthResult.success_result(auth_context)
    
    def get_auth_type(self) -> str:
        return "none"


class MultiAuthHandler(AuthHandler):
    """Handler that supports multiple authentication methods."""
    
    def __init__(self, handlers: List[AuthHandler]):
        self.handlers = handlers
    
    async def authenticate(self, context: grpc.ServicerContext) -> AuthResult:
        """Try each authentication handler in order."""
        for handler in self.handlers:
            try:
                result = await handler.authenticate(context)
                if result.success:
                    return result
            except Exception:
                continue  # Try next handler
        
        return AuthResult.failure_result(
            "Authentication failed with all available methods",
            "AUTH_FAILED"
        )
    
    def get_auth_type(self) -> str:
        return "multi"