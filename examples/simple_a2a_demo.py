"""
Simple A2A Demo - Basic agent-to-agent communication example

This demonstrates:
1. Creating agents with capabilities
2. Agent discovery
3. Simple agent communication
4. Basic workflow orchestration
"""

import asyncio
import logging
import sys
import os

# Add the parent directory to sys.path to import the local grpc_mcp_sdk
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import core MCP functionality
from grpc_mcp_sdk import mcp_tool, MCPToolResult, is_a2a_available

# Import A2A functionality if available
if is_a2a_available():
    from grpc_mcp_sdk import (
        agent_capability, register_local_agent, create_agent_client,
        create_workflow_orchestrator, AgentCapabilityType, WorkflowStep
    )
else:
    # Mock functions if A2A not available
    def agent_capability(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    def register_local_agent(*args, **kwargs):
        return "mock-agent-id"
    
    def create_agent_client():
        class MockClient:
            async def discover_agents(self, capability):
                return []
            async def find_best_agent(self, capability, requirements=None):
                return None
        return MockClient()
    
    def create_workflow_orchestrator():
        class MockOrchestrator:
            async def execute_workflow(self, workflow_id, steps):
                class MockResult:
                    success = False
                return MockResult()
        return MockOrchestrator()
    
    class AgentCapabilityType:
        TOOL_PROVIDER = "tool_provider"
        DATA_PROCESSOR = "data_processor"
    
    class WorkflowStep:
        def __init__(self, step_id, capability_name, arguments):
            self.step_id = step_id
            self.capability_name = capability_name
            self.arguments = arguments

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Example 1: Simple Calculator Agent
@agent_capability(
    name="add_numbers",
    description="Add two numbers together",
    capability_type=AgentCapabilityType.TOOL_PROVIDER
)
@mcp_tool(description="Add two numbers")
def add_numbers(a: float, b: float) -> MCPToolResult:
    result = a + b
    return MCPToolResult().add_text(f"{a} + {b} = {result}")

# Example 2: Text Processor Agent  
@agent_capability(
    name="process_text",
    description="Process and transform text",
    capability_type=AgentCapabilityType.DATA_PROCESSOR
)
@mcp_tool(description="Process text input")
async def process_text(text: str, operation: str = "uppercase") -> MCPToolResult:
    """Process text with various operations"""
    if operation == "uppercase":
        result = text.upper()
    elif operation == "lowercase":
        result = text.lower()
    elif operation == "reverse":
        result = text[::-1]
    elif operation == "length":
        result = f"Length: {len(text)}"
    else:
        result = text
    
    return MCPToolResult().add_text(f"Processed '{text}' -> '{result}'")

async def main():
    logger.info("🚀 Simple A2A Demo")
    
    if not is_a2a_available():
        logger.error("A2A extensions not available")
        return
    
    # Register local agent
    agent_id = register_local_agent(
        name="Simple Demo Agent",
        description="Basic A2A demonstration agent"
    )
    logger.info(f"Registered agent: {agent_id}")
    
    # Create client and test discovery
    client = create_agent_client()
    
    # Find agents with math capabilities
    math_agents = await client.discover_agents("add_numbers")
    logger.info(f"Found {len(math_agents)} math agents")
    
    # Find agents with text processing capabilities
    text_agents = await client.discover_agents("process_text")
    logger.info(f"Found {len(text_agents)} text processing agents")
    
    # Test direct capability execution
    if math_agents:
        result = await client.execute_capability(
            agent_id=math_agents[0].agent_id,
            capability_name="add_numbers",
            arguments={"a": 5, "b": 3}
        )
        logger.info(f"Math result: {result.content}")
    
    # Test workflow
    orchestrator = create_workflow_orchestrator()
    
    steps = [
        WorkflowStep(
            step_id="math",
            capability_name="add_numbers", 
            arguments={"a": 10, "b": 20}
        ),
        WorkflowStep(
            step_id="text",
            capability_name="process_text",
            arguments={"text": "Hello World", "operation": "uppercase"}
        )
    ]
    
    result = await orchestrator.execute_workflow("demo", steps)
    logger.info(f"Workflow success: {result.success}")

if __name__ == "__main__":
    asyncio.run(main())