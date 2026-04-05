#!/usr/bin/env python3
"""
Google Sheets MCP Server.

Provides tools to read, write, search, and manage Google Sheets
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

mcp = FastMCP("google_sheets_mcp")


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
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
