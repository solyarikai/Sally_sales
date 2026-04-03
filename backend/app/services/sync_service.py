"""
Sync Service - Automatic synchronization between local files and database

Features:
- Watch local CSV files for changes
- Auto-upload updates to database
- Real-time sync via WebSocket
- Multi-user support
"""

import asyncio
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
import hashlib
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.db import async_session_maker
from app.models import Dataset, DataRow, Company
from app.api.websocket import notify_dataset_update

logger = logging.getLogger(__name__)


class DatasetSyncHandler(FileSystemEventHandler):
    """Handler for file system events - watches CSV files"""
    
    def __init__(self, sync_service: 'SyncService'):
        self.sync_service = sync_service
        self.debounce_timers: Dict[str, asyncio.Task] = {}
    
    def on_modified(self, event: FileModifiedEvent):
        """Handle file modification"""
        if event.is_directory:
            return
        
        file_path = event.src_path
        
        # Only process CSV files
        if not file_path.endswith('.csv'):
            return
        
        # Skip temp files
        if '~' in file_path or file_path.startswith('.'):
            return
        
        logger.info(f"File modified: {file_path}")
        
        # Debounce: wait 2 seconds before syncing
        if file_path in self.debounce_timers:
            self.debounce_timers[file_path].cancel()
        
        async def debounced_sync():
            await asyncio.sleep(2)
            await self.sync_service.sync_file(file_path)
        
        self.debounce_timers[file_path] = asyncio.create_task(debounced_sync())


class SyncService:
    """Service for automatic synchronization between local and database"""
    
    def __init__(self):
        self.observer: Optional[Observer] = None
        self.watched_folders: Dict[str, Dict] = {}  # path -> {company_id, dataset_id}
        self.file_hashes: Dict[str, str] = {}  # path -> hash
    
    def get_file_hash(self, file_path: str) -> str:
        """Calculate file hash to detect changes"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return ""
    
    async def sync_file(self, file_path: str):
        """Sync a file to database"""
        try:
            # Check if file changed
            current_hash = self.get_file_hash(file_path)
            if current_hash == self.file_hashes.get(file_path):
                logger.debug(f"File unchanged, skipping: {file_path}")
                return
            
            logger.info(f"Syncing file to database: {file_path}")
            
            # Find dataset for this file
            dataset_info = self._find_dataset_for_file(file_path)
            if not dataset_info:
                logger.warning(f"No dataset mapping found for: {file_path}")
                return
            
            # Read CSV
            df = pd.read_csv(file_path)
            logger.info(f"Read {len(df)} rows from {file_path}")
            
            # Update database
            async with async_session_maker() as session:
                await self._update_dataset_rows(
                    session,
                    dataset_info['dataset_id'],
                    dataset_info['company_id'],
                    df
                )
                await session.commit()
            
            # Update hash
            self.file_hashes[file_path] = current_hash
            
            # Notify clients via WebSocket
            await notify_dataset_update(
                dataset_info['dataset_id'],
                f"Dataset updated from file: {Path(file_path).name}"
            )
            
            logger.info(f"Successfully synced {file_path}")
            
        except Exception as e:
            logger.error(f"Error syncing file {file_path}: {e}")
    
    def _find_dataset_for_file(self, file_path: str) -> Optional[Dict]:
        """Find dataset mapping for a file"""
        file_path = str(Path(file_path).resolve())
        
        # Check exact path
        if file_path in self.watched_folders:
            return self.watched_folders[file_path]
        
        # Check if file is in a watched folder
        for watched_path, info in self.watched_folders.items():
            if file_path.startswith(watched_path):
                return info
        
        return None
    
    async def _update_dataset_rows(
        self,
        session: AsyncSession,
        dataset_id: int,
        company_id: int,
        df: pd.DataFrame
    ):
        """Update dataset rows from dataframe"""
        # Get existing rows
        query = select(DataRow).where(DataRow.dataset_id == dataset_id)
        result = await session.execute(query)
        existing_rows = {row.row_index: row for row in result.scalars().all()}
        
        # Get dataset to know original columns
        from app.models import Dataset
        dataset = await session.get(Dataset, dataset_id)
        original_columns = set(dataset.columns) if dataset else set()
        
        # Update rows
        updated_count = 0
        new_columns = set()
        
        for idx, row_data in df.iterrows():
            row_dict = row_data.to_dict()
            
            if idx in existing_rows:
                # Update existing row
                db_row = existing_rows[idx]
                
                # Separate original and enriched columns
                data_updates = {}
                enriched_updates = {}
                
                for col, val in row_dict.items():
                    if pd.isna(val):
                        continue
                    
                    # Check if this is an enriched column (MV_*, *_Verified, etc.)
                    is_enriched = (
                        col.startswith('MV_') or 
                        col.endswith('_Verified') or
                        col.endswith('_verified') or
                        col not in original_columns
                    )
                    
                    if is_enriched:
                        # Convert boolean to string for storage
                        if isinstance(val, bool):
                            enriched_updates[col] = str(val)
                        else:
                            enriched_updates[col] = str(val)
                        new_columns.add(col)
                    else:
                        data_updates[col] = val
                
                # Update data columns
                if data_updates:
                    db_row.data = {**db_row.data, **data_updates}
                
                # Update enriched columns
                if enriched_updates:
                    db_row.enriched_data = {**db_row.enriched_data, **enriched_updates}
                    db_row.last_enriched_at = datetime.utcnow()
                
                updated_count += 1
        
        logger.info(f"Updated {updated_count} rows, added {len(new_columns)} enriched columns: {new_columns}")
    
    def watch_folder(
        self,
        folder_path: str,
        company_id: int,
        dataset_id: int,
        recursive: bool = False
    ):
        """Start watching a folder for changes"""
        folder_path = str(Path(folder_path).resolve())
        
        if folder_path in self.watched_folders:
            logger.info(f"Already watching: {folder_path}")
            return
        
        self.watched_folders[folder_path] = {
            'company_id': company_id,
            'dataset_id': dataset_id
        }
        
        if not self.observer:
            self.observer = Observer()
            self.observer.start()
        
        handler = DatasetSyncHandler(self)
        self.observer.schedule(handler, folder_path, recursive=recursive)
        
        logger.info(f"Started watching: {folder_path} (dataset_id={dataset_id})")
    
    def watch_file(
        self,
        file_path: str,
        company_id: int,
        dataset_id: int
    ):
        """Watch a specific file"""
        file_path = str(Path(file_path).resolve())
        folder_path = str(Path(file_path).parent)
        
        self.watched_folders[file_path] = {
            'company_id': company_id,
            'dataset_id': dataset_id
        }
        
        self.watch_folder(folder_path, company_id, dataset_id, recursive=False)
        
        logger.info(f"Started watching file: {file_path} (dataset_id={dataset_id})")
    
    def stop_watching(self, path: str = None):
        """Stop watching a path or all paths"""
        if path:
            path = str(Path(path).resolve())
            if path in self.watched_folders:
                del self.watched_folders[path]
                logger.info(f"Stopped watching: {path}")
        else:
            self.watched_folders.clear()
            if self.observer:
                self.observer.stop()
                self.observer.join()
                self.observer = None
            logger.info("Stopped all file watching")
    
    async def manual_sync(
        self,
        file_path: str,
        dataset_id: int,
        company_id: int
    ):
        """Manually sync a file to database"""
        # Temporarily register the file
        self.watched_folders[file_path] = {
            'company_id': company_id,
            'dataset_id': dataset_id
        }
        
        try:
            await self.sync_file(file_path)
        finally:
            # Clean up temporary registration
            if file_path in self.watched_folders:
                del self.watched_folders[file_path]
    
    def get_watched_paths(self) -> List[Dict]:
        """Get list of watched paths"""
        return [
            {
                'path': path,
                'company_id': info['company_id'],
                'dataset_id': info['dataset_id']
            }
            for path, info in self.watched_folders.items()
        ]


# Global instance
sync_service = SyncService()


async def setup_default_syncs():
    """
    Setup default file syncs.
    
    This is a placeholder function. Configure file watching via API endpoints
    or environment variables in production.
    """
    # No default syncs - configure via API or environment
    logger.info("Sync service initialized (no default syncs configured)")
