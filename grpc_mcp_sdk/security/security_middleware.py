"""Comprehensive security middleware for gRPC MCP SDK."""

import grpc
import time
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .rate_limiter import RateLimiter, RateLimitConfig
from .input_sanitizer import InputSanitizer, SanitizationConfig
from ..auth.base import AuthHandler, AuthContext
from ..auth.middleware import AuthMiddleware
from ..utils.errors import RateLimitError, ValidationError, AuthenticationError

logger = logging.getLogger(__name__)


@dataclass
class SecurityConfig:
    """Configuration for security middleware."""
    # Rate limiting
    enable_rate_limiting: bool = True
    rate_limit_config: RateLimitConfig = None
    
    # Input sanitization
    enable_input_sanitization: bool = True
    sanitization_config: SanitizationConfig = None
    
    # Request validation
    enable_request_validation: bool = True
    max_request_size: int = 1024 * 1024  # 1MB
    
    # Security headers
    enable_security_headers: bool = True
    
    # Logging
    enable_security_logging: bool = True
    log_failed_requests: bool = True
    
    def __post_init__(self):
        if self.rate_limit_config is None:
            self.rate_limit_config = RateLimitConfig()
        if self.sanitization_config is None:
            self.sanitization_config = SanitizationConfig()


class SecurityMiddleware:
    """Comprehensive security middleware."""
    
    def __init__(
        self,
        auth_handler: Optional[AuthHandler] = None,
        config: Optional[SecurityConfig] = None
    ):
        self.config = config or SecurityConfig()
        self.auth_middleware = AuthMiddleware(auth_handler)
        
        # Initialize security components
        if self.config.enable_rate_limiting:
            from .rate_limiter import RateLimiter
            self.rate_limiter = RateLimiter(self.config.rate_limit_config)
        else:
            self.rate_limiter = None
        
        if self.config.enable_input_sanitization:
            self.input_sanitizer = InputSanitizer(self.config.sanitization_config)
        else:
            self.input_sanitizer = None
        
        # Security metrics
        self.security_metrics = {
            "requests_processed": 0,
            "requests_blocked": 0,
            "rate_limit_violations": 0,
            "sanitization_violations": 0,
            "auth_failures": 0
        }
    
    async def process_request(
        self,
        context: grpc.ServicerContext,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> tuple[AuthContext, Dict[str, Any]]:
        """
        Process a request through all security layers.
        
        Args:
            context: gRPC context
            tool_name: Name of the tool being called
            arguments: Tool arguments
            
        Returns:
            Tuple of (auth_context, sanitized_arguments)
            
        Raises:
            AuthenticationError: If authentication fails
            RateLimitError: If rate limit is exceeded
            ValidationError: If input validation fails
        """
        start_time = time.time()
        
        try:
            # 1. Authenticate request
            auth_context = await self.auth_middleware.authenticate_request(context)
            
            # 2. Check rate limits
            if self.rate_limiter:
                self._check_rate_limits(auth_context, tool_name, context)
            
            # 3. Validate request size
            if self.config.enable_request_validation:
                self._validate_request_size(arguments)
            
            # 4. Sanitize input
            sanitized_arguments = arguments
            if self.input_sanitizer:
                sanitized_arguments = self._sanitize_input(arguments)
            
            # 5. Log security event
            if self.config.enable_security_logging:
                self._log_security_event(
                    "REQUEST_ALLOWED",
                    auth_context,
                    tool_name,
                    time.time() - start_time
                )
            
            self.security_metrics["requests_processed"] += 1
            return auth_context, sanitized_arguments
            
        except (AuthenticationError, RateLimitError, ValidationError) as e:
            # Log security violation
            if self.config.log_failed_requests:
                self._log_security_violation(str(e), tool_name, context)
            
            self.security_metrics["requests_blocked"] += 1
            
            if isinstance(e, RateLimitError):
                self.security_metrics["rate_limit_violations"] += 1
            elif isinstance(e, ValidationError):
                self.security_metrics["sanitization_violations"] += 1
            elif isinstance(e, AuthenticationError):
                self.security_metrics["auth_failures"] += 1
            
            raise
    
    def _check_rate_limits(
        self,
        auth_context: AuthContext,
        tool_name: str,
        grpc_context: grpc.ServicerContext
    ):
        """Check rate limits for the request."""
        # Get client IP
        peer_info = grpc_context.peer()
        ip_address = self._extract_ip_from_peer(peer_info)
        
        # Check rate limit
        allowed, info = self.rate_limiter.check_rate_limit(
            user_id=auth_context.user_id,
            tool_name=tool_name,
            ip_address=ip_address
        )
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for user {auth_context.user_id}: {info}")
            raise RateLimitError(
                info.get('limit', 60),
                info.get('window', 60)
            )
    
    def _validate_request_size(self, arguments: Dict[str, Any]):
        """Validate request size."""
        import sys
        
        request_size = sys.getsizeof(str(arguments))
        if request_size > self.config.max_request_size:
            raise ValidationError(
                f"Request too large: {request_size} > {self.config.max_request_size}"
            )
    
    def _sanitize_input(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize input arguments."""
        try:
            return self.input_sanitizer.sanitize_input(arguments)
        except Exception as e:
            raise ValidationError(f"Input sanitization failed: {str(e)}")
    
    def _extract_ip_from_peer(self, peer_info: str) -> str:
        """Extract IP address from gRPC peer info."""
        # peer_info format: "ipv4:192.168.1.1:12345" or "ipv6:[::1]:12345"
        if peer_info.startswith("ipv4:"):
            return peer_info.split(":")[1]
        elif peer_info.startswith("ipv6:"):
            # Extract IPv6 address between brackets
            start = peer_info.find("[") + 1
            end = peer_info.find("]")
            return peer_info[start:end]
        else:
            return "unknown"
    
    def _log_security_event(
        self,
        event_type: str,
        auth_context: AuthContext,
        tool_name: str,
        processing_time: float
    ):
        """Log security event."""
        logger.info(
            f"Security event: {event_type} | "
            f"User: {auth_context.user_id} | "
            f"Tool: {tool_name} | "
            f"Time: {processing_time:.3f}s"
        )
    
    def _log_security_violation(
        self,
        violation: str,
        tool_name: str,
        context: grpc.ServicerContext
    ):
        """Log security violation."""
        peer_info = context.peer()
        ip_address = self._extract_ip_from_peer(peer_info)
        
        logger.warning(
            f"Security violation: {violation} | "
            f"Tool: {tool_name} | "
            f"IP: {ip_address}"
        )
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """Get security metrics."""
        metrics = self.security_metrics.copy()
        
        if self.rate_limiter:
            metrics["rate_limiter_status"] = self.rate_limiter.get_all_limits()
        
        return metrics
    
    def reset_security_metrics(self):
        """Reset security metrics."""
        self.security_metrics = {
            "requests_processed": 0,
            "requests_blocked": 0,
            "rate_limit_violations": 0,
            "sanitization_violations": 0,
            "auth_failures": 0
        }
    
    def create_security_interceptor(self):
        """Create a gRPC interceptor for security."""
        return SecurityInterceptor(self)


class SecurityInterceptor(grpc.aio.ServerInterceptor):
    """gRPC server interceptor for security."""
    
    def __init__(self, security_middleware: SecurityMiddleware):
        self.security_middleware = security_middleware
    
    async def intercept_service(self, continuation, handler_call_details):
        """Intercept service calls for security processing."""
        method_name = handler_call_details.method
        
        # Skip security for certain methods
        if method_name.endswith(('HealthCheck', 'Initialize')):
            return await continuation(handler_call_details)
        
        # Create a wrapper handler that includes security
        def security_wrapper(original_handler):
            async def wrapper(request, context):
                try:
                    # Extract tool name from method
                    tool_name = method_name.split('/')[-1]
                    
                    # Get arguments from request
                    arguments = {}
                    if hasattr(request, 'arguments'):
                        from google.protobuf.json_format import MessageToDict
                        arguments = MessageToDict(request.arguments)
                    
                    # Process through security middleware
                    auth_context, sanitized_args = await self.security_middleware.process_request(
                        context, tool_name, arguments
                    )
                    
                    # Add security context to gRPC context
                    context.auth_context = auth_context
                    context.sanitized_arguments = sanitized_args
                    
                    # Call the original handler
                    return await original_handler(request, context)
                    
                except AuthenticationError as e:
                    context.abort(grpc.StatusCode.UNAUTHENTICATED, str(e))
                except RateLimitError as e:
                    context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, str(e))
                except ValidationError as e:
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))
                except Exception as e:
                    logger.error(f"Security interceptor error: {e}")
                    context.abort(grpc.StatusCode.INTERNAL, "Security error")
            
            return wrapper
        
        # Get the original handler
        handler = await continuation(handler_call_details)
        
        # Wrap the handler with security
        if hasattr(handler, 'unary_unary'):
            original_method = handler.unary_unary
            handler.unary_unary = security_wrapper(original_method)
        elif hasattr(handler, 'unary_stream'):
            original_method = handler.unary_stream
            handler.unary_stream = security_wrapper(original_method)
        
        return handler


def create_security_middleware(
    auth_handler: Optional[AuthHandler] = None,
    enable_rate_limiting: bool = True,
    enable_input_sanitization: bool = True,
    requests_per_minute: int = 60,
    max_string_length: int = 10000
) -> SecurityMiddleware:
    """
    Create security middleware with common configuration.
    
    Args:
        auth_handler: Authentication handler
        enable_rate_limiting: Enable rate limiting
        enable_input_sanitization: Enable input sanitization
        requests_per_minute: Rate limit threshold
        max_string_length: Maximum string length
        
    Returns:
        SecurityMiddleware instance
    """
    config = SecurityConfig(
        enable_rate_limiting=enable_rate_limiting,
        enable_input_sanitization=enable_input_sanitization,
        rate_limit_config=RateLimitConfig(
            requests_per_minute=requests_per_minute
        ),
        sanitization_config=SanitizationConfig(
            max_string_length=max_string_length
        )
    )
    
    return SecurityMiddleware(auth_handler, config)