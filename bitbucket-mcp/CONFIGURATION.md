# Configuration Guide

## Environment Variables

The Bitbucket MCP server uses environment variables from a `.env` file for configuration.

### Required Variables

- **BITBUCKET_WORKSPACE**: Your Bitbucket workspace slug (e.g., "mycompany")
- **Authentication**: Must provide ONE of:
  - `BITBUCKET_TOKEN`: Personal access token
  - `BITBUCKET_USERNAME` + `BITBUCKET_PASSWORD`: App password authentication

### Optional Variables

- **BITBUCKET_REPO_SLUG**: Default repository to use for all operations
  - When set, `repo_slug` becomes optional in all tool calls
  - Useful when working primarily with a single repository
  - Example: `buildkit-runners`

- **BITBUCKET_API_URL**: Bitbucket API endpoint
  - Default: `https://api.bitbucket.org/2.0`
  - Only change for self-hosted Bitbucket instances

## Default Repository Feature

When you set `BITBUCKET_REPO_SLUG` in your `.env` file:

1. **All tools become simpler** - No need to specify `repo_slug` in every call
2. **Tool descriptions update** - Shows the default repo in tool descriptions
3. **Schema changes** - `repo_slug` is no longer required in the input schema
4. **Flexible usage** - Can still override by providing `repo_slug` explicitly

### Example Usage

**Without default repo** (`.env`):
```env
BITBUCKET_WORKSPACE=mycompany
BITBUCKET_TOKEN=xyz...
```

Tool call requires `repo_slug`:
```json
{
  "repo_slug": "my-repository",
  "limit": 10
}
```

**With default repo** (`.env`):
```env
BITBUCKET_WORKSPACE=mycompany
BITBUCKET_TOKEN=xyz...
BITBUCKET_REPO_SLUG=my-repository
```

Tool call is simplified:
```json
{
  "limit": 10
}
```

Or override the default:
```json
{
  "repo_slug": "different-repository",
  "limit": 10
}
```

## Configuration Examples

### Single Repository Setup

Perfect for teams working on one main repository:

```env
BITBUCKET_WORKSPACE=mycompany
BITBUCKET_TOKEN=ATCTT3xFfGN0...
BITBUCKET_REPO_SLUG=main-application
```

### Multi-Repository Setup

For working across multiple repositories:

```env
BITBUCKET_WORKSPACE=mycompany
BITBUCKET_TOKEN=ATCTT3xFfGN0...
# No BITBUCKET_REPO_SLUG - must specify repo_slug in each call
```

### Self-Hosted Bitbucket

```env
BITBUCKET_WORKSPACE=mycompany
BITBUCKET_USERNAME=john.doe
BITBUCKET_PASSWORD=app-password-here
BITBUCKET_API_URL=https://bitbucket.internal.company.com/api/2.0
```

## Impact on Tool Calls

All six pipeline tools support the default repository feature:

1. **list_pipelines**
2. **get_pipeline_details**
3. **get_failed_pipelines**
4. **get_step_logs**
5. **analyze_step_failures**
6. **get_latest_failure_logs**

When `BITBUCKET_REPO_SLUG` is set, these tools automatically use it unless you provide a different `repo_slug` in the tool arguments.
