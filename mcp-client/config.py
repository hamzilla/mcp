"""
Configuration module for MCP Client.

Handles environment variables and settings using Pydantic.
"""

from typing import Optional, Union, Literal
import re
import os
from pydantic import BaseModel, field_validator, ConfigDict
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


class StdioServerConfig(BaseModel):
    """Stdio transport (local process execution)."""

    model_config = ConfigDict(extra='forbid')

    transport: Literal["stdio"] = "stdio"
    name: str
    path: str
    command: str = "uv"
    args: list[str] = ["run"]
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Server name cannot be empty")
        return v.strip()

    @field_validator("path")
    @classmethod
    def validate_path_exists(cls, v: str) -> str:
        """Validate that server path exists."""
        if not v or not v.strip():
            raise ValueError("Server path cannot be empty")

        path = v.strip()
        expanded_path = os.path.expanduser(os.path.expandvars(path))

        if not os.path.exists(expanded_path):
            raise ValueError(f"Server path does not exist: {expanded_path}")

        return path


class SSEServerConfig(BaseModel):
    """SSE transport (remote HTTP/SSE connection)."""

    model_config = ConfigDict(extra='forbid')

    transport: Literal["sse"] = "sse"
    name: str
    url: str  # SSE endpoint URL
    headers: dict[str, str] = {}  # Optional headers (supports ${ENV_VAR})
    timeout: float = 5.0  # HTTP timeout
    sse_read_timeout: float = 300.0  # SSE read timeout (5 min)
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Server name cannot be empty")
        return v.strip()

    @field_validator("url")
    @classmethod
    def validate_url_format(cls, v: str) -> str:
        """Validate URL is well-formed."""
        if not v or not v.strip():
            raise ValueError("Server URL cannot be empty")

        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"URL must start with http:// or https://: {v}")

        return v

    def substitute_env_vars(self) -> "SSEServerConfig":
        """
        Substitute ${VAR_NAME} patterns with environment variables.

        Raises ValueError if variable not found.
        """
        def substitute(value: str) -> str:
            pattern = r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)'

            def replacer(match):
                var_name = match.group(1) or match.group(2)
                env_value = os.getenv(var_name)
                if env_value is None:
                    raise ValueError(f"Environment variable not found: {var_name}")
                return env_value

            return re.sub(pattern, replacer, value)

        config_dict = self.model_dump()
        config_dict["url"] = substitute(config_dict["url"])
        config_dict["headers"] = {k: substitute(v) for k, v in config_dict["headers"].items()}

        return SSEServerConfig(**config_dict)


# Discriminated union type
ServerConfig = Union[StdioServerConfig, SSEServerConfig]


def parse_server_config(data: dict) -> Union[StdioServerConfig, SSEServerConfig]:
    """
    Parse server config from dict using transport discriminator.

    Raises ValueError if transport type unknown.
    """
    transport = data.get("transport")

    if transport == "stdio":
        return StdioServerConfig(**data)
    elif transport == "sse":
        return SSEServerConfig(**data)
    else:
        raise ValueError(
            f"Unknown transport type: {transport}. Must be 'stdio' or 'sse'"
        )


class DatabaseConfig(BaseModel):
    """PostgreSQL database configuration."""

    host: str = "localhost"
    port: int = 5432
    database: str = "mcp_client"
    user: str = "mcp_user"
    password: str
    pool_min_size: int = 2
    pool_max_size: int = 10

    @property
    def connection_string(self) -> str:
        """
        Build PostgreSQL connection string.

        Returns:
            Connection string in format: postgresql://user:password@host:port/database
        """
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

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


def load_servers_from_yaml(yaml_path: str) -> list:
    """
    Load server configurations from YAML.

    Returns list of StdioServerConfig or SSEServerConfig objects.

    Args:
        yaml_path: Path to servers.yaml file

    Returns:
        List of ServerConfig objects (only enabled servers)

    Raises:
        FileNotFoundError: If YAML file doesn't exist
        ValueError: If YAML is invalid or server validation fails
    """
    import yaml
    from pathlib import Path
    from loguru import logger

    path = Path(yaml_path)

    if not path.exists():
        raise FileNotFoundError(f"Server configuration file not found: {yaml_path}")

    with open(path, 'r') as f:
        data = yaml.safe_load(f)

    if not data or 'servers' not in data:
        raise ValueError(f"Invalid servers.yaml: missing 'servers' key")

    servers = []
    for server_dict in data['servers']:
        # Validate transport field present
        if 'transport' not in server_dict:
            raise ValueError(
                f"Server '{server_dict.get('name', 'unknown')}' missing required 'transport' field. "
                f"Must be 'stdio' or 'sse'"
            )

        # Parse based on transport type
        server = parse_server_config(server_dict)

        # Only include enabled servers
        if server.enabled:
            servers.append(server)
            logger.info(f"Loaded {server.transport} server: {server.name}")
        else:
            logger.info(f"Skipping disabled server: {server.name}")

    if not servers:
        raise ValueError("No enabled servers found in servers.yaml")

    logger.info(
        f"Loaded {len(servers)} enabled servers from {yaml_path}",
        stdio_count=sum(1 for s in servers if isinstance(s, StdioServerConfig)),
        sse_count=sum(1 for s in servers if isinstance(s, SSEServerConfig)),
    )

    return servers
