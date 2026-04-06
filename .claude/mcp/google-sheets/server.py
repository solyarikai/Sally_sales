#!/usr/bin/env python3
"""
Google Sheets & Drive MCP Server.

Provides 25 tools to read, write, search, and manage Google Sheets and Drive
using existing OAuth2 credentials (credentials.json + token.json).
"""

import os
import json
from typing import Optional, List, Any
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CREDENTIALS_PATH = os.environ.get(
    "GOOGLE_CREDENTIALS_PATH",
    os.path.join(os.path.dirname(__file__), "credentials.json"),
)
TOKEN_PATH = os.environ.get(
    "GOOGLE_TOKEN_PATH",
    os.path.join(os.path.dirname(__file__), "token.json"),
)

mcp = FastMCP("google_sheets_drive_mcp")


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


def _get_service():
    """Return an authenticated Google Sheets service object."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())
    return build("sheets", "v4", credentials=creds)


def _get_drive_service():
    """Return an authenticated Google Drive service object (for listing sheets)."""
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("drive", "v3", credentials=creds)


def _handle_error(e: Exception) -> str:
    if isinstance(e, HttpError):
        code = e.resp.status
        if code == 404:
            return "Error: Spreadsheet or range not found. Check the spreadsheet ID and range."
        if code == 403:
            return "Error: Permission denied. Make sure the spreadsheet is shared with your account."
        if code == 400:
            return f"Error: Bad request — {e.reason}"
        return f"Error: Google API error {code}: {e.reason}"
    return f"Error: {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class ReadRangeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    spreadsheet_id: str = Field(
        ...,
        description="Google Sheets ID from the URL (e.g., '1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms')",
    )
    range: str = Field(
        ...,
        description="A1 notation range, e.g. 'Sheet1!A1:E50' or just 'A1:C10' for the first sheet",
    )
    as_json: bool = Field(
        default=False,
        description="Return data as JSON array of objects using first row as headers",
    )


class WriteRangeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    spreadsheet_id: str = Field(..., description="Google Sheets ID from the URL")
    range: str = Field(
        ..., description="A1 notation range where writing starts, e.g. 'Sheet1!A1'"
    )
    values: List[List[Any]] = Field(
        ...,
        description="2D array of values to write, e.g. [['Name','Email'],['Alice','alice@x.com']]",
    )
    value_input_option: str = Field(
        default="USER_ENTERED",
        description="'USER_ENTERED' (interprets formulas) or 'RAW' (literal strings)",
    )


class AppendRowsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    spreadsheet_id: str = Field(..., description="Google Sheets ID from the URL")
    range: str = Field(
        ...,
        description="Range to append after, e.g. 'Sheet1!A:Z' — rows are appended after the last filled row",
    )
    values: List[List[Any]] = Field(..., description="2D array of rows to append")


class SearchSheetInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    spreadsheet_id: str = Field(..., description="Google Sheets ID from the URL")
    sheet_name: str = Field(
        ..., description="Name of the sheet/tab to search in, e.g. 'Sheet1'"
    )
    query: str = Field(..., description="String to search for (case-insensitive)")
    search_column: Optional[str] = Field(
        default=None,
        description="Column letter to limit search, e.g. 'B'. If omitted, searches all columns.",
    )


class ListSheetsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    spreadsheet_id: str = Field(..., description="Google Sheets ID from the URL")


class CreateSpreadsheetInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(
        ..., description="Title of the new spreadsheet", min_length=1, max_length=200
    )
    sheet_names: Optional[List[str]] = Field(
        default=None,
        description="Optional list of sheet/tab names to create, e.g. ['Leads','Done']",
    )


class ClearRangeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    spreadsheet_id: str = Field(..., description="Google Sheets ID from the URL")
    range: str = Field(
        ..., description="A1 notation range to clear, e.g. 'Sheet1!A2:Z1000'"
    )


class ListUserSpreadsheetsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    max_results: int = Field(
        default=20, description="Maximum number of spreadsheets to return", ge=1, le=100
    )
    query: Optional[str] = Field(
        default=None, description="Optional filter by name fragment"
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="sheets_read_range",
    annotations={
        "title": "Read Range from Google Sheet",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def sheets_read_range(params: ReadRangeInput) -> str:
    """Read a range of cells from a Google Sheet.

    Fetches the specified A1-notation range. Can return raw 2D array or
    structured JSON objects using the first row as column headers.

    Args:
        params.spreadsheet_id: The Sheet ID from its URL.
        params.range: A1-notation range, e.g. 'Sheet1!A1:E100'.
        params.as_json: If True, uses row 0 as headers and returns list of dicts.

    Returns:
        str: JSON with 'range', 'row_count', and 'values' (list of rows or dicts).
             Returns "No data found" if range is empty.
    """
    try:
        service = _get_service()
        result = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=params.spreadsheet_id,
                range=params.range,
            )
            .execute()
        )

        rows = result.get("values", [])
        if not rows:
            return f"No data found in range '{params.range}'."

        if params.as_json and len(rows) > 1:
            headers = rows[0]
            records = []
            for row in rows[1:]:
                record = {}
                for i, header in enumerate(headers):
                    record[header] = row[i] if i < len(row) else ""
                records.append(record)
            return json.dumps(
                {"range": params.range, "row_count": len(records), "values": records},
                ensure_ascii=False,
                indent=2,
            )

        return json.dumps(
            {"range": params.range, "row_count": len(rows), "values": rows},
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="sheets_write_range",
    annotations={
        "title": "Write Range to Google Sheet",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def sheets_write_range(params: WriteRangeInput) -> str:
    """Write values to a range in a Google Sheet (overwrites existing data).

    Use for bulk updates or replacing a known block of cells.
    For adding new rows at the end, use sheets_append_rows instead.

    Args:
        params.spreadsheet_id: The Sheet ID.
        params.range: Starting cell in A1 notation, e.g. 'Sheet1!A1'.
        params.values: 2D list of values. Each inner list is a row.
        params.value_input_option: 'USER_ENTERED' to parse formulas, 'RAW' for literal.

    Returns:
        str: Confirmation with updated range and cell count.
    """
    try:
        service = _get_service()
        body = {"values": params.values}
        result = (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId=params.spreadsheet_id,
                range=params.range,
                valueInputOption=params.value_input_option,
                body=body,
            )
            .execute()
        )
        return json.dumps(
            {
                "updated_range": result.get("updatedRange"),
                "updated_rows": result.get("updatedRows"),
                "updated_columns": result.get("updatedColumns"),
                "updated_cells": result.get("updatedCells"),
            },
            indent=2,
        )
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="sheets_append_rows",
    annotations={
        "title": "Append Rows to Google Sheet",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def sheets_append_rows(params: AppendRowsInput) -> str:
    """Append rows after the last filled row in a Google Sheet.

    Safe to use for adding new leads, results, or entries without
    overwriting existing data.

    Args:
        params.spreadsheet_id: The Sheet ID.
        params.range: Range like 'Sheet1!A:Z' — rows append after last filled row.
        params.values: 2D list of rows to add.

    Returns:
        str: Confirmation with the range where rows were appended and count.
    """
    try:
        service = _get_service()
        body = {"values": params.values}
        result = (
            service.spreadsheets()
            .values()
            .append(
                spreadsheetId=params.spreadsheet_id,
                range=params.range,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body,
            )
            .execute()
        )
        updates = result.get("updates", {})
        return json.dumps(
            {
                "appended_range": updates.get("updatedRange"),
                "appended_rows": updates.get("updatedRows"),
                "appended_cells": updates.get("updatedCells"),
            },
            indent=2,
        )
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="sheets_search",
    annotations={
        "title": "Search in Google Sheet",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def sheets_search(params: SearchSheetInput) -> str:
    """Search for a string across rows in a Google Sheet tab.

    Loads all data from the sheet and returns rows containing the query string.
    Optionally restrict search to a single column.

    Args:
        params.spreadsheet_id: The Sheet ID.
        params.sheet_name: Name of the tab to search (e.g. 'Sheet1').
        params.query: Case-insensitive search string.
        params.search_column: Optional column letter to restrict search (e.g. 'B').

    Returns:
        str: JSON with matching rows (including row numbers) and total match count.
    """
    try:
        service = _get_service()
        range_notation = f"{params.sheet_name}!A:ZZ"
        result = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=params.spreadsheet_id,
                range=range_notation,
            )
            .execute()
        )

        rows = result.get("values", [])
        if not rows:
            return f"Sheet '{params.sheet_name}' is empty."

        query_lower = params.query.lower()
        matches = []

        # Determine column index if filtering by column letter
        col_index = None
        if params.search_column:
            col_index = ord(params.search_column.upper()) - ord("A")

        for row_num, row in enumerate(rows, start=1):
            if col_index is not None:
                cell_val = row[col_index] if col_index < len(row) else ""
                if query_lower in str(cell_val).lower():
                    matches.append({"row": row_num, "values": row})
            else:
                if any(query_lower in str(cell).lower() for cell in row):
                    matches.append({"row": row_num, "values": row})

        if not matches:
            return f"No rows found matching '{params.query}' in sheet '{params.sheet_name}'."

        return json.dumps(
            {
                "query": params.query,
                "sheet": params.sheet_name,
                "match_count": len(matches),
                "matches": matches,
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="sheets_list_sheets",
    annotations={
        "title": "List Sheets/Tabs in Spreadsheet",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def sheets_list_sheets(params: ListSheetsInput) -> str:
    """List all tabs/sheets inside a Google Spreadsheet.

    Returns the name, ID, and row/column count of each tab.

    Args:
        params.spreadsheet_id: The Sheet ID.

    Returns:
        str: JSON list of sheets with name, sheetId, rowCount, columnCount.
    """
    try:
        service = _get_service()
        meta = (
            service.spreadsheets()
            .get(
                spreadsheetId=params.spreadsheet_id,
                fields="properties.title,sheets.properties",
            )
            .execute()
        )

        title = meta.get("properties", {}).get("title", "Unknown")
        sheets = []
        for s in meta.get("sheets", []):
            props = s.get("properties", {})
            grid = props.get("gridProperties", {})
            sheets.append(
                {
                    "name": props.get("title"),
                    "sheetId": props.get("sheetId"),
                    "rowCount": grid.get("rowCount"),
                    "columnCount": grid.get("columnCount"),
                }
            )

        return json.dumps({"spreadsheet_title": title, "sheets": sheets}, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="sheets_create_spreadsheet",
    annotations={
        "title": "Create New Google Spreadsheet",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def sheets_create_spreadsheet(params: CreateSpreadsheetInput) -> str:
    """Create a new Google Spreadsheet with optional custom tab names.

    Args:
        params.title: Title of the new spreadsheet.
        params.sheet_names: Optional list of tab names. Defaults to ['Sheet1'].

    Returns:
        str: JSON with new spreadsheet ID, URL, and sheet names.
    """
    try:
        service = _get_service()
        body: dict = {"properties": {"title": params.title}}
        if params.sheet_names:
            body["sheets"] = [
                {"properties": {"title": name}} for name in params.sheet_names
            ]
        result = service.spreadsheets().create(body=body).execute()
        spreadsheet_id = result["spreadsheetId"]
        return json.dumps(
            {
                "spreadsheet_id": spreadsheet_id,
                "url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
                "title": params.title,
                "sheets": [s["properties"]["title"] for s in result.get("sheets", [])],
            },
            indent=2,
        )
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="sheets_clear_range",
    annotations={
        "title": "Clear Range in Google Sheet",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def sheets_clear_range(params: ClearRangeInput) -> str:
    """Clear all values in a specified range (does NOT delete rows/formatting).

    Args:
        params.spreadsheet_id: The Sheet ID.
        params.range: A1-notation range to clear, e.g. 'Sheet1!A2:Z1000'.

    Returns:
        str: Confirmation with cleared range.
    """
    try:
        service = _get_service()
        result = (
            service.spreadsheets()
            .values()
            .clear(
                spreadsheetId=params.spreadsheet_id,
                range=params.range,
            )
            .execute()
        )
        return json.dumps({"cleared_range": result.get("clearedRange")}, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="sheets_list_my_spreadsheets",
    annotations={
        "title": "List My Google Spreadsheets",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def sheets_list_my_spreadsheets(params: ListUserSpreadsheetsInput) -> str:
    """List Google Spreadsheets accessible to the authenticated account.

    Useful for finding spreadsheet IDs by name.

    Args:
        params.max_results: Max number to return (1-100, default 20).
        params.query: Optional name fragment to filter results.

    Returns:
        str: JSON list of spreadsheets with id, name, and URL.
    """
    try:
        drive = _get_drive_service()
        q = "mimeType='application/vnd.google-apps.spreadsheet'"
        if params.query:
            q += f" and name contains '{params.query}'"
        result = (
            drive.files()
            .list(
                q=q,
                pageSize=params.max_results,
                fields="files(id, name, modifiedTime)",
                orderBy="modifiedTime desc",
            )
            .execute()
        )
        files = result.get("files", [])
        spreadsheets = [
            {
                "id": f["id"],
                "name": f["name"],
                "url": f"https://docs.google.com/spreadsheets/d/{f['id']}",
                "modified": f.get("modifiedTime", ""),
            }
            for f in files
        ]
        return json.dumps(
            {"count": len(spreadsheets), "spreadsheets": spreadsheets}, indent=2
        )
    except Exception as e:
        return _handle_error(e)


# ---------------------------------------------------------------------------
# Extended Sheets input models
# ---------------------------------------------------------------------------


class AddTabInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    spreadsheet_id: str = Field(..., description="Google Sheets ID from the URL")
    title: str = Field(..., description="Name for the new tab")


class DeleteTabInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    spreadsheet_id: str = Field(..., description="Google Sheets ID from the URL")
    sheet_id: int = Field(
        ..., description="Numeric sheet/tab ID (from sheets_list_sheets)"
    )


class RenameTabInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    spreadsheet_id: str = Field(..., description="Google Sheets ID from the URL")
    sheet_id: int = Field(..., description="Numeric sheet/tab ID")
    new_title: str = Field(..., description="New name for the tab")


class DuplicateTabInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    spreadsheet_id: str = Field(..., description="Google Sheets ID from the URL")
    sheet_id: int = Field(..., description="Numeric sheet/tab ID to duplicate")
    new_title: Optional[str] = Field(
        default=None,
        description="Name for the copy. If omitted, uses 'Copy of <original>'",
    )


class GetMetadataInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    spreadsheet_id: str = Field(..., description="Google Sheets ID from the URL")


class UpdateMetadataInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    spreadsheet_id: str = Field(..., description="Google Sheets ID from the URL")
    new_title: Optional[str] = Field(
        default=None, description="New title for the spreadsheet"
    )
    locale: Optional[str] = Field(default=None, description="Locale, e.g. 'en_US'")


class SortRangeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    spreadsheet_id: str = Field(..., description="Google Sheets ID from the URL")
    sheet_id: int = Field(..., description="Numeric sheet/tab ID")
    start_row: int = Field(..., description="Start row index (0-based, inclusive)")
    end_row: int = Field(..., description="End row index (0-based, exclusive)")
    start_col: int = Field(..., description="Start column index (0-based, inclusive)")
    end_col: int = Field(..., description="End column index (0-based, exclusive)")
    sort_column: int = Field(..., description="Column index to sort by (0-based)")
    ascending: bool = Field(
        default=True, description="Sort ascending (True) or descending (False)"
    )


class AutoResizeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    spreadsheet_id: str = Field(..., description="Google Sheets ID from the URL")
    sheet_id: int = Field(..., description="Numeric sheet/tab ID")
    start_col: int = Field(default=0, description="Start column index (0-based)")
    end_col: int = Field(
        default=26, description="End column index (0-based, exclusive)"
    )


class BatchFormatInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    spreadsheet_id: str = Field(..., description="Google Sheets ID from the URL")
    sheet_id: int = Field(..., description="Numeric sheet/tab ID")
    start_row: int = Field(..., description="Start row index (0-based)")
    end_row: int = Field(..., description="End row index (0-based, exclusive)")
    start_col: int = Field(..., description="Start column index (0-based)")
    end_col: int = Field(..., description="End column index (0-based, exclusive)")
    bold: Optional[bool] = Field(default=None, description="Set bold")
    bg_color_hex: Optional[str] = Field(
        default=None, description="Background color as hex, e.g. '#FFD700'"
    )


# ---------------------------------------------------------------------------
# Drive input models
# ---------------------------------------------------------------------------


class DriveCreateFolderInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(..., description="Folder name")
    parent_id: Optional[str] = Field(
        default=None, description="Parent folder ID. If omitted, creates in root."
    )


class DriveMoveFileInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    file_id: str = Field(..., description="ID of the file/spreadsheet to move")
    folder_id: str = Field(..., description="Target folder ID")


class DriveListFolderInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    folder_id: str = Field(..., description="Folder ID to list contents of")
    max_results: int = Field(
        default=50, description="Max items to return", ge=1, le=200
    )


class DriveSearchFilesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    query: str = Field(..., description="Search string for file name")
    file_type: Optional[str] = Field(
        default=None,
        description="MIME type filter, e.g. 'application/vnd.google-apps.spreadsheet'",
    )
    max_results: int = Field(default=20, description="Max results", ge=1, le=100)


class DriveDeleteFileInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    file_id: str = Field(..., description="ID of the file to delete (moves to trash)")


class DriveGetFileInfoInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    file_id: str = Field(..., description="ID of the file")


class DriveShareFileInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    file_id: str = Field(..., description="ID of the file to share")
    email: str = Field(..., description="Email address to share with")
    role: str = Field(
        default="reader",
        description="Permission role: 'reader', 'writer', or 'commenter'",
    )


class DriveCopyFileInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    file_id: str = Field(..., description="ID of the file to copy")
    new_name: Optional[str] = Field(
        default=None,
        description="Name for the copy. If omitted, uses 'Copy of <original>'",
    )
    parent_id: Optional[str] = Field(
        default=None, description="Target folder ID for the copy"
    )


# ---------------------------------------------------------------------------
# Extended Sheets tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="sheets_add_tab",
    annotations={
        "title": "Add Tab to Spreadsheet",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def sheets_add_tab(params: AddTabInput) -> str:
    """Add a new tab/sheet to an existing spreadsheet.

    Args:
        params.spreadsheet_id: The Sheet ID.
        params.title: Name for the new tab.
    """
    try:
        service = _get_service()
        body = {"requests": [{"addSheet": {"properties": {"title": params.title}}}]}
        result = (
            service.spreadsheets()
            .batchUpdate(spreadsheetId=params.spreadsheet_id, body=body)
            .execute()
        )
        props = result["replies"][0]["addSheet"]["properties"]
        return json.dumps(
            {"sheetId": props["sheetId"], "title": props["title"]}, indent=2
        )
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="sheets_delete_tab",
    annotations={
        "title": "Delete Tab from Spreadsheet",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def sheets_delete_tab(params: DeleteTabInput) -> str:
    """Delete a tab/sheet from a spreadsheet by its numeric ID.

    Args:
        params.spreadsheet_id: The Sheet ID.
        params.sheet_id: Numeric tab ID (get from sheets_list_sheets).
    """
    try:
        service = _get_service()
        body = {"requests": [{"deleteSheet": {"sheetId": params.sheet_id}}]}
        service.spreadsheets().batchUpdate(
            spreadsheetId=params.spreadsheet_id, body=body
        ).execute()
        return json.dumps(
            {"deleted_sheet_id": params.sheet_id, "status": "ok"}, indent=2
        )
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="sheets_rename_tab",
    annotations={
        "title": "Rename Tab in Spreadsheet",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def sheets_rename_tab(params: RenameTabInput) -> str:
    """Rename a tab/sheet in a spreadsheet.

    Args:
        params.spreadsheet_id: The Sheet ID.
        params.sheet_id: Numeric tab ID.
        params.new_title: New name for the tab.
    """
    try:
        service = _get_service()
        body = {
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": params.sheet_id,
                            "title": params.new_title,
                        },
                        "fields": "title",
                    }
                }
            ]
        }
        service.spreadsheets().batchUpdate(
            spreadsheetId=params.spreadsheet_id, body=body
        ).execute()
        return json.dumps(
            {
                "sheet_id": params.sheet_id,
                "new_title": params.new_title,
                "status": "ok",
            },
            indent=2,
        )
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="sheets_duplicate_tab",
    annotations={
        "title": "Duplicate Tab in Spreadsheet",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def sheets_duplicate_tab(params: DuplicateTabInput) -> str:
    """Duplicate a tab/sheet within the same spreadsheet.

    Args:
        params.spreadsheet_id: The Sheet ID.
        params.sheet_id: Numeric tab ID to duplicate.
        params.new_title: Name for the copy (optional).
    """
    try:
        service = _get_service()
        req = {"duplicateSheet": {"sourceSheetId": params.sheet_id}}
        if params.new_title:
            req["duplicateSheet"]["newSheetName"] = params.new_title
        body = {"requests": [req]}
        result = (
            service.spreadsheets()
            .batchUpdate(spreadsheetId=params.spreadsheet_id, body=body)
            .execute()
        )
        props = result["replies"][0]["duplicateSheet"]["properties"]
        return json.dumps(
            {"new_sheet_id": props["sheetId"], "title": props["title"]}, indent=2
        )
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="sheets_get_metadata",
    annotations={
        "title": "Get Spreadsheet Metadata",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def sheets_get_metadata(params: GetMetadataInput) -> str:
    """Get full metadata of a spreadsheet (title, locale, timezone, sheets).

    Args:
        params.spreadsheet_id: The Sheet ID.
    """
    try:
        service = _get_service()
        meta = (
            service.spreadsheets()
            .get(
                spreadsheetId=params.spreadsheet_id,
                fields="properties,sheets.properties",
            )
            .execute()
        )
        props = meta.get("properties", {})
        sheets = [
            {"name": s["properties"]["title"], "sheetId": s["properties"]["sheetId"]}
            for s in meta.get("sheets", [])
        ]
        return json.dumps(
            {
                "title": props.get("title"),
                "locale": props.get("locale"),
                "timeZone": props.get("timeZone"),
                "defaultFormat": props.get("defaultFormat", {}),
                "sheets": sheets,
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="sheets_update_metadata",
    annotations={
        "title": "Update Spreadsheet Metadata",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def sheets_update_metadata(params: UpdateMetadataInput) -> str:
    """Update spreadsheet title or locale.

    Args:
        params.spreadsheet_id: The Sheet ID.
        params.new_title: New title (optional).
        params.locale: New locale (optional).
    """
    try:
        service = _get_service()
        props = {}
        fields = []
        if params.new_title:
            props["title"] = params.new_title
            fields.append("title")
        if params.locale:
            props["locale"] = params.locale
            fields.append("locale")
        if not fields:
            return "Error: Provide at least new_title or locale."
        body = {
            "requests": [
                {
                    "updateSpreadsheetProperties": {
                        "properties": props,
                        "fields": ",".join(fields),
                    }
                }
            ]
        }
        service.spreadsheets().batchUpdate(
            spreadsheetId=params.spreadsheet_id, body=body
        ).execute()
        return json.dumps({"updated": fields, "status": "ok"}, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="sheets_sort_range",
    annotations={
        "title": "Sort Range in Google Sheet",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def sheets_sort_range(params: SortRangeInput) -> str:
    """Sort a range by a specific column.

    Args:
        params.spreadsheet_id: The Sheet ID.
        params.sheet_id: Numeric tab ID.
        params.start_row/end_row: Row range (0-based).
        params.start_col/end_col: Column range (0-based).
        params.sort_column: Column index to sort by.
        params.ascending: Sort direction.
    """
    try:
        service = _get_service()
        body = {
            "requests": [
                {
                    "sortRange": {
                        "range": {
                            "sheetId": params.sheet_id,
                            "startRowIndex": params.start_row,
                            "endRowIndex": params.end_row,
                            "startColumnIndex": params.start_col,
                            "endColumnIndex": params.end_col,
                        },
                        "sortSpecs": [
                            {
                                "dimensionIndex": params.sort_column,
                                "sortOrder": "ASCENDING"
                                if params.ascending
                                else "DESCENDING",
                            }
                        ],
                    }
                }
            ]
        }
        service.spreadsheets().batchUpdate(
            spreadsheetId=params.spreadsheet_id, body=body
        ).execute()
        return json.dumps(
            {
                "status": "ok",
                "sorted_by_column": params.sort_column,
                "ascending": params.ascending,
            },
            indent=2,
        )
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="sheets_auto_resize",
    annotations={
        "title": "Auto-Resize Columns",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def sheets_auto_resize(params: AutoResizeInput) -> str:
    """Auto-resize columns to fit content.

    Args:
        params.spreadsheet_id: The Sheet ID.
        params.sheet_id: Numeric tab ID.
        params.start_col/end_col: Column range (0-based).
    """
    try:
        service = _get_service()
        body = {
            "requests": [
                {
                    "autoResizeDimensions": {
                        "dimensions": {
                            "sheetId": params.sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": params.start_col,
                            "endIndex": params.end_col,
                        }
                    }
                }
            ]
        }
        service.spreadsheets().batchUpdate(
            spreadsheetId=params.spreadsheet_id, body=body
        ).execute()
        return json.dumps(
            {"status": "ok", "resized_columns": f"{params.start_col}-{params.end_col}"},
            indent=2,
        )
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="sheets_format_range",
    annotations={
        "title": "Format Range in Google Sheet",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def sheets_format_range(params: BatchFormatInput) -> str:
    """Apply formatting (bold, background color) to a cell range.

    Args:
        params.spreadsheet_id: The Sheet ID.
        params.sheet_id: Numeric tab ID.
        params.start_row/end_row/start_col/end_col: Range (0-based).
        params.bold: Set bold (optional).
        params.bg_color_hex: Background color as hex (optional).
    """
    try:
        service = _get_service()
        cell_format = {}
        fields_parts = []
        if params.bold is not None:
            cell_format["textFormat"] = {"bold": params.bold}
            fields_parts.append("userEnteredFormat.textFormat.bold")
        if params.bg_color_hex:
            h = params.bg_color_hex.lstrip("#")
            r, g, b = (
                int(h[0:2], 16) / 255,
                int(h[2:4], 16) / 255,
                int(h[4:6], 16) / 255,
            )
            cell_format["backgroundColor"] = {"red": r, "green": g, "blue": b}
            fields_parts.append("userEnteredFormat.backgroundColor")
        if not fields_parts:
            return "Error: Provide at least bold or bg_color_hex."
        body = {
            "requests": [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": params.sheet_id,
                            "startRowIndex": params.start_row,
                            "endRowIndex": params.end_row,
                            "startColumnIndex": params.start_col,
                            "endColumnIndex": params.end_col,
                        },
                        "cell": {"userEnteredFormat": cell_format},
                        "fields": ",".join(fields_parts),
                    }
                }
            ]
        }
        service.spreadsheets().batchUpdate(
            spreadsheetId=params.spreadsheet_id, body=body
        ).execute()
        return json.dumps({"status": "ok", "formatted_fields": fields_parts}, indent=2)
    except Exception as e:
        return _handle_error(e)


# ---------------------------------------------------------------------------
# Drive tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="drive_create_folder",
    annotations={
        "title": "Create Google Drive Folder",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def drive_create_folder(params: DriveCreateFolderInput) -> str:
    """Create a new folder in Google Drive.

    Args:
        params.name: Folder name.
        params.parent_id: Parent folder ID (optional, defaults to root).
    """
    try:
        drive = _get_drive_service()
        metadata = {
            "name": params.name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if params.parent_id:
            metadata["parents"] = [params.parent_id]
        folder = (
            drive.files()
            .create(body=metadata, fields="id, name, webViewLink")
            .execute()
        )
        return json.dumps(
            {
                "folder_id": folder["id"],
                "name": folder["name"],
                "url": folder.get("webViewLink", ""),
            },
            indent=2,
        )
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="drive_move_file",
    annotations={
        "title": "Move File to Folder",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def drive_move_file(params: DriveMoveFileInput) -> str:
    """Move a file/spreadsheet to a specific Drive folder.

    Args:
        params.file_id: ID of the file to move.
        params.folder_id: Target folder ID.
    """
    try:
        drive = _get_drive_service()
        file_info = drive.files().get(fileId=params.file_id, fields="parents").execute()
        previous_parents = ",".join(file_info.get("parents", []))
        result = (
            drive.files()
            .update(
                fileId=params.file_id,
                addParents=params.folder_id,
                removeParents=previous_parents,
                fields="id, name, parents",
            )
            .execute()
        )
        return json.dumps(
            {
                "file_id": result["id"],
                "name": result.get("name"),
                "new_parents": result.get("parents", []),
            },
            indent=2,
        )
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="drive_list_folder",
    annotations={
        "title": "List Folder Contents",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def drive_list_folder(params: DriveListFolderInput) -> str:
    """List files and subfolders in a Google Drive folder.

    Args:
        params.folder_id: Folder ID.
        params.max_results: Max items to return.
    """
    try:
        drive = _get_drive_service()
        q = f"'{params.folder_id}' in parents and trashed = false"
        result = (
            drive.files()
            .list(
                q=q,
                pageSize=params.max_results,
                fields="files(id, name, mimeType, modifiedTime)",
                orderBy="modifiedTime desc",
            )
            .execute()
        )
        files = [
            {
                "id": f["id"],
                "name": f["name"],
                "type": f["mimeType"],
                "modified": f.get("modifiedTime", ""),
            }
            for f in result.get("files", [])
        ]
        return json.dumps(
            {"folder_id": params.folder_id, "count": len(files), "files": files},
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="drive_search_files",
    annotations={
        "title": "Search Google Drive Files",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def drive_search_files(params: DriveSearchFilesInput) -> str:
    """Search for files by name in Google Drive.

    Args:
        params.query: Name fragment to search.
        params.file_type: MIME type filter (optional).
        params.max_results: Max results.
    """
    try:
        drive = _get_drive_service()
        q = f"name contains '{params.query}' and trashed = false"
        if params.file_type:
            q += f" and mimeType='{params.file_type}'"
        result = (
            drive.files()
            .list(
                q=q,
                pageSize=params.max_results,
                fields="files(id, name, mimeType, modifiedTime, webViewLink)",
                orderBy="modifiedTime desc",
            )
            .execute()
        )
        files = [
            {
                "id": f["id"],
                "name": f["name"],
                "type": f["mimeType"],
                "modified": f.get("modifiedTime", ""),
                "url": f.get("webViewLink", ""),
            }
            for f in result.get("files", [])
        ]
        return json.dumps(
            {"query": params.query, "count": len(files), "files": files},
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="drive_delete_file",
    annotations={
        "title": "Delete/Trash File in Drive",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def drive_delete_file(params: DriveDeleteFileInput) -> str:
    """Move a file to trash in Google Drive (recoverable).

    Args:
        params.file_id: ID of the file to trash.
    """
    try:
        drive = _get_drive_service()
        drive.files().update(fileId=params.file_id, body={"trashed": True}).execute()
        return json.dumps({"file_id": params.file_id, "status": "trashed"}, indent=2)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="drive_get_file_info",
    annotations={
        "title": "Get File Info from Drive",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def drive_get_file_info(params: DriveGetFileInfoInput) -> str:
    """Get metadata about a file in Google Drive.

    Args:
        params.file_id: ID of the file.
    """
    try:
        drive = _get_drive_service()
        f = (
            drive.files()
            .get(
                fileId=params.file_id,
                fields="id, name, mimeType, modifiedTime, createdTime, size, parents, webViewLink, owners",
            )
            .execute()
        )
        return json.dumps(
            {
                "id": f["id"],
                "name": f["name"],
                "type": f["mimeType"],
                "created": f.get("createdTime", ""),
                "modified": f.get("modifiedTime", ""),
                "size": f.get("size"),
                "parents": f.get("parents", []),
                "url": f.get("webViewLink", ""),
                "owners": [o.get("emailAddress", "") for o in f.get("owners", [])],
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="drive_share_file",
    annotations={
        "title": "Share File in Drive",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def drive_share_file(params: DriveShareFileInput) -> str:
    """Share a file with a specific email address.

    Args:
        params.file_id: ID of the file to share.
        params.email: Email to share with.
        params.role: Permission role (reader/writer/commenter).
    """
    try:
        drive = _get_drive_service()
        permission = {"type": "user", "role": params.role, "emailAddress": params.email}
        result = (
            drive.permissions()
            .create(
                fileId=params.file_id, body=permission, fields="id, role, emailAddress"
            )
            .execute()
        )
        return json.dumps(
            {
                "permission_id": result["id"],
                "role": result.get("role"),
                "email": result.get("emailAddress"),
            },
            indent=2,
        )
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="drive_copy_file",
    annotations={
        "title": "Copy File in Drive",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def drive_copy_file(params: DriveCopyFileInput) -> str:
    """Copy a file in Google Drive.

    Args:
        params.file_id: ID of the file to copy.
        params.new_name: Name for the copy (optional).
        params.parent_id: Target folder ID (optional).
    """
    try:
        drive = _get_drive_service()
        body = {}
        if params.new_name:
            body["name"] = params.new_name
        if params.parent_id:
            body["parents"] = [params.parent_id]
        result = (
            drive.files()
            .copy(fileId=params.file_id, body=body, fields="id, name, webViewLink")
            .execute()
        )
        return json.dumps(
            {
                "id": result["id"],
                "name": result["name"],
                "url": result.get("webViewLink", ""),
            },
            indent=2,
        )
    except Exception as e:
        return _handle_error(e)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
