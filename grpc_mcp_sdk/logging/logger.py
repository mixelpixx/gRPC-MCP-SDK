"""Advanced logging configuration for gRPC MCP SDK."""

import logging
import logging.handlers
import json
import time
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
import sys
import traceback


@dataclass
class LogConfig:
    """Configuration for logging."""
    # Basic settings
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # File logging
    enable_file_logging: bool = True
    log_dir: str = "logs"
    log_file: str = "mcp_server.log"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    
    # Console logging
    enable_console_logging: bool = True
    console_level: str = "INFO"
    
    # JSON logging
    enable_json_logging: bool = False
    json_log_file: str = "mcp_server.json"
    
    # Structured logging
    enable_structured_logging: bool = True
    include_context: bool = True
    include_performance: bool = True
    
    # Security logging
    enable_security_logging: bool = True
    security_log_file: str = "security.log"
    
    # Audit logging
    enable_audit_logging: bool = True
    audit_log_file: str = "audit.log"
    
    # Log rotation
    enable_rotation: bool = True
    rotation_when: str = "midnight"  # 'midnight', 'H', 'D', 'W0'-'W6'
    rotation_interval: int = 1
    
    # Additional loggers
    additional_loggers: Dict[str, str] = field(default_factory=dict)


class ContextFilter(logging.Filter):
    """Filter to add context information to log records."""
    
    def __init__(self):
        super().__init__()
        self.context_data = threading.local()
    
    def filter(self, record):
        """Add context data to log record."""
        context = getattr(self.context_data, 'context', {})
        
        # Add context fields to record
        for key, value in context.items():
            setattr(record, key, value)
        
        return True
    
    def set_context(self, **kwargs):
        """Set context data for current thread."""
        if not hasattr(self.context_data, 'context'):
            self.context_data.context = {}
        self.context_data.context.update(kwargs)
    
    def clear_context(self):
        """Clear context data for current thread."""
        if hasattr(self.context_data, 'context'):
            self.context_data.context.clear()


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def __init__(self, include_context: bool = True):
        super().__init__()
        self.include_context = include_context
    
    def format(self, record):
        """Format log record as JSON."""
        log_obj = {
            "timestamp": time.time(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "thread_name": record.threadName,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add context if enabled
        if self.include_context:
            for key, value in record.__dict__.items():
                if key not in log_obj and not key.startswith('_'):
                    log_obj[key] = value
        
        return json.dumps(log_obj)


class PerformanceFilter(logging.Filter):
    """Filter to add performance metrics to log records."""
    
    def __init__(self):
        super().__init__()
        self.request_times = threading.local()
    
    def filter(self, record):
        """Add performance data to log record."""
        # Add timing information if available
        if hasattr(self.request_times, 'start_time'):
            record.duration = time.time() - self.request_times.start_time
        
        return True
    
    def start_request(self):
        """Start timing a request."""
        self.request_times.start_time = time.time()
    
    def end_request(self):
        """End timing a request."""
        if hasattr(self.request_times, 'start_time'):
            delattr(self.request_times, 'start_time')


class MCPLogger:
    """Advanced logger for MCP SDK."""
    
    def __init__(self, config: LogConfig):
        self.config = config
        self.context_filter = ContextFilter()
        self.performance_filter = PerformanceFilter()
        self.loggers: Dict[str, logging.Logger] = {}
        
        # Create log directory
        if config.enable_file_logging:
            Path(config.log_dir).mkdir(parents=True, exist_ok=True)
        
        # Setup main logger
        self.logger = self._setup_logger("grpc_mcp_sdk")
        
        # Setup specialized loggers
        if config.enable_security_logging:
            self.security_logger = self._setup_security_logger()
        
        if config.enable_audit_logging:
            self.audit_logger = self._setup_audit_logger()
    
    def _setup_logger(self, name: str) -> logging.Logger:
        """Setup a logger with the configured handlers."""
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, self.config.level.upper()))
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Add console handler
        if self.config.enable_console_logging:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, self.config.console_level.upper()))
            
            if self.config.enable_structured_logging:
                console_formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                    + (" [%(user_id)s]" if self.config.include_context else "")
                )
            else:
                console_formatter = logging.Formatter(self.config.format)
            
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
        
        # Add file handler
        if self.config.enable_file_logging:
            log_file_path = Path(self.config.log_dir) / self.config.log_file
            
            if self.config.enable_rotation:
                file_handler = logging.handlers.TimedRotatingFileHandler(
                    log_file_path,
                    when=self.config.rotation_when,
                    interval=self.config.rotation_interval,
                    backupCount=self.config.backup_count
                )
            else:
                file_handler = logging.handlers.RotatingFileHandler(
                    log_file_path,
                    maxBytes=self.config.max_file_size,
                    backupCount=self.config.backup_count
                )
            
            file_formatter = logging.Formatter(self.config.format)
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        
        # Add JSON handler
        if self.config.enable_json_logging:
            json_file_path = Path(self.config.log_dir) / self.config.json_log_file
            json_handler = logging.handlers.RotatingFileHandler(
                json_file_path,
                maxBytes=self.config.max_file_size,
                backupCount=self.config.backup_count
            )
            json_formatter = JSONFormatter(self.config.include_context)
            json_handler.setFormatter(json_formatter)
            logger.addHandler(json_handler)
        
        # Add filters
        if self.config.include_context:
            logger.addFilter(self.context_filter)
        
        if self.config.include_performance:
            logger.addFilter(self.performance_filter)
        
        self.loggers[name] = logger
        return logger
    
    def _setup_security_logger(self) -> logging.Logger:
        """Setup security-specific logger."""
        security_logger = logging.getLogger("grpc_mcp_sdk.security")
        security_logger.setLevel(logging.WARNING)
        
        # Security log file
        security_file_path = Path(self.config.log_dir) / self.config.security_log_file
        security_handler = logging.handlers.RotatingFileHandler(
            security_file_path,
            maxBytes=self.config.max_file_size,
            backupCount=self.config.backup_count
        )
        
        security_formatter = logging.Formatter(
            "%(asctime)s - SECURITY - %(levelname)s - %(message)s"
        )
        security_handler.setFormatter(security_formatter)
        security_logger.addHandler(security_handler)
        
        return security_logger
    
    def _setup_audit_logger(self) -> logging.Logger:
        """Setup audit-specific logger."""
        audit_logger = logging.getLogger("grpc_mcp_sdk.audit")
        audit_logger.setLevel(logging.INFO)
        
        # Audit log file
        audit_file_path = Path(self.config.log_dir) / self.config.audit_log_file
        audit_handler = logging.handlers.RotatingFileHandler(
            audit_file_path,
            maxBytes=self.config.max_file_size,
            backupCount=self.config.backup_count
        )
        
        audit_formatter = JSONFormatter(include_context=True)
        audit_handler.setFormatter(audit_formatter)
        audit_logger.addHandler(audit_handler)
        
        return audit_logger
    
    def set_context(self, **kwargs):
        """Set logging context for current thread."""
        self.context_filter.set_context(**kwargs)
    
    def clear_context(self):
        """Clear logging context for current thread."""
        self.context_filter.clear_context()
    
    def start_request(self):
        """Start timing a request."""
        self.performance_filter.start_request()
    
    def end_request(self):
        """End timing a request."""
        self.performance_filter.end_request()
    
    def log_security_event(self, event: str, details: Dict[str, Any]):
        """Log a security event."""
        if hasattr(self, 'security_logger'):
            self.security_logger.warning(f"{event}: {json.dumps(details)}")
    
    def log_audit_event(self, event: str, details: Dict[str, Any]):
        """Log an audit event."""
        if hasattr(self, 'audit_logger'):
            self.audit_logger.info(f"{event}: {json.dumps(details)}")
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger by name."""
        if name not in self.loggers:
            self.loggers[name] = self._setup_logger(name)
        return self.loggers[name]
    
    def configure_external_logger(self, name: str, level: str):
        """Configure an external logger."""
        external_logger = logging.getLogger(name)
        external_logger.setLevel(getattr(logging, level.upper()))
        
        # Add our handlers to external logger
        for handler in self.logger.handlers:
            external_logger.addHandler(handler)
    
    def shutdown(self):
        """Shutdown all loggers."""
        for logger in self.loggers.values():
            for handler in logger.handlers:
                handler.close()
        
        logging.shutdown()


def create_logger(
    level: str = "INFO",
    log_dir: str = "logs",
    enable_json_logging: bool = False,
    enable_security_logging: bool = True,
    enable_audit_logging: bool = True
) -> MCPLogger:
    """
    Create a logger with common configuration.
    
    Args:
        level: Log level
        log_dir: Directory for log files
        enable_json_logging: Enable JSON logging
        enable_security_logging: Enable security logging
        enable_audit_logging: Enable audit logging
        
    Returns:
        MCPLogger instance
    """
    config = LogConfig(
        level=level,
        log_dir=log_dir,
        enable_json_logging=enable_json_logging,
        enable_security_logging=enable_security_logging,
        enable_audit_logging=enable_audit_logging
    )
    
    return MCPLogger(config)


# Global logger instance
_global_logger: Optional[MCPLogger] = None


def get_logger() -> MCPLogger:
    """Get the global logger instance."""
    global _global_logger
    if _global_logger is None:
        _global_logger = create_logger()
    return _global_logger


def set_global_logger(logger: MCPLogger):
    """Set the global logger instance."""
    global _global_logger
    _global_logger = logger