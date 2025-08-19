"""Orchestrator for managing multiple Claude Code instances and worktrees."""

import asyncio
import logging

from .claude_instance import ClaudeCodeInstance, ClaudeInstanceConfig
from .config import Config
from .database import Database
from .session import SessionManager
from .worktree import WorktreeManager

# Set up logger
logger = logging.getLogger(__name__)


class Orchestrator:
    """High-level orchestrator for managing Claude Code instances across worktrees."""

    def __init__(self, base_repo_path: str, config: Config | None = None):
        """Initialize the orchestrator.
        
        Args:
            base_repo_path: Path to the main git repository
            config: Configuration settings
        """
        self.config = config or Config()
        self.config.ensure_directories()

        self.database = Database(self.config.database_url)
        self.worktree_manager = WorktreeManager(
            base_repo_path=base_repo_path,
            worktree_base_path=self.config.worktree_base_path,
            database=self.database
        )
        self.session_manager = SessionManager(self.database)

        # Active instances tracking with async thread safety
        self.active_instances: dict[str, ClaudeCodeInstance] = {}
        self._instance_lock = asyncio.Lock()  # Async lock for concurrency safety

        logger.info(f"Initialized orchestrator with base repo: {base_repo_path}")

    async def create_instance(self,
                            worktree_name: str | None = None,
                            branch: str | None = None,
                            base_branch: str = "main",
                            instance_config: ClaudeInstanceConfig | None = None) -> ClaudeCodeInstance:
        """Create a new Claude Code instance in a new worktree.
        
        Args:
            worktree_name: Name for the worktree (auto-generated if None)
            branch: Branch name (auto-generated if None)
            base_branch: Base branch to create the new branch from
            instance_config: Configuration for the Claude instance
            
        Returns:
            Created Claude Code instance
        """
        async with self._instance_lock:
            # Check instance limit
            if len(self.active_instances) >= self.config.max_concurrent_instances:
                raise RuntimeError(f"Maximum concurrent instances ({self.config.max_concurrent_instances}) reached")

            # Create worktree
            worktree = self.worktree_manager.create_worktree(
                name=worktree_name,
                branch=branch,
                base_branch=base_branch
            )

            # Create instance configuration
            if instance_config is None:
                instance_config = ClaudeInstanceConfig(
                    model=self.config.claude_model,
                    max_tokens=self.config.max_tokens,
                    timeout=self.config.instance_timeout
                )

            # Create Claude instance
            instance = ClaudeCodeInstance(
                worktree=worktree,
                config=instance_config,
                database=self.database
            )

            self.active_instances[instance.instance_id] = instance
            return instance

    async def get_instance(self, instance_id: str) -> ClaudeCodeInstance | None:
        """Get an existing Claude instance by ID.
        
        Args:
            instance_id: Instance ID
            
        Returns:
            Claude instance if found, None otherwise
        """
        if instance_id in self.active_instances:
            return self.active_instances[instance_id]

        # Try to load from database
        instance_model = self.database.get_claude_instance(instance_id)
        if instance_model:
            worktree = self.worktree_manager.get_worktree(instance_model.worktree_name)
            if worktree:
                # Reconstruct instance
                config = ClaudeInstanceConfig()
                if instance_model.config_json:
                    import json
                    try:
                        config_data = json.loads(instance_model.config_json)
                        config = ClaudeInstanceConfig(**config_data)
                    except Exception:
                        pass

                instance = ClaudeCodeInstance(
                    worktree=worktree,
                    config=config,
                    database=self.database
                )
                instance.instance_id = instance_model.instance_id

                self.active_instances[instance_id] = instance
                return instance

        return None

    async def remove_instance(self, instance_id: str, remove_worktree: bool = True) -> bool:
        """Remove a Claude instance and optionally its worktree.
        
        Args:
            instance_id: Instance ID to remove
            remove_worktree: Whether to also remove the worktree
            
        Returns:
            True if removed successfully, False otherwise
        """
        async with self._instance_lock:
            instance = await self.get_instance(instance_id)
            if not instance:
                return False

            # Stop the instance if running
            if instance.is_running:
                await instance.stop()

            # Remove worktree if requested
            if remove_worktree:
                instance.worktree.remove(force=True)

            # Remove from active instances
            if instance_id in self.active_instances:
                del self.active_instances[instance_id]

            # Remove from database
            self.database.delete_claude_instance(instance_id)

            return True

    async def list_instances(self) -> list[dict[str, any]]:
        """List all active Claude instances with their status.
        
        Returns:
            List of instance status dictionaries
        """
        instances_info = []

        for instance in self.active_instances.values():
            status_info = await instance.get_status_info()
            instances_info.append(status_info)

        return instances_info

    async def run_parallel_tasks(self,
                                tasks: list[dict[str, any]],
                                session_name: str = "parallel_execution",
                                max_concurrent: int | None = None) -> dict[str, any]:
        """Run multiple tasks in parallel across available instances.
        
        Args:
            tasks: List of task dictionaries with 'name', 'description', and optional 'context'
            session_name: Name for the session
            max_concurrent: Maximum concurrent tasks (uses config default if None)
            
        Returns:
            Dictionary with execution results
        """
        max_concurrent = max_concurrent or self.config.max_concurrent_instances

        # Create session
        session = self.session_manager.create_session(
            name=session_name,
            description=f"Parallel execution of {len(tasks)} tasks"
        )

        # Add tasks to session
        for task_data in tasks:
            self.session_manager.add_task(
                session_id=session.session_id,
                name=task_data.get("name", "Unnamed Task"),
                description=task_data.get("description", ""),
                priority=task_data.get("priority", 0),
                dependencies=task_data.get("dependencies", []),
                context=task_data.get("context", {})
            )

        # Ensure we have enough instances
        instances = list(self.active_instances.values())
        needed_instances = min(len(tasks), max_concurrent) - len(instances)

        for _ in range(needed_instances):
            try:
                instance = await self.create_instance()
                instances.append(instance)
                await instance.start()
            except Exception:
                break  # Can't create more instances

        # Add instances to session
        for instance in instances[:max_concurrent]:
            self.session_manager.add_instance(session.session_id, instance)

        # Execute session
        success = await self.session_manager.execute_session(
            session_id=session.session_id,
            instances=instances[:max_concurrent],
            max_concurrent=max_concurrent
        )

        # Get final status
        status = self.session_manager.get_session_status(session.session_id)

        return {
            "success": success,
            "session_id": session.session_id,
            "status": status,
            "instances_used": len(instances[:max_concurrent])
        }

    async def run_sequential_workflow(self,
                                    workflow: list[dict[str, any]],
                                    session_name: str = "sequential_workflow") -> dict[str, any]:
        """Run a sequential workflow where tasks depend on previous tasks.
        
        Args:
            workflow: List of workflow step dictionaries
            session_name: Name for the session
            
        Returns:
            Dictionary with execution results
        """
        # Create session
        session = self.session_manager.create_session(
            name=session_name,
            description=f"Sequential workflow with {len(workflow)} steps"
        )

        # Add tasks with dependencies
        task_ids = []
        for i, step in enumerate(workflow):
            dependencies = [task_ids[i-1]] if i > 0 else []

            task = self.session_manager.add_task(
                session_id=session.session_id,
                name=step.get("name", f"Step {i+1}"),
                description=step.get("description", ""),
                dependencies=dependencies,
                context=step.get("context", {})
            )

            if task:
                task_ids.append(task.task_id)

        # Create single instance for sequential execution
        if not self.active_instances:
            instance = await self.create_instance()
            await instance.start()
        else:
            instance = next(iter(self.active_instances.values()))

        self.session_manager.add_instance(session.session_id, instance)

        # Execute session
        success = await self.session_manager.execute_session(
            session_id=session.session_id,
            instances=[instance],
            max_concurrent=1  # Sequential execution
        )

        # Get final status
        status = self.session_manager.get_session_status(session.session_id)

        return {
            "success": success,
            "session_id": session.session_id,
            "status": status
        }

    async def health_check(self) -> dict[str, any]:
        """Perform a comprehensive health check of all components.
        
        Returns:
            Health status dictionary
        """
        health_info = {
            "overall_healthy": True,
            "components": {},
            "instances": {},
            "worktrees": {}
        }

        # Check database
        try:
            # Simple database check
            self.database.list_worktrees()
            health_info["components"]["database"] = {"healthy": True}
        except Exception as e:
            health_info["components"]["database"] = {"healthy": False, "error": str(e)}
            health_info["overall_healthy"] = False

        # Check worktree manager
        try:
            worktrees = self.worktree_manager.list_worktrees()
            health_info["components"]["worktree_manager"] = {
                "healthy": True,
                "worktree_count": len(worktrees)
            }

            # Check individual worktrees
            for worktree in worktrees:
                wt_health = {
                    "exists": worktree.exists,
                    "is_git_repo": worktree.is_git_repo,
                    "current_branch": worktree.current_branch,
                    "has_changes": worktree.has_changes
                }
                health_info["worktrees"][worktree.name] = wt_health

        except Exception as e:
            health_info["components"]["worktree_manager"] = {"healthy": False, "error": str(e)}
            health_info["overall_healthy"] = False

        # Check instances
        for instance_id, instance in self.active_instances.items():
            instance_health = await instance.health_check()
            health_info["instances"][instance_id] = instance_health
            if not instance_health["healthy"]:
                health_info["overall_healthy"] = False

        return health_info

    async def cleanup(self, max_age_hours: int = 24) -> dict[str, any]:
        """Clean up old resources and inactive instances.
        
        Args:
            max_age_hours: Maximum age in hours before cleanup
            
        Returns:
            Cleanup results
        """
        results = {
            "worktrees_cleaned": [],
            "instances_stopped": [],
            "sessions_archived": []
        }

        # Clean up old worktrees
        cleaned_worktrees = await self.worktree_manager.cleanup_inactive_worktrees(max_age_hours)
        results["worktrees_cleaned"] = cleaned_worktrees

        # Stop inactive instances
        for instance_id, instance in list(self.active_instances.items()):
            # Check if instance should be cleaned up based on your criteria
            status_info = await instance.get_status_info()
            if status_info.get("last_activity"):
                import datetime
                last_activity = datetime.datetime.fromisoformat(status_info["last_activity"])
                if (datetime.datetime.utcnow() - last_activity).total_seconds() > max_age_hours * 3600:
                    await self.remove_instance(instance_id, remove_worktree=True)
                    results["instances_stopped"].append(instance_id)

        return results

    async def shutdown(self) -> None:
        """Shutdown all instances and clean up resources."""
        # Stop all active instances
        for instance in self.active_instances.values():
            if instance.is_running:
                await instance.stop()

        self.active_instances.clear()

        # Cancel any running tasks
        for task in list(self.session_manager._running_tasks.values()):
            if not task.done():
                task.cancel()

        # Clear running tasks
        self.session_manager._running_tasks.clear()
