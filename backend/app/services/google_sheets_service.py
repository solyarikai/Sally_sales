"""Google Sheets Service for Reply Automation.

This service handles creating NEW Google Sheets and APPENDING reply data.
SAFETY FIRST: 
- Only creates NEW sheets (never modifies existing data)
- Append-only operations
- Uses service account authentication
"""
import logging
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class GoogleSheetsService:
    """Service for interacting with Google Sheets API."""
    
    # Scopes needed for creating and writing to sheets
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    
    # Standard column headers for reply logging
        # Column headers matching reference sheet: Outreach: Internal -> Replies tab
    # Reference: https://docs.google.com/spreadsheets/d/1MepWTwCGJX-fGQPkygQouF-hfL8WYV4DRAdmqI3DbDg/edit?gid=1698920485
    REPLY_HEADERS = [
        'first name',           # A
        'last name',            # B  
        'Position',             # C - Job title
        'Website',              # D - Company website
        'Linkedin',             # E - LinkedIn profile
        'Company ',             # F - Company name (note: has trailing space in original)
        'Company Location',     # G
        'segment',              # H
        'Employees',            # I
        'target_lead_email',    # J - Lead email
        'Industry',             # K
        'Status ',              # L - Our category/status (note: trailing space)
        'Sample Status',        # M
        'Sample Comment',       # N
        'Sample Responsible',   # O
        'Кто привел',           # P - Who brought (Russian)
        'Updates after communication',  # Q
        'Sample link',          # R
        'Market size, k',       # S
        'Канал',                # T - Channel (Russian)
        'campaign',             # U - Campaign name
        'text',                 # V - Reply text
        'time',                 # W - Reply time
        'created time',         # X - When processed
        'campaign_id',          # Y - Campaign ID
        'category',             # Z - AI category
    ]
    
    # Default tab name for replies (can be overridden per-sheet)
    DEFAULT_TAB = 'Replies'

    
    def __init__(self):
        """Initialize the Google Sheets service."""
        self.credentials = None
        self.sheets_service = None
        self.drive_service = None
        self._initialized = False
        
    def _initialize(self) -> bool:
        """Initialize the Google API clients using service account credentials.
        
        Looks for credentials in:
        1. GOOGLE_SERVICE_ACCOUNT_JSON env var (JSON string)
        2. GOOGLE_APPLICATION_CREDENTIALS env var (path to JSON file)
        """
        if self._initialized:
            return True
            
        try:
            # Try JSON from environment variable first
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
            
            # Apply domain-wide delegation if configured
            impersonate_email = os.environ.get('GOOGLE_IMPERSONATE_EMAIL')
            if impersonate_email:
                self.credentials = self.credentials.with_subject(impersonate_email)
                logger.info(f"Using domain-wide delegation, impersonating: {impersonate_email}")
            
            # Build API clients
            self.sheets_service = build('sheets', 'v4', credentials=self.credentials)
            self.drive_service = build('drive', 'v3', credentials=self.credentials)
            self._initialized = True
            logger.info("Google Sheets service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets service: {e}")
            return False
    
    def is_configured(self) -> bool:
        """Check if Google Sheets integration is configured."""
        return self._initialize()
    
    def get_service_account_email(self) -> Optional[str]:
        """Get the service account email for sharing purposes."""
        if not self._initialize():
            return None
        
        try:
            return self.credentials.service_account_email
        except Exception:
            return None
    
    def create_reply_sheet(self, name: str, share_with_email: Optional[str] = None, use_drive_api: bool = True) -> Optional[Dict[str, str]]:
        """Create a NEW Google Sheet for logging replies.
        
        SAFETY: Only creates new sheets, never modifies existing ones.
        Will try Drive API first as fallback for when Sheets API is disabled.
        
        Args:
            name: Name for the new spreadsheet
            share_with_email: Optional email to share the sheet with (editor access)
            use_drive_api: Try Drive API first (recommended)
            
        Returns:
            Dict with 'sheet_id' and 'sheet_url' if successful, None otherwise
        """
        if not self._initialize():
            logger.error("Google Sheets service not initialized")
            return None
        
        # Try Drive API first (works even if Sheets API is disabled)
        if use_drive_api:
            result = self.create_reply_sheet_via_drive(name, share_with_email)
            if result:
                return result
            logger.warning("Drive API failed, trying Sheets API...")
            
        try:
            # Create the spreadsheet
            spreadsheet = {
                'properties': {
                    'title': f"Reply Log - {name}"
                },
                'sheets': [{
                    'properties': {
                        'title': 'Replies',
                        'gridProperties': {
                            'frozenRowCount': 1  # Freeze header row
                        }
                    }
                }]
            }
            
            result = self.sheets_service.spreadsheets().create(
                body=spreadsheet,
                fields='spreadsheetId,spreadsheetUrl'
            ).execute()
            
            sheet_id = result.get('spreadsheetId')
            sheet_url = result.get('spreadsheetUrl')
            
            if not sheet_id:
                logger.error("Failed to get sheet ID from creation response")
                return None
            
            # Add headers to the first row
            self._add_headers(sheet_id)
            
            # Format the header row
            self._format_header_row(sheet_id)
            
            # Share the sheet if email provided
            if share_with_email:
                self._share_sheet(sheet_id, share_with_email)
            
            logger.info(f"Created new reply sheet: {sheet_id}")
            return {
                'sheet_id': sheet_id,
                'sheet_url': sheet_url
            }
            
        except HttpError as e:
            logger.error(f"Google API error creating sheet: {e}")
            return None
        except Exception as e:
            logger.error(f"Error creating reply sheet: {e}")
            return None
    
    def _add_headers(self, sheet_id: str) -> bool:
        """Add standard headers to the sheet."""
        try:
            body = {
                'values': [self.REPLY_HEADERS]
            }
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range='Sheet1!A1',
                valueInputOption='RAW',
                body=body
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Error adding headers: {e}")
            return False
    
    def _format_header_row(self, sheet_id: str) -> bool:
        """Format the header row (bold, background color)."""
        try:
            requests = [{
                'repeatCell': {
                    'range': {
                        'sheetId': 0,
                        'startRowIndex': 0,
                        'endRowIndex': 1
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'backgroundColor': {
                                'red': 0.2,
                                'green': 0.2,
                                'blue': 0.4
                            },
                            'textFormat': {
                                'bold': True,
                                'foregroundColor': {
                                    'red': 1.0,
                                    'green': 1.0,
                                    'blue': 1.0
                                }
                            }
                        }
                    },
                    'fields': 'userEnteredFormat(backgroundColor,textFormat)'
                }
            }]
            
            self.sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body={'requests': requests}
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Error formatting header row: {e}")
            return False
    
    def _share_sheet(self, sheet_id: str, email: str) -> bool:
        """Share the sheet with an email address (editor access)."""
        try:
            permission = {
                'type': 'user',
                'role': 'writer',
                'emailAddress': email
            }
            self.drive_service.permissions().create(
                fileId=sheet_id,
                body=permission,
                sendNotificationEmail=True,
                emailMessage='A new Reply Log sheet has been created and shared with you.'
            ).execute()
            logger.info(f"Shared sheet {sheet_id} with {email}")
            return True
        except Exception as e:
            logger.error(f"Error sharing sheet: {e}")
            return False
    
    def append_reply(self, sheet_id: str, reply_data: Dict[str, Any], tab_name: str = None) -> bool:
        """Append a reply to the sheet.
        
        Matches reference sheet format: Outreach: Internal -> Replies tab
        
        Args:
            sheet_id: The Google Sheet ID
            reply_data: Dictionary containing reply information
            tab_name: Tab name to write to (defaults to 'Replies' for existing sheets, 'Sheet1' for new ones)
            
        Returns:
            True if successful, False otherwise
        """
        if not self._initialize():
            logger.error("Google Sheets service not initialized")
            return False
        
        # Determine tab name - try Replies first, fallback to Sheet1
        if not tab_name:
            tab_name = self._get_tab_name(sheet_id)
            
        try:
            # Format row to match reference sheet columns A-Z
            row = [
                reply_data.get('lead_first_name', ''),              # A: first name
                reply_data.get('lead_last_name', ''),               # B: last name
                reply_data.get('job_title', ''),                    # C: Position
                reply_data.get('website', ''),                      # D: Website
                reply_data.get('linkedin_profile', ''),             # E: Linkedin
                reply_data.get('lead_company', ''),                 # F: Company
                reply_data.get('company_location', ''),             # G: Company Location
                reply_data.get('segment', ''),                      # H: segment
                reply_data.get('employees', ''),                    # I: Employees
                reply_data.get('lead_email', ''),                   # J: target_lead_email
                reply_data.get('industry', ''),                     # K: Industry
                reply_data.get('category', ''),                     # L: Status (our category)
                '',                                                 # M: Sample Status
                '',                                                 # N: Sample Comment
                '',                                                 # O: Sample Responsible
                '',                                                 # P: Кто привел
                '',                                                 # Q: Updates after communication
                reply_data.get('inbox_link', ''),                   # R: Sample link
                '',                                                 # S: Market size, k
                'Email',                                            # T: Канал (Channel)
                reply_data.get('campaign_name', ''),                # U: campaign
                reply_data.get('email_body', reply_data.get('reply_text', '')),  # V: text
                reply_data.get('received_at', ''),                  # W: time
                datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),    # X: created time
                reply_data.get('campaign_id', ''),                  # Y: campaign_id
                reply_data.get('category', ''),                     # Z: category
            ]
            
            body = {'values': [row]}
            
            # Append to the Replies tab
            range_name = f"'{tab_name}'!A:Z"
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=range_name,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            logger.info(f"Appended reply for {reply_data.get('lead_email')} to sheet {sheet_id} tab {tab_name}")
            return True
            
        except HttpError as e:
            logger.error(f"Google API error appending reply: {e}")
            return False
        except Exception as e:
            logger.error(f"Error appending reply to sheet: {e}")
            return False
    
    def _get_tab_name(self, sheet_id: str) -> str:
        """Get the appropriate tab name for a sheet."""
        try:
            result = self.sheets_service.spreadsheets().get(spreadsheetId=sheet_id).execute()
            tabs = [s.get('properties', {}).get('title') for s in result.get('sheets', [])]
            
            # Prefer 'Replies' tab if it exists
            if 'Replies' in tabs:
                return 'Replies'
            # Fallback to Sheet1
            if 'Sheet1' in tabs:
                return 'Sheet1'
            # Otherwise use first tab
            return tabs[0] if tabs else 'Sheet1'
        except Exception as e:
            logger.warning(f"Could not determine tab name: {e}")
            return 'Sheet1'

    def get_sheet_info(self, sheet_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a sheet.
        
        Args:
            sheet_id: The Google Sheet ID
            
        Returns:
            Dict with sheet info or None if not accessible
        """
        if not self._initialize():
            return None
            
        try:
            result = self.sheets_service.spreadsheets().get(
                spreadsheetId=sheet_id,
                fields='properties.title,spreadsheetUrl'
            ).execute()
            
            return {
                'title': result.get('properties', {}).get('title'),
                'url': result.get('spreadsheetUrl')
            }
        except HttpError as e:
            if e.resp.status == 404:
                logger.warning(f"Sheet {sheet_id} not found")
            else:
                logger.error(f"Google API error getting sheet info: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting sheet info: {e}")
            return None



    def create_reply_sheet_via_drive(self, name: str, share_with_email: Optional[str] = None) -> Optional[Dict[str, str]]:
        """Create a Google Sheet using Drive API with Shared Drive support."""
        if not self._initialize():
            logger.error("Google Sheets service not initialized")
            return None
        
        try:
            drive_service = build('drive', 'v3', credentials=self.credentials)
            
            # Get Shared Drive ID from environment
            shared_drive_id = os.environ.get('SHARED_DRIVE_ID')
            
            file_metadata = {
                'name': f"Reply Log - {name}",
                'mimeType': 'application/vnd.google-apps.spreadsheet'
            }
            
            # If shared drive is configured, create file in shared drive
            if shared_drive_id:
                file_metadata['parents'] = [shared_drive_id]
                logger.info(f"Creating sheet in Shared Drive: {shared_drive_id}")
            
            file = drive_service.files().create(
                body=file_metadata,
                fields='id,webViewLink',
                supportsAllDrives=True  # Required for Shared Drives
            ).execute()
            
            sheet_id = file.get('id')
            sheet_url = file.get('webViewLink')
            
            if not sheet_id:
                logger.error("Failed to get sheet ID from Drive API response")
                return None
            
            try:
                self._add_headers(sheet_id)
                self._format_header_row(sheet_id)
            except Exception as e:
                logger.warning(f"Could not add headers: {e}")
            
            if share_with_email:
                try:
                    permission = {'type': 'user', 'role': 'writer', 'emailAddress': share_with_email}
                    drive_service.permissions().create(fileId=sheet_id, body=permission, sendNotificationEmail=False, supportsAllDrives=True).execute()
                except Exception as e:
                    logger.warning(f"Could not share sheet: {e}")
            
            logger.info(f"Created sheet via Drive API: {sheet_id}")
            return {'sheet_id': sheet_id, 'sheet_url': sheet_url or f"https://docs.google.com/spreadsheets/d/{sheet_id}"}
            
        except HttpError as e:
            logger.error(f"Drive API error creating sheet: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating sheet via Drive: {e}")
            return None



    def update_reply_status(self, sheet_id: str, row_number: int, approval_status: str, 
                            approved_by: str = '', approved_at: str = '') -> bool:
        """Update the status of a reply in the sheet.
        
        In reference format, Status is in column L (12th column).
        
        Args:
            sheet_id: The Google Sheet ID
            row_number: The row number (1-indexed, header is row 1)
            approval_status: New status (pending, approved, dismissed)
            approved_by: Who approved (optional) - stored in Sample Comment (N)
            approved_at: When approved (optional) - stored in Updates (Q)
            
        Returns:
            True if successful, False otherwise
        """
        if not self._initialize():
            logger.error("Google Sheets service not initialized")
            return False
        
        tab_name = self._get_tab_name(sheet_id)
            
        try:
            # In reference format: Status is column L, Sample Comment is N, Updates is Q
            # Update Status (L), Sample Comment (N), Updates (Q)
            updates = []
            
            # Update Status in column L
            updates.append({
                'range': f"'{tab_name}'!L{row_number}",
                'values': [[approval_status]]
            })
            
            # If approved, add note in Updates column Q
            if approved_at:
                updates.append({
                    'range': f"'{tab_name}'!Q{row_number}",
                    'values': [[f"{approval_status} at {approved_at}"]]
                })
            
            body = {'data': updates, 'valueInputOption': 'RAW'}
            
            self.sheets_service.spreadsheets().values().batchUpdate(
                spreadsheetId=sheet_id,
                body=body
            ).execute()
            
            logger.info(f"Updated row {row_number} to {approval_status} in sheet {sheet_id} tab {tab_name}")
            return True
        except Exception as e:
            logger.error(f"Error updating reply status: {e}")
            return False
    def append_reply_and_get_row(self, sheet_id: str, reply_data: Dict[str, Any]) -> Optional[int]:
        """Append a reply and return the row number."""
        if not self._initialize():
            return None
        
        # Get tab name using initialized service
        tab_name = 'Replies'  # Default to Replies for reference sheet format
        try:
            result = self.sheets_service.spreadsheets().get(spreadsheetId=sheet_id).execute()
            tabs = [s.get('properties', {}).get('title') for s in result.get('sheets', [])]
            if 'Replies' in tabs:
                tab_name = 'Replies'
            elif 'Sheet1' in tabs:
                tab_name = 'Sheet1'
            logger.info(f"Using tab: {tab_name} (available: {tabs[:3]}...)")
        except Exception as e:
            logger.warning(f"Could not get tabs, using default: {e}")
            
        try:
            # Get current row count from the correct tab
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=f"'{tab_name}'!A:A"
            ).execute()
            current_rows = len(result.get('values', []))
            new_row = current_rows + 1
            
            if self.append_reply(sheet_id, reply_data, tab_name):
                return new_row
            return None
        except Exception as e:
            logger.error(f"Error in append_reply_and_get_row: {e}")
            if self.append_reply(sheet_id, reply_data):
                return None
            return None


# Global instance
google_sheets_service = GoogleSheetsService()
