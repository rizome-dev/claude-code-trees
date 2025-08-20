#!/usr/bin/env python3
"""
Example demonstrating proper usage of claude-code-trees orchestration.

This example shows how to:
1. Initialize the orchestrator with a git repository
2. Create properly formatted tasks with the required 'description' field
3. Execute tasks in parallel across multiple worktrees
"""

import os
import asyncio
import tempfile
import subprocess
from pathlib import Path
from claude_code_trees import (
    Config,
    Database,
    Orchestrator,
)


async def main():
    """Run the orchestration example."""
    
    # Setup temporary directory for demonstration
    demo_dir = tempfile.mkdtemp(prefix="claude_trees_example_")
    print(f"Working directory: {demo_dir}\n")
    
    # 1. Create a git repository
    print("Setting up git repository...")
    repo_path = Path(demo_dir) / "repo"
    repo_path.mkdir()
    
    # Initialize git repo
    subprocess.run(['git', 'init'], cwd=repo_path, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Example User'], cwd=repo_path, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'user@example.com'], cwd=repo_path, capture_output=True)
    
    # Create sample files
    (repo_path / "calculator.py").write_text("""def add(a, b):
    \"\"\"Add two numbers.\"\"\"
    # TODO: Implement this function
    pass

def multiply(a, b):
    \"\"\"Multiply two numbers.\"\"\"
    # TODO: Implement this function
    pass
""")
    
    (repo_path / "utils.py").write_text("""def format_output(value):
    \"\"\"Format a value for display.\"\"\"
    # TODO: Format as string with 2 decimal places
    pass
""")
    
    # Commit initial files
    subprocess.run(['git', 'add', '.'], cwd=repo_path, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=repo_path, capture_output=True)
    print("Repository created successfully\n")
    
    # 2. Create configuration
    print("Creating configuration...")
    config_yaml = f"""database_url: "sqlite:///{demo_dir}/orchestrator.db"
default_branch: "main"
worktree_base_path: "{demo_dir}/worktrees"
claude_api_key: "{os.environ.get('ANTHROPIC_API_KEY', '')}"
claude_model: "claude-3-sonnet-20240229"
max_tokens: 4000
max_concurrent_instances: 3
instance_timeout: 300
session_timeout: 1800
log_level: "INFO"
log_file: "{demo_dir}/orchestrator.log"
"""
    
    config_path = Path(demo_dir) / "config.yaml"
    config_path.write_text(config_yaml)
    config = Config.load_from_file(config_path)
    print("Configuration loaded\n")
    
    # 3. Initialize Orchestrator
    print("Initializing Orchestrator...")
    database = Database(f"sqlite:///{demo_dir}/orchestrator.db")
    orchestrator = Orchestrator(str(repo_path), config)
    print("Orchestrator ready\n")
    
    # 4. Define tasks with proper format
    # IMPORTANT: Tasks must have a 'description' field, not 'command' or other names
    tasks = [
        {
            "name": "implement_add_function",
            "description": "Implement the add(a, b) function in calculator.py to return the sum of two numbers",
            "priority": 1,
            "context": {
                "file": "calculator.py",
                "function": "add",
                "expected_behavior": "Should return a + b"
            }
        },
        {
            "name": "implement_multiply_function",
            "description": "Implement the multiply(a, b) function in calculator.py to return the product of two numbers",
            "priority": 1,
            "context": {
                "file": "calculator.py",
                "function": "multiply",
                "expected_behavior": "Should return a * b"
            }
        },
        {
            "name": "implement_format_output",
            "description": "Implement format_output(value) in utils.py to return the value as a string with 2 decimal places",
            "priority": 2,
            "context": {
                "file": "utils.py",
                "function": "format_output",
                "expected_format": "'{:.2f}'.format(value)"
            }
        }
    ]
    
    print("Tasks to execute:")
    for task in tasks:
        print(f"  - {task['name']}")
        print(f"    Description: {task['description'][:60]}...")
    print()
    
    # 5. Execute tasks
    print("Executing tasks in parallel...")
    try:
        result = await orchestrator.run_parallel_tasks(
            tasks,
            session_name="code_implementation_session",
            max_concurrent=2  # Run up to 2 tasks simultaneously
        )
        
        print("\nExecution complete!")
        print(f"Session ID: {result['session_id']}")
        print(f"Success: {result['success']}")
        print(f"Instances used: {result['instances_used']}")
        
        # Display task results
        status = result.get('status', {})
        task_counts = status.get('task_counts', {})
        print(f"\nTask Summary:")
        print(f"  Completed: {task_counts.get('completed', 0)}")
        print(f"  Failed: {task_counts.get('failed', 0)}")
        print(f"  Pending: {task_counts.get('pending', 0)}")
        
    except Exception as e:
        print(f"Error during execution: {e}")
    
    print(f"\nArtifacts location: {demo_dir}")
    print(f"Log file: {demo_dir}/orchestrator.log")
    
    return demo_dir


if __name__ == "__main__":
    print("Claude Code Trees - Orchestration Example")
    print("=" * 50)
    print()
    
    # Check for API key
    if not os.environ.get('ANTHROPIC_API_KEY'):
        print("WARNING: ANTHROPIC_API_KEY environment variable not set")
        print("Set it with: export ANTHROPIC_API_KEY='your-api-key'")
        print()
    
    # Run the example
    demo_dir = asyncio.run(main())
    print(f"\nExample complete. Results saved to: {demo_dir}")
