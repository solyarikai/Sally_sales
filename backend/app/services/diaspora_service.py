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
        # NOTE: first_names excludes common Arabic names (Muhammad, Ahmed, Ali, Hassan, Khalid, etc.)
        # to avoid false positives in Middle East. GPT handles ambiguous names.
        "first_names": "Imran, Kashif, Naveed, Arshad, Shoaib, Waqas, Rizwan, Babar, Junaid, Hira, Saima, Bushra, Sidra, Aamir, Asif, Atif, Irfan, Javed, Mazhar, Pervez, Sohail, Tanveer, Waheed, Zeeshan, Zia, Sarfraz, Shakeel, Sharjeel, Uzair, Ahsan, Danish, Ghulam, Mehmood, Mudassar, Muzammil, Nauman, Rehan, Safdar, Shabbir, Azhar, Faraz, Furqan, Hafeez, Ijaz, Liaqat, Mubashir, Mushtaq, Rauf, Shafiq, Shaukat, Suleman, Tauqeer, Zohaib",
        "last_names": "Khan, Malik, Butt, Chaudhry, Qureshi, Rana, Rajput, Akhtar, Mirza, Gill, Bhatti, Aslam, Javed, Abbasi, Hashmi, Zaidi, Rizvi, Naqvi, Durrani, Khattak, Afridi, Yousafzai, Lodhi, Mughal, Niazi, Baloch, Mengal, Jamali, Bangash, Baig, Bukhari, Gondal, Khawaja, Minhas, Memon, Paracha, Rathore, Sahi, Sethi, Virk, Warraich, Alvi, Arain, Cheema, Dar, Farooqui, Gujjar, Iftikhar, Jadoon, Kiani, Marwat, Nawaz, Rehman, Riaz, Siddiqui, Soomro, Usmani, Wattoo, Younis, Bajwa, Chohan, Gardezi, Gilani, Kakar, Khokar, Laghari, Leghari, Mazari, Pasha, Pirzada, Tareen, Tiwana, Awan, Chandio, Junejo, Kalhoro, Magsi, Mahesar, Palijo, Panhwar, Rind, Samo, Talpur",
        "disambiguation": "CRITICAL in UAE: Most Arabic first names (Muhammad, Ahmed, Ali, Hassan, Bilal, Faisal, Khalid, etc.) are shared across ALL Muslim countries. Do NOT score these high unless combined with a distinctively Pakistani last name. Distinctively Pakistani indicators: Khan, Malik, Butt, Chaudhry, Rana, Rajput, Akhtar, Gill, Bhatti, Cheema, Awan, Virk, Warraich, Gondal, Bajwa, Afridi, Khattak. Indian-leaning: Sharma, Patel, Gupta, Reddy, Nair, Iyer, Rao. Arab (NOT Pakistani): Al-prefix surnames, bin/ibn. Indonesian: -to, -no endings.",
    },
    "Philippines": {
        "description": "Filipino",
        "first_names": "Jose, Juan, Maria, Ana, Mark, John, Michael, Christian, Angelica, Jasmine, Jerome, Jericho, Rhea, Cherry, Jonel, Ariel, Rommel, Rodel, Reynaldo, Rodolfo, Edgardo, Ernesto, Rolando, Florante, Lorna, Marites, Maricel, Mylene, Rosemarie, Jocelyn, Rogelio, Catalino, Diosdado, Renato, Virgilio, Danilo, Wilfredo, Crisanto, Teresita, Corazon, Imelda, Lourdes, Erlinda",
        "last_names": "Santos, Reyes, Cruz, Bautista, Ocampo, Garcia, Mendoza, Torres, Villanueva, Ramos, Aquino, Castillo, Rivera, Flores, Lopez, Gonzales, Hernandez, Perez, Fernandez, Soriano, Pascual, Manalo, Tolentino, Salvador, Mercado, Aguilar, Navarro, Enriquez, Pangilinan, Dimaculangan, dela Cruz, de los Santos, San Juan, del Rosario, de la Peña, Magno, Dela Rosa, Macapagal, Magsaysay, Lacson, Mangubat, Dizon, Cunanan, Concepcion, Magbanua, Tan, Chua, Go, Ong, Sy, Lim, Co, Ang, Uy, Tiu, Yap, Teo, Abad, Araneta, Ayala, Cojuangco, Roxas, Laurel, Zobel, Razon, Gokongwei, Lucio, Zobel, Alcantara, Villar, Uytengsu, Montinola, Ortigas, Tuason, Madrigal",
        "disambiguation": "Filipino names are Spanish-influenced but distinct from Latin American. Key Filipino indicators: double-barrel prefixes (dela, de los, del), very common clusters (Santos, Reyes, Cruz, Bautista, Ocampo), unique names like Pangilinan, Dimaculangan, Mangubat, Dizon, Cunanan. Latin American names like Rodriguez, Martinez, Gonzalez are also common in PH. Chinese-Filipino names (Tan, Chua, Go, Ong, Sy, Lim, Co) also count as Filipino. Key difference from other Spanish-name countries: Filipino culture uses BOTH Spanish AND Chinese surnames. Do NOT confuse with Latin American names — score based on the combination of first+last.",
    },
    "South Africa": {
        "description": "South African",
        "first_names": "Pieter, Hendrik, Johannes, Gerrit, Willem, Jacobus, Francois, Christo, Petrus, Gert, Thabo, Sipho, Bongani, Nkosinathi, Themba, Sibusiso, Mandla, Lucky, Blessing, Precious, Nandi, Thandiwe, Palesa, Lerato, Kagiso, Mpho, Tshepo, Tumi, Buhle, Ayanda, Siyabonga, Lungelo, Nhlanhla, Sizwe, Vusi, Zandile, Nomvula, Nomsa, Zanele, Lindiwe, Nomzamo, Nonhlanhla, Sbongile, Thulani, Muzi, Frik, Danie, Kobus, Jannie, Bettie, Elna",
        "last_names": "Botha, du Plessis, van der Merwe, Pretorius, Joubert, Steyn, van der Walt, Venter, Swanepoel, Coetzee, Kruger, Erasmus, du Toit, Vermeulen, Cilliers, de Villiers, Engelbrecht, Fourie, le Roux, Malan, Visser, Viljoen, Louw, Marais, van Zyl, Nkosi, Dlamini, Ndlovu, Mkhize, Khumalo, Naidoo, Govender, Pillay, Chetty, Moodley, Cele, Ngcobo, Sithole, Mthembu, Radebe, Molefe, Moyo, Sibanda, Buthelezi, Mahlangu, Naicker, Reddy, Maharaj, Singh, Moosa, Ebrahim, Cassim, Joosub, Sobukwe, Motlanthe, Ramaphosa, Zuma, Mbeki, Sisulu, Slovo, Tambo, Hani, Oppenheimer, Rupert, Wiese, Memory, Motsepe, Sobrato, Sobukwe, Barnard, Roux, Bekker, Rossouw, Jansen, Bezuidenhout, Nel, Groenewald, Prinsloo, Lombard, Potgieter, Jacobs, Henning, Mostert, Brink, Naude, Basson, Dippenaar, Gouws, Theron, van Niekerk, van Rensburg, van Wyk",
        "disambiguation": "South African names are highly distinctive across three groups: Afrikaans (Botha, du Plessis, Coetzee, van Zyl, Pretorius, Bezuidenhout, Groenewald), Zulu/Xhosa (Nkosi, Dlamini, Ndlovu, Mkhize, Khumalo, Ngcobo, Cele), and SA Indian (Naidoo, Govender, Pillay, Chetty, Moodley, Naicker, Maharaj). Key SA business names: Motsepe, Oppenheimer, Rupert, Wiese, Bekker, Joosub. 'van' prefix + Afrikaans surname = very strong SA signal. English SA names (Henderson, Mitchell) overlap with UK/AU — score lower unless combined with other signals. In Arabic countries context: SA names are VERY distinctive and should score high.",
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

# University batches per target country — used for people-first search
# Each batch is a list of schools searched together
UNIVERSITY_BATCHES = {
    "Pakistan": [
        {
            "label": "pk_top_business",
            "schools": [
                "LUMS", "IBA Karachi", "NUST",
                "Lahore University of Management Sciences",
                "Institute of Business Administration",
            ],
        },
        {
            "label": "pk_engineering",
            "schools": [
                "NED University", "GIK Institute", "FAST-NUCES",
                "COMSATS University", "UET Lahore",
                "University of Engineering and Technology",
            ],
        },
        {
            "label": "pk_general",
            "schools": [
                "University of Punjab", "Quaid-i-Azam University",
                "Aga Khan University", "University of Karachi",
                "PIEAS", "Bahria University",
            ],
        },
        {
            "label": "pk_other",
            "schools": [
                "University of Peshawar", "Habib University",
                "Ghulam Ishaq Khan Institute", "Air University",
                "National Defence University Pakistan",
                "Sukkur IBA University",
            ],
        },
    ],
    "Philippines": [
        {
            "label": "ph_top",
            "schools": [
                "University of the Philippines",
                "Ateneo de Manila University",
                "De La Salle University",
                "University of Santo Tomas",
                "Asian Institute of Management",
            ],
        },
        {
            "label": "ph_other",
            "schools": [
                "Mapua University", "Adamson University",
                "Far Eastern University", "University of San Carlos",
                "Silliman University", "Xavier University",
            ],
        },
        {
            "label": "ph_more",
            "schools": [
                "Polytechnic University of the Philippines",
                "University of the East",
                "National University Philippines",
                "Lyceum of the Philippines University",
                "Centro Escolar University",
                "San Beda University",
            ],
        },
        {
            "label": "ph_tech",
            "schools": [
                "Technological University of the Philippines",
                "Mindanao State University",
                "University of San Agustin",
                "Pamantasan ng Lungsod ng Maynila",
                "Central Philippine University",
            ],
        },
    ],
    "South Africa": [
        {
            "label": "za_top",
            "schools": [
                "University of Cape Town",
                "University of the Witwatersrand",
                "Stellenbosch University",
                "University of Pretoria",
                "University of Johannesburg",
            ],
        },
        {
            "label": "za_other",
            "schools": [
                "University of KwaZulu-Natal",
                "Rhodes University",
                "University of the Free State",
                "North-West University",
                "Nelson Mandela University",
            ],
        },
        {
            "label": "za_more",
            "schools": [
                "University of South Africa",
                "Durban University of Technology",
                "Cape Peninsula University of Technology",
                "Tshwane University of Technology",
                "Walter Sisulu University",
            ],
        },
    ],
}


async def run_diaspora_pipeline(
    corridor_key: str,
    project_id: int,
    target_count: int = 1000,
    on_progress: Optional[Callable] = None,
    mode: str = "full",  # "full" = industry + university, "university" = university-only
    existing_sheet_id: Optional[str] = None,  # Append to existing sheet
) -> Dict[str, Any]:
    """Run the full diaspora gathering pipeline for a corridor.

    1. Iterate through industry batches (skipped in university mode)
    2. For each batch: find companies → find contacts → classify names
    3. University-based search (always runs if target not reached)
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

    # Create or reuse Google Sheet for incremental updates
    _sheet_id = existing_sheet_id
    if not _sheet_id:
        try:
            sheets_service, drive_service = _get_sheets_service()
            shared_drive_id = os.environ.get("SHARED_DRIVE_ID", "0AEvTjlJFlWnZUk9PVA")
            title = f"Diaspora Contacts — {corridor['label']} — {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            file_metadata = {
                "name": title,
                "mimeType": "application/vnd.google-apps.spreadsheet",
                "parents": [shared_drive_id],
            }
            sheet_file = drive_service.files().create(
                body=file_metadata, fields="id", supportsAllDrives=True,
            ).execute()
            _sheet_id = sheet_file["id"]
            drive_service.permissions().create(
                fileId=_sheet_id,
                body={"type": "anyone", "role": "reader"},
                supportsAllDrives=True,
            ).execute()
            # Rename Sheet1
            sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=_sheet_id,
                body={"requests": [{"updateSheetProperties": {
                    "properties": {"sheetId": 0, "title": corridor["sheet_name"]}, "fields": "title",
                }}]},
            ).execute()
            sheet_url_early = f"https://docs.google.com/spreadsheets/d/{_sheet_id}"
            await _emit(f"Google Sheet created: {sheet_url_early}")
        except Exception as e:
            logger.warning(f"Failed to create sheet early: {e}")
            _sheet_id = None

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

    await _emit(f"Starting diaspora pipeline: {label} (mode={mode})")
    await _emit(f"Target: {target_count} {contractor_country}-origin decision-makers in {', '.join(employer_countries)}")
    if all_matched_contacts:
        await _emit(f"Resuming with {len(all_matched_contacts)} previously matched contacts")

    if skip_batches > 0:
        await _emit(f"Resuming from iteration {skip_batches+1} with {len(all_matched_contacts)} contacts already matched")

    # Skip industry batches in university mode
    if mode == "university":
        await _emit("University-only mode — skipping industry searches")
    else:
        pass  # Run industry batches below

    # COMPANY→PEOPLE→NAME approach with larger batches for scale
    for batch_config in (INDUSTRY_BATCHES if mode != "university" else []):
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

        # Cap at 1000 domains (Clay splits into 200-domain batches internally)
        import random
        if len(all_domains) > 1000:
            random.shuffle(all_domains)
            domains = all_domains[:1000]
            await _emit(f"Sampling 1000 of {len(all_domains)} companies for people search...")
        else:
            domains = all_domains

        # Phase 2: Find contacts
        await _emit(f"Phase 2: Finding contacts at {len(domains)} companies...")
        try:
            people_result = await clay_service.run_people_search(
                domains=domains,
                project_id=project_id,
                on_progress=on_progress,
            )
        except Exception as e:
            logger.error(f"People search failed: {e}")
            await _emit(f"People search failed: {e}. Skipping.")
            failed_batches += 1
            continue

        all_people = people_result.get("people", [])
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
        industries_str = ", ".join(batch_config.get("industries", []))
        for c in matched:
            key = c.get("linkedin_url") or f"{c.get('name', '')}|{c.get('company', '')}"
            if key.lower() not in existing_keys:
                c["_search_method"] = f"industry_search: {batch_label}"
                c["_search_details"] = (
                    f"Company-first: {industries_str} in {', '.join(employer_countries)} → "
                    f"get contacts → filter C-level → classify {contractor_country} names via GPT"
                )
                c["_corridor"] = corridor_key
                new_matches.append(c)
                existing_keys.add(key.lower())

        all_matched_contacts.extend(new_matches)
        await _emit(
            f"New unique matches: {len(new_matches)}. "
            f"Total: {len(all_matched_contacts)}/{target_count}"
        )

        # Incremental export to Google Sheet
        if new_matches and _sheet_id:
            try:
                await incremental_sheet_export(
                    all_matched_contacts, corridor, _sheet_id,
                    approach_log={
                        "timestamp": datetime.now().isoformat(),
                        "approach": f"Industry Search: {batch_label}",
                        "details": f"Companies in {industries_str} in {', '.join(employer_countries)} → contacts → C-level filter → name classification",
                        "contacts_found": len(all_people),
                        "decision_makers": len(decision_makers),
                        "matched": len(new_matches),
                        "hit_rate": f"{len(matched)/max(len(classified),1)*100:.1f}%",
                        "total_so_far": len(all_matched_contacts),
                    },
                )
                await _emit(f"Sheet updated: {len(all_matched_contacts)} contacts")
            except Exception as e:
                logger.warning(f"Incremental export failed: {e}")

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

    # Phase 3b: University-based people search (people-first, no company step)
    uni_batches = UNIVERSITY_BATCHES.get(contractor_country, [])
    if uni_batches and len(all_matched_contacts) < target_count:
        await _emit(f"\n=== University-based search: {len(uni_batches)} batches ===")

        for uni_batch in uni_batches:
            if len(all_matched_contacts) >= target_count:
                break

            uni_label = uni_batch["label"]
            schools = uni_batch["schools"]
            iteration += 1

            await _emit(f"\n--- University batch {uni_label} ---")
            await _emit(f"Schools: {', '.join(schools)}")
            await _emit(f"Progress: {len(all_matched_contacts)}/{target_count}")

            try:
                people_result = await clay_service.run_people_search(
                    domains=None,  # No company domains — filter-based search
                    project_id=project_id,
                    on_progress=on_progress,
                    use_titles=True,  # Decision-makers only
                    countries=employer_countries,
                    schools=schools,
                )
            except Exception as e:
                logger.error(f"University search failed for {uni_label}: {e}")
                await _emit(f"University search failed: {e}. Skipping.")
                failed_batches += 1
                continue

            all_people = people_result.get("people", [])
            if not all_people:
                await _emit(f"No contacts found for {uni_label}. Skipping.")
                continue

            # University search already filters titles via --titles flag,
            # but let's also apply our own filter for consistency
            clevel_keywords = [
                "ceo", "cto", "cfo", "coo", "cmo", "cpo", "cio", "cro",
                "chief", "founder", "co-founder", "cofounder", "owner",
                "managing director", "general manager", "president",
                "vp", "vice president", "director", "head of", "head",
                "partner", "principal", "country manager", "regional manager",
            ]
            decision_makers = [
                p for p in all_people
                if (p.get("title") or "") and any(
                    kw in (p.get("title") or "").lower() for kw in clevel_keywords
                )
            ]

            if not decision_makers:
                await _emit(f"Found {len(all_people)} contacts, 0 decision-makers. Skipping.")
                continue

            await _emit(f"Found {len(all_people)} contacts → {len(decision_makers)} decision-makers")
            all_scanned += len(decision_makers)

            # For university-based search, people who studied at target country's
            # universities are very likely from that country — score them higher
            # but still run classification for quality
            await _emit(f"Classifying {len(decision_makers)} names (university signal = strong)...")

            try:
                classified = await classify_names_by_origin(
                    decision_makers, contractor_country,
                )
            except Exception as e:
                logger.error(f"Classification failed for {uni_label}: {e}")
                # University signal is strong enough — accept all as matches on failure
                for p in decision_makers:
                    p["_origin_score"] = 8
                    p["_origin_match"] = True
                classified = decision_makers

            matched = [c for c in classified if c.get("_origin_match")]
            await _emit(
                f"Classification: {len(matched)}/{len(classified)} matched {contractor_country}"
            )

            # Deduplicate
            existing_keys = set()
            for c in all_matched_contacts:
                key = c.get("linkedin_url") or f"{c.get('name', '')}|{c.get('company', '')}"
                existing_keys.add(key.lower())

            new_matches = []
            schools_str = ", ".join(schools)
            for c in matched:
                key = c.get("linkedin_url") or f"{c.get('name', '')}|{c.get('company', '')}"
                if key.lower() not in existing_keys:
                    c["_search_method"] = f"university_search: {uni_label}"
                    c["_search_details"] = (
                        f"University-first: Schools={schools_str}, "
                        f"Location={', '.join(employer_countries)}, "
                        f"Titles=C-level/VP/Director → classify {contractor_country} names via GPT"
                    )
                    c["_corridor"] = corridor_key
                    new_matches.append(c)
                    existing_keys.add(key.lower())

            all_matched_contacts.extend(new_matches)
            await _emit(
                f"New unique matches: {len(new_matches)}. "
                f"Total: {len(all_matched_contacts)}/{target_count}"
            )

            # Incremental export to Google Sheet
            if new_matches and _sheet_id:
                try:
                    await incremental_sheet_export(
                        all_matched_contacts, corridor, _sheet_id,
                        approach_log={
                            "timestamp": datetime.now().isoformat(),
                            "approach": f"University Search: {uni_label}",
                            "details": f"Schools: {schools_str} | Location: {', '.join(employer_countries)} | Titles: C-level/VP/Director/Head",
                            "contacts_found": len(all_people),
                            "decision_makers": len(decision_makers),
                            "matched": len(new_matches),
                            "hit_rate": f"{len(matched)/max(len(classified),1)*100:.1f}%",
                            "total_so_far": len(all_matched_contacts),
                        },
                    )
                    await _emit(f"Sheet updated: {len(all_matched_contacts)} contacts")
                except Exception as e:
                    logger.warning(f"Incremental export failed: {e}")

            # Save interim
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
            except Exception as e:
                logger.warning(f"Failed to save interim: {e}")

    # Phase 4: Final export to Google Sheet
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
            existing_sheet_id=_sheet_id,  # Use the sheet we created/used throughout
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


def _get_sheets_service():
    """Get authenticated Google Sheets + Drive services."""
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    creds_file = "/app/google-credentials.json"
    if not os.path.exists(creds_file):
        creds_file = str(Path(__file__).parent.parent.parent.parent / "google-credentials.json")
        if not os.path.exists(creds_file):
            raise FileNotFoundError("Google credentials not found")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
    drive_service = build("drive", "v3", credentials=creds)
    sheets_service = build("sheets", "v4", credentials=creds)
    return sheets_service, drive_service


# Column definitions for contact data
CONTACT_COLUMNS = [
    "Name", "First Name", "Last Name", "Email", "Title", "Company",
    "Domain", "Location", "LinkedIn URL", "Phone",
    "Origin Score", "Search Method", "Search Details", "Corridor",
]
CONTACT_FIELD_MAP = {
    "Name": "name", "First Name": "first_name", "Last Name": "last_name",
    "Email": "email", "Title": "title", "Company": "company",
    "Domain": "company_domain", "Location": "location",
    "LinkedIn URL": "linkedin_url", "Phone": "phone",
    "Origin Score": "_origin_score", "Search Method": "_search_method",
    "Search Details": "_search_details", "Corridor": "_corridor",
}


def _contact_to_row(contact: Dict[str, Any]) -> List[str]:
    """Convert a contact dict to a row for Google Sheets."""
    row = []
    for col in CONTACT_COLUMNS:
        val = contact.get(CONTACT_FIELD_MAP[col], "")
        if val is None:
            val = ""
        row.append(str(val)[:500])
    return row


async def export_diaspora_to_sheet(
    contacts: List[Dict[str, Any]],
    corridor: Dict[str, Any],
    stats: Dict[str, Any],
    existing_sheet_id: Optional[str] = None,
) -> str:
    """Export ALL diaspora contacts to Google Sheet (full rewrite). Returns sheet URL."""
    sheets_service, drive_service = _get_sheets_service()
    shared_drive_id = os.environ.get("SHARED_DRIVE_ID", "0AEvTjlJFlWnZUk9PVA")

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

    # Ensure main sheet exists with correct name
    try:
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"updateSheetProperties": {
                "properties": {"sheetId": 0, "title": corridor["sheet_name"]}, "fields": "title",
            }}]},
        ).execute()
    except Exception:
        pass  # Already named

    # Build all rows (header + all contacts)
    rows = [CONTACT_COLUMNS]
    for contact in contacts:
        rows.append(_contact_to_row(contact))

    # Clear and rewrite entire sheet
    sheet_name = corridor["sheet_name"]
    try:
        sheets_service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:Z",
        ).execute()
    except Exception:
        pass

    for i in range(0, len(rows), 5000):
        batch = rows[i:i + 5000]
        start_row = i + 1
        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A{start_row}",
            valueInputOption="RAW",
            body={"values": batch},
        ).execute()

    # Update stats tab (overwrite)
    try:
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": "Pipeline Stats"}}}]},
        ).execute()
    except Exception:
        pass  # Already exists

    stats_rows = [["Metric", "Value"]]
    for k, v in stats.items():
        stats_rows.append([str(k), str(v)])
    stats_rows.append(["generated_at", datetime.now().isoformat()])

    try:
        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="Pipeline Stats!A1",
            valueInputOption="RAW",
            body={"values": stats_rows},
        ).execute()
    except Exception as e:
        logger.warning(f"Failed to update stats tab: {e}")

    logger.info(f"Diaspora export: {len(contacts)} contacts to {sheet_url}")
    return sheet_url


async def incremental_sheet_export(
    contacts: List[Dict[str, Any]],
    corridor: Dict[str, Any],
    sheet_id: str,
    approach_log: Optional[Dict[str, Any]] = None,
) -> None:
    """Incrementally update Google Sheet — rewrite all contacts + append approach log."""
    try:
        sheets_service, _ = _get_sheets_service()
        sheet_name = corridor["sheet_name"]

        # Rewrite all contacts (header + data)
        rows = [CONTACT_COLUMNS]
        for contact in contacts:
            rows.append(_contact_to_row(contact))

        sheets_service.spreadsheets().values().clear(
            spreadsheetId=sheet_id,
            range=f"{sheet_name}!A:Z",
        ).execute()

        for i in range(0, len(rows), 5000):
            batch = rows[i:i + 5000]
            start_row = i + 1
            sheets_service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=f"{sheet_name}!A{start_row}",
                valueInputOption="RAW",
                body={"values": batch},
            ).execute()

        # Append to Approaches Log
        if approach_log:
            try:
                sheets_service.spreadsheets().batchUpdate(
                    spreadsheetId=sheet_id,
                    body={"requests": [{"addSheet": {"properties": {"title": "Approaches Log"}}}]},
                ).execute()
                # Write header
                sheets_service.spreadsheets().values().update(
                    spreadsheetId=sheet_id,
                    range="Approaches Log!A1",
                    valueInputOption="RAW",
                    body={"values": [[
                        "Timestamp", "Approach", "Details", "Contacts Found",
                        "Decision Makers", "Matched", "Hit Rate", "Total So Far",
                    ]]},
                ).execute()
            except Exception:
                pass  # Sheet already exists

            # Append approach row
            sheets_service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range="Approaches Log!A:H",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [[
                    approach_log.get("timestamp", datetime.now().isoformat()),
                    approach_log.get("approach", ""),
                    approach_log.get("details", ""),
                    approach_log.get("contacts_found", 0),
                    approach_log.get("decision_makers", 0),
                    approach_log.get("matched", 0),
                    approach_log.get("hit_rate", ""),
                    approach_log.get("total_so_far", 0),
                ]]},
            ).execute()

        logger.info(f"Incremental export: {len(contacts)} contacts to sheet {sheet_id}")
    except Exception as e:
        logger.error(f"Incremental sheet export failed: {e}")


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
