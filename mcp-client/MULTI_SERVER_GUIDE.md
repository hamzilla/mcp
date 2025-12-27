# Multi-Server Setup Guide

This guide shows how to use the MCP client with multiple servers simultaneously.

## Quick Start

The client is already configured to connect to both the Weather and Bitbucket servers. Just run:

```bash
cd /Users/hamzilla/mcp/mcp-client
python client.py
```

## Current Configuration

The client in [client.py](client.py) is configured with:

```python
servers = [
    {
        "name": "weather",
        "path": "/Users/hamzilla/mcp/weather/weather.py",
        "command": "python"
    },
    {
        "name": "bitbucket",
        "path": "/Users/hamzilla/mcp/bitbucket-mcp/main.py",
        "command": "python"
    }
]
```

## Example Usage

### Weather Server Tools

Ask questions about weather:
- "What's the weather in San Francisco?"
- "Tell me the temperature in New York"
- "Is it going to rain in Seattle?"

### Bitbucket Server Tools

Ask questions about pipelines:
- "Which pipelines failed in my-repo?"
- "Which pipeline steps fail the most in my-repo?"
- "Get me the logs for the latest pipeline failure in my-repo"
- "Show me all recent pipelines for my-repo"
- "Analyze step failures in my-repo"

### Combined Queries

The LLM can intelligently use tools from both servers:
- "Check the weather in San Francisco and also tell me about failed pipelines in my-repo"

## How Tool Routing Works

1. When the client starts, it connects to all configured servers
2. Each server provides a list of tools it offers
3. The client builds a combined tool list and tracks which server owns each tool
4. When the LLM wants to call a tool, the client automatically routes it to the correct server
5. Results are returned to the LLM seamlessly

## Adding More Servers

To add another MCP server, just add it to the `servers` list:

```python
servers = [
    {
        "name": "weather",
        "path": "/Users/hamzilla/mcp/weather/weather.py",
        "command": "python"
    },
    {
        "name": "bitbucket",
        "path": "/Users/hamzilla/mcp/bitbucket-mcp/main.py",
        "command": "python"
    },
    {
        "name": "my-new-server",
        "path": "/path/to/server.py",
        "command": "python"  # or "uvx", "npx", etc.
    }
]
```

## Server Requirements

Each MCP server must:
- Implement the MCP protocol correctly
- Run via stdio (standard input/output)
- Provide unique tool names (no conflicts with other servers)

## Troubleshooting Multi-Server Setup

**One server fails to connect**: The client will show which server failed in the logs. Check that server's path and permissions.

**Tool name conflicts**: If two servers provide a tool with the same name, the last one loaded will override. Ensure unique tool names.

**Performance**: Each server runs as a separate process. If you have many servers, startup time may increase slightly.

## Benefits of Multi-Server Setup

✅ **Single interface** - Ask questions about weather, pipelines, or anything else in one chat
✅ **Automatic routing** - The client handles routing tool calls to the right server
✅ **Independent servers** - Each server can be updated/replaced without affecting others
✅ **Scalable** - Add as many servers as you need
✅ **Type safety** - Each server maintains its own tool definitions and schemas
