"""
Field Mapper Service
Smart mapping of source columns to MasterLead core fields.
Uses: 1) Aliases, 2) Pattern detection from sample data, 3) AI fallback
"""
import re
from typing import Dict, List, Any, Optional, Tuple
from difflib import SequenceMatcher
import logging

from app.schemas.prospect import FieldMapping, FieldMappingSuggestion, CORE_FIELD_NAMES

logger = logging.getLogger(__name__)


# Comprehensive aliases for each core field
FIELD_ALIASES: Dict[str, List[str]] = {
    "email": [
        "email", "e-mail", "email_address", "emailaddress", "mail", "email address",
        "work_email", "work email", "business_email", "business email", "contact_email",
        "primary_email", "электронная почта", "почта", "емейл", "имейл", "personal_email",
        "corporate_email", "user_email", "lead_email"
    ],
    "linkedin_url": [
        "linkedin", "linkedin_url", "linkedin url", "linkedin_profile", "linkedin profile",
        "li_url", "linkedinurl", "linkedin link", "person linkedin url", "profile url",
        "linkedin_profile_url", "member_urn_id", "линкедин", "li_profile", "linkedin_link",
        "person_linkedin", "linkedin_person_url"
    ],
    "first_name": [
        "first_name", "firstname", "first name", "first", "given_name", "given name",
        "fname", "name_first", "имя", "forename", "christian_name"
    ],
    "last_name": [
        "last_name", "lastname", "last name", "last", "surname", "family_name",
        "family name", "lname", "name_last", "фамилия", "second_name"
    ],
    "full_name": [
        "full_name", "fullname", "full name", "name", "contact_name", "contact name",
        "person_name", "person name", "полное имя", "фио", "display_name", "complete_name"
    ],
    "company_name": [
        "company", "company_name", "companyname", "company name", "organization",
        "organisation", "org", "employer", "business_name", "business name",
        "current_company", "current company", "компания", "организация", "firm",
        "account_name", "account", "company_title", "org_name"
    ],
    "company_domain": [
        "company_domain", "domain", "company domain", "website_domain", "company_website",
        "primary_domain", "домен", "company_url_domain", "org_domain", "business_domain"
    ],
    "company_linkedin": [
        "company_linkedin", "company linkedin", "company_linkedin_url", 
        "organization_linkedin", "org_linkedin", "company linkedin url",
        "company_li_url", "employer_linkedin"
    ],
    "job_title": [
        "job_title", "jobtitle", "job title", "title", "position", "role",
        "job_position", "job position", "occupation", "headline",
        "current_title", "current title", "должность", "позиция", "job_role",
        "professional_title", "work_title", "designation"
    ],
    "phone": [
        "phone", "phone_number", "phone number", "telephone", "tel", "mobile",
        "mobile_phone", "mobile phone", "cell", "cell_phone", "direct_phone",
        "work_phone", "work phone", "телефон", "мобильный", "contact_phone",
        "primary_phone", "business_phone", "direct_dial"
    ],
    "location": [
        "location", "address", "full_address", "full address", "geo",
        "person_location", "person location", "местоположение", "адрес",
        "person_city", "headquarters", "hq_location"
    ],
    "country": [
        "country", "country_name", "country name", "nation", "страна",
        "country_code", "region", "country_region"
    ],
    "city": [
        "city", "city_name", "city name", "town", "город", "locality", "metro"
    ],
    "industry": [
        "industry", "sector", "vertical", "business_type", "company_industry",
        "индустрия", "отрасль", "industry_name", "company_sector"
    ],
    "company_size": [
        "company_size", "companysize", "company size", "employees", "employee_count",
        "employee count", "headcount", "team_size", "размер компании", "staff_count",
        "company_headcount", "num_employees", "employee_range"
    ],
    "website": [
        "website", "site", "url", "web", "company_url", "company_website",
        "homepage", "сайт", "веб-сайт", "web_address", "company_site"
    ],
}

# Regex patterns for detecting data types from values
DATA_PATTERNS = {
    "email": re.compile(r'^[\w\.-]+@[\w\.-]+\.\w+$', re.IGNORECASE),
    "linkedin_url": re.compile(r'linkedin\.com/(in|company|pub)/[\w\-]+', re.IGNORECASE),
    "phone": re.compile(r'^[\+]?[\d\s\-\(\)]{7,20}$'),
    "website": re.compile(r'^(https?://)?(www\.)?[\w\-]+\.[\w\-\.]+(/.*)?$', re.IGNORECASE),
    "company_domain": re.compile(r'^[\w\-]+\.[\w\-\.]+$'),
}

# Patterns for detecting specific value types
def detect_email(value: str) -> bool:
    """Check if value looks like an email"""
    if not value or not isinstance(value, str):
        return False
    return bool(DATA_PATTERNS["email"].match(value.strip()))

def detect_linkedin_url(value: str) -> bool:
    """Check if value looks like a LinkedIn URL"""
    if not value or not isinstance(value, str):
        return False
    return bool(DATA_PATTERNS["linkedin_url"].search(value.strip()))

def detect_phone(value: str) -> bool:
    """Check if value looks like a phone number"""
    if not value or not isinstance(value, str):
        return False
    cleaned = re.sub(r'[^\d\+\-\(\)\s]', '', str(value))
    return len(cleaned) >= 7 and bool(DATA_PATTERNS["phone"].match(cleaned))

def detect_url(value: str) -> bool:
    """Check if value looks like a URL"""
    if not value or not isinstance(value, str):
        return False
    return bool(DATA_PATTERNS["website"].match(value.strip()))

def detect_domain(value: str) -> bool:
    """Check if value looks like a domain"""
    if not value or not isinstance(value, str):
        return False
    value = value.strip().lower()
    # Not a full URL, just domain
    if value.startswith('http'):
        return False
    return bool(DATA_PATTERNS["company_domain"].match(value)) and '/' not in value


def normalize_column_name(name: str) -> str:
    """Normalize column name for comparison"""
    normalized = name.lower().strip()
    normalized = re.sub(r'[\s\-\.]+', '_', normalized)
    normalized = re.sub(r'[^\w]', '', normalized)
    return normalized


def calculate_similarity(s1: str, s2: str) -> float:
    """Calculate string similarity ratio (0-1)"""
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def find_best_alias_match(column: str) -> Tuple[Optional[str], float]:
    """Find the best matching core field for a column using aliases."""
    normalized = normalize_column_name(column)
    
    best_match = None
    best_score = 0.0
    
    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            normalized_alias = normalize_column_name(alias)
            
            # Exact match
            if normalized == normalized_alias:
                return (field, 1.0)
            
            # Contains match (e.g., "person_email_address" contains "email")
            if normalized_alias in normalized or normalized in normalized_alias:
                score = 0.9
                if score > best_score:
                    best_score = score
                    best_match = field
                continue
            
            # Fuzzy match
            similarity = calculate_similarity(normalized, normalized_alias)
            if similarity > best_score and similarity >= 0.75:
                best_score = similarity
                best_match = field
    
    return (best_match, best_score)


def detect_field_from_values(column: str, sample_values: List[Any]) -> Tuple[Optional[str], float]:
    """
    Detect field type by analyzing sample values.
    Returns (field_name, confidence) or (None, 0.0)
    """
    if not sample_values:
        return (None, 0.0)
    
    # Filter valid string values
    values = [str(v).strip() for v in sample_values if v and str(v).strip()]
    if not values:
        return (None, 0.0)
    
    # Count matches for each type
    email_count = sum(1 for v in values if detect_email(v))
    linkedin_count = sum(1 for v in values if detect_linkedin_url(v))
    phone_count = sum(1 for v in values if detect_phone(v))
    url_count = sum(1 for v in values if detect_url(v) and not detect_linkedin_url(v))
    domain_count = sum(1 for v in values if detect_domain(v))
    
    total = len(values)
    threshold = 0.6  # At least 60% of values should match
    
    # Check patterns in order of specificity
    if linkedin_count / total >= threshold:
        # Check if it's company linkedin or person linkedin
        col_lower = column.lower()
        if 'company' in col_lower or 'org' in col_lower:
            return ("company_linkedin", 0.9)
        return ("linkedin_url", 0.9)
    
    if email_count / total >= threshold:
        return ("email", 0.95)
    
    if phone_count / total >= threshold:
        return ("phone", 0.85)
    
    if domain_count / total >= threshold:
        return ("company_domain", 0.8)
    
    if url_count / total >= threshold:
        return ("website", 0.8)
    
    return (None, 0.0)


async def get_ai_mapping(
    column: str,
    sample_values: List[Any],
    core_fields: List[str] = CORE_FIELD_NAMES
) -> Tuple[str, float]:
    """
    Use AI to determine the best field mapping for ambiguous columns.
    Returns (field_name or "custom", confidence)
    """
    try:
        from app.services.openai_service import openai_service
        
        if not openai_service.client:
            logger.warning("OpenAI not configured, skipping AI mapping")
            return ("custom", 0.5)
        
        # Build sample values string
        samples = [str(v) for v in sample_values[:5] if v and str(v).strip()]
        samples_str = ", ".join(f'"{s}"' for s in samples[:3]) if samples else "no sample values"
        
        prompt = f"""Analyze this CSV column and determine which standard CRM field it maps to.

Column name: "{column}"
Sample values: {samples_str}

Available standard fields:
- email (email addresses)
- linkedin_url (LinkedIn profile URLs for people)
- first_name (person's first name)
- last_name (person's last name) 
- full_name (complete name)
- company_name (company/organization name)
- company_domain (company website domain like "acme.com")
- company_linkedin (LinkedIn URL for companies)
- job_title (person's role/position)
- phone (phone numbers)
- location (address or location)
- country
- city
- industry (business sector)
- company_size (employee count)
- website (company website URL)

If the column clearly matches one of these fields, respond with ONLY the field name.
If it doesn't match any standard field, respond with "custom".

Your response (one word only):"""

        result = await openai_service.enrich_single_row(
            prompt=prompt,
            system_prompt="You are a data mapping assistant. Respond with only the field name, nothing else.",
            model="gpt-4o-mini"
        )
        
        if result.get("success"):
            field = result.get("result", "").strip().lower().replace('"', '').replace("'", "")
            if field in core_fields:
                return (field, 0.85)
            return ("custom", 0.7)
        
    except Exception as e:
        logger.error(f"AI mapping error: {e}")
    
    return ("custom", 0.5)


async def suggest_mappings(
    columns: List[str],
    sample_data: Optional[List[Dict[str, Any]]] = None,
    use_ai: bool = True
) -> FieldMappingSuggestion:
    """
    Generate field mapping suggestions for a list of columns.
    
    Strategy:
    1. Pattern detection from sample values (most reliable - actual data)
    2. Exact/high-confidence alias matching
    3. AI fallback for remaining ambiguous columns
    """
    mappings: List[FieldMapping] = []
    used_fields: set = set()
    pending_ai: List[Tuple[str, List[Any]]] = []
    
    for column in columns:
        # Skip internal/enriched columns
        if column.startswith("_") or column.startswith("enriched_"):
            mappings.append(FieldMapping(
                source_column=column,
                target_field="custom",
                custom_field_name=column,
                confidence=1.0
            ))
            continue
        
        # Collect sample values for this column
        samples = []
        if sample_data:
            for row in sample_data[:5]:
                val = row.get(column)
                if val is not None:
                    samples.append(val)
        
        # Step 1: Try pattern detection from values FIRST (most reliable)
        # Pattern detection looks at actual data, not column names
        detected_field, detected_confidence = detect_field_from_values(column, samples)
        
        if detected_field and detected_field not in used_fields and detected_confidence >= 0.8:
            mappings.append(FieldMapping(
                source_column=column,
                target_field=detected_field,
                confidence=detected_confidence
            ))
            used_fields.add(detected_field)
            continue
        
        # Step 2: Try alias matching on column name
        field, alias_confidence = find_best_alias_match(column)
        
        # If exact alias match, use it
        if field and field not in used_fields and alias_confidence >= 0.95:
            mappings.append(FieldMapping(
                source_column=column,
                target_field=field,
                confidence=alias_confidence
            ))
            used_fields.add(field)
            continue
        
        # If pattern detected something with lower confidence, prefer it over partial alias
        if detected_field and detected_field not in used_fields and detected_confidence > 0:
            mappings.append(FieldMapping(
                source_column=column,
                target_field=detected_field,
                confidence=detected_confidence
            ))
            used_fields.add(detected_field)
            continue
        
        # Good alias match without pattern detection
        if field and field not in used_fields and alias_confidence >= 0.75:
            mappings.append(FieldMapping(
                source_column=column,
                target_field=field,
                confidence=alias_confidence
            ))
            used_fields.add(field)
            continue
        
        # Step 3: Queue for AI if alias had partial match
        if field and alias_confidence >= 0.5:
            pending_ai.append((column, samples, field, alias_confidence))
        else:
            pending_ai.append((column, samples, None, 0.0))
    
    # Process AI mappings
    for item in pending_ai:
        if len(item) == 4:
            column, samples, partial_field, partial_conf = item
        else:
            column, samples = item
            partial_field, partial_conf = None, 0.0
        
        if use_ai:
            field, confidence = await get_ai_mapping(column, samples)
            
            if field != "custom" and field not in used_fields:
                mappings.append(FieldMapping(
                    source_column=column,
                    target_field=field,
                    confidence=confidence
                ))
                used_fields.add(field)
            elif partial_field and partial_field not in used_fields:
                # Use partial match if AI didn't help
                mappings.append(FieldMapping(
                    source_column=column,
                    target_field=partial_field,
                    confidence=partial_conf
                ))
                used_fields.add(partial_field)
            else:
                mappings.append(FieldMapping(
                    source_column=column,
                    target_field="custom",
                    custom_field_name=column,
                    confidence=0.5
                ))
        else:
            # No AI - use partial match or custom
            if partial_field and partial_field not in used_fields:
                mappings.append(FieldMapping(
                    source_column=column,
                    target_field=partial_field,
                    confidence=partial_conf
                ))
                used_fields.add(partial_field)
            else:
                mappings.append(FieldMapping(
                    source_column=column,
                    target_field="custom",
                    custom_field_name=column,
                    confidence=0.5
                ))
    
    return FieldMappingSuggestion(
        mappings=mappings,
        unmapped_columns=[]
    )


def apply_mapping(
    row_data: Dict[str, Any],
    enriched_data: Dict[str, Any],
    mappings: List[FieldMapping]
) -> Dict[str, Any]:
    """Apply field mappings to a row's data."""
    result = {field: None for field in CORE_FIELD_NAMES}
    result["custom_fields"] = {}
    
    all_data = {**row_data, **enriched_data}
    
    for mapping in mappings:
        value = all_data.get(mapping.source_column)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
            
        if mapping.target_field == "custom":
            field_name = mapping.custom_field_name or mapping.source_column
            result["custom_fields"][field_name] = value
        else:
            result[mapping.target_field] = value
    
    return result


class FieldMapperService:
    async def suggest_mappings(
        self,
        columns: List[str],
        sample_data: Optional[List[Dict[str, Any]]] = None,
        use_ai: bool = True
    ) -> FieldMappingSuggestion:
        return await suggest_mappings(columns, sample_data, use_ai)
    
    def apply_mapping(
        self,
        row_data: Dict[str, Any],
        enriched_data: Dict[str, Any],
        mappings: List[FieldMapping]
    ) -> Dict[str, Any]:
        return apply_mapping(row_data, enriched_data, mappings)


field_mapper_service = FieldMapperService()
