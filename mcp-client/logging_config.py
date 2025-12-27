"""
Logging configuration for MCP Client.

Provides structured logging setup with support for both JSON (production)
and human-readable (development) formats.
"""

import sys
from loguru import logger


def setup_logging(log_level: str = "INFO", structured: bool = False) -> None:
    """
    Configure loguru with appropriate format for environment.

    Args:
        log_level: Logging level (TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL)
        structured: If True, use JSON format for log aggregation tools.
                   If False, use human-readable format for development.

    Example:
        >>> setup_logging("INFO", structured=True)  # Production
        >>> setup_logging("DEBUG", structured=False)  # Development
    """
    # Remove default handler
    logger.remove()

    if structured:
        # JSON format for production/log aggregation
        # Each log line is a complete JSON object with all fields
        logger.add(
            sys.stderr,
            format="{message}",  # Just the message field (loguru will serialize)
            serialize=True,  # Serialize to JSON
            level=log_level,
            backtrace=True,  # Include traceback info
            diagnose=True,  # Include variable values in exceptions
        )
    else:
        # Human-readable format for development
        # Includes colored output and clear formatting
        logger.add(
            sys.stderr,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            ),
            level=log_level,
            colorize=True,  # Enable colored output
            backtrace=True,
            diagnose=True,
        )

    logger.info(
        f"Logging configured",
        level=log_level,
        structured=structured,
    )


def get_logger_with_context(**context):
    """
    Get a logger instance bound with context variables.

    Args:
        **context: Key-value pairs to bind to the logger

    Returns:
        Logger instance with bound context

    Example:
        >>> log = get_logger_with_context(
        ...     correlation_id="abc-123",
        ...     user_id="user-456"
        ... )
        >>> log.info("Processing request")
        # Output includes correlation_id and user_id in every log
    """
    return logger.bind(**context)
