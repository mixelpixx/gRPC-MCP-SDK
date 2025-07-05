"""
Multi-Agent MCP Tool Demo
=========================

This demonstrates building an MCP tool that appears as a single "research_and_analyze" tool
to external LLM clients (like Claude, GPT, etc.), but internally uses multiple specialized 
agents collaborating via A2A protocol to provide comprehensive results.

From the LLM client's perspective: One powerful research tool
Behind the scenes: Multiple AI agents working together

Agents:
- Research Agent: Gathers comprehensive information using Claude
- Analysis Agent: Performs deep analysis of research data  
- Fact Checker Agent: Validates claims and assesses credibility
- Synthesis Agent: Combines all insights into a unified report

This showcases how our gRPC-MCP SDK enables building sophisticated multi-agent tools
that present a simple interface while delivering complex, coordinated AI capabilities.
"""

import asyncio
import logging
import os
import sys
import json
from typing import Dict, Any, List

# Add the parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grpc_mcp_sdk import (
    mcp_tool, MCPToolResult, is_a2a_available, run_server,
    agent_capability, register_local_agent, 
    AgentCapabilityType, WorkflowStep,
    create_agent_client, create_workflow_orchestrator
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check for Anthropic API
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

def get_claude_client():
    """Get Claude client with API key from environment"""
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    return anthropic.Anthropic(api_key=api_key)

# =============================================================================
# Internal Specialized Agents (Hidden from External LLM Client)
# =============================================================================

@agent_capability(
    name="research_specialist",
    description="Specialized research agent for gathering comprehensive information",
    capability_type=AgentCapabilityType.KNOWLEDGE_BASE,
    requirements=["anthropic_api"],
    version="1.0.0"
)
async def research_specialist(topic: str, research_depth: str = "comprehensive") -> MCPToolResult:
    """Specialized research agent that gathers comprehensive information"""
    
    if not ANTHROPIC_AVAILABLE:
        return MCPToolResult().set_error("Anthropic API not available")
    
    try:
        client = get_claude_client()
        
        if research_depth == "comprehensive":
            prompt = f"""You are a research specialist. Conduct comprehensive research on: "{topic}"

Provide detailed information including:
1. Key concepts and definitions
2. Current state and recent developments  
3. Major stakeholders and players
4. Historical context and evolution
5. Statistical data and trends
6. Multiple perspectives and viewpoints
7. Related topics and connections

Be thorough, accurate, and cite specific examples where possible."""

        elif research_depth == "focused":
            prompt = f"""You are a research specialist. Conduct focused research on: "{topic}"

Provide specific, actionable information including:
1. Core facts and key points
2. Most recent developments
3. Primary sources and authorities
4. Critical success factors
5. Immediate opportunities and challenges

Focus on practical, current, and relevant information."""

        else:
            prompt = f"""Research the topic: "{topic}" with depth level: {research_depth}"""

        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}]
        )
        
        research_content = response.content[0].text
        
        result = MCPToolResult()
        result.add_text(f"Research completed by Research Specialist")
        result.add_json({
            "agent": "research_specialist",
            "topic": topic,
            "depth": research_depth,
            "research_findings": research_content,
            "word_count": len(research_content.split())
        })
        
        return result
        
    except Exception as e:
        return MCPToolResult().set_error(f"Research specialist failed: {str(e)}")

@agent_capability(
    name="analysis_specialist", 
    description="Specialized analysis agent for deep analytical insights",
    capability_type=AgentCapabilityType.DATA_PROCESSOR,
    requirements=["anthropic_api"],
    version="1.0.0"
)
async def analysis_specialist(research_data: str, analysis_focus: str = "insights") -> MCPToolResult:
    """Specialized analysis agent that performs deep analysis of research data"""
    
    if not ANTHROPIC_AVAILABLE:
        return MCPToolResult().set_error("Anthropic API not available")
    
    try:
        client = get_claude_client()
        
        prompt = f"""You are an analysis specialist. Analyze this research data with focus on: {analysis_focus}

Research Data:
{research_data}

Provide analytical insights including:
1. Key patterns and trends identified
2. Cause and effect relationships
3. Strengths, weaknesses, opportunities, threats (SWOT analysis)
4. Quantitative and qualitative assessments
5. Comparative analysis with benchmarks
6. Predictive insights and future implications
7. Strategic recommendations

Be analytical, objective, and provide evidence-based conclusions."""

        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        analysis_content = response.content[0].text
        
        result = MCPToolResult()
        result.add_text(f"Analysis completed by Analysis Specialist")
        result.add_json({
            "agent": "analysis_specialist",
            "focus": analysis_focus,
            "analytical_insights": analysis_content,
            "confidence_level": "high"
        })
        
        return result
        
    except Exception as e:
        return MCPToolResult().set_error(f"Analysis specialist failed: {str(e)}")

@agent_capability(
    name="fact_checker",
    description="Specialized fact-checking agent for validation and credibility assessment",
    capability_type=AgentCapabilityType.DATA_PROCESSOR,
    requirements=["anthropic_api"],
    version="1.0.0"
)
async def fact_checker(content: str) -> MCPToolResult:
    """Specialized fact-checking agent that validates claims and assesses credibility"""
    
    if not ANTHROPIC_AVAILABLE:
        return MCPToolResult().set_error("Anthropic API not available")
    
    try:
        client = get_claude_client()
        
        prompt = f"""You are a fact-checking specialist. Review this content for accuracy and credibility:

Content to fact-check:
{content}

Provide fact-checking assessment including:
1. Verification of key claims and statements
2. Identification of any potential inaccuracies or biases
3. Assessment of source credibility (when sources are mentioned)
4. Confidence levels for major assertions
5. Recommendations for additional verification
6. Overall credibility score (1-10 scale)

Be objective, thorough, and highlight both confirmed facts and areas needing verification."""

        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        
        fact_check_content = response.content[0].text
        
        result = MCPToolResult()
        result.add_text(f"Fact-checking completed by Fact Checker")
        result.add_json({
            "agent": "fact_checker",
            "fact_check_report": fact_check_content,
            "verification_status": "completed"
        })
        
        return result
        
    except Exception as e:
        return MCPToolResult().set_error(f"Fact checker failed: {str(e)}")

@agent_capability(
    name="synthesis_specialist",
    description="Specialized synthesis agent for combining insights into unified reports",
    capability_type=AgentCapabilityType.COORDINATOR,
    requirements=["anthropic_api"],
    version="1.0.0"
)
async def synthesis_specialist(
    research_data: str,
    analysis_data: str, 
    fact_check_data: str,
    output_format: str = "comprehensive_report"
) -> MCPToolResult:
    """Synthesis specialist that combines all agent insights into a unified report"""
    
    if not ANTHROPIC_AVAILABLE:
        return MCPToolResult().set_error("Anthropic API not available")
    
    try:
        client = get_claude_client()
        
        prompt = f"""You are a synthesis specialist. Combine these multiple sources into a unified {output_format}:

RESEARCH FINDINGS:
{research_data}

ANALYTICAL INSIGHTS:
{analysis_data}

FACT-CHECK ASSESSMENT:
{fact_check_data}

Create a comprehensive, well-structured report that:
1. Synthesizes key findings from all sources
2. Presents information in a logical, coherent flow
3. Highlights the most important insights and conclusions
4. Balances different perspectives and findings
5. Provides clear, actionable takeaways
6. Maintains objectivity and credibility

Format as a professional research report suitable for decision-making."""

        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        synthesis_content = response.content[0].text
        
        result = MCPToolResult()
        result.add_text(f"Synthesis completed by Synthesis Specialist")
        result.add_json({
            "agent": "synthesis_specialist",
            "output_format": output_format,
            "unified_report": synthesis_content,
            "sources_integrated": ["research", "analysis", "fact_check"]
        })
        
        return result
        
    except Exception as e:
        return MCPToolResult().set_error(f"Synthesis specialist failed: {str(e)}")

# =============================================================================
# Public MCP Tool (What External LLM Clients See)
# =============================================================================

@mcp_tool(description="Comprehensive research and analysis tool powered by multiple AI specialists")
async def research_and_analyze(
    topic: str,
    research_depth: str = "comprehensive",
    analysis_focus: str = "insights",
    include_fact_check: bool = True,
    output_format: str = "comprehensive_report"
) -> MCPToolResult:
    """
    Comprehensive research and analysis tool that internally uses multiple AI agents
    
    This appears as a single MCP tool to external LLM clients, but uses multiple
    specialized agents working together via A2A protocol.
    
    Args:
        topic: The topic to research and analyze
        research_depth: Level of research (comprehensive, focused, basic)
        analysis_focus: Focus of analysis (insights, trends, opportunities, risks)
        include_fact_check: Whether to include fact-checking validation
        output_format: Format of final output (comprehensive_report, executive_summary, bullet_points)
    
    Returns:
        MCPToolResult: Unified result from multiple collaborating agents
    """
    
    logger.info(f"🔬 Multi-Agent Research & Analysis Tool called for topic: {topic}")
    
    if not is_a2a_available():
        return MCPToolResult().set_error("A2A functionality required but not available")
    
    if not ANTHROPIC_AVAILABLE:
        return MCPToolResult().set_error("Anthropic API required but not available")
    
    try:
        # Register agent system
        agent_id = register_local_agent(
            name="Multi-Agent Research & Analysis System",
            description="Coordinated multi-agent system for comprehensive research and analysis",
            version="1.0.0"
        )
        
        # Create workflow orchestrator  
        orchestrator = create_workflow_orchestrator()
        
        # Define multi-agent workflow
        workflow_steps = [
            WorkflowStep(
                step_id="research",
                capability_name="research_specialist",
                arguments={
                    "topic": topic,
                    "research_depth": research_depth
                },
                timeout=30.0
            ),
            WorkflowStep(
                step_id="analysis",
                capability_name="analysis_specialist",
                arguments={
                    "research_data": "",  # Will be populated from research step
                    "analysis_focus": analysis_focus
                },
                depends_on=["research"],
                timeout=25.0
            )
        ]
        
        # Add fact-checking step if requested
        if include_fact_check:
            workflow_steps.append(
                WorkflowStep(
                    step_id="fact_check",
                    capability_name="fact_checker",
                    arguments={
                        "content": ""  # Will be populated from research step
                    },
                    depends_on=["research"],
                    timeout=20.0
                )
            )
        
        # Add synthesis step
        synthesis_deps = ["research", "analysis"]
        if include_fact_check:
            synthesis_deps.append("fact_check")
            
        workflow_steps.append(
            WorkflowStep(
                step_id="synthesis",
                capability_name="synthesis_specialist",
                arguments={
                    "research_data": "",
                    "analysis_data": "",
                    "fact_check_data": "" if include_fact_check else "Not requested",
                    "output_format": output_format
                },
                depends_on=synthesis_deps,
                timeout=35.0
            )
        )
        
        # Execute multi-agent workflow
        workflow_id = f"research_analysis_{topic.replace(' ', '_')}"
        
        logger.info("⚡ Orchestrating multiple AI agents...")
        result = await orchestrator.execute_workflow(
            workflow_id=workflow_id,
            steps=workflow_steps,
            parallel_execution=True
        )
        
        if result.success:
            logger.info(f"✅ Multi-agent analysis completed in {result.total_time:.2f}s")
            
            # Extract the final synthesis result
            synthesis_result = result.steps.get("synthesis")
            if synthesis_result:
                # Get the unified report from synthesis
                for content in synthesis_result.content:
                    if content["type"] == "json":
                        try:
                            data = json.loads(content["text"])
                            unified_report = data.get("unified_report", "")
                            
                            # Create final result for external LLM client
                            final_result = MCPToolResult()
                            final_result.add_text(f"Research and Analysis Report: {topic}")
                            final_result.add_text(f"\n{unified_report}")
                            
                            # Add metadata about the multi-agent process
                            final_result.add_json({
                                "topic": topic,
                                "research_depth": research_depth,
                                "analysis_focus": analysis_focus,
                                "fact_checked": include_fact_check,
                                "output_format": output_format,
                                "agents_involved": len(workflow_steps),
                                "processing_time": f"{result.total_time:.2f}s",
                                "workflow_success": True
                            })
                            
                            final_result.metadata["multi_agent_system"] = "research_and_analysis"
                            final_result.metadata["agents_count"] = str(len(workflow_steps))
                            final_result.metadata["processing_time"] = f"{result.total_time:.2f}s"
                            
                            return final_result
                            
                        except Exception as e:
                            logger.error(f"Failed to parse synthesis result: {e}")
            
            # Fallback if synthesis parsing fails
            return MCPToolResult().add_text(f"Multi-agent research completed for: {topic}").add_json({
                "status": "completed",
                "agents_executed": len(result.steps),
                "processing_time": f"{result.total_time:.2f}s"
            })
            
        else:
            logger.error(f"❌ Multi-agent workflow failed: {result.error}")
            return MCPToolResult().set_error(f"Multi-agent analysis failed: {result.error}")
            
    except Exception as e:
        logger.error(f"💥 Multi-agent tool execution failed: {e}")
        return MCPToolResult().set_error(f"Research and analysis tool failed: {str(e)}")

# =============================================================================
# Server Setup and Demo
# =============================================================================

async def demo_multi_agent_mcp_tool():
    """Demo the multi-agent MCP tool"""
    
    print("🚀 Multi-Agent MCP Tool Demo")
    print("=" * 50)
    print("This demonstrates an MCP tool that appears as a single tool to LLM clients")
    print("but internally uses multiple AI agents collaborating via A2A protocol.\n")
    
    if not is_a2a_available():
        print("❌ A2A functionality not available")
        return
    
    if not ANTHROPIC_AVAILABLE:
        print("❌ Anthropic package not available. Install with: pip install anthropic")
        return
    
    try:
        get_claude_client()
    except ValueError:
        print("❌ ANTHROPIC_API_KEY environment variable not set")
        return
    
    print("✅ All prerequisites met!")
    
    # Demo the tool
    print("\n🔬 Testing Multi-Agent Research & Analysis Tool")
    print("Topic: 'Artificial Intelligence in Healthcare'")
    print("This will coordinate multiple AI agents internally...\n")
    
    result = await research_and_analyze(
        topic="Artificial Intelligence in Healthcare",
        research_depth="comprehensive", 
        analysis_focus="opportunities",
        include_fact_check=True,
        output_format="comprehensive_report"
    )
    
    if not result.is_error:
        print("✅ Multi-Agent Tool Execution Successful!")
        print("\n" + "="*60)
        print("🎯 UNIFIED RESULT (What LLM Client Sees)")
        print("="*60)
        
        for content in result.content:
            if content["type"] == "text":
                print(content["text"])
            elif content["type"] == "json":
                try:
                    data = json.loads(content["text"])
                    print(f"\nProcessing Summary:")
                    print(f"- Agents involved: {data.get('agents_involved', 'N/A')}")
                    print(f"- Processing time: {data.get('processing_time', 'N/A')}")
                    print(f"- Fact-checked: {data.get('fact_checked', 'N/A')}")
                except:
                    pass
        
        print("\n" + "="*60)
        print("🎉 DEMO COMPLETED SUCCESSFULLY!")
        print("External LLM client sees one powerful tool")
        print("Internal system coordinated multiple AI agents")
        print("="*60)
        
    else:
        print(f"❌ Tool execution failed: {result.error_message}")

async def start_mcp_server():
    """Start MCP server with the multi-agent tool"""
    
    print("🚀 Starting MCP Server with Multi-Agent Tool")
    print("=" * 50)
    print("The 'research_and_analyze' tool will be available to external LLM clients")
    print("Internally, it coordinates multiple AI agents via A2A protocol")
    print("Server starting on localhost:50051...")
    
    if is_a2a_available():
        # Register the multi-agent system
        register_local_agent(
            name="Multi-Agent MCP Tool Server",
            description="MCP server providing multi-agent research and analysis capabilities",
            version="1.0.0"
        )
    
    # Start the gRPC MCP server
    await run_server(host="0.0.0.0", port=50051)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        # Run interactive demo
        asyncio.run(demo_multi_agent_mcp_tool())
    elif len(sys.argv) > 1 and sys.argv[1] == "server":
        # Start MCP server
        asyncio.run(start_mcp_server())
    else:
        print("Multi-Agent MCP Tool")
        print("===================")
        print("Usage:")
        print("  python multi_agent_mcp_tool.py demo   - Run interactive demo")
        print("  python multi_agent_mcp_tool.py server - Start MCP server")
        print("\nThis demonstrates building MCP tools that internally use multiple")
        print("collaborating AI agents while presenting a single tool interface.")