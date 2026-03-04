"""
A2A Multi-Agent Example - Demonstrates agent-to-agent communication and workflow orchestration

This example shows how to:
1. Create agents with different capabilities
2. Register agents in the A2A registry
3. Enable agent discovery and communication
4. Orchestrate multi-agent workflows
5. Use both MCP tools and A2A capabilities together
"""

import asyncio
import logging
import time
import sys
import os
from typing import Dict, Any

# Add the parent directory to sys.path to import the local grpc_mcp_sdk
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grpc_mcp_sdk import (
    # Core MCP functionality
    mcp_tool, streaming_tool, MCPToolResult, run_server, is_a2a_available
)

# Import A2A functionality if available
if is_a2a_available():
    from grpc_mcp_sdk import (
        agent_capability, register_local_agent,
        AgentCapabilityType, A2AAgentClient, A2AWorkflowOrchestrator,
        WorkflowStep, create_agent_client, create_workflow_orchestrator
    )

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# Data Analysis Agent
# =============================================================================

@agent_capability(
    name="analyze_dataset",
    description="Analyze a dataset and extract insights",
    capability_type=AgentCapabilityType.DATA_PROCESSOR,
    requirements=["read_access"],
    version="1.0.0"
)
@mcp_tool(description="Analyze dataset and generate statistical insights")
async def analyze_dataset(data: Dict[str, Any], analysis_type: str = "basic") -> MCPToolResult:
    """Analyze a dataset and provide insights"""
    logger.info(f"Analyzing dataset with {len(data.get('records', []))} records")
    
    # Simulate analysis processing
    await asyncio.sleep(0.5)
    
    records = data.get('records', [])
    if not records:
        return MCPToolResult().set_error("No data records provided")
    
    # Perform basic analysis
    total_records = len(records)
    
    # Calculate basic statistics if numeric data is present
    numeric_fields = []
    for record in records[:5]:  # Sample first 5 records
        for key, value in record.items():
            if isinstance(value, (int, float)) and key not in numeric_fields:
                numeric_fields.append(key)
    
    analysis_results = {
        "total_records": total_records,
        "analysis_type": analysis_type,
        "numeric_fields": numeric_fields,
        "sample_record": records[0] if records else None,
        "analysis_timestamp": time.time()
    }
    
    if analysis_type == "detailed" and numeric_fields:
        # Detailed analysis for numeric fields
        for field in numeric_fields[:3]:  # Limit to first 3 numeric fields
            values = [record.get(field, 0) for record in records if isinstance(record.get(field), (int, float))]
            if values:
                analysis_results[f"{field}_stats"] = {
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                    "count": len(values)
                }
    
    result = MCPToolResult()
    result.add_text(f"Dataset analysis complete - {total_records} records processed")
    result.add_json(analysis_results)
    result.metadata["processing_time"] = "500ms"
    result.metadata["analysis_engine"] = "BasicAnalyzer_v1.0"
    
    return result

# =============================================================================
# Report Generation Agent
# =============================================================================

@agent_capability(
    name="generate_report",
    description="Generate reports from analysis data",
    capability_type=AgentCapabilityType.DATA_PROCESSOR,
    requirements=["write_access"],
    dependencies=["analyze_dataset"],
    version="1.0.0"
)
@mcp_tool(description="Generate formatted reports from analysis results")
async def generate_report(analysis_data: Dict[str, Any], format_type: str = "markdown") -> MCPToolResult:
    """Generate a formatted report from analysis data"""
    logger.info(f"Generating {format_type} report from analysis data")
    
    # Simulate report generation
    await asyncio.sleep(0.3)
    
    if format_type == "markdown":
        report = f"""# Dataset Analysis Report

## Summary
- **Total Records**: {analysis_data.get('total_records', 'N/A')}
- **Analysis Type**: {analysis_data.get('analysis_type', 'N/A')}
- **Generated**: {time.strftime('%Y-%m-%d %H:%M:%S')}

## Findings
"""
        
        numeric_fields = analysis_data.get('numeric_fields', [])
        if numeric_fields:
            report += f"\n### Numeric Fields Detected\n"
            for field in numeric_fields:
                report += f"- {field}\n"
                
                # Add detailed stats if available
                stats_key = f"{field}_stats"
                if stats_key in analysis_data:
                    stats = analysis_data[stats_key]
                    report += f"  - Min: {stats.get('min')}, Max: {stats.get('max')}, Avg: {stats.get('avg', 0):.2f}\n"
        
        if analysis_data.get('sample_record'):
            report += f"\n### Sample Record\n```json\n{analysis_data['sample_record']}\n```\n"
        
        report += f"\n---\n*Report generated by ReportGenerator v1.0*"
        
        result = MCPToolResult()
        result.add_text("Report generated successfully")
        result.add_text(report)
        result.metadata["report_format"] = format_type
        result.metadata["report_length"] = str(len(report))
        
    elif format_type == "json":
        report_data = {
            "title": "Dataset Analysis Report",
            "timestamp": time.time(),
            "summary": analysis_data,
            "metadata": {
                "generator": "ReportGenerator v1.0",
                "format": "json"
            }
        }
        
        result = MCPToolResult()
        result.add_text("JSON report generated successfully")
        result.add_json(report_data)
        result.metadata["report_format"] = format_type
        
    else:
        return MCPToolResult().set_error(f"Unsupported format: {format_type}")
    
    return result

# =============================================================================
# Data Validation Agent
# =============================================================================

@agent_capability(
    name="validate_data",
    description="Validate data quality and integrity",
    capability_type=AgentCapabilityType.DATA_PROCESSOR,
    requirements=["read_access"],
    version="1.0.0"
)
@mcp_tool(description="Validate data quality and detect issues")
async def validate_data(data: Dict[str, Any], validation_rules: Dict[str, Any] = None) -> MCPToolResult:
    """Validate data quality and integrity"""
    logger.info("Validating data quality")
    
    # Simulate validation processing
    await asyncio.sleep(0.2)
    
    records = data.get('records', [])
    validation_results = {
        "total_records": len(records),
        "valid_records": 0,
        "issues": [],
        "validation_timestamp": time.time()
    }
    
    rules = validation_rules or {}
    required_fields = rules.get('required_fields', [])
    numeric_fields = rules.get('numeric_fields', [])
    
    for i, record in enumerate(records):
        record_issues = []
        
        # Check required fields
        for field in required_fields:
            if field not in record or record[field] is None:
                record_issues.append(f"Missing required field: {field}")
        
        # Check numeric fields
        for field in numeric_fields:
            if field in record and not isinstance(record[field], (int, float)):
                record_issues.append(f"Field '{field}' should be numeric")
        
        if not record_issues:
            validation_results["valid_records"] += 1
        else:
            validation_results["issues"].append({
                "record_index": i,
                "issues": record_issues
            })
    
    validation_results["validation_success_rate"] = (
        validation_results["valid_records"] / len(records) if records else 0
    )
    
    result = MCPToolResult()
    
    if validation_results["validation_success_rate"] >= 0.8:
        result.add_text(f"Data validation passed - {validation_results['validation_success_rate']:.1%} success rate")
    else:
        result.add_text(f"Data validation concerns - {validation_results['validation_success_rate']:.1%} success rate")
    
    result.add_json(validation_results)
    result.metadata["validator_version"] = "DataValidator_v1.0"
    
    return result

# =============================================================================
# Workflow Orchestration Examples
# =============================================================================

async def run_data_processing_workflow():
    """Example of a multi-agent workflow for data processing"""
    if not is_a2a_available():
        logger.warning("A2A functionality not available - skipping workflow example")
        return
    
    logger.info("=== Running Data Processing Workflow ===")
    
    # Sample dataset
    sample_data = {
        "records": [
            {"id": 1, "name": "Alice", "age": 30, "salary": 50000},
            {"id": 2, "name": "Bob", "age": 25, "salary": 45000},
            {"id": 3, "name": "Charlie", "age": 35, "salary": 60000},
            {"id": 4, "name": "Diana", "age": 28, "salary": 52000},
            {"id": 5, "name": "Eve", "age": 32, "salary": 58000},
        ]
    }
    
    validation_rules = {
        "required_fields": ["id", "name", "age"],
        "numeric_fields": ["id", "age", "salary"]
    }
    
    # Create workflow orchestrator
    orchestrator = create_workflow_orchestrator()
    
    # Define workflow steps
    workflow_steps = [
        WorkflowStep(
            step_id="validate",
            capability_name="validate_data",
            arguments={
                "data": sample_data,
                "validation_rules": validation_rules
            },
            timeout=10.0
        ),
        WorkflowStep(
            step_id="analyze_basic",
            capability_name="analyze_dataset",
            arguments={
                "data": sample_data,
                "analysis_type": "basic"
            },
            depends_on=["validate"],
            timeout=15.0
        ),
        WorkflowStep(
            step_id="analyze_detailed",
            capability_name="analyze_dataset",
            arguments={
                "data": sample_data,
                "analysis_type": "detailed"
            },
            depends_on=["validate"],
            timeout=15.0
        ),
        WorkflowStep(
            step_id="generate_markdown_report",
            capability_name="generate_report",
            arguments={
                "analysis_data": {},  # Will be populated from analyze_detailed result
                "format_type": "markdown"
            },
            depends_on=["analyze_detailed"],
            timeout=10.0
        ),
        WorkflowStep(
            step_id="generate_json_report",
            capability_name="generate_report",
            arguments={
                "analysis_data": {},  # Will be populated from analyze_basic result
                "format_type": "json"
            },
            depends_on=["analyze_basic"],
            timeout=10.0
        )
    ]
    
    # Execute workflow
    workflow_id = "data_processing_demo"
    
    try:
        logger.info(f"Starting workflow: {workflow_id}")
        result = await orchestrator.execute_workflow(
            workflow_id=workflow_id,
            steps=workflow_steps,
            parallel_execution=True
        )
        
        if result.success:
            logger.info(f"Workflow completed successfully in {result.total_time:.2f}s")
            logger.info(f"Executed {len(result.steps)} steps")
            
            # Display results
            for step_id, step_result in result.steps.items():
                logger.info(f"Step '{step_id}' result:")
                for content in step_result.content:
                    if content["type"] == "text":
                        logger.info(f"  - {content['text']}")
        else:
            logger.error(f"Workflow failed: {result.error}")
            
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")

async def demonstrate_agent_discovery():
    """Demonstrate agent discovery and communication"""
    if not is_a2a_available():
        logger.warning("A2A functionality not available - skipping discovery example")
        return
        
    logger.info("=== Demonstrating Agent Discovery ===")
    
    # Create agent client
    client = create_agent_client()
    
    # Discover agents by capability
    data_processors = await client.discover_agents("analyze_dataset")
    logger.info(f"Found {len(data_processors)} agents with 'analyze_dataset' capability")
    
    validators = await client.discover_agents("validate_data")
    logger.info(f"Found {len(validators)} agents with 'validate_data' capability")
    
    # Find best agent for a task
    best_analyzer = await client.find_best_agent("analyze_dataset")
    if best_analyzer:
        logger.info(f"Best agent for analysis: {best_analyzer.name} ({best_analyzer.agent_id})")
    
    # Execute capability on best agent
    if best_analyzer:
        sample_data = {
            "records": [
                {"id": 1, "value": 100},
                {"id": 2, "value": 200}
            ]
        }
        
        try:
            result = await client.execute_capability(
                agent_id=best_analyzer.agent_id,
                capability_name="analyze_dataset",
                arguments={"data": sample_data, "analysis_type": "basic"}
            )
            
            logger.info("Direct capability execution result:")
            for content in result.content:
                if content["type"] == "text":
                    logger.info(f"  - {content['text']}")
                    
        except Exception as e:
            logger.error(f"Capability execution failed: {e}")

# =============================================================================
# Server Setup and Demo
# =============================================================================

async def main():
    """Main demo function"""
    logger.info("🚀 Starting A2A Multi-Agent Demo")
    logger.info("=" * 50)
    
    # Check A2A availability
    if is_a2a_available():
        logger.info("✅ A2A extensions available")
        
        # Register this process as an agent
        agent_id = register_local_agent(
            name="MultiAgent Data Processor",
            description="Demonstrates multi-agent data processing capabilities",
            version="1.0.0",
            tags={"demo", "data_processing", "a2a"}
        )
        logger.info(f"📝 Registered local agent with ID: {agent_id}")
        
        # Run discovery demo
        await demonstrate_agent_discovery()
        
        # Run workflow demo
        await run_data_processing_workflow()
        
    else:
        logger.warning("⚠️  A2A extensions not available - running basic MCP demo")
    
    # Test individual MCP tools
    logger.info("\n=== Testing Individual MCP Tools ===")
    
    # Test data validation
    test_data = {
        "records": [
            {"id": 1, "name": "Test", "age": 25},
            {"id": 2, "name": "User", "salary": 50000}  # Missing age
        ]
    }
    
    validation_result = await validate_data(test_data, {
        "required_fields": ["id", "name", "age"],
        "numeric_fields": ["id", "age", "salary"]
    })
    
    logger.info("Validation result:")
    for content in validation_result.content:
        if content["type"] == "text":
            logger.info(f"  - {content['text']}")
    
    # Test data analysis
    analysis_result = await analyze_dataset(test_data, "detailed")
    logger.info("Analysis result:")
    for content in analysis_result.content:
        if content["type"] == "text":
            logger.info(f"  - {content['text']}")
    
    logger.info("\n🎯 Demo completed successfully!")
    logger.info("To start the gRPC server, run: python -m grpc_mcp_sdk.examples.a2a_multi_agent_example")

if __name__ == "__main__":
    # Option 1: Run demo
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        asyncio.run(main())
    else:
        # Option 2: Start gRPC server
        logger.info("Starting gRPC MCP Server with A2A capabilities...")
        logger.info("Available tools:")
        logger.info("  🔍 validate_data - Validate data quality")
        logger.info("  📊 analyze_dataset - Analyze datasets") 
        logger.info("  📄 generate_report - Generate reports")
        
        if is_a2a_available():
            logger.info("  🤝 A2A agent capabilities enabled")
            
            # Register as agent
            register_local_agent(
                name="A2A Data Processing Server",
                description="Server providing data processing capabilities via MCP and A2A",
                version="1.0.0"
            )
        
        # Start the server
        asyncio.run(run_server(host="0.0.0.0", port=50051))