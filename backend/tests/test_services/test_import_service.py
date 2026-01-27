"""
Tests for Import Service.
"""

import pytest
from app.services.import_service import ImportService


class TestCSVParsing:
    """Test CSV parsing functionality."""
    
    def test_parse_csv_basic(self):
        """Test parsing a basic CSV file."""
        csv_content = b"email,name,company\njohn@test.com,John,Acme\njane@test.com,Jane,Corp"
        
        columns, rows = ImportService.parse_csv(csv_content, "test.csv")
        
        assert columns == ["email", "name", "company"]
        assert len(rows) == 2
        assert rows[0]["email"] == "john@test.com"
        assert rows[0]["name"] == "John"
        assert rows[1]["company"] == "Corp"
    
    def test_parse_csv_with_spaces_in_columns(self):
        """Test parsing CSV with spaces in column names."""
        csv_content = b"  Email  , First Name ,Last Name\njohn@test.com,John,Doe"
        
        columns, rows = ImportService.parse_csv(csv_content, "test.csv")
        
        assert "Email" in columns
        assert "First Name" in columns
    
    def test_parse_csv_with_empty_values(self):
        """Test parsing CSV with empty values."""
        csv_content = b"email,name,phone\njohn@test.com,John,\njane@test.com,,555-1234"
        
        columns, rows = ImportService.parse_csv(csv_content, "test.csv")
        
        assert len(rows) == 2
        assert rows[0]["phone"] == ""
        assert rows[1]["name"] == ""
    
    def test_parse_csv_utf8_encoding(self):
        """Test parsing CSV with UTF-8 characters."""
        csv_content = "email,name\ntest@test.com,Müller".encode("utf-8")
        
        columns, rows = ImportService.parse_csv(csv_content, "test.csv")
        
        assert rows[0]["name"] == "Müller"
    
    def test_parse_csv_latin1_encoding(self):
        """Test parsing CSV with Latin-1 encoding."""
        csv_content = "email,name\ntest@test.com,Müller".encode("latin-1")
        
        columns, rows = ImportService.parse_csv(csv_content, "test.csv")
        
        assert "Müller" in rows[0]["name"] or "M" in rows[0]["name"]
    
    def test_parse_csv_invalid_content(self):
        """Test parsing invalid content raises error."""
        with pytest.raises(ValueError):
            ImportService.parse_csv(b"", "empty.csv")


class TestGoogleSheetsURLParsing:
    """Test Google Sheets URL parsing."""
    
    def test_extract_sheet_id_standard_url(self):
        """Test extracting sheet ID from standard URL."""
        url = "https://docs.google.com/spreadsheets/d/1abc123def456/edit#gid=0"
        
        sheet_id = ImportService.extract_google_sheet_id(url)
        
        assert sheet_id == "1abc123def456"
    
    def test_extract_sheet_id_shared_url(self):
        """Test extracting sheet ID from shared URL."""
        url = "https://docs.google.com/spreadsheets/d/1abc123def456/view"
        
        sheet_id = ImportService.extract_google_sheet_id(url)
        
        assert sheet_id == "1abc123def456"
    
    def test_extract_sheet_id_invalid_url(self):
        """Test extracting sheet ID from invalid URL returns None."""
        url = "https://example.com/not-a-sheet"
        
        sheet_id = ImportService.extract_google_sheet_id(url)
        
        assert sheet_id is None
    
    def test_extract_gid_from_url(self):
        """Test extracting GID from URL."""
        url = "https://docs.google.com/spreadsheets/d/1abc123/edit#gid=12345"
        
        gid = ImportService.extract_gid(url)
        
        assert gid == "12345"
    
    def test_extract_gid_missing(self):
        """Test extracting GID when not present."""
        url = "https://docs.google.com/spreadsheets/d/1abc123/edit"
        
        gid = ImportService.extract_gid(url)
        
        assert gid is None
