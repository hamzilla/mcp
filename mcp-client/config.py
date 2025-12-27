"""
Configuration module for MCP Client.

Handles environment variables and settings using Pydantic.
"""

from typing import Optional
from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMConfig(BaseModel):
    """LLM configuration settings."""

    model_name: str = "gpt-oss:20b"
    temperature: float = 0.0
    timeout_seconds: int = 60
    max_iterations: int = 20  # Increased from hardcoded 10

    @field_validator("max_iterations")
    @classmethod
    def validate_max_iterations(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_iterations must be >= 1")
        return v

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if not 0 <= v <= 2:
            raise ValueError("temperature must be between 0 and 2")
        return v

    @field_validator("timeout_seconds")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        if v < 1:
            raise ValueError("timeout_seconds must be >= 1")
        return v


class ServerConfig(BaseModel):
    """MCP server configuration."""

    name: str
    path: str
    command: str = "uv"
    args: list[str] = ["run"]

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Server name cannot be empty")
        return v.strip()

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Server path cannot be empty")
        return v.strip()


class DatabaseConfig(BaseModel):
    """PostgreSQL database configuration."""

    host: str = "localhost"
    port: int = 5432
    database: str = "mcp_client"
    user: str = "mcp_user"
    password: str
    pool_min_size: int = 2
    pool_max_size: int = 10

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not 1 <= v <= 65535:
            raise ValueError("port must be between 1 and 65535")
        return v

    @field_validator("pool_min_size", "pool_max_size")
    @classmethod
    def validate_pool_sizes(cls, v: int) -> int:
        if v < 1:
            raise ValueError("pool size must be >= 1")
        return v


class MCPClientConfig(BaseSettings):
    """Main MCP client configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_nested_delimiter="__",
        extra="ignore",
    )

    # Core configuration
    llm: LLMConfig = LLMConfig()
    servers: list[ServerConfig]
    ollama_base_url: str = "http://localhost:11434"
    log_level: str = "INFO"

    # Optional database configuration
    database: Optional[DatabaseConfig] = None

    # Metrics configuration
    metrics_enabled: bool = True
    metrics_port: int = 9090

    @field_validator("servers")
    @classmethod
    def validate_servers(cls, v: list[ServerConfig]) -> list[ServerConfig]:
        if not v:
            raise ValueError("At least one server must be configured")

        # Check for duplicate names
        names = [s.name for s in v]
        if len(names) != len(set(names)):
            raise ValueError("Server names must be unique")

        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of: {', '.join(valid_levels)}")
        return v.upper()

    @field_validator("metrics_port")
    @classmethod
    def validate_metrics_port(cls, v: int) -> int:
        if not 1 <= v <= 65535:
            raise ValueError("metrics_port must be between 1 and 65535")
        return v
