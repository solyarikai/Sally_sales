"""
Diaspora Contact Gathering Service.

Finds C-level contacts from target countries working in employer countries.
Strategy: broad company search in employer country → get all contacts →
classify names by origin country using GPT-4o-mini → export matches.

Usage via API: POST /api/diaspora/gather
"""
import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ============================================================
# Corridor definitions: industry batches per employer country
# ============================================================
INDUSTRY_BATCHES = [
    {
        "label": "tech_it",
        "industries": ["IT Services and IT Consulting", "Software Development", "Technology, Information and Internet"],
        "keywords": ["software development", "IT consulting", "technology solutions", "digital transformation"],
    },
    {
        "label": "fintech_finance",
        "industries": ["Financial Services", "Banking", "Investment Banking"],
        "keywords": ["fintech platform", "payment processing", "digital banking", "financial technology"],
    },
    {
        "label": "ecommerce_retail",
        "industries": ["E-commerce", "Retail", "Consumer Services", "Internet Marketplace Platforms"],
        "keywords": ["online marketplace", "e-commerce platform", "digital commerce", "online retail"],
    },
    {
        "label": "construction_realestate",
        "industries": ["Construction", "Real Estate", "Architecture and Planning", "Civil Engineering"],
        "keywords": ["real estate development", "construction management", "property development", "building solutions"],
    },
    {
        "label": "trading_logistics",
        "industries": ["International Trade and Development", "Wholesale", "Transportation, Logistics, Supply Chain and Storage"],
        "keywords": ["import export", "international trading", "logistics solutions", "supply chain management"],
    },
    {
        "label": "consulting_professional",
        "industries": ["Business Consulting and Services", "Management Consulting", "Professional Services"],
        "keywords": ["management consulting", "business advisory", "strategy consulting", "professional services"],
    },
    {
        "label": "marketing_media",
        "industries": ["Marketing Services", "Advertising Services", "Online Audio and Video Media"],
        "keywords": ["digital marketing agency", "advertising platform", "media production", "content marketing"],
    },
    {
        "label": "healthcare_pharma",
        "industries": ["Hospitals and Health Care", "Pharmaceutical Manufacturing", "Medical Devices"],
        "keywords": ["healthcare technology", "medical devices", "pharmaceutical services", "health solutions"],
    },
    {
        "label": "education_hr",
        "industries": ["Education", "E-Learning Providers", "Human Resources Services"],
        "keywords": ["online education", "e-learning platform", "edtech", "talent management"],
    },
    {
        "label": "hospitality_tourism",
        "industries": ["Hospitality", "Travel Arrangements", "Food and Beverage Services"],
        "keywords": ["hotel management", "travel technology", "hospitality solutions", "restaurant chain"],
    },
    {
        "label": "gaming_entertainment",
        "industries": ["Computer Games", "Entertainment Providers", "Online Gaming"],
        "keywords": ["game development", "gaming platform", "entertainment technology", "esports"],
    },
    {
        "label": "energy_manufacturing",
        "industries": ["Oil and Gas", "Renewable Energy", "Industrial Machinery Manufacturing"],
        "keywords": ["energy technology", "renewable energy", "industrial automation", "manufacturing solutions"],
    },
]

# ============================================================
# Name classification: country-specific indicators
# ============================================================
COUNTRY_NAME_PROFILES = {
    "Pakistan": {
        "description": "Pakistani",
        "first_names": "Muhammad, Ahmed, Ali, Hassan, Hussain, Usman, Bilal, Faisal, Imran, Kashif, Asad, Tariq, Rashid, Shahid, Wasim, Naveed, Arshad, Shoaib, Iqbal, Raza, Kamran, Nadeem, Zahid, Waqas, Sajid, Khalid, Hamza, Abdullah, Zubair, Salman, Adnan, Rizwan, Farhan, Babar, Junaid, Sana, Hira, Maryam, Ayesha, Nadia, Rabia, Saima, Bushra, Amna, Sidra, Fatima, Aisha, Zara, Aamir, Amir, Asif, Atif, Fahad, Irfan, Javed, Mazhar, Mohsin, Naeem, Nasir, Omar, Pervez, Qasim, Rafiq, Saad, Sohail, Tahir, Tanveer, Umar, Waheed, Yasir, Zafar, Zeeshan, Zia, Hammad, Jawad, Noman, Owais, Saeed, Sarfraz, Shakeel, Sharjeel, Taimur, Uzair, Ahsan, Danish, Ghulam, Haroon, Mehmood, Mudassar, Murtaza, Muzammil, Nauman, Rehan, Safdar, Shabbir, Umair, Waleed, Azhar, Faraz, Furqan, Habib, Hafeez, Ijaz, Jamil, Liaqat, Mubashir, Mushtaq, Qadir, Rauf, Shafiq, Shaukat, Suleman, Tauqeer, Zaman, Zohaib",
        "last_names": "Khan, Malik, Butt, Chaudhry, Sheikh, Syed, Qureshi, Hussain, Rana, Rajput, Akhtar, Mirza, Gill, Bhatti, Aslam, Javed, Shah, Abbasi, Hashmi, Zaidi, Rizvi, Naqvi, Durrani, Khattak, Afridi, Yousafzai, Lodhi, Mughal, Niazi, Baloch, Mengal, Jamali, Bangash, Ahmed, Baig, Bukhari, Gondal, Gul, Hameed, Iqbal, Jaffri, Kazmi, Khawaja, Minhas, Memon, Paracha, Rathore, Sahi, Sethi, Tahir, Virk, Warraich, Zafar, Alvi, Ansari, Arain, Aziz, Cheema, Dar, Farooqui, Farooq, Ghaffar, Gondal, Gujjar, Haider, Iftikhar, Ilyas, Jadoon, Kiani, Latif, Manzoor, Marwat, Masood, Mukhtar, Nawaz, Rasheed, Rehman, Riaz, Saeed, Siddiqui, Soomro, Tanveer, Usmani, Wattoo, Younis, Yusuf, Abbasi, Asghar, Bajwa, Bilal, Chohan, Gardezi, Gilani, Hayat, Hussaini, Kakar, Khokar, Laghari, Leghari, Maneka, Mazari, Pasha, Pirzada, Sarwar, Sufi, Tareen, Tiwana, Turk, Awan, Chandio, Junejo, Kalhoro, Magsi, Mahesar, Palijo, Panhwar, Qazi, Rind, Samo, Shaikh, Talpur, Waseem",
        "disambiguation": "Distinguish from Indian names. Pakistani indicators: Khan, Malik, Butt, Chaudhry, Rana, Rajput, Akhtar, Gill, Bhatti, Abbasi, Hashmi, Khattak, Afridi, Cheema, Awan, Virk, Warraich, Gondal, Bajwa. Could be either: Ahmed, Ali, Hassan, Shah, Hussain, Syed, Qureshi. Indian-leaning: Sharma, Patel, Gupta, Reddy, Nair, Iyer, Rao. Arab names (not Pakistani): Al-, bin, ibn prefixes. Indonesian (not Pakistani): names ending in -to, -no, -wan (Javanese).",
    },
    "Philippines": {
        "description": "Filipino",
        "first_names": "Jose, Juan, Maria, Ana, Mark, John, Michael, Christian, Angelica, Jasmine, Jerome, Jericho, Rhea, Cherry, Jonel, Ariel, Rommel, Rodel, Reynaldo, Rodolfo, Edgardo, Ernesto, Rolando, Florante, Lorna, Marites, Maricel, Mylene, Rosemarie, Jocelyn",
        "last_names": "Santos, Reyes, Cruz, Bautista, Ocampo, Garcia, Mendoza, Torres, Villanueva, Ramos, Aquino, Castillo, Rivera, Flores, Lopez, Gonzales, Hernandez, Perez, Fernandez, Soriano, Pascual, Manalo, Tolentino, Salvador, Mercado, Aguilar, Navarro, Enriquez, Pangilinan, Dimaculangan, dela Cruz, de los Santos, San Juan, del Rosario, de la Peña, Magno, Dela Rosa, Macapagal, Magsaysay, Lacson, Mangubat, Dizon, Cunanan, Concepcion, Magbanua",
        "disambiguation": "Filipino names are Spanish-influenced but distinct from Latin American. Key Filipino indicators: double-barrel prefixes (dela, de los, del), very common clusters (Santos, Reyes, Cruz, Bautista, Ocampo), unique names like Pangilinan, Dimaculangan, Mangubat, Dizon, Cunanan. Latin American names like Rodriguez, Martinez, Gonzalez are also common in PH. Chinese-Filipino names (Tan, Chua, Go, Ong, Sy, Lim, Co) also count as Filipino.",
    },
    "South Africa": {
        "description": "South African",
        "first_names": "Pieter, Hendrik, Johannes, Gerrit, Willem, Jacobus, Francois, Christo, Petrus, Gert, Thabo, Sipho, Bongani, Nkosinathi, Themba, Sibusiso, Mandla, Lucky, Blessing, Precious, Nandi, Thandiwe, Palesa, Lerato, Kagiso, Mpho, Tshepo, Tumi, Buhle, Ayanda",
        "last_names": "Botha, du Plessis, van der Merwe, Pretorius, Joubert, Steyn, van der Walt, Venter, Swanepoel, Coetzee, Kruger, Erasmus, du Toit, Vermeulen, Cilliers, de Villiers, Engelbrecht, Fourie, le Roux, Malan, Visser, Viljoen, Louw, Marais, van Zyl, Nkosi, Dlamini, Ndlovu, Mkhize, Khumalo, Naidoo, Govender, Pillay, Chetty, Moodley, Cele, Ngcobo, Sithole, Mthembu, Radebe, Molefe, Moyo, Sibanda, Buthelezi, Mahlangu",
        "disambiguation": "South African names are highly distinctive across three groups: Afrikaans (Botha, du Plessis, Coetzee, van Zyl, Pretorius), Zulu/Xhosa (Nkosi, Dlamini, Ndlovu, Mkhize, Khumalo), and SA Indian (Naidoo, Govender, Pillay, Chetty, Moodley — these overlap with Indian-Indian but combined with SA education/company history = SA). English SA names (Henderson, Mitchell) overlap with UK/AU — score lower unless combined with other signals.",
    },
}


def _build_surname_set(profile: Dict[str, str]) -> set:
    """Build a lowercased set of known surnames for fast pre-filtering."""
    names = set()
    for field in ("first_names", "last_names"):
        for name in profile.get(field, "").split(","):
            name = name.strip().lower()
            if len(name) >= 3:  # Skip very short names that cause false positives
                names.add(name)
    return names


def pre_filter_by_surname(
    contacts: List[Dict[str, Any]],
    target_country: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Fast pre-filter: check if any name part matches known country surnames.

    Returns: (candidates, non_matches)
    Candidates go to GPT for scoring, non_matches are marked score=0.
    """
    profile = COUNTRY_NAME_PROFILES.get(target_country)
    if not profile:
        return contacts, []

    known_names = _build_surname_set(profile)
    candidates = []
    non_matches = []

    for contact in contacts:
        full_name = (
            contact.get("name", "")
            or f"{contact.get('first_name', '')} {contact.get('last_name', '')}"
        ).strip().lower()

        # Check if ANY name part matches known names
        name_parts = full_name.replace("-", " ").split()
        matched = any(part in known_names for part in name_parts)

        # Also check 2-word combinations (e.g., "du Plessis", "van der")
        if not matched and len(name_parts) >= 2:
            for i in range(len(name_parts) - 1):
                combo = f"{name_parts[i]} {name_parts[i+1]}"
                if combo in known_names:
                    matched = True
                    break

        if matched:
            candidates.append(contact)
        else:
            contact["_origin_score"] = 0
            contact["_origin_match"] = False
            non_matches.append(contact)

    return candidates, non_matches


def _classify_single_batch_sync(
    batch: List[Dict[str, Any]],
    system_prompt: str,
    api_key: str,
) -> List[Dict[str, Any]]:
    """Classify a single batch of names using GPT-4o-mini (SYNC version for thread pool).

    Runs in a thread to avoid event loop conflicts with Puppeteer subprocess.
    """
    import requests

    names_text = "\n".join(
        f"{i}. {c.get('name', '') or (c.get('first_name', '') + ' ' + c.get('last_name', '')).strip()}"
        for i, c in enumerate(batch)
    )

    for attempt in range(3):
        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Classify these {len(batch)} people:\n\n{names_text}"},
                    ],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                },
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            parsed = json.loads(content)
            scores = parsed if isinstance(parsed, list) else parsed.get("results", parsed.get("data", []))

            score_map = {}
            for item in scores:
                idx = item.get("i", item.get("idx", item.get("index")))
                score = item.get("s", item.get("score", 0))
                if idx is not None:
                    score_map[idx] = score

            results = []
            for i, contact in enumerate(batch):
                score = score_map.get(i, 0)
                contact["_origin_score"] = score
                contact["_origin_match"] = score >= 6
                results.append(contact)

            return results

        except Exception as e:
            err_msg = str(e) or repr(e)
            logger.warning(f"Classification batch attempt {attempt+1}: {err_msg}")
            if attempt < 2:
                import time
                time.sleep(2 ** attempt)

    # All retries failed — mark as unclassified
    for contact in batch:
        contact["_origin_score"] = -1
        contact["_origin_match"] = False
    return batch


async def classify_names_by_origin(
    contacts: List[Dict[str, Any]],
    target_country: str,
    batch_size: int = 40,
) -> List[Dict[str, Any]]:
    """Classify contacts by likely country of origin using GPT-4o-mini.

    Two-phase approach:
    1. Fast pre-filter by known surnames (reduces 30K+ to ~5K candidates)
    2. GPT-4o-mini scoring on candidates only

    Returns contacts with added fields: _origin_score (0-10), _origin_match (bool).
    Only contacts with score >= 6 are marked as matches.
    """
    profile = COUNTRY_NAME_PROFILES.get(target_country)
    if not profile:
        raise ValueError(f"No name profile for country: {target_country}")

    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    # Phase 1: Pre-filter by surname
    candidates, non_matches = pre_filter_by_surname(contacts, target_country)
    logger.info(
        f"Name pre-filter: {len(candidates)}/{len(contacts)} candidates "
        f"({len(candidates)/max(len(contacts),1)*100:.1f}%) for {target_country}"
    )

    if not candidates:
        return non_matches

    system_prompt = f"""You are a name origin classifier. For each person, rate 0-10 how likely they are originally from {target_country} based ONLY on their name.

{profile['description']} name indicators:
- Common first names: {profile['first_names']}
- Common last names: {profile['last_names']}

{profile['disambiguation']}

Scoring guide:
- 9-10: Very strong match (both first AND last name are distinctly {profile['description']})
- 7-8: Strong match (last name is clearly {profile['description']}, first name compatible)
- 5-6: Possible match (one name element matches, other is ambiguous)
- 3-4: Weak match (names could be from neighboring countries)
- 0-2: Not a match (names clearly from another country/culture)

Output ONLY a JSON array. Each element: {{"i": <index>, "s": <score>}}
Include ALL contacts. No explanation."""

    # Phase 2: GPT classification using sync requests in thread pool
    # This avoids event loop conflicts with Puppeteer subprocess
    from concurrent.futures import ThreadPoolExecutor
    import functools

    results: List[Dict[str, Any]] = []
    batches = [candidates[i:i + batch_size] for i in range(0, len(candidates), batch_size)]

    if batches:
        try:
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [
                    loop.run_in_executor(
                        executor,
                        functools.partial(
                            _classify_single_batch_sync, batch, system_prompt, api_key
                        ),
                    )
                    for batch in batches
                ]
                batch_results = await asyncio.gather(*futures, return_exceptions=True)

            for i, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Classification batch {i} failed: {result}")
                    for contact in batches[i]:
                        contact["_origin_score"] = -1
                        contact["_origin_match"] = False
                        results.append(contact)
                else:
                    results.extend(result)

        except Exception as e:
            logger.error(f"GPT classification failed: {e}. Using surname-only matching.")
            for contact in candidates:
                contact["_origin_score"] = 7  # surname match fallback
                contact["_origin_match"] = True
                results.append(contact)
    else:
        results = []

    matched = sum(1 for c in results if c.get("_origin_match"))
    logger.info(
        f"Name classification: {matched}/{len(results)} GPT-classified matched {target_country}, "
        f"total: {matched}/{len(results) + len(non_matches)}"
    )
    return results + non_matches


def build_icp_text(
    employer_countries: List[str],
    industry_batch: Dict[str, Any],
    company_sizes: str = "11-50, 51-200, 201-500, 501-1000",
) -> str:
    """Build ICP text for Clay company search."""
    countries_str = ", ".join(employer_countries)
    industries_str = ", ".join(industry_batch["industries"])
    keywords_str = ", ".join(industry_batch["keywords"])

    return (
        f"Companies in {countries_str} in {industries_str} "
        f"with {company_sizes} employees. "
        f"Focus on companies with keywords: {keywords_str}. "
        f"Exclude recruitment agencies, staffing firms, and consulting-only firms."
    )


# ============================================================
# Corridor definitions
# ============================================================
CORRIDORS = {
    "uae-pakistan": {
        "employer_countries": ["United Arab Emirates"],
        "contractor_country": "Pakistan",
        "label": "UAE → Pakistan",
        "sheet_name": "UAE-Pakistan",
    },
    "australia-philippines": {
        "employer_countries": ["Australia"],
        "contractor_country": "Philippines",
        "label": "Australia → Philippines",
        "sheet_name": "AU-Philippines",
    },
    "arabic-south-africa": {
        "employer_countries": [
            "United Arab Emirates", "Saudi Arabia", "Qatar",
            "Bahrain", "Kuwait", "Oman",
        ],
        "contractor_country": "South Africa",
        "label": "Arabic Countries → South Africa",
        "sheet_name": "Arabic-SouthAfrica",
    },
}


async def run_diaspora_pipeline(
    corridor_key: str,
    project_id: int,
    target_count: int = 1000,
    on_progress: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Run the full diaspora gathering pipeline for a corridor.

    1. Iterate through industry batches
    2. For each batch: find companies → find contacts → classify names
    3. Accumulate matches until target_count reached
    4. Export all to Google Sheet

    Returns: {matched: int, total_scanned: int, sheet_url: str, contacts: [...]}
    """
    from app.services.clay_service import clay_service

    corridor = CORRIDORS.get(corridor_key)
    if not corridor:
        raise ValueError(f"Unknown corridor: {corridor_key}. Options: {list(CORRIDORS.keys())}")

    async def _emit(msg: str):
        if on_progress:
            try:
                await on_progress(msg)
            except Exception:
                pass

    employer_countries = corridor["employer_countries"]
    contractor_country = corridor["contractor_country"]
    label = corridor["label"]

    all_matched_contacts = []
    all_scanned = 0
    all_companies_found = 0
    iteration = 0
    failed_batches = 0
    skip_batches = 0

    # Try to resume from interim results
    interim_path = Path("/tmp") / f"diaspora_{corridor_key}_interim.json"
    if interim_path.exists():
        try:
            interim_data = json.loads(interim_path.read_text())
            all_matched_contacts = interim_data.get("contacts", [])
            all_scanned = interim_data.get("scanned", 0)
            all_companies_found = interim_data.get("companies", 0)
            skip_batches = interim_data.get("iteration", 0)
            logger.info(
                f"Resuming {corridor_key}: {len(all_matched_contacts)} contacts from {skip_batches} iterations"
            )
        except Exception as e:
            logger.warning(f"Failed to load interim results: {e}")

    await _emit(f"Starting diaspora pipeline: {label}")
    await _emit(f"Target: {target_count} {contractor_country}-origin decision-makers in {', '.join(employer_countries)}")
    if all_matched_contacts:
        await _emit(f"Resuming with {len(all_matched_contacts)} previously matched contacts")

    if skip_batches > 0:
        await _emit(f"Resuming from iteration {skip_batches+1} with {len(all_matched_contacts)} contacts already matched")

    # COMPANY→PEOPLE→NAME approach with larger batches for scale
    for batch_config in INDUSTRY_BATCHES:
        if len(all_matched_contacts) >= target_count:
            break

        iteration += 1
        batch_label = batch_config["label"]

        if iteration <= skip_batches:
            await _emit(f"Skipping iteration {iteration}/{len(INDUSTRY_BATCHES)}: {batch_label} (already done)")
            continue

        await _emit(f"\n--- Iteration {iteration}/{len(INDUSTRY_BATCHES)}: {batch_label} ---")
        await _emit(f"Progress: {len(all_matched_contacts)}/{target_count} matched contacts")

        # Phase 1: Find companies for this industry
        icp_text = build_icp_text(employer_countries, batch_config)
        await _emit(f"Phase 1: Finding {batch_label} companies...")

        try:
            tam_result = await clay_service.run_tam_export(
                icp_text=icp_text,
                project_id=project_id,
                on_progress=on_progress,
            )
        except Exception as e:
            logger.error(f"TAM export failed for {batch_label}: {e}")
            await _emit(f"Company search failed: {e}. Skipping.")
            failed_batches += 1
            continue

        companies = tam_result.get("companies", [])
        if not companies:
            await _emit(f"No companies found. Skipping.")
            continue

        # Extract and deduplicate domains — use ALL of them
        all_domains = list({
            (c.get("Domain") or c.get("domain") or "").strip().lower().replace("www.", "")
            for c in companies
            if (c.get("Domain") or c.get("domain") or "").strip()
            and "." in (c.get("Domain") or c.get("domain") or "").strip()
        })

        await _emit(f"Found {len(all_domains)} companies with domains")
        all_companies_found += len(all_domains)

        # Phase 2: Search contacts in sub-batches of 500 domains
        # Clay people search handles 200 domains per UI batch internally
        DOMAIN_SUB_BATCH = 500
        all_people = []
        for sub_start in range(0, len(all_domains), DOMAIN_SUB_BATCH):
            sub_domains = all_domains[sub_start:sub_start + DOMAIN_SUB_BATCH]
            sub_label = f"{sub_start//DOMAIN_SUB_BATCH + 1}/{(len(all_domains) + DOMAIN_SUB_BATCH - 1)//DOMAIN_SUB_BATCH}"
            await _emit(f"Phase 2: People search sub-batch {sub_label} ({len(sub_domains)} companies)...")

            try:
                people_result = await clay_service.run_people_search(
                    domains=sub_domains,
                    project_id=project_id,
                    on_progress=on_progress,
                )
                people = people_result.get("people", [])
                all_people.extend(people)
                await _emit(f"Sub-batch {sub_label}: {len(people)} contacts (total: {len(all_people)})")
            except Exception as e:
                logger.error(f"People search sub-batch {sub_label} failed: {e}")
                await _emit(f"Sub-batch {sub_label} failed: {e}")
                failed_batches += 1

        if not all_people:
            await _emit(f"No contacts found. Skipping.")
            continue

        # Filter to decision-makers
        clevel_keywords = [
            "ceo", "cto", "cfo", "coo", "cmo", "cpo", "cio", "cro",
            "chief", "founder", "co-founder", "cofounder", "owner",
            "managing director", "general manager", "president",
            "vp", "vice president", "director", "head of", "head",
            "partner", "principal", "country manager", "regional manager",
        ]
        decision_makers = [
            p for p in all_people
            if (p.get("title") or "") and any(kw in (p.get("title") or "").lower() for kw in clevel_keywords)
        ]

        if not decision_makers:
            await _emit(f"Found {len(all_people)} contacts, 0 decision-makers. Skipping.")
            continue

        await _emit(f"Found {len(all_people)} contacts → {len(decision_makers)} decision-makers")
        all_scanned += len(decision_makers)
        await _emit(f"Phase 3: Classifying {len(decision_makers)} names...")

        # Phase 3: Classify decision-maker names by origin
        try:
            classified = await classify_names_by_origin(
                decision_makers, contractor_country,
            )
        except Exception as e:
            logger.error(f"Classification failed for {batch_label}: {e}")
            await _emit(f"Classification failed: {e}. Skipping batch.")
            failed_batches += 1
            continue

        matched = [c for c in classified if c.get("_origin_match")]
        await _emit(
            f"Classification: {len(matched)}/{len(classified)} matched {contractor_country} "
            f"(hit rate: {len(matched)/max(len(classified),1)*100:.1f}%)"
        )

        # Deduplicate against already matched (by name + company or linkedin_url)
        existing_keys = set()
        for c in all_matched_contacts:
            key = c.get("linkedin_url") or f"{c.get('name', '')}|{c.get('company', '')}"
            existing_keys.add(key.lower())

        new_matches = []
        for c in matched:
            key = c.get("linkedin_url") or f"{c.get('name', '')}|{c.get('company', '')}"
            if key.lower() not in existing_keys:
                c["_industry_batch"] = batch_label
                c["_corridor"] = corridor_key
                new_matches.append(c)
                existing_keys.add(key.lower())

        all_matched_contacts.extend(new_matches)
        await _emit(
            f"New unique matches: {len(new_matches)}. "
            f"Total: {len(all_matched_contacts)}/{target_count}"
        )

        # Save intermediate results to disk after each iteration
        try:
            interim_path = Path("/tmp") / f"diaspora_{corridor_key}_interim.json"
            interim_data = {
                "corridor": corridor_key,
                "matched_count": len(all_matched_contacts),
                "scanned": all_scanned,
                "companies": all_companies_found,
                "iteration": iteration,
                "contacts": all_matched_contacts,
                "updated_at": datetime.now().isoformat(),
            }
            interim_path.write_text(json.dumps(interim_data, default=str))
            logger.info(f"Saved {len(all_matched_contacts)} interim results to {interim_path}")
        except Exception as e:
            logger.warning(f"Failed to save interim results: {e}")

    # Phase 4: Export to Google Sheet
    await _emit(f"\nExporting {len(all_matched_contacts)} matched contacts to Google Sheet...")

    sheet_url = None
    try:
        sheet_url = await export_diaspora_to_sheet(
            all_matched_contacts,
            corridor,
            stats={
                "total_scanned": all_scanned,
                "total_companies": all_companies_found,
                "total_matched": len(all_matched_contacts),
                "target": target_count,
                "iterations": iteration,
                "failed_batches": failed_batches,
            },
        )
        await _emit(f"Google Sheet: {sheet_url}")
    except Exception as e:
        logger.error(f"Sheet export failed: {e}")
        await _emit(f"Sheet export failed: {e}")

    summary = {
        "corridor": corridor_key,
        "label": label,
        "matched": len(all_matched_contacts),
        "total_scanned": all_scanned,
        "total_companies": all_companies_found,
        "target": target_count,
        "iterations": iteration,
        "failed_batches": failed_batches,
        "hit_rate": len(all_matched_contacts) / max(all_scanned, 1) * 100,
        "sheet_url": sheet_url,
        "contacts": all_matched_contacts,
    }

    await _emit(
        f"\n=== {label} COMPLETE ===\n"
        f"Matched: {summary['matched']}/{target_count}\n"
        f"Scanned: {all_scanned} contacts at {all_companies_found} companies\n"
        f"Hit rate: {summary['hit_rate']:.1f}%\n"
        f"Iterations: {iteration}, Failed: {failed_batches}\n"
        f"Sheet: {sheet_url or 'N/A'}"
    )

    return summary


async def export_diaspora_to_sheet(
    contacts: List[Dict[str, Any]],
    corridor: Dict[str, Any],
    stats: Dict[str, Any],
    existing_sheet_id: Optional[str] = None,
) -> str:
    """Export diaspora contacts to Google Sheet. Returns sheet URL."""
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    creds_file = "/app/google-credentials.json"
    if not os.path.exists(creds_file):
        creds_file = str(Path(__file__).parent.parent.parent.parent / "google-credentials.json")
        if not os.path.exists(creds_file):
            raise FileNotFoundError("Google credentials not found")

    shared_drive_id = os.environ.get("SHARED_DRIVE_ID", "0AEvTjlJFlWnZUk9PVA")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
    drive_service = build("drive", "v3", credentials=creds)
    sheets_service = build("sheets", "v4", credentials=creds)

    # Create or reuse sheet
    if existing_sheet_id:
        spreadsheet_id = existing_sheet_id
    else:
        title = f"Diaspora Contacts — {corridor['label']} — {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        file_metadata = {
            "name": title,
            "mimeType": "application/vnd.google-apps.spreadsheet",
            "parents": [shared_drive_id],
        }
        sheet_file = drive_service.files().create(
            body=file_metadata, fields="id", supportsAllDrives=True,
        ).execute()
        spreadsheet_id = sheet_file["id"]

        # Make publicly readable
        drive_service.permissions().create(
            fileId=spreadsheet_id,
            body={"type": "anyone", "role": "reader"},
            supportsAllDrives=True,
        ).execute()

    sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"

    # Rename Sheet1 to corridor name
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"updateSheetProperties": {
            "properties": {"sheetId": 0, "title": corridor["sheet_name"]}, "fields": "title",
        }}]},
    ).execute()

    # Write contact data
    columns = [
        "Name", "First Name", "Last Name", "Email", "Title", "Company",
        "Domain", "Location", "LinkedIn URL", "Phone",
        "Origin Score", "Industry Batch", "Corridor",
    ]
    field_map = {
        "Name": "name", "First Name": "first_name", "Last Name": "last_name",
        "Email": "email", "Title": "title", "Company": "company",
        "Domain": "company_domain", "Location": "location",
        "LinkedIn URL": "linkedin_url", "Phone": "phone",
        "Origin Score": "_origin_score", "Industry Batch": "_industry_batch",
        "Corridor": "_corridor",
    }

    rows = [columns]
    for contact in contacts:
        row = []
        for col in columns:
            val = contact.get(field_map[col], "")
            if val is None:
                val = ""
            row.append(str(val)[:500])
        rows.append(row)

    # Write data
    for i in range(0, len(rows), 5000):
        batch = rows[i:i + 5000]
        start_row = i + 1 if i > 0 else 1
        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{corridor['sheet_name']}!A{start_row}",
            valueInputOption="RAW",
            body={"values": batch},
        ).execute()

    # Add stats tab
    try:
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": "Pipeline Stats"}}}]},
        ).execute()

        stats_rows = [["Metric", "Value"]]
        for k, v in stats.items():
            stats_rows.append([str(k), str(v)])
        stats_rows.append(["generated_at", datetime.now().isoformat()])

        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="Pipeline Stats!A1",
            valueInputOption="RAW",
            body={"values": stats_rows},
        ).execute()
    except Exception as e:
        logger.warning(f"Failed to create stats tab: {e}")

    logger.info(f"Diaspora export: {len(contacts)} contacts to {sheet_url}")
    return sheet_url


async def run_all_corridors(
    project_id: int,
    target_count: int = 1000,
    on_progress: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Run diaspora pipeline for all three corridors sequentially."""
    results = {}
    for corridor_key in CORRIDORS:
        try:
            result = await run_diaspora_pipeline(
                corridor_key=corridor_key,
                project_id=project_id,
                target_count=target_count,
                on_progress=on_progress,
            )
            results[corridor_key] = result
        except Exception as e:
            logger.error(f"Corridor {corridor_key} failed: {e}")
            results[corridor_key] = {"error": str(e)}

    return results
