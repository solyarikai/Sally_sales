"""
Device fingerprint pool for Telegram Desktop sessions.

Used when:
1. Adding accounts by phone number (no JSON import → generate fingerprint)
2. Auditing fingerprint uniqueness across accounts
3. Warm-up system (realistic device profiles)

Source: TeleRaptor EASY base (25 entries) + extended pool (75+ entries).
Format matches what Telegram Desktop reports to API: device_model = laptop model code.
"""

import random
from typing import Optional

# --- Device models ---
# Real Windows laptop model identifiers as reported by Telegram Desktop.
# Each string is what Windows WMI returns as the system model.

DEVICE_MODELS = [
    # === Original TeleRaptor pool (25) ===
    "ThinkPadL13",
    "15t-ed002",
    "DW0010",
    "S533EA",
    "R7-3700U",
    "Latitude5401",
    "A315-54K",
    "RZ09-0281CE53",
    "FHD-G15",
    "X512JA",
    "OmenX-17",
    "7DF52EA",
    "81XH",
    "A11SCS",
    "Precision3561",
    "13-aw2000",
    "81UR",
    "XPS13-9380",
    "RZ09-0367",
    "15Z980",
    "ThinkPadT590",
    "Aspire314",
    "DW1084",
    "NP930X2K",
    "C214MA",
    # === Extended pool — Lenovo (15) ===
    "ThinkPadX1Carbon",
    "ThinkPadT480",
    "ThinkPadE15",
    "ThinkPadX390",
    "ThinkPadT14",
    "ThinkPadX270",
    "ThinkPadL14",
    "IdeaPad5-15IIL",
    "Legion5-15ACH",
    "82JU",
    "81Y6",
    "82FG",
    "82B5",
    "82RC",
    "Yoga14s-ARH",
    # === Extended pool — Dell (15) ===
    "Inspiron15-3520",
    "Latitude7420",
    "XPS15-9510",
    "Vostro3500",
    "Latitude5520",
    "Inspiron14-5420",
    "Precision5560",
    "G15-5515",
    "Latitude3420",
    "Inspiron16-5625",
    "XPS17-9710",
    "Latitude7320",
    "Inspiron13-5310",
    "Vostro5402",
    "Precision3551",
    # === Extended pool — HP (15) ===
    "Pavilion15-eg",
    "EliteBook840G8",
    "ProBook450G9",
    "OMEN16-b0",
    "Victus16-d0",
    "EliteBook845G9",
    "ZBook15G6",
    "ProBook440G8",
    "Pavilion14-dv",
    "ENVY13-ba",
    "250G8",
    "255G9",
    "HP14s-dq2",
    "Spectre14-ea",
    "EliteBook830G9",
    # === Extended pool — ASUS (12) ===
    "VivoBook15-X513",
    "ROG-Strix-G15",
    "ZenBook14-UX425",
    "TUF-Gaming-F15",
    "X515JA",
    "VivoBook-S14",
    "ROG-Zephyrus-G14",
    "X412FA",
    "M515DA",
    "FX506LH",
    "UX363JA",
    "K513EA",
    # === Extended pool — Acer (10) ===
    "Aspire5-A515",
    "Nitro5-AN515",
    "Swift3-SF314",
    "TravelMate-P2",
    "Aspire7-A715",
    "Spin5-SP513",
    "Extensa15-EX215",
    "Swift5-SF514",
    "ConceptD3-CN3",
    "PredatorHelios300",
    # === Extended pool — MSI / Samsung / LG / Razer (8) ===
    "GF63-Thin",
    "Modern14-B11M",
    "GS66-Stealth",
    "Katana-GF66",
    "NP950XDB",
    "NP750XDA",
    "16Z90P",
    "RZ09-0421",
]

# --- System versions ---
SYSTEM_VERSIONS = ["Windows 10", "Windows 11"]

# --- Telegram Desktop app versions (recent) ---
# Base pool — updated dynamically by update_app_versions_pool() when GitHub is checked.
APP_VERSIONS = [
    "6.5.1 x64",
    "6.5.2 x64",
    "6.6.0 x64",
    "6.6.1 x64",
    "6.6.2 x64",
    "6.7.0 x64",
    "6.7.1 x64",
]

# Keep only the last N versions in the pool (older ones look suspicious).
_MAX_VERSIONS_IN_POOL = 5


def update_app_versions_pool(latest_raw: str) -> None:
    """Add the latest version to APP_VERSIONS and trim old ones.

    Call this whenever a new version is fetched from GitHub.
    `latest_raw` should be like "6.7.1" (without "x64" suffix).
    """
    global APP_VERSIONS
    full = f"{latest_raw} x64"
    if full not in APP_VERSIONS:
        APP_VERSIONS.append(full)
    # Keep only the most recent versions (sort by semver)
    try:
        sorted_versions = sorted(
            APP_VERSIONS,
            key=lambda v: tuple(int(x) for x in v.replace(" x64", "").split(".")),
        )
        APP_VERSIONS = sorted_versions[-_MAX_VERSIONS_IN_POOL:]
    except (ValueError, IndexError):
        pass


def get_default_app_version() -> str:
    """Return the latest app version string from the pool (for fallbacks)."""
    return APP_VERSIONS[-1] if APP_VERSIONS else "6.7.1 x64"

# --- Language codes ---
# Weighted: en most common for international outreach, then ru, de, etc.
LANG_CODES = [
    "en", "en", "en", "en",  # 40% weight
    "ru", "ru",               # 20% weight
    "de",                     # 10% weight
    "fr",                     # 10% weight
    "es",                     # 10% weight
    "pt",                     # 10% weight
]

SYSTEM_LANG_CODES = {
    "en": ["en-US", "en-GB"],
    "ru": ["ru-RU"],
    "de": ["de-DE"],
    "fr": ["fr-FR"],
    "es": ["es-ES"],
    "pt": ["pt-BR", "pt-PT"],
}


def generate_fingerprint(
    exclude_models: Optional[set] = None,
    lang_code: Optional[str] = None,
) -> dict:
    """Generate a random unique device fingerprint.

    Args:
        exclude_models: Set of device_model strings already in use (for uniqueness).
        lang_code: Force a specific lang_code (e.g., 'ru' for Russian accounts).

    Returns:
        Dict with keys: device_model, system_version, app_version, lang_code, system_lang_code
    """
    available = DEVICE_MODELS
    if exclude_models:
        available = [m for m in DEVICE_MODELS if m not in exclude_models]
        if not available:
            # All models used — fall back to full pool with suffix
            model = random.choice(DEVICE_MODELS)
            suffix = random.randint(100, 999)
            model = f"{model}-{suffix}"
        else:
            model = random.choice(available)
    else:
        model = random.choice(available)

    system_version = random.choice(SYSTEM_VERSIONS)
    app_version = random.choice(APP_VERSIONS)

    if lang_code is None:
        lang_code = random.choice(LANG_CODES)

    sys_langs = SYSTEM_LANG_CODES.get(lang_code, ["en-US"])
    system_lang_code = random.choice(sys_langs)

    return {
        "device_model": model,
        "system_version": system_version,
        "app_version": app_version,
        "lang_code": lang_code,
        "system_lang_code": system_lang_code,
    }


def get_pool_size() -> int:
    """Return total number of unique device models in the pool."""
    return len(DEVICE_MODELS)
