#!/usr/bin/env python3
"""OnSocial capacity - FINAL, all numbers verified live 2026-04-23."""

# ============= MAILBOXES (verified) =============
MAILBOXES_COUNT = 17
MSG_PER_DAY = 40
DAILY_CAP = MAILBOXES_COUNT * MSG_PER_DAY  # 680 msgs/workday

# ============= CAMPAIGN DATA (verified via SmartLead API) =============
ACTIVE_STATS = {
    3188673: ("IMAGENCY_SENIOR_LEADERSHIP", 250, 124),  # (API_total, stats_emailed)
    3188672: ("IMAGENCY_CREATIVE_CONTENT", 273, 80),
    3188671: ("IMAGENCY_OPS_ACCOUNT", 149, 74),
    3188670: ("IMAGENCY_FOUNDERS_LATAM", 185, 137),
    3188669: ("IMAGENCY_FOUNDERS_US_CA", 581, 90),
    3169118: ("IMAGENCY_FOUNDERS", 1108, 249),
    3169092: ("IMAGENCY_TECHLEAD", 184, 182),
    3124575: ("IMAGENCY_ACCOUNT_OPS", 453, 227),
    3124571: ("IMAGENCY_CREATIVE", 139, 70),
    3096747: ("INFLUENCER_PLATFORMS_ALL_GEO", 471, 182),
    3096746: ("IM_FIRST_AGENCIES_ALL_GEO", 475, 276),
    3050462: ("IM_FIRST_AGENCIES", 234, 234),
}

DRAFT_LEADS_TOTAL = (
    20
    + 4
    + 62
    + 71
    + 65
    + 7
    + 31
    + 132
    + 103
    + 109  # 3215354..3215199
    + 61
    + 52
    + 103
    + 78
    + 213
    + 342
    + 41
    + 10
    + 69
    + 39  # 3215198..3215185
    + 132
    + 79
    + 102
    + 295
    + 66
    + 294
    + 254  # 3215183..3215177
    + 102
    + 170
    + 5  # 3207897, 3207895, 3123881
)  # 30 DRAFT OnSocial campaigns

# Observed facts (from analyze.py run)
ACTIVE_IN_PIPELINE = 1846  # leads still working through sequence
REPLIED = 46
BOUNCED = 17
FINISHED = 16
DAILY_SEND_ACTUAL = 232  # msgs/workday last 5 working days
BOUNCE_PCT = 0.26
REPLY_PCT = 0.69

# Derived
total_in_active_campaigns = sum(v[1] for v in ACTIVE_STATS.values())  # 4502
already_emailed = sum(v[2] for v in ACTIVE_STATS.values())  # 1925
active_backlog = total_in_active_campaigns - already_emailed  # 2577

EMAILS_PER_LEAD = 2.9
WORKDAYS_PER_MONTH = 22
SEQUENCE_TAIL_WD = 10  # sequence takes ~10 workdays to complete

# ============= PRINT HEADLINE STATE =============
print("=" * 70)
print("  OnSocial SmartLead — Capacity Report")
print("  Live verification: 2026-04-23 (API pulls)")
print("=" * 70)

print(f"""
MAILBOXES (OnSocial pool):
  Active mailboxes:     {MAILBOXES_COUNT} (all bhaskar@onsocial-*, smtp+imap OK)
  Per-mailbox cap:      {MSG_PER_DAY} msgs/day
  Total daily cap:      {DAILY_CAP} msgs/workday
  Monthly cap (22 wd):  {DAILY_CAP * WORKDAYS_PER_MONTH:,} msgs
  Safe cap at 85%:      {int(DAILY_CAP * 0.85)} msgs/workday

CURRENT PIPELINE (12 ACTIVE campaigns):
  Total leads uploaded:         {total_in_active_campaigns:,}
  Already emailed at least 1x:  {already_emailed:,}
    - still active in pipeline:  {ACTIVE_IN_PIPELINE:,}
    - replied (out):             {REPLIED:,}
    - bounced (out):             {BOUNCED:,}
    - finished 3-step seq:       {FINISHED:,}
  >>> ACTIVE BACKLOG (uploaded, NOT yet emailed): {active_backlog:,} leads

DRAFT PIPELINE (30 OnSocial DRAFT campaigns):
  Total leads queued:           {DRAFT_LEADS_TOTAL:,}

SEND RATE (observed last 5 working days):
  Daily average:                {DAILY_SEND_ACTUAL} msgs/workday
  Utilization NOW:              {DAILY_SEND_ACTUAL / DAILY_CAP * 100:.1f}% of 680
  Health:                       bounce {BOUNCE_PCT}% / reply {REPLY_PCT}%
""")

# ============= DEMAND PROJECTIONS =============
print("=" * 70)
print("DEMAND PROJECTIONS — what needs to happen in next month")
print("=" * 70)

# 1. Emails already owed to in-flight (they'll burn ~1.5 emails each over 10 wd)
in_flight_residual = int(ACTIVE_IN_PIPELINE * 1.5)

# 2. Emails for ACTIVE backlog (2577 leads × 2.9 = 7473 emails)
active_backlog_emails = int(active_backlog * EMAILS_PER_LEAD)

# 3. Emails for DRAFT leads (3111 × 2.9 = 9022) — once activated
draft_emails = int(DRAFT_LEADS_TOTAL * EMAILS_PER_LEAD)

# 4. Plus user's planned +1500
NEW_1500 = int(1500 * EMAILS_PER_LEAD)

print(f"""
WHERE THE EMAILS COME FROM (next ~30 days):
  In-flight 1,846 leads will send ~{in_flight_residual:,} more emails (next 10 wd)
  ACTIVE backlog 2,577 leads × 2.9 = {active_backlog_emails:,} emails
  DRAFT 3,111 leads × 2.9 = {draft_emails:,} emails
  +1,500 new leads × 2.9 = {NEW_1500:,} emails
  ----------------------------------------------------
  TOTAL OUTBOUND DEMAND: {in_flight_residual + active_backlog_emails + draft_emails + NEW_1500:,} emails
""")

total_demand = in_flight_residual + active_backlog_emails + draft_emails + NEW_1500


# Scenarios
def scenario(
    label, leads_to_push_this_month, include_active_backlog=True, rollout_wd=22
):
    new_emails = int(leads_to_push_this_month * EMAILS_PER_LEAD)
    if include_active_backlog:
        new_emails += active_backlog_emails
    # + in-flight residual (first 10 wd overlap)
    # Peak = residual (spread over 10wd) + new (spread over rollout_wd)
    peak_daily = in_flight_residual / SEQUENCE_TAIL_WD + new_emails / rollout_wd
    steady_daily = new_emails / rollout_wd
    cap_safe = int(DAILY_CAP * 0.85)

    extra_needed = 0
    if peak_daily > cap_safe:
        extra_needed = int((peak_daily / 0.85 - DAILY_CAP) / MSG_PER_DAY) + 1

    return (
        label,
        leads_to_push_this_month,
        include_active_backlog,
        new_emails,
        peak_daily,
        steady_daily,
        extra_needed,
    )


print("=" * 70)
print("SCENARIOS — how many extra mailboxes needed")
print("=" * 70)

scenarios = [
    scenario(
        "A) Only push DRAFT 3,111 over 22 workdays (BAU, ignore ACTIVE backlog)",
        3111,
        False,
        22,
    ),
    scenario(
        "B) Push DRAFT + ACTIVE backlog = 5,688 leads over 22 wd (realistic)",
        3111,
        True,
        22,
    ),
    scenario(
        "C) Push 4,500 (your stated number, if included backlog) over 22 wd",
        4500,
        False,
        22,
    ),
    scenario(
        "D) Push 4,500 + 1,500 = 6,000 over 22 wd (your +1500 plan)", 6000, False, 22
    ),
    scenario(
        "E) REALISTIC: DRAFT + ACTIVE backlog + 1,500 new = 7,188 over 22 wd",
        3111 + 1500,
        True,
        22,
    ),
]

fmt = "  {:<65} {:>6} {:>6} {:>6} {:>4}"
print(fmt.format("", "leads", "peak/d", "stdy/d", "+box"))
print("-" * 100)
for lbl, leads, inc_bl, em, peak, steady, extra in scenarios:
    print(f"{lbl}")
    print(
        f"  -> new emails: {em:,}   peak: {peak:.0f}/wd   steady: {steady:.0f}/wd   "
        f"need +{extra} mailboxes"
    )
    print()

# ============= ANSWER =============
print("=" * 70)
print("ANSWERS TO YOUR 3 QUESTIONS")
print("=" * 70)

util_pct = DAILY_SEND_ACTUAL / DAILY_CAP * 100
print(f"""
Q1. НАСКОЛЬКО ИСПОЛЬЗУЮТСЯ ЯЩИКИ СЕЙЧАС?
  Ответ: ИСПОЛЬЗУЮТСЯ НА {util_pct:.0f}% (232 msgs/wd из 680).
  Диагноз: ящиков СИЛЬНО избыток — 76% мощности простаивает.
  Причина: 12 ACTIVE кампаний шлют медленно, в основном из-за того что
  2,577 лидов в них загружены но ещё не стартовали отправку. Когда они
  запустятся — загрузка резко вырастет.

Q2. ПОД 4,500 НОВЫХ ЛИДОВ — СКОЛЬКО ЯЩИКОВ НУЖНО?
  Если 4,500 = DRAFT (3,111) + ACTIVE backlog (2,577) ≈ 5,688 лидов:
     Peak:    {scenarios[1][4]:.0f}/wd (при capacity 680)
     Нужно +{scenarios[1][6]} ящиков.
  Если 4,500 = новые сверх текущего (игнор ACTIVE backlog):
     Peak:    {scenarios[2][4]:.0f}/wd
     Нужно +{scenarios[2][6]} ящиков (если есть; 680 почти хватит).

  РЕКОМЕНДАЦИЯ: Взять средний сценарий B (DRAFT+backlog+0) = +{scenarios[1][6]} mailboxes

Q3. ПЛЮС +1,500 СВЕРХУ (итого +6,000 нагрузки)?
  Scenario D (чистые 6000, без backlog):   +{scenarios[3][6]} ящиков
  Scenario E (realistic DRAFT+BL+1500):    +{scenarios[4][6]} ящиков

  РЕКОМЕНДАЦИЯ: +{scenarios[4][6]} ящиков (по 40 msg/day с warmup 14 дней).

ИТОГО:
  • Ящиков сейчас:              17  (используются на {util_pct:.0f}%)
  • Под план +4,500:            нужно +{scenarios[1][6]} ящиков  (BAU)
  • Под план +6,000 (4500+1500): нужно +{scenarios[4][6]} ящиков (realistic)

  Timeline: новые ящики требуют 14 дней warmup до 40 msg/day.
  Рекомендую заказать {max(scenarios[1][6], scenarios[4][6])} ящиков ПРЯМО СЕЙЧАС, чтобы
  через 2 недели они вышли на full capacity и ты смог запустить DRAFT
  кампании без throttling.
""")
