"""
Reverse Engineering Search Service

This service extracts common patterns from known/example companies
and generates structured search filters to find similar companies.

Approach:
1. User provides example companies they like (domains/names)
2. Service fetches company data (or uses provided attributes)
3. Extracts common patterns (industry, size, location, tech stack, etc.)
4. Generates Apollo-compatible filters based on patterns
5. Returns filters for searching similar companies
"""

import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from collections import Counter
import re

logger = logging.getLogger(__name__)


class CompanyProfile(BaseModel):
    """Company profile for pattern extraction"""
    name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    employee_count: Optional[str] = None
    location: Optional[str] = None
    founded_year: Optional[int] = None
    technologies: Optional[List[str]] = None
    revenue_range: Optional[str] = None
    description: Optional[str] = None


class ExtractedPattern(BaseModel):
    """A pattern extracted from example companies"""
    field: str
    value: str
    confidence: float  # 0.0 to 1.0
    count: int  # How many example companies matched
    total: int  # Total example companies


class SearchFilter(BaseModel):
    """Filter for company search"""
    field: str
    value: str
    operator: Optional[str] = "equals"


class ReverseEngineeringResult(BaseModel):
    """Result of reverse engineering analysis"""
    patterns: List[ExtractedPattern]
    suggested_filters: List[SearchFilter]
    analysis_summary: str
    example_companies_analyzed: int


class ReverseEngineeringService:
    """
    Extracts search filters by analyzing example companies.
    
    This is the "reverse engineering" approach:
    Instead of parsing a natural language query,
    we look at companies the user likes and find what they have in common.
    """
    
    # Standard employee count ranges
    EMPLOYEE_RANGES = [
        ("1-10", (1, 10)),
        ("10-50", (10, 50)),
        ("50-200", (50, 200)),
        ("200-500", (200, 500)),
        ("500-1000", (500, 1000)),
        ("1000-5000", (1000, 5000)),
        ("5000+", (5000, 100000)),
    ]
    
    # Industry keywords for matching
    INDUSTRY_KEYWORDS = {
        "saas": ["saas", "software as a service", "cloud software"],
        "fintech": ["fintech", "financial technology", "payments", "banking tech"],
        "healthtech": ["healthtech", "health tech", "healthcare technology", "medtech"],
        "ecommerce": ["ecommerce", "e-commerce", "online retail", "marketplace"],
        "edtech": ["edtech", "education technology", "learning platform"],
        "martech": ["martech", "marketing technology", "adtech"],
        "cybersecurity": ["cybersecurity", "security", "infosec"],
        "ai_ml": ["artificial intelligence", "machine learning", "ai", "ml"],
        "devtools": ["developer tools", "devtools", "developer platform"],
        "data_analytics": ["data analytics", "business intelligence", "bi", "analytics"],
    }
    
    # Region groupings
    REGIONS = {
        "DACH": ["Germany", "Austria", "Switzerland"],
        "Nordics": ["Sweden", "Norway", "Denmark", "Finland", "Iceland"],
        "UK": ["UK", "United Kingdom", "England", "Scotland", "Wales"],
        "USA": ["USA", "United States", "US"],
        "Western Europe": ["France", "Belgium", "Netherlands", "Luxembourg"],
    }
    
    def __init__(self, openai_service=None):
        """
        Initialize with optional OpenAI service for enhanced analysis.
        """
        self.openai = openai_service
    
    def _normalize_employee_count(self, count: str) -> Optional[str]:
        """Normalize employee count to standard ranges."""
        if not count:
            return None
        
        # Try to extract numbers
        numbers = re.findall(r'\d+', count.replace(',', ''))
        if not numbers:
            return count
        
        # Get the primary number
        num = int(numbers[0])
        
        for range_name, (low, high) in self.EMPLOYEE_RANGES:
            if low <= num <= high:
                return range_name
        
        return count
    
    def _normalize_location(self, location: str) -> Dict[str, str]:
        """Extract country and region from location string."""
        if not location:
            return {}
        
        location_lower = location.lower()
        result = {"original": location}
        
        # Check for country matches
        for region, countries in self.REGIONS.items():
            for country in countries:
                if country.lower() in location_lower:
                    result["country"] = country
                    result["region"] = region
                    break
        
        # Extract city if comma-separated
        if "," in location:
            parts = location.split(",")
            result["city"] = parts[0].strip()
        
        return result
    
    def _extract_industry_category(self, company: CompanyProfile) -> Optional[str]:
        """Extract standardized industry category."""
        # Check explicit industry field
        if company.industry:
            industry_lower = company.industry.lower()
            for category, keywords in self.INDUSTRY_KEYWORDS.items():
                if any(kw in industry_lower for kw in keywords):
                    return category
        
        # Check description for industry keywords
        if company.description:
            desc_lower = company.description.lower()
            for category, keywords in self.INDUSTRY_KEYWORDS.items():
                if any(kw in desc_lower for kw in keywords):
                    return category
        
        return company.industry
    
    def analyze_companies(
        self,
        companies: List[CompanyProfile],
        min_confidence: float = 0.5
    ) -> ReverseEngineeringResult:
        """
        Analyze a list of example companies and extract common patterns.
        
        Args:
            companies: List of company profiles to analyze
            min_confidence: Minimum confidence threshold for including patterns
            
        Returns:
            ReverseEngineeringResult with patterns and suggested filters
        """
        if not companies:
            return ReverseEngineeringResult(
                patterns=[],
                suggested_filters=[],
                analysis_summary="No companies provided for analysis",
                example_companies_analyzed=0
            )
        
        total = len(companies)
        patterns = []
        
        # === Industry Analysis ===
        industries = []
        for c in companies:
            category = self._extract_industry_category(c)
            if category:
                industries.append(category)
        
        if industries:
            industry_counts = Counter(industries)
            for industry, count in industry_counts.most_common(3):
                confidence = count / total
                if confidence >= min_confidence:
                    patterns.append(ExtractedPattern(
                        field="industry",
                        value=industry,
                        confidence=confidence,
                        count=count,
                        total=total
                    ))
        
        # === Employee Count Analysis ===
        sizes = []
        for c in companies:
            if c.employee_count:
                normalized = self._normalize_employee_count(c.employee_count)
                if normalized:
                    sizes.append(normalized)
        
        if sizes:
            size_counts = Counter(sizes)
            for size, count in size_counts.most_common(2):
                confidence = count / total
                if confidence >= min_confidence:
                    patterns.append(ExtractedPattern(
                        field="employee_count",
                        value=size,
                        confidence=confidence,
                        count=count,
                        total=total
                    ))
        
        # === Location Analysis ===
        countries = []
        regions = []
        for c in companies:
            if c.location:
                loc_info = self._normalize_location(c.location)
                if "country" in loc_info:
                    countries.append(loc_info["country"])
                if "region" in loc_info:
                    regions.append(loc_info["region"])
        
        # Prefer region over individual country if multiple countries in same region
        if regions:
            region_counts = Counter(regions)
            for region, count in region_counts.most_common(2):
                confidence = count / total
                if confidence >= min_confidence:
                    patterns.append(ExtractedPattern(
                        field="region",
                        value=region,
                        confidence=confidence,
                        count=count,
                        total=total
                    ))
        elif countries:
            country_counts = Counter(countries)
            for country, count in country_counts.most_common(2):
                confidence = count / total
                if confidence >= min_confidence:
                    patterns.append(ExtractedPattern(
                        field="location",
                        value=country,
                        confidence=confidence,
                        count=count,
                        total=total
                    ))
        
        # === Technology Analysis ===
        all_techs = []
        for c in companies:
            if c.technologies:
                all_techs.extend(c.technologies)
        
        if all_techs:
            tech_counts = Counter(all_techs)
            for tech, count in tech_counts.most_common(5):
                confidence = count / total
                if confidence >= min_confidence * 0.7:  # Lower threshold for tech
                    patterns.append(ExtractedPattern(
                        field="technology",
                        value=tech,
                        confidence=confidence,
                        count=count,
                        total=total
                    ))
        
        # === Founded Year Analysis ===
        years = [c.founded_year for c in companies if c.founded_year]
        if years:
            avg_year = sum(years) / len(years)
            min_year = min(years)
            max_year = max(years)
            
            # If most companies are recent startups
            recent_count = sum(1 for y in years if y >= 2018)
            if recent_count / total >= min_confidence:
                patterns.append(ExtractedPattern(
                    field="founded_year",
                    value="2018+",
                    confidence=recent_count / total,
                    count=recent_count,
                    total=total
                ))
        
        # === Generate Suggested Filters ===
        suggested_filters = []
        for pattern in sorted(patterns, key=lambda p: p.confidence, reverse=True):
            # Convert patterns to search filters
            if pattern.field == "industry":
                suggested_filters.append(SearchFilter(
                    field="industry",
                    value=pattern.value,
                    operator="equals"
                ))
            elif pattern.field == "employee_count":
                suggested_filters.append(SearchFilter(
                    field="employee_count",
                    value=pattern.value,
                    operator="equals"
                ))
            elif pattern.field in ["location", "region"]:
                suggested_filters.append(SearchFilter(
                    field="location",
                    value=pattern.value,
                    operator="contains"
                ))
            elif pattern.field == "technology":
                suggested_filters.append(SearchFilter(
                    field="technologies",
                    value=pattern.value,
                    operator="contains"
                ))
            elif pattern.field == "founded_year":
                suggested_filters.append(SearchFilter(
                    field="founded_year",
                    value=pattern.value.replace("+", ""),
                    operator="gte"
                ))
        
        # === Generate Summary ===
        summary_parts = []
        if patterns:
            top_patterns = sorted(patterns, key=lambda p: p.confidence, reverse=True)[:3]
            for p in top_patterns:
                pct = int(p.confidence * 100)
                summary_parts.append(f"{p.field}: {p.value} ({pct}% match)")
        
        summary = f"Analyzed {total} companies. " + (
            "Key patterns: " + ", ".join(summary_parts) if summary_parts
            else "No strong patterns found."
        )
        
        return ReverseEngineeringResult(
            patterns=patterns,
            suggested_filters=suggested_filters[:5],  # Limit to top 5 filters
            analysis_summary=summary,
            example_companies_analyzed=total
        )
    
    async def analyze_with_ai(
        self,
        companies: List[CompanyProfile],
        user_context: Optional[str] = None
    ) -> ReverseEngineeringResult:
        """
        Use AI to analyze companies and extract patterns.
        Falls back to rule-based analysis if OpenAI is not available.
        
        Args:
            companies: List of company profiles
            user_context: Optional context about what user is looking for
            
        Returns:
            ReverseEngineeringResult with AI-enhanced analysis
        """
        # First do rule-based analysis
        result = self.analyze_companies(companies)
        
        if not self.openai or not self.openai.is_connected():
            return result
        
        # Enhance with AI
        try:
            company_data = "\n".join([
                f"- {c.name}: {c.industry or 'Unknown industry'}, "
                f"{c.employee_count or 'Unknown size'}, "
                f"{c.location or 'Unknown location'}, "
                f"Tech: {', '.join(c.technologies or []) or 'Unknown'}"
                for c in companies[:10]  # Limit to 10 for token efficiency
            ])
            
            prompt = f"""Analyze these example companies and identify what they have in common.
            
Companies:
{company_data}

{f'User is looking for: {user_context}' if user_context else ''}

Identify:
1. Common industry/vertical
2. Company size pattern
3. Geographic pattern
4. Technology stack commonalities
5. Business model similarities (B2B, B2C, SaaS, etc.)

Return a concise analysis (max 3 sentences) of what makes these companies similar 
and what filters would find more like them."""

            ai_analysis = await self.openai.complete(
                prompt=prompt,
                model="gpt-4o-mini",
                temperature=0.3,
                max_tokens=300,
                system_prompt="You are a B2B sales intelligence analyst. Be concise and specific."
            )
            
            # Append AI analysis to summary
            result.analysis_summary = f"{result.analysis_summary}\n\nAI Analysis: {ai_analysis}"
            
        except Exception as e:
            logger.warning(f"AI analysis failed, using rule-based only: {e}")
        
        return result
    
    def suggest_search_strategy(
        self,
        result: ReverseEngineeringResult
    ) -> Dict[str, Any]:
        """
        Generate a search strategy based on extracted patterns.
        
        Returns dict with:
        - primary_filters: Most important filters to apply
        - secondary_filters: Nice-to-have filters
        - search_tips: Suggestions for refining search
        """
        if not result.patterns:
            return {
                "primary_filters": [],
                "secondary_filters": [],
                "search_tips": [
                    "Add more example companies for better pattern detection",
                    "Include companies from your target industry",
                    "Make sure example companies have complete profiles"
                ]
            }
        
        # Sort by confidence
        sorted_patterns = sorted(result.patterns, key=lambda p: p.confidence, reverse=True)
        
        # Primary: high confidence patterns
        primary = [p for p in sorted_patterns if p.confidence >= 0.7]
        # Secondary: medium confidence
        secondary = [p for p in sorted_patterns if 0.4 <= p.confidence < 0.7]
        
        tips = []
        if not primary:
            tips.append("Consider adding more similar companies to strengthen patterns")
        if len(result.suggested_filters) < 2:
            tips.append("Results may be broad - add more specific criteria")
        
        # Suggest refinements based on what's missing
        fields_covered = {p.field for p in result.patterns}
        if "industry" not in fields_covered:
            tips.append("Try adding industry filter manually for more relevant results")
        if "employee_count" not in fields_covered:
            tips.append("Consider filtering by company size")
        
        return {
            "primary_filters": [
                SearchFilter(field=p.field, value=p.value)
                for p in primary[:3]
            ],
            "secondary_filters": [
                SearchFilter(field=p.field, value=p.value)
                for p in secondary[:3]
            ],
            "search_tips": tips[:3]
        }


# Singleton instance
reverse_engineering_service = ReverseEngineeringService()


def get_reverse_engineering_service(openai_service=None) -> ReverseEngineeringService:
    """Get the reverse engineering service, optionally with OpenAI support."""
    if openai_service:
        return ReverseEngineeringService(openai_service)
    return reverse_engineering_service
