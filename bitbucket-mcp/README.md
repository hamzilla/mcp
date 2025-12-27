# Bitbucket MCP Server - Pipeline Operations

A Python MCP (Model Context Protocol) server for interacting with Bitbucket pipelines. This server enables AI assistants to query pipeline information, analyze failures, and retrieve logs.

## Features

### Available Tools

1. **list_pipelines** - List recent pipelines for a repository
   - Filter by status (SUCCESSFUL, FAILED, ERROR, etc.)
   - See build numbers, duration, trigger info, and more

2. **get_pipeline_details** - Get detailed information about a specific pipeline
   - View all steps and their status
   - See timing information for each step

3. **get_failed_pipelines** - Get all failed pipelines with failure details
   - Automatically identifies which steps failed
   - Returns failed step information

4. **get_step_logs** - Retrieve logs for a specific pipeline step
   - Get full log output for debugging

5. **analyze_step_failures** - Analyze which steps fail most frequently
   - Statistics across recent pipeline runs
   - Identify problematic steps

6. **get_latest_failure_logs** - Get logs from the most recent failed pipeline
   - Automatically finds the latest failure
   - Returns logs from the failed step

## Installation

### Prerequisites

- Python 3.13+
- Bitbucket account with API access
- Bitbucket App Password or Personal Access Token

### Create a Bitbucket App Password

1. Go to your Bitbucket account settings
2. Navigate to **App passwords** (under Access management)
3. Click **Create app password**
4. Give it a label (e.g., "MCP Server")
5. Select permissions:
   - **Repositories**: Read
   - **Pipelines**: Read
6. Click **Create** and save the password

### Install Dependencies

```bash
# Using uv (recommended)
cd /Users/hamzilla/mcp/bitbucket-mcp
uv sync

# Or using pip
pip install -e .
```

## Configuration

Create a `.env` file in the project directory:

```bash
cp .env.example .env
```

Edit `.env` with your Bitbucket credentials:

```env
# Required: Your Bitbucket workspace name
BITBUCKET_WORKSPACE=your-workspace-name

# Authentication Option 1: App Password (recommended)
BITBUCKET_USERNAME=your-username
BITBUCKET_PASSWORD=your-app-password

# Authentication Option 2: Personal Access Token
# BITBUCKET_TOKEN=your-access-token

# Optional: API URL (defaults to https://api.bitbucket.org/2.0)
# BITBUCKET_API_URL=https://api.bitbucket.org/2.0
```

## Usage

### Running the Server Standalone

```bash
python main.py
```

The server runs via stdio and communicates using the MCP protocol.

### Using with MCP Client

Update your MCP client configuration to use this server:

```python
from mcp_client import MCPClient

client = MCPClient(
    server_script_path="/Users/hamzilla/mcp/bitbucket-mcp/main.py",
    model_name="llama3.2",
)

await client.run()
```

### Example Queries

Once connected to an MCP client with an LLM:

```
You: Which pipelines failed recently in my-repo?
Assistant: [Calls get_failed_pipelines tool and shows results]

You: Which pipeline steps fail the most in my-repo?
Assistant: [Calls analyze_step_failures tool and shows statistics]

You: Get me the logs for the latest pipeline failure in my-repo
Assistant: [Calls get_latest_failure_logs tool and shows logs]

You: Show me all pipelines for my-repo
Assistant: [Calls list_pipelines tool and shows pipeline list]
```

## API Reference

### Tool Parameters

All tools accept:
- `repo_slug` (required): Repository name/slug
- `workspace` (optional): Workspace name (uses default from config if not provided)

#### list_pipelines
```json
{
  "repo_slug": "my-repository",
  "status": "FAILED",  // optional: filter by status
  "limit": 50          // optional: max pipelines to return
}
```

#### get_pipeline_details
```json
{
  "repo_slug": "my-repository",
  "pipeline_uuid": "{12345678-1234-1234-1234-123456789abc}"
}
```

#### get_failed_pipelines
```json
{
  "repo_slug": "my-repository",
  "limit": 100  // optional: max pipelines to check
}
```

#### get_step_logs
```json
{
  "repo_slug": "my-repository",
  "pipeline_uuid": "{pipeline-uuid}",
  "step_uuid": "{step-uuid}"
}
```

#### analyze_step_failures
```json
{
  "repo_slug": "my-repository",
  "limit": 100  // optional: pipelines to analyze
}
```

#### get_latest_failure_logs
```json
{
  "repo_slug": "my-repository"
}
```

## Architecture

```
┌─────────────────┐
│   MCP Client    │
│   (with LLM)    │
└────────┬────────┘
         │ MCP Protocol (stdio)
         │
┌────────▼────────┐
│ Bitbucket MCP   │
│     Server      │
│  ┌───────────┐  │
│  │  config   │  │
│  │  server   │  │
│  │   main    │  │
│  └───────────┘  │
└────────┬────────┘
         │ HTTPS
         │
┌────────▼────────┐
│  Bitbucket API  │
│  (api.bitbucket │
│    .org/2.0)    │
└─────────────────┘
```

## Project Structure

```
bitbucket-mcp/
├── main.py           # Entry point
├── server.py         # MCP server implementation with all tools
├── config.py         # Configuration and settings
├── pyproject.toml    # Dependencies
├── .env              # Environment variables (create from .env.example)
├── .env.example      # Example environment configuration
└── README.md         # This file
```

## Troubleshooting

### Authentication Errors

- Verify your app password or token is correct
- Check that your app password has the required permissions (Repositories: Read, Pipelines: Read)
- Ensure workspace name is correct

### Pipeline Not Found

- Verify the repository slug is correct (use the URL slug, not the display name)
- Check that the pipeline UUID is properly formatted (should have curly braces: `{uuid}`)

### No Failed Pipelines Found

- The repository may not have any recent failed pipelines
- Try increasing the `limit` parameter to check more history

## Development

### Running Tests

```bash
# TODO: Add tests
pytest
```

### Code Style

```bash
# Format code
black .

# Lint
ruff check .
```

## License

MIT

## References

Built using the [Model Context Protocol](https://modelcontextprotocol.io/) and based on patterns from [bitbucket-mcp TypeScript implementation](https://github.com/MatanYemini/bitbucket-mcp).

## Sources

- [Bitbucket Cloud REST API - Pipelines](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-pipelines/)
- [The Bitbucket Cloud REST API](https://developer.atlassian.com/cloud/bitbucket/rest/)
