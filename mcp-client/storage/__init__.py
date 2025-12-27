"""
Storage module for MCP Client.

Uses LangGraph's AsyncPostgresSaver for conversation state persistence.
"""


def build_connection_string(
    host: str,
    port: int,
    database: str,
    user: str,
    password: str
) -> str:
    """
    Build PostgreSQL connection string.

    Args:
        host: Database host
        port: Database port
        database: Database name
        user: Database user
        password: Database password

    Returns:
        Connection string in format: postgresql://user:password@host:port/database
    """
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


__all__ = ["build_connection_string"]
