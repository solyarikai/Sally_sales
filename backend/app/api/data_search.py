"""
Data Search API - Explee-like natural language search for companies.

Uses AI to parse natural language queries into structured filters,
then searches using Apollo or other data providers.

Features:
1. Direct Search: Natural language → AI parsing → structured filters → search
2. Reverse Engineering: Example companies → extract patterns → generate filters
3. Verification: Crona scrape + OpenAI verify - IMPLEMENTED
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import logging
import json
import re

from app.services.openai_service import openai_service
from app.services.reverse_engineering_service import (
    ReverseEngineeringService,
    CompanyProfile,
    get_reverse_engineering_service
)
from app.services.verification_service import (
    verification_service,
    VerificationCriteria,
    CompanyToVerify,
    VerificationResult,
    BatchVerificationResult
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data-search", tags=["data-search"])


class SearchFilter(BaseModel):
    field: str
    value: str
    operator: Optional[str] = "equals"


class CompanyResult(BaseModel):
    id: str
    name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    employee_count: Optional[str] = None
    location: Optional[str] = None
    founded_year: Optional[int] = None
    linkedin_url: Optional[str] = None
    description: Optional[str] = None
    technologies: Optional[List[str]] = None
    revenue_range: Optional[str] = None
    relevance_score: Optional[float] = None
    verified: Optional[bool] = None


class ParseQueryRequest(BaseModel):
    query: str


class ParseQueryResponse(BaseModel):
    filters: List[SearchFilter]
    intent: str
    clarifications: Optional[List[str]] = None


class SearchRequest(BaseModel):
    filters: List[SearchFilter]
    page: Optional[int] = 1
    limit: Optional[int] = 25


class SearchResponse(BaseModel):
    companies: List[CompanyResult]
    total: int
    filters_applied: List[SearchFilter]
    suggestions: Optional[List[str]] = None
    next_page_token: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[dict]] = None


class ChatResponse(BaseModel):
    response: str
    filters: List[SearchFilter]
    results: List[CompanyResult]
    total: int


class FeedbackRequest(BaseModel):
    company_id: str
    search_id: str
    is_relevant: bool


class ExportRequest(BaseModel):
    filters: List[SearchFilter]
    format: Optional[str] = "csv"


class ReverseEngineerRequest(BaseModel):
    """Request to reverse engineer search filters from example companies"""
    companies: List[dict]  # List of company data dicts
    user_context: Optional[str] = None  # What user is looking for
    use_ai: Optional[bool] = True  # Whether to use AI for enhanced analysis


class ReverseEngineerResponse(BaseModel):
    """Response from reverse engineering analysis"""
    patterns: List[dict]
    suggested_filters: List[SearchFilter]
    analysis_summary: str
    example_companies_analyzed: int
    search_strategy: Optional[dict] = None


# Sample data for demo/testing
SAMPLE_COMPANIES = [
    CompanyResult(
        id="1",
        name="TechCorp GmbH",
        domain="techcorp.de",
        industry="SaaS",
        employee_count="50-200",
        location="Berlin, Germany",
        founded_year=2018,
        description="B2B software platform for enterprise workflow automation.",
        technologies=["Python", "React", "AWS", "PostgreSQL"],
        verified=True,
    ),
    CompanyResult(
        id="2",
        name="CloudSync Solutions",
        domain="cloudsync.io",
        industry="Cloud Infrastructure",
        employee_count="100-500",
        location="Munich, Germany",
        founded_year=2015,
        description="Multi-cloud management and optimization platform.",
        technologies=["Go", "Kubernetes", "Terraform"],
        verified=True,
    ),
    CompanyResult(
        id="3",
        name="DataFlow Analytics",
        domain="dataflow.de",
        industry="Data Analytics",
        employee_count="20-50",
        location="Hamburg, Germany",
        founded_year=2020,
        description="Real-time data analytics for retail businesses.",
        technologies=["Python", "Apache Kafka", "Snowflake"],
        verified=False,
    ),
    CompanyResult(
        id="4",
        name="FinanceAI",
        domain="financeai.co.uk",
        industry="FinTech",
        employee_count="50-200",
        location="London, UK",
        founded_year=2019,
        description="AI-powered financial planning and investment tools.",
        technologies=["Python", "TensorFlow", "React", "AWS"],
        verified=True,
    ),
    CompanyResult(
        id="5",
        name="ShopifyPlus Partner",
        domain="shopifypartner.com",
        industry="E-commerce",
        employee_count="10-50",
        location="New York, USA",
        founded_year=2017,
        description="E-commerce development and optimization services.",
        technologies=["Shopify", "React", "Node.js"],
        verified=True,
    ),
]


async def parse_query_with_ai(query: str) -> tuple[List[SearchFilter], str]:
    """
    Parse natural language query using OpenAI for intelligent extraction.
    
    Returns tuple of (filters, intent_description)
    """
    if not openai_service.is_connected():
        # Fall back to rule-based parsing
        return parse_query_to_filters_rules(query)
    
    try:
        prompt = f"""Parse this company search query into structured filters.

Query: "{query}"

Extract the following fields if mentioned (return empty array if not found):
- industry: Company industry/vertical (e.g., "SaaS", "FinTech", "E-commerce", "Healthcare", "AI/ML")
- location: Country, region, or city (e.g., "Germany", "London, UK", "Nordics")
- employee_count: Size range (use standard ranges: "1-10", "10-50", "50-200", "200-500", "500-1000", "1000+")
- founded_year: If they mention startups, recent companies, or specific years
- technologies: Specific tech stack mentioned (e.g., "Python", "Shopify", "AWS")
- keywords: Industry-specific keywords mentioned (e.g., "B2B", "enterprise", "marketplace")

Return ONLY a valid JSON object in this exact format:
{{
  "filters": [
    {{"field": "industry", "value": "SaaS", "operator": "equals"}},
    {{"field": "location", "value": "Germany", "operator": "contains"}}
  ],
  "intent": "Brief description of what user is looking for"
}}"""

        response = await openai_service.complete(
            prompt=prompt,
            model="gpt-4o-mini",
            temperature=0.1,
            max_tokens=500,
            system_prompt="You are a search query parser. Return ONLY valid JSON, no explanation."
        )
        
        # Parse JSON response
        # Clean up response (remove markdown code blocks if present)
        response = response.strip()
        if response.startswith("```"):
            response = re.sub(r'^```json?\n?', '', response)
            response = re.sub(r'\n?```$', '', response)
        
        data = json.loads(response)
        filters = [
            SearchFilter(
                field=f["field"],
                value=f["value"],
                operator=f.get("operator", "equals")
            )
            for f in data.get("filters", [])
        ]
        intent = data.get("intent", "Find matching companies")
        
        logger.info(f"AI parsed query into {len(filters)} filters: {filters}")
        return filters, intent
        
    except Exception as e:
        logger.warning(f"AI parsing failed, falling back to rules: {e}")
        return parse_query_to_filters_rules(query)


def parse_query_to_filters_rules(query: str) -> tuple[List[SearchFilter], str]:
    """
    Rule-based fallback for parsing queries.
    Used when OpenAI is not available or fails.
    """
    query_lower = query.lower()
    filters = []
    intent = "Find companies matching criteria"
    
    # Industry detection (expanded list)
    industries = {
        "saas": "SaaS",
        "software as a service": "SaaS",
        "fintech": "FinTech",
        "financial technology": "FinTech",
        "e-commerce": "E-commerce",
        "ecommerce": "E-commerce",
        "online retail": "E-commerce",
        "healthcare": "Healthcare",
        "healthtech": "Healthcare Tech",
        "medtech": "Healthcare Tech",
        "cloud": "Cloud Infrastructure",
        "data": "Data Analytics",
        "analytics": "Data Analytics",
        "ai": "AI/ML",
        "artificial intelligence": "AI/ML",
        "machine learning": "AI/ML",
        "cybersecurity": "Cybersecurity",
        "security": "Cybersecurity",
        "martech": "MarTech",
        "marketing tech": "MarTech",
        "edtech": "EdTech",
        "education": "EdTech",
        "devtools": "Developer Tools",
        "developer tools": "Developer Tools",
    }
    for keyword, industry in industries.items():
        if keyword in query_lower:
            filters.append(SearchFilter(field="industry", value=industry))
            break
    
    # Location detection (expanded)
    locations = {
        "germany": "Germany",
        "german": "Germany",
        "berlin": "Berlin, Germany",
        "munich": "Munich, Germany",
        "hamburg": "Hamburg, Germany",
        "frankfurt": "Frankfurt, Germany",
        "dach": "DACH",
        "uk": "UK",
        "united kingdom": "UK",
        "london": "London, UK",
        "us": "USA",
        "usa": "USA",
        "united states": "USA",
        "new york": "New York, USA",
        "san francisco": "San Francisco, USA",
        "silicon valley": "San Francisco, USA",
        "nordics": "Nordics",
        "nordic": "Nordics",
        "scandinavia": "Nordics",
        "sweden": "Sweden",
        "norway": "Norway",
        "denmark": "Denmark",
        "finland": "Finland",
        "france": "France",
        "paris": "Paris, France",
        "netherlands": "Netherlands",
        "amsterdam": "Amsterdam, Netherlands",
    }
    for keyword, location in locations.items():
        if keyword in query_lower:
            filters.append(SearchFilter(field="location", value=location))
            break
    
    # Employee count detection (improved patterns)
    employee_patterns = [
        (r'\b50[\s-]*200\b', "50-200"),
        (r'\b100[\s-]*500\b', "100-500"),
        (r'\b200[\s-]*500\b', "200-500"),
        (r'\b10[\s-]*50\b', "10-50"),
        (r'\b1[\s-]*10\b', "1-10"),
        (r'\bstartup\b', "10-50"),
        (r'\bsmall\b', "10-50"),
        (r'\bmedium\b', "50-200"),
        (r'\bmid[\s-]*size\b', "50-200"),
        (r'\blarge\b', "500-1000"),
        (r'\benterprise\b', "1000+"),
    ]
    for pattern, size in employee_patterns:
        if re.search(pattern, query_lower):
            filters.append(SearchFilter(field="employee_count", value=size))
            break
    
    # Year founded detection
    year_match = re.search(r'\b(20[12]\d)\b', query)
    if year_match:
        filters.append(SearchFilter(field="founded_year", value=year_match.group(1), operator="gte"))
    elif "recent" in query_lower or "new" in query_lower:
        filters.append(SearchFilter(field="founded_year", value="2020", operator="gte"))
    
    # Technology detection
    technologies = {
        "shopify": "Shopify",
        "python": "Python",
        "react": "React",
        "aws": "AWS",
        "azure": "Azure",
        "gcp": "Google Cloud",
        "kubernetes": "Kubernetes",
        "docker": "Docker",
        "nodejs": "Node.js",
        "node.js": "Node.js",
        "typescript": "TypeScript",
        "java": "Java",
        "golang": "Go",
        "rust": "Rust",
        "postgresql": "PostgreSQL",
        "mongodb": "MongoDB",
        "salesforce": "Salesforce",
        "hubspot": "HubSpot",
    }
    for keyword, tech in technologies.items():
        if keyword in query_lower:
            filters.append(SearchFilter(field="technologies", value=tech, operator="contains"))
    
    return filters, intent


def parse_query_to_filters(query: str) -> tuple[List[SearchFilter], str]:
    """
    Synchronous wrapper for backward compatibility.
    Uses rule-based parsing. For AI parsing, use parse_query_with_ai.
    """
    return parse_query_to_filters_rules(query)


def filter_companies(companies: List[CompanyResult], filters: List[SearchFilter]) -> List[CompanyResult]:
    """Filter companies based on applied filters."""
    if not filters:
        return companies
    
    results = []
    for company in companies:
        matches = True
        for f in filters:
            company_value = getattr(company, f.field, None)
            if company_value is None:
                matches = False
                break
            
            if f.operator == "equals":
                if isinstance(company_value, str):
                    if f.value.lower() not in company_value.lower():
                        matches = False
                        break
                elif company_value != f.value:
                    matches = False
                    break
            elif f.operator == "gte":
                try:
                    if int(company_value) < int(f.value):
                        matches = False
                        break
                except (ValueError, TypeError):
                    matches = False
                    break
        
        if matches:
            results.append(company)
    
    return results


@router.post("/parse", response_model=ParseQueryResponse)
async def parse_query(request: ParseQueryRequest):
    """Parse a natural language query into structured filters."""
    filters, intent = parse_query_to_filters(request.query)
    
    return ParseQueryResponse(
        filters=filters,
        intent=intent,
        clarifications=None if filters else ["Could you be more specific about the companies you're looking for?"]
    )


@router.post("/search", response_model=SearchResponse)
async def search_companies(request: SearchRequest):
    """Search companies with structured filters."""
    results = filter_companies(SAMPLE_COMPANIES, request.filters)
    
    # Pagination
    start = (request.page - 1) * request.limit
    end = start + request.limit
    paginated = results[start:end]
    
    return SearchResponse(
        companies=paginated,
        total=len(results),
        filters_applied=request.filters,
        suggestions=["Try adding more filters to narrow results"] if len(results) > 10 else None
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_search(request: ChatRequest):
    """
    Chat-based search - combines parsing and searching.
    Takes natural language input and returns results with AI response.
    
    Uses AI to:
    1. Parse natural language into structured filters
    2. Generate conversational response
    """
    # Try AI parsing first, fall back to rules
    filters, intent = await parse_query_with_ai(request.message)
    
    # Search with filters
    results = filter_companies(SAMPLE_COMPANIES, filters)
    
    # Generate response (AI-enhanced if available)
    response = await generate_search_response(
        query=request.message,
        filters=filters,
        results=results,
        conversation_history=request.conversation_history
    )
    
    return ChatResponse(
        response=response,
        filters=filters,
        results=results[:25],  # Limit to 25 results
        total=len(results)
    )


async def generate_search_response(
    query: str,
    filters: List[SearchFilter],
    results: List[CompanyResult],
    conversation_history: Optional[List[dict]] = None
) -> str:
    """Generate a conversational response for search results."""
    
    # Try AI-generated response
    if openai_service.is_connected() and filters:
        try:
            filter_desc = ", ".join([f"{f.field}: {f.value}" for f in filters])
            
            prompt = f"""You are a helpful sales intelligence assistant. The user searched for:
"{query}"

I extracted these filters: {filter_desc}
Found {len(results)} matching companies.

Generate a brief, helpful response (2-3 sentences max) that:
1. Confirms what you understood from their query
2. Summarizes the results
3. Suggests how they could refine if needed

Be conversational but concise. Don't list the filters again."""

            response = await openai_service.complete(
                prompt=prompt,
                model="gpt-4o-mini",
                temperature=0.7,
                max_tokens=150,
                system_prompt="You are a helpful B2B sales assistant. Be concise and friendly."
            )
            return response
            
        except Exception as e:
            logger.warning(f"AI response generation failed: {e}")
    
    # Fallback to template response
    if not filters:
        return (
            "I'd be happy to help you find companies! Could you tell me more about what you're looking for? "
            "For example, you could specify:\n"
            "- Industry (SaaS, FinTech, E-commerce, etc.)\n"
            "- Location (Germany, UK, USA, etc.)\n"
            "- Company size (10-50, 50-200, 100-500 employees)\n"
            "- Technologies they use"
        )
    elif not results:
        filter_desc = ", ".join([f"{f.field}: {f.value}" for f in filters])
        return (
            f"I searched for companies matching: {filter_desc}\n\n"
            "Unfortunately, I didn't find any matches in my current dataset. Try:\n"
            "- Broadening the location (e.g., 'Europe' instead of specific city)\n"
            "- Adjusting the company size range\n"
            "- Trying a different industry"
        )
    else:
        filter_desc = ", ".join([f"{f.field}: {f.value}" for f in filters])
        return (
            f"Found {len(results)} companies matching: {filter_desc}\n\n"
            "You can refine by asking things like:\n"
            "- 'Only show companies using Python'\n"
            "- 'Filter to verified matches only'\n"
            "- 'Companies founded after 2019'"
        )


@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """Record feedback on a search result."""
    logger.info(
        f"Feedback received: company={request.company_id}, "
        f"search={request.search_id}, relevant={request.is_relevant}"
    )
    # In production, save to database for improving search relevance
    return {"status": "ok"}


@router.get("/suggestions")
async def get_suggestions(q: str = ""):
    """Get search suggestions based on partial input."""
    suggestions = [
        "SaaS companies in Germany",
        "FinTech startups in London",
        "E-commerce companies using Shopify",
        "Companies with 50-200 employees",
        "B2B software in the Nordics",
    ]
    
    if q:
        q_lower = q.lower()
        suggestions = [s for s in suggestions if q_lower in s.lower()]
    
    return {"suggestions": suggestions[:5]}


@router.post("/export")
async def export_results(request: ExportRequest):
    """Export search results to CSV or XLSX."""
    results = filter_companies(SAMPLE_COMPANIES, request.filters)
    
    if request.format == "csv":
        # Generate CSV
        import csv
        import io
        from fastapi.responses import StreamingResponse
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Name", "Domain", "Industry", "Employees", "Location", "Founded", "Description"])
        
        for company in results:
            writer.writerow([
                company.name,
                company.domain,
                company.industry,
                company.employee_count,
                company.location,
                company.founded_year,
                company.description,
            ])
        
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=search-results.csv"}
        )
    
    raise HTTPException(status_code=400, detail=f"Unsupported format: {request.format}")


@router.post("/reverse-engineer", response_model=ReverseEngineerResponse)
async def reverse_engineer_search(request: ReverseEngineerRequest):
    """
    Reverse engineering approach: Extract search filters from example companies.
    
    Instead of parsing a natural language query, analyze companies the user
    already knows and likes to find patterns and generate filters.
    
    Example use case:
    - User has 5 companies they've sold to successfully
    - This endpoint extracts what they have in common
    - Returns filters to find more similar companies
    """
    if not request.companies:
        raise HTTPException(status_code=400, detail="At least one example company required")
    
    # Convert dicts to CompanyProfile objects
    try:
        companies = [
            CompanyProfile(
                name=c.get("name", "Unknown"),
                domain=c.get("domain"),
                industry=c.get("industry"),
                employee_count=c.get("employee_count"),
                location=c.get("location"),
                founded_year=c.get("founded_year"),
                technologies=c.get("technologies", []),
                revenue_range=c.get("revenue_range"),
                description=c.get("description"),
            )
            for c in request.companies
        ]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid company data: {e}")
    
    # Get service with or without AI
    if request.use_ai and openai_service.is_connected():
        service = get_reverse_engineering_service(openai_service)
        result = await service.analyze_with_ai(companies, request.user_context)
    else:
        service = get_reverse_engineering_service()
        result = service.analyze_companies(companies)
    
    # Generate search strategy
    strategy = service.suggest_search_strategy(result)
    
    return ReverseEngineerResponse(
        patterns=[p.model_dump() for p in result.patterns],
        suggested_filters=result.suggested_filters,
        analysis_summary=result.analysis_summary,
        example_companies_analyzed=result.example_companies_analyzed,
        search_strategy=strategy
    )


@router.post("/search-like")
async def search_like_companies(request: ReverseEngineerRequest):
    """
    Convenience endpoint: Reverse engineer + search in one call.
    
    Takes example companies, extracts patterns, and immediately
    searches for similar companies.
    """
    if not request.companies:
        raise HTTPException(status_code=400, detail="At least one example company required")
    
    # Convert and analyze
    companies = [
        CompanyProfile(
            name=c.get("name", "Unknown"),
            domain=c.get("domain"),
            industry=c.get("industry"),
            employee_count=c.get("employee_count"),
            location=c.get("location"),
            founded_year=c.get("founded_year"),
            technologies=c.get("technologies", []),
            revenue_range=c.get("revenue_range"),
            description=c.get("description"),
        )
        for c in request.companies
    ]
    
    # Get patterns
    if request.use_ai and openai_service.is_connected():
        service = get_reverse_engineering_service(openai_service)
        result = await service.analyze_with_ai(companies, request.user_context)
    else:
        service = get_reverse_engineering_service()
        result = service.analyze_companies(companies)
    
    # Search with suggested filters
    search_results = filter_companies(SAMPLE_COMPANIES, result.suggested_filters)
    
    return {
        "analysis": {
            "patterns": [p.model_dump() for p in result.patterns],
            "analysis_summary": result.analysis_summary,
            "example_companies_analyzed": result.example_companies_analyzed,
        },
        "filters_applied": result.suggested_filters,
        "results": search_results[:25],
        "total": len(search_results),
        "search_strategy": service.suggest_search_strategy(result)
    }


# ============================================================================
# VERIFICATION ENDPOINTS - Crona scrape + OpenAI verify pipeline
# ============================================================================

class VerifyCompanyRequest(BaseModel):
    """Request to verify a single company"""
    company: dict  # Company data with id, name, domain, etc.
    criteria: dict  # Verification criteria (industry, location, keywords, etc.)
    use_ai: Optional[bool] = True


class VerifyBatchRequest(BaseModel):
    """Request to verify multiple companies"""
    companies: List[dict]
    criteria: dict
    use_ai: Optional[bool] = True
    max_concurrent: Optional[int] = 5
    verify_limit: Optional[int] = 10  # Max companies to verify for cost control


class VerifySearchResultsRequest(BaseModel):
    """Request to verify search results"""
    results: List[dict]  # Search results to verify
    criteria: dict  # Criteria to verify against
    use_ai: Optional[bool] = True
    verify_limit: Optional[int] = 10


@router.post("/verify")
async def verify_company(request: VerifyCompanyRequest):
    """
    Verify a single company matches search criteria.
    
    1. Scrapes the company's website
    2. Uses OpenAI to analyze if content matches criteria
    3. Returns verification result with confidence score
    
    Example:
    ```json
    {
        "company": {"id": "1", "name": "Acme Corp", "domain": "acme.com"},
        "criteria": {"industry": "SaaS", "location": "Germany"}
    }
    ```
    """
    try:
        # Convert company dict to CompanyToVerify
        company = CompanyToVerify(
            id=request.company.get("id", "unknown"),
            name=request.company.get("name", "Unknown"),
            domain=request.company.get("domain"),
            claimed_industry=request.company.get("industry"),
            claimed_employee_count=request.company.get("employee_count"),
            claimed_location=request.company.get("location"),
            claimed_technologies=request.company.get("technologies"),
        )
        
        # Convert criteria dict to VerificationCriteria
        criteria = VerificationCriteria(
            industry=request.criteria.get("industry"),
            employee_count=request.criteria.get("employee_count"),
            location=request.criteria.get("location"),
            technologies=request.criteria.get("technologies"),
            keywords=request.criteria.get("keywords"),
            description=request.criteria.get("description"),
        )
        
        result = await verification_service.verify_company(
            company=company,
            criteria=criteria,
            use_ai=request.use_ai
        )
        
        return result.model_dump()
        
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@router.post("/verify/batch")
async def verify_batch(request: VerifyBatchRequest):
    """
    Verify multiple companies against search criteria.
    
    Scrapes websites concurrently with rate limiting.
    Returns verification results for all companies.
    
    Example:
    ```json
    {
        "companies": [
            {"id": "1", "name": "Acme Corp", "domain": "acme.com"},
            {"id": "2", "name": "Beta Inc", "domain": "beta.io"}
        ],
        "criteria": {"industry": "SaaS", "keywords": ["automation", "workflow"]}
    }
    ```
    """
    if not request.companies:
        raise HTTPException(status_code=400, detail="At least one company required")
    
    try:
        # Convert companies
        companies = [
            CompanyToVerify(
                id=c.get("id", str(i)),
                name=c.get("name", "Unknown"),
                domain=c.get("domain"),
                claimed_industry=c.get("industry"),
                claimed_employee_count=c.get("employee_count"),
                claimed_location=c.get("location"),
                claimed_technologies=c.get("technologies"),
            )
            for i, c in enumerate(request.companies[:request.verify_limit])
        ]
        
        # Convert criteria
        criteria = VerificationCriteria(
            industry=request.criteria.get("industry"),
            employee_count=request.criteria.get("employee_count"),
            location=request.criteria.get("location"),
            technologies=request.criteria.get("technologies"),
            keywords=request.criteria.get("keywords"),
            description=request.criteria.get("description"),
        )
        
        result = await verification_service.verify_batch(
            companies=companies,
            criteria=criteria,
            use_ai=request.use_ai,
            max_concurrent=request.max_concurrent
        )
        
        return result.model_dump()
        
    except Exception as e:
        logger.error(f"Batch verification failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch verification failed: {str(e)}")


@router.post("/verify/search-results")
async def verify_search_results(request: VerifySearchResultsRequest):
    """
    Verify search results and return enriched results with verification info.
    
    Takes search results from /search or /chat endpoints,
    verifies them against criteria, and returns results with
    verification status attached to each company.
    
    Example:
    ```json
    {
        "results": [
            {"id": "1", "name": "TechCorp", "domain": "techcorp.de", "industry": "SaaS"}
        ],
        "criteria": {"industry": "SaaS", "location": "Germany"}
    }
    ```
    """
    if not request.results:
        return {"results": [], "verified_count": 0, "total": 0}
    
    try:
        criteria = VerificationCriteria(
            industry=request.criteria.get("industry"),
            employee_count=request.criteria.get("employee_count"),
            location=request.criteria.get("location"),
            technologies=request.criteria.get("technologies"),
            keywords=request.criteria.get("keywords"),
            description=request.criteria.get("description"),
        )
        
        enriched = await verification_service.verify_search_results(
            search_results=request.results,
            criteria=criteria,
            use_ai=request.use_ai,
            verify_limit=request.verify_limit
        )
        
        # Count verified
        verified_count = sum(1 for r in enriched if r.get("verified") is True)
        
        return {
            "results": enriched,
            "verified_count": verified_count,
            "total": len(enriched),
            "verification_summary": f"{verified_count}/{min(len(enriched), request.verify_limit)} companies verified"
        }
        
    except Exception as e:
        logger.error(f"Search results verification failed: {e}")
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@router.post("/chat-verified")
async def chat_search_verified(request: ChatRequest):
    """
    Chat-based search WITH automatic verification.
    
    Like /chat but also verifies top results by scraping their
    websites and checking if they truly match the criteria.
    
    This is the premium search experience with verified results.
    """
    # First do regular chat search
    filters, intent = await parse_query_with_ai(request.message)
    results = filter_companies(SAMPLE_COMPANIES, filters)
    response = await generate_search_response(
        query=request.message,
        filters=filters,
        results=results,
        conversation_history=request.conversation_history
    )
    
    # Now verify top results
    if results:
        criteria = VerificationCriteria(
            industry=next((f.value for f in filters if f.field == "industry"), None),
            employee_count=next((f.value for f in filters if f.field == "employee_count"), None),
            location=next((f.value for f in filters if f.field == "location"), None),
            technologies=[f.value for f in filters if f.field == "technologies"],
            keywords=[f.value for f in filters if f.field == "keywords"],
            description=request.message,  # Use original query as context
        )
        
        # Convert results to dicts for verification
        results_dicts = [r.model_dump() for r in results[:10]]
        
        verified_results = await verification_service.verify_search_results(
            search_results=results_dicts,
            criteria=criteria,
            use_ai=True,
            verify_limit=10
        )
        
        # Convert back to CompanyResult objects
        verified_companies = []
        for r in verified_results:
            verified_companies.append(CompanyResult(
                id=r.get("id", ""),
                name=r.get("name", ""),
                domain=r.get("domain"),
                industry=r.get("industry"),
                employee_count=r.get("employee_count"),
                location=r.get("location"),
                founded_year=r.get("founded_year"),
                description=r.get("ai_description") or r.get("description"),
                technologies=r.get("technologies"),
                verified=r.get("verified"),
                relevance_score=r.get("verification_confidence"),
            ))
        
        verified_count = sum(1 for r in verified_companies if r.verified)
        
        return ChatResponse(
            response=f"{response}\n\n✓ Verified {verified_count} of {len(verified_companies)} companies against your criteria.",
            filters=filters,
            results=verified_companies,
            total=len(verified_companies)
        )
    
    return ChatResponse(
        response=response,
        filters=filters,
        results=[],
        total=0
    )
