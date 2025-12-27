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
from langchain_core.messages import HumanMessage
from langchain.agents import create_agent
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from loguru import logger

from config import MCPClientConfig, ServerConfig
from logging_config import setup_logging
from storage import build_connection_string
from mcp_tool_wrapper import create_mcp_tool


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
        self.langchain_tools = []  # LangChain StructuredTool objects
        self.agent = None  # LangGraph agent
        self.checkpointer = None  # PostgreSQL checkpointer for conversation state
        self._checkpointer_cm = None  # Context manager for checkpointer cleanup

        # Database connection string (optional)
        self.connection_string: Optional[str] = None

        logger.info(
            "MCPClient initialized",
            model=self.config.llm.model_name,
            max_iterations=self.config.llm.max_iterations,
            server_count=len(self.config.servers),
            database_enabled=self.config.database is not None,
        )

    async def initialize_database(self):
        """Initialize database connection string and checkpointer if configured."""
        if not self.config.database:
            logger.info("\033[31mDatabase not configured, skipping initialization\033[0m")
            return

        correlation_id = str(uuid.uuid4())
        log = logger.bind(correlation_id=correlation_id)

        log.info(
            "Building database connection string",
            host=self.config.database.host,
            database=self.config.database.database,
        )

        # Build PostgreSQL connection string for LangChain
        self.connection_string = build_connection_string(
            host=self.config.database.host,
            port=self.config.database.port,
            database=self.config.database.database,
            user=self.config.database.user,
            password=self.config.database.password,
        )

        # Initialize LangGraph PostgreSQL checkpointer for conversation state persistence
        try:
            log.info("Attempting to connect to PostgreSQL...")
            # AsyncPostgresSaver.from_conn_string() returns an async context manager
            # We need to enter it to get the actual saver
            checkpointer_cm = AsyncPostgresSaver.from_conn_string(
                self.connection_string
            )
            self.checkpointer = await checkpointer_cm.__aenter__()
            # Store the context manager so we can clean it up later
            self._checkpointer_cm = checkpointer_cm

            await self.checkpointer.setup()
            log.info("✅ LangGraph PostgreSQL checkpointer initialized successfully")
            log.info("✅ Conversations will persist across restarts")
        except Exception as e:
            log.error(f"❌ Failed to initialize PostgreSQL checkpointer: {e}")
            log.error(f"   Connection string: postgresql://{self.config.database.user}:***@{self.config.database.host}:{self.config.database.port}/{self.config.database.database}")
            log.warning("⚠️  Continuing without conversation persistence")
            log.warning("   To enable persistence:")
            log.warning("   1. Start PostgreSQL: docker-compose up -d")
            log.warning("   2. Or install locally: brew install postgresql@16")
            log.warning("   3. See SETUP_POSTGRES.md for details")
            self.checkpointer = None
            self._checkpointer_cm = None

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

                # List available tools from this server and convert to LangChain tools
                response = await session.list_tools()
                server_tools = response.tools

                # Create LangChain StructuredTool for each MCP tool
                for tool in server_tools:
                    langchain_tool = create_mcp_tool(
                        tool_name=tool.name,
                        tool_description=tool.description,
                        tool_schema=tool.inputSchema,
                        session=session,
                        server_name=server_name
                    )
                    self.langchain_tools.append(langchain_tool)

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
            total_tools=len(self.langchain_tools),
            servers=list(self.sessions.keys()),
        )

    async def initialize_llm(self):
        """Initialize Ollama LLM and create LangGraph agent."""
        correlation_id = str(uuid.uuid4())
        log = logger.bind(
            correlation_id=correlation_id,
            model=self.config.llm.model_name,
        )

        log.info(f"Initializing Ollama LLM with model {self.config.llm.model_name}")

        # Initialize ChatOllama
        self.llm = ChatOllama(
            model=self.config.llm.model_name,
            base_url=self.config.ollama_base_url,
            temperature=self.config.llm.temperature
        )

        # Create LangGraph agent with tools and checkpointer
        self.agent = create_agent(
            self.llm,
            tools=self.langchain_tools,
            checkpointer=self.checkpointer,
            system_prompt=f"You are a helpful DevOps assistant with access to multiple tools. "
                         f"Use the available tools to help answer questions and perform tasks. "
                         f"You can call multiple tools if needed to complete a task."
        )

        log.info(
            "LangGraph agent initialized",
            tool_count=len(self.langchain_tools),
            temperature=self.config.llm.temperature,
            checkpointer_enabled=self.checkpointer is not None,
        )

    async def process_query(
        self,
        query: str,
        correlation_id: Optional[str] = None,
        session_id: Optional[str] = None,
        use_history: bool = True
    ) -> dict:
        """
        Process a user query using LangGraph agent.

        Args:
            query: User's question or request
            correlation_id: Optional correlation ID for tracking. Auto-generated if not provided.
            session_id: Optional session ID for conversation history. Auto-generated if not provided.
            use_history: Whether to use conversation history (requires checkpointer)

        Returns:
            Dictionary with:
                - content: The final response from the agent
                - status: 'success' or 'error'
                - session_id: Session ID (if checkpointer enabled)
        """
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        log = logger.bind(correlation_id=correlation_id)
        log.info("Processing query with LangGraph agent", query=query)

        # Generate session_id if not provided and checkpointer is enabled
        if use_history and self.checkpointer:
            if session_id is None:
                session_id = str(uuid.uuid4())
                log.info("Created new session", session_id=session_id)
            else:
                log.info("Using existing session", session_id=session_id)
        else:
            session_id = None
            log.debug("Running without conversation history")

        try:
            # Configure agent with recursion limit (equivalent to max_iterations)
            config = {
                "recursion_limit": self.config.llm.max_iterations,
            }

            # Add thread_id for checkpointer (conversation persistence)
            if session_id and self.checkpointer:
                config["configurable"] = {"thread_id": session_id}

            # Invoke the LangGraph agent
            log.debug("Invoking LangGraph agent", config=config)

            result = await asyncio.wait_for(
                self.agent.ainvoke(
                    {"messages": [HumanMessage(content=query)]},
                    config=config
                ),
                timeout=float(self.config.llm.timeout_seconds)
            )

            # Extract the final response
            messages = result.get("messages", [])
            if messages:
                final_message = messages[-1]
                content = final_message.content if hasattr(final_message, "content") else str(final_message)
            else:
                content = "No response generated"

            log.info("Query completed successfully via LangGraph agent")

            response = {
                "content": content,
                "status": "success",
            }
            if session_id:
                response["session_id"] = session_id

            return response

        except asyncio.TimeoutError:
            timeout = self.config.llm.timeout_seconds
            log.error(f"Agent execution timed out after {timeout}s")
            return {
                "content": f"Sorry, the request timed out after {timeout} seconds. Please try again with a simpler question.",
                "status": "timeout",
            }
        except Exception as e:
            log.error(f"Error executing agent: {e}", exc_info=True)
            return {
                "content": f"Error executing agent: {str(e)}",
                "status": "error",
            }

    async def chat_loop(self):
        """Run an interactive chat loop."""
        session_id = str(uuid.uuid4())
        log = logger.bind(session_id=session_id)

        log.info("Starting chat loop")
        print("\n🤖 Multi-Server MCP Client with Ollama + LangGraph")
        print("=" * 50)
        print(f"Connected servers: {', '.join(self.sessions.keys())}")
        print(f"Total tools available: {len(self.langchain_tools)}")
        print(f"Model: {self.config.llm.model_name}")
        print(f"Recursion limit: {self.config.llm.max_iterations}")
        if self.checkpointer:
            print(f"💾 Conversation persistence: Enabled (PostgreSQL)")
            print(f"   Thread ID: {session_id}")
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

                # Process the query (pass session_id to maintain conversation history)
                result = await self.process_query(
                    user_input,
                    correlation_id=correlation_id,
                    session_id=session_id  # Same session ID for entire chat session
                )

                # Display result
                print(f"\nAssistant: {result['content']}\n")

                # Show status if not success
                if result.get("status") != "success":
                    print(f"(⚠️  Status: {result['status']})\n")

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                log.error(f"Error in chat loop: {e}", exc_info=True)
                print(f"\nError: {str(e)}\n")

    async def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up resources")

        # Close server connections
        await self.exit_stack.aclose()

        # Close PostgreSQL checkpointer connection if it exists
        if self._checkpointer_cm:
            try:
                await self._checkpointer_cm.__aexit__(None, None, None)
                logger.info("PostgreSQL checkpointer closed")
            except Exception as e:
                logger.warning(f"Error closing checkpointer: {e}")

        logger.info("Cleanup complete")

    async def run(self):
        """Main entry point to run the client."""
        try:
            # Initialize database first (if configured)
            await self.initialize_database()

            # Connect to MCP servers
            await self.connect_to_servers()

            # Initialize LLM
            await self.initialize_llm()

            # Start chat loop
            await self.chat_loop()
        finally:
            await self.cleanup()


async def main():
    """Main function to run the MCP client."""
    # Load environment variables from .env file
    from dotenv import load_dotenv
    load_dotenv()

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
