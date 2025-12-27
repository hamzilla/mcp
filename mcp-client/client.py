"""
Basic MCP client that connects to multiple MCP servers using Ollama.
"""

import asyncio
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, ToolMessage
from loguru import logger


class MCPClient:
    """MCP Client that connects to multiple servers and uses Ollama for LLM interactions."""

    def __init__(
        self,
        server_configs: list[dict[str, str]],
        model_name: str = "llama3.2",
        ollama_base_url: str = "http://localhost:11434"
    ):
        """
        Initialize the MCP client.

        Args:
            server_configs: List of server configurations, each with 'name', 'path', and optional 'command'
                Example: [
                    {"name": "weather", "path": "/path/to/weather.py"},
                    {"name": "bitbucket", "path": "/path/to/bitbucket/main.py", "command": "python"}
                ]
            model_name: Ollama model name to use
            ollama_base_url: Base URL for Ollama API
        """
        self.server_configs = server_configs
        self.model_name = model_name
        self.ollama_base_url = ollama_base_url

        self.sessions: dict[str, ClientSession] = {}
        self.exit_stack = AsyncExitStack()
        self.llm = None
        self.tools = []
        self.tool_to_server_map = {}  # Maps tool names to server names

    async def connect_to_servers(self):
        """Connect to all configured MCP servers."""
        import os

        logger.info(f"Connecting to {len(self.server_configs)} MCP server(s)")

        for server_config in self.server_configs:
            server_name = server_config["name"]
            server_path = server_config["path"]
            command = server_config.get("command", "python")
            extra_args = server_config.get("args", [])

            logger.info(f"Connecting to {server_name} server: {server_path}")

            # Configure server parameters for stdio connection
            # Build args: extra_args + [server_path]
            all_args = extra_args + [server_path]

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
            logger.info(f"Connected to {server_name} server successfully")

            # List available tools from this server
            response = await session.list_tools()
            server_tools = response.tools

            # Track which server each tool belongs to
            for tool in server_tools:
                self.tool_to_server_map[tool.name] = server_name
                self.tools.append(tool)

            logger.info(f"{server_name} tools: {[tool.name for tool in server_tools]}")

        logger.info(f"Total tools available: {len(self.tools)}")

    async def initialize_llm(self):
        """Initialize Ollama LLM with MCP tools."""
        logger.info(f"Initializing Ollama with model: {self.model_name}")

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
            model=self.model_name,
            base_url=self.ollama_base_url,
            temperature=0
        ).bind_tools(langchain_tools)

        logger.info("LLM initialized with tools")

    async def process_query(self, query: str) -> str:
        """
        Process a user query using the LLM and MCP tools.

        Args:
            query: User's question or request

        Returns:
            The final response from the LLM
        """
        logger.info(f"Processing query: {query}")

        messages = [HumanMessage(content=query)]

        # Run the agent loop
        max_iterations = 10
        for i in range(max_iterations):
            logger.debug(f"Iteration {i + 1}/{max_iterations}")

            # Check if we're at the last iteration before calling LLM
            if i == max_iterations - 1:
                logger.warning("Reached maximum iterations, stopping")
                return "Sorry, I couldn't complete the task within the iteration limit. The conversation was too complex or the model kept trying to call tools."

            try:
                # Get response from LLM with timeout
                response = await asyncio.wait_for(
                    self.llm.ainvoke(messages),
                    timeout=60.0  # 60 second timeout
                )
                messages.append(response)
            except asyncio.TimeoutError:
                logger.error("LLM call timed out")
                return "Sorry, the request timed out. Please try again with a simpler question."
            except Exception as e:
                logger.error(f"Error calling LLM: {e}")
                return f"Error communicating with the AI model: {str(e)}"

            # Check if LLM wants to call a tool
            if not response.tool_calls:
                # No more tool calls, return the final response
                logger.info("No more tool calls, returning response")
                return response.content

            # Process each tool call
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_call_id = tool_call["id"]

                logger.info(f"Calling tool: {tool_name} with args: {tool_args}")

                try:
                    # Find which server has this tool
                    server_name = self.tool_to_server_map.get(tool_name)
                    if not server_name:
                        raise ValueError(f"Tool {tool_name} not found in any connected server")

                    session = self.sessions[server_name]
                    logger.debug(f"Routing {tool_name} to {server_name} server")

                    # Call the MCP tool on the appropriate server
                    result = await session.call_tool(tool_name, arguments=tool_args)
                    tool_result = result.content[0].text if result.content else "No result"
                    logger.debug(f"Tool result: {tool_result}")

                except Exception as e:
                    logger.error(f"Error calling tool {tool_name}: {e}")
                    tool_result = f"Error: {str(e)}"

                # Add tool result to messages
                messages.append(
                    ToolMessage(
                        content=tool_result,
                        tool_call_id=tool_call_id
                    )
                )

        logger.warning("Reached maximum iterations (shouldn't get here)")
        return "Sorry, I couldn't complete the task within the iteration limit."

    async def chat_loop(self):
        """Run an interactive chat loop."""
        logger.info("Starting chat loop. Type 'quit' or 'exit' to stop.")
        print("\n🤖 Multi-Server MCP Client with Ollama")
        print("=" * 50)
        print(f"Connected servers: {', '.join(self.sessions.keys())}")
        print(f"Total tools available: {len(self.tools)}")
        print("Ask me anything!\n")

        while True:
            try:
                user_input = input("You: ").strip()

                if user_input.lower() in ["quit", "exit", "bye"]:
                    print("Goodbye!")
                    break

                if not user_input:
                    continue

                # Process the query
                response = await self.process_query(user_input)
                print(f"\nAssistant: {response}\n")

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                logger.error(f"Error in chat loop: {e}")
                print(f"\nError: {str(e)}\n")

    async def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up...")
        await self.exit_stack.aclose()

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
    # Configure multiple MCP servers
    servers = [
        {
            "name": "weather",
            "path": "/Users/hamzilla/mcp/weather/weather.py",
            "command": "uv",
            "args": ["run"]
        },
        {
            "name": "bitbucket",
            "path": "/Users/hamzilla/mcp/bitbucket-mcp/main.py",
            "command": "uv",
            "args": ["run"]
        }
    ]

    # You can also use different commands like "uvx" or "npx" for different server types
    # For example: {"name": "npm-server", "path": "mcp-server-weather", "command": "npx"}

    client = MCPClient(
        server_configs=servers,
        model_name="deepseek-r1:70b",  # or any other Ollama model you have
        ollama_base_url="http://localhost:11434"
    )

    await client.run()


if __name__ == "__main__":
    asyncio.run(main())
