#!/usr/bin/env python3
"""
Advanced orchestration example for Claude Code Trees.

This example demonstrates:
1. Complex multi-stage workflows
2. Dynamic instance scaling
3. Error handling and recovery
4. Custom instance configurations
5. Resource management and cleanup
6. Integration with external systems
"""

import asyncio
import anyio
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Any

from claude_code_trees import Orchestrator, Config, ClaudeInstanceConfig


# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AdvancedOrchestrationDemo:
    """Demonstrates advanced orchestration patterns."""
    
    def __init__(self):
        """Initialize the demo with configuration."""
        self.config = Config(
            max_concurrent_instances=5,
            instance_timeout=900,  # 15 minutes
            worktree_base_path=Path.cwd() / ".worktrees",
            auto_save_interval=30
        )
        
        self.orchestrator = Orchestrator(str(Path.cwd()), self.config)
        self.metrics = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "instances_created": 0,
            "total_execution_time": 0
        }
    
    async def run_multi_stage_workflow(self):
        """Run a complex multi-stage development workflow."""
        logger.info("🏗️  Starting multi-stage workflow")
        
        # Define a complex workflow with multiple stages
        workflow_stages = [
            {
                "stage": "Analysis",
                "parallel": True,
                "tasks": [
                    {
                        "name": "Code Analysis",
                        "description": "Analyze codebase for potential issues using static analysis",
                        "priority": 1,
                        "instance_config": ClaudeInstanceConfig(
                            system_prompt="Focus on code quality, security, and performance issues",
                            allowed_tools=["Read", "Write", "Bash", "Edit", "Glob", "Grep"]
                        )
                    },
                    {
                        "name": "Dependency Audit",
                        "description": "Audit project dependencies for security vulnerabilities",
                        "priority": 1,
                        "instance_config": ClaudeInstanceConfig(
                            system_prompt="Focus on security vulnerabilities and license compliance",
                            allowed_tools=["Read", "Write", "Bash", "Edit", "Glob", "Grep"]
                        )
                    }
                ]
            },
            {
                "stage": "Implementation", 
                "parallel": True,
                "dependencies": ["Analysis"],
                "tasks": [
                    {
                        "name": "Fix Critical Issues",
                        "description": "Fix critical issues found during code analysis",
                        "priority": 1,
                        "dependencies": ["Code Analysis"]
                    },
                    {
                        "name": "Update Dependencies",
                        "description": "Update vulnerable dependencies identified in audit",
                        "priority": 2,
                        "dependencies": ["Dependency Audit"]
                    },
                    {
                        "name": "Add Security Headers",
                        "description": "Implement security best practices and headers",
                        "priority": 2
                    }
                ]
            },
            {
                "stage": "Testing",
                "parallel": True,
                "dependencies": ["Implementation"],
                "tasks": [
                    {
                        "name": "Unit Tests",
                        "description": "Create comprehensive unit tests for all modules",
                        "priority": 1,
                        "instance_config": ClaudeInstanceConfig(
                            system_prompt="Focus on test coverage and edge cases",
                            allowed_tools=["Read", "Write", "Bash", "Edit", "Glob", "Grep"]
                        )
                    },
                    {
                        "name": "Integration Tests", 
                        "description": "Create integration tests for API endpoints",
                        "priority": 1
                    },
                    {
                        "name": "Performance Tests",
                        "description": "Create performance benchmarks and load tests",
                        "priority": 2
                    }
                ]
            },
            {
                "stage": "Documentation",
                "parallel": False,
                "dependencies": ["Testing"],
                "tasks": [
                    {
                        "name": "API Documentation",
                        "description": "Generate comprehensive API documentation",
                        "priority": 1
                    },
                    {
                        "name": "User Guide",
                        "description": "Create user guide with examples and tutorials",
                        "priority": 2
                    }
                ]
            }
        ]
        
        start_time = time.time()
        
        try:
            # Execute each stage
            stage_results = {}
            for stage_info in workflow_stages:
                stage_name = stage_info["stage"]
                logger.info(f"📋 Starting stage: {stage_name}")
                
                # Check dependencies
                if "dependencies" in stage_info:
                    for dep_stage in stage_info["dependencies"]:
                        if dep_stage not in stage_results or not stage_results[dep_stage]["success"]:
                            logger.error(f"❌ Stage {stage_name} failed: dependency {dep_stage} not completed")
                            stage_results[stage_name] = {"success": False, "error": f"Dependency {dep_stage} failed"}
                            continue
                
                # Execute stage tasks
                if stage_info.get("parallel", True):
                    result = await self._execute_parallel_stage(stage_info)
                else:
                    result = await self._execute_sequential_stage(stage_info)
                
                stage_results[stage_name] = result
                
                if result["success"]:
                    logger.info(f"✅ Stage {stage_name} completed successfully")
                else:
                    logger.error(f"❌ Stage {stage_name} failed: {result.get('error', 'Unknown error')}")
                    # Decide whether to continue or abort
                    if stage_info.get("critical", True):
                        logger.error("💥 Critical stage failed, aborting workflow")
                        break
            
            # Calculate overall success
            successful_stages = sum(1 for result in stage_results.values() if result["success"])
            total_stages = len(workflow_stages)
            
            execution_time = time.time() - start_time
            self.metrics["total_execution_time"] += execution_time
            
            logger.info(f"🏁 Multi-stage workflow completed")
            logger.info(f"   Success Rate: {successful_stages}/{total_stages} stages")
            logger.info(f"   Execution Time: {execution_time:.2f}s")
            
            return {
                "success": successful_stages == total_stages,
                "stages": stage_results,
                "execution_time": execution_time,
                "success_rate": successful_stages / total_stages
            }
            
        except Exception as e:
            logger.error(f"💥 Multi-stage workflow failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _execute_parallel_stage(self, stage_info: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a stage with parallel tasks."""
        tasks = stage_info["tasks"]
        stage_name = stage_info["stage"]
        
        # Create custom instances for tasks that need them
        instances = []
        for i, task in enumerate(tasks):
            instance_config = task.get("instance_config")
            instance = await self.orchestrator.create_instance(
                worktree_name=f"{stage_name.lower()}-task-{i}",
                branch=f"{stage_name.lower()}-task-{i}-branch",
                instance_config=instance_config
            )
            instances.append(instance)
            self.metrics["instances_created"] += 1
        
        # Execute tasks in parallel
        result = await self.orchestrator.run_parallel_tasks(
            tasks=tasks,
            session_name=f"{stage_name} Stage",
            max_concurrent=min(len(tasks), self.config.max_concurrent_instances)
        )
        
        return result
    
    async def _execute_sequential_stage(self, stage_info: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a stage with sequential tasks."""
        tasks = stage_info["tasks"]
        stage_name = stage_info["stage"]
        
        result = await self.orchestrator.run_sequential_workflow(
            workflow=tasks,
            session_name=f"{stage_name} Sequential Stage"
        )
        
        return result
    
    async def demonstrate_dynamic_scaling(self):
        """Demonstrate dynamic instance scaling based on workload."""
        logger.info("📈 Demonstrating dynamic scaling")
        
        # Simulate varying workload
        workloads = [
            {"name": "Light Load", "task_count": 2, "expected_instances": 2},
            {"name": "Medium Load", "task_count": 5, "expected_instances": 3},
            {"name": "Heavy Load", "task_count": 8, "expected_instances": 5},
            {"name": "Peak Load", "task_count": 12, "expected_instances": 5},  # Capped by max_concurrent
        ]
        
        for workload in workloads:
            logger.info(f"🔄 Testing {workload['name']}: {workload['task_count']} tasks")
            
            # Generate tasks
            tasks = []
            for i in range(workload['task_count']):
                tasks.append({
                    "name": f"Task {i+1}",
                    "description": f"Process item {i+1} with scaling demo",
                    "priority": 1
                })
            
            # Record initial instance count
            initial_instances = len(await self.orchestrator.list_instances())
            
            # Execute workload
            result = await self.orchestrator.run_parallel_tasks(
                tasks=tasks,
                session_name=f"Dynamic Scaling - {workload['name']}",
                max_concurrent=workload['expected_instances']
            )
            
            # Record peak instance count
            peak_instances = len(await self.orchestrator.list_instances())
            
            logger.info(f"   Initial instances: {initial_instances}")
            logger.info(f"   Peak instances: {peak_instances}")
            logger.info(f"   Expected: {workload['expected_instances']}")
            logger.info(f"   Success: {result['success']}")
            
            # Clean up for next workload
            await self.orchestrator.cleanup(max_age_hours=0)
            await asyncio.sleep(1)  # Brief pause between workloads
    
    async def demonstrate_error_handling(self):
        """Demonstrate error handling and recovery strategies."""
        logger.info("🛠️  Demonstrating error handling and recovery")
        
        # Tasks designed to test different failure scenarios
        error_test_tasks = [
            {
                "name": "Invalid Command Test",
                "description": "Run an intentionally invalid command to test error handling",
                "expected_failure": True
            },
            {
                "name": "Timeout Test", 
                "description": "Run a task that should timeout",
                "timeout": 5,  # Very short timeout
                "expected_failure": True
            },
            {
                "name": "Recovery Test",
                "description": "Create a simple file after previous failures",
                "expected_failure": False
            }
        ]
        
        recovery_strategies = []
        
        for task in error_test_tasks:
            logger.info(f"🧪 Testing: {task['name']}")
            
            try:
                instance = await self.orchestrator.create_instance(
                    worktree_name=f"error-test-{task['name'].lower().replace(' ', '-')}"
                )
                await instance.start()
                
                # Execute task
                result = await instance.run_task(
                    task["description"],
                    timeout=task.get("timeout")
                )
                
                # Analyze result
                failed_as_expected = not result["success"] and task["expected_failure"]
                succeeded_as_expected = result["success"] and not task["expected_failure"]
                
                if failed_as_expected:
                    logger.info(f"✅ {task['name']}: Failed as expected")
                    recovery_strategies.append(f"Handled failure in {task['name']}")
                elif succeeded_as_expected:
                    logger.info(f"✅ {task['name']}: Succeeded as expected")
                else:
                    logger.warning(f"⚠️  {task['name']}: Unexpected result")
                
                # Health check after each task
                health = await instance.health_check()
                if not health["healthy"]:
                    logger.warning(f"⚠️  Instance unhealthy after {task['name']}: {health['issues']}")
                    # Attempt recovery
                    await instance.stop()
                    await instance.start()
                    recovery_strategies.append(f"Restarted instance after {task['name']}")
                
            except Exception as e:
                if task["expected_failure"]:
                    logger.info(f"✅ {task['name']}: Exception caught as expected: {e}")
                else:
                    logger.error(f"❌ {task['name']}: Unexpected exception: {e}")
                
                recovery_strategies.append(f"Exception handling for {task['name']}")
        
        logger.info(f"🛡️  Recovery strategies used: {len(recovery_strategies)}")
        for strategy in recovery_strategies:
            logger.info(f"   • {strategy}")
    
    async def demonstrate_resource_management(self):
        """Demonstrate advanced resource management techniques."""
        logger.info("💾 Demonstrating resource management")
        
        # Monitor resource usage
        initial_health = await self.orchestrator.health_check()
        logger.info(f"Initial state: {len(initial_health['instances'])} instances, {len(initial_health['worktrees'])} worktrees")
        
        # Create multiple instances with different lifespans
        logger.info("🏗️  Creating instances with different lifespans...")
        
        short_lived_instances = []
        long_lived_instances = []
        
        # Short-lived instances (will be cleaned up quickly)
        for i in range(3):
            instance = await self.orchestrator.create_instance(
                worktree_name=f"short-lived-{i}",
                branch=f"short-{i}"
            )
            short_lived_instances.append(instance)
            
            # Run a quick task
            await instance.run_task(f"Create temporary file {i}")
        
        # Long-lived instances (will persist longer)
        for i in range(2):
            instance = await self.orchestrator.create_instance(
                worktree_name=f"long-lived-{i}",
                branch=f"long-{i}"
            )
            long_lived_instances.append(instance)
            
            # Run a more substantial task
            await instance.run_task(f"Create project structure {i}")
        
        # Check resource usage
        mid_health = await self.orchestrator.health_check()
        logger.info(f"Peak usage: {len(mid_health['instances'])} instances, {len(mid_health['worktrees'])} worktrees")
        
        # Demonstrate selective cleanup
        logger.info("🧹 Performing selective cleanup...")
        
        # Clean up short-lived instances manually
        for instance in short_lived_instances:
            await self.orchestrator.remove_instance(instance.instance_id, remove_worktree=True)
        
        # Use automatic cleanup for older resources
        cleanup_results = await self.orchestrator.cleanup(max_age_hours=0)
        logger.info(f"Automatic cleanup results: {cleanup_results}")
        
        # Final resource check
        final_health = await self.orchestrator.health_check()
        logger.info(f"After cleanup: {len(final_health['instances'])} instances, {len(final_health['worktrees'])} worktrees")
        
        # Keep long-lived instances for a bit longer, then clean up
        await asyncio.sleep(2)
        for instance in long_lived_instances:
            await self.orchestrator.remove_instance(instance.instance_id, remove_worktree=True)
        
        logger.info("✅ Resource management demonstration completed")
    
    async def generate_execution_report(self) -> Dict[str, Any]:
        """Generate a comprehensive execution report."""
        health_info = await self.orchestrator.health_check()
        
        report = {
            "execution_time": self.metrics["total_execution_time"],
            "tasks_completed": self.metrics["tasks_completed"],
            "tasks_failed": self.metrics["tasks_failed"],
            "instances_created": self.metrics["instances_created"],
            "system_health": health_info["overall_healthy"],
            "active_instances": len(health_info["instances"]),
            "active_worktrees": len(health_info["worktrees"]),
            "success_rate": (
                self.metrics["tasks_completed"] / 
                max(1, self.metrics["tasks_completed"] + self.metrics["tasks_failed"])
            ),
            "timestamp": time.time()
        }
        
        return report
    
    async def cleanup(self):
        """Clean up all resources."""
        logger.info("🧹 Final cleanup...")
        await self.orchestrator.cleanup(max_age_hours=0)
        await self.orchestrator.shutdown()
        logger.info("✅ Cleanup completed")


async def main():
    """Run the advanced orchestration demonstration."""
    print("Claude Code Trees - Advanced Orchestration Demo")
    print("=" * 60)
    
    # Check if we're in a git repository
    if not (Path.cwd() / ".git").exists():
        print("❌ Error: This demo must be run from within a git repository.")
        exit(1)
    
    demo = AdvancedOrchestrationDemo()
    
    try:
        # Run all demonstrations
        logger.info("🚀 Starting advanced orchestration demonstrations...")
        
        # Multi-stage workflow
        workflow_result = await demo.run_multi_stage_workflow()
        logger.info(f"Multi-stage workflow result: {workflow_result['success']}")
        
        # Dynamic scaling
        await demo.demonstrate_dynamic_scaling()
        
        # Error handling
        await demo.demonstrate_error_handling()
        
        # Resource management
        await demo.demonstrate_resource_management()
        
        # Generate final report
        report = await demo.generate_execution_report()
        
        logger.info("📊 Final Execution Report:")
        logger.info(f"   Total Execution Time: {report['execution_time']:.2f}s")
        logger.info(f"   Tasks Completed: {report['tasks_completed']}")
        logger.info(f"   Tasks Failed: {report['tasks_failed']}")
        logger.info(f"   Instances Created: {report['instances_created']}")
        logger.info(f"   Success Rate: {report['success_rate']:.2%}")
        logger.info(f"   System Healthy: {report['system_health']}")
        
        print("\n🎉 Advanced orchestration demonstration completed!")
        
    except Exception as e:
        logger.error(f"💥 Demo failed: {e}")
        
    finally:
        await demo.cleanup()


if __name__ == "__main__":
    anyio.run(main)