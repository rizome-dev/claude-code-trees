"""Session management and persistence for Claude Code Trees."""

import asyncio
import datetime
import json
import uuid
from typing import Any

from pydantic import BaseModel

from .claude_instance import ClaudeCodeInstance
from .database import Database


class TaskResult(BaseModel):
    """Result of a completed task."""
    task_id: str
    success: bool
    output: str | None = None
    error: str | None = None
    execution_time: float | None = None
    metadata: dict[str, Any] = {}


class Task(BaseModel):
    """Represents a task to be executed."""
    task_id: str
    name: str
    description: str
    priority: int = 0
    dependencies: list[str] = []
    context: dict[str, Any] = {}
    status: str = "pending"  # pending, running, completed, failed
    assigned_instance: str | None = None
    result: TaskResult | None = None
    created_at: datetime.datetime
    started_at: datetime.datetime | None = None
    completed_at: datetime.datetime | None = None


class Session(BaseModel):
    """Represents a session with multiple tasks and instances."""
    session_id: str
    name: str
    description: str | None = None
    status: str = "active"  # active, completed, failed, paused
    tasks: dict[str, Task] = {}
    instances: dict[str, str] = {}  # instance_id -> worktree_name
    metadata: dict[str, Any] = {}
    created_at: datetime.datetime
    updated_at: datetime.datetime
    completed_at: datetime.datetime | None = None

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime.datetime: lambda v: v.isoformat()
        }


class SessionManager:
    """Manager for sessions and their execution."""

    def __init__(self, database: Database | None = None):
        """Initialize session manager.
        
        Args:
            database: Database instance for persistence
        """
        self.database = database or Database()
        self.active_sessions: dict[str, Session] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}

    def create_session(self, name: str, description: str | None = None,
                      metadata: dict[str, Any] | None = None) -> Session:
        """Create a new session.
        
        Args:
            name: Session name
            description: Session description
            metadata: Additional metadata
            
        Returns:
            Created session
        """
        session_id = f"session-{uuid.uuid4().hex[:8]}"
        now = datetime.datetime.utcnow()

        session = Session(
            session_id=session_id,
            name=name,
            description=description,
            metadata=metadata or {},
            created_at=now,
            updated_at=now
        )

        # Save to database
        self.database.create_session(
            session_id=session_id,
            name=name,
            description=description,
            data=session.model_dump_json()
        )

        self.active_sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session if found, None otherwise
        """
        # Check active sessions first
        if session_id in self.active_sessions:
            return self.active_sessions[session_id]

        # Load from database
        session_model = self.database.get_session_model(session_id)
        if session_model and session_model.data_json:
            try:
                session_data = json.loads(session_model.data_json)
                session = Session(**session_data)
                self.active_sessions[session_id] = session
                return session
            except Exception:
                return None

        return None

    def add_task(self, session_id: str, name: str, description: str,
                priority: int = 0, dependencies: list[str] | None = None,
                context: dict[str, Any] | None = None) -> Task | None:
        """Add a task to a session.
        
        Args:
            session_id: Session ID
            name: Task name
            description: Task description
            priority: Task priority (higher = more important)
            dependencies: List of task IDs this task depends on
            context: Additional context for the task
            
        Returns:
            Created task or None if session not found
        """
        session = self.get_session(session_id)
        if not session:
            return None

        task_id = f"task-{uuid.uuid4().hex[:8]}"
        task = Task(
            task_id=task_id,
            name=name,
            description=description,
            priority=priority,
            dependencies=dependencies or [],
            context=context or {},
            created_at=datetime.datetime.utcnow()
        )

        session.tasks[task_id] = task
        session.updated_at = datetime.datetime.utcnow()

        # Save to database
        self._save_session(session)

        return task

    def add_instance(self, session_id: str, instance: ClaudeCodeInstance) -> bool:
        """Add a Claude instance to a session.
        
        Args:
            session_id: Session ID
            instance: Claude Code instance
            
        Returns:
            True if added successfully, False otherwise
        """
        session = self.get_session(session_id)
        if not session:
            return False

        session.instances[instance.instance_id] = instance.worktree.name
        session.updated_at = datetime.datetime.utcnow()

        # Save to database
        self._save_session(session)

        return True

    async def execute_session(self, session_id: str,
                            instances: list[ClaudeCodeInstance],
                            max_concurrent: int = 3) -> bool:
        """Execute all tasks in a session.
        
        Args:
            session_id: Session ID
            instances: Available Claude instances
            max_concurrent: Maximum concurrent tasks
            
        Returns:
            True if execution completed successfully, False otherwise
        """
        session = self.get_session(session_id)
        if not session:
            return False

        if session.status != "active":
            return False

        try:
            # Create a semaphore to limit concurrent tasks
            semaphore = asyncio.Semaphore(max_concurrent)

            # Execute tasks with dependency resolution
            await self._execute_tasks_with_dependencies(session, instances, semaphore)

            # Update session status
            session.status = "completed"
            session.completed_at = datetime.datetime.utcnow()
            session.updated_at = datetime.datetime.utcnow()

            self._save_session(session)
            self.database.update_session_status(session_id, "completed", session.completed_at)

            return True

        except Exception as e:
            session.status = "failed"
            session.updated_at = datetime.datetime.utcnow()
            session.metadata["error"] = str(e)

            self._save_session(session)
            self.database.update_session_status(session_id, "failed")

            return False

    async def _execute_tasks_with_dependencies(self, session: Session,
                                             instances: list[ClaudeCodeInstance],
                                             semaphore: asyncio.Semaphore) -> None:
        """Execute tasks respecting dependencies."""
        completed_tasks = set()
        running_tasks = {}

        while len(completed_tasks) < len(session.tasks):
            # Find tasks that can be started
            ready_tasks = []
            for task_id, task in session.tasks.items():
                if (task.status == "pending" and
                    task_id not in running_tasks and
                    task_id not in completed_tasks and
                    all(dep in completed_tasks for dep in task.dependencies)):
                    ready_tasks.append(task)

            # Sort by priority
            ready_tasks.sort(key=lambda t: t.priority, reverse=True)

            # Start tasks up to semaphore limit
            for task in ready_tasks:
                if len(running_tasks) >= semaphore._value:
                    break

                # Find available instance
                available_instance = None
                for instance in instances:
                    if not any(t.assigned_instance == instance.instance_id
                             for t in running_tasks.values()):
                        available_instance = instance
                        break

                if available_instance:
                    task.assigned_instance = available_instance.instance_id
                    task.status = "running"
                    task.started_at = datetime.datetime.utcnow()

                    # Start task execution
                    task_coro = self._execute_single_task(task, available_instance, semaphore)
                    running_task = asyncio.create_task(task_coro)
                    running_tasks[task.task_id] = task
                    self._running_tasks[task.task_id] = running_task

            # Wait for at least one task to complete
            if running_tasks:
                done_task_ids = []
                for task_id, running_task in self._running_tasks.items():
                    if running_task.done():
                        done_task_ids.append(task_id)

                # Clean up completed tasks
                for task_id in done_task_ids:
                    del self._running_tasks[task_id]
                    if task_id in running_tasks:
                        completed_tasks.add(task_id)
                        del running_tasks[task_id]

                # If no tasks completed, wait a bit
                if not done_task_ids:
                    await asyncio.sleep(0.1)
            else:
                # No tasks to run, wait a bit
                await asyncio.sleep(0.1)

    async def _execute_single_task(self, task: Task, instance: ClaudeCodeInstance,
                                 semaphore: asyncio.Semaphore) -> None:
        """Execute a single task."""
        async with semaphore:
            start_time = datetime.datetime.utcnow()

            try:
                # Execute the task
                result = await instance.run_task(task.description, task.context)

                # Create task result
                execution_time = (datetime.datetime.utcnow() - start_time).total_seconds()
                task_result = TaskResult(
                    task_id=task.task_id,
                    success=result.get("success", False),
                    output=result.get("output"),
                    error=result.get("error"),
                    execution_time=execution_time,
                    metadata={"instance_id": instance.instance_id}
                )

                # Update task
                task.result = task_result
                task.status = "completed" if task_result.success else "failed"
                task.completed_at = datetime.datetime.utcnow()

            except Exception as e:
                # Handle execution error
                execution_time = (datetime.datetime.utcnow() - start_time).total_seconds()
                task_result = TaskResult(
                    task_id=task.task_id,
                    success=False,
                    error=str(e),
                    execution_time=execution_time,
                    metadata={"instance_id": instance.instance_id}
                )

                task.result = task_result
                task.status = "failed"
                task.completed_at = datetime.datetime.utcnow()

    def get_session_status(self, session_id: str) -> dict[str, Any] | None:
        """Get detailed status of a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Status information or None if session not found
        """
        session = self.get_session(session_id)
        if not session:
            return None

        task_counts = {"pending": 0, "running": 0, "completed": 0, "failed": 0}
        for task in session.tasks.values():
            task_counts[task.status] += 1

        return {
            "session_id": session_id,
            "name": session.name,
            "status": session.status,
            "task_counts": task_counts,
            "total_tasks": len(session.tasks),
            "instances": len(session.instances),
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "completed_at": session.completed_at,
            "metadata": session.metadata
        }

    def pause_session(self, session_id: str) -> bool:
        """Pause a running session."""
        session = self.get_session(session_id)
        if not session or session.status != "active":
            return False

        session.status = "paused"
        session.updated_at = datetime.datetime.utcnow()

        self._save_session(session)
        self.database.update_session_status(session_id, "paused")

        return True

    def resume_session(self, session_id: str) -> bool:
        """Resume a paused session."""
        session = self.get_session(session_id)
        if not session or session.status != "paused":
            return False

        session.status = "active"
        session.updated_at = datetime.datetime.utcnow()

        self._save_session(session)
        self.database.update_session_status(session_id, "active")

        return True

    def _save_session(self, session: Session) -> None:
        """Save session to database."""
        session_model = self.database.get_session_model(session.session_id)
        if session_model:
            # Update existing session
            session_model.data_json = session.model_dump_json()
            session_model.updated_at = session.updated_at
            # Note: This is simplified - in practice you'd use proper session management
        else:
            # Create new session record
            self.database.create_session(
                session_id=session.session_id,
                name=session.name,
                description=session.description,
                data=session.model_dump_json()
            )
