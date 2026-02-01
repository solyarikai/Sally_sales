"""Google Drive Upload Service.

This service handles uploading files to Google Drive.
Port of the Ruby GoogleDriveUploadService to Python.

SAFETY:
- Only uploads NEW files (never modifies existing files)
- Sets permissions to make files viewable by anyone with link
"""
import logging
import json
import os
from typing import Optional, Dict, Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class GoogleDriveService:
    """Service for uploading files to Google Drive."""
    
    APPLICATION_NAME = "Leadokol"
    
    # Scopes needed for Drive API
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
    # MIME type mappings for conversion
    MIME_TYPES = {
        # Excel/Spreadsheet -> Google Sheets
        '.xlsx': {
            'upload_mime': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'google_mime': 'application/vnd.google-apps.spreadsheet',
            'view_url': 'https://docs.google.com/spreadsheets/d/{file_id}/view'
        },
        '.xls': {
            'upload_mime': 'application/vnd.ms-excel',
            'google_mime': 'application/vnd.google-apps.spreadsheet',
            'view_url': 'https://docs.google.com/spreadsheets/d/{file_id}/view'
        },
        '.csv': {
            'upload_mime': 'text/csv',
            'google_mime': 'application/vnd.google-apps.spreadsheet',
            'view_url': 'https://docs.google.com/spreadsheets/d/{file_id}/view'
        },
        # Word -> Google Docs
        '.docx': {
            'upload_mime': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'google_mime': 'application/vnd.google-apps.document',
            'view_url': 'https://docs.google.com/document/d/{file_id}/view'
        },
        '.doc': {
            'upload_mime': 'application/msword',
            'google_mime': 'application/vnd.google-apps.document',
            'view_url': 'https://docs.google.com/document/d/{file_id}/view'
        },
        # PowerPoint -> Google Slides
        '.pptx': {
            'upload_mime': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'google_mime': 'application/vnd.google-apps.presentation',
            'view_url': 'https://docs.google.com/presentation/d/{file_id}/view'
        },
        '.ppt': {
            'upload_mime': 'application/vnd.ms-powerpoint',
            'google_mime': 'application/vnd.google-apps.presentation',
            'view_url': 'https://docs.google.com/presentation/d/{file_id}/view'
        },
        # PDF (no conversion, just upload)
        '.pdf': {
            'upload_mime': 'application/pdf',
            'google_mime': None,  # No conversion
            'view_url': 'https://drive.google.com/file/d/{file_id}/view'
        },
    }
    
    def __init__(self):
        """Initialize the Google Drive service."""
        self.credentials = None
        self.drive_service = None
        self._initialized = False
        
    def _initialize(self) -> bool:
        """Initialize the Google API client using service account credentials.
        
        Looks for credentials in:
        1. GOOGLE_SERVICE_ACCOUNT_JSON env var (JSON string - like GOOGLE_KEY in Ruby)
        2. GOOGLE_APPLICATION_CREDENTIALS env var (path to JSON file)
        """
        if self._initialized:
            return True
            
        try:
            # Try JSON from environment variable first (like Ruby's ENV.fetch("GOOGLE_KEY"))
            service_account_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
            credentials_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
            
            if service_account_json:
                # Parse JSON string from environment
                creds_info = json.loads(service_account_json)
                self.credentials = service_account.Credentials.from_service_account_info(
                    creds_info,
                    scopes=self.SCOPES
                )
            elif credentials_path and os.path.exists(credentials_path):
                # Use credentials file
                self.credentials = service_account.Credentials.from_service_account_file(
                    credentials_path,
                    scopes=self.SCOPES
                )
            else:
                logger.warning("No Google service account credentials configured")
                return False
            
            # Build Drive API client
            self.drive_service = build('drive', 'v3', credentials=self.credentials)
            self._initialized = True
            logger.info("Google Drive service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {e}")
            return False
    
    def is_configured(self) -> bool:
        """Check if Google Drive integration is configured."""
        return self._initialize()
    
    def get_shared_drive_id(self) -> Optional[str]:
        """Get the Shared Drive ID from environment."""
        return os.environ.get('SHARED_DRIVE_ID')
    
    def upload_file(
        self, 
        file_path: str, 
        convert_to_google_format: bool = True,
        shared_drive_id: Optional[str] = None,
        folder_id: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        """Upload a file to Google Drive.
        
        This is equivalent to the Ruby `call` method.
        
        Args:
            file_path: Path to the file to upload
            convert_to_google_format: Whether to convert to Google Docs/Sheets format
            shared_drive_id: Optional Shared Drive ID (defaults to SHARED_DRIVE_ID env var)
            folder_id: Optional folder ID to upload to
            
        Returns:
            Dict with 'file_id', 'view_url', 'name' if successful, None otherwise
        """
        if not self._initialize():
            logger.error("Google Drive service not initialized")
            return None
            
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return None
            
        try:
            file_name = os.path.basename(file_path)
            file_ext = os.path.splitext(file_name)[1].lower()
            
            # Get MIME type info
            mime_info = self.MIME_TYPES.get(file_ext)
            if mime_info:
                upload_mime = mime_info['upload_mime']
                google_mime = mime_info['google_mime'] if convert_to_google_format else None
                view_url_template = mime_info['view_url']
            else:
                # Default to binary upload
                upload_mime = 'application/octet-stream'
                google_mime = None
                view_url_template = 'https://drive.google.com/file/d/{file_id}/view'
            
            # Prepare file metadata
            file_metadata = {
                'name': file_name,
            }
            
            # Set conversion MIME type if requested
            if google_mime and convert_to_google_format:
                file_metadata['mimeType'] = google_mime
            
            # Set parent folder (Shared Drive or regular folder)
            drive_id = shared_drive_id or self.get_shared_drive_id()
            if drive_id:
                file_metadata['parents'] = [drive_id]
            elif folder_id:
                file_metadata['parents'] = [folder_id]
            
            # Create media upload
            media = MediaFileUpload(
                file_path,
                mimetype=upload_mime,
                resumable=True
            )
            
            # Upload the file
            # Use supportsAllDrives for Shared Drives
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,webViewLink',
                supportsAllDrives=True
            ).execute()
            
            file_id = file.get('id')
            
            if not file_id:
                logger.error("Failed to get file ID from upload response")
                return None
            
            # Set permissions to make file viewable by anyone with link
            self._set_public_permissions(file_id)
            
            # Generate view URL
            view_url = view_url_template.format(file_id=file_id)
            
            logger.info(f"Uploaded file: {file_name} -> {view_url}")
            
            return {
                'file_id': file_id,
                'view_url': view_url,
                'name': file_name,
                'web_view_link': file.get('webViewLink')
            }
            
        except HttpError as e:
            logger.error(f"Google API error uploading file: {e}")
            return None
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return None
    
    def _set_public_permissions(self, file_id: str) -> bool:
        """Set file permissions to 'anyone with link can view'.
        
        Equivalent to Ruby's set_permissions method.
        """
        try:
            permission = {
                'type': 'anyone',
                'role': 'reader'
            }
            self.drive_service.permissions().create(
                fileId=file_id,
                body=permission,
                supportsAllDrives=True
            ).execute()
            logger.debug(f"Set public permissions for file {file_id}")
            return True
        except Exception as e:
            logger.error(f"Error setting permissions: {e}")
            return False
    
    def upload_xlsx_as_sheet(self, file_path: str) -> Optional[str]:
        """Upload an XLSX file and convert to Google Sheets.
        
        Convenience method matching the Ruby service's primary use case.
        Returns the view URL for the Google Sheet.
        
        Args:
            file_path: Path to the .xlsx file
            
        Returns:
            Google Sheets view URL or None if failed
        """
        result = self.upload_file(file_path, convert_to_google_format=True)
        if result:
            return result['view_url']
        return None


# Global instance
google_drive_service = GoogleDriveService()
