"""
Claude Code Trees - Lightweight Python library for managing Claude Code instances on git worktrees.

This library provides a high-level interface for managing multiple Claude Code instances
across different git worktrees, enabling parallel development workflows and sophisticated
orchestration of AI-powered coding tasks.
"""

from .claude_instance import ClaudeCodeInstance
from .config import Config
from .database import Database
from .orchestrator import Orchestrator
from .session import Session, SessionManager
from .utils import FileUtils, GitUtils
from .worktree import WorktreeManager

__version__ = "0.1.0"
__author__ = "samjtro"
__email__ = "hi@samjtro.com"

__all__ = [
    "ClaudeCodeInstance",
    "Config",
    "Database",
    "Orchestrator",
    "Session",
    "SessionManager",
    "GitUtils",
    "FileUtils",
    "WorktreeManager",
]
