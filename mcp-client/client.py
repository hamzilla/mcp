"""
Production-ready MCP client that connects to multiple MCP servers using Ollama.

Features:
- Configurable via environment variables
- Structured logging with correlation IDs
- Proper iteration limit handling with partial results
- Robust error handling
"""

import asyncio
import uuid
import os
from contextlib import AsyncExitStack
from typing import Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, ToolMessage
from loguru import logger

from config import MCPClientConfig, ServerConfig
from logging_config import setup_logging


class MCPClient:
    """MCP Client that connects to multiple servers and uses Ollama for LLM interactions."""

    def __init__(self, config: Optional[MCPClientConfig] = None):
        """
        Initialize the MCP client with configuration.

        Args:
            config: MCPClientConfig instance. If None, loads from environment/.env file.
        """
        # Load configuration
        if config is None:
            config = MCPClientConfig()
        self.config = config

        # Setup logging based on configuration
        setup_logging(log_level=self.config.log_level, structured=False)

        # Client state
        self.sessions: dict[str, ClientSession] = {}
        self.exit_stack = AsyncExitStack()
        self.llm = None
        self.tools = []
        self.tool_to_server_map = {}  # Maps tool names to server names

        logger.info(
            "MCPClient initialized",
            model=self.config.llm.model_name,
            max_iterations=self.config.llm.max_iterations,
            server_count=len(self.config.servers),
        )

    async def connect_to_servers(self):
        """Connect to all configured MCP servers."""
        logger.info(f"Connecting to {len(self.config.servers)} MCP server(s)")

        for server_config in self.config.servers:
            server_name = server_config.name
            server_path = server_config.path
            command = server_config.command
            args = server_config.args

            correlation_id = str(uuid.uuid4())
            log = logger.bind(
                correlation_id=correlation_id,
                server_name=server_name,
                server_path=server_path,
            )

            log.info(f"Connecting to {server_name} server")

            try:
                # Build command args
                all_args = args + [server_path]

                # Determine working directory (directory containing the script)
                # This ensures .env files are loaded correctly
                working_dir = os.path.dirname(os.path.abspath(server_path))

                server_params = StdioServerParameters(
                    command=command,
                    args=all_args,
                    env=None,
                    cwd=working_dir
                )

                # Connect to server
                stdio_transport = await self.exit_stack.enter_async_context(
                    stdio_client(server_params)
                )
                stdio, write = stdio_transport
                session = await self.exit_stack.enter_async_context(
                    ClientSession(stdio, write)
                )

                # Initialize the session
                await session.initialize()
                self.sessions[server_name] = session
                log.info(f"Connected to {server_name} server successfully")

                # List available tools from this server
                response = await session.list_tools()
                server_tools = response.tools

                # Track which server each tool belongs to
                for tool in server_tools:
                    self.tool_to_server_map[tool.name] = server_name
                    self.tools.append(tool)

                log.info(
                    f"Loaded tools from {server_name}",
                    tool_count=len(server_tools),
                    tools=[tool.name for tool in server_tools],
                )

            except Exception as e:
                log.error(f"Failed to connect to {server_name} server: {e}", exc_info=True)
                raise

        logger.info(
            "All servers connected",
            total_tools=len(self.tools),
            servers=list(self.sessions.keys()),
        )

    async def initialize_llm(self):
        """Initialize Ollama LLM with MCP tools."""
        correlation_id = str(uuid.uuid4())
        log = logger.bind(
            correlation_id=correlation_id,
            model=self.config.llm.model_name,
        )

        log.info(f"Initializing Ollama LLM with model {self.config.llm.model_name}")

        # Convert MCP tools to LangChain format
        langchain_tools = []
        for tool in self.tools:
            langchain_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema
                }
            })

        # Initialize ChatOllama with tools
        self.llm = ChatOllama(
            model=self.config.llm.model_name,
            base_url=self.config.ollama_base_url,
            temperature=self.config.llm.temperature
        ).bind_tools(langchain_tools)

        log.info(
            "LLM initialized with tools",
            tool_count=len(langchain_tools),
            temperature=self.config.llm.temperature,
        )

    async def process_query(self, query: str, correlation_id: Optional[str] = None) -> dict:
        """
        Process a user query using the LLM and MCP tools.

        Args:
            query: User's question or request
            correlation_id: Optional correlation ID for tracking. Auto-generated if not provided.

        Returns:
            Dictionary with:
                - content: The final response from the LLM
                - iterations: Number of iterations used
                - status: 'success' or 'max_iterations_reached'
                - partial: True if hit max iterations
        """
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        log = logger.bind(correlation_id=correlation_id)
        log.info("Processing query", query=query)

        messages = [HumanMessage(content=query)]

        # Run the agent loop
        max_iterations = self.config.llm.max_iterations
        for i in range(max_iterations):
            log.debug(f"Agent loop iteration {i + 1}/{max_iterations}")

            try:
                # Get response from LLM with timeout
                timeout = self.config.llm.timeout_seconds
                response = await asyncio.wait_for(
                    self.llm.ainvoke(messages),
                    timeout=float(timeout)
                )
                messages.append(response)

                log.debug("LLM response received", has_tool_calls=bool(response.tool_calls))

            except asyncio.TimeoutError:
                log.error(f"LLM call timed out after {timeout}s")
                return {
                    "content": f"Sorry, the request timed out after {timeout} seconds. Please try again with a simpler question.",
                    "iterations": i + 1,
                    "status": "timeout",
                    "partial": True,
                }
            except Exception as e:
                log.error(f"Error calling LLM: {e}", exc_info=True)
                return {
                    "content": f"Error communicating with the AI model: {str(e)}",
                    "iterations": i + 1,
                    "status": "error",
                    "partial": True,
                }

            # Check if LLM wants to call a tool
            if not response.tool_calls:
                # No more tool calls, return the final response
                log.info("Query completed successfully", iterations=i + 1)
                return {
                    "content": response.content,
                    "iterations": i + 1,
                    "status": "success",
                    "partial": False,
                }

            # Process each tool call
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_call_id = tool_call["id"]

                tool_log = log.bind(
                    tool_name=tool_name,
                    tool_call_id=tool_call_id,
                )
                tool_log.info(f"Calling tool {tool_name}", args=tool_args)

                try:
                    # Find which server has this tool
                    server_name = self.tool_to_server_map.get(tool_name)
                    if not server_name:
                        raise ValueError(f"Tool {tool_name} not found in any connected server")

                    session = self.sessions[server_name]
                    tool_log.debug(f"Routing tool to server", server=server_name)

                    # Call the MCP tool on the appropriate server
                    result = await session.call_tool(tool_name, arguments=tool_args)
                    tool_result = result.content[0].text if result.content else "No result"
                    tool_log.info("Tool call completed successfully")

                except Exception as e:
                    tool_log.error(f"Error calling tool: {e}", exc_info=True)
                    tool_result = f"Error: {str(e)}"

                # Add tool result to messages
                messages.append(
                    ToolMessage(
                        content=tool_result,
                        tool_call_id=tool_call_id
                    )
                )

        # If we exit the loop, we hit max iterations
        log.warning(
            f"Reached max iterations ({max_iterations}), returning partial result",
            iterations=max_iterations,
        )

        # Return partial result with the last response
        final_content = response.content if response and response.content else \
                       "I couldn't complete the task within the iteration limit. The conversation required too many tool calls."

        return {
            "content": final_content,
            "iterations": max_iterations,
            "status": "max_iterations_reached",
            "partial": True,
        }

    async def chat_loop(self):
        """Run an interactive chat loop."""
        session_id = str(uuid.uuid4())
        log = logger.bind(session_id=session_id)

        log.info("Starting chat loop")
        print("\n🤖 Multi-Server MCP Client with Ollama")
        print("=" * 50)
        print(f"Connected servers: {', '.join(self.sessions.keys())}")
        print(f"Total tools available: {len(self.tools)}")
        print(f"Model: {self.config.llm.model_name}")
        print(f"Max iterations: {self.config.llm.max_iterations}")
        print("Ask me anything!\n")

        query_count = 0

        while True:
            try:
                user_input = input("You: ").strip()

                if user_input.lower() in ["quit", "exit", "bye"]:
                    print("Goodbye!")
                    break

                if not user_input:
                    continue

                query_count += 1
                correlation_id = f"{session_id}-q{query_count}"

                # Process the query
                result = await self.process_query(user_input, correlation_id=correlation_id)

                # Display result
                print(f"\nAssistant: {result['content']}\n")

                # Show metadata if partial result
                if result.get("partial"):
                    print(f"(⚠️  Partial result after {result['iterations']} iterations - {result['status']})\n")

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                log.error(f"Error in chat loop: {e}", exc_info=True)
                print(f"\nError: {str(e)}\n")

    async def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up resources")
        await self.exit_stack.aclose()
        logger.info("Cleanup complete")

    async def run(self):
        """Main entry point to run the client."""
        try:
            await self.connect_to_servers()
            await self.initialize_llm()
            await self.chat_loop()
        finally:
            await self.cleanup()


async def main():
    """Main function to run the MCP client."""
    # Example of configuring servers programmatically
    # Note: In production, you might want to load these from a config file
    from config import ServerConfig

    servers = [
        ServerConfig(
            name="weather",
            path="/Users/hamzilla/mcp/weather/weather.py",
            command="uv",
            args=["run"]
        ),
        ServerConfig(
            name="bitbucket",
            path="/Users/hamzilla/mcp/bitbucket-mcp/main.py",
            command="uv",
            args=["run"]
        )
    ]

    # Create configuration
    config = MCPClientConfig(servers=servers)

    # Create and run client
    client = MCPClient(config=config)
    await client.run()


if __name__ == "__main__":
    asyncio.run(main())
