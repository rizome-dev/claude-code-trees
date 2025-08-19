"""Tests for worktree management."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from claude_code_trees.database import Database
from claude_code_trees.worktree import Worktree, WorktreeManager


@pytest.fixture
def temp_repo():
    """Create a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir) / "test_repo"
        repo_path.mkdir()

        # Initialize git repository
        import subprocess
        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_path, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_path, check=True)

        # Create initial commit
        (repo_path / "README.md").write_text("# Test Repository")
        subprocess.run(["git", "add", "README.md"], cwd=repo_path, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True)

        yield repo_path


@pytest.fixture
def temp_worktree_base():
    """Create a temporary directory for worktrees."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_database():
    """Mock database for testing."""
    db = Mock(spec=Database)
    return db


@pytest.fixture
def worktree_manager(temp_repo, temp_worktree_base, mock_database):
    """Create a WorktreeManager instance for testing."""
    return WorktreeManager(temp_repo, temp_worktree_base, mock_database)


class TestWorktreeManager:
    """Test cases for WorktreeManager."""

    def test_init_valid_repo(self, temp_repo, temp_worktree_base, mock_database):
        """Test initialization with valid repository."""
        manager = WorktreeManager(temp_repo, temp_worktree_base, mock_database)
        assert manager.base_repo_path == temp_repo
        assert manager.worktree_base_path == temp_worktree_base
        assert manager.database == mock_database

    def test_init_invalid_repo(self, temp_worktree_base, mock_database):
        """Test initialization with invalid repository."""
        invalid_repo = Path("/nonexistent/path")
        with pytest.raises(ValueError, match="is not a git repository"):
            WorktreeManager(invalid_repo, temp_worktree_base, mock_database)

    @patch('subprocess.run')
    def test_create_worktree_success(self, mock_subprocess, worktree_manager):
        """Test successful worktree creation."""
        # Mock subprocess.run to simulate successful git worktree add
        mock_subprocess.return_value = Mock(returncode=0)

        # Mock database methods
        worktree_manager.database.create_worktree.return_value = Mock()

        # Mock GitUtils.create_branch
        with patch('claude_code_trees.worktree.GitUtils.create_branch', return_value=True):
            worktree = worktree_manager.create_worktree("test-worktree", "test-branch")

            assert isinstance(worktree, Worktree)
            assert worktree.name == "test-worktree"
            assert worktree.branch == "test-branch"

            # Verify database was called
            worktree_manager.database.create_worktree.assert_called_once()

    def test_create_worktree_existing_path(self, worktree_manager, temp_worktree_base):
        """Test creating worktree with existing path."""
        existing_path = temp_worktree_base / "existing"
        existing_path.mkdir()

        with pytest.raises(ValueError, match="already exists"):
            worktree_manager.create_worktree("existing")

    @patch('claude_code_trees.worktree.GitUtils.create_branch', return_value=False)
    def test_create_worktree_branch_creation_fails(self, mock_create_branch, worktree_manager):
        """Test worktree creation when branch creation fails."""
        with pytest.raises(RuntimeError, match="Failed to create branch"):
            worktree_manager.create_worktree("test-worktree", "test-branch")

    def test_get_worktree_exists(self, worktree_manager, temp_worktree_base):
        """Test getting existing worktree."""
        # Mock database response
        mock_worktree_model = Mock()
        mock_worktree_model.name = "test-worktree"
        mock_worktree_model.path = str(temp_worktree_base / "test-worktree")
        mock_worktree_model.branch = "test-branch"

        # Create the actual directory
        Path(mock_worktree_model.path).mkdir()

        worktree_manager.database.get_worktree.return_value = mock_worktree_model
        worktree_manager.database.update_worktree_access_time.return_value = True

        worktree = worktree_manager.get_worktree("test-worktree")

        assert worktree is not None
        assert worktree.name == "test-worktree"
        assert worktree.branch == "test-branch"

        # Verify access time was updated
        worktree_manager.database.update_worktree_access_time.assert_called_once_with("test-worktree")

    def test_get_worktree_not_exists(self, worktree_manager):
        """Test getting non-existent worktree."""
        worktree_manager.database.get_worktree.return_value = None

        worktree = worktree_manager.get_worktree("nonexistent")

        assert worktree is None

    def test_list_worktrees(self, worktree_manager, temp_worktree_base):
        """Test listing worktrees."""
        # Mock database response
        mock_worktree1 = Mock()
        mock_worktree1.name = "worktree1"
        mock_worktree1.path = str(temp_worktree_base / "worktree1")
        mock_worktree1.branch = "branch1"

        mock_worktree2 = Mock()
        mock_worktree2.name = "worktree2"
        mock_worktree2.path = str(temp_worktree_base / "worktree2")
        mock_worktree2.branch = "branch2"

        # Create actual directories
        Path(mock_worktree1.path).mkdir()
        Path(mock_worktree2.path).mkdir()

        worktree_manager.database.list_worktrees.return_value = [mock_worktree1, mock_worktree2]

        worktrees = worktree_manager.list_worktrees()

        assert len(worktrees) == 2
        assert worktrees[0].name == "worktree1"
        assert worktrees[1].name == "worktree2"

    @patch('subprocess.run')
    def test_remove_worktree_success(self, mock_subprocess, worktree_manager):
        """Test successful worktree removal."""
        # Mock database response
        mock_worktree_model = Mock()
        mock_worktree_model.path = "/test/path"
        worktree_manager.database.get_worktree.return_value = mock_worktree_model
        worktree_manager.database.delete_worktree.return_value = True

        # Mock subprocess success
        mock_subprocess.return_value = Mock(returncode=0)

        # Mock GitUtils.has_uncommitted_changes
        with patch('claude_code_trees.worktree.GitUtils.has_uncommitted_changes', return_value=False):
            result = worktree_manager.remove_worktree("test-worktree")

            assert result is True
            worktree_manager.database.delete_worktree.assert_called_once_with("test-worktree")

    def test_remove_worktree_not_exists(self, worktree_manager):
        """Test removing non-existent worktree."""
        worktree_manager.database.get_worktree.return_value = None

        result = worktree_manager.remove_worktree("nonexistent")

        assert result is False

    def test_remove_worktree_uncommitted_changes(self, worktree_manager, temp_worktree_base):
        """Test removing worktree with uncommitted changes."""
        # Mock database response
        mock_worktree_model = Mock()
        mock_worktree_model.path = str(temp_worktree_base / "test-worktree")

        # Create the directory
        Path(mock_worktree_model.path).mkdir()

        worktree_manager.database.get_worktree.return_value = mock_worktree_model

        # Mock uncommitted changes
        with patch('claude_code_trees.worktree.GitUtils.has_uncommitted_changes', return_value=True):
            with pytest.raises(ValueError, match="has uncommitted changes"):
                worktree_manager.remove_worktree("test-worktree", force=False)


class TestWorktree:
    """Test cases for Worktree class."""

    @pytest.fixture
    def mock_manager(self):
        """Mock WorktreeManager."""
        return Mock(spec=WorktreeManager)

    @pytest.fixture
    def worktree(self, mock_manager, temp_worktree_base):
        """Create a Worktree instance for testing."""
        worktree_path = temp_worktree_base / "test-worktree"
        worktree_path.mkdir()
        return Worktree("test-worktree", worktree_path, "test-branch", mock_manager)

    def test_worktree_properties(self, worktree):
        """Test worktree properties."""
        assert worktree.name == "test-worktree"
        assert worktree.branch == "test-branch"
        assert worktree.exists is True

    def test_worktree_exists_false(self, mock_manager):
        """Test worktree exists property when directory doesn't exist."""
        nonexistent_path = Path("/nonexistent/path")
        worktree = Worktree("test", nonexistent_path, "branch", mock_manager)
        assert worktree.exists is False

    @patch('claude_code_trees.worktree.GitUtils.is_git_repo')
    def test_is_git_repo(self, mock_is_git_repo, worktree):
        """Test is_git_repo property."""
        mock_is_git_repo.return_value = True
        assert worktree.is_git_repo is True
        mock_is_git_repo.assert_called_once_with(worktree.path)

    @patch('claude_code_trees.worktree.GitUtils.get_current_branch')
    @patch('claude_code_trees.worktree.GitUtils.is_git_repo')
    def test_current_branch(self, mock_is_git_repo, mock_get_current_branch, worktree):
        """Test current_branch property."""
        mock_is_git_repo.return_value = True
        mock_get_current_branch.return_value = "current-branch"

        assert worktree.current_branch == "current-branch"
        mock_is_git_repo.assert_called_once_with(worktree.path)
        mock_get_current_branch.assert_called_once_with(worktree.path)

    @patch('claude_code_trees.worktree.GitUtils.has_uncommitted_changes')
    @patch('claude_code_trees.worktree.GitUtils.is_git_repo')
    def test_has_changes(self, mock_is_git_repo, mock_has_changes, worktree):
        """Test has_changes property."""
        mock_is_git_repo.return_value = True
        mock_has_changes.return_value = True

        assert worktree.has_changes is True
        mock_is_git_repo.assert_called_once_with(worktree.path)
        mock_has_changes.assert_called_once_with(worktree.path)

    def test_read_write_file(self, worktree):
        """Test file reading and writing."""
        test_content = "Hello, World!"
        test_file = "test.txt"

        # Write file
        success = worktree.write_file(test_file, test_content)
        assert success is True

        # Read file
        content = worktree.read_file(test_file)
        assert content == test_content

    def test_file_exists(self, worktree):
        """Test file existence check."""
        test_file = "test.txt"

        # File doesn't exist initially
        assert worktree.file_exists(test_file) is False

        # Create file
        worktree.write_file(test_file, "content")

        # File should exist now
        assert worktree.file_exists(test_file) is True

    def test_str_representation(self, worktree):
        """Test string representation."""
        str_repr = str(worktree)
        assert "test-worktree" in str_repr
        assert "test-branch" in str_repr

    def test_repr_representation(self, worktree):
        """Test detailed string representation."""
        repr_str = repr(worktree)
        assert "Worktree" in repr_str
        assert "test-worktree" in repr_str
        assert "test-branch" in repr_str


@pytest.mark.asyncio
class TestWorktreeAsync:
    """Async test cases for Worktree."""

    @pytest.fixture
    def mock_manager(self):
        """Mock WorktreeManager."""
        return Mock(spec=WorktreeManager)

    @pytest.fixture
    def worktree(self, mock_manager, temp_worktree_base):
        """Create a Worktree instance for testing."""
        worktree_path = temp_worktree_base / "test-worktree"
        worktree_path.mkdir()
        return Worktree("test-worktree", worktree_path, "test-branch", mock_manager)

    @patch('claude_code_trees.worktree.GitUtils.run_git_command')
    async def test_run_git_command(self, mock_run_git_command, worktree):
        """Test running git command."""
        mock_run_git_command.return_value = (0, "output", "")

        result = await worktree.run_git_command(["status"])

        assert result == (0, "output", "")
        mock_run_git_command.assert_called_once_with(worktree.path, ["status"])
