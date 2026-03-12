"""Dynamic segment extraction from campaign names.

Derives business verticals from campaign naming patterns.
Works for any project by stripping project prefix, dates, person names,
location modifiers, and campaign suffixes — then grouping similar segments.
"""
import re
from typing import Dict, List

# Date patterns to strip
_DATE_PATTERNS = [
    r'\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b',   # DD.MM.YY, DD/MM/YYYY
    r'(?:\s+\d{1,2}){2,3}\s*$',               # trailing "27 02 26", "08 03"
]

# Campaign suffixes (follow-up markers, copies, etc.)
_SUFFIX_NOISE = re.compile(
    r'\b(?:FU\d*\+?|LPR|LVPR|copy|RERUN|Re-Run|part\s*\d*|sr)\b',
    re.IGNORECASE,
)

# Location/channel modifiers
_LOCATION_MODS = re.compile(
    r'\b(?:Global|Miami|Latam|Europe|Asia|UK|Singapore|Hong\s*\w*|Cyprus|APAC)\b',
    re.IGNORECASE,
)

# Person names commonly found in campaign names across projects
_PERSON_NAMES = re.compile(
    r'\b(?:Aleks(?:andr[a]?)?|Nikita|Danila|Serge[iy]?|Lisa|Robert|Anna|Katya|'
    r'Eleonora|Andriy|Sophia|Valeriia|Lera|Dias|Elena|Daniel|Arina|Marina|'
    r'Alexandra|Tamara|Aliaksandr[a]?|Andrei|Pavel)\b',
    re.IGNORECASE,
)

# Utility/internal campaigns → "Other"
_UTILITY_CAMPAIGNS = re.compile(
    r'\b(?:Mailboxes?\s*Health\s*[Cc]heck|(?:^|\s)test(?:\s|$)|spam\s*test|'
    r'outreach\d*day|subsequence\s*all\s*but|extra\s*spam)\b',
    re.IGNORECASE,
)

# Words that don't contribute to segment identity (used in grouping)
_NOISE_WORDS = frozenset({
    'a', 'an', 'the', 'and', 'or', 'in', 'of', 'for', 'to', 'de', 'by',
    'y', 'e', 'la', 'el', 'los', 'las', 'con', 'por', 'que',
    'web', 'new', 'app', 'apps', 'sin', 'mails', 'no', 'from',
    'networking', 'msg', 'dm', 'dms', 'pack',
})


def extract_segment(cname: str, project_name: str) -> str:
    """Extract segment label from a single campaign name."""
    cn = cname.strip()

    # Multi-campaign (comma-separated from GetSales) → take first
    if ', ' in cn:
        cn = cn.split(', ')[0].strip()

    project_lower = project_name.lower().strip()
    cn_lower = cn.lower()

    # Strip project name prefix (case-insensitive)
    if cn_lower.startswith(project_lower):
        cn = cn[len(project_lower):].strip()

    # Strip separators and normalize
    cn = cn.lstrip("-_–— ").strip()
    cn = cn.replace('_', ' ')
    cn = cn.replace('&', ' & ')  # ensure & is word-separated

    # Utility campaigns → Other
    if _UTILITY_CAMPAIGNS.search(cn):
        return "Other"

    # Remove content in brackets [...] and parens (...)
    cn = re.sub(r'\s*[\[\(][^\]\)]*[\]\)]', '', cn).strip()

    # Remove hash tags (#612 ...)
    cn = re.sub(r'\s*#\d+.*$', '', cn).strip()

    # Remove date patterns
    for pattern in _DATE_PATTERNS:
        cn = re.sub(pattern, '', cn).strip()

    # Remove trailing standalone numbers
    cn = re.sub(r'\s+\d+\s*$', '', cn).strip()

    # Remove known suffixes
    cn = _SUFFIX_NOISE.sub('', cn).strip()
    cn = re.sub(r'\s*-\s*(?:copy|sr|rerun)\s*$', '', cn, flags=re.IGNORECASE).strip()

    # Remove "Big N" prefix
    cn = re.sub(r'^Big\s+\d+\s+', '', cn, flags=re.IGNORECASE).strip()

    # Remove location modifiers
    cn = _LOCATION_MODS.sub('', cn).strip()

    # Remove person names
    cn = _PERSON_NAMES.sub('', cn).strip()

    # Remove trailing apostrophe-s
    cn = re.sub(r"'s?\s*\d*\s*$", '', cn).strip()

    # Clean up whitespace and edge chars
    cn = re.sub(r'\s+', ' ', cn).strip()
    cn = cn.strip("-_–—&, ")

    if not cn or len(cn) < 2:
        return "Other"

    # Preserve acronyms (short all-caps words like QSR, PSP, AI, SaaS)
    words = cn.split()
    result_words = []
    for w in words:
        if w.isupper() and len(w) <= 5:
            result_words.append(w)  # Keep QSR, PSP, AI, VAS, etc.
        elif w.lower() == 'saas':
            result_words.append('SaaS')
        else:
            result_words.append(w.title())
    return ' '.join(result_words)


def _meaningful_words(text: str) -> frozenset:
    """Extract meaningful words for segment comparison."""
    normalized = text.lower().replace('&', ' ').replace('/', ' ')
    return frozenset(
        w for w in normalized.split()
        if len(w) > 1 and w not in _NOISE_WORDS
    )


def _group_segments(segment_map: Dict[str, str]) -> Dict[str, str]:
    """Group similar extracted segments under canonical names.

    Strategies (in order):
    1. Prefix match: "Telemed" matches "Telemedicine & Checkups"
    2. Word subset match: {"fintech"} in {"performance", "fintech"}
    """
    unique_segs = sorted(
        {v for v in segment_map.values() if v != "Other"},
        key=len,
    )

    # canonical_name → meaningful words
    canonical: Dict[str, str] = {}       # raw_seg → canonical_name
    canon_registry: Dict[str, frozenset] = {}  # canonical_name → words

    for seg in unique_segs:
        seg_lower = seg.lower().replace('&', ' and ')
        seg_words = _meaningful_words(seg)

        if not seg_words:
            canonical[seg] = "Other"
            continue

        best_match = None
        for c_name, c_words in canon_registry.items():
            c_lower = c_name.lower().replace('&', ' and ')

            # Strategy 1: string prefix match
            shorter, longer = sorted([c_lower, seg_lower], key=len)
            if longer.startswith(shorter):
                best_match = c_name
                break

            # Strategy 2: word subset match
            if c_words.issubset(seg_words) or seg_words.issubset(c_words):
                best_match = c_name
                break

            # Strategy 3: word-stem prefix (food→foodtech, telemed→telemedicine)
            for cw in c_words:
                for sw in seg_words:
                    shorter_w, longer_w = sorted([cw, sw], key=len)
                    if len(shorter_w) >= 4 and longer_w.startswith(shorter_w):
                        best_match = c_name
                        break
                if best_match:
                    break

        if best_match:
            canonical[seg] = best_match
        else:
            canonical[seg] = seg
            canon_registry[seg] = seg_words

    # Apply canonical mapping
    return {
        cname: canonical.get(raw_seg, raw_seg) if raw_seg != "Other" else "Other"
        for cname, raw_seg in segment_map.items()
    }


def build_segment_map(campaign_names: List[str], project_name: str) -> Dict[str, str]:
    """Build campaign_name → segment mapping with extraction + grouping."""
    raw_map = {}
    for cname in campaign_names:
        raw_map[cname] = extract_segment(cname, project_name)
    return _group_segments(raw_map)


def build_segment_case_when(segment_map: Dict[str, str], col_expr: str) -> str:
    """Build SQL CASE WHEN expression from segment map."""
    whens = []
    for cname, seg in segment_map.items():
        escaped_name = cname.replace("'", "''")
        escaped_seg = seg.replace("'", "''")
        whens.append(f"WHEN {col_expr} = '{escaped_name}' THEN '{escaped_seg}'")
    if not whens:
        return "'Other'"
    return "CASE " + " ".join(whens) + " ELSE 'Other' END"
