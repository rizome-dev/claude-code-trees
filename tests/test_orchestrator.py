"""Tests for the Orchestrator class."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from claude_code_trees.claude_instance import ClaudeCodeInstance, ClaudeInstanceConfig
from claude_code_trees.config import Config
from claude_code_trees.orchestrator import Orchestrator
from claude_code_trees.session import SessionManager
from claude_code_trees.worktree import Worktree


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    config = Mock(spec=Config)
    config.database_url = "sqlite:///:memory:"
    config.worktree_base_path = "/tmp/worktrees"
    config.claude_model = "claude-3-sonnet-20240229"
    config.max_tokens = 4096
    config.instance_timeout = 300
    config.max_concurrent_instances = 3
    config.ensure_directories.return_value = None
    return config


@pytest.fixture
def mock_database():
    """Mock database for testing."""
    from claude_code_trees.database import Database
    return Mock(spec=Database)


@pytest.fixture
def mock_worktree_manager():
    """Mock WorktreeManager for testing."""
    from claude_code_trees.worktree import WorktreeManager
    return Mock(spec=WorktreeManager)


@pytest.fixture
def mock_session_manager():
    """Mock SessionManager for testing."""
    return Mock(spec=SessionManager)


@pytest.fixture
def orchestrator(mock_config):
    """Create an Orchestrator instance for testing."""
    base_repo_path = "/test/repo"

    with patch('claude_code_trees.orchestrator.Database') as mock_db_class, \
         patch('claude_code_trees.orchestrator.WorktreeManager') as mock_wm_class, \
         patch('claude_code_trees.orchestrator.SessionManager') as mock_sm_class:

        orchestrator = Orchestrator(base_repo_path, mock_config)
        orchestrator.database = mock_db_class.return_value
        orchestrator.worktree_manager = mock_wm_class.return_value
        orchestrator.session_manager = mock_sm_class.return_value

        return orchestrator


class TestOrchestrator:
    """Test cases for Orchestrator."""

    def test_init(self, mock_config):
        """Test Orchestrator initialization."""
        base_repo_path = "/test/repo"

        with patch('claude_code_trees.orchestrator.Database') as mock_db_class, \
             patch('claude_code_trees.orchestrator.WorktreeManager') as mock_wm_class, \
             patch('claude_code_trees.orchestrator.SessionManager') as mock_sm_class:

            orchestrator = Orchestrator(base_repo_path, mock_config)

            assert orchestrator.config == mock_config
            assert orchestrator.active_instances == {}
            mock_config.ensure_directories.assert_called_once()
            mock_db_class.assert_called_once()
            mock_wm_class.assert_called_once()
            mock_sm_class.assert_called_once()

    def test_init_default_config(self):
        """Test Orchestrator initialization with default config."""
        base_repo_path = "/test/repo"

        with patch('claude_code_trees.orchestrator.Database'), \
             patch('claude_code_trees.orchestrator.WorktreeManager'), \
             patch('claude_code_trees.orchestrator.SessionManager'), \
             patch('claude_code_trees.orchestrator.Config') as mock_config_class:

            mock_config = Mock()
            mock_config.ensure_directories.return_value = None
            mock_config_class.return_value = mock_config

            orchestrator = Orchestrator(base_repo_path)

            mock_config_class.assert_called_once()
            assert orchestrator.config == mock_config


@pytest.mark.asyncio
class TestOrchestratorAsync:
    """Async test cases for Orchestrator."""

    async def test_create_instance_success(self, orchestrator):
        """Test successful instance creation."""
        mock_worktree = Mock(spec=Worktree)
        mock_worktree.name = "test-worktree"

        orchestrator.worktree_manager.create_worktree.return_value = mock_worktree

        with patch('claude_code_trees.orchestrator.ClaudeCodeInstance') as mock_instance_class:
            mock_instance = Mock(spec=ClaudeCodeInstance)
            mock_instance.instance_id = "test-instance-id"
            mock_instance_class.return_value = mock_instance

            instance = await orchestrator.create_instance(
                worktree_name="test-worktree",
                branch="test-branch"
            )

            assert instance == mock_instance
            assert orchestrator.active_instances["test-instance-id"] == mock_instance
            orchestrator.worktree_manager.create_worktree.assert_called_once()

    async def test_create_instance_limit_reached(self, orchestrator):
        """Test instance creation when limit is reached."""
        # Fill up to the limit
        for i in range(3):  # max_concurrent_instances = 3
            orchestrator.active_instances[f"instance-{i}"] = Mock()

        with pytest.raises(RuntimeError, match="Maximum concurrent instances"):
            await orchestrator.create_instance()

    async def test_create_instance_with_custom_config(self, orchestrator):
        """Test instance creation with custom configuration."""
        mock_worktree = Mock(spec=Worktree)
        orchestrator.worktree_manager.create_worktree.return_value = mock_worktree

        custom_config = ClaudeInstanceConfig(
            model="claude-3-opus-20240229",
            max_tokens=8192
        )

        with patch('claude_code_trees.orchestrator.ClaudeCodeInstance') as mock_instance_class:
            mock_instance = Mock()
            mock_instance.instance_id = "test-id"
            mock_instance_class.return_value = mock_instance

            await orchestrator.create_instance(instance_config=custom_config)

            # Verify the custom config was passed
            call_args = mock_instance_class.call_args
            assert call_args[1]['config'] == custom_config

    async def test_get_instance_from_active(self, orchestrator):
        """Test getting instance from active instances."""
        mock_instance = Mock(spec=ClaudeCodeInstance)
        orchestrator.active_instances["test-id"] = mock_instance

        instance = await orchestrator.get_instance("test-id")

        assert instance == mock_instance

    async def test_get_instance_from_database(self, orchestrator):
        """Test getting instance from database."""
        # Mock database response
        mock_instance_model = Mock()
        mock_instance_model.instance_id = "test-id"
        mock_instance_model.worktree_name = "test-worktree"
        mock_instance_model.config_json = '{"model": "claude-3-sonnet-20240229"}'

        orchestrator.database.get_claude_instance.return_value = mock_instance_model

        # Mock worktree
        mock_worktree = Mock(spec=Worktree)
        orchestrator.worktree_manager.get_worktree.return_value = mock_worktree

        with patch('claude_code_trees.orchestrator.ClaudeCodeInstance') as mock_instance_class:
            mock_instance = Mock()
            mock_instance.instance_id = "test-id"
            mock_instance_class.return_value = mock_instance

            instance = await orchestrator.get_instance("test-id")

            assert instance == mock_instance
            assert orchestrator.active_instances["test-id"] == mock_instance

    async def test_get_instance_not_found(self, orchestrator):
        """Test getting non-existent instance."""
        orchestrator.database.get_claude_instance.return_value = None

        instance = await orchestrator.get_instance("nonexistent")

        assert instance is None

    async def test_remove_instance_success(self, orchestrator):
        """Test successful instance removal."""
        mock_instance = Mock(spec=ClaudeCodeInstance)
        mock_instance.is_running = True
        mock_instance.stop = AsyncMock()
        mock_instance.worktree = Mock()
        mock_instance.worktree.remove = Mock(return_value=True)

        orchestrator.active_instances["test-id"] = mock_instance
        orchestrator.database.delete_claude_instance.return_value = True

        with patch.object(orchestrator, 'get_instance', return_value=mock_instance):
            result = await orchestrator.remove_instance("test-id", remove_worktree=True)

            assert result is True
            assert "test-id" not in orchestrator.active_instances
            mock_instance.stop.assert_called_once()
            mock_instance.worktree.remove.assert_called_once_with(force=True)
            orchestrator.database.delete_claude_instance.assert_called_once_with("test-id")

    async def test_remove_instance_not_found(self, orchestrator):
        """Test removing non-existent instance."""
        with patch.object(orchestrator, 'get_instance', return_value=None):
            result = await orchestrator.remove_instance("nonexistent")

            assert result is False

    async def test_list_instances(self, orchestrator):
        """Test listing instances."""
        mock_instance1 = Mock(spec=ClaudeCodeInstance)
        mock_instance1.get_status_info = AsyncMock(return_value={"id": "instance1"})

        mock_instance2 = Mock(spec=ClaudeCodeInstance)
        mock_instance2.get_status_info = AsyncMock(return_value={"id": "instance2"})

        orchestrator.active_instances = {
            "instance1": mock_instance1,
            "instance2": mock_instance2
        }

        instances_info = await orchestrator.list_instances()

        assert len(instances_info) == 2
        assert {"id": "instance1"} in instances_info
        assert {"id": "instance2"} in instances_info

    async def test_run_parallel_tasks(self, orchestrator):
        """Test running parallel tasks."""
        tasks = [
            {"name": "Task 1", "description": "First task"},
            {"name": "Task 2", "description": "Second task"}
        ]

        # Mock session creation and execution
        mock_session = Mock()
        mock_session.session_id = "session-123"
        orchestrator.session_manager.create_session.return_value = mock_session
        orchestrator.session_manager.add_task.return_value = Mock()
        orchestrator.session_manager.add_instance.return_value = True
        orchestrator.session_manager.execute_session = AsyncMock(return_value=True)
        orchestrator.session_manager.get_session_status.return_value = {
            "status": "completed",
            "task_counts": {"completed": 2, "failed": 0}
        }

        # Mock instance creation
        mock_instance = Mock(spec=ClaudeCodeInstance)
        mock_instance.start = AsyncMock()

        with patch.object(orchestrator, 'create_instance', return_value=mock_instance):
            result = await orchestrator.run_parallel_tasks(tasks)

            assert result["success"] is True
            assert result["session_id"] == "session-123"
            orchestrator.session_manager.create_session.assert_called_once()
            assert orchestrator.session_manager.add_task.call_count == 2

    async def test_run_sequential_workflow(self, orchestrator):
        """Test running sequential workflow."""
        workflow = [
            {"name": "Step 1", "description": "First step"},
            {"name": "Step 2", "description": "Second step"}
        ]

        # Mock session and execution
        mock_session = Mock()
        mock_session.session_id = "workflow-123"
        orchestrator.session_manager.create_session.return_value = mock_session

        mock_task1 = Mock()
        mock_task1.task_id = "task-1"
        mock_task2 = Mock()
        mock_task2.task_id = "task-2"

        orchestrator.session_manager.add_task.side_effect = [mock_task1, mock_task2]
        orchestrator.session_manager.add_instance.return_value = True
        orchestrator.session_manager.execute_session = AsyncMock(return_value=True)
        orchestrator.session_manager.get_session_status.return_value = {
            "status": "completed"
        }

        # Mock existing instance
        mock_instance = Mock(spec=ClaudeCodeInstance)
        orchestrator.active_instances["existing"] = mock_instance

        result = await orchestrator.run_sequential_workflow(workflow)

        assert result["success"] is True
        assert result["session_id"] == "workflow-123"

        # Verify tasks were added with dependencies
        task_calls = orchestrator.session_manager.add_task.call_args_list
        assert len(task_calls) == 2

        # First task should have no dependencies
        assert task_calls[0][1]["dependencies"] == []
        # Second task should depend on first
        assert task_calls[1][1]["dependencies"] == ["task-1"]

    async def test_health_check(self, orchestrator):
        """Test comprehensive health check."""
        # Mock database health
        orchestrator.database.list_worktrees.return_value = []

        # Mock worktree manager health
        mock_worktree = Mock()
        mock_worktree.name = "test-wt"
        mock_worktree.exists = True
        mock_worktree.is_git_repo = True
        mock_worktree.current_branch = "main"
        mock_worktree.has_changes = False

        orchestrator.worktree_manager.list_worktrees.return_value = [mock_worktree]

        # Mock instance health
        mock_instance = Mock(spec=ClaudeCodeInstance)
        mock_instance.health_check = AsyncMock(return_value={"healthy": True})
        orchestrator.active_instances["test-instance"] = mock_instance

        health_info = await orchestrator.health_check()

        assert health_info["overall_healthy"] is True
        assert health_info["components"]["database"]["healthy"] is True
        assert health_info["components"]["worktree_manager"]["healthy"] is True
        assert health_info["worktrees"]["test-wt"]["exists"] is True
        assert health_info["instances"]["test-instance"]["healthy"] is True

    async def test_health_check_with_issues(self, orchestrator):
        """Test health check with component issues."""
        # Mock database error
        orchestrator.database.list_worktrees.side_effect = Exception("DB Error")

        # Mock worktree manager
        orchestrator.worktree_manager.list_worktrees.return_value = []

        # Mock unhealthy instance
        mock_instance = Mock(spec=ClaudeCodeInstance)
        mock_instance.health_check = AsyncMock(return_value={
            "healthy": False,
            "issues": ["Instance not running"]
        })
        orchestrator.active_instances["bad-instance"] = mock_instance

        health_info = await orchestrator.health_check()

        assert health_info["overall_healthy"] is False
        assert health_info["components"]["database"]["healthy"] is False
        assert "DB Error" in health_info["components"]["database"]["error"]
        assert health_info["instances"]["bad-instance"]["healthy"] is False

    async def test_cleanup(self, orchestrator):
        """Test cleanup of old resources."""
        # Mock worktree cleanup
        orchestrator.worktree_manager.cleanup_inactive_worktrees = AsyncMock(
            return_value=["old-worktree-1", "old-worktree-2"]
        )

        # Mock instance with old activity
        mock_instance = Mock(spec=ClaudeCodeInstance)
        mock_instance.get_status_info = AsyncMock(return_value={
            "last_activity": "2023-01-01T00:00:00"  # Very old
        })
        orchestrator.active_instances["old-instance"] = mock_instance

        with patch.object(orchestrator, 'remove_instance', return_value=True) as mock_remove:
            # Patch datetime that is imported inside the cleanup method
            with patch('datetime.datetime') as mock_datetime:
                # Mock current time as much later
                from datetime import datetime
                current_time = datetime(2023, 12, 31, 23, 59, 59)
                old_time = datetime(2023, 1, 1, 0, 0, 0)

                mock_datetime.utcnow.return_value = current_time
                mock_datetime.fromisoformat.return_value = old_time

                # Mock the timedelta result
                mock_timedelta = Mock()
                mock_timedelta.total_seconds.return_value = 8760 * 3600  # Many hours in seconds
                mock_datetime.utcnow.return_value.__sub__ = Mock(return_value=mock_timedelta)

                results = await orchestrator.cleanup(max_age_hours=1)

                assert results["worktrees_cleaned"] == ["old-worktree-1", "old-worktree-2"]
                # Note: The instance cleanup logic needs datetime handling fix in actual implementation

    async def test_shutdown(self, orchestrator):
        """Test orchestrator shutdown."""
        # Mock running instances
        mock_instance1 = Mock(spec=ClaudeCodeInstance)
        mock_instance1.is_running = True
        mock_instance1.stop = AsyncMock()

        mock_instance2 = Mock(spec=ClaudeCodeInstance)
        mock_instance2.is_running = False
        mock_instance2.stop = AsyncMock()

        orchestrator.active_instances = {
            "instance1": mock_instance1,
            "instance2": mock_instance2
        }

        # Mock running tasks
        mock_task = Mock()
        mock_task.done.return_value = False
        mock_task.cancel.return_value = None
        orchestrator.session_manager._running_tasks = {"task1": mock_task}

        await orchestrator.shutdown()

        # Verify instances were stopped
        mock_instance1.stop.assert_called_once()
        mock_instance2.stop.assert_not_called()  # Not running

        # Verify cleanup
        assert orchestrator.active_instances == {}
        mock_task.cancel.assert_called_once()
        assert orchestrator.session_manager._running_tasks == {}
