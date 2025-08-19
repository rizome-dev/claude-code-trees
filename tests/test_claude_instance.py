"""Tests for Claude Code instance management."""

import asyncio
from unittest.mock import Mock, patch

import pytest

from claude_code_trees.claude_instance import (
    ClaudeCodeInstance,
    ClaudeInstanceConfig,
    InstanceStatus,
)
from claude_code_trees.database import Database
from claude_code_trees.worktree import Worktree


@pytest.fixture
def mock_worktree():
    """Mock Worktree for testing."""
    worktree = Mock(spec=Worktree)
    worktree.name = "test-worktree"
    worktree.path = "/test/path"
    worktree.exists = True
    worktree.is_git_repo = True
    worktree.current_branch = "test-branch"
    worktree.has_changes = False
    return worktree


@pytest.fixture
def mock_database():
    """Mock Database for testing."""
    db = Mock(spec=Database)
    db.create_claude_instance.return_value = Mock()
    db.update_claude_instance_status.return_value = True
    return db


@pytest.fixture
def instance_config():
    """Claude instance configuration for testing."""
    return ClaudeInstanceConfig(
        system_prompt="Test system prompt",
        max_turns=5,
        timeout=300,
        allowed_tools=["Read", "Write", "Bash"],
        permission_mode="acceptEdits"
    )


@pytest.fixture
def claude_instance(mock_worktree, instance_config, mock_database):
    """Create a ClaudeCodeInstance for testing."""
    return ClaudeCodeInstance(mock_worktree, instance_config, mock_database)


class TestClaudeInstanceConfig:
    """Test cases for ClaudeInstanceConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ClaudeInstanceConfig()
        assert config.system_prompt is None
        assert config.max_turns is None
        assert config.timeout == 300
        assert config.custom_instructions is None
        assert config.allowed_tools == ["Read", "Write", "Bash", "Edit", "Glob", "Grep"]
        assert config.permission_mode == "acceptEdits"
        assert config.environment == {}
        assert config.working_directory is None

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ClaudeInstanceConfig(
            system_prompt="Custom system prompt",
            max_turns=10,
            timeout=600,
            custom_instructions="Custom instructions",
            allowed_tools=["Read", "Write"],
            permission_mode="requireConfirm",
            environment={"KEY": "value"},
            working_directory="/custom/dir"
        )
        assert config.system_prompt == "Custom system prompt"
        assert config.max_turns == 10
        assert config.timeout == 600
        assert config.custom_instructions == "Custom instructions"
        assert config.allowed_tools == ["Read", "Write"]
        assert config.permission_mode == "requireConfirm"
        assert config.environment == {"KEY": "value"}
        assert config.working_directory == "/custom/dir"


class TestClaudeCodeInstance:
    """Test cases for ClaudeCodeInstance."""

    def test_init(self, claude_instance, mock_worktree, instance_config, mock_database):
        """Test initialization of Claude instance."""
        assert claude_instance.worktree == mock_worktree
        assert claude_instance.config == instance_config
        assert claude_instance.database == mock_database
        assert claude_instance.status == InstanceStatus.IDLE
        # Process is no longer tracked directly
        assert claude_instance.instance_id.startswith("claude-")

        # Verify database was called
        mock_database.create_claude_instance.assert_called_once()

    def test_is_running_idle(self, claude_instance):
        """Test is_running property when status is IDLE."""
        claude_instance.status = InstanceStatus.IDLE
        assert claude_instance.is_running is True

    def test_is_running_active(self, claude_instance):
        """Test is_running property when status is ACTIVE."""
        claude_instance.status = InstanceStatus.ACTIVE
        assert claude_instance.is_running is True

    def test_is_running_stopped(self, claude_instance):
        """Test is_running property when status is STOPPED."""
        claude_instance.status = InstanceStatus.STOPPED
        assert claude_instance.is_running is False

    def test_is_running_error(self, claude_instance):
        """Test is_running property when status is ERROR."""
        claude_instance.status = InstanceStatus.ERROR
        assert claude_instance.is_running is False

    def test_claude_options_property(self, claude_instance):
        """Test claude_options property."""
        options = claude_instance.claude_options
        assert options.system_prompt == "Test system prompt"
        assert options.max_turns == 5
        assert options.allowed_tools == ["Read", "Write", "Bash"]
        assert options.permission_mode == "acceptEdits"
        assert options.cwd == str(claude_instance.worktree.path)


@pytest.mark.asyncio
class TestClaudeCodeInstanceAsync:
    """Async test cases for ClaudeCodeInstance."""

    async def test_start_success(self, claude_instance):
        """Test successful instance start."""
        with patch.object(claude_instance, '_test_connection', return_value=True) as mock_test:
            result = await claude_instance.start()

            assert result is True
            assert claude_instance.status == InstanceStatus.ACTIVE
            mock_test.assert_called_once()

    async def test_start_connection_failed(self, claude_instance):
        """Test start when connection test fails."""
        with patch.object(claude_instance, '_test_connection', return_value=False) as mock_test:
            result = await claude_instance.start()

            assert result is False
            assert claude_instance.status == InstanceStatus.ERROR
            mock_test.assert_called_once()

    async def test_start_worktree_not_exists(self, claude_instance):
        """Test start when worktree doesn't exist."""
        claude_instance.worktree.exists = False

        with pytest.raises(ValueError, match="does not exist"):
            await claude_instance.start()

    async def test_start_exception(self, claude_instance):
        """Test start with connection exception."""
        with patch.object(claude_instance, '_test_connection', side_effect=Exception("Connection error")):
            result = await claude_instance.start()

            assert result is False
            assert claude_instance.status == InstanceStatus.ERROR

    async def test_stop_success(self, claude_instance):
        """Test successful instance stop."""
        result = await claude_instance.stop()

        assert result is True
        assert claude_instance.status == InstanceStatus.STOPPED

    async def test_stop_with_exception(self, claude_instance):
        """Test stop with exception during status update."""
        with patch.object(claude_instance, '_update_status', side_effect=Exception("Update error")):
            result = await claude_instance.stop()

            assert result is False

    async def test_execute_query_success(self, claude_instance):
        """Test successful query execution."""
        from claude_code_sdk import AssistantMessage, TextBlock

        # Mock the query function
        mock_message = Mock(spec=AssistantMessage)
        mock_text_block = Mock(spec=TextBlock)
        mock_text_block.text = "Test response"
        mock_message.content = [mock_text_block]

        async def mock_query(prompt, options):
            yield mock_message

        with patch.object(claude_instance, 'status', InstanceStatus.ACTIVE):
            with patch('claude_code_trees.claude_instance.query', side_effect=mock_query):
                with patch.object(claude_instance, '_update_status') as mock_update:
                    result = await claude_instance.execute_query("test prompt")

                    assert result["success"] is True
                    assert "Test response" in result["output"]
                    assert result["prompt"] == "test prompt"
                    assert len(result["messages"]) == 1
                    assert mock_update.call_count == 2  # BUSY -> ACTIVE

    async def test_execute_query_not_running(self, claude_instance):
        """Test query execution when instance not running."""
        with patch.object(claude_instance, 'start', return_value=False):
            result = await claude_instance.execute_query("test prompt")

            assert result["success"] is False
            assert "Working directory does not exist" in result["error"] or "Failed to initialize" in result["error"]

    async def test_execute_query_timeout(self, claude_instance):
        """Test query execution timeout."""
        async def timeout_query(prompt, options):
            await asyncio.sleep(10)  # Long delay
            yield Mock()

        with patch.object(claude_instance, 'status', InstanceStatus.ACTIVE):
            with patch('claude_code_trees.claude_instance.query', side_effect=timeout_query):
                with patch.object(claude_instance, '_update_status'):
                    result = await claude_instance.execute_query("test prompt", timeout=0.1)

                    assert result["success"] is False
                    assert "timed out" in result["error"]
                    assert claude_instance.status == InstanceStatus.ERROR

    async def test_run_task(self, claude_instance):
        """Test running a high-level task."""
        expected_result = {
            "success": True,
            "output": "task completed",
            "messages": [],
            "prompt": "Test task"
        }

        with patch.object(claude_instance, 'execute_query', return_value=expected_result) as mock_exec:
            result = await claude_instance.run_task("Test task")

            assert result == expected_result
            mock_exec.assert_called_once()
            # Check that the prompt contains the task description
            call_args = mock_exec.call_args[0][0]
            assert "Test task" in call_args

    async def test_run_task_with_context(self, claude_instance):
        """Test running task with context."""
        context = {"key": "value", "number": 42}

        with patch.object(claude_instance, 'execute_query', return_value={"success": True}) as mock_exec:
            await claude_instance.run_task("Test task", context)

            call_args = mock_exec.call_args[0][0]
            # Context should be included in the prompt
            assert "key: value" in call_args
            assert "number: 42" in call_args

    async def test_get_status_info(self, claude_instance):
        """Test getting status information."""
        claude_instance.last_activity = "2023-01-01T00:00:00"

        status_info = await claude_instance.get_status_info()

        assert status_info["instance_id"] == claude_instance.instance_id
        assert status_info["worktree"] == "test-worktree"
        assert status_info["status"] == InstanceStatus.IDLE.value
        assert status_info["is_running"] is True
        assert status_info["current_branch"] == "test-branch"
        assert status_info["has_changes"] is False

    async def test_health_check_healthy(self, claude_instance):
        """Test health check when instance is healthy."""
        claude_instance.status = InstanceStatus.ACTIVE
        health_info = await claude_instance.health_check()

        assert health_info["healthy"] is True
        assert len(health_info["issues"]) == 0
        assert health_info["instance_running"] is True
        assert health_info["worktree_exists"] is True
        assert health_info["worktree_is_git"] is True

    async def test_health_check_unhealthy(self, claude_instance):
        """Test health check when instance has issues."""
        claude_instance.worktree.exists = False
        claude_instance.worktree.is_git_repo = False
        claude_instance.status = InstanceStatus.STOPPED

        health_info = await claude_instance.health_check()

        assert health_info["healthy"] is False
        assert len(health_info["issues"]) == 3
        assert "Instance process not running" in health_info["issues"]
        assert "Worktree directory does not exist" in health_info["issues"]
        assert any("git repository" in issue for issue in health_info["issues"])

    async def test_update_status(self, claude_instance):
        """Test status update."""
        with patch('claude_code_trees.claude_instance.datetime') as mock_datetime:
            mock_now = Mock()
            mock_datetime.datetime.utcnow.return_value = mock_now

            await claude_instance._update_status()

            assert claude_instance.last_activity == mock_now
            claude_instance.database.update_claude_instance_status.assert_called_with(
                claude_instance.instance_id, InstanceStatus.IDLE.value
            )

    def test_str_representation(self, claude_instance):
        """Test string representation."""
        str_repr = str(claude_instance)
        assert claude_instance.instance_id in str_repr
        assert "test-worktree" in str_repr
        assert "idle" in str_repr

    def test_repr_representation(self, claude_instance):
        """Test detailed representation."""
        repr_str = repr(claude_instance)
        assert "ClaudeCodeInstance" in repr_str
        assert claude_instance.instance_id in repr_str
        assert "test-worktree" in repr_str

    async def test_test_connection_success(self, claude_instance):
        """Test successful connection test."""
        from claude_code_sdk import AssistantMessage, TextBlock

        mock_message = Mock(spec=AssistantMessage)
        mock_text_block = Mock(spec=TextBlock)
        mock_text_block.text = "Hello"
        mock_message.content = [mock_text_block]

        async def mock_query(prompt, options):
            yield mock_message

        with patch('claude_code_trees.claude_instance.query', side_effect=mock_query):
            result = await claude_instance._test_connection()
            assert result is True

    async def test_test_connection_failure(self, claude_instance):
        """Test failed connection test."""
        with patch('claude_code_trees.claude_instance.query', side_effect=Exception("Connection failed")):
            result = await claude_instance._test_connection()
            assert result is False

    def test_message_to_dict_text_block(self, claude_instance):
        """Test message to dict conversion with text block."""
        from claude_code_sdk import AssistantMessage, TextBlock

        mock_message = Mock(spec=AssistantMessage)
        mock_text_block = Mock(spec=TextBlock)
        mock_text_block.text = "Test response"
        mock_message.content = [mock_text_block]

        result = claude_instance._message_to_dict(mock_message)

        assert result["type"] == "Mock"  # Mock class name
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert result["content"][0]["text"] == "Test response"

    def test_del_cleanup(self, claude_instance):
        """Test cleanup on deletion."""
        # No process cleanup in new implementation
        claude_instance.__del__()
        # Should not raise any errors
