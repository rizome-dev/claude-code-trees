"""Claude Code instance wrapper for managing individual instances."""

import asyncio
import datetime
import logging
import uuid
from enum import Enum
from typing import Any

from claude_code_sdk import (
    AssistantMessage,
    ClaudeCodeOptions,
    CLIConnectionError,
    CLIJSONDecodeError,
    CLINotFoundError,
    ProcessError,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    query,
)
from pydantic import BaseModel

from .database import Database
from .worktree import Worktree

# Set up logger
logger = logging.getLogger(__name__)


class InstanceStatus(str, Enum):
    """Status enum for Claude Code instances."""
    IDLE = "idle"
    ACTIVE = "active"
    BUSY = "busy"
    STOPPED = "stopped"
    ERROR = "error"


class ClaudeInstanceConfig(BaseModel):
    """Configuration for a Claude Code instance."""
    system_prompt: str | None = None
    max_turns: int | None = None
    timeout: int = 300  # seconds
    custom_instructions: str | None = None
    allowed_tools: list[str] = ["Read", "Write", "Bash", "Edit", "Glob", "Grep"]
    permission_mode: str = "acceptEdits"  # auto-accept file edits
    environment: dict[str, str] = {}
    working_directory: str | None = None


class ClaudeCodeInstance:
    """Wrapper for a Claude Code instance running in a specific worktree."""

    def __init__(self,
                 worktree: Worktree,
                 config: ClaudeInstanceConfig | None = None,
                 database: Database | None = None):
        """Initialize Claude Code instance.
        
        Args:
            worktree: Worktree where this instance will operate
            config: Configuration for the instance
            database: Database instance for persistence
        """
        self.worktree = worktree
        self.config = config or ClaudeInstanceConfig()
        self.database = database or Database()
        self.instance_id = f"claude-{uuid.uuid4().hex[:8]}"
        self.status = InstanceStatus.IDLE
        self.last_activity = None
        self._claude_options: ClaudeCodeOptions | None = None

        # Create database record
        self.database.create_claude_instance(
            instance_id=self.instance_id,
            worktree_name=self.worktree.name,
            status=self.status.value,
            config=self.config.model_dump_json()
        )

    @property
    def is_running(self) -> bool:
        """Check if the instance is available for queries."""
        return self.status in [InstanceStatus.IDLE, InstanceStatus.ACTIVE]

    @property
    def claude_options(self) -> ClaudeCodeOptions:
        """Get Claude Code options for this instance."""
        if not self._claude_options:
            self._claude_options = ClaudeCodeOptions(
                system_prompt=self.config.system_prompt or self.config.custom_instructions,
                max_turns=self.config.max_turns,
                allowed_tools=self.config.allowed_tools,
                permission_mode=self.config.permission_mode,
                cwd=self.config.working_directory or str(self.worktree.path)
            )
        return self._claude_options

    async def start(self) -> bool:
        """Initialize the Claude Code instance.
        
        Returns:
            True if initialized successfully, False otherwise
        """
        if not self.worktree.exists:
            raise ValueError(f"Worktree {self.worktree.name} does not exist")

        try:
            # Test the connection by doing a simple query
            test_result = await self._test_connection()
            if test_result:
                self.status = InstanceStatus.ACTIVE
                await self._update_status()
                return True
            else:
                self.status = InstanceStatus.ERROR
                await self._update_status()
                return False

        except Exception:
            self.status = InstanceStatus.ERROR
            await self._update_status()
            return False

    async def stop(self) -> bool:
        """Stop the Claude Code instance.
        
        Returns:
            True if stopped successfully, False otherwise
        """
        try:
            self.status = InstanceStatus.STOPPED
            await self._update_status()
            return True
        except Exception:
            return False

    async def execute_query(self, prompt: str, timeout: int | None = None, max_retries: int = 3) -> dict[str, Any]:
        """Execute a query using Claude Code SDK with retry logic.
        
        Args:
            prompt: Prompt to send to Claude
            timeout: Timeout in seconds (uses instance config if None)
            max_retries: Maximum number of retry attempts for transient failures
            
        Returns:
            Dictionary with execution results
        """
        logger.info(f"Executing query for instance {self.instance_id}")

        if not self.is_running:
            logger.info(f"Instance {self.instance_id} not running, attempting to start")
            await self.start()

        if not self.is_running:
            logger.error(f"Failed to start instance {self.instance_id}")
            return {
                "success": False,
                "error": "Failed to initialize Claude instance",
                "output": "",
                "messages": []
            }

        timeout = timeout or self.config.timeout
        self.status = InstanceStatus.BUSY
        await self._update_status()

        # Retry logic for transient failures
        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"Query attempt {attempt + 1}/{max_retries + 1} for instance {self.instance_id}")
                messages = []
                output_parts = []

                # Execute the query with timeout
                async def _query_with_timeout():
                    async for message in query(prompt=prompt, options=self.claude_options):
                        messages.append(message)

                        if isinstance(message, AssistantMessage):
                            for block in message.content:
                                if isinstance(block, TextBlock):
                                    output_parts.append(block.text)
                                elif isinstance(block, ToolUseBlock):
                                    # Log tool usage
                                    logger.debug(f"Tool used: {block.name}")
                                    output_parts.append(f"[Tool used: {block.name}]")
                        elif isinstance(message, ResultMessage):
                            # Process tool results
                            if hasattr(message, 'content'):
                                for block in message.content:
                                    if isinstance(block, ToolResultBlock):
                                        if block.content:
                                            output_parts.append(f"[Tool result: {block.content[:100]}...]")

                await asyncio.wait_for(_query_with_timeout(), timeout=timeout)

                self.status = InstanceStatus.ACTIVE
                await self._update_status()
                logger.info(f"Query completed successfully for instance {self.instance_id}")

                return {
                    "success": True,
                    "output": "\n".join(output_parts),
                    "messages": [self._message_to_dict(msg) for msg in messages],
                    "prompt": prompt
                }

            except asyncio.TimeoutError:
                logger.warning(f"Query timeout for instance {self.instance_id} (attempt {attempt + 1})")
                if attempt == max_retries:  # Last attempt
                    self.status = InstanceStatus.ERROR
                    await self._update_status()
                    return {
                        "success": False,
                        "error": "Query timed out after multiple attempts",
                        "output": "",
                        "messages": [],
                        "prompt": prompt
                    }
                # Wait before retrying
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue

            except CLINotFoundError as e:
                logger.error(f"Claude Code CLI not found for instance {self.instance_id}: {e}")
                self.status = InstanceStatus.ERROR
                await self._update_status()
                return {
                    "success": False,
                    "error": "Claude Code CLI not found. Please install claude-code-sdk with: pip install claude-code-sdk",
                    "output": "",
                    "messages": [],
                    "prompt": prompt
                }

            except (CLIConnectionError, ProcessError) as e:
                logger.warning(f"Transient error for instance {self.instance_id} (attempt {attempt + 1}): {e}")
                if attempt == max_retries:  # Last attempt
                    self.status = InstanceStatus.ERROR
                    await self._update_status()
                    return {
                        "success": False,
                        "error": f"Claude Code SDK error after {max_retries + 1} attempts: {str(e)}",
                        "output": "",
                        "messages": [],
                        "prompt": prompt
                    }
                # Wait before retrying
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue

            except CLIJSONDecodeError as e:
                logger.error(f"JSON decode error for instance {self.instance_id}: {e}")
                self.status = InstanceStatus.ERROR
                await self._update_status()
                return {
                    "success": False,
                    "error": f"Claude Code SDK JSON error: {str(e)}",
                    "output": "",
                    "messages": [],
                    "prompt": prompt
                }

            except Exception as e:
                logger.error(f"Unexpected error for instance {self.instance_id} (attempt {attempt + 1}): {e}")
                if attempt == max_retries:  # Last attempt
                    self.status = InstanceStatus.ERROR
                    await self._update_status()
                    return {
                        "success": False,
                        "error": f"Unexpected error after {max_retries + 1} attempts: {str(e)}",
                        "output": "",
                        "messages": [],
                        "prompt": prompt
                    }
                # Wait before retrying
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue

        # This should never be reached due to the loop structure, but just in case
        self.status = InstanceStatus.ERROR
        await self._update_status()
        return {
            "success": False,
            "error": "Unexpected termination of retry loop",
            "output": "",
            "messages": [],
            "prompt": prompt
        }

    async def run_task(self, task_description: str,
                      context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run a high-level task using Claude Code.
        
        Args:
            task_description: Description of the task to perform
            context: Additional context for the task
            
        Returns:
            Dictionary with task results
        """
        # Construct prompt with task description and context
        prompt_parts = [task_description]

        if context:
            prompt_parts.append("\nAdditional context:")
            for key, value in context.items():
                prompt_parts.append(f"- {key}: {value}")

        prompt = "\n".join(prompt_parts)
        return await self.execute_query(prompt)

    async def get_status_info(self) -> dict[str, Any]:
        """Get detailed status information about the instance.
        
        Returns:
            Dictionary with status information
        """
        return {
            "instance_id": self.instance_id,
            "worktree": self.worktree.name,
            "status": self.status.value,
            "is_running": self.is_running,
            "worktree_path": str(self.worktree.path),
            "current_branch": self.worktree.current_branch,
            "has_changes": self.worktree.has_changes,
            "last_activity": self.last_activity,
            "config": self.config.model_dump()
        }

    async def health_check(self) -> dict[str, Any]:
        """Perform a health check on the instance.
        
        Returns:
            Dictionary with health status
        """
        health_info = {
            "healthy": True,
            "issues": [],
            "instance_running": self.is_running,
            "worktree_exists": self.worktree.exists,
            "worktree_is_git": self.worktree.is_git_repo
        }

        if not self.is_running:
            health_info["healthy"] = False
            health_info["issues"].append("Instance process not running")

        if not self.worktree.exists:
            health_info["healthy"] = False
            health_info["issues"].append("Worktree directory does not exist")

        if not self.worktree.is_git_repo:
            health_info["healthy"] = False
            health_info["issues"].append("Worktree is not a valid git repository")

        return health_info

    async def _test_connection(self) -> bool:
        """Test the Claude Code connection."""
        try:
            messages = []
            async for message in query(prompt="Hello", options=self.claude_options):
                messages.append(message)
                # Just need one response to confirm it works
                if isinstance(message, AssistantMessage):
                    return True
            return len(messages) > 0
        except Exception:
            return False

    def _message_to_dict(self, message: Any) -> dict[str, Any]:
        """Convert a Claude SDK message to a dictionary."""
        message_dict = {
            "type": type(message).__name__,
            "content": []
        }

        if hasattr(message, 'content'):
            for block in message.content:
                if isinstance(block, TextBlock):
                    message_dict["content"].append({
                        "type": "text",
                        "text": block.text
                    })
                elif isinstance(block, ToolUseBlock):
                    message_dict["content"].append({
                        "type": "tool_use",
                        "name": block.name,
                        "input": getattr(block, 'input', {})
                    })
                elif isinstance(block, ToolResultBlock):
                    message_dict["content"].append({
                        "type": "tool_result",
                        "content": getattr(block, 'content', ''),
                        "is_error": getattr(block, 'is_error', False)
                    })

        return message_dict

    async def _update_status(self) -> None:
        """Update status in database."""
        self.last_activity = datetime.datetime.utcnow()
        self.database.update_claude_instance_status(self.instance_id, self.status.value)

    def __del__(self):
        """Cleanup when instance is destroyed."""
        # No process cleanup needed for SDK-based implementation
        pass

    def __str__(self) -> str:
        """String representation of instance."""
        return f"ClaudeCodeInstance(id={self.instance_id}, worktree={self.worktree.name}, status={self.status.value})"

    def __repr__(self) -> str:
        """Detailed string representation of instance."""
        return (f"ClaudeCodeInstance(instance_id='{self.instance_id}', "
                f"worktree='{self.worktree.name}', status='{self.status.value}', "
                f"running={self.is_running})")
