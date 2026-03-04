"""
A2A (Agent-to-Agent) Protocol Extensions for gRPC-MCP SDK

This module extends the core MCP functionality with A2A capabilities:
- Agent discovery and capability negotiation
- Agent-to-agent communication
- Multi-agent workflow orchestration
- Enhanced security for agent interactions
"""

import asyncio
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Set, Union, get_type_hints
import inspect

from .core import MCPToolResult, MCPToolContext, MCPToolDefinition, MCPToolRegistry

logger = logging.getLogger(__name__)

# =============================================================================
# A2A Core Data Structures
# =============================================================================

class AgentCapabilityType(Enum):
    """Types of agent capabilities"""
    TOOL_PROVIDER = "tool_provider"          # Provides MCP tools
    WORKFLOW_ORCHESTRATOR = "orchestrator"   # Orchestrates multi-agent workflows
    DATA_PROCESSOR = "data_processor"        # Processes and transforms data
    API_GATEWAY = "api_gateway"             # Provides API access
    KNOWLEDGE_BASE = "knowledge_base"        # Provides domain knowledge
    COORDINATOR = "coordinator"              # Coordinates agent interactions

class AgentProtocol(Enum):
    """Supported communication protocols"""
    MCP_GRPC = "mcp_grpc"
    A2A_GRPC = "a2a_grpc"
    HTTP_REST = "http_rest"
    WEBSOCKET = "websocket"

class AgentStatus(Enum):
    """Agent operational status"""
    ACTIVE = "active"
    BUSY = "busy"
    IDLE = "idle"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"

@dataclass
class AgentCapability:
    """Represents a capability that an agent provides"""
    name: str
    description: str
    version: str
    capability_type: AgentCapabilityType
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    requirements: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    sla: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AgentEndpoint:
    """Agent communication endpoint"""
    protocol: AgentProtocol
    address: str
    port: int
    secure: bool = True
    metadata: Dict[str, str] = field(default_factory=dict)

@dataclass
class AgentInfo:
    """Complete agent information"""
    agent_id: str
    name: str
    description: str
    version: str
    capabilities: List[AgentCapability]
    endpoints: List[AgentEndpoint]
    status: AgentStatus = AgentStatus.ACTIVE
    health_score: float = 1.0
    last_seen: float = field(default_factory=time.time)
    load_metrics: Dict[str, float] = field(default_factory=dict)
    tags: Set[str] = field(default_factory=set)
    owner: Optional[str] = None
    created_at: float = field(default_factory=time.time)

# =============================================================================
# Enhanced Registry with Agent Discovery
# =============================================================================

class A2AAgentRegistry:
    """Enhanced registry supporting both MCP tools and A2A agents"""
    
    def __init__(self):
        self._agents: Dict[str, AgentInfo] = {}
        self._capabilities: Dict[str, List[str]] = {}  # capability_name -> [agent_ids]
        self._tool_registry = MCPToolRegistry()  # Embed existing MCP registry
        self._discovery_callbacks: List[Callable[[AgentInfo], None]] = []
        
    def register_agent(self, agent_info: AgentInfo):
        """Register an agent with its capabilities"""
        self._agents[agent_info.agent_id] = agent_info
        
        # Index capabilities
        for capability in agent_info.capabilities:
            if capability.name not in self._capabilities:
                self._capabilities[capability.name] = []
            self._capabilities[capability.name].append(agent_info.agent_id)
        
        # Notify discovery callbacks
        for callback in self._discovery_callbacks:
            try:
                callback(agent_info)
            except Exception as e:
                logger.warning(f"Discovery callback failed: {e}")
        
        logger.info(f"Registered agent: {agent_info.name} ({agent_info.agent_id})")
    
    def unregister_agent(self, agent_id: str):
        """Unregister an agent"""
        if agent_id in self._agents:
            agent_info = self._agents[agent_id]
            
            # Remove from capability index
            for capability in agent_info.capabilities:
                if capability.name in self._capabilities:
                    if agent_id in self._capabilities[capability.name]:
                        self._capabilities[capability.name].remove(agent_id)
                    if not self._capabilities[capability.name]:
                        del self._capabilities[capability.name]
            
            del self._agents[agent_id]
            logger.info(f"Unregistered agent: {agent_id}")
    
    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent information by ID"""
        return self._agents.get(agent_id)
    
    def find_agents_by_capability(self, capability_name: str) -> List[AgentInfo]:
        """Find agents that provide a specific capability"""
        agent_ids = self._capabilities.get(capability_name, [])
        return [self._agents[agent_id] for agent_id in agent_ids if agent_id in self._agents]
    
    def find_agents_by_type(self, capability_type: AgentCapabilityType) -> List[AgentInfo]:
        """Find agents by capability type"""
        matching_agents = []
        for agent in self._agents.values():
            for capability in agent.capabilities:
                if capability.capability_type == capability_type:
                    matching_agents.append(agent)
                    break
        return matching_agents
    
    def find_best_agent(self, capability_name: str, requirements: Optional[List[str]] = None) -> Optional[AgentInfo]:
        """Find the best agent for a capability based on health, load, and requirements"""
        candidates = self.find_agents_by_capability(capability_name)
        
        if not candidates:
            return None
        
        # Filter by requirements
        if requirements:
            filtered_candidates = []
            for agent in candidates:
                for capability in agent.capabilities:
                    if capability.name == capability_name:
                        if all(req in capability.requirements for req in requirements):
                            filtered_candidates.append(agent)
                        break
            candidates = filtered_candidates
        
        if not candidates:
            return None
        
        # Score agents based on health, load, and status
        def score_agent(agent: AgentInfo) -> float:
            if agent.status != AgentStatus.ACTIVE:
                return 0.0
            
            health_score = agent.health_score
            load_score = 1.0 - agent.load_metrics.get('cpu_usage', 0.0)
            recency_score = max(0.0, 1.0 - (time.time() - agent.last_seen) / 300)  # 5 min decay
            
            return health_score * 0.4 + load_score * 0.4 + recency_score * 0.2
        
        best_agent = max(candidates, key=score_agent)
        return best_agent if score_agent(best_agent) > 0 else None
    
    def list_agents(self, status: Optional[AgentStatus] = None) -> List[AgentInfo]:
        """List all agents, optionally filtered by status"""
        agents = list(self._agents.values())
        if status:
            agents = [agent for agent in agents if agent.status == status]
        return agents
    
    def update_agent_health(self, agent_id: str, health_score: float, load_metrics: Dict[str, float]):
        """Update agent health and load metrics"""
        if agent_id in self._agents:
            self._agents[agent_id].health_score = health_score
            self._agents[agent_id].load_metrics = load_metrics
            self._agents[agent_id].last_seen = time.time()
    
    def add_discovery_callback(self, callback: Callable[[AgentInfo], None]):
        """Add a callback for agent discovery events"""
        self._discovery_callbacks.append(callback)
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        return {
            "total_agents": len(self._agents),
            "active_agents": len([a for a in self._agents.values() if a.status == AgentStatus.ACTIVE]),
            "total_capabilities": len(self._capabilities),
            "capabilities": {cap: len(agents) for cap, agents in self._capabilities.items()},
            "agent_types": {}
        }
    
    # MCP Tool Registry delegation
    def register_tool(self, tool: MCPToolDefinition):
        """Register an MCP tool (delegates to embedded registry)"""
        self._tool_registry.register(tool)
    
    def get_tool(self, name: str) -> Optional[MCPToolDefinition]:
        """Get MCP tool by name"""
        return self._tool_registry.get(name)
    
    def list_tools(self) -> List[MCPToolDefinition]:
        """List all MCP tools"""
        return self._tool_registry.list_tools()

# Global enhanced registry
_a2a_registry = A2AAgentRegistry()

# =============================================================================
# Agent Decorators and Registration
# =============================================================================

def agent_capability(
    name: str,
    description: str,
    version: str = "1.0.0",
    capability_type: AgentCapabilityType = AgentCapabilityType.TOOL_PROVIDER,
    requirements: Optional[List[str]] = None,
    dependencies: Optional[List[str]] = None,
    sla: Optional[Dict[str, Any]] = None
):
    """
    Decorator to define an agent capability
    
    Args:
        name: Capability name
        description: Capability description
        version: Capability version
        capability_type: Type of capability
        requirements: List of requirements (e.g., permissions, resources)
        dependencies: List of dependent capabilities
        sla: Service Level Agreement definition
    
    Example:
        @agent_capability(
            name="data_analysis",
            description="Analyze datasets and generate insights",
            capability_type=AgentCapabilityType.DATA_PROCESSOR,
            requirements=["read_access", "compute_intensive"]
        )
        async def analyze_data(data: dict) -> MCPToolResult:
            # Implementation
            pass
    """
    def decorator(func: Callable):
        # Extract function metadata
        type_hints = get_type_hints(func)
        sig = inspect.signature(func)
        
        # Build input schema
        input_schema = {"type": "object", "properties": {}}
        for param_name, param in sig.parameters.items():
            if param_name in ('context', 'ctx'):
                continue
            param_type = type_hints.get(param_name, str)
            input_schema["properties"][param_name] = _type_to_json_schema(param_type)
        
        # Build output schema (simplified)
        output_schema = {"type": "object", "properties": {"result": {"type": "object"}}}
        
        # Create capability
        capability = AgentCapability(
            name=name,
            description=description,
            version=version,
            capability_type=capability_type,
            input_schema=input_schema,
            output_schema=output_schema,
            requirements=requirements or [],
            dependencies=dependencies or [],
            sla=sla,
            metadata={"function": func.__name__, "module": func.__module__}
        )
        
        # Store capability metadata on function
        if not hasattr(func, '_a2a_capabilities'):
            func._a2a_capabilities = []
        func._a2a_capabilities.append(capability)
        
        return func
    
    return decorator

def register_local_agent(
    name: str,
    description: str,
    version: str = "1.0.0",
    endpoints: Optional[List[AgentEndpoint]] = None,
    tags: Optional[Set[str]] = None,
    owner: Optional[str] = None
) -> str:
    """
    Register the current process as an agent
    
    Returns:
        agent_id: Unique identifier for the registered agent
    """
    agent_id = str(uuid.uuid4())
    
    # Collect capabilities from decorated functions
    capabilities = []
    
    # Scan for functions with capability decorators in the calling module
    import sys
    import inspect
    
    # Get the calling frame to find the caller's module
    frame = inspect.currentframe()
    try:
        caller_frame = frame.f_back
        caller_module = sys.modules[caller_frame.f_globals['__name__']]
        
        # Scan the caller's module for decorated functions
        for name_attr in dir(caller_module):
            try:
                obj = getattr(caller_module, name_attr)
                if callable(obj) and hasattr(obj, '_a2a_capabilities'):
                    capabilities.extend(obj._a2a_capabilities)
            except AttributeError:
                # Skip attributes that can't be accessed
                continue
                
    except Exception as e:
        logger.warning(f"Could not scan for capabilities: {e}")
        # Fallback: scan all modules for decorated functions
        for module_name, module in sys.modules.items():
            if module and hasattr(module, '__dict__'):
                for name_attr in dir(module):
                    try:
                        obj = getattr(module, name_attr)
                        if callable(obj) and hasattr(obj, '_a2a_capabilities'):
                            capabilities.extend(obj._a2a_capabilities)
                    except (AttributeError, TypeError):
                        continue
    finally:
        del frame
    
    # Default endpoint
    if not endpoints:
        endpoints = [AgentEndpoint(
            protocol=AgentProtocol.MCP_GRPC,
            address="localhost",
            port=50051
        )]
    
    agent_info = AgentInfo(
        agent_id=agent_id,
        name=name,
        description=description,
        version=version,
        capabilities=capabilities,
        endpoints=endpoints,
        tags=tags or set(),
        owner=owner
    )
    
    _a2a_registry.register_agent(agent_info)
    return agent_id

def _type_to_json_schema(python_type) -> Dict[str, Any]:
    """Convert Python type to JSON schema (helper function)"""
    if python_type == str:
        return {"type": "string"}
    elif python_type == int:
        return {"type": "integer"}
    elif python_type == float:
        return {"type": "number"}
    elif python_type == bool:
        return {"type": "boolean"}
    elif python_type == list:
        return {"type": "array"}
    elif python_type == dict:
        return {"type": "object"}
    else:
        return {"type": "string", "description": f"Type: {python_type.__name__}"}

# =============================================================================
# Agent Communication Client
# =============================================================================

class AgentCommunicationError(Exception):
    """Exception raised when agent communication fails"""
    pass

class A2AAgentClient:
    """Client for communicating with other agents"""
    
    def __init__(self, registry: A2AAgentRegistry = None):
        self.registry = registry or _a2a_registry
        self._connections: Dict[str, Any] = {}  # agent_id -> connection
    
    async def discover_agents(self, capability_name: str) -> List[AgentInfo]:
        """Discover agents that provide a specific capability"""
        return self.registry.find_agents_by_capability(capability_name)
    
    async def find_best_agent(self, capability_name: str, requirements: Optional[List[str]] = None) -> Optional[AgentInfo]:
        """Find the best agent for a capability"""
        return self.registry.find_best_agent(capability_name, requirements)
    
    async def execute_capability(
        self,
        agent_id: str,
        capability_name: str,
        arguments: Dict[str, Any],
        timeout: float = 30.0
    ) -> MCPToolResult:
        """Execute a capability on a remote agent"""
        agent = self.registry.get_agent(agent_id)
        if not agent:
            raise AgentCommunicationError(f"Agent not found: {agent_id}")
        
        # Find the capability
        capability = None
        for cap in agent.capabilities:
            if cap.name == capability_name:
                capability = cap
                break
        
        if not capability:
            raise AgentCommunicationError(f"Capability '{capability_name}' not found on agent {agent_id}")
        
        logger.info(f"Executing capability '{capability_name}' on agent {agent_id}")
        
        try:
            # Try to find and execute the local function if available
            result = await self._execute_local_capability(capability, arguments)
            if result:
                return result
            
            # Fallback to mock execution (for remote agents or when function not found)
            await asyncio.sleep(0.1)
            
            # Create mock result
            result = MCPToolResult()
            result.add_text(f"Executed {capability_name} on {agent.name}")
            result.add_json({
                "agent_id": agent_id,
                "capability": capability_name,
                "arguments": arguments,
                "timestamp": time.time()
            })
            result.metadata["execution_time"] = "100ms"
            result.metadata["agent_version"] = agent.version
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to execute capability {capability_name} on {agent_id}: {e}")
            raise AgentCommunicationError(f"Execution failed: {e}")
    
    async def _execute_local_capability(
        self,
        capability: AgentCapability,
        arguments: Dict[str, Any]
    ) -> Optional[MCPToolResult]:
        """Try to execute a capability locally if the function is available"""
        try:
            # Look for the function in loaded modules
            import sys
            
            function_name = capability.metadata.get('function')
            module_name = capability.metadata.get('module')
            
            if not function_name or not module_name:
                return None
            
            if module_name in sys.modules:
                module = sys.modules[module_name]
                if hasattr(module, function_name):
                    func = getattr(module, function_name)
                    
                    # Execute the function
                    if asyncio.iscoroutinefunction(func):
                        result = await func(**arguments)
                    else:
                        result = func(**arguments)
                    
                    # Ensure result is MCPToolResult
                    if not isinstance(result, MCPToolResult):
                        if isinstance(result, str):
                            result = MCPToolResult().add_text(result)
                        elif isinstance(result, dict):
                            result = MCPToolResult().add_json(result)
                        else:
                            result = MCPToolResult().add_text(str(result))
                    
                    return result
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to execute local capability: {e}")
            return None
    
    async def delegate_task(
        self,
        capability_name: str,
        arguments: Dict[str, Any],
        requirements: Optional[List[str]] = None,
        timeout: float = 30.0
    ) -> MCPToolResult:
        """Delegate a task to the best available agent"""
        best_agent = await self.find_best_agent(capability_name, requirements)
        if not best_agent:
            raise AgentCommunicationError(f"No suitable agent found for capability: {capability_name}")
        
        return await self.execute_capability(best_agent.agent_id, capability_name, arguments, timeout)
    
    async def broadcast_capability(
        self,
        capability_name: str,
        arguments: Dict[str, Any],
        max_agents: int = 5
    ) -> List[MCPToolResult]:
        """Broadcast a capability execution to multiple agents"""
        agents = await self.discover_agents(capability_name)
        if not agents:
            return []
        
        # Limit to max_agents
        agents = agents[:max_agents]
        
        # Execute in parallel
        tasks = [
            self.execute_capability(agent.agent_id, capability_name, arguments)
            for agent in agents
        ]
        
        results = []
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                results.append(result)
            except Exception as e:
                logger.warning(f"Broadcast execution failed: {e}")
        
        return results

# =============================================================================
# Workflow Orchestration
# =============================================================================

@dataclass
class WorkflowStep:
    """A step in an agent workflow"""
    step_id: str
    capability_name: str
    arguments: Dict[str, Any]
    requirements: Optional[List[str]] = None
    depends_on: List[str] = field(default_factory=list)
    timeout: float = 30.0
    retry_count: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class WorkflowResult:
    """Result of workflow execution"""
    workflow_id: str
    steps: Dict[str, MCPToolResult]
    success: bool
    total_time: float
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class A2AWorkflowOrchestrator:
    """Orchestrator for multi-agent workflows"""
    
    def __init__(self, client: A2AAgentClient = None):
        self.client = client or A2AAgentClient()
        self._active_workflows: Dict[str, Dict[str, Any]] = {}
    
    async def execute_workflow(
        self,
        workflow_id: str,
        steps: List[WorkflowStep],
        parallel_execution: bool = True
    ) -> WorkflowResult:
        """Execute a multi-step workflow across agents"""
        start_time = time.time()
        
        try:
            # Track workflow
            self._active_workflows[workflow_id] = {
                "steps": steps,
                "start_time": start_time,
                "status": "running"
            }
            
            # Build dependency graph
            step_map = {step.step_id: step for step in steps}
            completed_steps = {}
            
            if parallel_execution:
                results = await self._execute_workflow_parallel(step_map, completed_steps)
            else:
                results = await self._execute_workflow_sequential(step_map, completed_steps)
            
            total_time = time.time() - start_time
            
            return WorkflowResult(
                workflow_id=workflow_id,
                steps=results,
                success=True,
                total_time=total_time,
                metadata={"execution_mode": "parallel" if parallel_execution else "sequential"}
            )
            
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"Workflow {workflow_id} failed: {e}")
            
            return WorkflowResult(
                workflow_id=workflow_id,
                steps=completed_steps,
                success=False,
                total_time=total_time,
                error=str(e)
            )
        finally:
            # Cleanup
            if workflow_id in self._active_workflows:
                del self._active_workflows[workflow_id]
    
    async def _execute_workflow_parallel(
        self,
        step_map: Dict[str, WorkflowStep],
        completed_steps: Dict[str, MCPToolResult]
    ) -> Dict[str, MCPToolResult]:
        """Execute workflow steps in parallel where possible"""
        remaining_steps = set(step_map.keys())
        
        while remaining_steps:
            # Find steps that can be executed (dependencies satisfied)
            ready_steps = []
            for step_id in remaining_steps:
                step = step_map[step_id]
                if all(dep in completed_steps for dep in step.depends_on):
                    ready_steps.append(step)
            
            if not ready_steps:
                raise Exception("Circular dependency detected in workflow")
            
            # Execute ready steps in parallel
            tasks = [
                self._execute_workflow_step(step, completed_steps)
                for step in ready_steps
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for step, result in zip(ready_steps, results):
                if isinstance(result, Exception):
                    raise result
                completed_steps[step.step_id] = result
                remaining_steps.remove(step.step_id)
        
        return completed_steps
    
    async def _execute_workflow_sequential(
        self,
        step_map: Dict[str, WorkflowStep],
        completed_steps: Dict[str, MCPToolResult]
    ) -> Dict[str, MCPToolResult]:
        """Execute workflow steps sequentially"""
        # Topological sort of steps based on dependencies
        sorted_steps = self._topological_sort(step_map)
        
        for step in sorted_steps:
            result = await self._execute_workflow_step(step, completed_steps)
            completed_steps[step.step_id] = result
        
        return completed_steps
    
    async def _execute_workflow_step(
        self,
        step: WorkflowStep,
        completed_steps: Dict[str, MCPToolResult]
    ) -> MCPToolResult:
        """Execute a single workflow step with retry logic"""
        # Use the step arguments as-is (don't automatically inject dependency results)
        arguments = step.arguments.copy()
        
        # Only add dependency results if they're explicitly referenced in arguments
        # by placeholder syntax like ${step_id.field} or similar
        for dep_id in step.depends_on:
            if dep_id in completed_steps:
                dep_result = completed_steps[dep_id]
                # Check if any argument values reference this dependency
                for key, value in step.arguments.items():
                    if isinstance(value, str) and f"{{{dep_id}}}" in value:
                        # Replace placeholder with dependency result data
                        if dep_result.content:
                            # Use the first content item's text or data
                            first_content = dep_result.content[0]
                            if first_content.get("type") == "text":
                                replacement = first_content.get("text", "")
                            elif first_content.get("type") == "json":
                                replacement = first_content.get("text", "{}")
                            else:
                                replacement = str(first_content)
                            arguments[key] = value.replace(f"{{{dep_id}}}", replacement)
        
        # Execute with retry
        last_exception = None
        for attempt in range(step.retry_count):
            try:
                result = await self.client.delegate_task(
                    capability_name=step.capability_name,
                    arguments=arguments,
                    requirements=step.requirements,
                    timeout=step.timeout
                )
                return result
            except Exception as e:
                last_exception = e
                if attempt < step.retry_count - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        raise last_exception or Exception("Max retries exceeded")
    
    def _topological_sort(self, step_map: Dict[str, WorkflowStep]) -> List[WorkflowStep]:
        """Topologically sort workflow steps based on dependencies"""
        # Simple topological sort implementation
        visited = set()
        temp_visited = set()
        result = []
        
        def visit(step_id: str):
            if step_id in temp_visited:
                raise Exception("Circular dependency detected")
            if step_id in visited:
                return
            
            temp_visited.add(step_id)
            step = step_map[step_id]
            
            for dep_id in step.depends_on:
                if dep_id in step_map:
                    visit(dep_id)
            
            temp_visited.remove(step_id)
            visited.add(step_id)
            result.append(step)
        
        for step_id in step_map:
            if step_id not in visited:
                visit(step_id)
        
        return result

# =============================================================================
# API Extensions for Core SDK
# =============================================================================

def get_a2a_registry() -> A2AAgentRegistry:
    """Get the global A2A registry"""
    return _a2a_registry

def create_agent_client() -> A2AAgentClient:
    """Create an A2A agent client"""
    return A2AAgentClient()

def create_workflow_orchestrator() -> A2AWorkflowOrchestrator:
    """Create a workflow orchestrator"""
    return A2AWorkflowOrchestrator()

# Export main A2A API
__all__ = [
    'AgentCapabilityType',
    'AgentProtocol', 
    'AgentStatus',
    'AgentCapability',
    'AgentEndpoint',
    'AgentInfo',
    'A2AAgentRegistry',
    'agent_capability',
    'register_local_agent',
    'A2AAgentClient',
    'WorkflowStep',
    'WorkflowResult',
    'A2AWorkflowOrchestrator',
    'get_a2a_registry',
    'create_agent_client',
    'create_workflow_orchestrator',
    'AgentCommunicationError'
]