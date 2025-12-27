"""
MCP Tool Wrapper for LangGraph.

Bridges MCP server tools to LangGraph's tool format.
"""

from typing import Any, Callable
from langchain_core.tools import StructuredTool
from mcp import ClientSession
from loguru import logger


def create_mcp_tool(
    tool_name: str,
    tool_description: str,
    tool_schema: dict,
    session: ClientSession,
    server_name: str
) -> StructuredTool:
    """
    Create a LangGraph-compatible tool from an MCP tool.

    Args:
        tool_name: Name of the MCP tool
        tool_description: Description of what the tool does
        tool_schema: JSON schema for tool input
        session: MCP client session for the server that has this tool
        server_name: Name of the MCP server

    Returns:
        StructuredTool compatible with LangGraph
    """

    async def tool_func(**kwargs) -> str:
        """Execute the MCP tool and return result."""
        tool_log = logger.bind(
            tool_name=tool_name,
            server=server_name,
        )
        tool_log.debug(f"Executing MCP tool", args=kwargs)

        try:
            result = await session.call_tool(tool_name, arguments=kwargs)
            tool_result = result.content[0].text if result.content else "No result"
            tool_log.info("MCP tool call completed successfully")
            return tool_result
        except Exception as e:
            tool_log.error(f"Error calling MCP tool: {e}", exc_info=True)
            return f"Error: {str(e)}"

    # Create LangGraph StructuredTool
    return StructuredTool(
        name=tool_name,
        description=tool_description or f"Call {tool_name} on {server_name} server",
        func=tool_func,
        coroutine=tool_func,  # Use async version
        args_schema=None,  # We'll use the schema from MCP
    )
