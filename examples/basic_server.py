"""
Basic MCP server example demonstrating core functionality.
"""
import asyncio
import logging
from grpc_mcp_sdk import mcp_tool, streaming_tool, MCPToolResult, run_server

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@mcp_tool(description="Calculate the square of a number")
def square_number(x: float) -> MCPToolResult:
    """Calculate x squared"""
    result = x * x
    return MCPToolResult().add_text(f"{x}² = {result}")


@mcp_tool(description="Add two numbers together")
def add_numbers(a: float, b: float) -> MCPToolResult:
    """Add two numbers"""
    result = a + b
    return MCPToolResult().add_json({
        "operation": "addition",
        "operands": [a, b],
        "result": result
    })


@mcp_tool(description="Get information about a person")
def get_person_info(name: str, age: int = 25) -> MCPToolResult:
    """Get formatted person information"""
    result = MCPToolResult()
    result.add_text(f"Person: {name}")
    result.add_json({
        "name": name,
        "age": age,
        "category": "adult" if age >= 18 else "minor"
    })
    result.set_metadata("processed_by", "basic_server")
    return result


@streaming_tool(description="Count from 1 to N with progress updates")
async def count_to_n(n: int = 10):
    """Count from 1 to N with streaming updates"""
    for i in range(1, n + 1):
        # Yield progress update
        yield {"progress": i / n, "message": f"Counting: {i}/{n}"}
        
        # Yield actual result
        result = MCPToolResult()
        result.add_text(f"Count: {i}")
        result.add_json({"current": i, "total": n, "percentage": (i/n)*100})
        yield result
        
        # Small delay to simulate work
        await asyncio.sleep(0.1)
    
    # Final result
    final_result = MCPToolResult()
    final_result.add_text(f"Finished counting to {n}")
    final_result.set_metadata("final_count", str(n))
    yield final_result


@streaming_tool(description="Process a list of items with updates")
async def process_items(items: list):
    """Process a list of items with streaming updates"""
    total = len(items)
    
    for i, item in enumerate(items):
        # Progress update
        yield {"progress": i / total, "message": f"Processing item {i+1}/{total}"}
        
        # Process the item
        result = MCPToolResult()
        result.add_text(f"Processed: {item}")
        result.add_json({
            "item": item,
            "index": i,
            "processed_at": f"step_{i+1}"
        })
        yield result
        
        await asyncio.sleep(0.2)
    
    # Final summary
    summary = MCPToolResult()
    summary.add_text(f"Processing complete! Processed {total} items.")
    summary.add_json({
        "total_items": total,
        "status": "completed",
        "items_processed": items
    })
    yield summary


if __name__ == "__main__":
    logger.info("Starting basic gRPC MCP server...")
    logger.info("Available tools:")
    logger.info("  - square_number: Calculate square of a number")
    logger.info("  - add_numbers: Add two numbers")
    logger.info("  - get_person_info: Get person information")
    logger.info("  - count_to_n: Streaming counter (streaming)")
    logger.info("  - process_items: Process list items (streaming)")
    
    asyncio.run(run_server(
        host="0.0.0.0",
        port=50051,
        server_name="Basic-MCP-Server",
        version="1.0.0"
    ))