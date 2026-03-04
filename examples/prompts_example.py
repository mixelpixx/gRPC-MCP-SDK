"""
MCP Prompts example demonstrating reusable prompt templates.

Prompts are templates that help structure LLM interactions.
They can accept arguments and return messages in various formats.

Run with:
    python examples/prompts_example.py

Or use stdio for Claude Desktop:
    grpc-mcp stdio --module examples.prompts_example
"""
import asyncio
import logging

from grpc_mcp_sdk import run_server
from grpc_mcp_sdk.core import mcp_prompt, PromptRegistry, GetPromptResult, PromptMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Simple prompt returning a string (converted to user message)
@mcp_prompt(
    description="Generate a greeting message"
)
def greeting(name: str, formal: bool = False):
    """Generate a greeting for the given name."""
    if formal:
        return f"Good day, {name}. How may I assist you today?"
    else:
        return f"Hey {name}! What can I help you with?"


# Prompt with explicit argument definitions
@mcp_prompt(
    description="Generate a code review prompt",
    arguments=[
        {"name": "code", "description": "The code to review", "required": True},
        {"name": "language", "description": "Programming language", "required": False},
        {"name": "focus", "description": "Areas to focus on (security, performance, style)", "required": False}
    ]
)
def code_review(code: str, language: str = "python", focus: str = "general"):
    """Generate a code review prompt with specific focus areas."""
    focus_instructions = {
        "security": "Focus on security vulnerabilities, input validation, and potential exploits.",
        "performance": "Focus on performance bottlenecks, algorithmic complexity, and optimization opportunities.",
        "style": "Focus on code style, readability, naming conventions, and best practices.",
        "general": "Provide a comprehensive review covering correctness, style, and potential improvements."
    }

    instruction = focus_instructions.get(focus, focus_instructions["general"])

    return f"""Review the following {language} code:

```{language}
{code}
```

{instruction}

Provide specific, actionable feedback."""


# Prompt returning a list of messages
@mcp_prompt(
    description="Start a debugging session"
)
def debug_session(error_message: str, context: str = ""):
    """Generate a multi-turn debugging conversation starter."""
    messages = [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": f"I'm encountering this error:\n\n{error_message}"
            }
        },
        {
            "role": "assistant",
            "content": {
                "type": "text",
                "text": "I'll help you debug this. Let me analyze the error message."
            }
        },
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": f"Here's the relevant context:\n\n{context}" if context else "What information do you need to help debug this?"
            }
        }
    ]
    return messages


# Async prompt with external data
@mcp_prompt(
    description="Generate a summary prompt for a document"
)
async def summarize_document(document: str, max_words: int = 200, style: str = "concise"):
    """Generate a document summarization prompt."""
    await asyncio.sleep(0.01)  # Simulate async processing

    style_instructions = {
        "concise": "Be brief and focus on key points only.",
        "detailed": "Include important details and context.",
        "bullet": "Format the summary as bullet points.",
        "executive": "Write an executive summary suitable for stakeholders."
    }

    instruction = style_instructions.get(style, style_instructions["concise"])

    return f"""Summarize the following document in approximately {max_words} words.

{instruction}

Document:
---
{document}
---

Summary:"""


# Prompt returning GetPromptResult for full control
@mcp_prompt(
    description="Generate a technical explanation prompt"
)
def explain_concept(concept: str, audience: str = "beginner", include_examples: bool = True):
    """Generate a prompt for explaining technical concepts."""
    audience_instructions = {
        "beginner": "Explain as if to someone with no technical background. Avoid jargon.",
        "intermediate": "Assume basic technical knowledge. Include some technical details.",
        "expert": "Use precise technical language. Focus on nuances and edge cases."
    }

    audience_instruction = audience_instructions.get(audience, audience_instructions["beginner"])

    messages = [
        PromptMessage(
            role="user",
            content={
                "type": "text",
                "text": f"Explain the concept of '{concept}'.\n\n{audience_instruction}"
            }
        )
    ]

    if include_examples:
        messages.append(PromptMessage(
            role="user",
            content={
                "type": "text",
                "text": "Please include practical examples to illustrate the concept."
            }
        ))

    return GetPromptResult(
        description=f"Explanation of {concept} for {audience} audience",
        messages=messages
    )


# Prompt for generating test cases
@mcp_prompt(
    description="Generate test cases for a function",
    arguments=[
        {"name": "function_signature", "description": "The function signature to test", "required": True},
        {"name": "function_description", "description": "What the function does", "required": True},
        {"name": "test_framework", "description": "Testing framework to use", "required": False}
    ]
)
def generate_tests(function_signature: str, function_description: str, test_framework: str = "pytest"):
    """Generate test cases for a given function."""
    return f"""Generate comprehensive test cases for the following function.

Function signature:
```python
{function_signature}
```

Function description: {function_description}

Requirements:
1. Use {test_framework} as the testing framework
2. Include test cases for:
   - Normal/expected inputs
   - Edge cases (empty inputs, boundary values)
   - Error cases (invalid inputs)
3. Add descriptive test names
4. Include comments explaining each test case

Generate the test code:"""


# Multi-step prompt for problem solving
@mcp_prompt(
    description="Structure a problem-solving approach"
)
def problem_solving(problem: str, constraints: str = "", domain: str = "software"):
    """Generate a structured problem-solving prompt."""
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": f"I need to solve this problem:\n\n{problem}"
            }
        },
        {
            "role": "assistant",
            "content": {
                "type": "text",
                "text": f"I'll help you solve this {domain} problem systematically. Let me break it down."
            }
        },
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": f"The constraints are:\n{constraints}" if constraints else "There are no specific constraints."
            }
        },
        {
            "role": "assistant",
            "content": {
                "type": "text",
                "text": """Let's approach this step by step:

1. First, I'll clarify the requirements
2. Then, I'll identify potential approaches
3. Next, I'll evaluate tradeoffs
4. Finally, I'll propose a solution

Let's start with step 1..."""
            }
        }
    ]


def print_registered_prompts():
    """Print all registered prompts for reference."""
    registry = PromptRegistry.global_registry()

    logger.info("Registered prompts:")
    for prompt in registry.list_prompts():
        args = ", ".join(
            f"{a.name}{'*' if a.required else ''}"
            for a in prompt.arguments
        )
        logger.info(f"  - {prompt.name}({args}): {prompt.description}")


if __name__ == "__main__":
    print_registered_prompts()

    logger.info("Starting gRPC MCP server with prompts...")
    logger.info("Connect a client and use prompts/list to see available prompts")
    logger.info("Use prompts/get with a name and arguments to generate prompt messages")

    asyncio.run(run_server(
        host="0.0.0.0",
        port=50051,
        server_name="Prompts-Example-Server",
        version="1.0.0"
    ))
