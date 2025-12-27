# MCP Client with LangGraph

Production-ready MCP client powered by LangGraph for autonomous agent workflows.

## 🚀 What's New

This client has been migrated from a custom agent implementation to **LangGraph**, the official agent framework from LangChain. This provides:

- ✅ **Production-grade agent execution** with built-in error handling
- ✅ **PostgreSQL conversation persistence** across restarts
- ✅ **Automatic tool execution** with retry logic
- ✅ **Streaming support** (ready to enable)
- ✅ **Better observability** via LangSmith integration
- ✅ **155 fewer lines** of custom code to maintain

## 📋 Quick Start

### 1. Install Dependencies

```bash
uv sync
```

This installs:
- `langgraph>=0.2.59` - Agent framework
- `langgraph-checkpoint-postgres>=3.0.2` - PostgreSQL persistence
- `langchain-core>=0.3.29` - Core LangChain functionality
- `langchain-postgres>=0.0.12` - PostgreSQL utilities

### 2. Configure Database (Optional)

For conversation persistence, create `.env`:

```bash
# Database configuration (optional - skip for no persistence)
DATABASE__HOST=localhost
DATABASE__PORT=5432
DATABASE__DATABASE=mcp_client
DATABASE__USER=mcp_user
DATABASE__PASSWORD=your_password

# LLM configuration
LLM__MODEL_NAME=gpt-oss:20b
LLM__MAX_ITERATIONS=20
LLM__TEMPERATURE=0.0
LLM__TIMEOUT_SECONDS=60
```

### 3. Run the Client

```bash
uv run python client.py
```

## 🎯 Key Features

### Agent-Based Execution

The client uses LangGraph's ReAct agent pattern:
1. **Observe** - Receive user query
2. **Think** - Determine which tools to use
3. **Act** - Execute tools and gather results
4. **Repeat** - Continue until task is complete

### Conversation Persistence

With PostgreSQL configured, conversations persist across restarts:
- Each conversation has a unique `thread_id`
- Full message history is maintained
- Pick up where you left off after restart
- LangGraph auto-creates database tables on first run

### Multi-Server Tool Support

Connect to multiple MCP servers simultaneously:
- Bitbucket (pipelines, PRs, repositories)
- Weather (current conditions, forecasts)
- Custom servers (add your own)

The agent automatically routes tool calls to the correct server.

## 🏗️ Architecture

### Before (Custom Implementation)

```python
# ~155 lines of custom code
for i in range(max_iterations):
    response = await llm.ainvoke(messages)

    if not response.tool_calls:
        return response.content

    for tool_call in response.tool_calls:
        server = tool_to_server_map[tool_name]
        result = await server.call_tool(tool_name, args)
        messages.append(ToolMessage(...))
```

### After (LangGraph)

```python
# ~40 lines using LangGraph
config = {
    "recursion_limit": max_iterations,
    "configurable": {"thread_id": session_id}
}

result = await agent.ainvoke(
    {"messages": [HumanMessage(content=query)]},
    config=config
)
```

## 📁 Project Structure

```
mcp-client/
├── client.py                    # Main MCP client with LangGraph agent
├── mcp_tool_wrapper.py         # MCP → LangChain tool bridge
├── config.py                   # Pydantic configuration
├── logging_config.py           # Structured logging setup
├── storage/
│   ├── __init__.py            # Connection string builder
│   └── conversation_store.py  # Agent mode tables (future)
├── LANGGRAPH_MIGRATION.md     # Detailed migration notes
└── README_LANGGRAPH.md        # This file
```

## 🔧 Configuration

### LLM Settings

```python
class LLMConfig(BaseModel):
    model_name: str = "gpt-oss:20b"
    temperature: float = 0.0
    timeout_seconds: int = 60
    max_iterations: int = 20  # Recursion limit
```

### Server Configuration

```python
servers = [
    ServerConfig(
        name="bitbucket",
        path="/Users/hamzilla/mcp/bitbucket-mcp/main.py",
        command="uv",
        args=["run"]
    ),
    ServerConfig(
        name="weather",
        path="/Users/hamzilla/mcp/weather/weather.py",
        command="uv",
        args=["run"]
    )
]
```

## 🗄️ Database Schema

When database is configured, LangGraph automatically creates:

### Checkpointer Tables
- `checkpoints` - Conversation state snapshots
- `checkpoint_writes` - Pending checkpoint writes
- `checkpoint_blobs` - Binary checkpoint data

### Future: Agent Mode Tables
(In `storage/schema.sql` - not yet used)
- `scheduled_tasks` - Cron/interval jobs
- `alert_rules` - Condition-based alerts
- `webhook_configs` - Event webhooks
- `task_executions` - Execution history

## 🧪 Testing

### Import Test

```bash
uv run python -c "
from client import MCPClient
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
print('✓ All imports successful')
"
```

### Integration Test

```bash
# 1. Start PostgreSQL (if using persistence)
docker-compose up -d postgres

# 2. Run client
uv run python client.py

# 3. Test multi-turn conversation
You: What's the weather in San Francisco?
Assistant: [Uses weather tool, provides answer]

You: How about New York?
Assistant: [Remembers context, gets NYC weather]
```

## 🚀 Future Enhancements

With LangGraph, these features are now easy to add:

### 1. Streaming Responses
```python
async for event in agent.astream({"messages": [query]}, config):
    print(event)  # Stream intermediate steps
```

### 2. Human-in-the-Loop
```python
# Pause execution for approval
checkpointer.interrupt_before = ["tool_execution"]
```

### 3. Multi-Agent Workflows
```python
# Create specialized sub-agents
ci_agent = create_agent(llm, tools=ci_tools)
ops_agent = create_agent(llm, tools=ops_tools)
```

### 4. Custom Middleware
```python
@before_model
async def add_context(state):
    # Inject additional context
    pass

@after_model
async def validate_output(state):
    # Content filtering
    pass
```

## 📚 Resources

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Migration Guide](LANGGRAPH_MIGRATION.md)
- [LangGraph Agents: Complete Guide 2025](https://www.leanware.co/insights/langchain-agents-complete-guide-in-2025)
- [Checkpointing Documentation](https://docs.langchain.com/oss/python/langgraph/persistence)

## 🐛 Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker ps | grep postgres

# Test connection
psql -U mcp_user -d mcp_client -h localhost

# Check logs
tail -f logs/mcp_client.log
```

### Tool Execution Errors

```python
# Enable debug logging
export LOG_LEVEL=DEBUG
uv run python client.py
```

### Import Errors

```bash
# Reinstall dependencies
uv sync --reinstall
```

## 📝 License

Same as main project.

## 🙏 Acknowledgments

Built with:
- [LangGraph](https://github.com/langchain-ai/langgraph) by LangChain
- [Model Context Protocol](https://modelcontextprotocol.io/) by Anthropic
- [Ollama](https://ollama.ai/) for local LLM execution
