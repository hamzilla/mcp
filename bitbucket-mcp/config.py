"""
Configuration module for Bitbucket MCP Server.

Handles environment variables and settings using Pydantic.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Bitbucket API Configuration
    bitbucket_api_url: str = "https://api.bitbucket.org/2.0"
    bitbucket_workspace: str

    # Authentication - use either token OR username/password
    bitbucket_token: Optional[str] = None
    bitbucket_username: Optional[str] = None
    bitbucket_password: Optional[str] = None

    # Repository Slug (optional)
    bitbucket_repo_slug: Optional[str] = None

    def model_post_init(self, __context) -> None:
        """Validate that authentication is properly configured."""
        has_token = bool(self.bitbucket_token)
        has_basic_auth = bool(self.bitbucket_username and self.bitbucket_password)

        if not has_token and not has_basic_auth:
            raise ValueError(
                "Authentication required: provide either BITBUCKET_TOKEN "
                "or both BITBUCKET_USERNAME and BITBUCKET_PASSWORD"
            )
