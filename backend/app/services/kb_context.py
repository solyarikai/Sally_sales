"""
Knowledge Base Context Service - Handle @tags in prompts
Multi-tenant support - all queries filter by company_id
"""
import re
from typing import List, Dict, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.knowledge_base import (
    CompanyProfile, Product, Segment, Competitor, CaseStudy,
    VoiceTone, BookingLink, Document
)


# Tag patterns
TAG_PATTERN = re.compile(r'@(\w+)(?::([^\s@]+))?')


async def get_available_tags(db: AsyncSession, company_id: int) -> List[Dict[str, Any]]:
    """
    Get all available @tags for autocomplete.
    Returns list of {tag, label, description, type}
    Filters by company_id for data isolation.
    """
    tags = []
    
    # Company summary
    company_result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.company_id == company_id)
    )
    company = company_result.scalar_one_or_none()
    if company and company.summary:
        tags.append({
            "tag": "@summary",
            "label": "Company Summary",
            "description": "Auto-generated company overview",
            "type": "summary"
        })
    
    if company:
        tags.append({
            "tag": "@company",
            "label": "Company Profile",
            "description": company.name or "Company info",
            "type": "company"
        })
    
    # Products
    products_result = await db.execute(
        select(Product).where(
            and_(Product.company_id == company_id, Product.is_active == True)
        ).order_by(Product.name)
    )
    for prod in products_result.scalars():
        tags.append({
            "tag": f"@product:{prod.name.replace(' ', '_')}",
            "label": prod.name,
            "description": (prod.description or "")[:50] + "..." if prod.description and len(prod.description) > 50 else prod.description,
            "type": "product"
        })
    
    # Segments
    segments_result = await db.execute(
        select(Segment).where(
            and_(Segment.company_id == company_id, Segment.is_active == True)
        ).order_by(Segment.name)
    )
    for seg in segments_result.scalars():
        desc = seg.data.get("description", "") if seg.data else ""
        tags.append({
            "tag": f"@segment:{seg.name.replace(' ', '_')}",
            "label": seg.name,
            "description": desc[:50] + "..." if len(desc) > 50 else desc,
            "type": "segment"
        })
    
    # Voice Tones
    tones_result = await db.execute(
        select(VoiceTone).where(VoiceTone.company_id == company_id).order_by(VoiceTone.name)
    )
    for tone in tones_result.scalars():
        tags.append({
            "tag": f"@voice:{tone.name.replace(' ', '_')}",
            "label": tone.name,
            "description": (tone.description or "")[:50] + "..." if tone.description and len(tone.description) > 50 else tone.description,
            "type": "voice"
        })
    
    # Case Studies
    cases_result = await db.execute(
        select(CaseStudy).where(CaseStudy.company_id == company_id).order_by(CaseStudy.client_name)
    )
    for case in cases_result.scalars():
        tags.append({
            "tag": f"@case:{case.client_name.replace(' ', '_')}",
            "label": case.client_name,
            "description": case.client_industry or "Case study",
            "type": "case"
        })
    
    # Booking Links
    booking_result = await db.execute(
        select(BookingLink).where(
            and_(BookingLink.company_id == company_id, BookingLink.is_active == True)
        ).order_by(BookingLink.name)
    )
    for link in booking_result.scalars():
        tags.append({
            "tag": f"@booking:{link.name.replace(' ', '_')}",
            "label": link.name,
            "description": link.when_to_use[:50] if link.when_to_use else "Booking link",
            "type": "booking"
        })
    
    # Competitors
    competitors_result = await db.execute(
        select(Competitor).where(Competitor.company_id == company_id).order_by(Competitor.name)
    )
    for comp in competitors_result.scalars():
        tags.append({
            "tag": f"@competitor:{comp.name.replace(' ', '_')}",
            "label": comp.name,
            "description": comp.website or "Competitor",
            "type": "competitor"
        })
    
    # Documents
    docs_result = await db.execute(
        select(Document).where(
            and_(Document.company_id == company_id, Document.status == 'processed')
        ).order_by(Document.name)
    )
    for doc in docs_result.scalars():
        tags.append({
            "tag": f"@doc:{doc.name.replace(' ', '_')}",
            "label": doc.name,
            "description": doc.document_type or doc.original_filename,
            "type": "document"
        })
    
    return tags


async def resolve_tags(prompt: str, db: AsyncSession, company_id: int) -> Dict[str, Any]:
    """
    Find all @tags in prompt and resolve them to actual content.
    Returns {resolved_prompt, context_parts, tags_found}
    Filters by company_id for data isolation.
    """
    tags_found = TAG_PATTERN.findall(prompt)
    context_parts = []
    
    for tag_type, tag_value in tags_found:
        content = await _get_tag_content(tag_type, tag_value, db, company_id)
        if content:
            context_parts.append(content)
    
    # Build context block to prepend
    if context_parts:
        context_block = "\n\n---\n# CONTEXT FROM KNOWLEDGE BASE\n\n" + "\n\n".join(context_parts) + "\n---\n\n"
    else:
        context_block = ""
    
    return {
        "original_prompt": prompt,
        "context": context_block,
        "enriched_prompt": context_block + prompt,
        "tags_found": [f"@{t}:{v}" if v else f"@{t}" for t, v in tags_found],
        "context_parts": context_parts
    }


async def _get_tag_content(tag_type: str, tag_value: Optional[str], db: AsyncSession, company_id: int) -> Optional[str]:
    """Get markdown content for a specific tag. Filters by company_id."""
    
    tag_type = tag_type.lower()
    
    if tag_type == "summary":
        result = await db.execute(
            select(CompanyProfile).where(CompanyProfile.company_id == company_id)
        )
        company = result.scalar_one_or_none()
        if company and company.summary:
            return f"## Company Summary\n\n{company.summary}"
    
    elif tag_type == "company":
        result = await db.execute(
            select(CompanyProfile).where(CompanyProfile.company_id == company_id)
        )
        company = result.scalar_one_or_none()
        if company:
            return f"""## Company: {company.name or 'Our Company'}
**Website:** {company.website or 'N/A'}

{company.summary or ''}"""
    
    elif tag_type == "product" and tag_value:
        search_name = tag_value.replace('_', ' ')
        result = await db.execute(
            select(Product).where(
                and_(Product.company_id == company_id, Product.name.ilike(f"%{search_name}%"))
            )
        )
        prod = result.scalar_one_or_none()
        if prod:
            features = "\n".join(f"- {f}" for f in (prod.features or []))
            pricing_str = ""
            if prod.pricing:
                pricing_str = f"\n**Pricing:** {prod.pricing.get('price', 'Contact us')}"
            
            return f"""## Product: {prod.name}
{prod.description or ''}
{pricing_str}

**Features:**
{features}

**Email snippet:** {prod.email_snippet or 'N/A'}"""
    
    elif tag_type == "segment" and tag_value:
        search_name = tag_value.replace('_', ' ')
        result = await db.execute(
            select(Segment).where(
                and_(Segment.company_id == company_id, Segment.name.ilike(f"%{search_name}%"))
            )
        )
        seg = result.scalar_one_or_none()
        if seg:
            data = seg.data or {}
            
            problems = "\n".join(f"- {p}" for p in (data.get('problems_we_solve') or []))
            offers = "\n".join(f"- {o}" for o in (data.get('our_offer') or []))
            diffs = "\n".join(f"- {d}" for d in (data.get('differentiators') or []))
            titles = ", ".join(data.get('target_job_titles') or [])
            
            return f"""## Segment: {seg.name}
{data.get('description', '')}

**Target:** {data.get('employee_count', 'N/A')} employees, {data.get('revenue', 'N/A')} revenue
**Job Titles:** {titles}

### Problems We Solve
{problems}

### Our Offer
{offers}

### Differentiators
{diffs}

### Email Sequence
{data.get('email_sequence', 'N/A')}

### Pricing
{data.get('pricing', 'N/A')}"""
    
    elif tag_type == "voice" and tag_value:
        search_name = tag_value.replace('_', ' ')
        result = await db.execute(
            select(VoiceTone).where(
                and_(VoiceTone.company_id == company_id, VoiceTone.name.ilike(f"%{search_name}%"))
            )
        )
        tone = result.scalar_one_or_none()
        if tone:
            do_use = ", ".join(tone.do_use or [])
            dont_use = ", ".join(tone.dont_use or [])
            traits = ", ".join(tone.personality_traits or [])
            
            return f"""## Voice & Tone: {tone.name}
{tone.description or ''}

**Style:** {tone.writing_style or 'N/A'}
**Personality:** {traits}
**Formality:** {tone.formality_level}/10
**Use emojis:** {'Yes' if tone.emoji_usage else 'No'}

**Do use:** {do_use}
**Don't use:** {dont_use}"""
    
    elif tag_type == "case" and tag_value:
        search_name = tag_value.replace('_', ' ')
        result = await db.execute(
            select(CaseStudy).where(
                and_(CaseStudy.company_id == company_id, CaseStudy.client_name.ilike(f"%{search_name}%"))
            )
        )
        case = result.scalar_one_or_none()
        if case:
            return f"""## Case Study: {case.client_name}
**Industry:** {case.client_industry or 'N/A'}
**Size:** {case.client_size or 'N/A'}

**Challenge:** {case.challenge or 'N/A'}
**Solution:** {case.solution or 'N/A'}
**Results:** {case.results or 'N/A'}

**Testimonial:** "{case.testimonial or 'N/A'}"
— {case.testimonial_author or 'N/A'}, {case.testimonial_title or 'N/A'}

**Email snippet:** {case.email_snippet or 'N/A'}"""
    
    elif tag_type == "booking" and tag_value:
        search_name = tag_value.replace('_', ' ')
        result = await db.execute(
            select(BookingLink).where(
                and_(BookingLink.company_id == company_id, BookingLink.name.ilike(f"%{search_name}%"))
            )
        )
        link = result.scalar_one_or_none()
        if link:
            return f"""## Booking Link: {link.name}
**URL:** {link.url}
**When to use:** {link.when_to_use or 'N/A'}"""
    
    elif tag_type == "competitor" and tag_value:
        search_name = tag_value.replace('_', ' ')
        result = await db.execute(
            select(Competitor).where(
                and_(Competitor.company_id == company_id, Competitor.name.ilike(f"%{search_name}%"))
            )
        )
        comp = result.scalar_one_or_none()
        if comp:
            strengths = "\n".join(f"- {s}" for s in (comp.their_strengths or []))
            weaknesses = "\n".join(f"- {w}" for w in (comp.their_weaknesses or []))
            advantages = "\n".join(f"- {a}" for a in (comp.our_advantages or []))
            
            return f"""## Competitor: {comp.name}
**Website:** {comp.website or 'N/A'}
{comp.description or ''}

**Their Strengths:**
{strengths}

**Their Weaknesses:**
{weaknesses}

**Our Advantages:**
{advantages}

**Their Positioning:** {comp.their_positioning or 'N/A'}
**Price Comparison:** {comp.price_comparison or 'N/A'}"""
    
    elif tag_type == "doc" and tag_value:
        search_name = tag_value.replace('_', ' ')
        result = await db.execute(
            select(Document).where(
                and_(Document.company_id == company_id, Document.name.ilike(f"%{search_name}%"))
            )
        )
        doc = result.scalar_one_or_none()
        if doc and doc.content_md:
            return f"""## Document: {doc.name}
**Type:** {doc.document_type or 'N/A'}

{doc.content_md}"""
    
    return None
