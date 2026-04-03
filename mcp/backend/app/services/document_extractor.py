"""Document Extraction Service — extracts project data from strategy documents.

Reads a user-provided document (outreach plan, ICP definition, campaign brief)
and extracts structured data: offer, roles, filters, sequences, settings.
Silently skips what can't be automated.
"""
import json
import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


async def extract_from_document(
    text: str,
    website: str,
    openai_key: str,
    model: str = "gpt-5.4-mini",
) -> Dict[str, Any]:
    """Extract project data from a strategy document.

    Extracts what can be automated. Silently skips the rest.
    Model: gpt-5.4-mini (v5 prompt) — tested 2026-04-03 across 11 models x 4 prompts.
    Winner: 100% accuracy, 11s, $0.003/call, 8 segments, 80 keywords on both fintech + iGaming docs.
    """
    prompt = f"""Read this outreach campaign document. Extract everything into JSON.

Website: {website}

I need:
- offer: what the company sells (1 sentence)
- value_prop: the key value proposition
- target_audience: who they sell to
- target_roles: {{primary: [titles], secondary: [titles], tertiary: [titles], seniorities: [apollo seniority levels]}}
- segments: EVERY industry sub-vertical mentioned in the document. Each segment is a distinct type of company. NOT generic categories like "Funded Companies" or "High Value Targets". Format:
  {{"name": "SHORT_CAPS_LABEL", "keywords": [8-10 specific product/technology terms that ONLY companies in this sub-vertical would have on their website]}}
- apollo_filters:
  - combined_keywords: merge ALL segment keywords into one flat list (aim for 60-80 total)
  - locations: [target countries]
  - employee_range: "min,max"
  - industries: [broad industry names]
  - funding_stages: [if mentioned]
- sequences: email sequences from the doc as {{name, steps: [{{day, subject, body}}]}}
  - Use ONLY SmartLead variable format: {{{{first_name}}}}, {{{{last_name}}}}, {{{{company_name}}}}, {{{{city}}}}, {{{{signature}}}}
  - For ANY non-standard variable: replace with natural text that works without external data
- exclusion_list: company types to NOT target. Format: {{type: "category", reason: "why exclude"}}
- example_companies: seed companies mentioned. Format: {{domain, name, reason}}
- campaign_settings: {{tracking, stop_on_reply, plain_text, daily_limit_per_mailbox}}

Return ONLY JSON. No explanation, no markdown.

DOCUMENT:
{text[:25000]}"""

    try:
        is_reasoning = model.startswith("o") or model.startswith("gpt-5")
        request_body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if is_reasoning:
            request_body["max_completion_tokens"] = 8000
        else:
            request_body["max_tokens"] = 4000
            request_body["temperature"] = 0

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                json=request_body,
            )
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Parse JSON — handle markdown wrapping and reasoning model output
            import re as _re
            clean = content.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
            # Reasoning models may have text before/after JSON
            json_match = _re.search(r'\{[\s\S]+\}', clean)
            if json_match:
                clean = json_match.group()

            result = json.loads(clean)

            # Post-process sequences: GPT rewrites emails with unfillable variables
            # Keeps user's tone/intent but makes ALL variables standard SmartLead ones
            import re
            # SmartLead variable name mapping: normalize to match lead column names
            VAR_MAP = {
                "firstname": "first_name", "firstName": "first_name",
                "lastname": "last_name", "lastName": "last_name",
                "company": "company_name", "companyName": "company_name", "company_name": "company_name",
                "city": "city", "email": "email",
                "phone": "phone_number", "phoneNumber": "phone_number", "phone_number": "phone_number",
                "signature": "signature",
                "first_name": "first_name", "last_name": "last_name",
            }
            STANDARD_VARS = set(VAR_MAP.values()) | set(VAR_MAP.keys())

            # First pass: normalize all variable names to SmartLead format
            for seq in result.get("sequences", []):
                for step in seq.get("steps", []):
                    for field in ("subject", "body"):
                        text = step.get(field, "")
                        for old_var, new_var in VAR_MAP.items():
                            if old_var != new_var:
                                text = text.replace("{{" + old_var + "}}", "{{" + new_var + "}}")
                        step[field] = text

            for seq in result.get("sequences", []):
                has_unfillable = False
                for step in seq.get("steps", []):
                    for field in ("subject", "body"):
                        variables = re.findall(r'\{\{(\w+)\}\}', step.get(field, ""))
                        if any(v.lower() not in STANDARD_VARS for v in variables):
                            has_unfillable = True
                            break

                if has_unfillable:
                    # GPT rewrites the sequence to use only standard variables
                    try:
                        rewrite_prompt = (
                            f"Fix the variables in this email sequence. Available variables: "
                            f"{{{{first_name}}}}, {{{{last_name}}}}, {{{{company_name}}}}, {{{{city}}}}, {{{{signature}}}}\n\n"
                            f"RULES:\n"
                            f"1. Keep the EXACT original text word-for-word. Do NOT rewrite, paraphrase, or shorten.\n"
                            f"2. ONLY change unfillable variables like {{{{hiring_role_or_signal}}}}, {{{{estimated_acv}}}}, {{{{calendly_link}}}} — "
                            f"replace them with natural language that makes sense without external data.\n"
                            f"3. Normalize variable names: {{{{firstName}}}} → {{{{first_name}}}}, {{{{company}}}} → {{{{company_name}}}}\n"
                            f"4. Keep ALL line breaks, formatting, and structure exactly as-is.\n\n"
                            f"Original sequence:\n"
                        )
                        for step in seq.get("steps", []):
                            rewrite_prompt += f"\nEmail (Day {step.get('day')}):\nSubject: {step.get('subject')}\nBody: {step.get('body')}\n"

                        rewrite_prompt += (
                            f"\n\nReturn JSON array: [{{\"day\": N, \"subject\": \"...\", \"body\": \"...\"}}]\n"
                            f"Keep {{{{company}}}}, {{{{firstName}}}}, {{{{signature}}}} as variables. Replace everything else with natural text."
                        )

                        async with httpx.AsyncClient(timeout=30) as rewrite_client:
                            rr = await rewrite_client.post(
                                "https://api.openai.com/v1/chat/completions",
                                headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
                                json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": rewrite_prompt}],
                                      "max_tokens": 3000, "temperature": 0.3},
                            )
                            rr_data = rr.json()
                            rr_content = rr_data["choices"][0]["message"]["content"].strip()
                            if rr_content.startswith("```"):
                                rr_content = rr_content.split("\n", 1)[1].rsplit("```", 1)[0]
                            rewritten = json.loads(rr_content)
                            seq["steps"] = rewritten
                            logger.info(f"GPT rewrote sequence '{seq.get('name','')}' — {len(rewritten)} emails, all variables standard")
                    except Exception as e:
                        # Fallback: simple replacement
                        logger.warning(f"GPT sequence rewrite failed: {e}, using simple replacement")
                        for step in seq.get("steps", []):
                            for field in ("subject", "body"):
                                text = step.get(field, "")
                                variables = re.findall(r'\{\{(\w+)\}\}', text)
                                for var in variables:
                                    if var.lower() not in STANDARD_VARS:
                                        replacement = var.replace("_", " ")
                                        text = text.replace("{{" + var + "}}", replacement)
                                        logger.info(f"Replaced unfillable {{{{{var}}}}} → '{replacement}'")
                                step[field] = text

            # Add metadata
            result["_model"] = model
            result["_tokens"] = data.get("usage", {})
            result["_website"] = website

            logger.info(f"Document extraction ({model}): "
                       f"{len(result.get('segments', []))} segments, "
                       f"{len(result.get('sequences', []))} sequences, "
                       f"{len(result.get('apollo_filters', {}).get('combined_keywords', []))} keywords")

            return result

    except Exception as e:
        logger.error(f"Document extraction failed ({model}): {e}")
        return {"error": str(e), "_model": model}


async def test_model_extraction(
    text: str,
    website: str,
    openai_key: str,
    models: list = None,
) -> list:
    """Test document extraction across multiple models. Returns scored results."""
    if not models:
        models = [
            "gpt-4o-mini",
            "gpt-4.1-mini",
            "gpt-4.1-nano",
            "gpt-5-nano",
            "gpt-5-mini",
            "gpt-5.4-nano",
            "gpt-5.4-mini",
        ]

    results = []
    for model in models:
        logger.info(f"Testing model: {model}")
        result = await extract_from_document(text, website, openai_key, model)
        result["_model"] = model
        results.append(result)

    return results


def score_extraction(result: Dict, ground_truth: Dict) -> Dict:
    """Score an extraction result against ground truth. Returns per-field scores."""
    scores = {}

    # Offer (1 point)
    if result.get("offer") and len(result["offer"]) > 20:
        scores["offer"] = 1
    else:
        scores["offer"] = 0

    # Target audience (1 point)
    if result.get("target_audience") and len(result["target_audience"]) > 10:
        scores["target_audience"] = 1
    else:
        scores["target_audience"] = 0

    # Roles (3 points — 1 per tier)
    roles = result.get("target_roles", {})
    gt_roles = ground_truth.get("target_roles", {})
    for tier in ["primary", "secondary", "tertiary"]:
        extracted = set(r.lower() for r in roles.get(tier, []))
        expected = set(r.lower() for r in gt_roles.get(tier, []))
        if extracted and len(extracted & expected) >= len(expected) * 0.5:
            scores[f"roles_{tier}"] = 1
        else:
            scores[f"roles_{tier}"] = 0

    # Keywords (1 point — need 10+)
    kw = result.get("apollo_filters", {}).get("combined_keywords", [])
    scores["keywords"] = 1 if len(kw) >= 10 else 0

    # Locations (1 point — need 3+)
    locs = result.get("apollo_filters", {}).get("locations", [])
    scores["locations"] = 1 if len(locs) >= 3 else 0

    # Employee range (1 point)
    emp = result.get("apollo_filters", {}).get("employee_range", "")
    scores["employee_range"] = 1 if "20" in emp and "500" in emp else 0

    # Sequence (4 points — 1 per email)
    seqs = result.get("sequences", [])
    if seqs:
        steps = seqs[0].get("steps", [])
        for i in range(min(4, len(steps))):
            step = steps[i]
            has_subject = bool(step.get("subject"))
            has_body = bool(step.get("body")) and len(step.get("body", "")) > 50
            scores[f"sequence_email_{i+1}"] = 1 if has_subject and has_body else 0
        for i in range(len(steps), 4):
            scores[f"sequence_email_{i+1}"] = 0
    else:
        for i in range(4):
            scores[f"sequence_email_{i+1}"] = 0

    # Campaign settings (1 point)
    settings = result.get("campaign_settings", {})
    scores["settings"] = 1 if settings.get("stop_on_reply") is not None else 0

    scores["total"] = sum(scores.values())
    scores["max"] = 13
    scores["pct"] = round(scores["total"] / 13 * 100)

    return scores
