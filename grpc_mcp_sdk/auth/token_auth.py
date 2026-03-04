"""Token-based authentication handler."""

import grpc
from typing import List, Optional, Dict, Any
import hashlib
import secrets
from .base import AuthHandler, AuthResult, AuthContext


class TokenAuthHandler(AuthHandler):
    """Simple token-based authentication handler."""
    
    def __init__(
        self,
        valid_tokens: List[str],
        permissions_map: Optional[Dict[str, List[str]]] = None,
        user_map: Optional[Dict[str, str]] = None
    ):
        """
        Initialize token authentication handler.
        
        Args:
            valid_tokens: List of valid authentication tokens
            permissions_map: Map of token to permissions list
            user_map: Map of token to user ID
        """
        self.valid_tokens = set(valid_tokens)
        self.permissions_map = permissions_map or {}
        self.user_map = user_map or {}
        
        # Create hashed tokens for security
        self.hashed_tokens = {}
        for token in valid_tokens:
            hashed = hashlib.sha256(token.encode()).hexdigest()
            self.hashed_tokens[hashed] = token
    
    async def authenticate(self, context: grpc.ServicerContext) -> AuthResult:
        """Authenticate using bearer token."""
        credentials = self.extract_credentials(context)
        
        if not credentials:
            return AuthResult.failure_result(
                "Missing authentication token",
                "AUTH_MISSING_TOKEN"
            )
        
        # Handle Bearer token format
        token = credentials
        if credentials.startswith("Bearer "):
            token = credentials[7:]  # Remove "Bearer " prefix
        
        # Check if token is valid
        if token not in self.valid_tokens:
            return AuthResult.failure_result(
                "Invalid authentication token",
                "AUTH_INVALID_TOKEN"
            )
        
        # Get user ID and permissions
        user_id = self.user_map.get(token, f"user_{hashlib.md5(token.encode()).hexdigest()[:8]}")
        permissions = self.permissions_map.get(token, ["basic"])
        
        auth_context = AuthContext(
            user_id=user_id,
            permissions=permissions,
            metadata={"auth_type": "token"}
        )
        
        return AuthResult.success_result(auth_context)
    
    def get_auth_type(self) -> str:
        return "token"
    
    def add_token(self, token: str, user_id: Optional[str] = None, permissions: Optional[List[str]] = None):
        """Add a new valid token."""
        self.valid_tokens.add(token)
        if user_id:
            self.user_map[token] = user_id
        if permissions:
            self.permissions_map[token] = permissions
    
    def remove_token(self, token: str):
        """Remove a token."""
        self.valid_tokens.discard(token)
        self.user_map.pop(token, None)
        self.permissions_map.pop(token, None)
    
    def generate_token(self, user_id: str, permissions: List[str]) -> str:
        """Generate a new secure token."""
        token = secrets.token_urlsafe(32)
        self.add_token(token, user_id, permissions)
        return token


def create_token_auth(
    tokens: List[str],
    permissions_map: Optional[Dict[str, List[str]]] = None,
    user_map: Optional[Dict[str, str]] = None
) -> TokenAuthHandler:
    """
    Create a token authentication handler.
    
    Args:
        tokens: List of valid tokens
        permissions_map: Map tokens to permissions
        user_map: Map tokens to user IDs
        
    Returns:
        TokenAuthHandler instance
    """
    return TokenAuthHandler(tokens, permissions_map, user_map)