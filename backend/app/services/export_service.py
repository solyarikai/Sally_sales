import csv
import io
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ExportService:
    """Service for exporting data to various formats"""
    
    @staticmethod
    def prepare_row_data(
        rows: List[Dict[str, Any]], 
        columns: List[str],
        include_enriched: bool = True
    ) -> List[Dict[str, Any]]:
        """Prepare row data for export, merging original and enriched data"""
        result = []
        for row in rows:
            row_dict = {}
            # Add original data
            for col in columns:
                row_dict[col] = row.get("data", {}).get(col, "")
            
            # Add enriched data if requested
            if include_enriched:
                enriched = row.get("enriched_data", {})
                for key, value in enriched.items():
                    # Use enriched_ prefix if key conflicts with original columns
                    col_name = f"enriched_{key}" if key in columns else key
                    row_dict[col_name] = value
            
            result.append(row_dict)
        return result
    
    @staticmethod
    def export_to_csv(
        rows: List[Dict[str, Any]],
        columns: List[str],
        include_enriched: bool = True
    ) -> str:
        """Export data to CSV format"""
        if not rows:
            return ""
        
        # Prepare data
        prepared_rows = ExportService.prepare_row_data(rows, columns, include_enriched)
        
        # Get all columns including enriched ones
        all_columns = set(columns)
        for row in prepared_rows:
            all_columns.update(row.keys())
        
        # Order columns: original first, then enriched
        ordered_columns = list(columns)
        enriched_cols = [c for c in all_columns if c not in columns]
        ordered_columns.extend(sorted(enriched_cols))
        
        # Write CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=ordered_columns)
        writer.writeheader()
        for row in prepared_rows:
            writer.writerow({col: row.get(col, "") for col in ordered_columns})
        
        return output.getvalue()
    
    @staticmethod
    def export_to_instantly_csv(
        rows: List[Dict[str, Any]],
        columns: List[str],
        email_column: str,
        first_name_column: Optional[str] = None,
        last_name_column: Optional[str] = None,
        company_column: Optional[str] = None,
        custom_columns: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Export data in Instantly.ai compatible format
        Required columns: email
        Optional: firstName, lastName, companyName, + custom variables
        """
        prepared_rows = ExportService.prepare_row_data(rows, columns, include_enriched=True)
        
        output = io.StringIO()
        
        # Instantly requires specific column names
        instantly_columns = ["email"]
        column_mapping = {"email": email_column}
        
        if first_name_column:
            instantly_columns.append("firstName")
            column_mapping["firstName"] = first_name_column
        
        if last_name_column:
            instantly_columns.append("lastName")
            column_mapping["lastName"] = last_name_column
            
        if company_column:
            instantly_columns.append("companyName")
            column_mapping["companyName"] = company_column
        
        # Add custom columns (for personalization variables)
        if custom_columns:
            for instantly_col, source_col in custom_columns.items():
                instantly_columns.append(instantly_col)
                column_mapping[instantly_col] = source_col
        
        writer = csv.DictWriter(output, fieldnames=instantly_columns)
        writer.writeheader()
        
        for row in prepared_rows:
            instantly_row = {}
            for instantly_col, source_col in column_mapping.items():
                instantly_row[instantly_col] = row.get(source_col, "")
            writer.writerow(instantly_row)
        
        return output.getvalue()
    
    @staticmethod
    def export_to_smartlead_csv(
        rows: List[Dict[str, Any]],
        columns: List[str],
        linkedin_url_column: Optional[str] = None,
        first_name_column: Optional[str] = None,
        last_name_column: Optional[str] = None,
        company_column: Optional[str] = None,
        email_column: Optional[str] = None,
        message_column: Optional[str] = None
    ) -> str:
        """
        Export data in GetSales.io compatible format for LinkedIn automation
        Required: linkedinUrl or email
        Optional: firstName, lastName, company, message
        """
        prepared_rows = ExportService.prepare_row_data(rows, columns, include_enriched=True)
        
        output = io.StringIO()
        
        # GetSales column format
        getsales_columns = []
        column_mapping = {}
        
        if linkedin_url_column:
            getsales_columns.append("linkedinUrl")
            column_mapping["linkedinUrl"] = linkedin_url_column
        
        if first_name_column:
            getsales_columns.append("firstName")
            column_mapping["firstName"] = first_name_column
        
        if last_name_column:
            getsales_columns.append("lastName") 
            column_mapping["lastName"] = last_name_column
            
        if company_column:
            getsales_columns.append("company")
            column_mapping["company"] = company_column
            
        if email_column:
            getsales_columns.append("email")
            column_mapping["email"] = email_column
            
        if message_column:
            getsales_columns.append("message")
            column_mapping["message"] = message_column
        
        if not getsales_columns:
            # Export all columns if no mapping specified
            getsales_columns = list(prepared_rows[0].keys()) if prepared_rows else []
            column_mapping = {c: c for c in getsales_columns}
        
        writer = csv.DictWriter(output, fieldnames=getsales_columns)
        writer.writeheader()
        
        for row in prepared_rows:
            getsales_row = {}
            for getsales_col, source_col in column_mapping.items():
                getsales_row[getsales_col] = row.get(source_col, "")
            writer.writerow(getsales_row)
        
        return output.getvalue()
    
    @staticmethod
    def generate_google_sheets_data(
        rows: List[Dict[str, Any]],
        columns: List[str],
        include_enriched: bool = True
    ) -> List[List[Any]]:
        """
        Prepare data for Google Sheets API
        Returns list of rows where first row is headers
        """
        prepared_rows = ExportService.prepare_row_data(rows, columns, include_enriched)
        
        if not prepared_rows:
            return [columns]
        
        # Get all columns
        all_columns = set(columns)
        for row in prepared_rows:
            all_columns.update(row.keys())
        
        ordered_columns = list(columns)
        enriched_cols = [c for c in all_columns if c not in columns]
        ordered_columns.extend(sorted(enriched_cols))
        
        # Build result
        result = [ordered_columns]
        for row in prepared_rows:
            result.append([row.get(col, "") for col in ordered_columns])
        
        return result


export_service = ExportService()
