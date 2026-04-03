"""
Model Mixins for consistent behavior across all models.
"""
from sqlalchemy import Column, DateTime, Boolean
from datetime import datetime


class SoftDeleteMixin:
    """
    Mixin for soft delete functionality.
    
    Adds:
    - is_active: Boolean flag (True = active, False = deleted)
    - deleted_at: Timestamp when deleted (None = not deleted)
    
    Usage in queries:
        - Active records: .where(Model.is_active == True)
        - Not deleted: .where(Model.deleted_at == None)
        - Both: .where(and_(Model.is_active == True, Model.deleted_at == None))
    
    To soft delete:
        record.is_active = False
        record.deleted_at = datetime.utcnow()
    """
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    
    def soft_delete(self):
        """Mark record as deleted"""
        self.is_active = False
        self.deleted_at = datetime.utcnow()
    
    def restore(self):
        """Restore soft-deleted record"""
        self.is_active = True
        self.deleted_at = None
    
    @property
    def is_deleted(self) -> bool:
        """Check if record is soft deleted"""
        return self.deleted_at is not None or not self.is_active


class TimestampMixin:
    """
    Mixin for created_at and updated_at timestamps.
    """
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
