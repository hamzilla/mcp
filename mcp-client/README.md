# Multi-Server MCP Client with Ollama

A powerful MCP (Model Context Protocol) client that connects to **multiple MCP servers** simultaneously using Ollama for LLM interactions.

## Prerequisites

1. **Python 3.13+** installed
2. **Ollama** installed and running locally
   ```bash
   # Install Ollama from https://ollama.ai
   # Start Ollama (usually runs automatically)
   ollama serve
   ```

3. **Ollama model** pulled
   ```bash
   ollama pull llama3.2
   # or any other model you prefer
   ```

## Installation

Dependencies are already specified in `pyproject.toml`. Install them with:

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

## Configuration

Update the `servers` list in [client.py](client.py:233-244) to configure your MCP servers:

```python
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
```

Each server configuration needs:
- **name**: A unique identifier for the server
- **path**: Path to the server script or package name
- **command**: Command to run the server (e.g., "python", "uv", "npx")
- **args** (optional): Additional arguments before the path (e.g., ["run"] for "uv run")

You can also customize:
- **Model name**: Change `model_name="gpt-oss:20b"` to any Ollama model you have
- **Ollama URL**: Change `ollama_base_url` if Ollama is running on a different port

## Usage

Run the client:

```bash
python client.py
```

This will start an interactive chat session where you can ask questions using tools from **all connected servers**:

```
🤖 Multi-Server MCP Client with Ollama
==================================================
Connected servers: weather, bitbucket
Total tools available: 12
Ask me anything!

You: What's the weather like in San Francisco?
Assistant: [Response from Ollama using the weather MCP server]

You: Which pipelines failed in my-repo?
Assistant: [Response from Ollama using the Bitbucket MCP server]

You: quit
Goodbye!
```

## How It Works

1. **Connects to Multiple MCP Servers**: Establishes stdio connections to all configured servers
2. **Lists Available Tools**: Retrieves all tools from all servers and combines them
3. **Tool Routing**: Tracks which server provides each tool for intelligent routing
4. **Initializes Ollama**: Sets up ChatOllama with all MCP tools bound to it
5. **Agent Loop**:
   - Takes user input
   - Sends it to Ollama
   - If Ollama wants to call a tool, automatically routes it to the correct server
   - Returns tool results to Ollama
   - Continues until Ollama has a final answer

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   User      │────▶│   MCP Client     │────▶│  Ollama (LLM)   │
└─────────────┘     │   (client.py)    │     └─────────────────┘
                    │                  │              │
                    │  ┌────────────┐  │              │
                    │  │ All Tools  │◀─┼──────────────┘
                    │  │  + Router  │  │
                    │  └──────┬─────┘  │
                    │         │        │
                    │    ┌────┴─────┐  │
                    │    │          │  │
                    │    ▼          ▼  │
                    │ ┌────────┐ ┌────────┐
                    │ │Weather │ │Bitbucket│
                    │ │Server  │ │Server   │
                    │ └────────┘ └────────┘
                    └──────────────────────┘
```

## Troubleshooting

**Ollama connection error**: Make sure Ollama is running (`ollama serve`)

**Model not found**: Pull the model first (`ollama pull llama3.2`)

**Server connection error**: Verify the paths to your servers are correct and the servers are executable

**Tool call errors**: Check that your servers are properly implementing the MCP protocol

**Tool routing errors**: Ensure each tool has a unique name across all servers
