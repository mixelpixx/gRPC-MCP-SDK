"""JWT (JSON Web Token) authentication handler."""

import grpc
from typing import List, Optional, Dict, Any
import time
import json
import base64
import hmac
import hashlib
from .base import AuthHandler, AuthResult, AuthContext


class JWTAuthHandler(AuthHandler):
    """JWT authentication handler."""
    
    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        verify_exp: bool = True,
        verify_iat: bool = True,
        leeway: int = 0
    ):
        """
        Initialize JWT authentication handler.
        
        Args:
            secret_key: Secret key for JWT signing/verification
            algorithm: JWT algorithm (only HS256 supported currently)
            verify_exp: Verify expiration time
            verify_iat: Verify issued at time
            leeway: Leeway for time-based claims (seconds)
        """
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.verify_exp = verify_exp
        self.verify_iat = verify_iat
        self.leeway = leeway
        
        if algorithm != "HS256":
            raise ValueError("Only HS256 algorithm is currently supported")
    
    async def authenticate(self, context: grpc.ServicerContext) -> AuthResult:
        """Authenticate using JWT token."""
        credentials = self.extract_credentials(context)
        
        if not credentials:
            return AuthResult.failure_result(
                "Missing JWT token",
                "AUTH_MISSING_JWT"
            )
        
        # Handle Bearer token format
        token = credentials
        if credentials.startswith("Bearer "):
            token = credentials[7:]
        
        try:
            payload = self._decode_jwt(token)
        except Exception as e:
            return AuthResult.failure_result(
                f"Invalid JWT token: {str(e)}",
                "AUTH_INVALID_JWT"
            )
        
        # Extract user information from payload
        user_id = payload.get("sub") or payload.get("user_id")
        permissions = payload.get("permissions", ["basic"])
        
        auth_context = AuthContext(
            user_id=user_id,
            permissions=permissions,
            metadata={
                "auth_type": "jwt",
                "jwt_payload": payload
            },
            expires_at=payload.get("exp")
        )
        
        return AuthResult.success_result(auth_context)
    
    def get_auth_type(self) -> str:
        return "jwt"
    
    def generate_token(
        self,
        user_id: str,
        permissions: List[str],
        expires_in: int = 3600,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a JWT token.
        
        Args:
            user_id: User identifier
            permissions: List of permissions
            expires_in: Token expiration time in seconds
            additional_claims: Additional JWT claims
            
        Returns:
            JWT token string
        """
        now = int(time.time())
        
        payload = {
            "sub": user_id,
            "permissions": permissions,
            "iat": now,
            "exp": now + expires_in
        }
        
        if additional_claims:
            payload.update(additional_claims)
        
        return self._encode_jwt(payload)
    
    def _encode_jwt(self, payload: Dict[str, Any]) -> str:
        """Encode JWT token."""
        header = {
            "typ": "JWT",
            "alg": self.algorithm
        }
        
        # Encode header and payload
        header_encoded = self._base64_encode(json.dumps(header))
        payload_encoded = self._base64_encode(json.dumps(payload))
        
        # Create signature
        message = f"{header_encoded}.{payload_encoded}"
        signature = self._create_signature(message)
        
        return f"{message}.{signature}"
    
    def _decode_jwt(self, token: str) -> Dict[str, Any]:
        """Decode and verify JWT token."""
        try:
            header_b64, payload_b64, signature_b64 = token.split(".")
        except ValueError:
            raise ValueError("Invalid JWT format")
        
        # Verify signature
        message = f"{header_b64}.{payload_b64}"
        expected_signature = self._create_signature(message)
        
        if not hmac.compare_digest(signature_b64, expected_signature):
            raise ValueError("Invalid JWT signature")
        
        # Decode payload
        payload = json.loads(self._base64_decode(payload_b64))
        
        # Verify time-based claims
        now = time.time()
        
        if self.verify_exp and "exp" in payload:
            if now > payload["exp"] + self.leeway:
                raise ValueError("JWT token has expired")
        
        if self.verify_iat and "iat" in payload:
            if now < payload["iat"] - self.leeway:
                raise ValueError("JWT token used before issued")
        
        return payload
    
    def _create_signature(self, message: str) -> str:
        """Create HMAC signature for JWT."""
        signature = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).digest()
        return self._base64_encode(signature, padding=False)
    
    def _base64_encode(self, data: Any, padding: bool = True) -> str:
        """Base64 encode data."""
        if isinstance(data, str):
            data = data.encode()
        elif not isinstance(data, bytes):
            data = str(data).encode()
        
        encoded = base64.urlsafe_b64encode(data).decode()
        if not padding:
            encoded = encoded.rstrip('=')
        return encoded
    
    def _base64_decode(self, data: str) -> str:
        """Base64 decode data."""
        # Add padding if needed
        missing_padding = len(data) % 4
        if missing_padding:
            data += '=' * (4 - missing_padding)
        
        return base64.urlsafe_b64decode(data).decode()


def create_jwt_auth(
    secret_key: str,
    algorithm: str = "HS256",
    verify_exp: bool = True,
    verify_iat: bool = True,
    leeway: int = 0
) -> JWTAuthHandler:
    """
    Create a JWT authentication handler.
    
    Args:
        secret_key: Secret key for JWT signing/verification
        algorithm: JWT algorithm
        verify_exp: Verify expiration time
        verify_iat: Verify issued at time
        leeway: Leeway for time-based claims
        
    Returns:
        JWTAuthHandler instance
    """
    return JWTAuthHandler(secret_key, algorithm, verify_exp, verify_iat, leeway)