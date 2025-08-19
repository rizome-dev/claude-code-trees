"""Utility functions for Claude Code Trees."""

import asyncio
import shutil
from pathlib import Path

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError, NoSuchPathError


class GitUtils:
    """Git utility functions."""

    @staticmethod
    def is_git_repo(path: str | Path) -> bool:
        """Check if path is a git repository."""
        try:
            Repo(path)
            return True
        except (InvalidGitRepositoryError, NoSuchPathError):
            return False

    @staticmethod
    def get_current_branch(repo_path: str | Path) -> str:
        """Get the current branch name."""
        repo = Repo(repo_path)
        return repo.active_branch.name

    @staticmethod
    def get_remote_url(repo_path: str | Path) -> str | None:
        """Get the remote URL of the repository."""
        try:
            repo = Repo(repo_path)
            return repo.remotes.origin.url
        except (AttributeError, IndexError):
            return None

    @staticmethod
    def list_branches(repo_path: str | Path, remote: bool = False) -> list[str]:
        """List all branches."""
        repo = Repo(repo_path)
        if remote:
            return [ref.name.split('/')[-1] for ref in repo.remotes.origin.refs]
        return [branch.name for branch in repo.branches]

    @staticmethod
    def create_branch(repo_path: str | Path, branch_name: str,
                     base_branch: str | None = None) -> bool:
        """Create a new branch."""
        try:
            repo = Repo(repo_path)
            if base_branch:
                base = repo.heads[base_branch]
                repo.create_head(branch_name, base)
            else:
                repo.create_head(branch_name)
            return True
        except GitCommandError:
            return False

    @staticmethod
    def checkout_branch(repo_path: str | Path, branch_name: str) -> bool:
        """Checkout a branch."""
        try:
            repo = Repo(repo_path)
            repo.heads[branch_name].checkout()
            return True
        except GitCommandError:
            return False

    @staticmethod
    def has_uncommitted_changes(repo_path: str | Path) -> bool:
        """Check if repository has uncommitted changes."""
        repo = Repo(repo_path)
        return repo.is_dirty()

    @staticmethod
    def commit_changes(repo_path: str | Path, message: str,
                      add_all: bool = True) -> bool:
        """Commit changes to the repository."""
        try:
            repo = Repo(repo_path)
            if add_all:
                repo.git.add(A=True)
            repo.index.commit(message)
            return True
        except GitCommandError:
            return False

    @staticmethod
    async def run_git_command(repo_path: str | Path,
                            command: list[str]) -> tuple[int, str, str]:
        """Run a git command asynchronously."""
        cmd = ["git", "-C", str(repo_path)] + command
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        return process.returncode, stdout.decode(), stderr.decode()


class FileUtils:
    """File system utility functions."""

    @staticmethod
    def copy_directory(src: Path, dst: Path, ignore_patterns: list[str] | None = None) -> bool:
        """Copy directory with optional ignore patterns."""
        try:
            if ignore_patterns:
                def ignore_func(dir_path: str, contents: list[str]) -> list[str]:
                    ignored = []
                    for pattern in ignore_patterns:
                        ignored.extend([item for item in contents if pattern in item])
                    return ignored
                shutil.copytree(src, dst, ignore=ignore_func, dirs_exist_ok=True)
            else:
                shutil.copytree(src, dst, dirs_exist_ok=True)
            return True
        except Exception:
            return False

    @staticmethod
    def remove_directory(path: Path, force: bool = False) -> bool:
        """Remove directory and all contents."""
        try:
            if force and path.exists():
                shutil.rmtree(path)
                return True
            elif path.exists() and path.is_dir():
                path.rmdir()
                return True
            return False
        except Exception:
            return False

    @staticmethod
    def create_directory(path: Path, parents: bool = True) -> bool:
        """Create directory."""
        try:
            path.mkdir(parents=parents, exist_ok=True)
            return True
        except Exception:
            return False

    @staticmethod
    def read_file(path: Path) -> str | None:
        """Read file content."""
        try:
            return path.read_text(encoding='utf-8')
        except Exception:
            return None

    @staticmethod
    def write_file(path: Path, content: str) -> bool:
        """Write content to file."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
            return True
        except Exception:
            return False

    @staticmethod
    def get_file_size(path: Path) -> int:
        """Get file size in bytes."""
        try:
            return path.stat().st_size
        except Exception:
            return 0

    @staticmethod
    def file_exists(path: Path) -> bool:
        """Check if file exists."""
        return path.exists() and path.is_file()

    @staticmethod
    def directory_exists(path: Path) -> bool:
        """Check if directory exists."""
        return path.exists() and path.is_dir()


class ProcessUtils:
    """Process utility functions."""

    @staticmethod
    async def run_command(command: list[str], cwd: Path | None = None,
                         timeout: int | None = None) -> tuple[int, str, str]:
        """Run a command asynchronously."""
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            return process.returncode, stdout.decode(), stderr.decode()
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)

    @staticmethod
    def is_process_running(pid: int) -> bool:
        """Check if process is running."""
        try:
            import psutil
            return psutil.pid_exists(pid)
        except ImportError:
            # Fallback without psutil
            try:
                import os
                os.kill(pid, 0)
                return True
            except OSError:
                return False
