#!/usr/bin/env python3
"""
OnSocial Clay→SmartLead Pipeline (Platforms + Agencies, 2026-03-26)

Full pipeline: Clay discovery → GPT classification → Apollo People Search →
FindyMail email enrichment → SmartLead upload with regional social_proof.

Steps 0-8: backend API on Hetzner (with checkpoints + Claude Code review).
Steps 9-12: Apollo + FindyMail + SmartLead (local on Hetzner).

Segments: INFLUENCER_PLATFORMS, IM_FIRST_AGENCIES (4 geo tiers each).

Usage (run on Hetzner via SSH):

  cd ~/magnum-opus-project/repo

  # Full pipeline from scratch
  python3 sofia/scripts/onsocial_clay_to_smartlead_platforms_agencies_2026-03-26.py --segment platforms_tier12

  # Resume from specific step
  python3 sofia/scripts/onsocial_clay_to_smartlead_platforms_agencies_2026-03-26.py --from-step scrape --run-id 150

  # Re-analyze with different prompt
  python3 sofia/scripts/onsocial_clay_to_smartlead_platforms_agencies_2026-03-26.py --re-analyze --run-id 150 --prompt-file prompts/v2.txt

  # Dry run
  python3 sofia/scripts/onsocial_clay_to_smartlead_platforms_agencies_2026-03-26.py --dry-run --segment platforms_tier12

Env vars: APOLLO_API_KEY, FINDYMAIL_API_KEY, SMARTLEAD_API_KEY
Backend must be running on localhost:8001 (Hetzner)
"""

import argparse
import asyncio
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

# ── PATHS ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
SOFIA_DIR = SCRIPT_DIR.parent
STATE_DIR = SOFIA_DIR.parent / "state" / "onsocial" / "v4"
STATE_DIR.mkdir(parents=True, exist_ok=True)

CSV_DIR = SOFIA_DIR / "output" / "OnSocial" / "v4"
CSV_DIR.mkdir(parents=True, exist_ok=True)

# State files
TARGETS_FILE = STATE_DIR / "targets.json"
CONTACTS_FILE = STATE_DIR / "contacts.json"
CONTACTS_CACHE = STATE_DIR / "contacts_cache.json"
ENRICHED_FILE = STATE_DIR / "enriched.json"
FINDYMAIL_PROGRESS = STATE_DIR / "findymail_progress.json"
UPLOAD_LOG = STATE_DIR / "upload_log.json"
RUN_STATE = STATE_DIR / "run_state.json"  # tracks current run_id + phase

# ── API CONFIG ────────────────────────────────────────────────────────────────
BACKEND_BASE = os.environ.get("BACKEND_BASE", "http://localhost:8000")
BACKEND_HEADERS = {"X-Company-ID": "1", "Content-Type": "application/json"}

APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY", "")
APOLLO_BASE = "https://api.apollo.io/api/v1"

FINDYMAIL_API_KEY = os.environ.get("FINDYMAIL_API_KEY", "")
FINDYMAIL_BASE = "https://app.findymail.com"
FINDYMAIL_CONCURRENT = 5

SMARTLEAD_API_KEY = os.environ.get("SMARTLEAD_API_KEY", "")
SMARTLEAD_BASE = "https://server.smartlead.ai/api/v1"

SMARTLEAD_EMAIL_ACCOUNTS = [
    2718958, 2718959, 2718960, 2718961, 2718962,
    2718963, 2718964, 2718965, 2718966, 2718967,
    2718968, 2718969, 2718970, 2718971,
]

PROJECT_ID = 42
MAX_CONTACTS_PER_COMPANY = 3
SENIORITIES = ["owner", "founder", "c_suite", "vp", "head", "director"]

# ── SOCIAL PROOF BY REGION ────────────────────────────────────────────────────

SOCIAL_PROOF = {
    "INFLUENCER_PLATFORMS": {
        "United Kingdom": "Whalar and Billion Dollar Boy",
        "Germany": "Zalando and Intermate",
        "France": "Kolsquare, Skeepers, and Favikon",
        "India": "Phyllo and KlugKlug",
        "Australia": "TRIBEGroup",
        "Spain": "SAMY Alliance",
        "United Arab Emirates": "ArabyAds and Sociata",
        "Saudi Arabia": "ArabyAds and Sociata",
        "Egypt": "ArabyAds and Sociata",
        "Turkey": "ArabyAds and Sociata",
        "Israel": "ArabyAds and Sociata",
        "Brazil": "Modash and Captiv8",
        "Mexico": "Modash and Captiv8",
        "Colombia": "Modash and Captiv8",
        "Argentina": "Modash and Captiv8",
        "_default": "Modash, Captiv8, and Lefty",
    },
    "IM_FIRST_AGENCIES": {
        "United Kingdom": "Whalar and Billion Dollar Boy",
        "Germany": "Linkster and Gocomo",
        "France": "Ykone and Skeepers",
        "India": "Qoruz and Tonic Worldwide",
        "Australia": "TRIBEGroup",
        "Spain": "SAMY Alliance",
        "United Arab Emirates": "ArabyAds and Sociata",
        "Saudi Arabia": "ArabyAds and Sociata",
        "Egypt": "ArabyAds and Sociata",
        "Turkey": "ArabyAds and Sociata",
        "Israel": "ArabyAds and Sociata",
        "Brazil": "Viral Nation and Captiv8",
        "Mexico": "Viral Nation and Captiv8",
        "Colombia": "Viral Nation and Captiv8",
        "Argentina": "Viral Nation and Captiv8",
        "_default": "Viral Nation and Obviously",
    },
}

# ── TITLES BY SEGMENT ─────────────────────────────────────────────────────────

TITLES = {
    "INFLUENCER_PLATFORMS": [
        "CTO", "VP Engineering", "VP of Engineering", "Head of Engineering",
        "Head of Product", "Chief Product Officer", "VP Product",
        "Director of Engineering", "Director of Product",
        "Co-Founder", "Founder", "CEO", "COO",
    ],
    "IM_FIRST_AGENCIES": [
        "CEO", "Founder", "Co-Founder", "Managing Director", "Managing Partner",
        "Head of Influencer Marketing", "Director of Influencer",
        "Head of Influencer", "VP Strategy", "Head of Partnerships",
        "Director of Client Services", "Head of Strategy",
        "General Manager", "Partner", "Owner",
    ],
}

# ── CLAY FILTER CONFIGS ──────────────────────────────────────────────────────

CLAY_FILTERS = {
    # ── Legacy configs (runs 154-158) ─────────────────────────────
    "platforms_tier12": {
        "segment": "INFLUENCER_PLATFORMS",
        "filters": {
            "icp_text": (
                "SaaS companies building products for influencer marketing and creator economy. "
                "These are platforms for influencer discovery, audience analytics, creator marketplaces, "
                "social listening, UGC platforms, creator data APIs, brand monitoring tools. "
                "Examples: Modash, Captiv8, Lefty, Kolsquare, Skeepers, Favikon, Phyllo, KlugKlug, The Shelf, impact.com. "
                "NOT: recruitment agencies, PR agencies, generic SMM agencies, web design, SEO/PPC agencies, consulting, fintech. "
                "Key characteristic: company HAS its own technology product (platform/SaaS/API) for influencer/creator data or analytics."
            ),
            "industries": ["Computer Software", "Internet", "Marketing and Advertising", "Information Technology and Services", "Online Media"],
            "country_names": [
                "United States", "United Kingdom", "Germany", "Netherlands", "France",
                "Canada", "Australia", "Spain", "Italy", "Sweden", "Denmark", "Belgium",
                "United Arab Emirates", "Saudi Arabia", "Egypt", "Turkey", "Israel",
            ],
            "minimum_member_count": 10,
            "maximum_member_count": 5000,
            "max_results": 5000,
        },
    },
    "platforms_tier34": {
        "segment": "INFLUENCER_PLATFORMS",
        "filters": {
            "icp_text": (
                "SaaS companies building products for influencer marketing and creator economy. "
                "Platforms for influencer discovery, audience analytics, creator marketplaces, social listening, UGC, creator data APIs. "
                "Examples: Modash, Captiv8, Phyllo, KlugKlug. "
                "NOT: recruitment, PR, web design, SEO, consulting, fintech. "
                "Must have own technology product (platform/SaaS/API)."
            ),
            "industries": ["Computer Software", "Internet", "Marketing and Advertising", "Information Technology and Services"],
            "country_names": ["India", "Brazil", "Mexico", "Colombia", "Argentina"],
            "minimum_member_count": 10,
            "maximum_member_count": 5000,
            "max_results": 2000,
        },
    },
    "agencies_tier12": {
        "segment": "IM_FIRST_AGENCIES",
        "filters": {
            "icp_text": (
                "Agencies where influencer marketing is the CORE business, not a side service. "
                "Specialize in launching campaigns with influencers, managing creator contracts, TikTok/Instagram/YouTube campaigns. "
                "Examples: Viral Nation, Obviously, Ykone, Billion Dollar Boy, SAMY Alliance, TRIBEGroup, Whalar, Intermate, Brighter Click. "
                "NOT: PR agencies, generic digital agencies, SEO/PPC, marketing holdings (WPP, Omnicom, HAVAS, Publicis, Mindshare), "
                "freelancers, agencies under 10 people, web studios, consulting firms. "
                "Key: influencer marketing or creator marketing explicitly stated as core service. Size 10-500 employees."
            ),
            "industries": ["Marketing and Advertising"],
            "country_names": [
                "United States", "United Kingdom", "Germany", "Netherlands", "France",
                "Australia", "Canada", "Spain", "Belgium", "Denmark",
                "United Arab Emirates", "Saudi Arabia", "Egypt", "Turkey", "Israel",
            ],
            "minimum_member_count": 10,
            "maximum_member_count": 500,
            "max_results": 5000,
        },
    },
    "agencies_tier34": {
        "segment": "IM_FIRST_AGENCIES",
        "filters": {
            "icp_text": (
                "Agencies where influencer marketing is the CORE business. "
                "Specialize in influencer campaigns, creator management, TikTok/Instagram/YouTube. "
                "Examples: Viral Nation, Qoruz, Tonic Worldwide, SAMY Alliance. "
                "NOT: PR, digital agencies, SEO/PPC, holdings, freelancers, <10 people, web studios. "
                "Must have influencer/creator marketing as core. 10-500 employees."
            ),
            "industries": ["Marketing and Advertising"],
            "country_names": ["India", "Brazil", "Mexico", "Colombia", "Argentina"],
            "minimum_member_count": 10,
            "maximum_member_count": 500,
            "max_results": 2000,
        },
    },

    # ── v4.1: Per-region configs (7 regions × 2 segments = 14) ────

    # ── 1. MENA (HIGH PRIORITY — 10x conversion) ─────────────────
    "platforms_mena": {
        "segment": "INFLUENCER_PLATFORMS",
        "filters": {
            "icp_text": (
                "SaaS companies building products for influencer marketing and creator economy. "
                "Platforms for influencer discovery, audience analytics, creator marketplaces, "
                "social listening, UGC platforms, creator data APIs, brand monitoring tools, "
                "social commerce, live shopping platforms, creator monetization tools. "
                "Company keywords: influencer marketing platform, creator analytics, creator marketplace, "
                "influencer platform, social media analytics, UGC platform, creator economy, "
                "audience analytics, influencer API, social listening, brand monitoring, creator data, "
                "influencer discovery, creator tools, influencer intelligence, audience intelligence, social data. "
                "Examples: ArabyAds, Sociata, Vamp, Tagger, CreatorIQ. "
                "NOT: recruitment, PR, generic SMM, web design, SEO/PPC, consulting, fintech. "
                "Must have own technology product (platform/SaaS/API)."
            ),
            "industries": ["Computer Software", "Internet", "Marketing and Advertising", "Information Technology and Services", "Online Media"],
            "country_names": ["United Arab Emirates", "Saudi Arabia", "Egypt", "Turkey", "Israel"],
            "minimum_member_count": 5,
            "maximum_member_count": 5000,
            "max_results": 2000,
        },
    },
    "agencies_mena": {
        "segment": "IM_FIRST_AGENCIES",
        "filters": {
            "icp_text": (
                "Agencies where influencer marketing is the CORE business, not a side service. "
                "Specialize in influencer campaigns, creator management, TikTok/Instagram/YouTube campaigns. "
                "Company keywords: influencer marketing agency, influencer agency, creator agency, "
                "influencer management, creator campaigns, influencer marketing, creator partnerships, "
                "TikTok agency, influencer talent, creator talent, influencer strategy, UGC agency. "
                "Examples: ArabyAds, Sociata, Vamp, ITP Media Group. "
                "NOT: PR, generic digital agencies, SEO/PPC, marketing holdings (WPP, Omnicom, HAVAS, Publicis, Mindshare), "
                "freelancers, web studios, consulting. "
                "Must have influencer/creator marketing as core. 10-500 employees."
            ),
            "industries": ["Marketing and Advertising"],
            "country_names": ["United Arab Emirates", "Saudi Arabia", "Egypt", "Turkey", "Israel"],
            "minimum_member_count": 10,
            "maximum_member_count": 500,
            "max_results": 2000,
        },
    },

    # ── 2. India (HIGH PRIORITY — agencies 100% warm) ─────────────
    "platforms_india": {
        "segment": "INFLUENCER_PLATFORMS",
        "filters": {
            "icp_text": (
                "SaaS companies building products for influencer marketing and creator economy. "
                "Platforms for influencer discovery, audience analytics, creator marketplaces, "
                "social listening, UGC platforms, creator data APIs, brand monitoring, "
                "social commerce, creator monetization, live shopping platforms. "
                "Company keywords: influencer marketing platform, creator analytics, creator marketplace, "
                "influencer platform, social media analytics, UGC platform, creator economy, "
                "audience analytics, influencer API, social listening, creator data, "
                "influencer discovery, influencer intelligence, audience intelligence. "
                "Examples: Phyllo, KlugKlug, Qoruz, Atisfyre, Winkl, Plixxo, Chtrbox. "
                "NOT: recruitment, PR, generic SMM, web design, SEO/PPC, consulting, fintech, e-commerce brands. "
                "Must have own technology product (platform/SaaS/API)."
            ),
            "industries": ["Computer Software", "Internet", "Marketing and Advertising", "Information Technology and Services", "Online Media"],
            "country_names": ["India"],
            "minimum_member_count": 5,
            "maximum_member_count": 5000,
            "max_results": 2000,
        },
    },
    "agencies_india": {
        "segment": "IM_FIRST_AGENCIES",
        "filters": {
            "icp_text": (
                "Agencies where influencer marketing is the CORE business, not a side service. "
                "Specialize in influencer campaigns, creator management, TikTok/Instagram/YouTube campaigns. "
                "Company keywords: influencer marketing agency, influencer agency, creator agency, "
                "influencer management, creator campaigns, influencer marketing, creator partnerships, "
                "TikTok agency, influencer talent, creator talent, influencer strategy, UGC agency. "
                "Examples: Qoruz, Tonic Worldwide, Chtrbox, Plixxo, Winkl, Grynow, WhizCo. "
                "NOT: PR, generic digital agencies, SEO/PPC, marketing holdings, "
                "freelancers, IT outsourcing, web development, consulting. "
                "Must have influencer/creator marketing as core. 10-500 employees."
            ),
            "industries": ["Marketing and Advertising"],
            "country_names": ["India"],
            "minimum_member_count": 10,
            "maximum_member_count": 500,
            "max_results": 2000,
        },
    },

    # ── 3. US/Canada (HIGH PRIORITY — flagship) ──────────────────
    "platforms_us": {
        "segment": "INFLUENCER_PLATFORMS",
        "filters": {
            "icp_text": (
                "SaaS companies building products for influencer marketing and creator economy. "
                "Platforms for influencer discovery, audience analytics, creator marketplaces, "
                "social listening, UGC platforms, creator data APIs, brand monitoring tools, "
                "social commerce, live shopping, creator monetization, affiliate-influencer platforms. "
                "Company keywords: influencer marketing platform, creator analytics, creator marketplace, "
                "influencer platform, social media analytics, UGC platform, creator economy, "
                "audience analytics, influencer API, social listening, brand monitoring, creator data, "
                "influencer discovery, creator tools, influencer intelligence, audience intelligence, "
                "social data, affiliate marketing platform, creator commerce, creator storefront. "
                "Examples: Modash, Captiv8, Lefty, The Shelf, impact.com, GRIN, Aspire, CreatorIQ. "
                "NOT: recruitment, PR, generic SMM, web design, SEO/PPC, consulting, fintech. "
                "Must have own technology product (platform/SaaS/API)."
            ),
            "industries": ["Computer Software", "Internet", "Marketing and Advertising", "Information Technology and Services", "Online Media"],
            "country_names": ["United States", "Canada"],
            "minimum_member_count": 5,
            "maximum_member_count": 5000,
            "max_results": 5000,
        },
    },
    "agencies_us": {
        "segment": "IM_FIRST_AGENCIES",
        "filters": {
            "icp_text": (
                "Agencies where influencer marketing is the CORE business, not a side service. "
                "Specialize in influencer campaigns, creator management, TikTok/Instagram/YouTube campaigns. "
                "Company keywords: influencer marketing agency, influencer agency, creator agency, "
                "influencer management, creator campaigns, influencer marketing, creator partnerships, "
                "TikTok agency, influencer talent, creator talent, influencer strategy, UGC agency. "
                "Examples: Viral Nation, Obviously, Socially Powerful, NeoReach, Open Influence. "
                "NOT: PR, generic digital agencies, SEO/PPC, marketing holdings (WPP, Omnicom, HAVAS, Publicis, Mindshare), "
                "freelancers, web studios, consulting. "
                "Must have influencer/creator marketing as core. 10-500 employees."
            ),
            "industries": ["Marketing and Advertising"],
            "country_names": ["United States", "Canada"],
            "minimum_member_count": 10,
            "maximum_member_count": 500,
            "max_results": 5000,
        },
    },

    # ── 4. UK (MEDIUM PRIORITY) ──────────────────────────────────
    "platforms_uk": {
        "segment": "INFLUENCER_PLATFORMS",
        "filters": {
            "icp_text": (
                "SaaS companies building products for influencer marketing and creator economy. "
                "Platforms for influencer discovery, audience analytics, creator marketplaces, "
                "social listening, UGC platforms, creator data APIs, brand monitoring tools, "
                "social commerce, creator monetization tools. "
                "Company keywords: influencer marketing platform, creator analytics, creator marketplace, "
                "influencer platform, social media analytics, UGC platform, creator economy, "
                "audience analytics, influencer API, social listening, brand monitoring, creator data, "
                "influencer discovery, creator tools, influencer intelligence, audience intelligence. "
                "Examples: Whalar, Billion Dollar Boy, Traackr, Influencity. "
                "NOT: recruitment, PR, generic SMM, web design, SEO/PPC, consulting, fintech. "
                "Must have own technology product (platform/SaaS/API)."
            ),
            "industries": ["Computer Software", "Internet", "Marketing and Advertising", "Information Technology and Services", "Online Media"],
            "country_names": ["United Kingdom"],
            "minimum_member_count": 5,
            "maximum_member_count": 5000,
            "max_results": 2000,
        },
    },
    "agencies_uk": {
        "segment": "IM_FIRST_AGENCIES",
        "filters": {
            "icp_text": (
                "Agencies where influencer marketing is the CORE business, not a side service. "
                "Specialize in influencer campaigns, creator management, TikTok/Instagram/YouTube campaigns. "
                "Company keywords: influencer marketing agency, influencer agency, creator agency, "
                "influencer management, creator campaigns, influencer marketing, creator partnerships, "
                "TikTok agency, influencer talent, creator talent, influencer strategy, UGC agency. "
                "Examples: Whalar, Billion Dollar Boy, Socially Powerful, Goat Agency, Brighter Click. "
                "NOT: PR, generic digital agencies, SEO/PPC, marketing holdings (WPP, Omnicom, HAVAS, Publicis), "
                "freelancers, web studios, consulting. "
                "Must have influencer/creator marketing as core. 10-500 employees."
            ),
            "industries": ["Marketing and Advertising"],
            "country_names": ["United Kingdom"],
            "minimum_member_count": 10,
            "maximum_member_count": 500,
            "max_results": 2000,
        },
    },

    # ── 5. LATAM (MEDIUM PRIORITY) ───────────────────────────────
    "platforms_latam": {
        "segment": "INFLUENCER_PLATFORMS",
        "filters": {
            "icp_text": (
                "SaaS companies building products for influencer marketing and creator economy. "
                "Platforms for influencer discovery, audience analytics, creator marketplaces, "
                "social listening, UGC platforms, creator data APIs, brand monitoring tools, "
                "social commerce, creator monetization tools. "
                "Company keywords: influencer marketing platform, creator analytics, creator marketplace, "
                "influencer platform, social media analytics, UGC platform, creator economy, "
                "audience analytics, influencer API, social listening, creator data, "
                "influencer discovery, influencer intelligence, audience intelligence. "
                "Examples: Modash, Captiv8, Squid (now part of Locaweb). "
                "NOT: recruitment, PR, generic SMM, web design, SEO/PPC, consulting, fintech. "
                "Must have own technology product (platform/SaaS/API)."
            ),
            "industries": ["Computer Software", "Internet", "Marketing and Advertising", "Information Technology and Services", "Online Media"],
            "country_names": ["Brazil", "Mexico", "Colombia", "Argentina"],
            "minimum_member_count": 5,
            "maximum_member_count": 5000,
            "max_results": 2000,
        },
    },
    "agencies_latam": {
        "segment": "IM_FIRST_AGENCIES",
        "filters": {
            "icp_text": (
                "Agencies where influencer marketing is the CORE business, not a side service. "
                "Specialize in influencer campaigns, creator management, TikTok/Instagram/YouTube campaigns. "
                "Company keywords: influencer marketing agency, influencer agency, creator agency, "
                "influencer management, creator campaigns, influencer marketing, creator partnerships, "
                "TikTok agency, influencer talent, creator talent, influencer strategy, UGC agency, "
                "agencia de influencers, marketing de influenciadores. "
                "Examples: Viral Nation, Captiv8, SAMY Alliance, Buzzmonitor. "
                "NOT: PR, generic digital agencies, SEO/PPC, marketing holdings, "
                "freelancers, web studios, consulting. "
                "Must have influencer/creator marketing as core. 10-500 employees."
            ),
            "industries": ["Marketing and Advertising"],
            "country_names": ["Brazil", "Mexico", "Colombia", "Argentina"],
            "minimum_member_count": 10,
            "maximum_member_count": 500,
            "max_results": 2000,
        },
    },

    # ── 6. Europe (LOW PRIORITY — 0% reply solo, but v4 copy is different) ──
    "platforms_europe": {
        "segment": "INFLUENCER_PLATFORMS",
        "filters": {
            "icp_text": (
                "SaaS companies building products for influencer marketing and creator economy. "
                "Platforms for influencer discovery, audience analytics, creator marketplaces, "
                "social listening, UGC platforms, creator data APIs, brand monitoring tools, "
                "social commerce, creator monetization tools. "
                "Company keywords: influencer marketing platform, creator analytics, creator marketplace, "
                "influencer platform, social media analytics, UGC platform, creator economy, "
                "audience analytics, influencer API, social listening, brand monitoring, creator data, "
                "influencer discovery, creator tools, influencer intelligence, audience intelligence. "
                "Examples: Kolsquare, Skeepers, Favikon, Zalando (creator tools), Intermate, SAMY Alliance. "
                "NOT: recruitment, PR, generic SMM, web design, SEO/PPC, consulting, fintech. "
                "Must have own technology product (platform/SaaS/API)."
            ),
            "industries": ["Computer Software", "Internet", "Marketing and Advertising", "Information Technology and Services", "Online Media"],
            "country_names": ["Germany", "France", "Netherlands", "Spain", "Italy", "Sweden", "Denmark", "Belgium"],
            "minimum_member_count": 5,
            "maximum_member_count": 5000,
            "max_results": 3000,
        },
    },
    "agencies_europe": {
        "segment": "IM_FIRST_AGENCIES",
        "filters": {
            "icp_text": (
                "Agencies where influencer marketing is the CORE business, not a side service. "
                "Specialize in influencer campaigns, creator management, TikTok/Instagram/YouTube campaigns. "
                "Company keywords: influencer marketing agency, influencer agency, creator agency, "
                "influencer management, creator campaigns, influencer marketing, creator partnerships, "
                "TikTok agency, influencer talent, creator talent, influencer strategy, UGC agency, "
                "Influencer-Agentur, agence influenceurs, agencia influencers. "
                "Examples: Intermate, Ykone, SAMY Alliance, Linkster, Gocomo, Kolsquare. "
                "NOT: PR, generic digital agencies, SEO/PPC, marketing holdings (WPP, Omnicom, HAVAS, Publicis), "
                "freelancers, web studios, consulting. "
                "Must have influencer/creator marketing as core. 10-500 employees."
            ),
            "industries": ["Marketing and Advertising"],
            "country_names": ["Germany", "France", "Netherlands", "Spain", "Italy", "Sweden", "Denmark", "Belgium"],
            "minimum_member_count": 10,
            "maximum_member_count": 500,
            "max_results": 3000,
        },
    },

    # ── 7. Australia (LOW PRIORITY — small market, test) ──────────
    "platforms_australia": {
        "segment": "INFLUENCER_PLATFORMS",
        "filters": {
            "icp_text": (
                "SaaS companies building products for influencer marketing and creator economy. "
                "Platforms for influencer discovery, audience analytics, creator marketplaces, "
                "social listening, UGC platforms, creator data APIs, brand monitoring tools, "
                "social commerce, creator monetization tools. "
                "Company keywords: influencer marketing platform, creator analytics, creator marketplace, "
                "influencer platform, social media analytics, UGC platform, creator economy, "
                "audience analytics, influencer API, social listening, creator data, "
                "influencer discovery, influencer intelligence, audience intelligence. "
                "Examples: TRIBEGroup, Vamp, Hypetap. "
                "NOT: recruitment, PR, generic SMM, web design, SEO/PPC, consulting, fintech. "
                "Must have own technology product (platform/SaaS/API)."
            ),
            "industries": ["Computer Software", "Internet", "Marketing and Advertising", "Information Technology and Services", "Online Media"],
            "country_names": ["Australia"],
            "minimum_member_count": 5,
            "maximum_member_count": 5000,
            "max_results": 1000,
        },
    },
    "agencies_australia": {
        "segment": "IM_FIRST_AGENCIES",
        "filters": {
            "icp_text": (
                "Agencies where influencer marketing is the CORE business, not a side service. "
                "Specialize in influencer campaigns, creator management, TikTok/Instagram/YouTube campaigns. "
                "Company keywords: influencer marketing agency, influencer agency, creator agency, "
                "influencer management, creator campaigns, influencer marketing, creator partnerships, "
                "TikTok agency, influencer talent, creator talent, influencer strategy, UGC agency. "
                "Examples: TRIBEGroup, Vamp, The Influence Agency, Hypetap. "
                "NOT: PR, generic digital agencies, SEO/PPC, marketing holdings, "
                "freelancers, web studios, consulting. "
                "Must have influencer/creator marketing as core. 10-500 employees."
            ),
            "industries": ["Marketing and Advertising"],
            "country_names": ["Australia"],
            "minimum_member_count": 10,
            "maximum_member_count": 500,
            "max_results": 1000,
        },
    },
}

# ── CLASSIFICATION PROMPT ─────────────────────────────────────────────────────
# Used in Step 5 (Analyze). Same logic as GOD_pipeline CLASSIFICATION_PROMPT.
# Can be overridden with --prompt-file.

DEFAULT_ANALYSIS_PROMPT = """\
You classify companies as potential customers of OnSocial — a B2B API
that provides creator/influencer data for Instagram, TikTok, and YouTube
(audience demographics, engagement analytics, fake follower detection,
creator search).

Companies that need OnSocial are those whose CORE business involves
working with social media creators.

== STEP 1: INSTANT DISQUALIFIERS ==
- website_content is EMPTY and no description → "OTHER | No data available"
- Domain is parked / for sale / dead → "OTHER | Domain inactive"
- 5000+ employees → "OTHER | Enterprise, too large"
- <10 employees → "OTHER | Too small"

If none triggered → continue to Step 2.

== STEP 2: SEGMENTS ==

INFLUENCER_PLATFORMS
  Builds SaaS / software / tools for influencer marketing: analytics,
  creator discovery, campaign management, creator CRM, UGC content
  platforms, creator marketplaces, creator monetization tools, social
  commerce, live shopping platforms, social listening with creator focus.
  KEY TEST: they have a PRODUCT (software/platform/API) that brands or
  agencies use to find, analyze, manage, or pay creators.

IM_FIRST_AGENCIES
  Agency where influencer/creator campaigns are THE primary business,
  not a side service. 10-500 employees. Includes: influencer-first
  agencies, MCN (multi-channel networks), creator talent management,
  gaming influencer agencies, UGC production agencies.
  KEY TEST: 60%+ of their visible offering (homepage, case studies,
  team titles) is about creator/influencer work.

OTHER
  Everything that does NOT fit above. Includes: generic digital agencies,
  PR firms, SEO/PPC shops, web development, e-commerce brands (unless
  they BUILD creator tools), consulting, recruitment, fintech, etc.

== STEP 3: CONFLICT RESOLUTION ==
- Company does BOTH agency work AND has a SaaS product → INFLUENCER_PLATFORMS
  (product companies are higher-value targets)
- Company is a "full-service digital agency" that also does IM → OTHER
  (not IM-first, IM is a side service)
- Company description mentions "influencer" but core is PR → OTHER
- Company is an affiliate network without creator focus → OTHER

== OUTPUT FORMAT (strict) ==
SEGMENT | confidence (0.0-1.0) | one-line reasoning

Examples:
INFLUENCER_PLATFORMS | 0.92 | SaaS platform for influencer discovery and analytics
IM_FIRST_AGENCIES | 0.85 | Agency specializing in TikTok creator campaigns, 50 employees
OTHER | 0.95 | Generic digital marketing agency, IM is one of 8 services listed
"""


# ── HELPERS ───────────────────────────────────────────────────────────────────

def load_json(path: Path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None

def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def save_csv(path: Path, rows: list[dict], sheet_name: str = None):
    """Save CSV locally and optionally to Google Sheets.

    If sheet_name is provided, the local file is renamed to match the sheet name
    (with | and — replaced for filesystem safety). Both local and Sheets get
    identical names per convention: [PROJECT] | [TYPE] | [SEGMENT] — [DATE].
    """
    if not rows:
        return

    # If sheet_name given, use it as local filename too
    if sheet_name:
        safe_name = sheet_name.replace(" | ", "_").replace(" — ", "_").replace(" ", "_").replace("/", "-")
        path = path.parent / f"{safe_name}.csv"

    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  → CSV: {path.name} ({len(rows)} rows)")

    if sheet_name:
        _upload_to_sheets(fieldnames, rows, sheet_name)


def _upload_to_sheets(headers: list[str], rows: list[dict], sheet_name: str):
    """Upload data to Google Sheets via backend API."""
    data = [headers] + [[str(row.get(h, "")) for h in headers] for row in rows]
    try:
        result = httpx.post(
            f"{BACKEND_BASE}/api/google-sheets/create",
            headers=BACKEND_HEADERS,
            json={"title": sheet_name, "data": data, "share_with": ["pn@getsally.io"]},
            timeout=60,
        )
        if result.status_code == 200:
            url = result.json().get("url", result.json().get("sheet_id", ""))
            print(f"  → Sheet: {sheet_name} — {url}")
        else:
            # Fallback: direct call via subprocess (when running on Hetzner)
            _upload_to_sheets_direct(data, sheet_name)
    except Exception:
        _upload_to_sheets_direct(data, sheet_name)


def _upload_to_sheets_direct(data: list[list], sheet_name: str):
    """Fallback: upload via google_sheets_service directly (requires backend in path)."""
    try:
        import subprocess
        script = f'''
import sys, csv, json
sys.path.insert(0, "/app")
import os; os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", ""))
from app.services.google_sheets_service import google_sheets_service
data = json.loads(sys.stdin.read())
sid = google_sheets_service.create_and_populate(title="{sheet_name}", data=data["data"], share_with=["pn@getsally.io"])
print(sid if isinstance(sid, str) else "")
'''
        payload = json.dumps({"data": data})
        result = subprocess.run(
            ["docker", "exec", "-i", "leadgen-backend", "python3", "-c", script],
            input=payload, capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0 and result.stdout.strip():
            out = result.stdout.strip()
            # Extract sheet ID from URL if needed
            if "spreadsheets/d/" in out:
                sheet_id = out.split("spreadsheets/d/")[1].split("/")[0]
            else:
                sheet_id = out
            print(f"  → Sheet: {sheet_name} — https://docs.google.com/spreadsheets/d/{sheet_id}")
        else:
            print(f"  ⚠ Sheet upload failed: {result.stderr[:200]}")
    except Exception as e:
        print(f"  ⚠ Sheet upload skipped: {e}")

def normalize_company(name: str) -> str:
    for suffix in [" Inc", " Inc.", " LLC", " Ltd", " Ltd.", " GmbH", " Corp", " Corp.", " S.A.", " S.L."]:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    return name.strip()

def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def tag() -> str:
    return datetime.now().strftime("%b%d")

def api(method: str, path: str, raise_on_error: bool = True, **kwargs) -> dict:
    """Call backend API."""
    url = f"{BACKEND_BASE}/api{path}"
    r = getattr(httpx, method)(url, headers=BACKEND_HEADERS, timeout=300, **kwargs)
    if r.status_code >= 400:
        if raise_on_error:
            print(f"  API ERROR {r.status_code}: {r.text[:500]}")
            sys.exit(1)
        return {"_error": r.status_code, "_detail": r.text[:500]}
    return r.json()

def get_social_proof(country: str, segment: str) -> str:
    table = SOCIAL_PROOF.get(segment, SOCIAL_PROOF["INFLUENCER_PLATFORMS"])
    return table.get(country, table["_default"])

def get_latest_prompt_id(project_id: int = PROJECT_ID) -> int | None:
    """Get the latest active prompt_id for this project from gathering_prompts."""
    result = api("get", f"/pipeline/gathering/prompts?project_id={project_id}", raise_on_error=False)
    prompts = result if isinstance(result, list) else result.get("items", [])
    active = [p for p in prompts if p.get("is_active", True)]
    if active:
        latest = max(active, key=lambda p: p["id"])
        print(f"  Using prompt: #{latest['id']} '{latest.get('name', '?')}' "
              f"(usage={latest.get('usage_count', 0)}, avg_target_rate={latest.get('avg_target_rate', '?')})")
        return latest["id"]
    return None

def save_state(run_id: int, phase: str, gate_id: int = None, config_key: str = ""):
    save_json(RUN_STATE, {"run_id": run_id, "phase": phase, "gate_id": gate_id,
                           "config_key": config_key, "updated_at": ts()})

def load_state() -> dict:
    return load_json(RUN_STATE) or {}


# ══════════════════════════════════════════════════════════════════════════════
# STEP 0: START GATHERING (Clay)
# ══════════════════════════════════════════════════════════════════════════════

def step0_start(config_key: str, project_id: int = PROJECT_ID) -> int:
    """Start Clay gathering via backend API. Returns run_id."""
    config = CLAY_FILTERS[config_key]
    print(f"\n{'='*60}")
    print(f"STEP 0: Clay Gathering — {config_key}")
    print(f"  Segment: {config['segment']}")
    print(f"  Countries: {', '.join(config['filters'].get('country_names', []))}")
    print(f"  Max results: {config['filters'].get('max_results', 5000)}")
    print(f"{'='*60}")

    result = api("post", "/pipeline/gathering/start", json={
        "project_id": project_id,
        "source_type": "clay.companies.emulator",
        "filters": config["filters"],
        "triggered_by": "operator",
        "input_mode": "structured",
        "notes": f"v4 pipeline — {config_key}",
    })

    run_id = result["id"]
    print(f"\n  Run created: #{run_id}")
    print(f"  Status: {result['status']} / {result['current_phase']}")
    save_state(run_id, "started", config_key=config_key)
    return run_id


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1-2: BLACKLIST → CP1
# ══════════════════════════════════════════════════════════════════════════════

def step2_blacklist(run_id: int) -> dict:
    """Run blacklist check → creates CP1 gate."""
    print(f"\n{'='*60}")
    print(f"STEP 2: Blacklist Check (run #{run_id})")
    print(f"{'='*60}")

    result = api("post", f"/pipeline/gathering/runs/{run_id}/blacklist-check")
    print(f"  Phase: {result.get('current_phase', '?')}")

    # Get pending gate
    gates = api("get", f"/pipeline/gathering/runs/{run_id}/gates")
    pending = [g for g in gates if g["status"] == "pending"]
    if pending:
        gate = pending[0]
        gate_id = gate["id"]
        save_state(run_id, "awaiting_scope_ok", gate_id=gate_id)
        print(f"\n  ★ CHECKPOINT 1 — gate #{gate_id}")
        print(f"  Scope: {json.dumps(gate.get('scope', {}), indent=2)[:1000]}")
        return {"gate_id": gate_id, "scope": gate.get("scope", {})}
    return {}


def approve_gate(gate_id: int, note: str = "Approved by Claude Code") -> dict:
    """Approve a checkpoint gate."""
    result = api("post", f"/pipeline/gathering/approval-gates/{gate_id}/approve",
                 json={"decision_note": note})
    print(f"  Gate #{gate_id} approved")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3-4: PRE-FILTER + SCRAPE
# ══════════════════════════════════════════════════════════════════════════════

def step3_prefilter(run_id: int) -> dict:
    print(f"\n{'='*60}")
    print(f"STEP 3: Pre-filter (run #{run_id})")
    print(f"{'='*60}")
    result = api("post", f"/pipeline/gathering/runs/{run_id}/pre-filter")
    print(f"  Phase: {result.get('current_phase', '?')}")
    save_state(run_id, "pre_filtered")
    return result


def step4_scrape(run_id: int) -> dict:
    print(f"\n{'='*60}")
    print(f"STEP 4: Scrape websites (run #{run_id})")
    print(f"  This may take 10-30 minutes...")
    print(f"{'='*60}")
    result = api("post", f"/pipeline/gathering/runs/{run_id}/scrape")
    print(f"  Phase: {result.get('current_phase', '?')}")
    save_state(run_id, "scraped")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: ANALYZE (GPT) → CP2  — with re-analyze loop
# ══════════════════════════════════════════════════════════════════════════════

def step5_analyze(run_id: int, prompt_text: str = None, prompt_id: int = PROMPT_ID,
                   model: str = "gpt-4o-mini") -> dict:
    """Run GPT analysis. Uses prompt_id by default (tracks metrics in gathering_prompts).
    Falls back to prompt_text if prompt_id is None."""
    print(f"\n{'='*60}")
    print(f"STEP 5: Analyze (run #{run_id})")
    print(f"  Model: {model}")
    if prompt_id:
        print(f"  Prompt ID: {prompt_id}")
    else:
        print(f"  Prompt: {prompt_text[:100]}...")
    print(f"{'='*60}")

    params = {"model": model}
    if prompt_id:
        params["prompt_id"] = prompt_id
    elif prompt_text:
        params["prompt_text"] = prompt_text
    else:
        params["prompt_text"] = DEFAULT_ANALYSIS_PROMPT

    result = api("post", f"/pipeline/gathering/runs/{run_id}/analyze",
                 params=params)

    target_rate = result.get("target_rate", 0)
    targets_count = result.get("targets_count", 0)
    total_analyzed = result.get("total_analyzed", 0)

    print(f"\n  Analyzed: {total_analyzed}")
    print(f"  Targets: {targets_count} ({target_rate*100:.1f}%)")

    # Get CP2 gate
    gates = api("get", f"/pipeline/gathering/runs/{run_id}/gates")
    pending = [g for g in gates if g["status"] == "pending"]
    if pending:
        gate = pending[0]
        gate_id = gate["id"]
        save_state(run_id, "awaiting_targets_ok", gate_id=gate_id)

        # Output for Claude Code review
        print(f"\n  ★ CHECKPOINT 2 — gate #{gate_id}")
        print(f"  Target rate: {target_rate*100:.1f}%")
        print(f"  Review targets and decide:")
        print(f"    - approve: target rate OK, proceed to FindyMail")
        print(f"    - re-analyze: try different prompt")
        print(f"    - cancel: abort this run")

        return {
            "gate_id": gate_id,
            "target_rate": target_rate,
            "targets_count": targets_count,
            "total_analyzed": total_analyzed,
        }
    return {"target_rate": target_rate, "targets_count": targets_count}


def step5_reanalyze(run_id: int, prompt_text: str = None, prompt_id: int = None,
                     model: str = "gpt-4o-mini") -> dict:
    """Re-run analysis with different prompt (no re-scrape needed)."""
    print(f"\n{'='*60}")
    print(f"STEP 5 (RE-ANALYZE): run #{run_id}")
    if prompt_id:
        print(f"  Prompt ID: {prompt_id}")
    else:
        print(f"  New prompt: {prompt_text[:100]}...")
    print(f"{'='*60}")

    params = {"model": model}
    if prompt_id:
        params["prompt_id"] = prompt_id
    elif prompt_text:
        params["prompt_text"] = prompt_text

    result = api("post", f"/pipeline/gathering/runs/{run_id}/re-analyze",
                 params=params)

    target_rate = result.get("target_rate", 0)
    targets_count = result.get("targets_count", 0)

    print(f"\n  New target rate: {target_rate*100:.1f}%")
    print(f"  Targets: {targets_count}")

    gates = api("get", f"/pipeline/gathering/runs/{run_id}/gates")
    pending = [g for g in gates if g["status"] == "pending"]
    if pending:
        gate_id = pending[0]["id"]
        save_state(run_id, "awaiting_targets_ok", gate_id=gate_id)
        return {"gate_id": gate_id, "target_rate": target_rate, "targets_count": targets_count}
    return {"target_rate": target_rate, "targets_count": targets_count}


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6-8: VERIFY (FindyMail via backend) → CP3
# ══════════════════════════════════════════════════════════════════════════════

def step6_prepare_verify(run_id: int) -> dict:
    """Prepare FindyMail verification → creates CP3 with cost estimate."""
    print(f"\n{'='*60}")
    print(f"STEP 6: Prepare Verification (run #{run_id})")
    print(f"{'='*60}")

    result = api("post", f"/pipeline/gathering/runs/{run_id}/prepare-verification")

    gates = api("get", f"/pipeline/gathering/runs/{run_id}/gates")
    pending = [g for g in gates if g["status"] == "pending"]
    if pending:
        gate = pending[0]
        gate_id = gate["id"]
        scope = gate.get("scope", {})
        save_state(run_id, "awaiting_verify_ok", gate_id=gate_id)

        print(f"\n  ★ CHECKPOINT 3 — gate #{gate_id}")
        print(f"  Emails to verify: {scope.get('emails_to_verify', '?')}")
        print(f"  Estimated cost: ${scope.get('estimated_cost_usd', '?')}")
        return {"gate_id": gate_id, "scope": scope}
    return result


# ══════════════════════════════════════════════════════════════════════════════
# STEP 9: EXPORT TARGETS FROM DB
# ══════════════════════════════════════════════════════════════════════════════

def step9_export_targets(project_id: int, force: bool = False) -> list[dict]:
    """Export approved targets from backend DB."""
    print(f"\n{'='*60}")
    print(f"STEP 9: Export Targets (project_id={project_id})")
    print(f"{'='*60}")

    if TARGETS_FILE.exists() and not force:
        targets = load_json(TARGETS_FILE)
        print(f"  Loaded from cache: {len(targets)} targets")
        return targets

    # Try API first
    try:
        r = httpx.get(
            f"{BACKEND_BASE}/api/pipeline/gathering/targets/",
            params={"project_id": project_id, "is_target": True},
            headers=BACKEND_HEADERS, timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            targets = data if isinstance(data, list) else data.get("items", data.get("targets", []))
        else:
            targets = _export_targets_db(project_id)
    except Exception:
        targets = _export_targets_db(project_id)

    if not targets:
        print("  No targets found. Complete backend pipeline first (Steps 0-8).")
        sys.exit(1)

    save_json(TARGETS_FILE, targets)
    segments = {}
    for t in targets:
        seg = t.get("segment", t.get("analysis_segment", "UNKNOWN"))
        segments[seg] = segments.get(seg, 0) + 1
    print(f"  Exported: {len(targets)} targets")
    for seg, cnt in sorted(segments.items()):
        print(f"    {seg}: {cnt}")

    # Save per-segment CSVs (local + Google Sheets)
    today = datetime.now().strftime("%Y-%m-%d")
    seg_map = {"INFLUENCER_PLATFORMS": "INFPLAT", "IM_FIRST_AGENCIES": "IMAGENCY"}
    platforms = [t for t in targets if _is_platforms_segment(t.get("segment", ""))]
    agencies = [t for t in targets if _is_agencies_segment(t.get("segment", ""))]

    if platforms:
        save_csv(CSV_DIR / f"targets_INFPLAT_{tag()}.csv", platforms,
                 sheet_name=f"OS | Targets | INFPLAT — {today}")
    if agencies:
        save_csv(CSV_DIR / f"targets_IMAGENCY_{tag()}.csv", agencies,
                 sheet_name=f"OS | Targets | IMAGENCY — {today}")

    return targets


def _is_platforms_segment(seg: str) -> bool:
    seg_upper = seg.upper()
    return any(kw in seg_upper for kw in [
        "PLATFORM", "SAAS", "UGC", "ANALYTICS", "CREATOR_ECON",
        "MARKETPLACE", "COMMERCE", "LINK_IN_BIO", "NIL_MANAGEMENT",
        "MICRO-INFLUENCER", "MICRO_INFLUENCER", "INFLUENCER_PLATFORMS",
    ])


def _is_agencies_segment(seg: str) -> bool:
    seg_upper = seg.upper()
    return any(kw in seg_upper for kw in [
        "IM_FIRST", "IMAGENC", "INFLUENCER_MARKETING_AGENCY",
        "MCN", "TALENT_MANAGEMENT", "CREATOR_MANAGEMENT",
        "CREATOR_MARKETING_AGENCY", "CREATOR_NETWORK",
        "B2B_INFLUENCER", "AFFILIATE_PERF",
    ])


def _export_targets_db(project_id: int) -> list[dict]:
    """Fallback: export via psql on Hetzner."""
    import subprocess
    sql = (
        f"SELECT domain, name, matched_segment, confidence, latest_analysis_segment "
        f"FROM discovered_companies WHERE project_id={project_id} AND is_target=true"
    )
    cmd = f'docker exec leadgen-postgres psql -U leadgen -d leadgen -t -A -F \'|\' -c "{sql}"'
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        targets = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("|")
            if len(parts) >= 4:
                segment = (parts[4].strip() if len(parts) > 4 and parts[4].strip()
                           else parts[2].strip())
                targets.append({
                    "domain": parts[0].strip(),
                    "company_name": parts[1].strip(),
                    "segment": segment,
                    "confidence": parts[3].strip(),
                })
        return targets
    except Exception as e:
        print(f"  DB export error: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# STEP 10: APOLLO PEOPLE IMPORT (from manual Apollo People Search CSV)
# ══════════════════════════════════════════════════════════════════════════════

# Apollo People CSV column mapping (standard Apollo export)
APOLLO_CSV_COLUMNS = {
    "first_name": ["First Name", "first_name"],
    "last_name": ["Last Name", "last_name"],
    "email": ["Email", "email", "Email Address"],
    "title": ["Title", "title", "Job Title"],
    "company_name": ["Company", "company", "Company Name", "Organization Name"],
    "domain": ["Website", "website", "Company Domain", "domain", "Domain"],
    "linkedin_url": ["Person Linkedin Url", "LinkedIn URL", "linkedin_url", "LinkedIn", "Person LinkedIn URL"],
    "country": ["Country", "country", "Person Country"],
    "employees": ["# Employees", "employees", "Number of Employees", "Company Size"],
}


def _normalize_domain(raw: str) -> str:
    """Extract bare domain from URL or email."""
    d = raw.strip().lower()
    for prefix in ["https://", "http://", "www."]:
        if d.startswith(prefix):
            d = d[len(prefix):]
    d = d.rstrip("/").split("/")[0]
    return d


def _map_csv_row(row: dict, targets_by_domain: dict) -> dict:
    """Map an Apollo CSV row to our contact format."""
    def _get(field: str) -> str:
        for col in APOLLO_CSV_COLUMNS.get(field, [field]):
            if col in row and row[col]:
                return row[col].strip()
        return ""

    domain = _normalize_domain(_get("domain") or _get("email").split("@")[-1] if "@" in _get("email") else "")
    target = targets_by_domain.get(domain, {})
    segment = target.get("segment", target.get("analysis_segment", "UNKNOWN"))

    return {
        "first_name": _get("first_name"),
        "last_name": _get("last_name"),
        "email": _get("email"),
        "title": _get("title"),
        "company_name": normalize_company(_get("company_name") or target.get("company_name", domain)),
        "domain": domain,
        "segment": segment,
        "linkedin_url": _get("linkedin_url"),
        "country": _get("country") or target.get("country", ""),
        "employees": _get("employees") or target.get("employees", ""),
        "social_proof": get_social_proof(_get("country") or target.get("country", ""), segment),
    }


def step10_import_apollo_csv(csv_path: str, targets: list[dict],
                              force: bool = False,
                              segment_override: str = None) -> list[dict]:
    """Import contacts from a manual Apollo People Search CSV export."""
    print(f"\n{'='*60}")
    seg_label = f" ({segment_override})" if segment_override else ""
    print(f"STEP 10: Import Apollo People CSV{seg_label}")
    print(f"{'='*60}")

    if CONTACTS_FILE.exists() and not force:
        contacts = load_json(CONTACTS_FILE)
        print(f"  Loaded from cache: {len(contacts)} contacts")
        return contacts

    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f"  ERROR: CSV not found: {csv_path}")
        print(f"  Export from Apollo People Search UI and provide path via --apollo-csv")
        sys.exit(1)

    # Build domain→target lookup from targets
    targets_by_domain = {}
    for t in targets:
        d = t.get("domain", "").strip().lower()
        if d:
            targets_by_domain[d] = t

    # Read CSV
    with csv_file.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)
    print(f"  CSV rows: {len(raw_rows)}")
    if raw_rows:
        print(f"  Columns: {', '.join(raw_rows[0].keys())}")

    # Map and filter
    all_contacts = []
    skipped_no_name = 0
    skipped_no_domain = 0
    for row in raw_rows:
        contact = _map_csv_row(row, targets_by_domain)
        if segment_override:
            contact["segment"] = segment_override
            contact["social_proof"] = get_social_proof(contact["country"], segment_override)
        if not contact["first_name"]:
            skipped_no_name += 1
            continue
        if not contact["domain"]:
            skipped_no_domain += 1
            continue
        all_contacts.append(contact)

    # Dedupe by linkedin_url or (first_name + last_name + domain)
    seen = set()
    deduped = []
    for c in all_contacts:
        key = c["linkedin_url"] or f"{c['first_name']}|{c['last_name']}|{c['domain']}"
        if key not in seen:
            seen.add(key)
            deduped.append(c)
    all_contacts = deduped

    save_json(CONTACTS_FILE, all_contacts)

    with_email = sum(1 for c in all_contacts if c["email"])
    with_li = sum(1 for c in all_contacts if c["linkedin_url"])
    segments = {}
    for c in all_contacts:
        seg = c.get("segment", "UNKNOWN")
        segments[seg] = segments.get(seg, 0) + 1

    print(f"\n  Imported: {len(all_contacts)} contacts")
    print(f"  With email: {with_email}, with LinkedIn: {with_li}")
    if skipped_no_name:
        print(f"  Skipped (no name): {skipped_no_name}")
    if skipped_no_domain:
        print(f"  Skipped (no domain): {skipped_no_domain}")
    print(f"  Segments:")
    for seg, cnt in sorted(segments.items(), key=lambda x: -x[1]):
        print(f"    {seg}: {cnt}")

    today = datetime.now().strftime("%Y-%m-%d")
    save_csv(CSV_DIR / f"apollo_contacts_{tag()}.csv", all_contacts,
             sheet_name=f"OS | Import | Apollo People — {today}")
    return all_contacts


# ── GetSales Export ──────────────────────────────────────────────────────────

GETSALES_HEADERS = [
    "system_uuid", "pipeline_stage", "full_name", "first_name", "last_name",
    "position", "headline", "about", "linkedin_id", "sales_navigator_id",
    "linkedin_nickname", "linkedin_url", "facebook_nickname", "twitter_nickname",
    "work_email", "personal_email", "work_phone", "personal_phone",
    "connections_number", "followers_number", "primary_language",
    "has_open_profile", "has_verified_profile", "has_premium",
    "location_country", "location_state", "location_city",
    "active_flows", "list_name", "tags",
    "company_name", "company_industry", "company_linkedin_id", "company_domain",
    "company_linkedin_url", "company_employees_range", "company_headquarter",
    "cf_location", "cf_competitor_client",
    "cf_message1", "cf_message2", "cf_message3",
    "cf_personalization", "cf_compersonalization", "cf_personalization1",
    "cf_message4", "cf_linkedin_personalization", "cf_subject", "created_at",
]


def _extract_linkedin_nickname(url: str) -> str:
    m = re.search(r"linkedin\.com/in/([^/?]+)", url or "")
    return m.group(1) if m else ""


def _export_getsales(without_email: list[dict], today: str) -> Path:
    """Convert without-email contacts to GetSales-ready CSV."""
    date_folder = datetime.now().strftime("%d_%m")
    gs_dir = SOFIA_DIR / "get_sales_hub" / date_folder
    gs_dir.mkdir(parents=True, exist_ok=True)

    # Detect segment from first contact
    seg = without_email[0].get("segment", "UNKNOWN") if without_email else "UNKNOWN"
    out_path = gs_dir / f"GetSales — {seg}_without_email — {date_folder.replace('_', '.')}.csv"

    gs_rows = []
    for c in without_email:
        li_url = c.get("linkedin_url", "").strip()
        if li_url and not li_url.startswith("http"):
            li_url = f"https://{li_url}"

        gs = {h: "" for h in GETSALES_HEADERS}
        gs["full_name"] = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
        gs["first_name"] = c.get("first_name", "")
        gs["last_name"] = c.get("last_name", "")
        gs["position"] = c.get("title", "")
        gs["linkedin_nickname"] = _extract_linkedin_nickname(li_url)
        gs["linkedin_url"] = li_url
        gs["company_name"] = normalize_company(c.get("company_name", ""))
        gs["company_domain"] = c.get("domain", "")
        gs["cf_location"] = c.get("country", "")
        gs["list_name"] = f"{seg} Without Email {today}"
        gs["tags"] = seg
        gs_rows.append(gs)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=GETSALES_HEADERS)
        writer.writeheader()
        writer.writerows(gs_rows)

    print(f"  📋 GetSales-ready: {out_path.name} ({len(gs_rows)} contacts)")
    return out_path


# ══════════════════════════════════════════════════════════════════════════════
# STEP 11: FINDYMAIL
# ══════════════════════════════════════════════════════════════════════════════

async def find_email(client: httpx.AsyncClient, linkedin_url: str) -> dict:
    url = linkedin_url.strip()
    if not url.startswith("http"):
        url = f"https://{url}"
    try:
        r = await client.post(
            f"{FINDYMAIL_BASE}/api/search/linkedin",
            headers={"Authorization": f"Bearer {FINDYMAIL_API_KEY}", "Content-Type": "application/json"},
            json={"linkedin_url": url}, timeout=60.0,
        )
        if r.status_code == 200:
            data = r.json()
            contact = data.get("contact", {})
            return {"email": data.get("email") or contact.get("email") or "",
                    "verified": data.get("verified", False) or contact.get("verified", False)}
        elif r.status_code == 402:
            raise RuntimeError("OUT_OF_CREDITS")
        return {"email": "", "verified": False}
    except RuntimeError:
        raise
    except Exception:
        return {"email": "", "verified": False}


async def step11_findymail(contacts: list[dict], max_contacts: int = 1500,
                            force: bool = False) -> list[dict]:
    print(f"\n{'='*60}")
    print(f"STEP 11: FindyMail Enrichment")
    print(f"{'='*60}")

    if ENRICHED_FILE.exists() and not force:
        return load_json(ENRICHED_FILE)

    if not FINDYMAIL_API_KEY:
        print("  ERROR: FINDYMAIL_API_KEY not set")
        sys.exit(1)

    already_have = [c for c in contacts if c.get("email")]
    to_enrich = [c for c in contacts if not c.get("email") and c.get("linkedin_url")]
    to_enrich = to_enrich[:max_contacts]

    cost = len(to_enrich) * 0.01
    print(f"  {len(already_have)} already have email")
    print(f"  {len(to_enrich)} to enrich (~${cost:.2f})")
    print(f"\n  ★ CHECKPOINT: ${cost:.2f} for {len(to_enrich)} contacts.")
    if sys.stdin.isatty():
        print("  Enter to continue, Ctrl+C to abort.")
        input()
    else:
        print("  Non-interactive mode — proceeding automatically.")

    done = load_json(FINDYMAIL_PROGRESS) or {}
    sem = asyncio.Semaphore(FINDYMAIL_CONCURRENT)
    found = not_found = 0
    out_of_credits = False
    t0 = time.time()

    async def process_one(row):
        nonlocal found, not_found, out_of_credits
        if out_of_credits:
            return
        li = row.get("linkedin_url", "").strip()
        if not li:
            return
        if li in done:
            res = done[li]
            row["email"] = res.get("email", "")
            if res.get("email"): found += 1
            else: not_found += 1
            return
        async with sem:
            async with httpx.AsyncClient() as client:
                try:
                    res = await find_email(client, li)
                except RuntimeError:
                    out_of_credits = True
                    return
            row["email"] = res.get("email", "")
            done[li] = res
            if res.get("email"):
                found += 1
                print(f"  ✓ {row.get('first_name','')} {row.get('last_name','')} → {res['email']}")
            else:
                not_found += 1

    for i in range(0, len(to_enrich), 20):
        if out_of_credits:
            print("\n  OUT OF CREDITS")
            break
        await asyncio.gather(*[process_one(r) for r in to_enrich[i:i+20]])
        save_json(FINDYMAIL_PROGRESS, done)

    all_enriched = already_have + to_enrich
    save_json(ENRICHED_FILE, all_enriched)

    with_email = [c for c in all_enriched if c.get("email", "").strip()]
    without_email = [c for c in all_enriched if not c.get("email") and c.get("linkedin_url")]
    today = datetime.now().strftime("%Y-%m-%d")
    save_csv(CSV_DIR / f"with_email_{tag()}.csv", with_email,
             sheet_name=f"OS | Leads | Verified Emails — {today}")
    save_csv(CSV_DIR / f"without_email_{tag()}.csv", without_email,
             sheet_name=f"OS | Leads | No Email (LinkedIn only) — {today}")

    # Auto-export GetSales-ready CSV for contacts without email
    if without_email:
        _export_getsales(without_email, today)

    print(f"\n  Done in {time.time()-t0:.0f}s. With email: {len(with_email)}, without: {len(without_email)}")
    return all_enriched


# ══════════════════════════════════════════════════════════════════════════════
# STEP 12: SMARTLEAD UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

def sl_params():
    return {"api_key": SMARTLEAD_API_KEY}

def create_campaign(name: str) -> int:
    r = httpx.post(f"{SMARTLEAD_BASE}/campaigns/create", params=sl_params(), json={
        "name": name, "track_settings": ["DONT_TRACK_EMAIL_OPEN", "DONT_TRACK_LINK_CLICK"],
        "send_as_plain_text": True, "stop_lead_settings": "REPLY_TO_AN_EMAIL",
    }, timeout=30)
    r.raise_for_status()
    cid = r.json()["id"]
    print(f"  Created campaign: {cid} — {name}")
    return cid

def upload_leads(campaign_id: int, contacts: list[dict]) -> int:
    leads = []
    for c in contacts:
        leads.append({
            "email": c["email"].strip(),
            "first_name": c.get("first_name", ""),
            "last_name": c.get("last_name", ""),
            "company_name": normalize_company(c.get("company_name", "")),
            "linkedin_profile": c.get("linkedin_url", ""),
            "custom_fields": {
                "social_proof": c.get("social_proof", ""),
                "title": c.get("title", ""),
                "country": c.get("country", ""),
                "segment": c.get("segment", ""),
            },
        })
    total = 0
    for i in range(0, len(leads), 100):
        batch = leads[i:i+100]
        r = httpx.post(f"{SMARTLEAD_BASE}/leads", params={**sl_params(), "campaign_id": campaign_id},
                       json={"lead_list": batch}, timeout=60)
        if r.status_code == 200:
            total += len(batch)
        elif r.status_code == 429:
            time.sleep(70)
            r2 = httpx.post(f"{SMARTLEAD_BASE}/leads", params={**sl_params(), "campaign_id": campaign_id},
                            json={"lead_list": batch}, timeout=60)
            if r2.status_code == 200:
                total += len(batch)
        time.sleep(1)
    print(f"  Uploaded: {total}/{len(leads)}")
    return total

def step12_upload(contacts: list[dict]):
    print(f"\n{'='*60}")
    print(f"STEP 12: SmartLead Upload")
    print(f"{'='*60}")

    if not SMARTLEAD_API_KEY:
        print("  ERROR: SMARTLEAD_API_KEY not set")
        sys.exit(1)

    with_email = [c for c in contacts if c.get("email", "").strip()]
    seen = set()
    deduped = []
    for c in with_email:
        e = c["email"].strip().lower()
        if e not in seen:
            seen.add(e)
            deduped.append(c)

    by_segment = {}
    for c in deduped:
        seg = c.get("segment", "UNKNOWN")
        by_segment.setdefault(seg, []).append(c)

    NAMES = {
        "INFLUENCER_PLATFORMS": "INFLUENCER PLATFORMS v4",
        "IM_FIRST_AGENCIES": "IM-FIRST AGENCIES v4",
    }
    log = load_json(UPLOAD_LOG) or {}

    for seg, seg_contacts in sorted(by_segment.items()):
        name = NAMES.get(seg, f"OnSocial {seg} v4")
        print(f"\n  --- {name}: {len(seg_contacts)} leads ---")
        print(f"  ★ CHECKPOINT: Create '{name}'?")
        if sys.stdin.isatty():
            print("  Enter to continue, Ctrl+C to abort.")
            input()
        else:
            print("  Non-interactive mode — proceeding.")

        cid = log.get(seg, {}).get("campaign_id")
        if not cid:
            cid = create_campaign(name)
            httpx.post(f"{SMARTLEAD_BASE}/campaigns/{cid}/email-accounts", params=sl_params(),
                       json={"emailAccountIDs": SMARTLEAD_EMAIL_ACCOUNTS}, timeout=30)
            httpx.post(f"{SMARTLEAD_BASE}/campaigns/{cid}/schedule", params=sl_params(), json={
                "timezone": "America/New_York", "days_of_the_week": [1,2,3,4,5],
                "start_hour": "08:00", "end_hour": "18:00",
                "min_time_btw_emails": 15, "max_new_leads_per_day": 500,
            }, timeout=30)

        uploaded = upload_leads(cid, seg_contacts)
        log[seg] = {"campaign_id": cid, "campaign_name": name,
                     "leads": uploaded, "at": ts()}
        save_json(UPLOAD_LOG, log)

    print(f"\n  ⚠ Campaigns in DRAFTED status. Add v4 sequences + activate manually.")
    print(f"  ⚠ Use {{{{social_proof}}}} variable in sequences.")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

STEPS = ["start", "blacklist", "prefilter", "scrape", "analyze", "verify",
         "export", "people", "findymail", "upload"]

def main():
    p = argparse.ArgumentParser(description="OnSocial Clay→SmartLead (Platforms + Agencies)")
    p.add_argument("--project-id", type=int, default=PROJECT_ID)
    p.add_argument("--segment", choices=list(CLAY_FILTERS.keys()))
    p.add_argument("--from-step", choices=STEPS, default="start")
    p.add_argument("--run-id", type=int, help="Resume existing run")
    p.add_argument("--apollo-csv", help="Path to Apollo People CSV (single file, or platforms file)")
    p.add_argument("--apollo-csv-agencies", help="Path to Apollo People CSV for IM_FIRST_AGENCIES segment")
    p.add_argument("--max-companies", type=int, default=500)
    p.add_argument("--max-findymail", type=int, default=1500)
    p.add_argument("--prompt-file", help="Custom analysis prompt file")
    p.add_argument("--prompt-id", type=int, default=PROMPT_ID, help="Prompt ID from gathering_prompts (default: PROMPT_ID)")
    p.add_argument("--re-analyze", action="store_true", help="Re-analyze with new prompt")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    print(f"OnSocial v4 Pipeline — {ts()}")
    print(f"State: {STATE_DIR}")

    prompt_text = DEFAULT_ANALYSIS_PROMPT
    prompt_id = args.prompt_id
    if args.prompt_file:
        prompt_text = Path(args.prompt_file).read_text(encoding="utf-8")
        prompt_id = None  # custom file overrides prompt_id
        print(f"Custom prompt loaded: {args.prompt_file}")
    elif prompt_id:
        print(f"Using prompt_id={prompt_id} from gathering_prompts")

    run_id = args.run_id or load_state().get("run_id")

    # Re-analyze mode
    if args.re_analyze:
        if not run_id:
            print("ERROR: --run-id required for --re-analyze")
            sys.exit(1)
        step5_reanalyze(run_id, prompt_text=prompt_text, prompt_id=prompt_id)
        return

    steps = STEPS[STEPS.index(args.from_step):]

    if args.dry_run:
        config = CLAY_FILTERS.get(args.segment, {})
        filters = config.get("filters", {})
        print(f"\n  DRY RUN — no API calls")
        print(f"  Segment: {args.segment} ({config.get('segment', '?')})")
        print(f"  Countries: {', '.join(filters.get('country_names', []))}")
        print(f"  Max results: {filters.get('max_results', '?')}")
        print(f"  Employees: {filters.get('minimum_member_count', '?')}-{filters.get('maximum_member_count', '?')}")
        print(f"  Steps: {' → '.join(steps)}")
        print(f"  Prompt: {prompt_text[:80]}...")
        return

    # Steps 0-8: Backend API
    if "start" in steps:
        if not args.segment:
            print("ERROR: --segment required for start")
            sys.exit(1)
        run_id = step0_start(args.segment, args.project_id)
        # Wait for Clay to finish gathering (resilient to connection errors)
        print("\n  Waiting for Clay gathering to complete...")
        conn_errors = 0
        while True:
            time.sleep(15)
            try:
                r = httpx.get(f"{BACKEND_BASE}/api/pipeline/gathering/runs/{run_id}",
                              headers=BACKEND_HEADERS, timeout=30)
                phase = r.json().get("current_phase", "")
                conn_errors = 0  # reset on success
                if phase != "gather":
                    print(f"  Phase: {phase}")
                    break
                print("  ..still gathering")
            except (httpx.ConnectError, httpx.ReadError, httpx.TimeoutException) as e:
                conn_errors += 1
                print(f"  ..connection error ({conn_errors}/10): {type(e).__name__}")
                if conn_errors >= 10:
                    print("  Too many connection errors. Run may still be processing.")
                    print(f"  Resume later: --from-step blacklist --run-id {run_id}")
                    sys.exit(1)
                time.sleep(15)  # extra wait for backend restart

    if "blacklist" in steps and run_id:
        # Backend auto-runs blacklist after gather. Check if already at CP1.
        run_info = api("get", f"/pipeline/gathering/runs/{run_id}", raise_on_error=False)
        current_phase = run_info.get("current_phase", "")
        if current_phase == "awaiting_scope_ok":
            print(f"\n  Run #{run_id} already at CP1 (blacklist done automatically)")
            # Find pending gate
            gates_resp = api("get", f"/pipeline/gathering/approval-gates?project_id={args.project_id}",
                             raise_on_error=False)
            gates_list = gates_resp if isinstance(gates_resp, list) else gates_resp.get("items", [])
            pending = [g for g in gates_list
                       if g.get("gathering_run_id") == run_id and g.get("status") == "pending"]
            if pending:
                gate = pending[0]
                gate_id = gate["id"]
                scope = gate.get("scope", {})
                save_state(run_id, "awaiting_scope_ok", gate_id=gate_id)
                print(f"\n  ★ CHECKPOINT 1 — gate #{gate_id}")
                print(f"  Scope: {json.dumps(scope, indent=2)[:1000]}")
                raw = run_info.get("raw_results_count", 0)
                new = run_info.get("new_companies_count", 0)
                passed = scope.get("passed", 0)
                print(f"  Raw results: {raw}, New: {new}, Passed blacklist: {passed}")
                if passed == 0 and raw == 0:
                    print(f"\n  ⚠ Clay returned 0 companies. Consider cancelling this run.")
                print("\n  >>> Claude Code will review CP1 and decide <<<")
                print(f"  Pausing. Run with --from-step prefilter --run-id {run_id} after approval.")
                return
        elif current_phase not in ("gathered", "gather"):
            print(f"\n  Run #{run_id} at phase '{current_phase}' — skipping blacklist step")
        else:
            cp1 = step2_blacklist(run_id)
            if cp1.get("gate_id"):
                print("\n  >>> Claude Code will review CP1 and decide <<<")
                print(f"  Pausing. Run with --from-step prefilter --run-id {run_id} after approval.")
                return

    if "prefilter" in steps and run_id:
        step3_prefilter(run_id)

    if "scrape" in steps and run_id:
        step4_scrape(run_id)

    if "analyze" in steps and run_id:
        cp2 = step5_analyze(run_id, prompt_text=prompt_text, prompt_id=prompt_id)
        if cp2.get("gate_id"):
            print(f"\n  >>> Claude Code will review CP2 (target rate: {cp2.get('target_rate', 0)*100:.1f}%) <<<")
            print(f"  If OK: approve gate, then --from-step verify --run-id {run_id}")
            print(f"  If bad: --re-analyze --run-id {run_id} --prompt-file new_prompt.txt")
            return

    if "verify" in steps and run_id:
        cp3 = step6_prepare_verify(run_id)
        if cp3.get("gate_id"):
            print("\n  >>> Claude Code will review CP3 (cost) <<<")
            print(f"  After approval: --from-step export --run-id {run_id}")
            return

    # Steps 9-12: Local execution
    if "export" in steps:
        targets = step9_export_targets(args.project_id, force=args.force)
    else:
        targets = load_json(TARGETS_FILE) or []

    if "people" in steps:
        if args.apollo_csv:
            # Support two CSVs by segment
            all_contacts = []
            if args.apollo_csv:
                seg_override = "INFLUENCER_PLATFORMS" if args.apollo_csv_agencies else None
                c1 = step10_import_apollo_csv(args.apollo_csv, targets, force=args.force,
                                               segment_override=seg_override)
                all_contacts.extend(c1)
            if args.apollo_csv_agencies:
                c2 = step10_import_apollo_csv(args.apollo_csv_agencies, targets, force=True,
                                               segment_override="IM_FIRST_AGENCIES")
                all_contacts.extend(c2)
            if args.apollo_csv_agencies:
                # Merge and re-save
                save_json(CONTACTS_FILE, all_contacts)
                print(f"\n  Combined: {len(all_contacts)} contacts from both segments")
            contacts = all_contacts
        else:
            print("\n  ERROR: --apollo-csv required for people step")
            print("  Export contacts from Apollo People Search UI, then:")
            print(f"    python3 {Path(__file__).name} --from-step people \\")
            print(f"      --apollo-csv platforms_export.csv \\")
            print(f"      --apollo-csv-agencies agencies_export.csv")
            sys.exit(1)
    else:
        contacts = load_json(CONTACTS_FILE) or load_json(ENRICHED_FILE) or []

    if "findymail" in steps:
        contacts = asyncio.run(step11_findymail(contacts, max_contacts=args.max_findymail, force=args.force))
    else:
        contacts = load_json(ENRICHED_FILE) or contacts

    if "upload" in steps:
        step12_upload(contacts)


if __name__ == "__main__":
    main()
