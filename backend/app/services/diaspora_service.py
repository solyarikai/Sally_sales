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

# ============================================================
# Surname batches — distinctive last names for each target country
# Each surname becomes a separate Clay search: name + location + titles
# Only pick DISTINCTIVE surnames (avoid Khan/Ahmed which are pan-Muslim)
# ============================================================
SURNAME_BATCHES = {
    "Pakistan": [
        # Tier 1: Very distinctive Pakistani surnames (low false positive in UAE)
        {"label": "pk_surname_1", "names": ["Malik", "Butt", "Chaudhry", "Rana", "Rajput"]},
        {"label": "pk_surname_2", "names": ["Akhtar", "Bhatti", "Gill", "Cheema", "Awan"]},
        {"label": "pk_surname_3", "names": ["Virk", "Warraich", "Gondal", "Bajwa", "Afridi"]},
        {"label": "pk_surname_4", "names": ["Khattak", "Siddiqui", "Qureshi", "Sethi", "Khawaja"]},
        {"label": "pk_surname_5", "names": ["Memon", "Paracha", "Arain", "Minhas", "Lodhi"]},
        {"label": "pk_surname_6", "names": ["Mughal", "Niazi", "Baloch", "Durrani", "Leghari"]},
        # Tier 2: Common but still useful — pair with title filter to reduce noise
        {"label": "pk_surname_7", "names": ["Khan"]},  # Massive volume — solo batch
        {"label": "pk_surname_8", "names": ["Rizvi", "Naqvi", "Bukhari", "Gilani", "Pirzada"]},
    ],
    "Philippines": [
        # Tier 1: Very distinctive Filipino surnames
        {"label": "ph_surname_1", "names": ["Santos", "Reyes", "Cruz", "Bautista", "Ocampo"]},
        {"label": "ph_surname_2", "names": ["Mendoza", "Villanueva", "Ramos", "Aquino", "Castillo"]},
        {"label": "ph_surname_3", "names": ["Tolentino", "Pangilinan", "Dizon", "Cunanan", "Manalo"]},
        {"label": "ph_surname_4", "names": ["Soriano", "Mercado", "Aguilar", "Enriquez", "Magno"]},
        # Chinese-Filipino surnames (also count as Filipino)
        {"label": "ph_surname_5", "names": ["Tan", "Chua", "Go", "Ong", "Sy"]},
        {"label": "ph_surname_6", "names": ["dela Cruz", "de los Santos", "del Rosario"]},
    ],
    "South Africa": [
        # Afrikaans surnames (very distinctive)
        {"label": "za_surname_afr_1", "names": ["Botha", "du Plessis", "van der Merwe", "Pretorius", "Joubert"]},
        {"label": "za_surname_afr_2", "names": ["Steyn", "Coetzee", "Venter", "Swanepoel", "Kruger"]},
        {"label": "za_surname_afr_3", "names": ["Erasmus", "du Toit", "Vermeulen", "Fourie", "le Roux"]},
        {"label": "za_surname_afr_4", "names": ["van Zyl", "Visser", "Viljoen", "Louw", "Marais"]},
        # Zulu/Xhosa/Sotho surnames
        {"label": "za_surname_blk_1", "names": ["Nkosi", "Dlamini", "Ndlovu", "Mkhize", "Khumalo"]},
        {"label": "za_surname_blk_2", "names": ["Ngcobo", "Sithole", "Mthembu", "Radebe", "Molefe"]},
        # SA Indian surnames
        {"label": "za_surname_ind_1", "names": ["Naidoo", "Govender", "Pillay", "Chetty", "Moodley"]},
        # SA business surnames
        {"label": "za_surname_biz", "names": ["Motsepe", "Wiese", "Bekker", "Sobrato", "Dippenaar"]},
    ],
}

# ============================================================
# Extended university batches — deeper coverage for more TAM
# ============================================================
EXTENDED_UNIVERSITY_BATCHES = {
    "Pakistan": [
        {"label": "pk_uni_ext_1", "schools": ["SZABIST", "UMT", "Forman Christian College", "University of Faisalabad", "Government College University"]},
        {"label": "pk_uni_ext_2", "schools": ["Beaconhouse National University", "University of Central Punjab", "Riphah International University", "International Islamic University", "FAST Lahore"]},
    ],
    "Philippines": [
        {"label": "ph_uni_ext_1", "schools": ["University of the Philippines Diliman", "Philippine Normal University", "Manila Central University", "University of Perpetual Help", "Philippine Women's University"]},
        {"label": "ph_uni_ext_2", "schools": ["Cebu Technological University", "Mindanao State University", "Western Mindanao State University", "Batangas State University", "Bulacan State University"]},
    ],
    "South Africa": [
        {"label": "za_uni_ext_1", "schools": ["Monash South Africa", "University of Limpopo", "University of Venda", "Mangosuthu University of Technology", "Central University of Technology"]},
        {"label": "za_uni_ext_2", "schools": ["University of Zululand", "Sol Plaatje University", "Sefako Makgatho Health Sciences University", "University of Fort Hare", "University of Western Cape"]},
    ],
}


async def run_diaspora_pipeline(
    corridor_key: str,
    project_id: int,
    target_count: int = 1000,
    on_progress: Optional[Callable] = None,
    mode: str = "full",  # "full" = industry + uni + surname, "university" = uni-only, "full_tam" = ALL approaches
    existing_sheet_id: Optional[str] = None,  # Append to existing sheet
) -> Dict[str, Any]:
    """Run the full diaspora gathering pipeline for a corridor.

    Modes:
    - "university": universities only (fastest, 15-30% hit rate)
    - "full": university + industry (default)
    - "full_tam": ALL approaches — university + extended uni + surname + industry (max TAM)

    Approach order (fastest/highest-yield first):
    1. University-based search (school filter + location + titles)
    2. Extended university batches (more schools)
    3. Surname-based search (distinctive last names + location + titles)
    4. Industry company search (company domain → people → classify)

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
        await _emit("University-only mode — skipping industry & surname searches")
    elif mode == "full_tam":
        await _emit("FULL TAM mode — running ALL approaches: university → extended uni → surname → industry")
    else:
        await _emit("Full mode — running university + industry")

    # Industry search is LAST (lowest yield, ~0.5% hit rate).
    # Skip it now — runs after university + surname phases below.
    run_industry = mode in ("full", "full_tam")

    # COMPANY→PEOPLE→NAME approach — DEFERRED to after higher-yield approaches
    for batch_config in ([]):
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
                c["_search_type"] = "industry_company_first"
                c["_search_batch"] = batch_label
                c["_schools_filter"] = ""
                c["_location_filter"] = ", ".join(employer_countries)
                c["_title_filter"] = "C-level/VP/Director/Head (Python filter)"
                c["_corridor"] = corridor_key
                c["_found_at"] = datetime.now().isoformat()
                # Build match reason from score + surname
                score = c.get("_origin_score", 0)
                last = c.get("last_name", "") or c.get("name", "").split()[-1] if c.get("name") else ""
                c["_match_reason"] = (
                    f"GPT score={score}/10. "
                    f"Surname '{last}' pre-filtered as potential {contractor_country}. "
                    f"Found via {industries_str} companies in {', '.join(employer_countries)}"
                )
                new_matches.append(c)
                existing_keys.add(key.lower())

        all_matched_contacts.extend(new_matches)
        await _emit(
            f"New unique matches: {len(new_matches)}. "
            f"Total: {len(all_matched_contacts)}/{target_count}"
        )

        # Incremental export to Google Sheet (ALWAYS log approach, even zero matches)
        if _sheet_id:
            try:
                await incremental_sheet_export(
                    all_matched_contacts, corridor, _sheet_id,
                    approach_log={
                        "timestamp": datetime.now().isoformat(),
                        "search_type": "industry_company_first",
                        "batch_name": batch_label,
                        "schools_filter": "",
                        "location_filter": ", ".join(employer_countries),
                        "title_filter": "C-level/VP/Director/Head (Python)",
                        "contacts_found": len(all_people),
                        "decision_makers": len(decision_makers),
                        "prefilter_candidates": len([c for c in classified if c.get("_origin_score", 0) > 0]),
                        "matched": len(new_matches),
                        "hit_rate": f"{len(matched)/max(len(classified),1)*100:.1f}%",
                        "new_unique": len(new_matches),
                        "total_so_far": len(all_matched_contacts),
                        "assessment": f"Low yield — {contractor_country} names rare in {', '.join(employer_countries)} companies" if len(matched) < 5 else "Good yield",
                        "next_action": "Try university-based search" if len(matched) < 5 else "Continue",
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
                    c["_search_type"] = "university_people_first"
                    c["_search_batch"] = uni_label
                    c["_schools_filter"] = schools_str
                    c["_location_filter"] = ", ".join(employer_countries)
                    c["_title_filter"] = "C-level/VP/Director/Head (Clay --titles filter)"
                    c["_corridor"] = corridor_key
                    c["_found_at"] = datetime.now().isoformat()
                    # Build rich match reason
                    score = c.get("_origin_score", 0)
                    clay_schools = c.get("schools", "")
                    last = c.get("last_name", "") or (c.get("name", "").split()[-1] if c.get("name") else "")
                    reason_parts = [f"GPT score={score}/10"]
                    if clay_schools:
                        reason_parts.append(f"Education: {clay_schools}")
                    else:
                        reason_parts.append(f"Found via school filter: {schools_str}")
                    reason_parts.append(f"Surname '{last}' matches {contractor_country} profile")
                    reason_parts.append(f"Located in {', '.join(employer_countries)}")
                    c["_match_reason"] = ". ".join(reason_parts)
                    new_matches.append(c)
                    existing_keys.add(key.lower())

            all_matched_contacts.extend(new_matches)
            await _emit(
                f"New unique matches: {len(new_matches)}. "
                f"Total: {len(all_matched_contacts)}/{target_count}"
            )

            # Incremental export to Google Sheet (ALWAYS log approach, even zero matches)
            if _sheet_id:
                try:
                    await incremental_sheet_export(
                        all_matched_contacts, corridor, _sheet_id,
                        approach_log={
                            "timestamp": datetime.now().isoformat(),
                            "search_type": "university_people_search",
                            "batch_name": uni_label,
                            "schools_filter": schools_str,
                            "location_filter": ", ".join(employer_countries),
                            "title_filter": "C-level/VP/Director/Head (Clay filter)",
                            "contacts_found": len(all_people),
                            "decision_makers": len(decision_makers),
                            "prefilter_candidates": len([c for c in classified if c.get("_origin_score", 0) > 0]),
                            "matched": len(new_matches),
                            "hit_rate": f"{len(matched)/max(len(classified),1)*100:.1f}%",
                            "new_unique": len(new_matches),
                            "total_so_far": len(all_matched_contacts),
                            "assessment": f"University approach — {len(new_matches)} unique from {schools_str}" if new_matches else f"No new unique matches from {schools_str}",
                            "next_action": "Continue university batches" if len(all_matched_contacts) < target_count else "Target reached",
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

    # Phase 3b: Extended university batches (full_tam mode, or if target not reached)
    ext_uni_batches = EXTENDED_UNIVERSITY_BATCHES.get(contractor_country, [])
    if ext_uni_batches and len(all_matched_contacts) < target_count and mode in ("full", "full_tam"):
        await _emit(f"\n=== EXTENDED UNIVERSITY SEARCH ({contractor_country}) ===")
        for uni_batch in ext_uni_batches:
            if len(all_matched_contacts) >= target_count:
                break

            uni_label = uni_batch["label"]
            schools = uni_batch["schools"]
            schools_str = ", ".join(schools)
            iteration += 1

            await _emit(f"\n--- Extended university batch {uni_label} ---")
            await _emit(f"Schools: {schools_str}")
            await _emit(f"Progress: {len(all_matched_contacts)}/{target_count}")

            try:
                result = await clay_service.run_people_search(
                    domains=None,
                    project_id=project_id,
                    on_progress=on_progress,
                    use_titles=True,
                    countries=employer_countries,
                    schools=schools,
                )
            except Exception as e:
                logger.error(f"Extended university search failed for {uni_label}: {e}")
                await _emit(f"Search failed: {e}. Skipping.")
                failed_batches += 1
                # Log failed approach
                if _sheet_id:
                    try:
                        await incremental_sheet_export(
                            all_matched_contacts, corridor, _sheet_id,
                            approach_log={
                                "timestamp": datetime.now().isoformat(),
                                "search_type": "extended_university",
                                "batch_name": uni_label,
                                "schools_filter": schools_str,
                                "location_filter": ", ".join(employer_countries),
                                "title_filter": "C-level/VP/Director/Head",
                                "contacts_found": 0, "decision_makers": 0,
                                "prefilter_candidates": 0, "matched": 0,
                                "hit_rate": "0%", "new_unique": 0,
                                "total_so_far": len(all_matched_contacts),
                                "assessment": f"FAILED: {str(e)[:100]}",
                                "next_action": "Retry or skip",
                            },
                        )
                    except Exception:
                        pass
                continue

            all_people = result.get("people", [])
            if not all_people:
                await _emit(f"No contacts found for {uni_label}. Skipping.")
                if _sheet_id:
                    try:
                        await incremental_sheet_export(
                            all_matched_contacts, corridor, _sheet_id,
                            approach_log={
                                "timestamp": datetime.now().isoformat(),
                                "search_type": "extended_university",
                                "batch_name": uni_label, "schools_filter": schools_str,
                                "location_filter": ", ".join(employer_countries),
                                "title_filter": "C-level/VP/Director/Head",
                                "contacts_found": 0, "decision_makers": 0,
                                "prefilter_candidates": 0, "matched": 0,
                                "hit_rate": "0%", "new_unique": 0,
                                "total_so_far": len(all_matched_contacts),
                                "assessment": "No contacts found",
                                "next_action": "Continue to next batch",
                            },
                        )
                    except Exception:
                        pass
                continue

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
                await _emit(f"Found {len(all_people)} contacts, 0 decision-makers.")
                continue

            await _emit(f"Found {len(all_people)} contacts → {len(decision_makers)} decision-makers")
            all_scanned += len(decision_makers)

            await _emit(f"Classifying {len(decision_makers)} names...")
            try:
                classified = await classify_names_by_origin(decision_makers, contractor_country)
            except Exception as e:
                logger.error(f"Classification failed: {e}")
                for p in decision_makers:
                    p["_origin_score"] = 8
                    p["_origin_match"] = True
                classified = decision_makers

            matched = [c for c in classified if c.get("_origin_match")]
            existing_keys = {(c.get("linkedin_url") or f"{c.get('name', '')}|{c.get('company', '')}").lower() for c in all_matched_contacts}
            new_matches = []
            for c in matched:
                key = c.get("linkedin_url") or f"{c.get('name', '')}|{c.get('company', '')}"
                if key.lower() not in existing_keys:
                    c["_search_type"] = "extended_university"
                    c["_search_batch"] = uni_label
                    c["_schools_filter"] = schools_str
                    c["_location_filter"] = ", ".join(employer_countries)
                    c["_title_filter"] = "C-level/VP/Director/Head"
                    c["_corridor"] = corridor_key
                    c["_found_at"] = datetime.now().isoformat()
                    score = c.get("_origin_score", 0)
                    clay_schools = c.get("schools", "")
                    c["_match_reason"] = f"GPT score={score}/10. Education: {clay_schools or schools_str}. Extended university batch."
                    new_matches.append(c)
                    existing_keys.add(key.lower())

            all_matched_contacts.extend(new_matches)
            await _emit(f"New unique: {len(new_matches)}. Total: {len(all_matched_contacts)}/{target_count}")

            if _sheet_id:
                try:
                    await incremental_sheet_export(
                        all_matched_contacts, corridor, _sheet_id,
                        approach_log={
                            "timestamp": datetime.now().isoformat(),
                            "search_type": "extended_university",
                            "batch_name": uni_label, "schools_filter": schools_str,
                            "location_filter": ", ".join(employer_countries),
                            "title_filter": "C-level/VP/Director/Head",
                            "contacts_found": len(all_people),
                            "decision_makers": len(decision_makers),
                            "prefilter_candidates": len([c for c in classified if c.get("_origin_score", 0) > 0]),
                            "matched": len(new_matches),
                            "hit_rate": f"{len(matched)/max(len(classified),1)*100:.1f}%",
                            "new_unique": len(new_matches),
                            "total_so_far": len(all_matched_contacts),
                            "assessment": f"Extended uni — {len(new_matches)} unique from {schools_str}" if new_matches else "No new unique",
                            "next_action": "Continue" if len(all_matched_contacts) < target_count else "Target reached",
                        },
                    )
                    await _emit(f"Sheet updated: {len(all_matched_contacts)} contacts")
                except Exception as e:
                    logger.warning(f"Incremental export failed: {e}")

    # Phase 3c: Surname-based search (full_tam mode, or full mode if target not reached)
    surname_batches = SURNAME_BATCHES.get(contractor_country, [])
    if surname_batches and len(all_matched_contacts) < target_count and mode in ("full", "full_tam"):
        await _emit(f"\n=== SURNAME SEARCH ({contractor_country}) ===")
        await _emit(f"Searching {len(surname_batches)} distinctive surname batches in {', '.join(employer_countries)}")

        for surname_batch in surname_batches:
            if len(all_matched_contacts) >= target_count:
                break

            batch_label = surname_batch["label"]
            surnames = surname_batch["names"]
            iteration += 1

            # For each surname, search Clay with name + location + titles
            for surname in surnames:
                if len(all_matched_contacts) >= target_count:
                    break

                search_label = f"{batch_label}_{surname.replace(' ', '_')}"
                await _emit(f"\n--- Surname search: {surname} in {', '.join(employer_countries)} ---")
                await _emit(f"Progress: {len(all_matched_contacts)}/{target_count}")

                try:
                    result = await clay_service.run_people_search(
                        domains=None,
                        project_id=project_id,
                        on_progress=on_progress,
                        use_titles=True,
                        countries=employer_countries,
                        name=surname,
                    )
                except Exception as e:
                    logger.error(f"Surname search failed for {surname}: {e}")
                    await _emit(f"Search failed: {e}. Skipping.")
                    failed_batches += 1
                    if _sheet_id:
                        try:
                            await incremental_sheet_export(
                                all_matched_contacts, corridor, _sheet_id,
                                approach_log={
                                    "timestamp": datetime.now().isoformat(),
                                    "search_type": "surname_search",
                                    "batch_name": search_label, "schools_filter": "",
                                    "location_filter": ", ".join(employer_countries),
                                    "title_filter": "C-level/VP/Director/Head",
                                    "contacts_found": 0, "decision_makers": 0,
                                    "prefilter_candidates": 0, "matched": 0,
                                    "hit_rate": "0%", "new_unique": 0,
                                    "total_so_far": len(all_matched_contacts),
                                    "assessment": f"FAILED: {str(e)[:100]}",
                                    "next_action": "Retry or skip",
                                },
                            )
                        except Exception:
                            pass
                    continue

                all_people = result.get("people", [])
                if not all_people:
                    await _emit(f"No contacts for surname '{surname}'. Skipping.")
                    if _sheet_id:
                        try:
                            await incremental_sheet_export(
                                all_matched_contacts, corridor, _sheet_id,
                                approach_log={
                                    "timestamp": datetime.now().isoformat(),
                                    "search_type": "surname_search",
                                    "batch_name": search_label, "schools_filter": "",
                                    "location_filter": ", ".join(employer_countries),
                                    "title_filter": f"C-level + name='{surname}'",
                                    "contacts_found": 0, "decision_makers": 0,
                                    "prefilter_candidates": 0, "matched": 0,
                                    "hit_rate": "0%", "new_unique": 0,
                                    "total_so_far": len(all_matched_contacts),
                                    "assessment": f"No results for surname '{surname}'",
                                    "next_action": "Continue to next surname",
                                },
                            )
                        except Exception:
                            pass
                    continue

                # Surname search already targets the right names, but still classify
                # to filter out false positives (e.g., "Santos" could be Brazilian in AU)
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
                    decision_makers = all_people  # Title filter was in Clay, trust it

                await _emit(f"Found {len(all_people)} contacts → {len(decision_makers)} to classify")
                all_scanned += len(decision_makers)

                await _emit(f"Classifying {len(decision_makers)} '{surname}' contacts...")
                try:
                    classified = await classify_names_by_origin(decision_makers, contractor_country)
                except Exception as e:
                    logger.error(f"Classification failed: {e}")
                    # Surname match is a strong signal — accept on failure
                    for p in decision_makers:
                        p["_origin_score"] = 7
                        p["_origin_match"] = True
                    classified = decision_makers

                matched = [c for c in classified if c.get("_origin_match")]
                existing_keys = {(c.get("linkedin_url") or f"{c.get('name', '')}|{c.get('company', '')}").lower() for c in all_matched_contacts}
                new_matches = []
                for c in matched:
                    key = c.get("linkedin_url") or f"{c.get('name', '')}|{c.get('company', '')}"
                    if key.lower() not in existing_keys:
                        c["_search_type"] = "surname_search"
                        c["_search_batch"] = search_label
                        c["_schools_filter"] = ""
                        c["_location_filter"] = ", ".join(employer_countries)
                        c["_title_filter"] = f"C-level + name='{surname}'"
                        c["_corridor"] = corridor_key
                        c["_found_at"] = datetime.now().isoformat()
                        score = c.get("_origin_score", 0)
                        last = c.get("last_name", "") or surname
                        c["_match_reason"] = f"GPT score={score}/10. Surname '{last}' is distinctive {contractor_country}. Found via surname search in {', '.join(employer_countries)}."
                        new_matches.append(c)
                        existing_keys.add(key.lower())

                all_matched_contacts.extend(new_matches)
                await _emit(f"New unique: {len(new_matches)}. Total: {len(all_matched_contacts)}/{target_count}")

                if _sheet_id:
                    try:
                        await incremental_sheet_export(
                            all_matched_contacts, corridor, _sheet_id,
                            approach_log={
                                "timestamp": datetime.now().isoformat(),
                                "search_type": "surname_search",
                                "batch_name": search_label, "schools_filter": "",
                                "location_filter": ", ".join(employer_countries),
                                "title_filter": f"C-level + name='{surname}'",
                                "contacts_found": len(all_people),
                                "decision_makers": len(decision_makers),
                                "prefilter_candidates": len([c for c in classified if c.get("_origin_score", 0) > 0]),
                                "matched": len(new_matches),
                                "hit_rate": f"{len(matched)/max(len(classified),1)*100:.1f}%",
                                "new_unique": len(new_matches),
                                "total_so_far": len(all_matched_contacts),
                                "assessment": f"Surname '{surname}' — {len(new_matches)} unique" if new_matches else f"Surname '{surname}' — no new unique",
                                "next_action": "Continue" if len(all_matched_contacts) < target_count else "Target reached",
                            },
                        )
                        await _emit(f"Sheet updated: {len(all_matched_contacts)} contacts")
                    except Exception as e:
                        logger.warning(f"Incremental export failed: {e}")

    # Phase 3d: Title-split search — search each C-level title individually
    # Each title search returns up to 5K people, then classify ALL names
    # This catches people without university listed or non-distinctive surnames
    TITLE_SPLITS = [
        {"label": "ceo", "titles": ["CEO"]},
        {"label": "founder", "titles": ["Founder"]},
        {"label": "cto", "titles": ["CTO"]},
        {"label": "cfo", "titles": ["CFO"]},
        {"label": "coo", "titles": ["COO"]},
        {"label": "managing_director", "titles": ["Managing Director"]},
        {"label": "vp", "titles": ["VP"]},
        {"label": "director", "titles": ["Director"]},
        {"label": "head_of", "titles": ["Head of"]},
        {"label": "partner", "titles": ["Partner"]},
        {"label": "general_manager", "titles": ["General Manager"]},
        {"label": "country_manager", "titles": ["Country Manager"]},
    ]

    if len(all_matched_contacts) < target_count and mode in ("full", "full_tam"):
        await _emit(f"\n=== TITLE-SPLIT SEARCH ({len(all_matched_contacts)}/{target_count}) ===")
        await _emit(f"Searching each C-level title individually in {', '.join(employer_countries)} → classify all names")

        for title_batch in TITLE_SPLITS:
            if len(all_matched_contacts) >= target_count:
                break

            t_label = title_batch["label"]
            titles = title_batch["titles"]
            iteration += 1

            await _emit(f"\n--- Title search: {titles[0]} in {', '.join(employer_countries)} ---")
            await _emit(f"Progress: {len(all_matched_contacts)}/{target_count}")

            try:
                # Use Clay People search with ONLY this specific title + location
                result = await clay_service.run_people_search(
                    domains=None,
                    project_id=project_id,
                    on_progress=on_progress,
                    use_titles=False,
                    countries=employer_countries,
                    job_title=titles[0],  # Single title filter via --job-title
                )
            except Exception as e:
                logger.error(f"Title-split search failed for {t_label}: {e}")
                await _emit(f"Search failed: {e}. Skipping.")
                failed_batches += 1
                if _sheet_id:
                    try:
                        await incremental_sheet_export(
                            all_matched_contacts, corridor, _sheet_id,
                            approach_log={
                                "timestamp": datetime.now().isoformat(),
                                "search_type": "title_split",
                                "batch_name": t_label, "schools_filter": "",
                                "location_filter": ", ".join(employer_countries),
                                "title_filter": titles[0],
                                "contacts_found": 0, "decision_makers": 0,
                                "prefilter_candidates": 0, "matched": 0,
                                "hit_rate": "0%", "new_unique": 0,
                                "total_so_far": len(all_matched_contacts),
                                "assessment": f"FAILED: {str(e)[:100]}",
                                "next_action": "Continue",
                            },
                        )
                    except Exception:
                        pass
                continue

            all_people = result.get("people", [])
            if not all_people:
                await _emit(f"No contacts for title '{titles[0]}'. Skipping.")
                if _sheet_id:
                    try:
                        await incremental_sheet_export(
                            all_matched_contacts, corridor, _sheet_id,
                            approach_log={
                                "timestamp": datetime.now().isoformat(),
                                "search_type": "title_split",
                                "batch_name": t_label, "schools_filter": "",
                                "location_filter": ", ".join(employer_countries),
                                "title_filter": titles[0],
                                "contacts_found": 0, "decision_makers": 0,
                                "prefilter_candidates": 0, "matched": 0,
                                "hit_rate": "0%", "new_unique": 0,
                                "total_so_far": len(all_matched_contacts),
                                "assessment": f"No results for title '{titles[0]}'",
                                "next_action": "Continue",
                            },
                        )
                    except Exception:
                        pass
                continue

            # Filter to only the specific title we searched for
            title_lower = titles[0].lower()
            title_filtered = [
                p for p in all_people
                if title_lower in (p.get("title") or "").lower()
            ]
            if not title_filtered:
                title_filtered = all_people  # Trust Clay's filter

            await _emit(f"Found {len(all_people)} contacts → {len(title_filtered)} with '{titles[0]}' title")
            all_scanned += len(title_filtered)

            # Classify ALL names — no pre-filter by surname, catch everyone
            await _emit(f"Classifying ALL {len(title_filtered)} names (no surname pre-filter)...")
            try:
                classified = await classify_names_by_origin(title_filtered, contractor_country)
            except Exception as e:
                logger.error(f"Classification failed: {e}")
                continue

            matched = [c for c in classified if c.get("_origin_match")]
            existing_keys = {(c.get("linkedin_url") or f"{c.get('name', '')}|{c.get('company', '')}").lower() for c in all_matched_contacts}
            new_matches = []
            for c in matched:
                key = c.get("linkedin_url") or f"{c.get('name', '')}|{c.get('company', '')}"
                if key.lower() not in existing_keys:
                    c["_search_type"] = "title_split"
                    c["_search_batch"] = t_label
                    c["_schools_filter"] = ""
                    c["_location_filter"] = ", ".join(employer_countries)
                    c["_title_filter"] = titles[0]
                    c["_corridor"] = corridor_key
                    c["_found_at"] = datetime.now().isoformat()
                    score = c.get("_origin_score", 0)
                    last = c.get("last_name", "") or (c.get("name", "").split()[-1] if c.get("name") else "")
                    c["_match_reason"] = f"GPT score={score}/10. Found via title-split '{titles[0]}' search in {', '.join(employer_countries)}. Surname '{last}'."
                    new_matches.append(c)
                    existing_keys.add(key.lower())

            all_matched_contacts.extend(new_matches)
            await _emit(f"New unique: {len(new_matches)}. Total: {len(all_matched_contacts)}/{target_count}")

            if _sheet_id:
                try:
                    await incremental_sheet_export(
                        all_matched_contacts, corridor, _sheet_id,
                        approach_log={
                            "timestamp": datetime.now().isoformat(),
                            "search_type": "title_split",
                            "batch_name": t_label, "schools_filter": "",
                            "location_filter": ", ".join(employer_countries),
                            "title_filter": titles[0],
                            "contacts_found": len(all_people),
                            "decision_makers": len(title_filtered),
                            "prefilter_candidates": len([c for c in classified if c.get("_origin_score", 0) > 0]),
                            "matched": len(new_matches),
                            "hit_rate": f"{len(matched)/max(len(classified),1)*100:.1f}%",
                            "new_unique": len(new_matches),
                            "total_so_far": len(all_matched_contacts),
                            "assessment": f"Title '{titles[0]}' — {len(new_matches)} new unique from {len(all_people)} total" if new_matches else f"Title '{titles[0]}' — no new unique",
                            "next_action": "Continue" if len(all_matched_contacts) < target_count else "Target reached",
                        },
                    )
                    await _emit(f"Sheet updated: {len(all_matched_contacts)} contacts")
                except Exception as e:
                    logger.warning(f"Incremental export failed: {e}")

    # Phase 4: Industry search (lowest yield, runs last)
    if run_industry and len(all_matched_contacts) < target_count:
        await _emit(f"\n=== INDUSTRY SEARCH (lowest yield, {len(all_matched_contacts)}/{target_count} so far) ===")
        for batch_config in INDUSTRY_BATCHES:
            if len(all_matched_contacts) >= target_count:
                break

            iteration += 1
            batch_label = batch_config["label"]

            await _emit(f"\n--- Industry: {batch_label} ---")
            await _emit(f"Progress: {len(all_matched_contacts)}/{target_count}")

            icp_text = build_icp_text(employer_countries, batch_config)
            try:
                tam_result = await clay_service.run_tam_export(
                    icp_text=icp_text, project_id=project_id, on_progress=on_progress,
                )
            except Exception as e:
                logger.error(f"TAM export failed for {batch_label}: {e}")
                await _emit(f"Company search failed: {e}. Skipping.")
                failed_batches += 1
                if _sheet_id:
                    try:
                        await incremental_sheet_export(
                            all_matched_contacts, corridor, _sheet_id,
                            approach_log={
                                "timestamp": datetime.now().isoformat(),
                                "search_type": "industry_company_first",
                                "batch_name": batch_label, "schools_filter": "",
                                "location_filter": ", ".join(employer_countries),
                                "title_filter": "C-level (Python filter)",
                                "contacts_found": 0, "decision_makers": 0,
                                "prefilter_candidates": 0, "matched": 0,
                                "hit_rate": "0%", "new_unique": 0,
                                "total_so_far": len(all_matched_contacts),
                                "assessment": f"FAILED: {str(e)[:100]}",
                                "next_action": "Continue",
                            },
                        )
                    except Exception:
                        pass
                continue

            companies = tam_result.get("companies", [])
            if not companies:
                await _emit(f"No companies found. Skipping.")
                continue

            import random
            all_domains = list({
                (c.get("Domain") or c.get("domain") or "").strip().lower().replace("www.", "")
                for c in companies
                if (c.get("Domain") or c.get("domain") or "").strip()
                and "." in (c.get("Domain") or c.get("domain") or "").strip()
            })
            all_companies_found += len(all_domains)
            if len(all_domains) > 1000:
                random.shuffle(all_domains)
                all_domains = all_domains[:1000]

            await _emit(f"Found {len(all_domains)} companies → searching people...")
            try:
                result = await clay_service.run_people_search(
                    domains=all_domains, project_id=project_id,
                    on_progress=on_progress, use_titles=True,
                    countries=employer_countries,
                )
            except Exception as e:
                logger.error(f"People search failed: {e}")
                failed_batches += 1
                continue

            all_people = result.get("people", [])
            if not all_people:
                continue

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
                continue

            all_scanned += len(decision_makers)
            await _emit(f"Classifying {len(decision_makers)} names...")
            try:
                classified = await classify_names_by_origin(decision_makers, contractor_country)
            except Exception as e:
                logger.error(f"Classification failed: {e}")
                continue

            matched = [c for c in classified if c.get("_origin_match")]
            existing_keys = {(c.get("linkedin_url") or f"{c.get('name', '')}|{c.get('company', '')}").lower() for c in all_matched_contacts}
            new_matches = []
            for c in matched:
                key = c.get("linkedin_url") or f"{c.get('name', '')}|{c.get('company', '')}"
                if key.lower() not in existing_keys:
                    c["_search_type"] = "industry_company_first"
                    c["_search_batch"] = batch_label
                    c["_schools_filter"] = ""
                    c["_location_filter"] = ", ".join(employer_countries)
                    c["_title_filter"] = "C-level (Python filter)"
                    c["_corridor"] = corridor_key
                    c["_found_at"] = datetime.now().isoformat()
                    score = c.get("_origin_score", 0)
                    last = c.get("last_name", "") or (c.get("name", "").split()[-1] if c.get("name") else "")
                    c["_match_reason"] = f"GPT score={score}/10. Surname '{last}' pre-filtered. Found via {batch_label} companies in {', '.join(employer_countries)}"
                    new_matches.append(c)
                    existing_keys.add(key.lower())

            all_matched_contacts.extend(new_matches)
            await _emit(f"New unique: {len(new_matches)}. Total: {len(all_matched_contacts)}/{target_count}")

            if _sheet_id:
                try:
                    await incremental_sheet_export(
                        all_matched_contacts, corridor, _sheet_id,
                        approach_log={
                            "timestamp": datetime.now().isoformat(),
                            "search_type": "industry_company_first",
                            "batch_name": batch_label, "schools_filter": "",
                            "location_filter": ", ".join(employer_countries),
                            "title_filter": "C-level (Python filter)",
                            "contacts_found": len(all_people),
                            "decision_makers": len(decision_makers),
                            "prefilter_candidates": len([c for c in classified if c.get("_origin_score", 0) > 0]),
                            "matched": len(new_matches),
                            "hit_rate": f"{len(matched)/max(len(classified),1)*100:.1f}%",
                            "new_unique": len(new_matches),
                            "total_so_far": len(all_matched_contacts),
                            "assessment": f"Industry {batch_label} — {len(new_matches)} unique" if new_matches else f"Industry {batch_label} — no unique",
                            "next_action": "Continue" if len(all_matched_contacts) < target_count else "Target reached",
                        },
                    )
                    await _emit(f"Sheet updated: {len(all_matched_contacts)} contacts")
                except Exception as e:
                    logger.warning(f"Incremental export failed: {e}")

    # Phase 5: Final export to Google Sheet
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


# Column definitions for contact data — full provenance for TAM scalability
CONTACT_COLUMNS = [
    # Identity
    "Name", "First Name", "Last Name", "Email", "Title", "Company",
    "Domain", "Location", "LinkedIn URL", "Phone",
    # Company context
    "Industry", "Company Size", "Company Location",
    # Education (key for university-based search)
    "Schools (from Clay)",
    # Classification
    "Origin Score", "Name Match Reason",
    # Search provenance — HOW this contact was found
    "Search Type", "Search Batch", "Schools Filter Used",
    "Location Filter", "Title Filter", "Corridor",
    # Timestamps
    "Found At",
]
CONTACT_FIELD_MAP = {
    "Name": "name", "First Name": "first_name", "Last Name": "last_name",
    "Email": "email", "Title": "title", "Company": "company",
    "Domain": "company_domain", "Location": "location",
    "LinkedIn URL": "linkedin_url", "Phone": "phone",
    "Industry": "industry", "Company Size": "company_size",
    "Company Location": "company_location",
    "Schools (from Clay)": "schools",
    "Origin Score": "_origin_score", "Name Match Reason": "_match_reason",
    "Search Type": "_search_type", "Search Batch": "_search_batch",
    "Schools Filter Used": "_schools_filter", "Location Filter": "_location_filter",
    "Title Filter": "_title_filter", "Corridor": "_corridor",
    "Found At": "_found_at",
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
                        "Timestamp", "Corridor", "Search Type", "Batch Name",
                        "Schools Filter", "Location Filter", "Title Filter",
                        "Raw Contacts", "Decision Makers", "Name Pre-Filter Candidates",
                        "GPT Matched", "Hit Rate (%)", "New Unique", "Dedup Skipped",
                        "Total Cumulative", "Assessment", "Next Action",
                    ]]},
                ).execute()
            except Exception:
                pass  # Sheet already exists

            # Append approach row
            corridor_label = corridor.get("label", "") if isinstance(corridor, dict) else str(corridor)
            sheets_service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range="Approaches Log!A:Q",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": [[
                    approach_log.get("timestamp", datetime.now().isoformat()),
                    corridor_label,
                    approach_log.get("search_type", ""),
                    approach_log.get("batch_name", ""),
                    approach_log.get("schools_filter", ""),
                    approach_log.get("location_filter", ""),
                    approach_log.get("title_filter", ""),
                    approach_log.get("contacts_found", 0),
                    approach_log.get("decision_makers", 0),
                    approach_log.get("prefilter_candidates", 0),
                    approach_log.get("matched", 0),
                    approach_log.get("hit_rate", ""),
                    approach_log.get("new_unique", 0),
                    approach_log.get("matched", 0) - approach_log.get("new_unique", 0),  # dedup skipped
                    approach_log.get("total_so_far", 0),
                    approach_log.get("assessment", ""),
                    approach_log.get("next_action", ""),
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
