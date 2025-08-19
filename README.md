# Claude Code Trees

**Production-ready Python library for managing Claude Code instances on git worktrees**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![claude-code-sdk](https://img.shields.io/badge/claude--code--sdk-0.0.20+-green.svg)](https://pypi.org/project/claude-code-sdk/)
[![Tests](https://img.shields.io/badge/tests-96%20passing-success.svg)](https://github.com/rizome-dev/claude-code-trees)

Claude Code Trees enables you to orchestrate multiple Claude Code instances across different git worktrees, allowing for parallel development workflows and sophisticated AI-powered coding tasks. Perfect for managing complex projects, running parallel experiments, or coordinating multi-faceted development work.

## Quick Start

### Installation

```bash
# Step 1: Install Claude Code CLI (required)
npm install -g @anthropic-ai/claude-code

# Step 2: Install claude-code-trees
pip install claude-code-trees

# Or install from source with PDM (recommended for development)
git clone https://github.com/rizome-dev/claude-code-trees.git
cd claude-code-trees
pdm install
```

### Basic Usage

```python
import asyncio
from pathlib import Path
from claude_code_trees import Orchestrator, Config

async def main():
    # Configure the orchestrator
    config = Config(
        claude_api_key="your-api-key-here",
        max_concurrent_instances=3,
        worktree_base_path=Path.cwd() / ".worktrees"
    )
    
    # Initialize orchestrator with your git repository
    orchestrator = Orchestrator("/path/to/your/repo", config)
    
    try:
        # Create a Claude Code instance
        instance = await orchestrator.create_instance(
            worktree_name="feature-branch",
            branch="feature/new-functionality"
        )
        
        # Start the instance and run a task
        await instance.start()
        result = await instance.run_task(
            "Create a new Python module with comprehensive documentation"
        )
        
        if result["success"]:
            print(f"Task completed: {result['output']}")
        else:
            print(f"Task failed: {result['error']}")
            
    finally:
        await orchestrator.shutdown()

# Run the example
asyncio.run(main())
```

### CLI Usage

```bash
# Create a new Claude Code instance
clct create --name my-instance --branch feature/new-work

# List all instances
clct list

# Run a task on an instance
clct run-task <instance-id> "Implement user authentication system"

# Run multiple tasks in parallel
clct parallel tasks.json --session-name "parallel-dev-work"

# Monitor system health
clct health

# Clean up old resources
clct cleanup --max-age-hours 24
```

## Documentation

### Core Components

#### Orchestrator
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

#### ClaudeCodeInstance
Wrapper for individual Claude Code instances running in specific worktrees.

```python
# Execute commands
result = await instance.execute_command("create new file")

# Run high-level tasks
result = await instance.run_task("Implement feature X", context={})

# Health checks
health = await instance.health_check()
```

#### WorktreeManager
Manages git worktrees for isolated development environments.

```python
# Create worktrees
worktree = manager.create_worktree("feature-wt", "feature-branch")

# List and manage worktrees
worktrees = manager.list_worktrees()
success = manager.remove_worktree("old-worktree")
```

#### SessionManager
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

### Configuration

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

## Use Cases

### Parallel Feature Development
```python
# Run multiple feature implementations simultaneously
tasks = [
    {"name": "User Auth", "description": "Implement user authentication"},
    {"name": "API Endpoints", "description": "Create REST API endpoints"},
    {"name": "Database Schema", "description": "Design and implement database schema"}
]

result = await orchestrator.run_parallel_tasks(tasks)
```

### Sequential Workflow
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

### Code Review and Analysis
```python
# Analyze code across multiple worktrees
analysis_tasks = [
    {"name": "Security Audit", "description": "Perform security analysis"},
    {"name": "Performance Review", "description": "Identify performance bottlenecks"},
    {"name": "Code Quality", "description": "Check code quality and standards"}
]

results = await orchestrator.run_parallel_tasks(analysis_tasks)
```

## Features

### Error Handling & Resilience

The library includes comprehensive error handling for common failure scenarios:

```python
# Automatic retry with exponential backoff
result = await instance.execute_query(
    prompt="Create a new module",
    max_retries=3  # Retries on transient failures
)

# Handles specific Claude Code SDK errors
try:
    await instance.start()
except CLINotFoundError:
    print("Claude Code CLI not installed. Run: npm install -g @anthropic-ai/claude-code")
except CLIConnectionError:
    print("Failed to connect to Claude Code service")
```

### Logging

Built-in structured logging for debugging and monitoring:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Logs include:
# - Task execution status
# - Retry attempts
# - Performance metrics
# - Error details
```

### Thread Safety

Safe for concurrent use with async/await patterns:

```python
# Run multiple instances concurrently
async with orchestrator:
    tasks = [
        orchestrator.create_instance(f"instance-{i}")
        for i in range(5)
    ]
    instances = await asyncio.gather(*tasks)
```

## Development

### Setup

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

### Running Examples

```bash
# Basic usage
python examples/basic_usage.py

# Parallel tasks
python examples/parallel_tasks.py

# Advanced orchestration
python examples/advanced_orchestration.py
```

---

Built with ❤️ by [Rizome Labs](https://rizome.dev)
