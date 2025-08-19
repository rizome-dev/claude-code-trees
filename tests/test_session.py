"""Tests for session management."""

import asyncio
import datetime
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from claude_code_trees.claude_instance import ClaudeCodeInstance
from claude_code_trees.database import Database
from claude_code_trees.session import Session, SessionManager, Task, TaskResult


@pytest.fixture
def mock_database():
    """Mock Database for testing."""
    db = Mock(spec=Database)
    db.create_session.return_value = Mock()
    db.get_session_model.return_value = None
    db.update_session_status.return_value = True
    return db


@pytest.fixture
def session_manager(mock_database):
    """Create a SessionManager instance for testing."""
    return SessionManager(mock_database)


@pytest.fixture
def sample_session():
    """Create a sample session for testing."""
    now = datetime.datetime.utcnow()
    return Session(
        session_id="test-session-123",
        name="Test Session",
        description="A test session",
        created_at=now,
        updated_at=now
    )


@pytest.fixture
def sample_task():
    """Create a sample task for testing."""
    return Task(
        task_id="test-task-123",
        name="Test Task",
        description="A test task",
        created_at=datetime.datetime.utcnow()
    )


@pytest.fixture
def mock_claude_instance():
    """Mock ClaudeCodeInstance for testing."""
    instance = Mock(spec=ClaudeCodeInstance)
    instance.instance_id = "test-instance-123"
    instance.worktree = Mock()
    instance.worktree.name = "test-worktree"
    instance.run_task = AsyncMock()
    return instance


class TestTaskResult:
    """Test cases for TaskResult model."""

    def test_task_result_creation(self):
        """Test TaskResult creation with all fields."""
        result = TaskResult(
            task_id="test-task",
            success=True,
            output="Task completed successfully",
            execution_time=5.2,
            metadata={"instance_id": "test-instance"}
        )

        assert result.task_id == "test-task"
        assert result.success is True
        assert result.output == "Task completed successfully"
        assert result.execution_time == 5.2
        assert result.metadata["instance_id"] == "test-instance"

    def test_task_result_minimal(self):
        """Test TaskResult with minimal required fields."""
        result = TaskResult(
            task_id="test-task",
            success=False,
            error="Task failed"
        )

        assert result.task_id == "test-task"
        assert result.success is False
        assert result.error == "Task failed"
        assert result.output is None
        assert result.execution_time is None
        assert result.metadata == {}


class TestTask:
    """Test cases for Task model."""

    def test_task_creation(self, sample_task):
        """Test Task creation."""
        assert sample_task.task_id == "test-task-123"
        assert sample_task.name == "Test Task"
        assert sample_task.description == "A test task"
        assert sample_task.priority == 0
        assert sample_task.dependencies == []
        assert sample_task.context == {}
        assert sample_task.status == "pending"
        assert sample_task.assigned_instance is None
        assert sample_task.result is None

    def test_task_with_dependencies(self):
        """Test Task creation with dependencies."""
        task = Task(
            task_id="dependent-task",
            name="Dependent Task",
            description="Task with dependencies",
            dependencies=["task-1", "task-2"],
            priority=5,
            context={"key": "value"},
            created_at=datetime.datetime.utcnow()
        )

        assert task.dependencies == ["task-1", "task-2"]
        assert task.priority == 5
        assert task.context == {"key": "value"}


class TestSession:
    """Test cases for Session model."""

    def test_session_creation(self, sample_session):
        """Test Session creation."""
        assert sample_session.session_id == "test-session-123"
        assert sample_session.name == "Test Session"
        assert sample_session.description == "A test session"
        assert sample_session.status == "active"
        assert sample_session.tasks == {}
        assert sample_session.instances == {}
        assert sample_session.metadata == {}

    def test_session_json_serialization(self, sample_session):
        """Test Session JSON serialization."""
        json_str = sample_session.model_dump_json()
        data = json.loads(json_str)

        assert data["session_id"] == "test-session-123"
        assert data["name"] == "Test Session"
        assert data["status"] == "active"
        # DateTime should be serialized as ISO format
        assert "T" in data["created_at"]


class TestSessionManager:
    """Test cases for SessionManager."""

    def test_init(self, session_manager, mock_database):
        """Test SessionManager initialization."""
        assert session_manager.database == mock_database
        assert session_manager.active_sessions == {}
        assert session_manager._running_tasks == {}

    def test_create_session(self, session_manager):
        """Test session creation."""
        session = session_manager.create_session(
            name="Test Session",
            description="Test description",
            metadata={"key": "value"}
        )

        assert isinstance(session, Session)
        assert session.name == "Test Session"
        assert session.description == "Test description"
        assert session.metadata == {"key": "value"}
        assert session.status == "active"
        assert session.session_id.startswith("session-")

        # Verify it's in active sessions
        assert session.session_id in session_manager.active_sessions

        # Verify database was called
        session_manager.database.create_session.assert_called_once()

    def test_get_session_from_active(self, session_manager, sample_session):
        """Test getting session from active sessions."""
        session_manager.active_sessions[sample_session.session_id] = sample_session

        retrieved_session = session_manager.get_session(sample_session.session_id)

        assert retrieved_session == sample_session

    def test_get_session_from_database(self, session_manager):
        """Test getting session from database."""
        # Mock database response
        mock_session_model = Mock()
        mock_session_model.data_json = json.dumps({
            "session_id": "db-session-123",
            "name": "DB Session",
            "description": None,
            "status": "active",
            "tasks": {},
            "instances": {},
            "metadata": {},
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
            "completed_at": None
        })

        session_manager.database.get_session_model.return_value = mock_session_model

        session = session_manager.get_session("db-session-123")

        assert session is not None
        assert session.session_id == "db-session-123"
        assert session.name == "DB Session"

        # Should be added to active sessions
        assert "db-session-123" in session_manager.active_sessions

    def test_get_session_not_found(self, session_manager):
        """Test getting non-existent session."""
        session_manager.database.get_session_model.return_value = None

        session = session_manager.get_session("nonexistent")

        assert session is None

    def test_add_task(self, session_manager, sample_session):
        """Test adding task to session."""
        session_manager.active_sessions[sample_session.session_id] = sample_session

        with patch.object(session_manager, '_save_session') as mock_save:
            task = session_manager.add_task(
                session_id=sample_session.session_id,
                name="New Task",
                description="Task description",
                priority=5,
                dependencies=["dep-1"],
                context={"key": "value"}
            )

            assert task is not None
            assert task.name == "New Task"
            assert task.description == "Task description"
            assert task.priority == 5
            assert task.dependencies == ["dep-1"]
            assert task.context == {"key": "value"}

            # Verify task was added to session
            assert task.task_id in sample_session.tasks
            assert sample_session.tasks[task.task_id] == task

            # Verify session was saved
            mock_save.assert_called_once_with(sample_session)

    def test_add_task_session_not_found(self, session_manager):
        """Test adding task to non-existent session."""
        task = session_manager.add_task(
            session_id="nonexistent",
            name="Task",
            description="Description"
        )

        assert task is None

    def test_add_instance(self, session_manager, sample_session, mock_claude_instance):
        """Test adding Claude instance to session."""
        session_manager.active_sessions[sample_session.session_id] = sample_session

        with patch.object(session_manager, '_save_session') as mock_save:
            result = session_manager.add_instance(sample_session.session_id, mock_claude_instance)

            assert result is True
            assert mock_claude_instance.instance_id in sample_session.instances
            assert sample_session.instances[mock_claude_instance.instance_id] == "test-worktree"
            mock_save.assert_called_once()

    def test_add_instance_session_not_found(self, session_manager, mock_claude_instance):
        """Test adding instance to non-existent session."""
        result = session_manager.add_instance("nonexistent", mock_claude_instance)

        assert result is False


@pytest.mark.asyncio
class TestSessionManagerAsync:
    """Async test cases for SessionManager."""

    async def test_execute_session_success(self, session_manager, sample_session, mock_claude_instance):
        """Test successful session execution."""
        # Add tasks to session
        task1 = Task(
            task_id="task-1",
            name="Task 1",
            description="First task",
            created_at=datetime.datetime.utcnow()
        )
        task2 = Task(
            task_id="task-2",
            name="Task 2",
            description="Second task",
            dependencies=["task-1"],
            created_at=datetime.datetime.utcnow()
        )

        sample_session.tasks = {
            "task-1": task1,
            "task-2": task2
        }
        sample_session.instances = {mock_claude_instance.instance_id: "test-worktree"}

        session_manager.active_sessions[sample_session.session_id] = sample_session

        # Mock instance responses
        mock_claude_instance.run_task.return_value = {
            "success": True,
            "output": "Task completed"
        }

        with patch.object(session_manager, '_save_session') as mock_save:
            result = await session_manager.execute_session(
                sample_session.session_id,
                [mock_claude_instance],
                max_concurrent=1
            )

            assert result is True
            assert sample_session.status == "completed"
            assert sample_session.completed_at is not None

            # Verify tasks were executed
            assert task1.status == "completed"
            assert task2.status == "completed"
            assert task1.result is not None
            assert task2.result is not None

    async def test_execute_session_not_found(self, session_manager):
        """Test executing non-existent session."""
        result = await session_manager.execute_session("nonexistent", [])

        assert result is False

    async def test_execute_session_not_active(self, session_manager, sample_session):
        """Test executing non-active session."""
        sample_session.status = "completed"
        session_manager.active_sessions[sample_session.session_id] = sample_session

        result = await session_manager.execute_session(sample_session.session_id, [])

        assert result is False

    async def test_execute_single_task_success(self, session_manager, sample_task, mock_claude_instance):
        """Test successful single task execution."""
        # Mock instance response
        mock_claude_instance.run_task.return_value = {
            "success": True,
            "output": "Task completed successfully"
        }

        semaphore = asyncio.Semaphore(1)

        await session_manager._execute_single_task(sample_task, mock_claude_instance, semaphore)

        assert sample_task.status == "completed"
        assert sample_task.result is not None
        assert sample_task.result.success is True
        assert sample_task.result.output == "Task completed successfully"
        assert sample_task.completed_at is not None

        # Verify instance was called
        mock_claude_instance.run_task.assert_called_once_with(
            sample_task.description, sample_task.context
        )

    async def test_execute_single_task_failure(self, session_manager, sample_task, mock_claude_instance):
        """Test single task execution failure."""
        # Mock instance response
        mock_claude_instance.run_task.return_value = {
            "success": False,
            "error": "Task failed"
        }

        semaphore = asyncio.Semaphore(1)

        await session_manager._execute_single_task(sample_task, mock_claude_instance, semaphore)

        assert sample_task.status == "failed"
        assert sample_task.result is not None
        assert sample_task.result.success is False
        assert sample_task.result.error == "Task failed"

    async def test_execute_single_task_exception(self, session_manager, sample_task, mock_claude_instance):
        """Test single task execution with exception."""
        # Mock instance to raise exception
        mock_claude_instance.run_task.side_effect = Exception("Instance error")

        semaphore = asyncio.Semaphore(1)

        await session_manager._execute_single_task(sample_task, mock_claude_instance, semaphore)

        assert sample_task.status == "failed"
        assert sample_task.result is not None
        assert sample_task.result.success is False
        assert "Instance error" in sample_task.result.error

    def test_get_session_status(self, session_manager, sample_session):
        """Test getting session status."""
        # Add some tasks with different statuses
        tasks = {
            "task-1": Mock(status="completed"),
            "task-2": Mock(status="completed"),
            "task-3": Mock(status="failed"),
            "task-4": Mock(status="pending")
        }
        sample_session.tasks = tasks
        sample_session.instances = {"instance-1": "worktree-1"}

        session_manager.active_sessions[sample_session.session_id] = sample_session

        status = session_manager.get_session_status(sample_session.session_id)

        assert status is not None
        assert status["session_id"] == sample_session.session_id
        assert status["name"] == sample_session.name
        assert status["status"] == sample_session.status
        assert status["total_tasks"] == 4
        assert status["instances"] == 1
        assert status["task_counts"]["completed"] == 2
        assert status["task_counts"]["failed"] == 1
        assert status["task_counts"]["pending"] == 1
        assert status["task_counts"]["running"] == 0

    def test_get_session_status_not_found(self, session_manager):
        """Test getting status for non-existent session."""
        status = session_manager.get_session_status("nonexistent")

        assert status is None

    def test_pause_session(self, session_manager, sample_session):
        """Test pausing an active session."""
        session_manager.active_sessions[sample_session.session_id] = sample_session

        with patch.object(session_manager, '_save_session') as mock_save:
            result = session_manager.pause_session(sample_session.session_id)

            assert result is True
            assert sample_session.status == "paused"
            mock_save.assert_called_once()
            session_manager.database.update_session_status.assert_called_with(
                sample_session.session_id, "paused"
            )

    def test_pause_session_not_active(self, session_manager, sample_session):
        """Test pausing non-active session."""
        sample_session.status = "completed"
        session_manager.active_sessions[sample_session.session_id] = sample_session

        result = session_manager.pause_session(sample_session.session_id)

        assert result is False

    def test_resume_session(self, session_manager, sample_session):
        """Test resuming a paused session."""
        sample_session.status = "paused"
        session_manager.active_sessions[sample_session.session_id] = sample_session

        with patch.object(session_manager, '_save_session') as mock_save:
            result = session_manager.resume_session(sample_session.session_id)

            assert result is True
            assert sample_session.status == "active"
            mock_save.assert_called_once()

    def test_resume_session_not_paused(self, session_manager, sample_session):
        """Test resuming non-paused session."""
        result = session_manager.resume_session(sample_session.session_id)

        assert result is False

    def test_save_session_existing(self, session_manager, sample_session):
        """Test saving existing session."""
        mock_session_model = Mock()
        session_manager.database.get_session_model.return_value = mock_session_model

        session_manager._save_session(sample_session)

        assert mock_session_model.data_json == sample_session.model_dump_json()
        assert mock_session_model.updated_at == sample_session.updated_at

    def test_save_session_new(self, session_manager, sample_session):
        """Test saving new session."""
        session_manager.database.get_session_model.return_value = None

        session_manager._save_session(sample_session)

        session_manager.database.create_session.assert_called_with(
            session_id=sample_session.session_id,
            name=sample_session.name,
            description=sample_session.description,
            data=sample_session.model_dump_json()
        )
