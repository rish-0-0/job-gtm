from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.sql import func
from database import Base

class WorkflowRun(Base):
    """
    Model for tracking Temporal workflow runs
    """
    __tablename__ = "workflow_runs"

    id = Column(Integer, primary_key=True, index=True)

    # Workflow identification
    workflow_id = Column(String(255), unique=True, nullable=False, index=True)
    run_id = Column(String(255), nullable=False)
    workflow_type = Column(String(100), nullable=False, index=True)  # scrape, ai, etc.

    # Workflow status
    status = Column(String(50), nullable=False, index=True)  # started, running, completed, failed

    # Workflow parameters and results
    input_params = Column(JSON)
    result = Column(JSON)
    error_message = Column(Text)

    # Timing
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<WorkflowRun(id={self.id}, workflow_id={self.workflow_id}, status={self.status})>"
