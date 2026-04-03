"""
Default Field Mappings for Lead Import

Provides smart default mappings so users don't need to manually configure
ALL fields every time. Maps standard fields to prospect fields based on
common naming conventions.
"""

from typing import List, Dict


# Common field name variations mapped to standard prospect fields
FIELD_NAME_PATTERNS = {
    "email": ["email", "e-mail", "email_address", "emailaddress", "mail"],
    "first_name": ["first_name", "firstname", "first", "given_name", "givenname"],
    "last_name": ["last_name", "lastname", "last", "surname", "family_name"],
    "full_name": ["full_name", "fullname", "name", "contact_name", "contactname"],
    "company_name": ["company_name", "companyname", "company", "organization", "organisation", "org"],
    "job_title": ["job_title", "jobtitle", "title", "position", "role"],
    "phone": ["phone", "phone_number", "phonenumber", "telephone", "tel", "mobile"],
    "linkedin_url": ["linkedin_url", "linkedin", "linkedin_profile", "linkedinurl"],
    "website": ["website", "url", "company_website", "site", "web"],
    "location": ["location", "address", "city_state", "region"],
    "country": ["country", "nation", "country_name"],
    "city": ["city", "town"],
    "industry": ["industry", "sector", "vertical"],
    "company_size": ["company_size", "companysize", "employees", "employee_count", "size"],
    "company_domain": ["company_domain", "domain", "company_url"],
}


def normalize_column_name(name: str) -> str:
    """Normalize column name for comparison"""
    return name.lower().strip().replace(" ", "_").replace("-", "_")


def find_target_field(column_name: str) -> str:
    """
    Find the target prospect field for a given column name.
    Returns the field name if matched, or 'custom' for unknown columns.
    """
    normalized = normalize_column_name(column_name)
    
    for target_field, patterns in FIELD_NAME_PATTERNS.items():
        if normalized in patterns:
            return target_field
    
    return "custom"


def get_default_mappings() -> List[Dict]:
    """
    Get generic default field mappings.
    
    These cover the most common column name patterns found in lead lists.
    """
    return [
        # Email variations
        {"source_column": "Email", "target_field": "email"},
        {"source_column": "email", "target_field": "email"},
        {"source_column": "E-mail", "target_field": "email"},
        
        # Name fields
        {"source_column": "First Name", "target_field": "first_name"},
        {"source_column": "first_name", "target_field": "first_name"},
        {"source_column": "FirstName", "target_field": "first_name"},
        {"source_column": "Last Name", "target_field": "last_name"},
        {"source_column": "last_name", "target_field": "last_name"},
        {"source_column": "LastName", "target_field": "last_name"},
        {"source_column": "Full Name", "target_field": "full_name"},
        {"source_column": "full_name", "target_field": "full_name"},
        {"source_column": "Name", "target_field": "full_name"},
        
        # Company fields
        {"source_column": "Company Name", "target_field": "company_name"},
        {"source_column": "company_name", "target_field": "company_name"},
        {"source_column": "Company", "target_field": "company_name"},
        {"source_column": "Organization", "target_field": "company_name"},
        
        # Contact fields
        {"source_column": "Phone", "target_field": "phone"},
        {"source_column": "phone", "target_field": "phone"},
        {"source_column": "Phone Number", "target_field": "phone"},
        {"source_column": "Telephone", "target_field": "phone"},
        
        # Job info
        {"source_column": "Title", "target_field": "job_title"},
        {"source_column": "Job Title", "target_field": "job_title"},
        {"source_column": "job_title", "target_field": "job_title"},
        {"source_column": "Position", "target_field": "job_title"},
        
        # Social/Web
        {"source_column": "LinkedIn", "target_field": "linkedin_url"},
        {"source_column": "LinkedIn URL", "target_field": "linkedin_url"},
        {"source_column": "LinkedIn Profile", "target_field": "linkedin_url"},
        {"source_column": "linkedin_url", "target_field": "linkedin_url"},
        {"source_column": "Website", "target_field": "website"},
        {"source_column": "website", "target_field": "website"},
        {"source_column": "URL", "target_field": "website"},
        
        # Location
        {"source_column": "Location", "target_field": "location"},
        {"source_column": "location", "target_field": "location"},
        {"source_column": "Country", "target_field": "country"},
        {"source_column": "country", "target_field": "country"},
        {"source_column": "City", "target_field": "city"},
        {"source_column": "city", "target_field": "city"},
        
        # Industry/Company info
        {"source_column": "Industry", "target_field": "industry"},
        {"source_column": "industry", "target_field": "industry"},
        {"source_column": "Company Size", "target_field": "company_size"},
        {"source_column": "Employees", "target_field": "company_size"},
        {"source_column": "Domain", "target_field": "company_domain"},
        {"source_column": "company_domain", "target_field": "company_domain"},
    ]


def smart_field_mapping(available_columns: List[str], company_name: str = None) -> List[Dict]:
    """
    Smart field mapping based on available columns.
    
    Analyzes available columns and creates appropriate mappings:
    - Standard fields -> direct mapping to prospect fields
    - Unknown fields -> custom fields with original names
    
    Args:
        available_columns: List of column names from dataset
        company_name: Optional company name (not used, kept for API compatibility)
    
    Returns:
        List of field mappings
    """
    mappings = []
    mapped_columns = set()
    
    # First, try to match known patterns
    default_mappings = get_default_mappings()
    default_sources = {m["source_column"]: m["target_field"] for m in default_mappings}
    
    for col in available_columns:
        # Check if column matches a known pattern
        if col in default_sources:
            mappings.append({
                "source_column": col,
                "target_field": default_sources[col]
            })
            mapped_columns.add(col)
        else:
            # Try to find target field using normalized name
            target = find_target_field(col)
            if target != "custom":
                mappings.append({
                    "source_column": col,
                    "target_field": target
                })
                mapped_columns.add(col)
    
    # Add remaining columns as custom fields
    skip_columns = {"id", "row_index", "dataset_id", "created_at", "updated_at"}
    for col in available_columns:
        if col not in mapped_columns and col.lower() not in skip_columns:
            mappings.append({
                "source_column": col,
                "target_field": "custom",
                "custom_field_name": col.replace(" ", "_").replace("-", "_")
            })
    
    return mappings
