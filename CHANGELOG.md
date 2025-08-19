# Changelog

All notable changes to Claude Code Trees will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2024-01-19

### Added
- Comprehensive error handling for all Claude Code SDK errors
- Retry logic with exponential backoff for transient failures
- Structured logging throughout the codebase
- Thread-safe operations with async locks
- Production-ready features and hardening
- Architecture documentation in README
- Comprehensive test coverage (96 tests, all passing)

### Changed
- Updated to use real claude-code-sdk package (v0.0.20+)
- Migrated from Pydantic v1 to v2 syntax
- Updated SQLAlchemy imports to use non-deprecated modules
- Improved test mocking strategies
- Enhanced documentation to reflect production status

### Fixed
- All test failures (8 failing tests now passing)
- Property mocking issues in tests
- Deprecated Pydantic method calls (.json() → .model_dump_json())
- Deprecated SQLAlchemy imports
- Datetime mocking in orchestrator tests

### Removed
- Conceptual framework disclaimer from README
- Placeholder/mocked SDK implementations

## [0.1.0] - 2024-01-18

### Added
- Initial implementation of Claude Code Trees
- Orchestrator for managing multiple Claude instances
- ClaudeCodeInstance wrapper for Claude SDK
- WorktreeManager for git worktree operations
- SessionManager for persistent task management
- Database layer with SQLAlchemy
- CLI interface with Click
- Basic examples and documentation

### Dependencies
- claude-code-sdk (>=0.0.20)
- anyio (>=4.0.0)
- GitPython (>=3.1.40)
- SQLAlchemy (>=2.0.0)
- Pydantic (>=2.0.0)
- Click (>=8.0.0)
- Rich (>=13.0.0)