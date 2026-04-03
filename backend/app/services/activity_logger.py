"""
Activity Logger Service - Tracks all user actions for auditing and debugging
"""
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Any, Dict
from datetime import datetime
from app.models import UserActivityLog


class ActivityLogger:
    """
    Service for logging user activities.
    All actions are logged to user_activity_logs table.
    """
    
    def __init__(self, db: AsyncSession, user_id: int, company_id: Optional[int] = None):
        self.db = db
        self.user_id = user_id
        self.company_id = company_id
        self.ip_address: Optional[str] = None
        self.user_agent: Optional[str] = None
    
    def set_request_info(self, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Set request metadata for logs"""
        self.ip_address = ip_address
        self.user_agent = user_agent
        return self
    
    async def log(
        self,
        action: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> UserActivityLog:
        """
        Log a user activity.
        
        Args:
            action: The action performed (create, update, delete, export, import, enrich, view, etc.)
            entity_type: Type of entity (prospect, dataset, document, company, etc.)
            entity_id: ID of the affected entity
            details: Additional context (changes, counts, etc.)
        
        Returns:
            The created activity log entry
        """
        log_entry = UserActivityLog(
            user_id=self.user_id,
            company_id=self.company_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=self.ip_address,
            user_agent=self.user_agent,
            created_at=datetime.utcnow()
        )
        
        self.db.add(log_entry)
        # Don't commit here - let the caller handle the transaction
        return log_entry
    
    # ============ Convenience methods ============
    
    async def log_create(
        self,
        entity_type: str,
        entity_id: int,
        details: Optional[Dict[str, Any]] = None
    ) -> UserActivityLog:
        """Log a create action"""
        return await self.log("create", entity_type, entity_id, details)
    
    async def log_update(
        self,
        entity_type: str,
        entity_id: int,
        changes: Optional[Dict[str, Any]] = None
    ) -> UserActivityLog:
        """Log an update action with changes"""
        return await self.log("update", entity_type, entity_id, {"changes": changes} if changes else None)
    
    async def log_delete(
        self,
        entity_type: str,
        entity_id: int,
        details: Optional[Dict[str, Any]] = None
    ) -> UserActivityLog:
        """Log a delete action"""
        return await self.log("delete", entity_type, entity_id, details)
    
    async def log_export(
        self,
        entity_type: str,
        count: int,
        destination: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> UserActivityLog:
        """Log an export action"""
        export_details = {"count": count}
        if destination:
            export_details["destination"] = destination
        if details:
            export_details.update(details)
        return await self.log("export", entity_type, None, export_details)
    
    async def log_import(
        self,
        entity_type: str,
        count: int,
        source: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> UserActivityLog:
        """Log an import action"""
        import_details = {"count": count}
        if source:
            import_details["source"] = source
        if details:
            import_details.update(details)
        return await self.log("import", entity_type, None, import_details)
    
    async def log_enrich(
        self,
        entity_type: str,
        count: int,
        model: Optional[str] = None,
        template_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> UserActivityLog:
        """Log an enrichment action"""
        enrich_details = {"count": count}
        if model:
            enrich_details["model"] = model
        if template_id:
            enrich_details["template_id"] = template_id
        if details:
            enrich_details.update(details)
        return await self.log("enrich", entity_type, None, enrich_details)
    
    async def log_bulk_action(
        self,
        action: str,
        entity_type: str,
        count: int,
        entity_ids: Optional[list] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> UserActivityLog:
        """Log a bulk action affecting multiple entities"""
        bulk_details = {"count": count}
        if entity_ids and len(entity_ids) <= 100:  # Only include IDs if not too many
            bulk_details["entity_ids"] = entity_ids
        if details:
            bulk_details.update(details)
        return await self.log(action, entity_type, None, bulk_details)


def get_activity_logger(
    db: AsyncSession,
    user_id: int,
    company_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> ActivityLogger:
    """
    Factory function to create an ActivityLogger instance.
    
    Usage:
        logger = get_activity_logger(db, user.id, company.id, request.client.host)
        await logger.log_create("prospect", prospect.id, {"email": prospect.email})
    """
    logger = ActivityLogger(db, user_id, company_id)
    logger.set_request_info(ip_address, user_agent)
    return logger
