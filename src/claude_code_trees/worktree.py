"""Git worktree management for Claude Code Trees."""

import uuid
from pathlib import Path
from typing import Optional

from .database import Database
from .utils import FileUtils, GitUtils


class WorktreeManager:
    """Manager for git worktrees used by Claude Code instances."""

    def __init__(self, base_repo_path: str | Path,
                 worktree_base_path: str | Path,
                 database: Database | None = None):
        """Initialize worktree manager.
        
        Args:
            base_repo_path: Path to the main git repository
            worktree_base_path: Base directory where worktrees will be created
            database: Database instance for persistence
        """
        self.base_repo_path = Path(base_repo_path)
        self.worktree_base_path = Path(worktree_base_path)
        self.database = database or Database()

        if not GitUtils.is_git_repo(self.base_repo_path):
            raise ValueError(f"Path {self.base_repo_path} is not a git repository")

        # Ensure worktree base directory exists
        FileUtils.create_directory(self.worktree_base_path)

    def create_worktree(self, name: str | None = None,
                       branch: str | None = None,
                       base_branch: str = "main") -> "Worktree":
        """Create a new git worktree.
        
        Args:
            name: Name for the worktree (auto-generated if None)
            branch: Branch to create/checkout (auto-generated if None)
            base_branch: Base branch to branch from
            
        Returns:
            Worktree instance
        """
        if name is None:
            name = f"worktree-{uuid.uuid4().hex[:8]}"

        if branch is None:
            branch = f"branch-{uuid.uuid4().hex[:8]}"

        worktree_path = self.worktree_base_path / name

        if worktree_path.exists():
            raise ValueError(f"Worktree path {worktree_path} already exists")

        # Create the branch in the base repository
        if not GitUtils.create_branch(self.base_repo_path, branch, base_branch):
            raise RuntimeError(f"Failed to create branch {branch}")

        # Create the worktree
        try:
            import subprocess
            result = subprocess.run([
                "git", "-C", str(self.base_repo_path),
                "worktree", "add", str(worktree_path), branch
            ], capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to create worktree: {e.stderr}")

        # Create database record
        self.database.create_worktree(
            name=name,
            path=str(worktree_path),
            branch=branch,
            base_repo_path=str(self.base_repo_path)
        )

        return Worktree(
            name=name,
            path=worktree_path,
            branch=branch,
            manager=self
        )

    def get_worktree(self, name: str) -> Optional["Worktree"]:
        """Get existing worktree by name.
        
        Args:
            name: Worktree name
            
        Returns:
            Worktree instance or None if not found
        """
        worktree_model = self.database.get_worktree(name)
        if worktree_model and Path(worktree_model.path).exists():
            self.database.update_worktree_access_time(name)
            return Worktree(
                name=worktree_model.name,
                path=Path(worktree_model.path),
                branch=worktree_model.branch,
                manager=self
            )
        return None

    def list_worktrees(self) -> list["Worktree"]:
        """List all active worktrees.
        
        Returns:
            List of Worktree instances
        """
        worktrees = []
        for worktree_model in self.database.list_worktrees():
            if Path(worktree_model.path).exists():
                worktrees.append(Worktree(
                    name=worktree_model.name,
                    path=Path(worktree_model.path),
                    branch=worktree_model.branch,
                    manager=self
                ))
        return worktrees

    def remove_worktree(self, name: str, force: bool = False) -> bool:
        """Remove a worktree.
        
        Args:
            name: Worktree name
            force: Force removal even if there are uncommitted changes
            
        Returns:
            True if successful, False otherwise
        """
        worktree_model = self.database.get_worktree(name)
        if not worktree_model:
            return False

        worktree_path = Path(worktree_model.path)

        # Check for uncommitted changes unless forcing
        if not force and worktree_path.exists() and GitUtils.has_uncommitted_changes(worktree_path):
            raise ValueError(f"Worktree {name} has uncommitted changes. Use force=True to remove anyway.")

        # Remove the git worktree
        try:
            import subprocess
            cmd = ["git", "-C", str(self.base_repo_path), "worktree", "remove"]
            if force:
                cmd.append("--force")
            cmd.append(str(worktree_path))

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError:
            # If git command fails, try to remove directory manually
            if worktree_path.exists():
                FileUtils.remove_directory(worktree_path, force=True)

        # Remove database record
        return self.database.delete_worktree(name)

    async def cleanup_inactive_worktrees(self, max_age_hours: int = 24) -> list[str]:
        """Clean up inactive worktrees older than specified age.
        
        Args:
            max_age_hours: Maximum age in hours before cleanup
            
        Returns:
            List of cleaned up worktree names
        """
        import datetime

        cutoff_time = datetime.datetime.utcnow() - datetime.timedelta(hours=max_age_hours)
        cleaned_up = []

        for worktree_model in self.database.list_worktrees():
            if worktree_model.last_accessed < cutoff_time:
                try:
                    if self.remove_worktree(worktree_model.name, force=True):
                        cleaned_up.append(worktree_model.name)
                except Exception:
                    continue  # Skip if removal fails

        return cleaned_up


class Worktree:
    """Represents a git worktree instance."""

    def __init__(self, name: str, path: Path, branch: str, manager: WorktreeManager):
        """Initialize worktree instance."""
        self.name = name
        self.path = path
        self.branch = branch
        self.manager = manager

    @property
    def exists(self) -> bool:
        """Check if worktree directory exists."""
        return self.path.exists() and self.path.is_dir()

    @property
    def is_git_repo(self) -> bool:
        """Check if worktree is a valid git repository."""
        return GitUtils.is_git_repo(self.path)

    @property
    def current_branch(self) -> str:
        """Get current branch name."""
        if self.is_git_repo:
            return GitUtils.get_current_branch(self.path)
        return ""

    @property
    def has_changes(self) -> bool:
        """Check if worktree has uncommitted changes."""
        if self.is_git_repo:
            return GitUtils.has_uncommitted_changes(self.path)
        return False

    def checkout_branch(self, branch_name: str) -> bool:
        """Checkout a different branch in this worktree."""
        return GitUtils.checkout_branch(self.path, branch_name)

    def create_branch(self, branch_name: str, base_branch: str | None = None) -> bool:
        """Create a new branch in this worktree."""
        return GitUtils.create_branch(self.path, branch_name, base_branch)

    def commit_changes(self, message: str, add_all: bool = True) -> bool:
        """Commit changes in this worktree."""
        return GitUtils.commit_changes(self.path, message, add_all)

    async def run_git_command(self, command: list[str]) -> tuple[int, str, str]:
        """Run a git command in this worktree."""
        return await GitUtils.run_git_command(self.path, command)

    def read_file(self, file_path: str | Path) -> str | None:
        """Read a file from this worktree."""
        full_path = self.path / file_path
        return FileUtils.read_file(full_path)

    def write_file(self, file_path: str | Path, content: str) -> bool:
        """Write content to a file in this worktree."""
        full_path = self.path / file_path
        return FileUtils.write_file(full_path, content)

    def file_exists(self, file_path: str | Path) -> bool:
        """Check if a file exists in this worktree."""
        full_path = self.path / file_path
        return FileUtils.file_exists(full_path)

    def remove(self, force: bool = False) -> bool:
        """Remove this worktree."""
        return self.manager.remove_worktree(self.name, force)

    def __str__(self) -> str:
        """String representation of worktree."""
        return f"Worktree(name={self.name}, branch={self.branch}, path={self.path})"

    def __repr__(self) -> str:
        """Detailed string representation of worktree."""
        return (f"Worktree(name='{self.name}', branch='{self.branch}', "
                f"path='{self.path}', exists={self.exists})")
