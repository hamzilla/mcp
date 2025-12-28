"""
MCP Tool Wrapper for LangGraph.

Bridges MCP server tools to LangGraph's tool format.
"""

from typing import Any, Callable, Type, Optional
from langchain_core.tools import StructuredTool
from mcp import ClientSession
from loguru import logger
from pydantic import BaseModel, create_model, Field


def json_schema_to_pydantic(schema: dict, model_name: str) -> Type[BaseModel]:
    """
    Convert JSON Schema to Pydantic model for LangChain tool.

    Args:
        schema: JSON schema from MCP tool
        model_name: Name for the Pydantic model

    Returns:
        Pydantic BaseModel class
    """
    if not schema or "properties" not in schema:
        # If no schema, create an empty model
        return create_model(model_name)

    # Build field definitions from JSON schema
    field_definitions = {}
    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))

    for field_name, field_info in properties.items():
        field_type = field_info.get("type", "string")
        field_description = field_info.get("description", "")

        # Map JSON types to Python types
        type_mapping = {
            "string": str,
            "number": float,
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        python_type = type_mapping.get(field_type, str)

        # Make field optional if not required
        if field_name not in required_fields:
            python_type = Optional[python_type]
            default_value = None
        else:
            default_value = ...

        # Create field with description
        field_definitions[field_name] = (
            python_type,
            Field(default=default_value, description=field_description)
        )

    # Create and return the model
    return create_model(model_name, **field_definitions)


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
        import time
        start_time = time.time()

        tool_log = logger.bind(
            tool_name=tool_name,
            server=server_name,
        )
        tool_log.debug(f"Executing MCP tool", args=kwargs)

        try:
            # Filter out None values for optional parameters
            # MCP servers validate against JSON schema which doesn't accept None for optional string fields
            filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}

            result = await session.call_tool(tool_name, arguments=filtered_kwargs)
            tool_result = result.content[0].text if result.content else "No result"

            duration_ms = int((time.time() - start_time) * 1000)
            tool_log.info(f"MCP tool call to {tool_name} completed successfully in {duration_ms}ms")
            return tool_result
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            tool_log.error(f"Error calling MCP tool after {duration_ms}ms: {e}", exc_info=True)
            return f"Error: {str(e)}"

    # Convert MCP JSON schema to Pydantic model
    args_schema = json_schema_to_pydantic(
        tool_schema,
        model_name=f"{tool_name.replace('-', '_').replace(':', '_')}_schema"
    )

    # Create LangGraph StructuredTool
    return StructuredTool(
        name=tool_name,
        description=tool_description or f"Call {tool_name} on {server_name} server",
        func=tool_func,
        coroutine=tool_func,  # Use async version
        args_schema=args_schema,  # Provide schema so LLM knows what parameters to use
    )
