"""
Demo App: AI-Powered Content Creation System
Using gRPC-MCP SDK with A2A capabilities and Anthropic's Claude API

This demo showcases:
1. Multiple AI agents powered by Claude API
2. Agent-to-agent communication via A2A protocol
3. Multi-agent workflow orchestration
4. Real-world AI capabilities integrated with our SDK

Agents:
- Research Agent: Generates research insights using Claude
- Writing Agent: Creates content using Claude
- Analysis Agent: Analyzes and improves content using Claude
"""

import asyncio
import logging
import os
import sys
from typing import Dict, Any, List

# Add the parent directory to sys.path to import the local grpc_mcp_sdk
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our SDK
from grpc_mcp_sdk import (
    mcp_tool, MCPToolResult, is_a2a_available,
    agent_capability, register_local_agent, 
    AgentCapabilityType, WorkflowStep,
    create_agent_client, create_workflow_orchestrator
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Check for Anthropic API
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("Anthropic package not available. Install with: pip install anthropic")

# =============================================================================
# AI-Powered Agents using Claude API
# =============================================================================

def get_claude_client():
    """Get Claude client with API key from environment"""
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    return anthropic.Anthropic(api_key=api_key)

@agent_capability(
    name="research_topic",
    description="Research a topic and generate insights using AI",
    capability_type=AgentCapabilityType.KNOWLEDGE_BASE,
    requirements=["anthropic_api"],
    version="1.0.0"
)
@mcp_tool(description="Research a topic using Claude AI")
async def research_topic(topic: str, focus_areas: str = "general analysis") -> MCPToolResult:
    """Research a topic using Claude AI to generate insights and questions"""
    
    if not ANTHROPIC_AVAILABLE:
        return MCPToolResult().set_error("Anthropic package not available")
    
    try:
        client = get_claude_client()
        
        prompt = f"""Research the topic: "{topic}"

Focus areas: {focus_areas}

Please provide:
1. Key insights and important points about this topic
2. 3-5 research questions that would be valuable to explore
3. Current trends or developments in this area
4. Potential applications or implications

Keep your response structured and informative, suitable for further content creation."""

        logger.info(f"Researching topic: {topic}")
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",  # Using Haiku for faster/cheaper responses
            max_tokens=1000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        research_content = response.content[0].text
        
        result = MCPToolResult()
        result.add_text(f"Research completed for topic: {topic}")
        result.add_json({
            "topic": topic,
            "focus_areas": focus_areas,
            "research_content": research_content,
            "word_count": len(research_content.split()),
            "timestamp": asyncio.get_event_loop().time()
        })
        result.metadata["model"] = "claude-3-haiku-20240307"
        result.metadata["agent_type"] = "research"
        
        return result
        
    except Exception as e:
        logger.error(f"Research failed: {e}")
        return MCPToolResult().set_error(f"Research failed: {str(e)}")

@agent_capability(
    name="create_content",
    description="Create written content using AI based on research",
    capability_type=AgentCapabilityType.DATA_PROCESSOR,
    requirements=["anthropic_api"],
    dependencies=["research_topic"],
    version="1.0.0"
)
@mcp_tool(description="Create content using Claude AI")
async def create_content(
    topic: str, 
    content_type: str = "article", 
    research_data: str = "",
    tone: str = "professional"
) -> MCPToolResult:
    """Create content using Claude AI based on topic and research"""
    
    if not ANTHROPIC_AVAILABLE:
        return MCPToolResult().set_error("Anthropic package not available")
    
    try:
        client = get_claude_client()
        
        research_context = f"\n\nResearch Context:\n{research_data}" if research_data else ""
        
        prompt = f"""Create a {content_type} about: "{topic}"

Tone: {tone}
{research_context}

Please create engaging, well-structured content that:
1. Has a compelling introduction
2. Covers key points thoroughly
3. Includes practical insights or examples
4. Has a strong conclusion
5. Is appropriate for the specified tone

Target length: 300-500 words."""

        logger.info(f"Creating {content_type} about: {topic}")
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1500,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        content = response.content[0].text
        
        result = MCPToolResult()
        result.add_text(f"Content created: {content_type} about {topic}")
        result.add_text(f"\n--- CONTENT ---\n{content}\n--- END CONTENT ---")
        result.add_json({
            "topic": topic,
            "content_type": content_type,
            "tone": tone,
            "content": content,
            "word_count": len(content.split()),
            "character_count": len(content)
        })
        result.metadata["model"] = "claude-3-haiku-20240307"
        result.metadata["agent_type"] = "writer"
        
        return result
        
    except Exception as e:
        logger.error(f"Content creation failed: {e}")
        return MCPToolResult().set_error(f"Content creation failed: {str(e)}")

@agent_capability(
    name="analyze_content",
    description="Analyze and improve content using AI",
    capability_type=AgentCapabilityType.DATA_PROCESSOR,
    requirements=["anthropic_api"],
    dependencies=["create_content"],
    version="1.0.0"
)
@mcp_tool(description="Analyze content and suggest improvements using Claude AI")
async def analyze_content(content: str, analysis_type: str = "comprehensive") -> MCPToolResult:
    """Analyze content and provide improvement suggestions using Claude AI"""
    
    if not ANTHROPIC_AVAILABLE:
        return MCPToolResult().set_error("Anthropic package not available")
    
    try:
        client = get_claude_client()
        
        if analysis_type == "comprehensive":
            prompt = f"""Analyze this content and provide comprehensive feedback:

{content}

Please provide:
1. Overall assessment (strengths and weaknesses)
2. Readability and clarity analysis
3. Structure and flow evaluation
4. Specific suggestions for improvement
5. Rating out of 10 for different aspects (clarity, engagement, structure)

Be constructive and specific in your feedback."""
        
        elif analysis_type == "brief":
            prompt = f"""Provide a brief analysis of this content:

{content}

Give a concise assessment focusing on:
- Main strengths
- Key areas for improvement
- Overall rating (1-10)"""
        
        else:
            prompt = f"""Analyze this content focusing on: {analysis_type}

{content}

Provide targeted feedback based on the specified focus area."""

        logger.info(f"Analyzing content ({analysis_type} analysis)")
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=800,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        analysis = response.content[0].text
        
        result = MCPToolResult()
        result.add_text(f"Content analysis completed ({analysis_type})")
        result.add_text(f"\n--- ANALYSIS ---\n{analysis}\n--- END ANALYSIS ---")
        result.add_json({
            "analysis_type": analysis_type,
            "analysis": analysis,
            "original_content_length": len(content),
            "analysis_length": len(analysis)
        })
        result.metadata["model"] = "claude-3-haiku-20240307"
        result.metadata["agent_type"] = "analyzer"
        
        return result
        
    except Exception as e:
        logger.error(f"Content analysis failed: {e}")
        return MCPToolResult().set_error(f"Content analysis failed: {str(e)}")

@agent_capability(
    name="summarize_session",
    description="Summarize the results of a content creation session",
    capability_type=AgentCapabilityType.COORDINATOR,
    version="1.0.0"
)
@mcp_tool(description="Summarize workflow results")
async def summarize_session(
    topic: str,
    research_summary: str = "",
    content_summary: str = "",
    analysis_summary: str = ""
) -> MCPToolResult:
    """Summarize the complete content creation session"""
    
    summary = f"""
# Content Creation Session Summary

## Topic: {topic}

## Research Phase:
{research_summary if research_summary else "No research data available"}

## Content Creation Phase:
{content_summary if content_summary else "No content data available"}

## Analysis Phase:
{analysis_summary if analysis_summary else "No analysis data available"}

## Session Complete
All phases of the content creation workflow have been completed successfully.
"""
    
    result = MCPToolResult()
    result.add_text("Content creation session completed successfully")
    result.add_text(summary)
    result.add_json({
        "topic": topic,
        "phases_completed": ["research", "content_creation", "analysis"],
        "summary": summary.strip()
    })
    result.metadata["agent_type"] = "coordinator"
    
    return result

# =============================================================================
# Demo Application
# =============================================================================

async def run_content_creation_workflow(topic: str, content_type: str = "article", tone: str = "professional"):
    """Run a complete content creation workflow using multiple AI agents"""
    
    logger.info(f"🚀 Starting Content Creation Workflow for: {topic}")
    
    if not is_a2a_available():
        logger.error("❌ A2A functionality not available")
        return
    
    if not ANTHROPIC_AVAILABLE:
        logger.error("❌ Anthropic package not available. Install with: pip install anthropic")
        return
    
    try:
        # Test API key
        get_claude_client()
    except ValueError as e:
        logger.error(f"❌ {e}")
        logger.info("💡 Set your API key with: export ANTHROPIC_API_KEY=your_api_key_here")
        return
    except Exception as e:
        logger.error(f"❌ Failed to initialize Claude client: {e}")
        return
    
    # Register our agents
    agent_id = register_local_agent(
        name="AI Content Creation System",
        description="Multi-agent system for AI-powered content creation using Claude",
        version="1.0.0",
        tags={"ai", "content", "claude", "demo"}
    )
    
    logger.info(f"📝 Registered agent system: {agent_id}")
    
    # Create workflow orchestrator
    orchestrator = create_workflow_orchestrator()
    
    # Define the complete workflow
    workflow_steps = [
        WorkflowStep(
            step_id="research",
            capability_name="research_topic",
            arguments={
                "topic": topic,
                "focus_areas": f"Key insights for {content_type} creation"
            },
            timeout=30.0
        ),
        WorkflowStep(
            step_id="content_creation",
            capability_name="create_content",
            arguments={
                "topic": topic,
                "content_type": content_type,
                "tone": tone,
                "research_data": ""  # Will be populated from research step
            },
            depends_on=["research"],
            timeout=45.0
        ),
        WorkflowStep(
            step_id="content_analysis",
            capability_name="analyze_content",
            arguments={
                "content": "",  # Will be populated from content creation step
                "analysis_type": "comprehensive"
            },
            depends_on=["content_creation"],
            timeout=30.0
        ),
        WorkflowStep(
            step_id="session_summary",
            capability_name="summarize_session",
            arguments={
                "topic": topic,
                "research_summary": "",
                "content_summary": "",
                "analysis_summary": ""
            },
            depends_on=["research", "content_creation", "content_analysis"],
            timeout=15.0
        )
    ]
    
    # Execute the workflow
    workflow_id = f"content_creation_{topic.replace(' ', '_')}"
    
    try:
        logger.info("⚡ Executing multi-agent workflow...")
        result = await orchestrator.execute_workflow(
            workflow_id=workflow_id,
            steps=workflow_steps,
            parallel_execution=True  # Research can run in parallel with content creation where dependencies allow
        )
        
        if result.success:
            logger.info(f"✅ Workflow completed successfully in {result.total_time:.2f}s")
            
            # Display results
            print("\n" + "="*60)
            print("🎯 CONTENT CREATION WORKFLOW RESULTS")
            print("="*60)
            
            for step_id, step_result in result.steps.items():
                print(f"\n📋 {step_id.upper()} RESULTS:")
                print("-" * 40)
                
                for content in step_result.content:
                    if content["type"] == "text":
                        print(content["text"])
                    elif content["type"] == "json":
                        # For JSON content, extract and display nicely
                        import json
                        try:
                            data = json.loads(content["text"])
                            if "research_content" in data:
                                print(f"Research Content:\n{data['research_content']}")
                            elif "content" in data:
                                print(f"Generated Content:\n{data['content']}")
                            elif "analysis" in data:
                                print(f"Analysis:\n{data['analysis']}")
                        except:
                            print(content["text"])
            
            print("\n" + "="*60)
            print("🎉 WORKFLOW COMPLETED SUCCESSFULLY!")
            print("="*60)
            
        else:
            logger.error(f"❌ Workflow failed: {result.error}")
            print(f"\n❌ Workflow failed: {result.error}")
            
    except Exception as e:
        logger.error(f"💥 Workflow execution failed: {e}")
        print(f"\n💥 Workflow execution failed: {e}")

async def run_simple_demo():
    """Run a simple demo showing individual agent capabilities"""
    
    logger.info("🔬 Running Simple AI Agent Demo")
    
    if not ANTHROPIC_AVAILABLE:
        print("❌ Anthropic package not available. Install with: pip install anthropic")
        return
    
    try:
        get_claude_client()
    except ValueError:
        print("❌ ANTHROPIC_API_KEY environment variable not set")
        print("💡 Set your API key with: export ANTHROPIC_API_KEY=your_api_key_here")
        return
    except Exception as e:
        print(f"❌ Failed to initialize Claude client: {e}")
        return
    
    # Register agent
    agent_id = register_local_agent(
        name="Simple AI Demo Agent",
        description="Demonstrates individual AI agent capabilities"
    )
    
    print(f"📝 Registered agent: {agent_id}")
    
    # Test individual capabilities
    topic = "Artificial Intelligence in Healthcare"
    
    print(f"\n🔍 Researching: {topic}")
    research_result = await research_topic(topic, "current applications and future potential")
    
    if not research_result.is_error:
        print("✅ Research completed")
        
        # Extract research content for content creation
        research_content = ""
        for content in research_result.content:
            if content["type"] == "json":
                import json
                try:
                    data = json.loads(content["text"])
                    research_content = data.get("research_content", "")
                except:
                    pass
        
        print(f"\n✍️ Creating content about: {topic}")
        content_result = await create_content(topic, "blog post", research_content, "engaging")
        
        if not content_result.is_error:
            print("✅ Content created")
            
            # Extract content for analysis
            created_content = ""
            for content in content_result.content:
                if content["type"] == "json":
                    import json
                    try:
                        data = json.loads(content["text"])
                        created_content = data.get("content", "")
                    except:
                        pass
            
            if created_content:
                print(f"\n📊 Analyzing content...")
                analysis_result = await analyze_content(created_content, "brief")
                
                if not analysis_result.is_error:
                    print("✅ Analysis completed")
                    
                    # Display final results
                    print("\n" + "="*50)
                    print("🎯 DEMO RESULTS")
                    print("="*50)
                    
                    for content in content_result.content:
                        if content["type"] == "text" and "CONTENT" in content["text"]:
                            print(content["text"])
                    
                    for content in analysis_result.content:
                        if content["type"] == "text" and "ANALYSIS" in content["text"]:
                            print(content["text"])
    
    print("\n🎉 Simple demo completed!")

async def main():
    """Main demo application"""
    
    print("🚀 AI-Powered Content Creation Demo")
    print("Using gRPC-MCP SDK with A2A capabilities + Anthropic Claude API")
    print("=" * 60)
    
    # Check prerequisites
    if not is_a2a_available():
        print("❌ A2A functionality not available")
        return
    
    if not ANTHROPIC_AVAILABLE:
        print("❌ Anthropic package not available")
        print("💡 Install with: pip install anthropic")
        return
    
    # Check API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("❌ ANTHROPIC_API_KEY environment variable not set")
        print("💡 Set your API key with: export ANTHROPIC_API_KEY=your_api_key_here")
        print("💡 You can get an API key from: https://console.anthropic.com/")
        return
    
    print("✅ All prerequisites met!")
    
    # Show menu
    print("\nChoose demo mode:")
    print("1. Full Workflow Demo (recommended)")
    print("2. Simple Agent Demo")
    print("3. Custom Topic Workflow")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        # Full workflow demo
        await run_content_creation_workflow(
            topic="The Future of Sustainable Energy",
            content_type="article",
            tone="informative"
        )
    
    elif choice == "2":
        # Simple demo
        await run_simple_demo()
    
    elif choice == "3":
        # Custom topic
        topic = input("Enter topic: ").strip()
        content_type = input("Content type (article/blog post/summary): ").strip() or "article"
        tone = input("Tone (professional/casual/engaging): ").strip() or "professional"
        
        await run_content_creation_workflow(topic, content_type, tone)
    
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Demo interrupted by user")
    except Exception as e:
        print(f"\n💥 Demo failed: {e}")
        logger.exception("Demo failed")