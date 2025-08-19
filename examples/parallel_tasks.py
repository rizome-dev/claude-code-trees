#!/usr/bin/env python3
"""
Parallel tasks example for Claude Code Trees.

This example demonstrates how to:
1. Run multiple tasks in parallel across different worktrees
2. Handle task dependencies
3. Monitor execution progress
4. Manage concurrent instances
"""

import asyncio
import anyio
import json
from pathlib import Path

from claude_code_trees import Orchestrator, Config


def create_sample_tasks():
    """Create a list of sample tasks for parallel execution."""
    return [
        {
            "name": "Create Documentation",
            "description": "Create a comprehensive README.md file with project documentation",
            "priority": 1,
            "context": {
                "project_name": "Claude Code Trees",
                "include_sections": ["installation", "usage", "examples", "api"]
            }
        },
        {
            "name": "Setup CI/CD",
            "description": "Create a GitHub Actions workflow for CI/CD",
            "priority": 2,
            "context": {
                "workflow_name": "ci.yml",
                "python_versions": ["3.10", "3.11", "3.12"],
                "test_command": "pytest",
                "include_coverage": True
            }
        },
        {
            "name": "Add Type Stubs",
            "description": "Create py.typed file and improve type annotations throughout the codebase",
            "priority": 1,
            "context": {
                "mypy_strict": True,
                "check_modules": ["claude_code_trees"]
            }
        },
        {
            "name": "Create Docker Setup",
            "description": "Create Dockerfile and docker-compose.yml for containerized development",
            "priority": 2,
            "context": {
                "python_version": "3.11",
                "include_dev_dependencies": True
            }
        },
        {
            "name": "Performance Tests",
            "description": "Create performance benchmarks for worktree and instance operations",
            "priority": 3,
            "context": {
                "benchmark_operations": ["create_worktree", "start_instance", "run_task"],
                "iterations": 10
            }
        }
    ]


async def parallel_tasks_example():
    """Run multiple tasks in parallel."""
    # Configuration
    config = Config(
        max_concurrent_instances=3,  # Allow up to 3 parallel instances
        instance_timeout=600,        # 10 minutes timeout per task
        worktree_base_path=Path.cwd() / ".worktrees"
    )
    
    # Initialize orchestrator
    repo_path = Path.cwd()
    orchestrator = Orchestrator(str(repo_path), config)
    
    try:
        print("🚀 Setting up parallel task execution...")
        
        # Create sample tasks
        tasks = create_sample_tasks()
        
        print(f"📋 Created {len(tasks)} tasks:")
        for task in tasks:
            print(f"   • {task['name']} (Priority: {task['priority']})")
        
        # Run tasks in parallel
        print(f"\n⚡ Starting parallel execution with max {config.max_concurrent_instances} concurrent tasks...")
        
        result = await orchestrator.run_parallel_tasks(
            tasks=tasks,
            session_name="Parallel Development Tasks",
            max_concurrent=3
        )
        
        if result["success"]:
            print("✅ All tasks completed successfully!")
            
            # Show execution summary
            status = result["status"]
            if status:
                print(f"\n📊 Execution Summary:")
                print(f"   Session ID: {result['session_id']}")
                print(f"   Instances Used: {result['instances_used']}")
                print(f"   Total Tasks: {status['total_tasks']}")
                print(f"   Completed: {status['task_counts']['completed']}")
                print(f"   Failed: {status['task_counts']['failed']}")
                
                if status['task_counts']['failed'] > 0:
                    print("⚠️  Some tasks failed - check individual task results")
        else:
            print("❌ Parallel execution failed")
            
        # List all instances and their status
        print(f"\n🔍 Instance Status:")
        instances = await orchestrator.list_instances()
        for instance_info in instances:
            status_emoji = "✅" if instance_info["is_running"] else "⏹️"
            print(f"   {status_emoji} {instance_info['instance_id'][:12]}... ({instance_info['status']})")
            print(f"      Worktree: {instance_info['worktree']} | Branch: {instance_info['current_branch']}")
            if instance_info["has_changes"]:
                print(f"      📝 Has uncommitted changes")
        
    except Exception as e:
        print(f"❌ Error during parallel execution: {e}")
        
    finally:
        print("\n🧹 Cleaning up resources...")
        await orchestrator.cleanup(max_age_hours=0)  # Clean up immediately for demo
        await orchestrator.shutdown()
        print("✅ Cleanup completed")


async def dependent_tasks_example():
    """Example with task dependencies."""
    config = Config(max_concurrent_instances=2)
    orchestrator = Orchestrator(str(Path.cwd()), config)
    
    try:
        print("🔗 Running dependent tasks example...")
        
        # Create a sequential workflow where tasks depend on each other
        workflow = [
            {
                "name": "Setup Project Structure",
                "description": "Create basic project directories and files",
                "context": {"directories": ["src", "tests", "docs", "scripts"]}
            },
            {
                "name": "Create Base Configuration",
                "description": "Create configuration files based on the project structure",
                "context": {"config_files": ["setup.cfg", "pyproject.toml", "tox.ini"]}
            },
            {
                "name": "Generate Initial Tests",
                "description": "Create test files for the established project structure",
                "context": {"test_framework": "pytest", "coverage": True}
            },
            {
                "name": "Create Documentation",
                "description": "Generate documentation based on the project structure and configuration",
                "context": {"doc_format": "sphinx", "api_docs": True}
            }
        ]
        
        print(f"📋 Sequential workflow with {len(workflow)} steps:")
        for i, step in enumerate(workflow, 1):
            print(f"   {i}. {step['name']}")
        
        result = await orchestrator.run_sequential_workflow(
            workflow=workflow,
            session_name="Sequential Project Setup"
        )
        
        if result["success"]:
            print("✅ Sequential workflow completed successfully!")
            
            status = result["status"]
            if status:
                print(f"\n📊 Workflow Summary:")
                print(f"   Session: {result['session_id']}")
                print(f"   Completed: {status['task_counts']['completed']}")
                print(f"   Failed: {status['task_counts']['failed']}")
        else:
            print("❌ Sequential workflow failed")
            
    except Exception as e:
        print(f"❌ Error during sequential execution: {e}")
        
    finally:
        await orchestrator.shutdown()


async def monitor_execution_example():
    """Example showing how to monitor task execution."""
    config = Config(max_concurrent_instances=2)
    orchestrator = Orchestrator(str(Path.cwd()), config)
    
    try:
        print("📊 Task execution monitoring example...")
        
        # Create some sample tasks
        tasks = [
            {
                "name": "Long Running Task 1",
                "description": "Simulate a long-running task by creating a large file",
                "priority": 1
            },
            {
                "name": "Long Running Task 2", 
                "description": "Another long-running task that processes files",
                "priority": 1
            }
        ]
        
        # Start execution in background
        print("🚀 Starting background task execution...")
        
        # Create session manually to get more control
        session = orchestrator.session_manager.create_session(
            name="Monitored Execution",
            description="Example of monitoring task execution"
        )
        
        # Add tasks
        for task_data in tasks:
            orchestrator.session_manager.add_task(
                session_id=session.session_id,
                name=task_data["name"],
                description=task_data["description"],
                priority=task_data.get("priority", 0)
            )
        
        # Create instances
        instance1 = await orchestrator.create_instance(
            worktree_name="monitor-wt1",
            branch="monitor-br1"
        )
        instance2 = await orchestrator.create_instance(
            worktree_name="monitor-wt2", 
            branch="monitor-br2"
        )
        
        orchestrator.session_manager.add_instance(session.session_id, instance1)
        orchestrator.session_manager.add_instance(session.session_id, instance2)
        
        # Start execution in background
        execution_task = asyncio.create_task(
            orchestrator.session_manager.execute_session(
                session.session_id,
                [instance1, instance2],
                max_concurrent=2
            )
        )
        
        # Monitor progress
        print("🔄 Monitoring execution progress...")
        while not execution_task.done():
            status = orchestrator.session_manager.get_session_status(session.session_id)
            if status:
                completed = status["task_counts"]["completed"]
                total = status["total_tasks"]
                running = status["task_counts"]["running"]
                
                print(f"   Progress: {completed}/{total} completed, {running} running")
            
            await asyncio.sleep(2)  # Check every 2 seconds
        
        # Get final result
        success = await execution_task
        final_status = orchestrator.session_manager.get_session_status(session.session_id)
        
        if success:
            print("✅ Monitored execution completed!")
            print(f"   Final status: {final_status['status']}")
            print(f"   Completed: {final_status['task_counts']['completed']}")
            print(f"   Failed: {final_status['task_counts']['failed']}")
        else:
            print("❌ Monitored execution failed")
            
    except Exception as e:
        print(f"❌ Error during monitoring: {e}")
        
    finally:
        await orchestrator.shutdown()


if __name__ == "__main__":
    print("Claude Code Trees - Parallel Tasks Examples")
    print("=" * 60)
    
    # Check if we're in a git repository
    if not (Path.cwd() / ".git").exists():
        print("❌ Error: This example must be run from within a git repository.")
        exit(1)
    
    print("\n1. Parallel Tasks Example:")
    anyio.run(parallel_tasks_example)
    
    print("\n" + "=" * 60)
    print("2. Dependent Tasks Example:")
    anyio.run(dependent_tasks_example)
    
    print("\n" + "=" * 60)
    print("3. Execution Monitoring Example:")
    anyio.run(monitor_execution_example)
    
    print("\n🎉 All examples completed!")