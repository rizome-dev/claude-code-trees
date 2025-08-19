#!/usr/bin/env python3
"""
Basic usage example for Claude Code Trees.

This example demonstrates how to:
1. Create an orchestrator
2. Create a Claude Code instance
3. Run a simple task
4. Clean up resources
"""

import anyio
from pathlib import Path

from claude_code_trees import Orchestrator, Config


async def basic_example():
    """Basic usage example."""
    # Set up configuration
    config = Config(
        max_concurrent_instances=2,
        worktree_base_path=Path.cwd() / ".worktrees"
    )
    
    # Initialize orchestrator with your git repository
    repo_path = Path.cwd()  # Current directory should be a git repo
    orchestrator = Orchestrator(str(repo_path), config)
    
    try:
        print("🚀 Creating Claude Code instance...")
        
        # Create a new instance in a worktree
        instance = await orchestrator.create_instance(
            worktree_name="example-worktree",
            branch="example-branch"
        )
        
        print(f"✅ Created instance: {instance.instance_id}")
        print(f"   Worktree: {instance.worktree.name}")
        print(f"   Branch: {instance.worktree.branch}")
        print(f"   Path: {instance.worktree.path}")
        
        # Start the instance
        print("\n🔄 Starting instance...")
        success = await instance.start()
        if success:
            print("✅ Instance started successfully")
        else:
            print("❌ Failed to start instance")
            return
        
        # Run a simple task
        print("\n📝 Running a simple task...")
        task_description = "Create a simple Python hello world script named hello.py"
        
        result = await instance.run_task(task_description)
        
        if result["success"]:
            print("✅ Task completed successfully!")
            if result.get("output"):
                print(f"Output: {result['output']}")
        else:
            print(f"❌ Task failed: {result.get('error', 'Unknown error')}")
        
        # Check if the file was created
        hello_file = instance.worktree.path / "hello.py"
        if hello_file.exists():
            print(f"✅ File created: {hello_file}")
            content = instance.worktree.read_file("hello.py")
            print(f"Content preview: {content[:100]}...")
        else:
            print("❌ Expected file not found")
        
        # Get instance status
        print("\n📊 Instance Status:")
        status = await instance.get_status_info()
        print(f"   Status: {status['status']}")
        print(f"   Running: {status['is_running']}")
        print(f"   Current Branch: {status['current_branch']}")
        print(f"   Has Changes: {status['has_changes']}")
        
        # Commit changes if any
        if status['has_changes']:
            print("\n💾 Committing changes...")
            success = instance.worktree.commit_changes("Add hello world script")
            if success:
                print("✅ Changes committed")
            else:
                print("❌ Failed to commit changes")
        
        # Stop the instance
        print("\n🛑 Stopping instance...")
        await instance.stop()
        print("✅ Instance stopped")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        
    finally:
        # Clean up resources
        print("\n🧹 Cleaning up...")
        await orchestrator.shutdown()
        print("✅ Cleanup completed")


async def health_check_example():
    """Example showing how to perform health checks."""
    config = Config()
    orchestrator = Orchestrator(str(Path.cwd()), config)
    
    try:
        print("🏥 Performing health check...")
        health_info = await orchestrator.health_check()
        
        if health_info["overall_healthy"]:
            print("✅ System is healthy")
        else:
            print("⚠️  System has issues")
        
        print(f"Database: {'✅' if health_info['components']['database']['healthy'] else '❌'}")
        print(f"Worktree Manager: {'✅' if health_info['components']['worktree_manager']['healthy'] else '❌'}")
        print(f"Active Instances: {len(health_info['instances'])}")
        print(f"Active Worktrees: {len(health_info['worktrees'])}")
        
    finally:
        await orchestrator.shutdown()


if __name__ == "__main__":
    print("Claude Code Trees - Basic Usage Example")
    print("=" * 50)
    
    # Check if we're in a git repository
    if not (Path.cwd() / ".git").exists():
        print("❌ Error: This example must be run from within a git repository.")
        print("   Please navigate to your git repository and try again.")
        exit(1)
    
    print("\n1. Basic Usage Example:")
    anyio.run(basic_example)
    
    print("\n" + "=" * 50)
    print("2. Health Check Example:")
    anyio.run(health_check_example)
    
    print("\n🎉 Examples completed!")