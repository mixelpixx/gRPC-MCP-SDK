"""Prompt registry for gRPC MCP SDK.

Provides registration and management of MCP prompts,
which are reusable templates for language model interactions.
"""

import inspect
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Union
from functools import wraps

from .types import Prompt, PromptArgument, PromptMessage, GetPromptResult
from ..utils.errors import PromptNotFoundError, ValidationError


@dataclass
class RegisteredPrompt:
    """A registered prompt with its generator function."""
    prompt: Prompt
    generator: Callable[..., Any]  # Takes arguments, returns messages
    is_async: bool = False

    async def get(self, arguments: Dict[str, Any]) -> GetPromptResult:
        """Generate prompt messages with the given arguments."""
        # Validate required arguments
        for arg in self.prompt.arguments:
            if arg.required and arg.name not in arguments:
                raise ValidationError(f"Missing required argument: {arg.name}")

        # Call generator
        if self.is_async:
            result = await self.generator(**arguments)
        else:
            result = self.generator(**arguments)

        # Convert to GetPromptResult if not already
        if isinstance(result, GetPromptResult):
            return result
        elif isinstance(result, list):
            # Assume list of messages
            messages = []
            for item in result:
                if isinstance(item, PromptMessage):
                    messages.append(item)
                elif isinstance(item, dict):
                    messages.append(PromptMessage(
                        role=item.get("role", "user"),
                        content=item.get("content", {"type": "text", "text": str(item)})
                    ))
                elif isinstance(item, str):
                    messages.append(PromptMessage(
                        role="user",
                        content={"type": "text", "text": item}
                    ))
            return GetPromptResult(
                description=self.prompt.description,
                messages=messages
            )
        elif isinstance(result, str):
            # Single text message
            return GetPromptResult(
                description=self.prompt.description,
                messages=[
                    PromptMessage(
                        role="user",
                        content={"type": "text", "text": result}
                    )
                ]
            )
        else:
            raise ValidationError(f"Invalid prompt result type: {type(result)}")


class PromptRegistry:
    """Registry for MCP prompts."""

    _global_instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.prompts: Dict[str, RegisteredPrompt] = {}
        self._healthy = True
        self._on_change_callback: Optional[Callable[[], None]] = None

    def set_on_change_callback(self, callback: Callable[[], None]) -> None:
        """Set callback to be invoked when prompts list changes."""
        self._on_change_callback = callback

    def _notify_change(self) -> None:
        """Notify that prompts list has changed."""
        if self._on_change_callback:
            try:
                self._on_change_callback()
            except Exception:
                pass  # Silently ignore callback errors

    @classmethod
    def global_registry(cls) -> "PromptRegistry":
        """Get the global prompt registry instance."""
        if cls._global_instance is None:
            with cls._lock:
                if cls._global_instance is None:
                    cls._global_instance = cls()
        return cls._global_instance

    def register(self, prompt: RegisteredPrompt) -> None:
        """Register a prompt."""
        if prompt.prompt.name in self.prompts:
            raise ValueError(f"Prompt already registered: {prompt.prompt.name}")
        self.prompts[prompt.prompt.name] = prompt
        self._notify_change()

    def unregister(self, name: str) -> None:
        """Unregister a prompt."""
        if name in self.prompts:
            del self.prompts[name]
            self._notify_change()

    def get_prompt(self, name: str) -> Optional[RegisteredPrompt]:
        """Get a prompt by name."""
        return self.prompts.get(name)

    def list_prompts(self) -> List[Prompt]:
        """List all registered prompts."""
        return [reg.prompt for reg in self.prompts.values()]

    async def execute_prompt(
        self,
        name: str,
        arguments: Dict[str, Any]
    ) -> GetPromptResult:
        """Execute a prompt with arguments."""
        prompt = self.get_prompt(name)
        if not prompt:
            raise PromptNotFoundError(name)

        return await prompt.get(arguments)

    def is_healthy(self) -> bool:
        """Check if registry is healthy."""
        return self._healthy

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        return {
            "total_prompts": len(self.prompts),
            "healthy": self.is_healthy()
        }

    def clear(self) -> None:
        """Clear all registered prompts."""
        self.prompts.clear()

    def __len__(self) -> int:
        """Return number of registered prompts."""
        return len(self.prompts)

    def __contains__(self, name: str) -> bool:
        """Check if prompt is registered."""
        return name in self.prompts

    def __iter__(self):
        """Iterate over registered prompts."""
        return iter(self.prompts.values())


# =============================================================================
# Decorators
# =============================================================================

def mcp_prompt(
    name: Optional[str] = None,
    description: Optional[str] = None,
    arguments: Optional[List[Dict[str, Any]]] = None
):
    """Decorator to register a function as an MCP prompt.

    The function should return either:
    - A GetPromptResult object
    - A list of PromptMessage objects or dicts
    - A string (converted to single user message)

    Args:
        name: Prompt name (defaults to function name)
        description: Human-readable description
        arguments: List of argument definitions with name, description, required

    Example:
        @mcp_prompt(
            description="Generate a code review prompt",
            arguments=[
                {"name": "code", "description": "Code to review", "required": True},
                {"name": "language", "description": "Programming language"}
            ]
        )
        def code_review(code: str, language: str = "python"):
            return [
                {"role": "user", "content": {"type": "text", "text": f"Review this {language} code:\\n{code}"}},
                {"role": "assistant", "content": {"type": "text", "text": "I'll review this code for..."}}
            ]
    """
    def decorator(func: Callable) -> Callable:
        prompt_name = name or func.__name__

        # Build arguments from decorator or function signature
        prompt_args = []
        if arguments:
            for arg in arguments:
                prompt_args.append(PromptArgument(
                    name=arg["name"],
                    description=arg.get("description"),
                    required=arg.get("required", False)
                ))
        else:
            # Extract from function signature
            sig = inspect.signature(func)
            for param_name, param in sig.parameters.items():
                if param_name in ['self', 'cls']:
                    continue
                prompt_args.append(PromptArgument(
                    name=param_name,
                    description=None,
                    required=param.default == inspect.Parameter.empty
                ))

        # Create prompt definition
        prompt = Prompt(
            name=prompt_name,
            description=description or func.__doc__ or f"Prompt: {prompt_name}",
            arguments=prompt_args
        )

        # Create registered prompt
        is_async = inspect.iscoroutinefunction(func)
        registered = RegisteredPrompt(
            prompt=prompt,
            generator=func,
            is_async=is_async
        )

        # Register globally
        PromptRegistry.global_registry().register(registered)

        return func

    return decorator


# Convenience alias
prompt = mcp_prompt
