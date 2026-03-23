# Clay Origin Detection — Language & University Filters

## Core Insight

Clay's **language filter** and **university/education filter** are the most reliable signals for identifying a person's country of origin, regardless of where they currently live/work.

## Proven Example: Pakistan Origin Detection

**Target**: Murtaza Hussain (linkedin.com/in/m-murtaza-hussain/)
- Currently: Project Manager at Australian Federal Government, Greater Melbourne Area
- Actually from: Pakistan

**How Clay finds him**:

### Method 1: University Filter
- Filter: Education → School names = "University of the Punjab"
- Location: Melbourne
- Result: 420 results including Murtaza Hussain (#2)
- His LinkedIn confirms: Bachelor's Degree, Economics from University of the Punjab

### Method 2: Language Filter
- Filter: Languages = "Urdu"
- Location: Melbourne
- Result: 3,838 results including Murtaza Hussain (#1)
- Broader net but same person surfaces

### Key Takeaway
Both filters independently identify the same person. University is more precise (420 vs 3,838 results) but language catches more people who didn't list their university.

## Origin Signal Reliability

| Signal | Precision | Volume | Notes |
|--------|-----------|--------|-------|
| University from origin country | Very High | Low-Medium | Definitive proof of origin |
| Language (native/regional) | High | High | Catches diaspora broadly |
| Surname patterns | Medium | Medium | Can overlap across countries |

## Applying to Any Corridor

For any "Country A people working in Country B" search:
1. Identify **universities** from Country A (top 20-30 institutions)
2. Identify **languages** unique to Country A (not shared with neighbors)
3. Set location filter to Country B cities
4. Run both searches, merge and dedup by LinkedIn URL
5. University results = high confidence, Language results = broader coverage

## Example Filter Combinations per Corridor

### UAE-Pakistan
- Universities: University of the Punjab, LUMS, NUST, COMSATS, FAST-NU, etc.
- Languages: Urdu
- Location: Dubai, Abu Dhabi, Sharjah

### Australia-Philippines
- Universities: University of the Philippines, Ateneo de Manila, De La Salle, UST, etc.
- Languages: Tagalog, Filipino, Cebuano
- Location: Sydney, Melbourne, Brisbane, Perth

### Arabic-South Africa
- Universities: University of Cape Town, Stellenbosch, Wits, etc.
- Languages: Afrikaans, Zulu, Xhosa
- Location: Dubai, Doha, Riyadh, Jeddah
