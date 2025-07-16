"""API Key authentication handler."""

import grpc
from typing import List, Optional, Dict, Any
import hashlib
import secrets
from .base import AuthHandler, AuthResult, AuthContext


class APIKeyAuthHandler(AuthHandler):
    """API Key authentication handler."""
    
    def __init__(
        self,
        api_keys: Dict[str, Dict[str, Any]],
        header_name: str = "x-api-key"
    ):
        """
        Initialize API key authentication handler.
        
        Args:
            api_keys: Dict mapping API keys to their metadata
                     Format: {api_key: {"user_id": str, "permissions": List[str], "name": str}}
            header_name: HTTP header name for API key
        """
        self.api_keys = api_keys
        self.header_name = header_name.lower()
        
        # Create hashed keys for security
        self.hashed_keys = {}
        for key, info in api_keys.items():
            hashed = hashlib.sha256(key.encode()).hexdigest()
            self.hashed_keys[hashed] = (key, info)
    
    async def authenticate(self, context: grpc.ServicerContext) -> AuthResult:
        """Authenticate using API key."""
        metadata = dict(context.invocation_metadata())
        
        # Try to get API key from various headers
        api_key = None
        for key in [self.header_name, 'authorization', 'api-key']:
            if key in metadata:
                api_key = metadata[key]
                break
        
        if not api_key:
            return AuthResult.failure_result(
                f"Missing API key in {self.header_name} header",
                "AUTH_MISSING_API_KEY"
            )
        
        # Handle "ApiKey" prefix
        if api_key.startswith("ApiKey "):
            api_key = api_key[7:]
        
        # Check if API key is valid
        if api_key not in self.api_keys:
            return AuthResult.failure_result(
                "Invalid API key",
                "AUTH_INVALID_API_KEY"
            )
        
        key_info = self.api_keys[api_key]
        
        auth_context = AuthContext(
            user_id=key_info.get("user_id", f"api_user_{hashlib.md5(api_key.encode()).hexdigest()[:8]}"),
            permissions=key_info.get("permissions", ["basic"]),
            metadata={
                "auth_type": "api_key",
                "key_name": key_info.get("name", "unnamed"),
                "key_id": hashlib.md5(api_key.encode()).hexdigest()[:8]
            }
        )
        
        return AuthResult.success_result(auth_context)
    
    def get_auth_type(self) -> str:
        return "api_key"
    
    def add_api_key(
        self,
        user_id: str,
        permissions: List[str],
        name: str = "unnamed"
    ) -> str:
        """Generate and add a new API key."""
        api_key = self._generate_api_key()
        self.api_keys[api_key] = {
            "user_id": user_id,
            "permissions": permissions,
            "name": name
        }
        return api_key
    
    def remove_api_key(self, api_key: str):
        """Remove an API key."""
        self.api_keys.pop(api_key, None)
    
    def update_api_key(self, api_key: str, **updates):
        """Update API key metadata."""
        if api_key in self.api_keys:
            self.api_keys[api_key].update(updates)
    
    def list_api_keys(self) -> List[Dict[str, Any]]:
        """List all API keys with metadata (keys are hashed)."""
        result = []
        for key, info in self.api_keys.items():
            result.append({
                "key_id": hashlib.md5(key.encode()).hexdigest()[:8],
                "user_id": info.get("user_id"),
                "permissions": info.get("permissions", []),
                "name": info.get("name", "unnamed")
            })
        return result
    
    def _generate_api_key(self) -> str:
        """Generate a secure API key."""
        # Generate key with prefix for easy identification
        return f"mcp_{secrets.token_urlsafe(32)}"


def create_api_key_auth(
    api_keys: Optional[Dict[str, Dict[str, Any]]] = None,
    header_name: str = "x-api-key"
) -> APIKeyAuthHandler:
    """
    Create an API key authentication handler.
    
    Args:
        api_keys: Dict of API keys to metadata
        header_name: Header name for API key
        
    Returns:
        APIKeyAuthHandler instance
    """
    return APIKeyAuthHandler(api_keys or {}, header_name)