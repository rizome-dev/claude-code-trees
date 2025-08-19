"""Configuration management for Claude Code Trees."""

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Config(BaseModel):
    """Configuration settings for Claude Code Trees."""

    # Database settings
    database_url: str = Field(default="sqlite:///claude_code_trees.db")

    # Git settings
    default_branch: str = Field(default="main")
    worktree_base_path: Path = Field(default_factory=lambda: Path.cwd() / ".worktrees")

    # Claude settings
    claude_api_key: str | None = Field(default=None)
    claude_model: str = Field(default="claude-3-sonnet-20240229")
    max_tokens: int = Field(default=4096)

    # Orchestration settings
    max_concurrent_instances: int = Field(default=3)
    instance_timeout: int = Field(default=300)  # seconds

    # Session settings
    session_timeout: int = Field(default=3600)  # seconds
    auto_save_interval: int = Field(default=60)  # seconds

    # Logging settings
    log_level: str = Field(default="INFO")
    log_file: Path | None = Field(default=None)

    model_config = ConfigDict(
        env_prefix="CLCT_",
        env_file=".env"
    )

    @field_validator("worktree_base_path", mode="before")
    @classmethod
    def resolve_path(cls, v: Any) -> Path:
        """Resolve and create path if it doesn't exist."""
        path = Path(v) if not isinstance(v, Path) else v
        return path.resolve()

    @field_validator("claude_api_key", mode="before")
    @classmethod
    def get_api_key(cls, v: str | None) -> str | None:
        """Get API key from environment if not provided."""
        if v is None:
            v = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        return v

    def ensure_directories(self) -> None:
        """Ensure required directories exist."""
        self.worktree_base_path.mkdir(parents=True, exist_ok=True)
        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load_from_file(cls, config_path: Path | None = None) -> "Config":
        """Load configuration from file."""
        if config_path and config_path.exists():
            # Could implement TOML/YAML loading here
            pass
        return cls()

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return self.model_dump()
