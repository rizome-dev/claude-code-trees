# Claude Code Trees

Easily manage Claude Code via Git Worktrees, SQLite & Claude Code SDK.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![claude-code-trees](https://img.shields.io/badge/claude--code--trees-0.1.0-green.svg)](https://pypi.org/project/claude-code-trees/)
[![Tests](https://img.shields.io/badge/tests-96%20passing-success.svg)](https://github.com/rizome-dev/claude-code-trees)

```bash
pip install claude-code-trees
```

[Example Usage](https://github.com/rizome-dev/claude-code-trees/blob/main/examples/orchestration.py)

## Documentation

### Orchestrator
The main coordination hub that manages instances, worktrees, and sessions.

```python
orchestrator = Orchestrator(
    base_repo_path="/path/to/repo",
    config=config
)

# Create instances
instance = await orchestrator.create_instance()

# Run parallel tasks
result = await orchestrator.run_parallel_tasks(tasks)

# Health monitoring
health = await orchestrator.health_check()
```

### ClaudeCodeInstance
Wrapper for individual Claude Code instances running in specific worktrees.

```python
# Execute commands
result = await instance.execute_command("create new file")

# Run high-level tasks
result = await instance.run_task("Implement feature X", context={})

# Health checks
health = await instance.health_check()
```

### WorktreeManager
Manages git worktrees for isolated development environments.

```python
# Create worktrees
worktree = manager.create_worktree("feature-wt", "feature-branch")

# List and manage worktrees
worktrees = manager.list_worktrees()
success = manager.remove_worktree("old-worktree")
```

### SessionManager
Handles persistent sessions with task tracking and execution.

```python
# Create sessions
session = manager.create_session("Development Session")

# Add tasks with dependencies
task = manager.add_task(
    session_id, 
    "Implement feature",
    dependencies=["setup-task"]
)

# Execute sessions
success = await manager.execute_session(session_id, instances)
```

## Configuration

Claude Code Trees uses a flexible configuration system:

```python
from claude_code_trees import Config

config = Config(
    # Claude settings
    claude_api_key="your-key",
    claude_model="claude-3-sonnet-20240229",
    max_tokens=4096,
    
    # Orchestration settings
    max_concurrent_instances=3,
    instance_timeout=300,
    
    # Database settings
    database_url="sqlite:///claude_trees.db",
    
    # Worktree settings
    worktree_base_path=Path("/tmp/worktrees"),
    default_branch="main"
)
```

Environment variables are also supported with the `CLCT_` prefix:

```bash
export CLCT_CLAUDE_API_KEY="your-key"
export CLCT_MAX_CONCURRENT_INSTANCES=5
export CLCT_WORKTREE_BASE_PATH="/custom/path"
```

### Use Cases

#### Parallel Feature Development
```python
# Run multiple feature implementations simultaneously
tasks = [
    {"name": "User Auth", "description": "Implement user authentication"},
    {"name": "API Endpoints", "description": "Create REST API endpoints"},
    {"name": "Database Schema", "description": "Design and implement database schema"}
]

result = await orchestrator.run_parallel_tasks(tasks)
```

#### Sequential Workflow
```python
# Run tasks in sequence with dependencies
workflow = [
    {"name": "Setup", "description": "Initialize project structure"},
    {"name": "Core Logic", "description": "Implement core business logic"},
    {"name": "Tests", "description": "Create comprehensive test suite"},
    {"name": "Documentation", "description": "Generate documentation"}
]

result = await orchestrator.run_sequential_workflow(workflow)
```

#### Code Review and Analysis
```python
# Analyze code across multiple worktrees
analysis_tasks = [
    {"name": "Security Audit", "description": "Perform security analysis"},
    {"name": "Performance Review", "description": "Identify performance bottlenecks"},
    {"name": "Code Quality", "description": "Check code quality and standards"}
]

results = await orchestrator.run_parallel_tasks(analysis_tasks)
```

## Development

```bash
# Clone the repository
git clone https://github.com/rizome-dev/claude-code-trees.git
cd claude-code-trees

# Install dependencies with PDM
pdm install -d

# Run tests (all 96 tests passing)
pdm run test

# Run linting
pdm run lint

# Format code
pdm run format

# Type checking
pdm run typecheck

# Test coverage
pdm run test-cov
```

---

Built with ❤️ by [Rizome Labs](https://rizome.dev)
