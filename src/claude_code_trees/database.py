"""Database layer for Claude Code Trees using SQLAlchemy."""

import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

Base = declarative_base()


class WorktreeModel(Base):
    """Database model for worktrees."""
    __tablename__ = "worktrees"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    path = Column(String(512), nullable=False)
    branch = Column(String(255), nullable=False)
    base_repo_path = Column(String(512), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.datetime.utcnow)
    is_active = Column(Boolean, default=True)
    metadata_json = Column(Text, nullable=True)  # JSON string for additional metadata


class ClaudeInstanceModel(Base):
    """Database model for Claude Code instances."""
    __tablename__ = "claude_instances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instance_id = Column(String(255), unique=True, nullable=False)
    worktree_name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)  # active, idle, stopped, error
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.datetime.utcnow)
    config_json = Column(Text, nullable=True)  # JSON string for instance configuration
    pid = Column(Integer, nullable=True)  # Process ID if applicable


class SessionModel(Base):
    """Database model for sessions."""
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False)  # active, completed, failed, paused
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                       onupdate=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    data_json = Column(Text, nullable=True)  # JSON string for session data


class TaskModel(Base):
    """Database model for tasks within sessions."""
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(255), unique=True, nullable=False)
    session_id = Column(String(255), nullable=False)
    instance_id = Column(String(255), nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False)  # pending, running, completed, failed
    priority = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    result_json = Column(Text, nullable=True)  # JSON string for task results
    error_message = Column(Text, nullable=True)


class Database:
    """Database interface for Claude Code Trees."""

    def __init__(self, database_url: str = "sqlite:///claude_code_trees.db"):
        """Initialize database connection."""
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False,
                                        bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

    def get_session(self) -> Session:
        """Get database session."""
        return self.SessionLocal()

    def create_worktree(self, name: str, path: str, branch: str,
                       base_repo_path: str, metadata: str | None = None) -> WorktreeModel:
        """Create a new worktree record."""
        with self.get_session() as session:
            worktree = WorktreeModel(
                name=name,
                path=path,
                branch=branch,
                base_repo_path=base_repo_path,
                metadata_json=metadata
            )
            session.add(worktree)
            session.commit()
            session.refresh(worktree)
            return worktree

    def get_worktree(self, name: str) -> WorktreeModel | None:
        """Get worktree by name."""
        with self.get_session() as session:
            return session.query(WorktreeModel).filter(WorktreeModel.name == name).first()

    def list_worktrees(self, active_only: bool = True) -> list[WorktreeModel]:
        """List all worktrees."""
        with self.get_session() as session:
            query = session.query(WorktreeModel)
            if active_only:
                query = query.filter(WorktreeModel.is_active == True)
            return query.all()

    def update_worktree_access_time(self, name: str) -> bool:
        """Update last accessed time for worktree."""
        with self.get_session() as session:
            worktree = session.query(WorktreeModel).filter(WorktreeModel.name == name).first()
            if worktree:
                worktree.last_accessed = datetime.datetime.utcnow()
                session.commit()
                return True
            return False

    def delete_worktree(self, name: str) -> bool:
        """Delete worktree record."""
        with self.get_session() as session:
            worktree = session.query(WorktreeModel).filter(WorktreeModel.name == name).first()
            if worktree:
                session.delete(worktree)
                session.commit()
                return True
            return False

    def create_claude_instance(self, instance_id: str, worktree_name: str,
                              status: str = "idle", config: str | None = None,
                              pid: int | None = None) -> ClaudeInstanceModel:
        """Create a new Claude instance record."""
        with self.get_session() as session:
            instance = ClaudeInstanceModel(
                instance_id=instance_id,
                worktree_name=worktree_name,
                status=status,
                config_json=config,
                pid=pid
            )
            session.add(instance)
            session.commit()
            session.refresh(instance)
            return instance

    def get_claude_instance(self, instance_id: str) -> ClaudeInstanceModel | None:
        """Get Claude instance by ID."""
        with self.get_session() as session:
            return session.query(ClaudeInstanceModel).filter(
                ClaudeInstanceModel.instance_id == instance_id
            ).first()

    def list_claude_instances(self, status: str | None = None) -> list[ClaudeInstanceModel]:
        """List Claude instances, optionally filtered by status."""
        with self.get_session() as session:
            query = session.query(ClaudeInstanceModel)
            if status:
                query = query.filter(ClaudeInstanceModel.status == status)
            return query.all()

    def update_claude_instance_status(self, instance_id: str, status: str) -> bool:
        """Update Claude instance status."""
        with self.get_session() as session:
            instance = session.query(ClaudeInstanceModel).filter(
                ClaudeInstanceModel.instance_id == instance_id
            ).first()
            if instance:
                instance.status = status
                instance.last_activity = datetime.datetime.utcnow()
                session.commit()
                return True
            return False

    def delete_claude_instance(self, instance_id: str) -> bool:
        """Delete Claude instance record."""
        with self.get_session() as session:
            instance = session.query(ClaudeInstanceModel).filter(
                ClaudeInstanceModel.instance_id == instance_id
            ).first()
            if instance:
                session.delete(instance)
                session.commit()
                return True
            return False

    def create_session(self, session_id: str, name: str, description: str | None = None,
                      data: str | None = None) -> SessionModel:
        """Create a new session record."""
        with self.get_session() as db_session:
            session_model = SessionModel(
                session_id=session_id,
                name=name,
                description=description,
                status="active",
                data_json=data
            )
            db_session.add(session_model)
            db_session.commit()
            db_session.refresh(session_model)
            return session_model

    def get_session_model(self, session_id: str) -> SessionModel | None:
        """Get session by ID."""
        with self.get_session() as session:
            return session.query(SessionModel).filter(
                SessionModel.session_id == session_id
            ).first()

    def update_session_status(self, session_id: str, status: str,
                             completed_at: datetime.datetime | None = None) -> bool:
        """Update session status."""
        with self.get_session() as db_session:
            session_model = db_session.query(SessionModel).filter(
                SessionModel.session_id == session_id
            ).first()
            if session_model:
                session_model.status = status
                session_model.updated_at = datetime.datetime.utcnow()
                if completed_at:
                    session_model.completed_at = completed_at
                db_session.commit()
                return True
            return False
