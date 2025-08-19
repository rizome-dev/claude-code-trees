"""Command-line interface for Claude Code Trees."""

import asyncio
import json
from pathlib import Path

import click
from rich.console import Console
from rich.json import JSON
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .claude_instance import ClaudeInstanceConfig
from .config import Config
from .orchestrator import Orchestrator

console = Console()


@click.group()
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.option('--repo', '-r', type=click.Path(exists=True), help='Base repository path')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.pass_context
def main(ctx: click.Context, config: str | None, repo: str | None, verbose: bool) -> None:
    """Claude Code Trees - Manage Claude Code instances on git worktrees."""
    ctx.ensure_object(dict)

    # Load configuration
    if config:
        ctx.obj['config'] = Config.load_from_file(Path(config))
    else:
        ctx.obj['config'] = Config()

    # Set repository path
    if repo:
        ctx.obj['repo_path'] = repo
    elif Path.cwd().is_dir() and (Path.cwd() / '.git').exists():
        ctx.obj['repo_path'] = str(Path.cwd())
    else:
        console.print("[red]Error: No git repository found. Use --repo to specify path.[/red]")
        ctx.exit(1)

    ctx.obj['verbose'] = verbose

    # Initialize orchestrator
    ctx.obj['orchestrator'] = Orchestrator(ctx.obj['repo_path'], ctx.obj['config'])


@main.command()
@click.option('--name', '-n', help='Worktree/instance name')
@click.option('--branch', '-b', help='Branch name')
@click.option('--base-branch', default='main', help='Base branch to branch from')
@click.option('--model', default='claude-3-sonnet-20240229', help='Claude model to use')
@click.option('--max-tokens', default=4096, type=int, help='Maximum tokens')
@click.option('--start', is_flag=True, help='Start the instance immediately')
@click.pass_context
def create(ctx: click.Context, name: str | None, branch: str | None,
          base_branch: str, model: str, max_tokens: int, start: bool) -> None:
    """Create a new Claude Code instance in a new worktree."""
    async def _create():
        orchestrator: Orchestrator = ctx.obj['orchestrator']

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Creating instance...", total=None)

            try:
                instance_config = ClaudeInstanceConfig(
                    model=model,
                    max_tokens=max_tokens
                )

                instance = await orchestrator.create_instance(
                    worktree_name=name,
                    branch=branch,
                    base_branch=base_branch,
                    instance_config=instance_config
                )

                progress.update(task, description="Instance created successfully")

                if start:
                    progress.update(task, description="Starting instance...")
                    await instance.start()
                    progress.update(task, description="Instance started successfully")

                console.print(f"[green]✓[/green] Instance created: [bold]{instance.instance_id}[/bold]")
                console.print(f"  Worktree: {instance.worktree.name}")
                console.print(f"  Branch: {instance.worktree.branch}")
                console.print(f"  Path: {instance.worktree.path}")
                console.print(f"  Status: {'Running' if instance.is_running else 'Stopped'}")

            except Exception as e:
                progress.update(task, description="Failed to create instance")
                console.print(f"[red]Error creating instance: {e}[/red]")

    asyncio.run(_create())


@main.command()
@click.argument('instance_id')
@click.pass_context
def start(ctx: click.Context, instance_id: str) -> None:
    """Start a Claude Code instance."""
    async def _start():
        orchestrator: Orchestrator = ctx.obj['orchestrator']

        instance = await orchestrator.get_instance(instance_id)
        if not instance:
            console.print(f"[red]Instance {instance_id} not found[/red]")
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Starting instance...", total=None)

            success = await instance.start()
            if success:
                progress.update(task, description="Instance started successfully")
                console.print(f"[green]✓[/green] Instance [bold]{instance_id}[/bold] started")
            else:
                progress.update(task, description="Failed to start instance")
                console.print(f"[red]Failed to start instance {instance_id}[/red]")

    asyncio.run(_start())


@main.command()
@click.argument('instance_id')
@click.option('--timeout', default=10, help='Shutdown timeout in seconds')
@click.pass_context
def stop(ctx: click.Context, instance_id: str, timeout: int) -> None:
    """Stop a Claude Code instance."""
    async def _stop():
        orchestrator: Orchestrator = ctx.obj['orchestrator']

        instance = await orchestrator.get_instance(instance_id)
        if not instance:
            console.print(f"[red]Instance {instance_id} not found[/red]")
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Stopping instance...", total=None)

            success = await instance.stop(timeout)
            if success:
                progress.update(task, description="Instance stopped successfully")
                console.print(f"[green]✓[/green] Instance [bold]{instance_id}[/bold] stopped")
            else:
                progress.update(task, description="Failed to stop instance")
                console.print(f"[red]Failed to stop instance {instance_id}[/red]")

    asyncio.run(_stop())


@main.command()
@click.option('--verbose', '-v', is_flag=True, help='Show detailed information')
@click.pass_context
def list(ctx: click.Context, verbose: bool) -> None:
    """List all Claude Code instances."""
    async def _list():
        orchestrator: Orchestrator = ctx.obj['orchestrator']

        instances = await orchestrator.list_instances()

        if not instances:
            console.print("No instances found")
            return

        table = Table(title="Claude Code Instances")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Worktree", style="green")
        table.add_column("Branch", style="yellow")
        table.add_column("Status", style="magenta")

        if verbose:
            table.add_column("Path", style="blue")
            table.add_column("PID", style="red")
            table.add_column("Changes", style="orange1")

        for instance_info in instances:
            row = [
                instance_info["instance_id"][:12] + "...",
                instance_info["worktree"],
                instance_info["current_branch"],
                instance_info["status"]
            ]

            if verbose:
                row.extend([
                    str(instance_info["worktree_path"]),
                    str(instance_info.get("pid", "N/A")),
                    "Yes" if instance_info["has_changes"] else "No"
                ])

            table.add_row(*row)

        console.print(table)

    asyncio.run(_list())


@main.command()
@click.argument('instance_id')
@click.argument('task_description')
@click.option('--context', '-c', help='JSON context for the task')
@click.pass_context
def run_task(ctx: click.Context, instance_id: str, task_description: str,
            context: str | None) -> None:
    """Run a task on a specific Claude Code instance."""
    async def _run_task():
        orchestrator: Orchestrator = ctx.obj['orchestrator']

        instance = await orchestrator.get_instance(instance_id)
        if not instance:
            console.print(f"[red]Instance {instance_id} not found[/red]")
            return

        # Parse context if provided
        task_context = {}
        if context:
            try:
                task_context = json.loads(context)
            except json.JSONDecodeError:
                console.print("[red]Invalid JSON context[/red]")
                return

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Running task...", total=None)

            result = await instance.run_task(task_description, task_context)

            if result.get("success"):
                progress.update(task, description="Task completed successfully")
                console.print(f"[green]✓[/green] Task completed on instance [bold]{instance_id}[/bold]")

                if result.get("output"):
                    console.print("\n[bold]Output:[/bold]")
                    console.print(result["output"])
            else:
                progress.update(task, description="Task failed")
                console.print(f"[red]Task failed on instance {instance_id}[/red]")

                if result.get("error"):
                    console.print(f"[red]Error: {result['error']}[/red]")

    asyncio.run(_run_task())


@main.command()
@click.argument('tasks_file', type=click.File('r'))
@click.option('--session-name', default='parallel_tasks', help='Session name')
@click.option('--max-concurrent', type=int, help='Maximum concurrent tasks')
@click.pass_context
def parallel(ctx: click.Context, tasks_file, session_name: str,
            max_concurrent: int | None) -> None:
    """Run tasks in parallel from a JSON file."""
    async def _parallel():
        orchestrator: Orchestrator = ctx.obj['orchestrator']

        try:
            tasks = json.load(tasks_file)
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON file: {e}[/red]")
            return

        if not isinstance(tasks, list):
            console.print("[red]Tasks file must contain a list of tasks[/red]")
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"Running {len(tasks)} tasks in parallel...", total=None)

            result = await orchestrator.run_parallel_tasks(
                tasks=tasks,
                session_name=session_name,
                max_concurrent=max_concurrent
            )

            if result["success"]:
                progress.update(task, description="All tasks completed")
                console.print("[green]✓[/green] Parallel execution completed")
                console.print(f"Session ID: {result['session_id']}")
                console.print(f"Instances used: {result['instances_used']}")

                # Show task results summary
                status = result["status"]
                if status:
                    task_counts = status["task_counts"]
                    console.print("\nTask Results:")
                    console.print(f"  Completed: {task_counts['completed']}")
                    console.print(f"  Failed: {task_counts['failed']}")
            else:
                progress.update(task, description="Parallel execution failed")
                console.print("[red]Parallel execution failed[/red]")

    asyncio.run(_parallel())


@main.command()
@click.pass_context
def health(ctx: click.Context) -> None:
    """Perform a health check on all components."""
    async def _health():
        orchestrator: Orchestrator = ctx.obj['orchestrator']

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Performing health check...", total=None)

            health_info = await orchestrator.health_check()
            progress.update(task, description="Health check completed")

            if health_info["overall_healthy"]:
                console.print("[green]✓[/green] System is healthy")
            else:
                console.print("[red]⚠[/red] System has issues")

            if ctx.obj['verbose']:
                console.print("\nDetailed Health Information:")
                console.print(JSON.from_data(health_info))

    asyncio.run(_health())


@main.command()
@click.option('--max-age-hours', default=24, type=int, help='Maximum age in hours before cleanup')
@click.pass_context
def cleanup(ctx: click.Context, max_age_hours: int) -> None:
    """Clean up old resources and inactive instances."""
    async def _cleanup():
        orchestrator: Orchestrator = ctx.obj['orchestrator']

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Cleaning up resources...", total=None)

            results = await orchestrator.cleanup(max_age_hours)
            progress.update(task, description="Cleanup completed")

            console.print("[green]✓[/green] Cleanup completed")
            console.print(f"Worktrees cleaned: {len(results['worktrees_cleaned'])}")
            console.print(f"Instances stopped: {len(results['instances_stopped'])}")

            if ctx.obj['verbose'] and results['worktrees_cleaned']:
                console.print(f"Cleaned worktrees: {results['worktrees_cleaned']}")

    asyncio.run(_cleanup())


@main.command()
@click.argument('instance_id')
@click.option('--remove-worktree', is_flag=True, help='Also remove the worktree')
@click.pass_context
def remove(ctx: click.Context, instance_id: str, remove_worktree: bool) -> None:
    """Remove a Claude Code instance."""
    async def _remove():
        orchestrator: Orchestrator = ctx.obj['orchestrator']

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Removing instance...", total=None)

            success = await orchestrator.remove_instance(instance_id, remove_worktree)

            if success:
                progress.update(task, description="Instance removed successfully")
                console.print(f"[green]✓[/green] Instance [bold]{instance_id}[/bold] removed")
                if remove_worktree:
                    console.print("  Worktree also removed")
            else:
                progress.update(task, description="Failed to remove instance")
                console.print(f"[red]Failed to remove instance {instance_id}[/red]")

    asyncio.run(_remove())


if __name__ == '__main__':
    main()
