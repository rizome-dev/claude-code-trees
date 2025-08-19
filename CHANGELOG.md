# Changelog

All notable changes to Claude Code Trees will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-01-19

### Added
- Initial production-ready implementation of Claude Code Trees
- Orchestrator for managing multiple Claude instances across git worktrees
- ClaudeCodeInstance wrapper for Claude SDK with retry logic and error handling
- WorktreeManager for git worktree operations
- SessionManager for persistent task management with dependencies
- Database layer with SQLAlchemy for state persistence
- CLI interface with Click for command-line operations
- Comprehensive error handling for all Claude Code SDK errors
- Retry logic with exponential backoff for transient failures
- Structured logging throughout the codebase
- Thread-safe operations with async locks
- Full test suite with 96 tests (all passing)
- Complete documentation with architecture diagrams
- Example scripts for common use cases
- GitHub Actions workflow for PyPI publishing

### Features
- Parallel execution of Claude instances in isolated worktrees
- Task orchestration with dependency management
- Persistent sessions with save/resume capability
- Health monitoring and resource cleanup
- Both CLI and Python API interfaces

### Dependencies
- claude-code-sdk (>=0.0.20)
- anyio (>=4.0.0)
- GitPython (>=3.1.40)
- SQLAlchemy (>=2.0.0)
- Pydantic (>=2.0.0)
- Click (>=8.0.0)
- Rich (>=13.0.0)