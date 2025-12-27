"""
PostgreSQL-backed conversation storage using asyncpg.

Handles persistence of:
- Conversations (chat sessions)
- Messages (human, AI, tool messages)
- Agent mode configuration (scheduled tasks, alerts, webhooks)
"""

import json
from typing import Optional, Any
from uuid import UUID
from datetime import datetime

import asyncpg
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage
from loguru import logger


class ConversationStore:
    """PostgreSQL-backed conversation storage using asyncpg."""

    def __init__(self, pool: asyncpg.Pool):
        """
        Initialize conversation store with database connection pool.

        Args:
            pool: asyncpg connection pool
        """
        self.pool = pool

    # =========================================================================
    # Conversation Management
    # =========================================================================

    async def create_conversation(
        self,
        user_id: str,
        mode: str = "chat",
        metadata: Optional[dict] = None
    ) -> UUID:
        """
        Create a new conversation.

        Args:
            user_id: User identifier
            mode: Conversation mode ('chat' or 'agent')
            metadata: Optional metadata dictionary

        Returns:
            UUID of the created conversation
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO conversations (user_id, mode, metadata)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                user_id,
                mode,
                json.dumps(metadata or {})
            )
            conversation_id = row["id"]
            logger.info(
                "Created conversation",
                conversation_id=str(conversation_id),
                user_id=user_id,
                mode=mode
            )
            return conversation_id

    async def get_conversation(self, conversation_id: UUID) -> Optional[dict]:
        """
        Get conversation details.

        Args:
            conversation_id: Conversation UUID

        Returns:
            Dictionary with conversation details or None if not found
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, user_id, mode, created_at, updated_at, metadata
                FROM conversations
                WHERE id = $1
                """,
                conversation_id
            )

            if not row:
                return None

            return {
                "id": str(row["id"]),
                "user_id": row["user_id"],
                "mode": row["mode"],
                "created_at": row["created_at"].isoformat(),
                "updated_at": row["updated_at"].isoformat(),
                "metadata": row["metadata"]
            }

    async def list_conversations(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> list[dict]:
        """
        List conversations for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of conversations to return
            offset: Offset for pagination

        Returns:
            List of conversation dictionaries
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, user_id, mode, created_at, updated_at, metadata
                FROM conversations
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                user_id,
                limit,
                offset
            )

            return [
                {
                    "id": str(row["id"]),
                    "user_id": row["user_id"],
                    "mode": row["mode"],
                    "created_at": row["created_at"].isoformat(),
                    "updated_at": row["updated_at"].isoformat(),
                    "metadata": row["metadata"]
                }
                for row in rows
            ]

    async def update_conversation_metadata(
        self,
        conversation_id: UUID,
        metadata: dict
    ) -> None:
        """
        Update conversation metadata.

        Args:
            conversation_id: Conversation UUID
            metadata: New metadata dictionary
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE conversations
                SET metadata = $1
                WHERE id = $2
                """,
                json.dumps(metadata),
                conversation_id
            )

    # =========================================================================
    # Message Management
    # =========================================================================

    async def save_message(
        self,
        conversation_id: UUID,
        message: BaseMessage,
        model_name: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> int:
        """
        Save a message to the conversation.

        Args:
            conversation_id: Conversation UUID
            message: LangChain message object
            model_name: Optional model name used
            metadata: Optional metadata dictionary

        Returns:
            Message ID
        """
        # Determine message type and extract fields
        role = self._get_message_role(message)
        content = getattr(message, "content", "")

        # Extract tool calls for AI messages
        tool_calls = None
        if isinstance(message, AIMessage) and hasattr(message, "tool_calls"):
            if message.tool_calls:
                tool_calls = json.dumps(message.tool_calls)

        # Extract tool_call_id for tool messages
        tool_call_id = None
        if isinstance(message, ToolMessage):
            tool_call_id = message.tool_call_id

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO messages (
                    conversation_id, role, content, tool_calls,
                    tool_call_id, model_name, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                conversation_id,
                role,
                content,
                tool_calls,
                tool_call_id,
                model_name,
                json.dumps(metadata or {})
            )
            message_id = row["id"]

            logger.debug(
                "Saved message",
                conversation_id=str(conversation_id),
                message_id=message_id,
                role=role
            )

            return message_id

    async def get_messages(
        self,
        conversation_id: UUID,
        limit: int = 100,
        offset: int = 0
    ) -> list[BaseMessage]:
        """
        Get messages for a conversation.

        Args:
            conversation_id: Conversation UUID
            limit: Maximum number of messages to return
            offset: Offset for pagination

        Returns:
            List of LangChain message objects
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, role, content, tool_calls, tool_call_id, model_name,
                       created_at, metadata
                FROM messages
                WHERE conversation_id = $1
                ORDER BY created_at ASC
                LIMIT $2 OFFSET $3
                """,
                conversation_id,
                limit,
                offset
            )

            messages = []
            for row in rows:
                message = self._row_to_message(row)
                if message:
                    messages.append(message)

            logger.debug(
                "Loaded messages",
                conversation_id=str(conversation_id),
                count=len(messages)
            )

            return messages

    async def delete_conversation(self, conversation_id: UUID) -> None:
        """
        Delete a conversation and all its messages.

        Args:
            conversation_id: Conversation UUID
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM conversations WHERE id = $1",
                conversation_id
            )
            logger.info(
                "Deleted conversation",
                conversation_id=str(conversation_id)
            )

    # =========================================================================
    # Agent Mode Methods (for future use)
    # =========================================================================

    async def create_scheduled_task(
        self,
        name: str,
        schedule_type: str,
        schedule_config: dict,
        query_template: str,
        description: Optional[str] = None,
        enabled: bool = True,
        metadata: Optional[dict] = None
    ) -> UUID:
        """Create a scheduled task for agent mode."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO scheduled_tasks (
                    name, description, schedule_type, schedule_config,
                    query_template, enabled, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                name,
                description,
                schedule_type,
                json.dumps(schedule_config),
                query_template,
                enabled,
                json.dumps(metadata or {})
            )
            return row["id"]

    async def get_scheduled_tasks(self, enabled_only: bool = True) -> list[dict]:
        """Get scheduled tasks."""
        async with self.pool.acquire() as conn:
            query = """
                SELECT id, name, description, schedule_type, schedule_config,
                       query_template, enabled, last_run, next_run, metadata
                FROM scheduled_tasks
            """
            if enabled_only:
                query += " WHERE enabled = TRUE"

            rows = await conn.fetch(query)

            return [
                {
                    "id": str(row["id"]),
                    "name": row["name"],
                    "description": row["description"],
                    "schedule_type": row["schedule_type"],
                    "schedule_config": row["schedule_config"],
                    "query_template": row["query_template"],
                    "enabled": row["enabled"],
                    "last_run": row["last_run"].isoformat() if row["last_run"] else None,
                    "next_run": row["next_run"].isoformat() if row["next_run"] else None,
                    "metadata": row["metadata"]
                }
                for row in rows
            ]

    async def update_task_execution(
        self,
        task_id: UUID,
        status: str,
        result: Optional[dict] = None,
        error: Optional[str] = None
    ) -> int:
        """Record task execution result."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO task_executions (task_id, status, result, error)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                task_id,
                status,
                json.dumps(result) if result else None,
                error
            )
            return row["id"]

    async def create_alert_rule(
        self,
        name: str,
        condition_type: str,
        condition_config: dict,
        action_type: str,
        action_config: dict,
        description: Optional[str] = None,
        enabled: bool = True,
        metadata: Optional[dict] = None
    ) -> UUID:
        """Create an alert rule for agent mode."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO alert_rules (
                    name, description, condition_type, condition_config,
                    action_type, action_config, enabled, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                name,
                description,
                condition_type,
                json.dumps(condition_config),
                action_type,
                json.dumps(action_config),
                enabled,
                json.dumps(metadata or {})
            )
            return row["id"]

    async def get_alert_rules(self, enabled_only: bool = True) -> list[dict]:
        """Get alert rules."""
        async with self.pool.acquire() as conn:
            query = """
                SELECT id, name, description, condition_type, condition_config,
                       action_type, action_config, enabled, metadata
                FROM alert_rules
            """
            if enabled_only:
                query += " WHERE enabled = TRUE"

            rows = await conn.fetch(query)

            return [
                {
                    "id": str(row["id"]),
                    "name": row["name"],
                    "description": row["description"],
                    "condition_type": row["condition_type"],
                    "condition_config": row["condition_config"],
                    "action_type": row["action_type"],
                    "action_config": row["action_config"],
                    "enabled": row["enabled"],
                    "metadata": row["metadata"]
                }
                for row in rows
            ]

    async def register_webhook(
        self,
        name: str,
        url: str,
        event_types: list[str],
        headers: Optional[dict] = None,
        enabled: bool = True
    ) -> UUID:
        """Register a webhook configuration."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO webhook_configs (name, url, event_types, headers, enabled)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                name,
                url,
                event_types,
                json.dumps(headers or {}),
                enabled
            )
            return row["id"]

    async def get_webhooks_for_event(self, event_type: str) -> list[dict]:
        """Get webhooks configured for a specific event type."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, name, url, event_types, headers, retry_config
                FROM webhook_configs
                WHERE enabled = TRUE AND $1 = ANY(event_types)
                """,
                event_type
            )

            return [
                {
                    "id": str(row["id"]),
                    "name": row["name"],
                    "url": row["url"],
                    "event_types": row["event_types"],
                    "headers": row["headers"],
                    "retry_config": row["retry_config"]
                }
                for row in rows
            ]

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_message_role(self, message: BaseMessage) -> str:
        """Get role string from message type."""
        if isinstance(message, HumanMessage):
            return "human"
        elif isinstance(message, AIMessage):
            return "ai"
        elif isinstance(message, ToolMessage):
            return "tool"
        else:
            return "unknown"

    def _row_to_message(self, row) -> Optional[BaseMessage]:
        """Convert database row to LangChain message object."""
        role = row["role"]
        content = row["content"] or ""

        if role == "human":
            return HumanMessage(content=content)

        elif role == "ai":
            # Reconstruct AIMessage with tool calls if present
            tool_calls = []
            if row["tool_calls"]:
                tool_calls = json.loads(row["tool_calls"])

            return AIMessage(content=content, tool_calls=tool_calls)

        elif role == "tool":
            # Reconstruct ToolMessage
            return ToolMessage(
                content=content,
                tool_call_id=row["tool_call_id"]
            )

        else:
            logger.warning(f"Unknown message role: {role}")
            return None


async def create_connection_pool(
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
    min_size: int = 2,
    max_size: int = 10
) -> asyncpg.Pool:
    """
    Create an asyncpg connection pool.

    Args:
        host: Database host
        port: Database port
        database: Database name
        user: Database user
        password: Database password
        min_size: Minimum pool size
        max_size: Maximum pool size

    Returns:
        asyncpg connection pool
    """
    pool = await asyncpg.create_pool(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        min_size=min_size,
        max_size=max_size
    )

    logger.info(
        "Created database connection pool",
        host=host,
        database=database,
        min_size=min_size,
        max_size=max_size
    )

    return pool
