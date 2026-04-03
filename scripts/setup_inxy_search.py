"""
Setup Inxy (project TBD) search config — gaming skins/items companies for crypto paygate.

Inxy offers a crypto payment gateway. Target: companies selling game skins,
loot boxes, in-game items, and digital gaming goods that could integrate
Inxy's crypto payments.

Only LOW RISK geos from Inxy's compliance sheet (no UK, no USA).

Scrape method: apify_proxy (Apify residential proxy via httpx, no Crona).

Run on Hetzner:
  docker exec leadgen-backend python /scripts/setup_inxy_search.py
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, "/app")
os.chdir("/app")

# Will be determined after checking if project exists or needs creation
PROJECT_NAME = "Inxy"
COMPANY_ID = 1

# Low-risk geos from compliance sheet, excluding UK/USA and tiny territories
# Focus on countries where gaming/esports marketplaces actually operate
LOW_RISK_GEOS = {
    "germany": {"country_en": "Germany", "cities_en": ["Berlin", "Hamburg", "Munich", "Frankfurt", "Cologne"]},
    "france": {"country_en": "France", "cities_en": ["Paris", "Lyon", "Marseille"]},
    "sweden": {"country_en": "Sweden", "cities_en": ["Stockholm", "Gothenburg", "Malmo"]},
    "finland": {"country_en": "Finland", "cities_en": ["Helsinki", "Espoo", "Tampere"]},
    "denmark": {"country_en": "Denmark", "cities_en": ["Copenhagen", "Aarhus"]},
    "norway": {"country_en": "Norway", "cities_en": ["Oslo", "Bergen"]},
    "canada": {"country_en": "Canada", "cities_en": ["Toronto", "Vancouver", "Montreal"]},
    "australia": {"country_en": "Australia", "cities_en": ["Sydney", "Melbourne", "Brisbane"]},
    "japan": {"country_en": "Japan", "cities_en": ["Tokyo", "Osaka", "Yokohama"]},
    "new_zealand": {"country_en": "New Zealand", "cities_en": ["Auckland", "Wellington"]},
    "austria": {"country_en": "Austria", "cities_en": ["Vienna", "Graz"]},
    "belgium": {"country_en": "Belgium", "cities_en": ["Brussels", "Antwerp"]},
    "ireland": {"country_en": "Ireland", "cities_en": ["Dublin", "Cork"]},
    "switzerland": {"country_en": "Switzerland", "cities_en": ["Zurich", "Geneva", "Basel"]},
    "iceland": {"country_en": "Iceland", "cities_en": ["Reykjavik"]},
    "estonia": {"country_en": "Estonia", "cities_en": ["Tallinn"]},
    "liechtenstein": {"country_en": "Liechtenstein", "cities_en": ["Vaduz"]},
    "andorra": {"country_en": "Andorra", "cities_en": ["Andorra la Vella"]},
    "san_marino": {"country_en": "San Marino", "cities_en": ["San Marino"]},
}

TARGET_SEGMENTS = """
Inxy — Crypto Payment Gateway for Gaming Digital Goods

TARGET COMPANIES: Online platforms and marketplaces that sell digital gaming goods
and could benefit from adding cryptocurrency as a payment method.

SEGMENT 1 (Priority 1): Game Skin Marketplaces
- Platforms selling CS2/CSGO skins, Dota 2 items, TF2 items, Rust skins
- Third-party skin trading/marketplace platforms
- P2P skin trading platforms
- Examples of what we look for: skin marketplaces, item trading sites
- Keywords: "buy skins", "sell skins", "skin marketplace", "trade skins", "CS2 skins", "CSGO marketplace"

SEGMENT 2 (Priority 1): Loot Box / Case Opening Sites
- Case/box opening platforms (CS2 cases, virtual cases)
- Gambling-style case opening sites (if not pure casino)
- Platforms where users open cases/boxes for virtual items
- Keywords: "case opening", "open cases", "loot box", "unbox skins"

SEGMENT 3 (Priority 2): In-Game Item / Virtual Goods Marketplaces
- Platforms selling in-game currency, accounts, items, boosts
- Game key marketplaces and digital game stores
- Virtual goods platforms for multiple games
- NFT gaming marketplaces selling in-game assets
- Keywords: "buy game items", "virtual goods", "game marketplace", "digital items"

SEGMENT 4 (Priority 2): Gaming Top-Up / Gift Card Platforms
- Platforms selling game credits, top-ups, gift cards
- Steam wallet, PlayStation Store, Xbox credits resellers
- Gaming voucher and prepaid card platforms
- Keywords: "game top up", "gaming credits", "gift cards gaming", "steam wallet"

GEOGRAPHY: Only LOW RISK countries per Inxy compliance:
Australia, Austria, Belgium, Canada, Denmark, Estonia, Finland, France,
Germany, Iceland, Ireland, Japan, Liechtenstein, New Zealand, Norway,
Sweden, Switzerland, Andorra, San Marino.
NO UK. NO USA.

NEGATIVE — ALWAYS EXCLUDE:
- Pure gambling/casino/betting sites (sports betting, poker, slots, roulette)
- Game development studios (they make games, not sell items)
- Esports teams/organizations (they compete, not sell goods)
- Gaming news/media sites
- Game review sites, forums, wikis
- Hardware/peripheral companies
- Streaming platforms (Twitch, YouTube Gaming)
- General e-commerce not focused on gaming
- Payment processors / fintech competitors

IMPORTANT SCORING NOTES:
- A company MUST sell digital gaming goods (skins, items, cases, keys, top-ups)
- Having "gaming" in the name is NOT enough — must be a marketplace/shop
- Crypto-native gaming platforms are EXTRA valuable (already use crypto)
- Global platforms are fine even if HQ is in a non-listed country, as long as they serve listed geos
"""

SEARCH_CONFIG = {
    "segments": {
        "skin_marketplaces": {
            "priority": 1,
            "label_en": "Game Skin Marketplaces",
            "geos": {geo_key: geo for geo_key, geo in LOW_RISK_GEOS.items()
                     if geo_key in ("germany", "france", "sweden", "finland", "denmark",
                                     "canada", "australia", "austria", "switzerland")},
            "vars": {
                "game": ["CS2", "CSGO", "Dota 2", "TF2", "Rust", "Steam"],
                "item_type": ["skins", "items", "knives", "gloves", "stickers"],
                "action": ["buy", "sell", "trade", "marketplace"],
            },
            "templates_en": [
                "{action} {game} {item_type}",
                "{game} skin marketplace",
                "{game} {item_type} trading platform",
                "buy {game} {item_type} online",
                "{game} skin shop",
            ],
        },
        "case_opening": {
            "priority": 1,
            "label_en": "Case Opening / Loot Box Platforms",
            "geos": {geo_key: geo for geo_key, geo in LOW_RISK_GEOS.items()
                     if geo_key in ("germany", "sweden", "finland", "denmark",
                                     "canada", "australia", "switzerland")},
            "vars": {
                "game": ["CS2", "CSGO", "CS:GO"],
                "action": ["case opening", "open cases", "unbox", "loot box"],
            },
            "templates_en": [
                "{game} {action} site",
                "{action} {game} skins",
                "online {action} platform",
                "virtual case opening website",
            ],
        },
        "virtual_goods": {
            "priority": 2,
            "label_en": "In-Game Items & Virtual Goods",
            "geos": {geo_key: geo for geo_key, geo in LOW_RISK_GEOS.items()
                     if geo_key in ("germany", "france", "sweden", "canada",
                                     "australia", "japan", "new_zealand")},
            "vars": {
                "game": ["World of Warcraft", "Fortnite", "Roblox", "Minecraft", "League of Legends", "Valorant", "FIFA", "Path of Exile"],
                "product": ["items", "accounts", "currency", "gold", "coins", "boosting"],
            },
            "templates_en": [
                "buy {game} {product}",
                "{game} {product} marketplace",
                "sell {game} {product} online",
                "gaming virtual goods marketplace",
                "buy game accounts online",
            ],
        },
        "topup_giftcards": {
            "priority": 2,
            "label_en": "Gaming Top-Up & Gift Cards",
            "geos": {geo_key: geo for geo_key, geo in LOW_RISK_GEOS.items()
                     if geo_key in ("germany", "france", "canada", "australia",
                                     "japan", "switzerland", "austria", "belgium")},
            "vars": {
                "platform": ["Steam", "PlayStation", "Xbox", "Nintendo", "Epic Games", "Riot Games"],
                "product": ["gift card", "wallet code", "top up", "prepaid card", "credits"],
            },
            "templates_en": [
                "buy {platform} {product}",
                "{platform} {product} online",
                "gaming gift cards marketplace",
                "buy game codes online",
                "digital game keys store",
            ],
        },
    },
    "doc_keywords": [
        # === SKIN MARKETPLACES (high-signal curated queries) ===
        ["skin_marketplaces", None, "en", [
            "CS2 skin marketplace buy sell",
            "CSGO skins trading platform",
            "buy CS2 skins with crypto",
            "Dota 2 items marketplace",
            "Rust skins marketplace",
            "TF2 items trading",
            "Steam marketplace alternative",
            "P2P skin trading platform",
            "buy cheap CS2 skins",
            "sell CSGO skins for money",
            "instant skin cashout",
            "skin trading bot",
            "csgo float checker marketplace",
            "buy knife csgo cheap",
            "buy csgo gloves",
            "steam trade bot",
            "csgo skin deposit site",
            "sell dota items for real money",
            "rust skin shop",
        ]],
        # === CASE OPENING ===
        ["case_opening", None, "en", [
            "CS2 case opening site",
            "CSGO case opening online",
            "open CS2 cases with crypto",
            "virtual case opening platform",
            "case battle site",
            "csgo case simulator real skins",
            "online case unboxing",
            "cs2 case opening website",
            "csgo daily free case",
            "upgrade skins case opening",
            "provably fair case opening",
        ]],
        # === VIRTUAL GOODS ===
        ["virtual_goods", None, "en", [
            "buy game accounts online",
            "gaming marketplace virtual goods",
            "buy WoW gold",
            "buy Fortnite accounts",
            "Roblox items marketplace",
            "buy game currency cheap",
            "MMO gold buying",
            "game item marketplace crypto",
            "NFT gaming marketplace",
            "play to earn marketplace",
            "buy in-game items",
            "sell game accounts safely",
            "boosting service marketplace",
            "buy League of Legends account",
            "Valorant account marketplace",
            "FIFA coins buy",
            "Path of Exile currency shop",
        ]],
        # === TOP-UP / GIFT CARDS ===
        ["topup_giftcards", None, "en", [
            "buy Steam gift card with crypto",
            "gaming gift cards cryptocurrency",
            "buy PlayStation gift card online",
            "Xbox gift card cheap",
            "Nintendo eShop card buy",
            "buy game keys online",
            "digital game code marketplace",
            "cheap game keys store",
            "buy Steam wallet code",
            "game key reseller",
            "game top up with Bitcoin",
            "buy Epic Games gift card",
        ]],
    ],
}

ANTI_KEYWORDS = [
    # Pure gambling
    "casino", "poker", "slots", "roulette", "blackjack", "sports betting",
    "betting site", "bookmaker", "sportsbook",
    # Game dev, not marketplace
    "game engine", "game development studio", "game developer SDK",
    "unity asset store", "unreal engine",
    # Esports org
    "esports team", "esports organization", "competitive gaming team",
    # Media/content
    "gaming news", "game review", "game wiki", "game guide",
    "streaming platform", "twitch",
    # Hardware
    "gaming mouse", "gaming keyboard", "gaming chair", "gaming monitor",
    "gaming headset", "gaming PC build",
    # Non-gaming e-commerce
    "general merchandise", "fashion", "clothing", "grocery",
    # Competitors / fintech
    "payment processor", "payment gateway", "merchant services",
]


async def main():
    from app.db import async_session_maker
    from sqlalchemy import select
    from app.models.domain import ProjectSearchKnowledge
    from app.models.contact import Project

    async with async_session_maker() as session:
        # Check if Inxy project already exists
        result = await session.execute(
            select(Project).where(Project.name == PROJECT_NAME, Project.company_id == COMPANY_ID)
        )
        project = result.scalar_one_or_none()

        if project:
            print(f"Found existing project: {project.name} (ID {project.id})")
        else:
            # Create new project
            project = Project(
                company_id=COMPANY_ID,
                name=PROJECT_NAME,
                description="Crypto payment gateway — find gaming companies selling skins, items, cases, top-ups",
            )
            session.add(project)
            await session.flush()
            print(f"Created new project: {project.name} (ID {project.id})")

        # Update target segments
        project.target_segments = TARGET_SEGMENTS

        # Set auto_enrich_config with apify_proxy scraping
        project.auto_enrich_config = {
            "auto_extract": True,
            "auto_apollo": False,
            "apollo_titles": ["CEO", "Founder", "CTO", "Co-Founder", "Head of Payments", "COO"],
            "apollo_max_people": 5,
            "apollo_max_credits": 50,
            "scrape_method": "apify_proxy",  # Use Apify residential proxy, not Crona
        }

        await session.flush()
        project_id = project.id

        # Upsert ProjectSearchKnowledge
        result = await session.execute(
            select(ProjectSearchKnowledge).where(
                ProjectSearchKnowledge.project_id == project_id
            )
        )
        knowledge = result.scalar_one_or_none()

        if not knowledge:
            knowledge = ProjectSearchKnowledge(project_id=project_id)
            session.add(knowledge)

        knowledge.search_config = SEARCH_CONFIG
        knowledge.anti_keywords = ANTI_KEYWORDS

        await session.commit()

        # Verify
        print(f"\n=== Inxy Search Config (Project {project_id}) ===")
        print(f"Segments: {list(SEARCH_CONFIG['segments'].keys())}")
        total_doc_kw = sum(len(dk[3]) for dk in SEARCH_CONFIG["doc_keywords"])
        print(f"Doc keywords: {total_doc_kw} curated queries across {len(SEARCH_CONFIG['doc_keywords'])} groups")
        print(f"Anti-keywords: {len(ANTI_KEYWORDS)}")
        print(f"Scrape method: apify_proxy")
        print(f"Target segments: {len(TARGET_SEGMENTS)} chars")

        # Count template query combos
        total_combos = 0
        for seg_key, seg in SEARCH_CONFIG["segments"].items():
            geos = seg.get("geos", {})
            total_combos += len(geos)
        print(f"Segment x Geo combos: {total_combos}")

        print(f"\nReady! Run search via UI or API:")
        print(f"  POST /search/projects/{project_id}/batch-segments")
        print(f'  {{"search_engine": "yandex_api", "max_concurrent": 2}}')


if __name__ == "__main__":
    asyncio.run(main())
