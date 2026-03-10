"""Seed Campaign table with all GetSales automations from hardcoded dict.

This bootstraps the DB so the dynamic flow cache works before the dict is deleted.

Revision ID: 202603060200
Revises: 202603060100
Create Date: 2026-03-06
"""
from alembic import op

revision = "202603060200"
down_revision = "202603060100"
branch_labels = None
depends_on = None

# All GetSales automations from GETSALES_FLOW_NAMES dict (current state)
# Format: (external_id/UUID, name, project_prefix_for_routing)
GETSALES_AUTOMATIONS = [
    # EasyStaff (project 40)
    ("b4188b80-4e23-47df-83cf-29d2654fc943", "EasyStaff - Russian DM [>500 connects]"),
    ("073fbf20-a196-45f2-8f10-d6fde419ee64", "EasyStaff - Qatar - South Africa"),
    ("e98903f7-5617-4e63-a907-618bb7433dd0", "EasyStaff - UAE - India"),
    ("cbf94285-cf1e-4f86-b6bc-9910f9d18ca7", "SquareFi - ES - RUS DMs"),
    # Rizzult (project 22)
    ("4bbd26d3-706b-4168-9262-d70fe09a5b25", "RIzzult_Wellness apps 10 01 26"),
    ("6bfeca8c-23a6-49da-a8e8-b0dacae88857", "Rizzult_shopping_apps"),
    ("df157019-c1fb-4562-b136-b92c9a9c99ab", "RIzzult Cleaning 14 02 26"),
    ("0089aa05-f8a3-4a0b-ab94-00db9603dd7d", "RIzzult Farmacies 14 02 26"),
    ("60b1ab51-5139-4256-a2fa-92bd88252d7d", "RIzzult Streaming 14 02 26"),
    ("779377b5-4856-4f0e-b028-19ebff994dce", "RIzzult Telemed 20 02 26"),
    ("3323b4f3-d0e9-427e-9540-191e10b8d4d7", "RIzzult partner agencies Miami 20 02 26 networking msg"),
    ("8c164da8-d63c-42b9-9a83-1c5e7194d5ba", "RIzzult_Food&Drink apps 02 02 26"),
    ("f917f58a-2b77-4613-9adb-63ca94183dac", "RIzzult_QSR_LPR_20.11.25"),
    ("9515a70b-0020-4955-8bea-9c2f7b904be8", "RIzzult big 5 agencies 27 02 26"),
    ("5a8628e0-f8b5-43f7-9477-0bd825bb7ee5", "RIzzult partner agencies 15 02 26"),
    # Mifort (project 21)
    ("cc73c018-510d-4edc-b41c-59f4dccff6bb", "Mifort Partners BizDevs"),
    ("a8d7562b-fdea-4394-8a39-b40910f5a8af", "Mifort Partners Clutch"),
    ("d793c3dc-78db-46a7-9916-13346d66ce97", "Mifort Partners Salesforce"),
    ("b7930e29-9247-4586-aeb3-eccc6841d18d", "Mifort Partners Java Enterprise"),
    ("04d46b71-9d62-44bd-9c22-0a4cd6cdfc97", "Mifort Partners PHP"),
    ("89961bab-733e-4857-956e-810231c1448c", "Mifort iGaming Providers"),
    ("02469dd6-a727-4ef7-86e7-d85ac2729ed9", "Mifort iGaming Marketing"),
    ("81ed1274-1d39-455f-be37-8548cbc9ae42", "MFT. Marketing New vacs"),
    ("7895a776-a21d-4d3a-9b8a-4b32a03fc857", "MFT. Marketing"),
    ("107ee83a-3259-4ece-a7b7-5319c0605568", "Mifort iGaming Operators"),
    ("c3d72e1c-061a-4b75-92e1-75669d08bcdc", "Mifort Fintech Crypto Clay"),
    # TFP (project 13)
    ("99eab5dd-3abb-4387-8757-7b908a0d7bb2", "TFP - Apparel&fashion--only Dias"),
    ("ce0035f2-0f22-42c9-b84c-d1a71852e3ef", "TFP - France Explee"),
    ("90acfa5f-3ed8-4f23-a7ff-cc494ac0d004", "TFP - UK contacts"),
    ("5bf9a955-e404-4f94-8aa2-904fafc1f98a", "TFP - Who is Next"),
    ("a576670f-2ce6-4810-9918-4753dd4a4e51", "TFP - Zalando contacts"),
    ("2ccbefdb-c1a7-4665-bcc1-630306281b60", "TFP - UK Directories"),
    ("5723168d-15de-486d-a0bb-306d924231c3", "TFP - Fashion brands Italy 3"),
    ("c5ac34f7-cd68-4d4b-abdf-c540d65219a4", "TFP - Li groups contacts"),
    ("bd1f5ffb-2dbe-429a-b0f3-dcab147e4f99", "TFP - Apparel&fashion"),
    # Archistruct (project 24)
    ("1c05ddab-2d69-4735-a3c8-1eb6a9a91dfe", "Archistruct Devs Dubai"),
    ("a8c636e9-c5c1-4426-bd16-35066c112ecb", "Archistruct Devs Dubai NEW"),
    ("7aad9446-7712-4588-8e48-3a1c7f98ac85", "Archistruct Architects 4/12"),
    ("7b8d0ada-e7b7-457a-aa3b-9feb1f2ed56d", "Archistruct Devs outDubai(BV)"),
    # GWC (project 17)
    ("33c589e4-0fc4-4c05-a711-e6196d0cf010", "GWC - ICE Orchestrations Nataliya"),
    ("2cf4a1da-310c-4b24-8c5b-78c688041b09", "GWC - ICE Platforms Post Conf Hugo"),
    # Inxy (project 48)
    ("34faa8f9-0217-486f-a852-77a9a865c0ca", "1 Inxy - Low-risk clients of High-risk PSPs--"),
    ("4e8fdc35-6923-4db5-8502-4ec57db330ab", "INXY - ES - Rus DMs No Title"),
    ("12911a9a-93a3-4b39-8728-4c786b049ab1", "INXY - Rus Data - sin mails - 8,050-10,300"),
    ("0648691b-d26a-4e40-8ef1-c2c2201a6bdd", "INXY - Rus Data - sin mails - up to 8,050"),
    ("76c5d917-ce18-406f-ac73-814581ecdd67", "Inxy - AI Agents"),
    ("0fd373f0-30bd-47e6-820e-5fac66c235a4", "Inxy - Baxity lookalike"),
    ("3af573f2-b19b-48be-b123-3aac0effd527", "Inxy - Baxity lookalike"),
    ("ac55e8bc-4b52-4a69-a97d-9ce6ac1a31aa", "Inxy - Baxity lookalike - no pers"),
    ("3763516d-a11f-4ad2-89bd-2bf98ab4ce97", "Inxy - Creator Platforms"),
    ("c96e9ed9-55b2-4e56-b2b6-0a14af2c3f0d", "Inxy - Creators Economy"),
    ("8362f9d3-d289-4414-bfa2-c62151a457d8", "Inxy - Creators Economy 2 [Danila]"),
    ("55bf249b-3dd7-4f32-bffd-7c6910d287d6", "Inxy - Creators Economy [Danila]"),
    ("745bf464-1bcf-4c17-875d-36cdcece8a23", "Inxy - Creators Platform [Personalization]"),
    ("b7a31e91-9166-41f8-9d16-4c2f8823ba5b", "Inxy - Crypto Payments"),
    ("0b8153f6-9e15-48b5-adc3-02dca13f1b5a", "Inxy - Digital Marketplaces"),
    ("561ce386-0998-47e6-990f-21dbf012f2a0", "Inxy - Digital Marketplaces"),
    ("83194850-ee3f-4f0e-9d33-ef7fe97830ce", "Inxy - EOR"),
    ("f463a98c-632c-4e45-98da-5437930b651f", "Inxy - ES - Rus DM mix"),
    ("70510e25-16ad-4b0f-92da-8ef920168cf2", "Inxy - ES - Rus DMs MIX (RN)"),
    ("c86c53b0-9992-4ba7-b307-cbd4fd2d92e3", "Inxy - ES - Rus DMs sin emails first 2380"),
    ("094ede58-79b3-4e8d-8a92-436353b4eff1", "Inxy - Hostings 2"),
    ("21ff206f-97ac-4bee-9b60-615ba4f4f3af", "Inxy - Investment"),
    ("41857d74-cdb1-43ab-846d-9e8b30f09ed5", "Inxy - Ledokol"),
    ("f9940b3e-69a6-48e2-9229-e2e6f9666cb5", "Inxy - Low-risk clients of High-risk PSPs"),
    ("2080cbba-e6a1-4cdf-a448-d41c978f7d2d", "Inxy - Luma"),
    ("2ebe0504-810c-4782-9f47-82f0eb98fac2", "Inxy - Luma 2"),
    ("f4ee67e5-9b98-430f-8cb8-b1c773cec0f7", "Inxy - Marketplaces"),
    ("c5b356bb-cc5f-41dd-8c5c-2a884b326be1", "Inxy - Mass payout"),
    ("a21a378f-f1e5-4a3e-951a-9f14e909cc1b", "Inxy - Merchants"),
    ("237b6604-da24-473e-91b4-c29e1501759c", "Inxy - Monetization"),
    ("072ea574-267e-4363-aee3-cded84b0d639", "Inxy - PS&FX"),
    ("f62647b1-c054-4434-8402-7adac1c26e64", "Inxy - Russian DM's"),
    ("2f7c3c57-b2ba-4bf3-8671-18d4cb5f3254", "Inxy - SEP"),
    ("c2dd0678-7a0a-42e4-b823-7deae3c2aa42", "Inxy - SaaS"),
    ("c7072067-f246-4024-9b98-1a2d51b6d841", "Inxy - Ticketing"),
    ("3d6d1399-f054-4968-9a41-a708aef93ee5", "Inxy - Token2049"),
    ("3948b8b9-c823-4817-895d-8af7bc16c489", "Inxy - Tokenization"),
    ("fd9f5ea9-a8d7-46e9-ba6c-3e905bf0b908", "Inxy - Tokenization [Personalization]"),
    ("f9c239c3-313f-4c02-9a4c-0550f9d08118", "Inxy - Tokenization [Personalization] 2"),
    ("b6f10ee8-b662-4e3b-8dda-23554070fa47", "Inxy - Trading"),
    ("94747ff5-cc88-4bee-8fa7-989297c8da86", "Inxy - hostings"),
    ("bd1965c4-5136-4b6e-94cb-2062a3b833db", "Inxy P2E"),
    # OnSocial (project 42)
    ("c7465183-9bc3-4bb7-8cb1-854b6b54f37e", "OnSocial | Generic"),
    ("b5307c82-c997-4cc5-84c7-8340b1428fb8", "OnSocial | Marketing agencies"),
    ("2238070f-e038-4209-9c0c-3fddb4946654", "OnSocial | IM platforms & SaaS"),
    # Palark (project 16)
    ("3df443f1-1e7c-4ac9-9636-c95bbc52bb04", "Palark - After ICE 19/02 - Nikita"),
    # EasyStaff Global (project 9)
    ("5d5daa90-2746-470f-952d-66223afd13d6", "EasyStaff - AU - PH"),
    # Deliryo
    ("e567a094-7915-4476-8f69-4f69f1024fed", "Deliryo Недвижимость за рубежом (ОАЭ/Дубай)"),
]

# Project prefix → project_id mapping for routing
_PREFIX_TO_PROJECT = {
    "squarefi - es": 47,
    "squarefi - psp": 46,
    "squarefi - igaming fedor": 46,
    "squarefi - fedor": 46,
    "squarefi - agencies - fedor": 46,
    "squarefi - amazon - fedor": 46,
    "squarefi": 46,
    "easystaff": 40,
    "inxy": 48,
    "1 inxy": 48,
    "rizzult": 22,
    "rizzult_": 22,  # underscore variant
    "mifort": 21,
    "mft": 21,
    "tfp": 13,
    "archistruct": 24,
    "gwc": 17,
    "onsocial": 42,
    "palark": 16,
    "paybis": 15,
    "deliryo": None,  # no project ID yet
}


def _resolve_project_id(name: str) -> int | None:
    """Resolve campaign name to project_id using prefix matching (longest first)."""
    name_lower = name.lower()
    # Sort by prefix length DESC so longest match wins
    for prefix in sorted(_PREFIX_TO_PROJECT.keys(), key=len, reverse=True):
        if name_lower.startswith(prefix):
            return _PREFIX_TO_PROJECT[prefix]
    return None


def upgrade():
    # Insert all GetSales automations into campaigns table
    # Use ON CONFLICT to avoid duplicates (uq_campaign_platform_ext unique index)
    for ext_id, name in GETSALES_AUTOMATIONS:
        project_id = _resolve_project_id(name)
        pid_sql = str(project_id) if project_id else "NULL"
        # Escape single quotes in campaign names
        safe_name = name.replace("'", "''")
        op.execute(f"""
            INSERT INTO campaigns (company_id, project_id, platform, channel, external_id, name, status, resolution_method, resolution_detail, first_seen_at, created_at, updated_at)
            VALUES (1, {pid_sql}, 'getsales', 'linkedin', '{ext_id}', '{safe_name}', 'active', 'seed', 'Seeded from GETSALES_FLOW_NAMES dict', NOW(), NOW(), NOW())
            ON CONFLICT (platform, external_id) WHERE external_id IS NOT NULL
            DO UPDATE SET name = EXCLUDED.name, project_id = COALESCE(campaigns.project_id, EXCLUDED.project_id)
        """)


def downgrade():
    # Remove seeded campaigns (only those with resolution_method='seed')
    op.execute("DELETE FROM campaigns WHERE resolution_method = 'seed' AND platform = 'getsales'")
