"""
AI Import Service - Parse free-form text into structured knowledge base entities
"""
import json
from typing import Optional, Any
from openai import AsyncOpenAI
from app.core.config import settings


client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


ENTITY_PROMPTS = {
    "competitor": """Parse this text about a competitor into structured data.
Extract:
- name: Company name
- website: Their website URL
- description: Brief description
- their_strengths: List of their strengths
- their_weaknesses: List of their weaknesses
- our_advantages: How we're better than them
- their_positioning: How they position themselves
- price_comparison: How their pricing compares

Return JSON only, no markdown.""",

    "case_study": """Parse this text about a customer success story into structured data.
Extract:
- client_name: Customer company name
- client_website: Their website
- client_industry: Their industry
- client_size: Company size (employees or revenue)
- challenge: What problem they had
- solution: How we helped them
- results: What they achieved
- key_metrics: Dict of specific metrics (e.g., {"conversion_increase": "32%"})
- testimonial: Any quote from them
- testimonial_author: Who said the quote
- testimonial_title: Their job title
- email_snippet: A short version to use in emails

Return JSON only, no markdown.""",

    "current_client": """Parse this text about a current client into structured data.
Extract:
- company_name: Company name
- website: Their website
- industry: Their industry
- employee_count: Number of employees
- revenue: Their revenue
- contact_name: Main contact person
- contact_title: Their job title
- products_used: List of our products they use
- contract_value: Annual contract value
- started_date: When they became a client
- can_reference: Can we mention them publicly? (true/false)
- notes: Any other notes

Return JSON only, no markdown.""",

    "voice_tone": """Parse this text about a messaging style into structured data.
Extract:
- name: Style name (e.g., "Professional", "Friendly")
- description: Description of this style
- personality_traits: List of personality traits
- writing_style: How to write in this style
- do_use: List of words/phrases to use
- dont_use: List of words/phrases to avoid
- example_messages: List of example messages
- formality_level: 1-10 scale (1=casual, 10=formal)
- emoji_usage: Should we use emojis? (true/false)

Return JSON only, no markdown.""",

    "pricing": """Parse this text about pricing into structured data.
Extract:
- name: Tier name (e.g., "Enterprise", "Starter")
- description: Description of this tier
- price: Price (e.g., "$500/mo", "Custom")
- billing_period: "monthly", "annual", or "one-time"
- features: List of included features
- limitations: List of limitations
- ideal_for: Who this tier is for
- email_snippet: How to describe in outreach emails

Return JSON only, no markdown.""",

    "email_sequence": """Parse this text about an email sequence into structured data.
Extract:
- name: Sequence name
- description: What this sequence is for
- steps: List of email steps, each with:
  - step: Step number (1, 2, 3...)
  - delay_days: Days after previous email
  - subject: Email subject line
  - body: Email body text
  - notes: Any notes about this step
- open_rate: Expected open rate (if mentioned)
- reply_rate: Expected reply rate (if mentioned)

Return JSON only, no markdown.""",

    "booking_link": """Parse this text about a booking link into structured data.
Extract:
- name: Link name (e.g., "Demo Call - John")
- url: The booking URL
- link_type: Type of link (calendly, hubspot, custom)
- sending_account_email: Which sender email uses this
- sending_account_name: Sender name
- use_case: When to use this link
- duration_minutes: Meeting duration
- meeting_type: Type of meeting (intro, demo, follow-up)

Return JSON only, no markdown.""",

    "segment": """Parse this text about a target segment into structured data.
Extract:
- name: Segment identifier (e.g., "CRYPTO_EXCHANGE")
- description: Full description of this segment
- employee_count_min: Minimum employee count
- employee_count_max: Maximum employee count  
- revenue_min: Minimum revenue (e.g., "$50M")
- revenue_max: Maximum revenue (e.g., "$800M")
- example_companies: List of example company domains
- target_countries: List of target countries
- target_job_titles: List of target job titles
- problems_we_solve: List of problems we solve for them
- what_they_need: List of what they need
- our_offer: List of what we offer them
- differentiators: List of our differentiators
- social_proof: List of relevant social proof
- cases: List of relevant case studies
- notes: Any additional notes

Return JSON only, no markdown.""",
}


async def parse_free_text(
    text: str, 
    entity_type: str,
    additional_context: Optional[str] = None
) -> dict:
    """
    Parse free-form text into structured entity data using AI.
    
    Args:
        text: The free-form text to parse
        entity_type: Type of entity to extract (competitor, case_study, etc.)
        additional_context: Optional company context to help AI understand better
    
    Returns:
        Dict with extracted data
    """
    if entity_type not in ENTITY_PROMPTS:
        raise ValueError(f"Unknown entity type: {entity_type}")
    
    system_prompt = ENTITY_PROMPTS[entity_type]
    
    if additional_context:
        system_prompt += f"\n\nCompany context:\n{additional_context}"
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return {
            "success": True,
            "data": result,
            "tokens_used": response.usage.total_tokens if response.usage else 0
        }
        
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Failed to parse AI response as JSON: {str(e)}",
            "raw_response": response.choices[0].message.content if response else None
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


async def parse_multiple_entities(
    text: str,
    entity_type: str,
    additional_context: Optional[str] = None
) -> dict:
    """
    Parse text that may contain multiple entities of the same type.
    Useful for bulk import.
    """
    system_prompt = f"""Parse this text and extract ALL {entity_type}s mentioned.
Return a JSON object with a "{entity_type}s" array containing each extracted entity.

{ENTITY_PROMPTS.get(entity_type, '')}

If multiple entities are found, return them all in the array.
Return JSON only, no markdown."""

    if additional_context:
        system_prompt += f"\n\nCompany context:\n{additional_context}"
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return {
            "success": True,
            "data": result,
            "tokens_used": response.usage.total_tokens if response.usage else 0
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


async def convert_document_to_markdown(content: str, filename: str) -> dict:
    """
    Convert document content to clean markdown format for AI context.
    """
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system", 
                    "content": """Convert this document to clean, well-structured Markdown.
- Keep all important information
- Use headers, lists, and formatting appropriately
- Remove any formatting artifacts or noise
- Make it easy for an AI to understand and reference
Return only the markdown, no explanations."""
                },
                {"role": "user", "content": f"Filename: {filename}\n\nContent:\n{content}"}
            ],
            temperature=0.1,
        )
        
        return {
            "success": True,
            "markdown": response.choices[0].message.content,
            "tokens_used": response.usage.total_tokens if response.usage else 0
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
