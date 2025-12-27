# PostgreSQL Setup for Conversation Memory

## Why You're Not Seeing Memory

Currently, the LangGraph checkpointer **fails to initialize** because PostgreSQL is not running. You'll see this in the logs:

```
Failed to initialize PostgreSQL checkpointer: ...
Continuing without conversation persistence
```

Without the checkpointer, each query is independent - no conversation history.

## Quick Setup (2 minutes)

### Step 1: Start PostgreSQL with Docker

```bash
cd /Users/hamzilla/mcp/mcp-client
docker-compose up -d
```

This starts PostgreSQL on `localhost:5432` with:
- Database: `mcp_client`
- User: `mcp_user`
- Password: `changeme`

### Step 2: Create .env File

```bash
cp .env.example .env
```

Then edit `.env` and **uncomment** the database section:

```bash
# Change from commented:
# DATABASE__HOST=localhost
# DATABASE__PORT=5432

# To uncommented:
DATABASE__HOST=localhost
DATABASE__PORT=5432
DATABASE__DATABASE=mcp_client
DATABASE__USER=mcp_user
DATABASE__PASSWORD=changeme
```

### Step 3: Restart the Client

```bash
uv run python client.py
```

You should now see:
```
LangGraph PostgreSQL checkpointer initialized successfully
Conversations will persist across restarts
💾 Conversation persistence: Enabled (PostgreSQL)
```

## Testing Memory

Try this conversation:

```
You: My name is Alice
Assistant: Nice to meet you, Alice! How can I help you today?

You: What's my name?
Assistant: Your name is Alice.
```

The second query works because the checkpointer saved the conversation history!

## What Tables Are Created?

LangGraph automatically creates these tables:

```sql
-- Conversation state snapshots
CREATE TABLE checkpoints (...)

-- Pending checkpoint writes
CREATE TABLE checkpoint_writes (...)

-- Binary checkpoint data
CREATE TABLE checkpoint_blobs (...)
```

You can inspect them:

```bash
docker exec -it mcp-postgres psql -U mcp_user -d mcp_client

# Inside psql:
\dt                          # List tables
SELECT * FROM checkpoints;   # View saved conversations
```

## Troubleshooting

### Port 5432 Already in Use

If you have PostgreSQL already running:

**Option A:** Use existing PostgreSQL
```bash
# Update .env to point to your existing server
DATABASE__HOST=localhost
DATABASE__PORT=5432
DATABASE__DATABASE=your_existing_db
DATABASE__USER=your_user
DATABASE__PASSWORD=your_password
```

**Option B:** Use different port
```yaml
# In docker-compose.yml, change:
ports:
  - "5433:5432"  # Host port 5433 instead

# Then in .env:
DATABASE__PORT=5433
```

### Connection Refused

```bash
# Check PostgreSQL is running
docker ps | grep postgres

# Check logs
docker logs mcp-postgres

# Restart if needed
docker-compose restart
```

### Permission Denied

```bash
# Reset volumes
docker-compose down -v
docker-compose up -d
```

## Stop PostgreSQL

When done testing:

```bash
docker-compose down          # Stop and remove container
docker-compose down -v       # Also delete data
```

## Production Setup

For production, use managed PostgreSQL:
- AWS RDS
- Google Cloud SQL
- Azure Database for PostgreSQL
- Supabase
- Neon

Update `.env` with production credentials:
```bash
DATABASE__HOST=your-prod-server.aws.com
DATABASE__PORT=5432
DATABASE__DATABASE=mcp_prod
DATABASE__USER=mcp_prod_user
DATABASE__PASSWORD=<strong-password>
```

## Without PostgreSQL

If you don't want to use PostgreSQL, the client still works - you just won't have conversation memory. Each query is independent.

To verify this is expected behavior, check the startup message:
```
Database not configured, skipping initialization
```

This means conversation memory is disabled by design.
