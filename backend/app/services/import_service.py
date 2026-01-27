import pandas as pd
import csv
import re
from io import StringIO, BytesIO, TextIOWrapper
from typing import List, Dict, Any, Optional, Tuple, AsyncGenerator, Callable
import httpx
import logging
import aiofiles
from app.core.config import settings

logger = logging.getLogger(__name__)


class ImportService:
    """Service for importing data from CSV and Google Sheets"""
    
    @staticmethod
    def parse_csv(content: bytes, filename: str) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Parse CSV content and return columns and rows (for small files)"""
        try:
            # Try different encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    df = pd.read_csv(BytesIO(content), encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("Could not decode CSV file with any supported encoding")
            
            # Clean column names
            df.columns = [str(col).strip() for col in df.columns]
            
            # Convert to list of dicts
            columns = df.columns.tolist()
            rows = df.fillna("").to_dict(orient="records")
            
            return columns, rows
        except Exception as e:
            logger.error(f"Error parsing CSV: {str(e)}")
            raise ValueError(f"Failed to parse CSV: {str(e)}")
    
    @staticmethod
    async def stream_csv_rows(
        file_stream,
        chunk_size: int = None
    ) -> AsyncGenerator[Tuple[List[str], List[Dict[str, Any]]], None]:
        """
        Stream CSV file and yield batches of rows.
        Memory-efficient for large files.
        
        Yields: (columns, batch_of_rows)
        First yield includes columns, subsequent yields are just rows.
        """
        chunk_size = chunk_size or settings.BATCH_SIZE * 40  # ~1000 rows per batch
        
        # Buffer for accumulating bytes
        buffer = b""
        columns = None
        current_batch = []
        
        # Try to detect encoding from first chunk
        encoding = 'utf-8'
        first_chunk = await file_stream.read(min(8192, settings.STREAMING_CHUNK_SIZE))
        
        # Try different encodings
        for enc in ['utf-8', 'latin-1', 'cp1252']:
            try:
                first_chunk.decode(enc)
                encoding = enc
                break
            except UnicodeDecodeError:
                continue
        
        buffer = first_chunk
        
        # Read rest of file
        while True:
            chunk = await file_stream.read(settings.STREAMING_CHUNK_SIZE)
            if not chunk:
                break
            buffer += chunk
            
            # Try to process complete lines
            try:
                text = buffer.decode(encoding)
                lines = text.split('\n')
                
                # Keep last incomplete line in buffer
                if not text.endswith('\n'):
                    buffer = lines[-1].encode(encoding)
                    lines = lines[:-1]
                else:
                    buffer = b""
                
                # Process lines
                reader = csv.DictReader(StringIO('\n'.join(lines))) if columns else csv.reader(StringIO('\n'.join(lines)))
                
                for row in reader:
                    if columns is None:
                        # First row is header
                        columns = [str(col).strip() for col in row]
                        continue
                    
                    if isinstance(row, list):
                        row_dict = {columns[i]: (row[i] if i < len(row) else "") for i in range(len(columns))}
                    else:
                        row_dict = {k: (v if v is not None else "") for k, v in row.items()}
                    
                    current_batch.append(row_dict)
                    
                    if len(current_batch) >= chunk_size:
                        yield columns, current_batch
                        current_batch = []
                        
            except Exception as e:
                logger.warning(f"Error processing chunk: {e}")
                continue
        
        # Process remaining buffer
        if buffer:
            try:
                text = buffer.decode(encoding)
                if columns:
                    reader = csv.DictReader(StringIO(text), fieldnames=columns)
                    for row in reader:
                        row_dict = {k: (v if v is not None else "") for k, v in row.items()}
                        current_batch.append(row_dict)
            except Exception as e:
                logger.warning(f"Error processing final buffer: {e}")
        
        # Yield final batch
        if current_batch:
            yield columns, current_batch
    
    @staticmethod
    async def parse_csv_streaming(
        file_stream,
        row_callback: Callable[[List[str], List[Dict[str, Any]], int], Any],
        batch_size: int = 1000
    ) -> Tuple[List[str], int]:
        """
        Parse CSV file in streaming mode with callback for each batch.
        
        Args:
            file_stream: Async file stream
            row_callback: Async callback(columns, rows, batch_index)
            batch_size: Number of rows per batch
            
        Returns: (columns, total_rows)
        """
        columns = None
        total_rows = 0
        batch_index = 0
        
        async for cols, rows in ImportService.stream_csv_rows(file_stream, batch_size):
            if columns is None:
                columns = cols
            
            await row_callback(columns, rows, batch_index)
            total_rows += len(rows)
            batch_index += 1
            
            logger.debug(f"Processed batch {batch_index}: {len(rows)} rows, total: {total_rows}")
        
        return columns or [], total_rows
    
    @staticmethod
    def get_csv_preview(content: bytes, max_rows: int = 100) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Get preview of CSV file (first N rows) without loading entire file"""
        try:
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    df = pd.read_csv(BytesIO(content), encoding=encoding, nrows=max_rows)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("Could not decode CSV file")
            
            df.columns = [str(col).strip() for col in df.columns]
            columns = df.columns.tolist()
            rows = df.fillna("").to_dict(orient="records")
            
            return columns, rows
        except Exception as e:
            logger.error(f"Error getting CSV preview: {str(e)}")
            raise ValueError(f"Failed to preview CSV: {str(e)}")
    
    @staticmethod
    def extract_google_sheet_id(url: str) -> Optional[str]:
        """Extract Google Sheet ID from URL"""
        patterns = [
            r'/spreadsheets/d/([a-zA-Z0-9-_]+)',
            r'id=([a-zA-Z0-9-_]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    @staticmethod
    def extract_gid(url: str) -> Optional[str]:
        """Extract GID (sheet ID) from URL"""
        match = re.search(r'gid=(\d+)', url)
        return match.group(1) if match else None
    
    @staticmethod
    async def import_google_sheet(url: str) -> Tuple[List[str], List[Dict[str, Any]], str]:
        """
        Import Google Sheet using public CSV export
        Returns: (columns, rows, sheet_name)
        """
        sheet_id = ImportService.extract_google_sheet_id(url)
        if not sheet_id:
            raise ValueError("Invalid Google Sheets URL")
        
        gid = ImportService.extract_gid(url) or "0"
        
        # Use public CSV export URL
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(csv_url, follow_redirects=True, timeout=30)
            
            if response.status_code == 404:
                raise ValueError("Google Sheet not found. Make sure it's publicly accessible (Anyone with the link can view)")
            elif response.status_code != 200:
                raise ValueError(f"Failed to fetch Google Sheet: HTTP {response.status_code}")
            
            content = response.content
        
        columns, rows = ImportService.parse_csv(content, "google_sheet.csv")
        
        # Try to get sheet name from URL or use default
        sheet_name = f"Sheet (gid={gid})"
        
        return columns, rows, sheet_name


import_service = ImportService()
