"""Input sanitization and validation for gRPC MCP SDK."""

import re
import html
import json
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
import logging

from ..utils.errors import ValidationError

logger = logging.getLogger(__name__)


@dataclass
class SanitizationConfig:
    """Configuration for input sanitization."""
    max_string_length: int = 10000
    max_json_depth: int = 10
    max_array_length: int = 1000
    max_dict_keys: int = 100
    allow_html: bool = False
    allow_scripts: bool = False
    strip_control_chars: bool = True
    normalize_unicode: bool = True
    
    # Regex patterns for dangerous content
    dangerous_patterns: List[str] = None
    
    def __post_init__(self):
        if self.dangerous_patterns is None:
            self.dangerous_patterns = [
                r'<script[^>]*>.*?</script>',  # Script tags
                r'javascript:',  # JavaScript URLs
                r'vbscript:',  # VBScript URLs
                r'on\w+\s*=',  # Event handlers
                r'<iframe[^>]*>',  # iframes
                r'<object[^>]*>',  # Objects
                r'<embed[^>]*>',  # Embeds
                r'<form[^>]*>',  # Forms
                r'<input[^>]*>',  # Input fields
            ]


class InputSanitizer:
    """Advanced input sanitization for MCP tools."""
    
    def __init__(self, config: SanitizationConfig = None):
        self.config = config or SanitizationConfig()
        self.dangerous_regex = re.compile(
            '|'.join(self.config.dangerous_patterns),
            re.IGNORECASE | re.DOTALL
        )
    
    def sanitize_input(self, data: Any, path: str = "root") -> Any:
        """
        Sanitize input data recursively.
        
        Args:
            data: Input data to sanitize
            path: Path to current data for error reporting
            
        Returns:
            Sanitized data
            
        Raises:
            ValidationError: If data is invalid or dangerous
        """
        if data is None:
            return None
        
        if isinstance(data, str):
            return self._sanitize_string(data, path)
        elif isinstance(data, (int, float, bool)):
            return self._sanitize_number(data, path)
        elif isinstance(data, list):
            return self._sanitize_array(data, path)
        elif isinstance(data, dict):
            return self._sanitize_dict(data, path)
        else:
            # For other types, convert to string and sanitize
            return self._sanitize_string(str(data), path)
    
    def _sanitize_string(self, value: str, path: str) -> str:
        """Sanitize string input."""
        if len(value) > self.config.max_string_length:
            raise ValidationError(
                f"String too long at {path}: {len(value)} > {self.config.max_string_length}"
            )
        
        # Remove control characters
        if self.config.strip_control_chars:
            value = self._remove_control_chars(value)
        
        # Normalize Unicode
        if self.config.normalize_unicode:
            import unicodedata
            value = unicodedata.normalize('NFC', value)
        
        # Check for dangerous patterns
        if self.dangerous_regex.search(value):
            logger.warning(f"Dangerous content detected at {path}: {value[:100]}...")
            if not self.config.allow_scripts:
                raise ValidationError(f"Dangerous content detected at {path}")
        
        # HTML escape if not allowing HTML
        if not self.config.allow_html:
            value = html.escape(value)
        
        return value
    
    def _sanitize_number(self, value: Union[int, float, bool], path: str) -> Union[int, float, bool]:
        """Sanitize numeric input."""
        if isinstance(value, bool):
            return value
        
        # Check for NaN and infinity
        if isinstance(value, float):
            if value != value:  # NaN check
                raise ValidationError(f"NaN value at {path}")
            if value == float('inf') or value == float('-inf'):
                raise ValidationError(f"Infinite value at {path}")
        
        # Check for extremely large numbers
        if isinstance(value, (int, float)) and abs(value) > 10**15:
            raise ValidationError(f"Number too large at {path}: {value}")
        
        return value
    
    def _sanitize_array(self, value: List[Any], path: str) -> List[Any]:
        """Sanitize array input."""
        if len(value) > self.config.max_array_length:
            raise ValidationError(
                f"Array too long at {path}: {len(value)} > {self.config.max_array_length}"
            )
        
        sanitized = []
        for i, item in enumerate(value):
            item_path = f"{path}[{i}]"
            sanitized.append(self.sanitize_input(item, item_path))
        
        return sanitized
    
    def _sanitize_dict(self, value: Dict[str, Any], path: str, depth: int = 0) -> Dict[str, Any]:
        """Sanitize dictionary input."""
        if depth > self.config.max_json_depth:
            raise ValidationError(f"JSON too deep at {path}: depth > {self.config.max_json_depth}")
        
        if len(value) > self.config.max_dict_keys:
            raise ValidationError(
                f"Dictionary too many keys at {path}: {len(value)} > {self.config.max_dict_keys}"
            )
        
        sanitized = {}
        for key, val in value.items():
            # Sanitize key
            sanitized_key = self._sanitize_string(str(key), f"{path}.{key}")
            
            # Sanitize value
            val_path = f"{path}.{key}"
            sanitized_val = self.sanitize_input(val, val_path) if not isinstance(val, dict) else self._sanitize_dict(val, val_path, depth + 1)
            
            sanitized[sanitized_key] = sanitized_val
        
        return sanitized
    
    def _remove_control_chars(self, value: str) -> str:
        """Remove control characters from string."""
        # Keep only printable characters and common whitespace
        return ''.join(
            char for char in value
            if ord(char) >= 32 or char in '\t\n\r'
        )
    
    def validate_json_structure(self, data: Any, max_depth: int = None) -> bool:
        """Validate JSON structure depth and complexity."""
        max_depth = max_depth or self.config.max_json_depth
        
        def check_depth(obj, current_depth=0):
            if current_depth > max_depth:
                return False
            
            if isinstance(obj, dict):
                if len(obj) > self.config.max_dict_keys:
                    return False
                for value in obj.values():
                    if not check_depth(value, current_depth + 1):
                        return False
            elif isinstance(obj, list):
                if len(obj) > self.config.max_array_length:
                    return False
                for item in obj:
                    if not check_depth(item, current_depth + 1):
                        return False
            
            return True
        
        return check_depth(data)
    
    def sanitize_sql_injection(self, value: str) -> str:
        """Basic SQL injection prevention."""
        # Remove common SQL injection patterns
        sql_patterns = [
            r"(\s*(union|select|insert|update|delete|drop|create|alter|exec|execute)\s+)",
            r"(\s*(-{2}|/\*|\*/)\s*)",  # Comments
            r"(\s*;\s*)",  # Semicolons
            r"(\s*'\s*)",  # Single quotes
        ]
        
        for pattern in sql_patterns:
            value = re.sub(pattern, '', value, flags=re.IGNORECASE)
        
        return value
    
    def sanitize_command_injection(self, value: str) -> str:
        """Basic command injection prevention."""
        # Remove common command injection patterns
        cmd_patterns = [
            r"[;&|`$()]",  # Shell metacharacters
            r"\\",  # Backslashes
            r"\s*\.\./",  # Directory traversal
        ]
        
        for pattern in cmd_patterns:
            value = re.sub(pattern, '', value)
        
        return value


def sanitize_input(
    data: Any,
    max_string_length: int = 10000,
    max_json_depth: int = 10,
    allow_html: bool = False,
    allow_scripts: bool = False
) -> Any:
    """
    Convenience function to sanitize input data.
    
    Args:
        data: Input data to sanitize
        max_string_length: Maximum string length
        max_json_depth: Maximum JSON depth
        allow_html: Allow HTML content
        allow_scripts: Allow script content
        
    Returns:
        Sanitized data
    """
    config = SanitizationConfig(
        max_string_length=max_string_length,
        max_json_depth=max_json_depth,
        allow_html=allow_html,
        allow_scripts=allow_scripts
    )
    
    sanitizer = InputSanitizer(config)
    return sanitizer.sanitize_input(data)


def create_sanitizer(
    max_string_length: int = 10000,
    max_json_depth: int = 10,
    max_array_length: int = 1000,
    allow_html: bool = False,
    allow_scripts: bool = False
) -> InputSanitizer:
    """
    Create an input sanitizer with custom configuration.
    
    Args:
        max_string_length: Maximum string length
        max_json_depth: Maximum JSON depth
        max_array_length: Maximum array length
        allow_html: Allow HTML content
        allow_scripts: Allow script content
        
    Returns:
        InputSanitizer instance
    """
    config = SanitizationConfig(
        max_string_length=max_string_length,
        max_json_depth=max_json_depth,
        max_array_length=max_array_length,
        allow_html=allow_html,
        allow_scripts=allow_scripts
    )
    
    return InputSanitizer(config)