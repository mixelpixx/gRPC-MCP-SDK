"""Advanced rate limiting implementation for gRPC MCP SDK."""

import time
import asyncio
from typing import Dict, Optional, Tuple, List, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
import threading
import logging

from ..utils.errors import RateLimitError

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_minute: int = 60
    burst_size: int = 10
    window_size: int = 60  # seconds
    per_user: bool = True
    per_tool: bool = False
    per_ip: bool = False
    enabled: bool = True
    
    def __post_init__(self):
        if self.burst_size > self.requests_per_minute:
            self.burst_size = self.requests_per_minute


class TokenBucket:
    """Token bucket implementation for rate limiting."""
    
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.tokens = float(capacity)
        self.refill_rate = refill_rate  # tokens per second
        self.last_refill = time.time()
        self.lock = threading.Lock()
    
    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from the bucket.
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens were consumed, False otherwise
        """
        with self.lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    def _refill(self):
        """Refill the token bucket based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
    
    def get_wait_time(self, tokens: int = 1) -> float:
        """Get the time to wait before tokens are available."""
        with self.lock:
            self._refill()
            if self.tokens >= tokens:
                return 0.0
            needed_tokens = tokens - self.tokens
            return needed_tokens / self.refill_rate


class SlidingWindowCounter:
    """Sliding window counter for rate limiting."""
    
    def __init__(self, window_size: int, max_requests: int):
        self.window_size = window_size
        self.max_requests = max_requests
        self.requests = deque()
        self.lock = threading.Lock()
    
    def is_allowed(self) -> bool:
        """Check if a request is allowed."""
        with self.lock:
            now = time.time()
            
            # Remove old requests outside the window
            while self.requests and self.requests[0] <= now - self.window_size:
                self.requests.popleft()
            
            # Check if we're within the limit
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            
            return False
    
    def get_reset_time(self) -> float:
        """Get the time when the rate limit will reset."""
        with self.lock:
            if not self.requests:
                return 0.0
            return self.requests[0] + self.window_size


class RateLimiter:
    """Advanced rate limiter with multiple strategies."""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.token_buckets: Dict[str, TokenBucket] = {}
        self.sliding_windows: Dict[str, SlidingWindowCounter] = {}
        self.request_counts: Dict[str, List[float]] = defaultdict(list)
        self.lock = threading.Lock()
        
        # Calculate refill rate for token bucket
        self.refill_rate = config.requests_per_minute / 60.0  # per second
    
    def check_rate_limit(
        self,
        user_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_size: int = 1
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if a request is within rate limits.
        
        Args:
            user_id: User identifier
            tool_name: Tool name
            ip_address: IP address
            request_size: Size of the request (for weighted limiting)
            
        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        if not self.config.enabled:
            return True, {}
        
        # Generate keys for different rate limiting strategies
        keys = []
        
        if self.config.per_user and user_id:
            keys.append(f"user:{user_id}")
        
        if self.config.per_tool and tool_name:
            keys.append(f"tool:{tool_name}")
        
        if self.config.per_ip and ip_address:
            keys.append(f"ip:{ip_address}")
        
        # If no specific keys, use a global key
        if not keys:
            keys.append("global")
        
        # Check each key
        for key in keys:
            allowed, info = self._check_key_rate_limit(key, request_size)
            if not allowed:
                return False, {
                    "key": key,
                    "limit": self.config.requests_per_minute,
                    "window": self.config.window_size,
                    "retry_after": info.get("retry_after", 60),
                    **info
                }
        
        return True, {}
    
    def _check_key_rate_limit(self, key: str, request_size: int) -> Tuple[bool, Dict[str, Any]]:
        """Check rate limit for a specific key."""
        with self.lock:
            # Use token bucket for burst handling
            if key not in self.token_buckets:
                self.token_buckets[key] = TokenBucket(
                    capacity=self.config.burst_size,
                    refill_rate=self.refill_rate
                )
            
            bucket = self.token_buckets[key]
            
            # Try to consume tokens
            if bucket.consume(request_size):
                return True, {"tokens_remaining": bucket.tokens}
            
            # Calculate wait time
            wait_time = bucket.get_wait_time(request_size)
            
            return False, {
                "retry_after": wait_time,
                "tokens_remaining": bucket.tokens
            }
    
    def get_rate_limit_status(self, key: str) -> Dict[str, Any]:
        """Get current rate limit status for a key."""
        with self.lock:
            if key not in self.token_buckets:
                return {
                    "limit": self.config.requests_per_minute,
                    "remaining": self.config.burst_size,
                    "reset_time": time.time() + 60
                }
            
            bucket = self.token_buckets[key]
            bucket._refill()  # Update tokens
            
            return {
                "limit": self.config.requests_per_minute,
                "remaining": int(bucket.tokens),
                "reset_time": time.time() + 60,
                "burst_capacity": self.config.burst_size
            }
    
    def reset_rate_limit(self, key: str):
        """Reset rate limit for a specific key."""
        with self.lock:
            if key in self.token_buckets:
                del self.token_buckets[key]
            if key in self.sliding_windows:
                del self.sliding_windows[key]
    
    def get_all_limits(self) -> Dict[str, Dict[str, Any]]:
        """Get rate limit status for all keys."""
        with self.lock:
            results = {}
            for key in self.token_buckets:
                results[key] = self.get_rate_limit_status(key)
            return results
    
    def cleanup_old_entries(self, max_age: int = 3600):
        """Clean up old rate limit entries."""
        with self.lock:
            current_time = time.time()
            keys_to_remove = []
            
            for key, bucket in self.token_buckets.items():
                # Remove buckets that haven't been used recently
                if current_time - bucket.last_refill > max_age:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self.token_buckets[key]
                if key in self.sliding_windows:
                    del self.sliding_windows[key]
            
            if keys_to_remove:
                logger.info(f"Cleaned up {len(keys_to_remove)} old rate limit entries")


class AdaptiveRateLimiter(RateLimiter):
    """Rate limiter that adapts based on server load."""
    
    def __init__(self, config: RateLimitConfig):
        super().__init__(config)
        self.server_load = 0.0
        self.last_load_update = time.time()
        self.load_history = deque(maxlen=100)
    
    def update_server_load(self, cpu_usage: float, memory_usage: float):
        """Update server load metrics."""
        load = (cpu_usage + memory_usage) / 2.0
        self.server_load = load
        self.load_history.append(load)
        self.last_load_update = time.time()
    
    def _get_adaptive_limit(self) -> int:
        """Get adaptive rate limit based on server load."""
        if not self.load_history:
            return self.config.requests_per_minute
        
        avg_load = sum(self.load_history) / len(self.load_history)
        
        # Reduce limit if server is under high load
        if avg_load > 0.8:
            return int(self.config.requests_per_minute * 0.5)
        elif avg_load > 0.6:
            return int(self.config.requests_per_minute * 0.7)
        elif avg_load > 0.4:
            return int(self.config.requests_per_minute * 0.9)
        else:
            return self.config.requests_per_minute
    
    def check_rate_limit(self, **kwargs) -> Tuple[bool, Dict[str, Any]]:
        """Check rate limit with adaptive adjustment."""
        # Update config with adaptive limit
        original_limit = self.config.requests_per_minute
        self.config.requests_per_minute = self._get_adaptive_limit()
        
        try:
            return super().check_rate_limit(**kwargs)
        finally:
            # Restore original limit
            self.config.requests_per_minute = original_limit


def create_rate_limiter(
    requests_per_minute: int = 60,
    burst_size: int = 10,
    per_user: bool = True,
    per_tool: bool = False,
    per_ip: bool = False,
    adaptive: bool = False
) -> RateLimiter:
    """
    Create a rate limiter with the specified configuration.
    
    Args:
        requests_per_minute: Maximum requests per minute
        burst_size: Maximum burst size
        per_user: Enable per-user rate limiting
        per_tool: Enable per-tool rate limiting
        per_ip: Enable per-IP rate limiting
        adaptive: Enable adaptive rate limiting
        
    Returns:
        RateLimiter instance
    """
    config = RateLimitConfig(
        requests_per_minute=requests_per_minute,
        burst_size=burst_size,
        per_user=per_user,
        per_tool=per_tool,
        per_ip=per_ip
    )
    
    if adaptive:
        return AdaptiveRateLimiter(config)
    else:
        return RateLimiter(config)