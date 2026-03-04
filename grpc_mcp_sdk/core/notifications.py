"""Notification system for gRPC MCP SDK.

Implements the MCP notification protocol for server-initiated messages.
Notifications are one-way messages that don't expect a response.
"""

import asyncio
import json
import time
import threading
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Callable, Awaitable
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Standard MCP notification types."""
    # Lifecycle
    INITIALIZED = "notifications/initialized"
    CANCELLED = "notifications/cancelled"

    # List changes
    TOOLS_LIST_CHANGED = "notifications/tools/list_changed"
    RESOURCES_LIST_CHANGED = "notifications/resources/list_changed"
    RESOURCES_UPDATED = "notifications/resources/updated"
    PROMPTS_LIST_CHANGED = "notifications/prompts/list_changed"
    ROOTS_LIST_CHANGED = "notifications/roots/list_changed"

    # Progress and logging
    PROGRESS = "notifications/progress"
    MESSAGE = "notifications/message"


@dataclass
class Notification:
    """An MCP notification message."""
    method: str
    params: Optional[Dict[str, Any]] = None

    def to_jsonrpc(self) -> Dict[str, Any]:
        """Convert to JSON-RPC 2.0 notification format."""
        msg = {
            "jsonrpc": "2.0",
            "method": self.method
        }
        if self.params:
            msg["params"] = self.params
        return msg

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_jsonrpc())


@dataclass
class ProgressNotification:
    """Progress notification for long-running operations."""
    progress_token: str
    progress: float  # 0.0 to 1.0
    total: Optional[float] = None
    message: Optional[str] = None

    def to_notification(self) -> Notification:
        params = {
            "progressToken": self.progress_token,
            "progress": self.progress
        }
        if self.total is not None:
            params["total"] = self.total
        if self.message:
            params["message"] = self.message
        return Notification(
            method=NotificationType.PROGRESS,
            params=params
        )


@dataclass
class LogMessage:
    """Log message notification."""
    level: str  # "debug", "info", "notice", "warning", "error", "critical", "alert", "emergency"
    logger_name: Optional[str] = None
    data: Optional[Any] = None

    def to_notification(self) -> Notification:
        params = {"level": self.level}
        if self.logger_name:
            params["logger"] = self.logger_name
        if self.data is not None:
            params["data"] = self.data
        return Notification(
            method=NotificationType.MESSAGE,
            params=params
        )


@dataclass
class Session:
    """Represents a client session with notification queue."""
    session_id: str
    created_at: float = field(default_factory=time.time)
    notifications: asyncio.Queue = field(default_factory=lambda: asyncio.Queue())
    subscribed_resources: Set[str] = field(default_factory=set)
    active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    async def send(self, notification: Notification) -> None:
        """Queue a notification for this session."""
        if self.active:
            await self.notifications.put(notification)

    async def receive(self, timeout: Optional[float] = None) -> Optional[Notification]:
        """Receive next notification from queue."""
        try:
            if timeout:
                return await asyncio.wait_for(
                    self.notifications.get(),
                    timeout=timeout
                )
            return await self.notifications.get()
        except asyncio.TimeoutError:
            return None

    def close(self) -> None:
        """Mark session as closed."""
        self.active = False


class NotificationManager:
    """Manages notification delivery to connected clients.

    Handles:
    - Session management (create, get, close)
    - Broadcasting notifications to all sessions
    - Targeted notifications to specific sessions
    - Resource subscription management
    - Progress tracking
    """

    _global_instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.sessions: Dict[str, Session] = {}
        self.progress_tokens: Dict[str, str] = {}  # token -> session_id
        self._listeners: List[Callable[[Notification], Awaitable[None]]] = []

    @classmethod
    def global_manager(cls) -> "NotificationManager":
        """Get the global notification manager instance."""
        if cls._global_instance is None:
            with cls._lock:
                if cls._global_instance is None:
                    cls._global_instance = cls()
        return cls._global_instance

    # =========================================================================
    # Session Management
    # =========================================================================

    def create_session(self, session_id: Optional[str] = None, metadata: Optional[Dict] = None) -> Session:
        """Create a new session."""
        sid = session_id or str(uuid.uuid4())
        session = Session(session_id=sid, metadata=metadata or {})
        self.sessions[sid] = session
        logger.debug(f"Created session: {sid}")
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        return self.sessions.get(session_id)

    def close_session(self, session_id: str) -> None:
        """Close and remove a session."""
        if session_id in self.sessions:
            self.sessions[session_id].close()
            del self.sessions[session_id]
            logger.debug(f"Closed session: {session_id}")

    def list_sessions(self) -> List[str]:
        """List all active session IDs."""
        return [sid for sid, s in self.sessions.items() if s.active]

    # =========================================================================
    # Notification Broadcasting
    # =========================================================================

    async def broadcast(self, notification: Notification) -> int:
        """Send notification to all active sessions.

        Returns number of sessions notified.
        """
        count = 0
        for session in self.sessions.values():
            if session.active:
                await session.send(notification)
                count += 1

        # Also notify listeners
        for listener in self._listeners:
            try:
                await listener(notification)
            except Exception as e:
                logger.warning(f"Listener error: {e}")

        return count

    async def send_to_session(self, session_id: str, notification: Notification) -> bool:
        """Send notification to a specific session.

        Returns True if sent, False if session not found.
        """
        session = self.get_session(session_id)
        if session and session.active:
            await session.send(notification)
            return True
        return False

    def add_listener(self, callback: Callable[[Notification], Awaitable[None]]) -> None:
        """Add a notification listener callback."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[Notification], Awaitable[None]]) -> None:
        """Remove a notification listener callback."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    # =========================================================================
    # Standard Notifications
    # =========================================================================

    async def notify_initialized(self) -> None:
        """Send initialized notification."""
        await self.broadcast(Notification(method=NotificationType.INITIALIZED))

    async def notify_tools_changed(self) -> None:
        """Send tools list changed notification."""
        await self.broadcast(Notification(method=NotificationType.TOOLS_LIST_CHANGED))

    async def notify_resources_changed(self) -> None:
        """Send resources list changed notification."""
        await self.broadcast(Notification(method=NotificationType.RESOURCES_LIST_CHANGED))

    async def notify_resource_updated(self, uri: str) -> None:
        """Send resource updated notification to subscribed sessions."""
        notification = Notification(
            method=NotificationType.RESOURCES_UPDATED,
            params={"uri": uri}
        )
        # Only send to sessions subscribed to this resource
        for session in self.sessions.values():
            if session.active and uri in session.subscribed_resources:
                await session.send(notification)

    async def notify_prompts_changed(self) -> None:
        """Send prompts list changed notification."""
        await self.broadcast(Notification(method=NotificationType.PROMPTS_LIST_CHANGED))

    async def notify_cancelled(self, request_id: str, reason: Optional[str] = None) -> None:
        """Send cancellation notification."""
        params = {"requestId": request_id}
        if reason:
            params["reason"] = reason
        await self.broadcast(Notification(
            method=NotificationType.CANCELLED,
            params=params
        ))

    # =========================================================================
    # Progress Tracking
    # =========================================================================

    def create_progress_token(self, session_id: Optional[str] = None) -> str:
        """Create a progress token for tracking operation progress."""
        token = str(uuid.uuid4())
        if session_id:
            self.progress_tokens[token] = session_id
        return token

    async def report_progress(
        self,
        token: str,
        progress: float,
        total: Optional[float] = None,
        message: Optional[str] = None
    ) -> None:
        """Report progress for a tracked operation."""
        notification = ProgressNotification(
            progress_token=token,
            progress=progress,
            total=total,
            message=message
        ).to_notification()

        # Send to specific session if token is bound
        if token in self.progress_tokens:
            session_id = self.progress_tokens[token]
            await self.send_to_session(session_id, notification)
        else:
            # Broadcast if not bound to a session
            await self.broadcast(notification)

    def complete_progress(self, token: str) -> None:
        """Mark a progress token as complete."""
        if token in self.progress_tokens:
            del self.progress_tokens[token]

    # =========================================================================
    # Logging
    # =========================================================================

    async def log(
        self,
        level: str,
        data: Any,
        logger_name: Optional[str] = None
    ) -> None:
        """Send a log message notification."""
        notification = LogMessage(
            level=level,
            logger_name=logger_name,
            data=data
        ).to_notification()
        await self.broadcast(notification)

    async def log_debug(self, data: Any, logger_name: Optional[str] = None) -> None:
        await self.log("debug", data, logger_name)

    async def log_info(self, data: Any, logger_name: Optional[str] = None) -> None:
        await self.log("info", data, logger_name)

    async def log_warning(self, data: Any, logger_name: Optional[str] = None) -> None:
        await self.log("warning", data, logger_name)

    async def log_error(self, data: Any, logger_name: Optional[str] = None) -> None:
        await self.log("error", data, logger_name)

    # =========================================================================
    # Resource Subscriptions
    # =========================================================================

    def subscribe_resource(self, session_id: str, uri: str) -> bool:
        """Subscribe a session to resource updates."""
        session = self.get_session(session_id)
        if session:
            session.subscribed_resources.add(uri)
            return True
        return False

    def unsubscribe_resource(self, session_id: str, uri: str) -> bool:
        """Unsubscribe a session from resource updates."""
        session = self.get_session(session_id)
        if session:
            session.subscribed_resources.discard(uri)
            return True
        return False

    def get_resource_subscribers(self, uri: str) -> List[str]:
        """Get all session IDs subscribed to a resource."""
        return [
            sid for sid, session in self.sessions.items()
            if session.active and uri in session.subscribed_resources
        ]

    # =========================================================================
    # Stats and Health
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get notification manager statistics."""
        active_sessions = sum(1 for s in self.sessions.values() if s.active)
        total_subscriptions = sum(
            len(s.subscribed_resources) for s in self.sessions.values()
        )
        return {
            "total_sessions": len(self.sessions),
            "active_sessions": active_sessions,
            "active_progress_tokens": len(self.progress_tokens),
            "total_resource_subscriptions": total_subscriptions,
            "listeners": len(self._listeners)
        }

    def clear(self) -> None:
        """Clear all sessions and state."""
        for session in self.sessions.values():
            session.close()
        self.sessions.clear()
        self.progress_tokens.clear()
