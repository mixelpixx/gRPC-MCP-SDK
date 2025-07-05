# AI-Powered Content Creation Demo

This demo showcases the power of combining **gRPC-MCP SDK with A2A capabilities** and **Anthropic's Claude API** to create an intelligent multi-agent content creation system.

## 🌟 What This Demo Does

The demo creates a sophisticated AI-powered content creation workflow using multiple specialized agents:

1. **Research Agent** - Uses Claude AI to research topics and generate insights
2. **Writing Agent** - Creates high-quality content based on research
3. **Analysis Agent** - Analyzes content and provides improvement suggestions
4. **Coordinator Agent** - Summarizes the entire workflow process

All agents communicate using our **A2A (Agent-to-Agent) protocol**, demonstrating real-world multi-agent AI orchestration.

## 🚀 Features Demonstrated

- ✅ **Multi-Agent AI System** - Multiple specialized Claude-powered agents
- ✅ **A2A Communication** - Agents discover and communicate with each other
- ✅ **Workflow Orchestration** - Complex multi-step workflows with dependencies
- ✅ **Real AI Integration** - Live Claude API integration for actual AI capabilities
- ✅ **Error Handling** - Robust error handling and graceful degradation
- ✅ **Performance** - High-performance gRPC transport with streaming support

## 📋 Prerequisites

### 1. Anthropic API Key
You need an API key from Anthropic to use Claude:

1. Visit [Anthropic Console](https://console.anthropic.com/)
2. Create an account if you don't have one
3. Generate an API key
4. Set it as an environment variable:

```bash
# Linux/Mac
export ANTHROPIC_API_KEY="your_api_key_here"

# Windows
set ANTHROPIC_API_KEY=your_api_key_here
```

### 2. Python Dependencies
Install required packages:

```bash
pip install -r requirements.txt
```

Or install individually:
```bash
pip install anthropic>=0.8.0
pip install grpcio grpcio-tools protobuf
```

## 🏃‍♂️ Quick Start

### 1. Set Up Environment
```bash
# Navigate to the demo directory
cd demo

# Set your Anthropic API key
export ANTHROPIC_API_KEY="your_api_key_here"

# Install dependencies
pip install -r requirements.txt
```

### 2. Run the Demo
```bash
python demo_app.py
```

### 3. Choose Demo Mode
The app will present you with options:

1. **Full Workflow Demo** (recommended) - Complete content creation pipeline
2. **Simple Agent Demo** - Test individual agent capabilities
3. **Custom Topic Workflow** - Create content on your chosen topic

## 🎯 Demo Modes Explained

### Full Workflow Demo
Demonstrates the complete content creation pipeline:

```
Research Agent → Writing Agent → Analysis Agent → Coordinator
     ↓              ↓              ↓               ↓
  AI Research → AI Content → AI Analysis → Final Summary
```

**Topic**: "The Future of Sustainable Energy"
**Output**: Research insights, article content, analysis feedback, and complete summary

### Simple Agent Demo
Tests each agent individually with a healthcare AI topic:
- Shows research capabilities
- Demonstrates content creation
- Provides content analysis

### Custom Topic Workflow
Let's you specify:
- **Topic**: Any subject you want content about
- **Content Type**: Article, blog post, summary, etc.
- **Tone**: Professional, casual, engaging, etc.

## 📊 Sample Output

When you run the demo, you'll see output like:

```
🚀 AI-Powered Content Creation Demo
Using gRPC-MCP SDK with A2A capabilities + Anthropic Claude API
============================================================
✅ All prerequisites met!

Choose demo mode:
1. Full Workflow Demo (recommended)
2. Simple Agent Demo  
3. Custom Topic Workflow

Enter choice (1-3): 1

🚀 Starting Content Creation Workflow for: The Future of Sustainable Energy
📝 Registered agent system: abc-123-def
⚡ Executing multi-agent workflow...
✅ Workflow completed successfully in 15.32s

============================================================
🎯 CONTENT CREATION WORKFLOW RESULTS
============================================================

📋 RESEARCH RESULTS:
----------------------------------------
Research completed for topic: The Future of Sustainable Energy

Research Content:
The future of sustainable energy is rapidly evolving with breakthrough 
technologies in solar, wind, and battery storage...

📋 CONTENT_CREATION RESULTS:
----------------------------------------
Content created: article about The Future of Sustainable Energy

--- CONTENT ---
# The Future of Sustainable Energy: A New Dawn

As we stand at the crossroads of environmental necessity and 
technological innovation...
--- END CONTENT ---

📋 CONTENT_ANALYSIS RESULTS:
----------------------------------------
Content analysis completed (comprehensive)

--- ANALYSIS ---
Overall Assessment:
The article demonstrates strong technical knowledge and presents 
a balanced view of sustainable energy developments...
--- END ANALYSIS ---

============================================================
🎉 WORKFLOW COMPLETED SUCCESSFULLY!
============================================================
```

## 🔧 Technical Architecture

### Agent Capabilities
Each agent is defined using our SDK decorators:

```python
@agent_capability(
    name="research_topic",
    description="Research a topic and generate insights using AI",
    capability_type=AgentCapabilityType.KNOWLEDGE_BASE,
    requirements=["anthropic_api"],
    version="1.0.0"
)
@mcp_tool(description="Research a topic using Claude AI")
async def research_topic(topic: str, focus_areas: str = "general analysis") -> MCPToolResult:
    # Claude API integration here
    pass
```

### A2A Communication
Agents discover and communicate through our A2A protocol:

```python
# Register agents
agent_id = register_local_agent("AI Content Creation System", ...)

# Create workflow
orchestrator = create_workflow_orchestrator()

# Define multi-agent workflow with dependencies
workflow_steps = [
    WorkflowStep("research", "research_topic", {...}),
    WorkflowStep("content_creation", "create_content", {...}, depends_on=["research"]),
    # ... more steps
]

# Execute with A2A coordination
result = await orchestrator.execute_workflow(workflow_id, workflow_steps)
```

### Claude API Integration
Each agent uses Claude for AI capabilities:

```python
client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

response = client.messages.create(
    model="claude-3-haiku-20240307",
    max_tokens=1000,
    messages=[{"role": "user", "content": prompt}]
)
```

## 🛠️ Customization

### Adding New Agents
Create new agents by adding functions with our decorators:

```python
@agent_capability(
    name="your_capability",
    description="What your agent does",
    capability_type=AgentCapabilityType.DATA_PROCESSOR
)
@mcp_tool(description="Your tool description")
async def your_agent(param: str) -> MCPToolResult:
    # Your Claude API logic here
    client = get_claude_client()
    response = client.messages.create(...)
    return MCPToolResult().add_text(response.content[0].text)
```

### Modifying Workflows
Adjust the workflow steps in `run_content_creation_workflow()`:

```python
workflow_steps = [
    WorkflowStep("step1", "capability1", {...}),
    WorkflowStep("step2", "capability2", {...}, depends_on=["step1"]),
    # Add more steps or modify dependencies
]
```

### Changing AI Models
Update the Claude model in the agent functions:

```python
response = client.messages.create(
    model="claude-3-sonnet-20240229",  # Use Sonnet for better quality
    max_tokens=2000,                   # Increase for longer content
    messages=[{"role": "user", "content": prompt}]
)
```

## ⚠️ Important Notes

### API Costs
- Demo uses Claude 3 Haiku (fastest/cheapest model)
- Full workflow typically costs ~$0.05-0.10 per run
- Monitor your usage at [Anthropic Console](https://console.anthropic.com/)

### Rate Limits
- Anthropic has rate limits on API calls
- Demo includes error handling for rate limit exceeded
- For production use, implement proper rate limiting

### Error Handling
The demo includes comprehensive error handling:
- Missing API key detection
- Claude API error handling
- Workflow failure recovery
- Network timeout handling

## 🐛 Troubleshooting

### "ANTHROPIC_API_KEY environment variable not set"
```bash
# Make sure to set your API key
export ANTHROPIC_API_KEY="sk-ant-..."
```

### "Anthropic package not available"
```bash
pip install anthropic
```

### "A2A functionality not available"
Make sure you're running from the correct directory with the local SDK.

### API Rate Limit Errors
- Wait a moment and try again
- Check your API usage at Anthropic Console
- Consider upgrading your API plan

## 🌟 What This Demonstrates

This demo proves that our gRPC-MCP SDK with A2A capabilities can:

1. **Integrate Real AI Services** - Live Claude API integration
2. **Orchestrate Complex Workflows** - Multi-step AI pipelines
3. **Enable Agent Communication** - True agent-to-agent collaboration
4. **Maintain High Performance** - Fast gRPC transport
5. **Scale Production Systems** - Enterprise-ready architecture

Perfect for building:
- AI content creation systems
- Research and analysis pipelines
- Multi-agent AI assistants
- Automated content workflows
- AI-powered business processes

## 🎉 Success!

If you can run this demo successfully, you have a working AI-powered multi-agent system using our cutting-edge gRPC-MCP SDK with A2A capabilities!

Ready to build the future of AI agent collaboration! 🚀