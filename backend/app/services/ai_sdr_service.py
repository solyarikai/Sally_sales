"""
AI SDR Service - Generate TAM, GTM plans, and pitch templates per project.

Uses OpenAI to analyze contacts and generate strategic content.
"""
from typing import Dict, Any, List, Optional
from app.services.openai_service import openai_service
import logging
import json

logger = logging.getLogger(__name__)


class AISDRService:
    """Generate TAM analysis, GTM plans, and pitch templates for projects."""
    
    def __init__(self):
        self.openai = openai_service
    
    async def generate_tam_analysis(
        self,
        project_name: str,
        target_industries: Optional[str],
        target_segments: Optional[str],
        contacts: List[Dict[str, Any]],
    ) -> str:
        """
        Generate Total Addressable Market (TAM) analysis for a project.
        
        Analyzes contacts to understand:
        - Market size and segmentation
        - Company distribution by size/industry
        - Geographic distribution
        - Key decision-maker patterns
        """
        # Summarize contacts for analysis
        contact_summary = self._summarize_contacts(contacts)
        
        system_prompt = """You are a B2B market analyst specializing in TAM/SAM/SOM analysis.
Generate a concise, actionable TAM analysis based on the contact data provided.
Focus on practical insights, not theoretical frameworks.
Use bullet points and clear structure.
Keep the analysis under 500 words."""

        prompt = f"""Analyze the Total Addressable Market for project "{project_name}".

Target Industries: {target_industries or 'Not specified'}
Target Segments: {target_segments or 'Not specified'}

Contact Data Summary:
{contact_summary}

Generate a TAM analysis including:
1. **Market Overview** - Size estimate based on contact patterns
2. **Industry Breakdown** - Key industries and their potential
3. **Company Profiles** - Typical target company characteristics
4. **Decision Makers** - Common titles and roles
5. **Geographic Focus** - Where opportunities are concentrated
6. **Market Gaps** - Segments with few contacts (potential opportunities)

Be specific and actionable. Reference the actual data."""

        try:
            result = await self.openai.generate_single(
                prompt=prompt,
                system_prompt=system_prompt,
                model="gpt-4o-mini"
            )
            return result
        except Exception as e:
            logger.error(f"TAM generation failed: {e}")
            raise

    async def generate_gtm_plan(
        self,
        project_name: str,
        target_industries: Optional[str],
        target_segments: Optional[str],
        contacts: List[Dict[str, Any]],
        tam_analysis: Optional[str] = None,
    ) -> str:
        """
        Generate Go-To-Market plan for a project.
        
        Creates actionable outreach strategy based on:
        - Contact segmentation
        - Industry priorities
        - Channel recommendations
        - Sequence suggestions
        """
        contact_summary = self._summarize_contacts(contacts)
        
        system_prompt = """You are a B2B GTM strategist with expertise in outbound sales.
Generate a practical Go-To-Market plan that can be executed immediately.
Focus on actionable steps, not theory.
Use bullet points and clear structure.
Keep the plan under 600 words."""

        tam_context = f"\n\nTAM Analysis for context:\n{tam_analysis}" if tam_analysis else ""

        prompt = f"""Create a Go-To-Market plan for project "{project_name}".

Target Industries: {target_industries or 'Not specified'}
Target Segments: {target_segments or 'Not specified'}

Contact Data Summary:
{contact_summary}{tam_context}

Generate a GTM plan including:
1. **Priority Segments** - Which segments to target first and why
2. **Outreach Sequence** - Recommended touch points (email, LinkedIn, etc.)
3. **Messaging Angles** - Key value propositions per segment
4. **Timing Strategy** - Best times/days for outreach
5. **Qualification Criteria** - How to identify hot vs cold leads
6. **Metrics to Track** - KPIs for success

Be specific. Give concrete recommendations based on the contact data."""

        try:
            result = await self.openai.generate_single(
                prompt=prompt,
                system_prompt=system_prompt,
                model="gpt-4o-mini"
            )
            return result
        except Exception as e:
            logger.error(f"GTM generation failed: {e}")
            raise

    async def generate_pitch_templates(
        self,
        project_name: str,
        target_industries: Optional[str],
        target_segments: Optional[str],
        contacts: List[Dict[str, Any]],
        tam_analysis: Optional[str] = None,
        gtm_plan: Optional[str] = None,
    ) -> str:
        """
        Generate pitch email templates for a project.
        
        Creates personalized templates for different segments/personas.
        """
        contact_summary = self._summarize_contacts(contacts)
        
        # Extract unique segments and titles for template variety
        segments = list(set(c.get('segment') for c in contacts if c.get('segment')))[:5]
        titles = list(set(c.get('job_title') for c in contacts if c.get('job_title')))[:10]
        
        system_prompt = """You are an expert cold email copywriter specializing in B2B outreach.
Generate email templates that are:
- Personalized (using {{first_name}}, {{company_name}} placeholders)
- Concise (under 100 words body)
- Value-focused (not salesy)
- Easy to customize

Use placeholders: {{first_name}}, {{company_name}}, {{job_title}}"""

        context = ""
        if tam_analysis:
            context += f"\n\nTAM Analysis:\n{tam_analysis[:500]}..."
        if gtm_plan:
            context += f"\n\nGTM Plan:\n{gtm_plan[:500]}..."

        prompt = f"""Create cold email templates for project "{project_name}".

Target Industries: {target_industries or 'Not specified'}
Target Segments: {target_segments or 'Not specified'}
Common Segments in Data: {', '.join(segments) if segments else 'Various'}
Common Job Titles: {', '.join(titles[:5]) if titles else 'Various executives'}

Contact Summary:
{contact_summary}{context}

Generate 3-4 email templates:

1. **Initial Outreach** - First cold email (curiosity hook)
2. **Follow-up #1** - After no response (different angle)
3. **Value-Add** - Sharing relevant insight/resource
4. **Break-up Email** - Final attempt (creates urgency)

For each template, provide:
- Subject line
- Email body (use placeholders)
- Call-to-action

Make templates different enough that they don't feel like the same message."""

        try:
            result = await self.openai.generate_single(
                prompt=prompt,
                system_prompt=system_prompt,
                model="gpt-4o-mini"
            )
            return result
        except Exception as e:
            logger.error(f"Pitch templates generation failed: {e}")
            raise

    def _summarize_contacts(self, contacts: List[Dict[str, Any]]) -> str:
        """Create a summary of contacts for AI analysis."""
        if not contacts:
            return "No contacts in this project yet."
        
        total = len(contacts)
        
        # Count by segment
        segments: Dict[str, int] = {}
        for c in contacts:
            seg = c.get('segment') or 'Unknown'
            segments[seg] = segments.get(seg, 0) + 1
        
        # Count by status
        statuses: Dict[str, int] = {}
        for c in contacts:
            status = c.get('status') or 'Unknown'
            statuses[status] = statuses.get(status, 0) + 1
        
        # Count by company
        companies: Dict[str, int] = {}
        for c in contacts:
            company = c.get('company_name') or 'Unknown'
            companies[company] = companies.get(company, 0) + 1
        
        # Count by job title
        titles: Dict[str, int] = {}
        for c in contacts:
            title = c.get('job_title') or 'Unknown'
            titles[title] = titles.get(title, 0) + 1
        
        # Count by location
        locations: Dict[str, int] = {}
        for c in contacts:
            loc = c.get('location') or 'Unknown'
            locations[loc] = locations.get(loc, 0) + 1
        
        summary = f"""Total Contacts: {total}

By Segment:
{self._format_counts(segments)}

By Status:
{self._format_counts(statuses)}

Top Companies ({len(companies)} unique):
{self._format_counts(companies, limit=10)}

Top Job Titles ({len(titles)} unique):
{self._format_counts(titles, limit=10)}

Locations:
{self._format_counts(locations, limit=5)}"""
        
        return summary
    
    def _format_counts(self, counts: Dict[str, int], limit: int = 10) -> str:
        """Format a count dictionary as readable lines."""
        sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        return '\n'.join(f"  - {k}: {v}" for k, v in sorted_items)


# Global instance
ai_sdr_service = AISDRService()
