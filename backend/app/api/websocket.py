from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json
import asyncio
import logging
import time

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        # Map of job_id -> set of websocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        # Map of dataset_id -> set of websocket connections
        self.dataset_connections: Dict[int, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, job_id: int = None, dataset_id: int = None):
        await websocket.accept()
        
        if job_id:
            if job_id not in self.active_connections:
                self.active_connections[job_id] = set()
            self.active_connections[job_id].add(websocket)
        
        if dataset_id:
            if dataset_id not in self.dataset_connections:
                self.dataset_connections[dataset_id] = set()
            self.dataset_connections[dataset_id].add(websocket)
    
    def disconnect(self, websocket: WebSocket, job_id: int = None, dataset_id: int = None):
        if job_id and job_id in self.active_connections:
            self.active_connections[job_id].discard(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]
        
        if dataset_id and dataset_id in self.dataset_connections:
            self.dataset_connections[dataset_id].discard(websocket)
            if not self.dataset_connections[dataset_id]:
                del self.dataset_connections[dataset_id]
    
    async def broadcast_job_progress(self, job_id: int, data: dict):
        """Broadcast job progress to all connected clients"""
        if job_id not in self.active_connections:
            # No clients connected for this job - this is normal
            return
        
        connection_count = len(self.active_connections[job_id])
        dead_connections = set()
        
        for connection in self.active_connections[job_id]:
            try:
                await connection.send_json(data)
            except Exception as e:
                logger.debug(f"WebSocket send failed for job {job_id}: {e}")
                dead_connections.add(connection)
        
        # Clean up dead connections
        for conn in dead_connections:
            self.active_connections[job_id].discard(conn)
        
        # Log progress broadcasts periodically
        if data.get("type") == "progress" and data.get("processed", 0) % 50 == 0:
            logger.debug(f"[WS] Job {job_id}: {data.get('processed')}/{data.get('total')} ({connection_count} clients)")
    
    async def broadcast_dataset_update(self, dataset_id: int, data: dict):
        """Broadcast dataset updates to all connected clients"""
        if dataset_id not in self.dataset_connections:
            # No clients connected for this dataset - this is normal
            return
        
        dead_connections = set()
        for connection in self.dataset_connections[dataset_id]:
            try:
                await connection.send_json(data)
            except Exception as e:
                logger.debug(f"WebSocket send failed for dataset {dataset_id}: {e}")
                dead_connections.add(connection)
        
        for conn in dead_connections:
            self.dataset_connections[dataset_id].discard(conn)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws/job/{job_id}")
async def websocket_job_endpoint(websocket: WebSocket, job_id: int):
    """WebSocket endpoint for job progress updates"""
    await manager.connect(websocket, job_id=job_id)
    try:
        while True:
            # Keep connection alive, listen for any client messages
            data = await websocket.receive_text()
            # Echo back any received data (for ping/pong)
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, job_id=job_id)


@router.websocket("/ws/dataset/{dataset_id}")
async def websocket_dataset_endpoint(websocket: WebSocket, dataset_id: int):
    """WebSocket endpoint for dataset updates"""
    await manager.connect(websocket, dataset_id=dataset_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, dataset_id=dataset_id)


async def notify_job_progress(
    job_id: int, 
    processed: int, 
    total: int, 
    status: str,
    failed: int = 0,
    start_time: float = None,
    eta_seconds: int = None
):
    """Helper function to notify connected clients about job progress"""
    try:
        percentage = round((processed / total) * 100, 1) if total > 0 else 0
        
        # Calculate ETA if start_time provided and we have progress
        if start_time and processed > 0 and total > processed:
            elapsed = time.time() - start_time
            rate = processed / elapsed  # rows per second
            remaining = total - processed
            eta_seconds = int(remaining / rate) if rate > 0 else None
        
        data = {
            "type": "progress",
            "job_id": job_id,
            "processed": processed,
            "total": total,
            "failed": failed,
            "status": status,
            "percentage": percentage,
        }
        
        if eta_seconds is not None:
            data["eta_seconds"] = eta_seconds
            data["eta_formatted"] = format_eta(eta_seconds)
        
        await manager.broadcast_job_progress(job_id, data)
    except Exception as e:
        # Don't let WebSocket errors break the enrichment job
        logger.warning(f"Failed to send progress notification for job {job_id}: {e}")


def format_eta(seconds: int) -> str:
    """Format ETA in human-readable format"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


async def notify_job_complete(job_id: int, dataset_id: int, success: bool, message: str = None):
    """Helper function to notify when job is complete"""
    try:
        await manager.broadcast_job_progress(job_id, {
            "type": "complete",
            "job_id": job_id,
            "success": success,
            "message": message,
        })
        
        # Also notify dataset listeners
        await manager.broadcast_dataset_update(dataset_id, {
            "type": "job_complete",
            "job_id": job_id,
            "success": success,
        })
        
        logger.info(f"[WS] Job {job_id} complete notification sent (success={success})")
    except Exception as e:
        # Don't let WebSocket errors break the flow
        logger.warning(f"Failed to send completion notification for job {job_id}: {e}")


async def notify_dataset_update(dataset_id: int, message: str = None):
    """Helper function to notify all clients about dataset changes"""
    try:
        await manager.broadcast_dataset_update(dataset_id, {
            "type": "dataset_update",
            "dataset_id": dataset_id,
            "message": message,
            "timestamp": time.time()
        })
    except Exception as e:
        # Don't let WebSocket errors break the flow
        logger.warning(f"Failed to send dataset update notification for dataset {dataset_id}: {e}")
