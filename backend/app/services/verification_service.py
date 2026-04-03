"""
Verification Service - Crona Scrape + OpenAI Verify Pipeline

This service verifies if companies match search criteria by:
1. Scraping their websites using the existing scraper service
2. Using OpenAI to analyze scraped content against search criteria
3. Returning verification scores and confidence levels

Used to improve search quality by filtering out false positives.
"""

import asyncio
import logging
import json
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from app.services.scraper_service import scraper_service
from app.services.openai_service import openai_service

logger = logging.getLogger(__name__)


class VerificationCriteria(BaseModel):
    """Criteria to verify against"""
    industry: Optional[str] = None
    employee_count: Optional[str] = None
    location: Optional[str] = None
    technologies: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    description: Optional[str] = None  # Free-text description of what we're looking for


class CompanyToVerify(BaseModel):
    """Company data to verify"""
    id: str
    name: str
    domain: Optional[str] = None
    claimed_industry: Optional[str] = None
    claimed_employee_count: Optional[str] = None
    claimed_location: Optional[str] = None
    claimed_technologies: Optional[List[str]] = None


class VerificationResult(BaseModel):
    """Result of verifying a single company"""
    company_id: str
    company_name: str
    domain: Optional[str] = None
    verified: bool
    confidence: float = Field(ge=0.0, le=1.0)
    match_reasons: List[str] = []
    mismatch_reasons: List[str] = []
    scraped_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    # Extracted info from website
    detected_industry: Optional[str] = None
    detected_employee_count: Optional[str] = None
    detected_location: Optional[str] = None
    detected_technologies: Optional[List[str]] = None
    company_description: Optional[str] = None


class BatchVerificationResult(BaseModel):
    """Result of verifying multiple companies"""
    total: int
    verified_count: int
    failed_count: int
    results: List[VerificationResult]
    summary: str


class VerificationService:
    """
    Verifies companies match search criteria by scraping websites
    and using OpenAI for intelligent content analysis.
    """
    
    # Keywords for industry detection
    INDUSTRY_PATTERNS = {
        "saas": ["saas", "software as a service", "cloud software", "subscription", "platform"],
        "fintech": ["fintech", "financial technology", "payments", "banking", "lending", "insurance tech"],
        "ecommerce": ["e-commerce", "ecommerce", "online store", "marketplace", "retail", "shopping"],
        "healthtech": ["health tech", "healthtech", "healthcare", "medical", "clinical", "patient"],
        "edtech": ["education", "edtech", "learning", "training", "courses", "lms"],
        "martech": ["marketing", "martech", "advertising", "analytics", "seo", "crm"],
        "cybersecurity": ["security", "cybersecurity", "protection", "threat", "encryption"],
        "ai_ml": ["artificial intelligence", "machine learning", "ai", "ml", "deep learning", "neural"],
        "devtools": ["developer", "devops", "ci/cd", "github", "api", "sdk", "infrastructure"],
        "hrtech": ["hr tech", "human resources", "recruiting", "hiring", "talent", "payroll"],
        "logistics": ["logistics", "shipping", "supply chain", "warehouse", "delivery", "freight"],
        "real_estate": ["real estate", "property", "housing", "rental", "mortgage", "proptech"],
    }
    
    # Keywords for company size detection
    SIZE_PATTERNS = {
        "1-10": ["startup", "small team", "founding team", "early stage"],
        "10-50": ["growing team", "small company", "seed", "series a"],
        "50-200": ["mid-size", "scaling", "series b", "expanding team"],
        "200-500": ["large team", "series c", "established"],
        "500-1000": ["enterprise", "global team", "multinational"],
        "1000+": ["global company", "thousands of employees", "worldwide offices"],
    }
    
    # Technology keywords
    TECH_PATTERNS = {
        "react": ["react", "reactjs", "react.js"],
        "python": ["python", "django", "flask", "fastapi"],
        "node": ["node", "nodejs", "node.js", "express"],
        "aws": ["aws", "amazon web services", "ec2", "s3", "lambda"],
        "gcp": ["google cloud", "gcp", "bigquery", "cloud run"],
        "azure": ["azure", "microsoft cloud"],
        "kubernetes": ["kubernetes", "k8s", "docker", "containers"],
        "salesforce": ["salesforce", "sfdc", "crm"],
        "shopify": ["shopify", "shopify plus"],
    }
    
    def __init__(self):
        self.scraper = scraper_service
        self.openai = openai_service
    
    def _extract_patterns_from_text(
        self,
        text: str,
        patterns: Dict[str, List[str]]
    ) -> List[str]:
        """Extract matching patterns from text."""
        text_lower = text.lower()
        matches = []
        
        for category, keywords in patterns.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    if category not in matches:
                        matches.append(category)
                    break
        
        return matches
    
    def _rule_based_verification(
        self,
        scraped_text: str,
        criteria: VerificationCriteria,
        company: CompanyToVerify
    ) -> Dict[str, Any]:
        """
        Rule-based verification using keyword matching.
        Used as fallback when OpenAI is not available.
        """
        text_lower = scraped_text.lower()
        match_reasons = []
        mismatch_reasons = []
        score = 0.0
        checks = 0
        
        # Industry check
        if criteria.industry:
            detected_industries = self._extract_patterns_from_text(
                scraped_text, self.INDUSTRY_PATTERNS
            )
            criteria_industry = criteria.industry.lower().replace(" ", "_")
            
            # Check if claimed industry matches criteria
            if criteria_industry in detected_industries:
                match_reasons.append(f"Industry '{criteria.industry}' confirmed from website content")
                score += 1.0
            elif detected_industries:
                mismatch_reasons.append(
                    f"Expected industry '{criteria.industry}', detected: {', '.join(detected_industries)}"
                )
            else:
                mismatch_reasons.append(f"Could not verify industry '{criteria.industry}' from website")
            checks += 1
        
        # Employee count check (harder to verify from website)
        if criteria.employee_count:
            detected_sizes = self._extract_patterns_from_text(
                scraped_text, self.SIZE_PATTERNS
            )
            if detected_sizes:
                match_reasons.append(f"Company size indicators found: {', '.join(detected_sizes)}")
                score += 0.5  # Lower confidence for size detection
            checks += 0.5
        
        # Location check
        if criteria.location:
            location_lower = criteria.location.lower()
            if location_lower in text_lower:
                match_reasons.append(f"Location '{criteria.location}' mentioned on website")
                score += 1.0
            else:
                mismatch_reasons.append(f"Could not verify location '{criteria.location}'")
            checks += 1
        
        # Technology check
        if criteria.technologies:
            detected_techs = self._extract_patterns_from_text(
                scraped_text, self.TECH_PATTERNS
            )
            matched_techs = set(t.lower() for t in criteria.technologies) & set(detected_techs)
            if matched_techs:
                match_reasons.append(f"Technologies verified: {', '.join(matched_techs)}")
                score += len(matched_techs) / len(criteria.technologies)
            else:
                mismatch_reasons.append(
                    f"Could not verify technologies: {', '.join(criteria.technologies)}"
                )
            checks += 1
        
        # Keyword check
        if criteria.keywords:
            found_keywords = []
            for kw in criteria.keywords:
                if kw.lower() in text_lower:
                    found_keywords.append(kw)
            
            if found_keywords:
                match_reasons.append(f"Keywords found: {', '.join(found_keywords)}")
                score += len(found_keywords) / len(criteria.keywords)
            else:
                mismatch_reasons.append(f"Keywords not found: {', '.join(criteria.keywords)}")
            checks += 1
        
        # Calculate final confidence
        confidence = score / max(checks, 1)
        verified = confidence >= 0.5
        
        return {
            "verified": verified,
            "confidence": round(confidence, 2),
            "match_reasons": match_reasons,
            "mismatch_reasons": mismatch_reasons,
            "detected_industry": self._extract_patterns_from_text(
                scraped_text, self.INDUSTRY_PATTERNS
            ),
            "detected_technologies": self._extract_patterns_from_text(
                scraped_text, self.TECH_PATTERNS
            ),
        }
    
    async def _ai_verification(
        self,
        scraped_text: str,
        criteria: VerificationCriteria,
        company: CompanyToVerify
    ) -> Dict[str, Any]:
        """
        AI-powered verification using OpenAI to analyze website content.
        """
        if not self.openai or not self.openai.is_connected():
            # Fall back to rule-based
            return self._rule_based_verification(scraped_text, criteria, company)
        
        # Truncate text for token efficiency (keep first ~4000 chars)
        text_excerpt = scraped_text[:4000] if len(scraped_text) > 4000 else scraped_text
        
        # Build criteria description
        criteria_parts = []
        if criteria.industry:
            criteria_parts.append(f"Industry: {criteria.industry}")
        if criteria.employee_count:
            criteria_parts.append(f"Company size: {criteria.employee_count} employees")
        if criteria.location:
            criteria_parts.append(f"Location: {criteria.location}")
        if criteria.technologies:
            criteria_parts.append(f"Technologies: {', '.join(criteria.technologies)}")
        if criteria.keywords:
            criteria_parts.append(f"Keywords: {', '.join(criteria.keywords)}")
        if criteria.description:
            criteria_parts.append(f"Description: {criteria.description}")
        
        criteria_str = "\n".join(criteria_parts) if criteria_parts else "No specific criteria"
        
        prompt = f"""Analyze this company website content and verify if it matches the search criteria.

COMPANY: {company.name}
DOMAIN: {company.domain or 'N/A'}
CLAIMED INDUSTRY: {company.claimed_industry or 'N/A'}

SEARCH CRITERIA:
{criteria_str}

WEBSITE CONTENT (excerpt):
{text_excerpt}

Analyze the website content and provide:
1. Does this company match the search criteria? (yes/no/uncertain)
2. Confidence level (0.0 to 1.0)
3. What industry does this company appear to be in?
4. What is their approximate company size based on content?
5. What location(s) are mentioned?
6. What technologies are mentioned?
7. Brief company description (1-2 sentences)
8. Reasons why it matches the criteria (list)
9. Reasons why it might not match (list)

Return ONLY valid JSON in this exact format:
{{
  "matches": true,
  "confidence": 0.85,
  "detected_industry": "SaaS",
  "detected_size": "50-200",
  "detected_location": "Germany",
  "detected_technologies": ["Python", "AWS"],
  "company_description": "B2B software company providing workflow automation.",
  "match_reasons": ["Industry matches: SaaS", "Location confirmed: Germany"],
  "mismatch_reasons": []
}}"""

        try:
            response = await self.openai.complete(
                prompt=prompt,
                model="gpt-4o-mini",
                temperature=0.1,
                max_tokens=600,
                system_prompt="You are a company data verification expert. Analyze website content to verify company attributes. Return ONLY valid JSON."
            )
            
            # Clean up response
            response = response.strip()
            if response.startswith("```"):
                response = re.sub(r'^```json?\n?', '', response)
                response = re.sub(r'\n?```$', '', response)
            
            data = json.loads(response)
            
            return {
                "verified": data.get("matches", False),
                "confidence": min(1.0, max(0.0, data.get("confidence", 0.5))),
                "match_reasons": data.get("match_reasons", []),
                "mismatch_reasons": data.get("mismatch_reasons", []),
                "detected_industry": data.get("detected_industry"),
                "detected_employee_count": data.get("detected_size"),
                "detected_location": data.get("detected_location"),
                "detected_technologies": data.get("detected_technologies", []),
                "company_description": data.get("company_description"),
            }
            
        except json.JSONDecodeError as e:
            logger.warning(f"AI verification JSON parse failed: {e}")
            return self._rule_based_verification(scraped_text, criteria, company)
        except Exception as e:
            logger.error(f"AI verification failed: {e}")
            return self._rule_based_verification(scraped_text, criteria, company)
    
    async def verify_company(
        self,
        company: CompanyToVerify,
        criteria: VerificationCriteria,
        use_ai: bool = True,
        scrape_timeout: int = 15
    ) -> VerificationResult:
        """
        Verify a single company against search criteria.
        
        1. Scrape the company's website
        2. Analyze content with AI (or rules if AI unavailable)
        3. Return verification result with confidence score
        """
        # Check if we have a domain to scrape
        if not company.domain:
            return VerificationResult(
                company_id=company.id,
                company_name=company.name,
                domain=company.domain,
                verified=False,
                confidence=0.0,
                error="No domain provided for verification",
            )
        
        # Scrape the website
        logger.info(f"Scraping {company.domain} for verification...")
        scrape_result = await self.scraper.scrape_website(
            company.domain,
            timeout=scrape_timeout
        )
        
        if not scrape_result["success"]:
            return VerificationResult(
                company_id=company.id,
                company_name=company.name,
                domain=company.domain,
                verified=False,
                confidence=0.0,
                error=f"Scrape failed: {scrape_result.get('error', 'Unknown error')}",
                scraped_data={"error": scrape_result.get("error")},
            )
        
        scraped_text = scrape_result.get("text", "")
        
        if len(scraped_text) < 100:
            return VerificationResult(
                company_id=company.id,
                company_name=company.name,
                domain=company.domain,
                verified=False,
                confidence=0.0,
                error="Insufficient content scraped from website",
                scraped_data={"text_length": len(scraped_text)},
            )
        
        # Analyze with AI or rules
        if use_ai:
            analysis = await self._ai_verification(scraped_text, criteria, company)
        else:
            analysis = self._rule_based_verification(scraped_text, criteria, company)
        
        return VerificationResult(
            company_id=company.id,
            company_name=company.name,
            domain=company.domain,
            verified=analysis["verified"],
            confidence=analysis["confidence"],
            match_reasons=analysis.get("match_reasons", []),
            mismatch_reasons=analysis.get("mismatch_reasons", []),
            scraped_data={
                "text_length": len(scraped_text),
                "url": scrape_result.get("final_url"),
            },
            detected_industry=analysis.get("detected_industry") if isinstance(analysis.get("detected_industry"), str) else (analysis.get("detected_industry", [None])[0] if analysis.get("detected_industry") else None),
            detected_employee_count=analysis.get("detected_employee_count"),
            detected_location=analysis.get("detected_location"),
            detected_technologies=analysis.get("detected_technologies", []) if isinstance(analysis.get("detected_technologies"), list) else [],
            company_description=analysis.get("company_description"),
        )
    
    async def verify_batch(
        self,
        companies: List[CompanyToVerify],
        criteria: VerificationCriteria,
        use_ai: bool = True,
        max_concurrent: int = 5,
        scrape_timeout: int = 15
    ) -> BatchVerificationResult:
        """
        Verify multiple companies concurrently.
        
        Args:
            companies: List of companies to verify
            criteria: Search criteria to verify against
            use_ai: Whether to use AI for verification
            max_concurrent: Maximum concurrent verifications
            scrape_timeout: Timeout for each website scrape
            
        Returns:
            BatchVerificationResult with all results and summary
        """
        if not companies:
            return BatchVerificationResult(
                total=0,
                verified_count=0,
                failed_count=0,
                results=[],
                summary="No companies to verify"
            )
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def verify_with_semaphore(company: CompanyToVerify) -> VerificationResult:
            async with semaphore:
                return await self.verify_company(
                    company, criteria, use_ai, scrape_timeout
                )
        
        # Run verifications concurrently
        tasks = [verify_with_semaphore(c) for c in companies]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        processed_results = []
        verified_count = 0
        failed_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed_count += 1
                processed_results.append(VerificationResult(
                    company_id=companies[i].id,
                    company_name=companies[i].name,
                    domain=companies[i].domain,
                    verified=False,
                    confidence=0.0,
                    error=str(result),
                ))
            else:
                processed_results.append(result)
                if result.verified:
                    verified_count += 1
                if result.error:
                    failed_count += 1
        
        # Generate summary
        total = len(companies)
        verification_rate = verified_count / total if total > 0 else 0
        summary = (
            f"Verified {verified_count}/{total} companies ({verification_rate:.0%}). "
            f"{failed_count} failed to scrape."
        )
        
        return BatchVerificationResult(
            total=total,
            verified_count=verified_count,
            failed_count=failed_count,
            results=processed_results,
            summary=summary
        )
    
    async def verify_search_results(
        self,
        search_results: List[Dict[str, Any]],
        criteria: VerificationCriteria,
        use_ai: bool = True,
        verify_limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Convenience method: Verify search results and return enriched results.
        
        Takes raw search results, verifies them, and returns results with
        verification info attached.
        
        Args:
            search_results: List of company dicts from search
            criteria: Criteria to verify against
            use_ai: Whether to use AI
            verify_limit: Max companies to verify (for cost control)
            
        Returns:
            Search results with verification info added
        """
        # Convert to CompanyToVerify objects
        companies_to_verify = []
        for result in search_results[:verify_limit]:
            companies_to_verify.append(CompanyToVerify(
                id=result.get("id", ""),
                name=result.get("name", "Unknown"),
                domain=result.get("domain"),
                claimed_industry=result.get("industry"),
                claimed_employee_count=result.get("employee_count"),
                claimed_location=result.get("location"),
                claimed_technologies=result.get("technologies"),
            ))
        
        if not companies_to_verify:
            return search_results
        
        # Run batch verification
        batch_result = await self.verify_batch(
            companies_to_verify,
            criteria,
            use_ai=use_ai
        )
        
        # Create lookup map
        verification_map = {r.company_id: r for r in batch_result.results}
        
        # Enrich search results
        enriched_results = []
        for result in search_results:
            result_copy = dict(result)
            verification = verification_map.get(result.get("id"))
            
            if verification:
                result_copy["verified"] = verification.verified
                result_copy["verification_confidence"] = verification.confidence
                result_copy["verification_reasons"] = verification.match_reasons
                result_copy["verification_warnings"] = verification.mismatch_reasons
                
                # Optionally override with detected values
                if verification.detected_industry:
                    result_copy["detected_industry"] = verification.detected_industry
                if verification.company_description:
                    result_copy["ai_description"] = verification.company_description
            else:
                result_copy["verified"] = None  # Not verified (beyond limit)
            
            enriched_results.append(result_copy)
        
        return enriched_results


# Singleton instance
verification_service = VerificationService()


def get_verification_service() -> VerificationService:
    """Get the verification service instance."""
    return verification_service
