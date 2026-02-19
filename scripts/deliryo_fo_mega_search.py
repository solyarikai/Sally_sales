"""
Deliryo MEGA Search — Lookalikes to Рэй (rayfamilyoffice.com) and Октан-Брокер (octan.ru).

RU ONLY. ALL 84 cities × ALL 76 regions.

Target profile:
- Рэй: фэмили офис, управление семейным капиталом, мультифэмили офис
- Октан: независимый брокер, доверительное управление, алготрейдинг,
  инвестиционный советник, QUIK, лицензия ЦБ, НАУФОР

Keywords sourced from:
  https://docs.google.com/document/d/1wkGtwFwM7AZnE0isIxqwLj8Nx2o7c33bdgHsXsTgENA

Strategy:
- Yandex: core terms × all cities/regions (cheap, ~$0.25/1K)
- Google: same RU queries (different algo, different results) (~$3.50/1K)
"""
import asyncio
import sys
import os
import logging

sys.path.insert(0, '/app')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy import select, text as sql_text
from app.db import async_session_maker
from app.models.domain import SearchJob, SearchJobStatus, SearchEngine, SearchQuery, SearchQueryStatus
from app.models.contact import Project

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

PROJECT_ID = 18
COMPANY_ID = 1

# ====================================================================
# ALL RUSSIAN CITIES (84 federal subject capitals + wealthy cities)
# ====================================================================

ALL_CITIES = [
    "Москва", "Санкт-Петербург", "Екатеринбург", "Новосибирск", "Казань",
    "Нижний Новгород", "Красноярск", "Краснодар", "Самара", "Ростов-на-Дону",
    "Тюмень", "Сочи", "Пермь", "Воронеж", "Уфа", "Челябинск", "Владивосток",
    "Омск", "Иркутск", "Хабаровск", "Калининград", "Барнаул", "Томск",
    "Кемерово", "Саратов", "Тольятти", "Мурманск", "Ярославль", "Рязань",
    "Тула", "Липецк", "Белгород", "Ставрополь", "Махачкала", "Волгоград",
    "Оренбург", "Сургут", "Ханты-Мансийск", "Южно-Сахалинск", "Петрозаводск",
    "Калуга", "Набережные Челны", "Астрахань", "Пенза", "Ульяновск", "Брянск",
    "Курск", "Орёл", "Смоленск", "Тверь", "Кострома", "Иваново", "Владимир",
    "Вологда", "Архангельск", "Сыктывкар", "Псков", "Великий Новгород",
    "Чебоксары", "Йошкар-Ола", "Саранск", "Якутск", "Благовещенск", "Чита",
    "Улан-Удэ", "Кызыл", "Абакан", "Горно-Алтайск", "Элиста", "Нальчик",
    "Владикавказ", "Грозный", "Черкесск", "Майкоп", "Биробиджан", "Анадырь",
    "Магадан", "Петропавловск-Камчатский", "Салехард", "Нарьян-Мар",
    "Новороссийск", "Нижний Тагил", "Магнитогорск", "Норильск",
]

# ====================================================================
# ALL RUSSIAN REGIONS (76 federal subjects)
# ====================================================================

ALL_REGIONS = [
    "Московская область", "Ленинградская область", "Свердловская область",
    "Новосибирская область", "Республика Татарстан", "Нижегородская область",
    "Красноярский край", "Краснодарский край", "Самарская область",
    "Ростовская область", "Тюменская область", "Пермский край",
    "Воронежская область", "Республика Башкортостан", "Челябинская область",
    "Приморский край", "Омская область", "Иркутская область",
    "Хабаровский край", "Калининградская область", "Алтайский край",
    "Томская область", "Кемеровская область", "Саратовская область",
    "Мурманская область", "Ярославская область", "Рязанская область",
    "Тульская область", "Липецкая область", "Белгородская область",
    "Ставропольский край", "Республика Дагестан", "Волгоградская область",
    "Оренбургская область", "Ханты-Мансийский АО", "Сахалинская область",
    "Республика Карелия", "Калужская область", "Астраханская область",
    "Пензенская область", "Ульяновская область", "Брянская область",
    "Курская область", "Орловская область", "Смоленская область",
    "Тверская область", "Костромская область", "Ивановская область",
    "Владимирская область", "Вологодская область", "Архангельская область",
    "Республика Коми", "Псковская область", "Новгородская область",
    "Чувашская Республика", "Республика Марий Эл", "Республика Мордовия",
    "Республика Саха", "Амурская область", "Забайкальский край",
    "Республика Бурятия", "Республика Тыва", "Республика Хакасия",
    "Республика Алтай", "Республика Калмыкия", "Кабардино-Балкарская Республика",
    "Республика Северная Осетия", "Чеченская Республика",
    "Карачаево-Черкесская Республика", "Республика Адыгея",
    "Еврейская АО", "Чукотский АО", "Магаданская область",
    "Камчатский край", "Ямало-Ненецкий АО", "Ненецкий АО",
]

# Combined: every city + every region = 160 places
ALL_PLACES = ALL_CITIES + ALL_REGIONS

TOP_50_CITIES = ALL_CITIES[:50]
TOP_30_CITIES = ALL_CITIES[:30]

# ====================================================================
# YANDEX QUERIES — ALL RU
# ====================================================================

YANDEX_QUERIES = [
    # ── Angle 1: Рэй-profile — фэмили офис terms × ALL places ──
    ("fo_фэмили_офис", "russia", [
        "фэмили офис {city}",
        "мультифэмили офис {city}",
        "управление семейным капиталом {city}",
        "частный фэмили офис {city}",
        "семейная инвестиционная компания {city}",
        "управление капиталом семьи {city}",
    ], ALL_PLACES),

    # ── Angle 2: Октан-profile — независимый брокер × ALL places ──
    ("fo_брокер", "russia", [
        "независимый брокер {city}",
        "брокерская компания {city}",
        "брокерское обслуживание {city}",
        "профессиональный участник рынка ценных бумаг {city}",
    ], ALL_PLACES),

    # ── Angle 3: Октан-profile — доверительное управление × ALL places ──
    ("fo_ду", "russia", [
        "доверительное управление {city}",
        "доверительное управление ценными бумагами {city}",
        "управляющая компания {city}",
        "управление капиталом {city}",
        "управление активами {city}",
    ], ALL_PLACES),

    # ── Angle 4: Октан-profile — инвестиционный советник × ALL places ──
    ("fo_советник", "russia", [
        "инвестиционный советник {city}",
        "инвестиционное консультирование {city}",
        "инвестиционная компания {city}",
        "финансовый консультант {city}",
        "персональный финансовый советник {city}",
    ], ALL_PLACES),

    # ── Angle 5: Алготрейдинг / QUIK / ИИС × top 50 cities ──
    ("fo_алго", "russia", [
        "алгоритмическая торговля {city}",
        "алготрейдинг {city}",
        "автоследование {city}",
        "QUIK торговый терминал {city}",
        "количественное инвестирование {city}",
        "квантовые стратегии {city}",
        "автоконсультирование {city}",
        "индивидуальный инвестиционный счёт {city}",
    ], TOP_50_CITIES),

    # ── Angle 6: Wealth management / private banking × ALL places ──
    ("fo_вм", "russia", [
        "управление состоянием {city}",
        "частный банкинг {city}",
        "приватный банкинг {city}",
        "управление активами состоятельных клиентов {city}",
        "VIP брокерское обслуживание {city}",
        "персональный менеджер инвестиции {city}",
    ], ALL_PLACES),

    # ── Angle 7: Financial products × top 50 cities ──
    ("fo_продукты", "russia", [
        "фондовый рынок {city}",
        "срочный рынок {city}",
        "фьючерсы и опционы {city}",
        "закрытый ПИФ {city}",
        "ЗПИФ недвижимость {city}",
        "паевой инвестиционный фонд {city}",
        "структурные продукты {city}",
        "хедж фонд {city}",
        "венчурный фонд {city}",
        "индивидуальный инвестиционный портфель {city}",
    ], TOP_50_CITIES),

    # ── Angle 8: Regulatory / registry × ALL places ──
    ("fo_лицензия", "russia", [
        "лицензия ЦБ управляющая компания {city}",
        "НАУФОР член {city}",
        "реестр инвестиционных советников {city}",
    ], ALL_PLACES),

    # ── Angle 9: Client-facing (how HNWI search) × top 50 cities ──
    ("fo_клиент", "russia", [
        "куда вложить крупную сумму {city}",
        "управление большим капиталом {city}",
        "инвестировать 100 миллионов {city}",
        "инвестиции для состоятельных {city}",
        "частное управление капиталом {city}",
        "независимый финансовый советник {city}",
        "финансовый консалтинг для бизнеса {city}",
        "хеджирование рисков {city}",
        "диверсификация активов {city}",
        "персонализированные торговые стратегии {city}",
    ], TOP_50_CITIES),

    # ── Angle 10: Succession / family wealth × top 30 cities ──
    ("fo_наследство", "russia", [
        "наследственное планирование {city}",
        "передача бизнеса наследникам {city}",
        "семейный траст {city}",
        "защита активов семьи {city}",
        "личный фонд {city}",
        "стоимостное инвестирование {city}",
    ], TOP_30_CITIES),

    # ── Angle 11: Registry / directory / rankings (no geo) ──
    ("fo_реестр", "russia", [
        "реестр инвестиционных советников ЦБ РФ",
        "список управляющих компаний НАУФОР",
        "список брокеров ЦБ России",
        "рейтинг управляющих компаний Россия",
        "топ фэмили офис Россия",
        "лучшие фэмили офис Россия",
        "реестр доверительных управляющих Россия",
        "лицензированные инвестиционные советники РФ",
        "рейтинг фэмили офис Россия",
        "каталог инвестиционных компаний Россия",
        "рейтинг брокеров Россия",
        "лучшие независимые брокеры Россия",
        "реестр профессиональных участников рынка ценных бумаг",
        "список квалифицированных инвесторов",
        "рейтинг доверительного управления Россия",
    ], []),

    # ── Angle 12: Events / conferences / associations (no geo) ──
    ("fo_мероприятия", "russia", [
        "форум фэмили офис Россия",
        "конференция управляющих активами",
        "НАУФОР конференция",
        "форум управляющих активами",
        "саммит частных инвесторов Россия",
        "конференция инвестиционных советников",
        "форум частного капитала Россия",
        "SPEAR'S Russia",
        "Forbes Club инвестиции",
        "РБК конференция инвестиции",
        "Ведомости форум капитал",
    ], []),

    # ── Angle 13: Named competitors / known players (no geo) ──
    # Primary targets + banks + known FOs from CRM
    ("fo_конкуренты", "russia", [
        # Primary targets
        "Рэй фэмили офис",
        "Октан Брокер",
        "октан инвестиции",
        # Banks with private banking
        "Газпромбанк управление активами",
        "Альфа-Банк управление благосостоянием",
        "Сбер управление капиталом",
        "Росбанк частный банкинг",
        "Открытие управление активами",
        "Тинькофф инвестиции управление",
        "БКС мир инвестиций",
        "ВТБ Капитал управление",
        "МКБ управление активами",
        "Совкомбанк управление",
        "Промсвязьбанк управление активами",
        "АК Барс частный банкинг",
        "Локо-Банк частный банкинг",
        # Known investment companies from Google Doc
        "UFG Wealth Management",
        "Accent Capital",
        "Svarog Capital Advisors",
        "Matrix Capital",
        "А1 Инвестиции",
        "Атон инвестиции",
        "Ренессанс Капитал",
        "ИК Фридом Финанс",
        "Сколково Wealth",
        "Ингосстрах инвестиции",
    ], []),

    # ── Angle 14: Known RU targets from CRM — find their lookalikes ──
    # Family offices already found
    ("fo_lookalike_fo", "russia", [
        "Rumberg Capital",
        "Озон Капитал",
        "Инвестум управление",
        "Аврора инвест",
        "Oasis Capital управление",
        "Мульти фэмили офис Россия",
        "Доверительная управляющая компания",
        "Династии фэмили офис",
        "October Family Office",
        "Швед фэмили офис",
        "Боруссия фэмили офис",
        "42 Solution фэмили офис",
        "AVC Family Office",
        "Noble Russian Finance Club",
        "D8 управление активами",
        "Mercury Capital Trust",
        "Финстар Капитал",
        "Бореа Групп",
        "AKBF управление",
        "Велес Траст",
        "Фортис Капитал",
        "Синара Финанс",
        "A-Capital управление",
        "ВИМ инвестиции управление",
    ], []),

    # Investment companies already found
    ("fo_lookalike_inv", "russia", [
        "АриКапитал",
        "Астра управление активами",
        "Арсагера управление",
        "Иволга Капитал",
        "Проксима Капитал",
        "КСП Капитал",
        "Апрель Капитал",
        "Система Капитал управление",
        "РСХБ управление активами",
        "Мовчанс управление",
        "Солид брокер",
        "Риком-Траст",
        "Импакт Капитал",
        "Московские партнеры инвестиции",
        "Велес Менеджмент",
        "Креско Финанс",
        "РВМ Капитал",
        "Национальная управляющая компания",
        "Грандис Капитал",
        "Капитал Флоу",
        "Инсайт Капитал",
        "Высокодоходные инвестиции Россия",
    ], []),
]

# ====================================================================
# GOOGLE QUERIES — ALL RU (different algo than Yandex = different results)
# ====================================================================

GOOGLE_QUERIES = [
    # ── Angle 1: Core Рэй/Октан terms × ALL places ──
    ("gfo_фэмили_офис", "russia_google", [
        "фэмили офис {city}",
        "мультифэмили офис {city}",
        "управление семейным капиталом {city}",
        "управление капиталом семьи {city}",
    ], ALL_PLACES),

    ("gfo_брокер", "russia_google", [
        "независимый брокер {city}",
        "брокерская компания {city}",
        "доверительное управление {city}",
        "управляющая компания {city}",
    ], ALL_PLACES),

    ("gfo_советник", "russia_google", [
        "инвестиционный советник {city}",
        "инвестиционная компания {city}",
        "управление капиталом {city}",
        "управление активами {city}",
    ], ALL_PLACES),

    # ── Angle 2: Wealth management + niche × top 50 cities ──
    ("gfo_вм", "russia_google", [
        "частный банкинг {city}",
        "управление состоянием {city}",
        "VIP брокерское обслуживание {city}",
        "алгоритмическая торговля {city}",
        "автоследование {city}",
        "QUIK {city}",
        "инвестиционное консультирование {city}",
        "персональный финансовый советник {city}",
    ], TOP_50_CITIES),

    # ── Angle 3: Financial products × top 50 cities ──
    ("gfo_продукты", "russia_google", [
        "закрытый ПИФ {city}",
        "ЗПИФ {city}",
        "паевой инвестиционный фонд {city}",
        "структурные продукты {city}",
        "хедж фонд {city}",
        "индивидуальный инвестиционный портфель {city}",
        "фьючерсы и опционы {city}",
        "лицензия ЦБ управляющая компания {city}",
    ], TOP_50_CITIES),

    # ── Angle 4: Client-facing × top 30 cities ──
    ("gfo_клиент", "russia_google", [
        "куда вложить крупную сумму {city}",
        "управление большим капиталом {city}",
        "инвестиции для состоятельных {city}",
        "наследственное планирование {city}",
        "защита активов семьи {city}",
        "семейный траст {city}",
    ], TOP_30_CITIES),

    # ── Angle 5: Registry / competitors (no geo) ──
    ("gfo_реестр", "russia_google", [
        "реестр инвестиционных советников ЦБ РФ",
        "список управляющих компаний НАУФОР",
        "рейтинг управляющих компаний Россия",
        "рейтинг фэмили офис Россия",
        "рейтинг брокеров Россия",
        "список брокеров ЦБ России",
        "лучшие независимые брокеры Россия",
        "Рэй фэмили офис",
        "Октан Брокер",
        "реестр профессиональных участников рынка ценных бумаг",
        "НАУФОР инвестиционный советник",
        "лицензированный брокер Россия",
        "доверительное управление активами Россия",
        "управляющая компания лицензия ЦБ РФ",
        "профессиональный участник рынка ценных бумаг Россия",
    ], []),
]


def generate_queries(templates, engine_label):
    queries = []
    seen = set()
    for segment, geo, patterns, places in templates:
        if places:
            for pattern in patterns:
                for place in places:
                    q = pattern.format(city=place)
                    if q not in seen:
                        seen.add(q)
                        queries.append((q, segment, geo))
        else:
            for pattern in patterns:
                if pattern not in seen:
                    seen.add(pattern)
                    queries.append((pattern, segment, geo))
    logger.info(f"[{engine_label}] Generated {len(queries)} unique queries")
    return queries


async def run_queries(session, job, queries):
    from app.services.company_search_service import company_search_service
    from app.services.search_service import search_service

    for q_text, segment, geo in queries:
        sq = SearchQuery(
            search_job_id=job.id, query_text=q_text,
            segment=segment, geo=geo, status=SearchQueryStatus.PENDING,
        )
        session.add(sq)
    job.queries_total = (job.queries_total or 0) + len(queries)
    await session.commit()

    logger.info(f"Searching job {job.id} ({len(queries)} queries, {job.search_engine.value})")
    await search_service.run_search_job(session, job.id)
    await session.refresh(job)

    skip_set = await company_search_service._build_skip_set(session, PROJECT_ID)
    new_domains = await company_search_service._get_new_domains_from_job(session, job, skip_set)
    logger.info(f"Job {job.id}: {len(new_domains)} new domains ({len(skip_set)} skip set)")

    if new_domains:
        project = await session.get(Project, PROJECT_ID)
        await company_search_service._scrape_and_analyze_domains(
            session=session, job=job, domains=new_domains,
            target_segments=project.target_segments,
        )
    await session.commit()

    result = await session.execute(sql_text(
        "SELECT COUNT(*) FILTER (WHERE is_target) as targets, COUNT(*) as total "
        "FROM search_results WHERE search_job_id = :jid"
    ), {"jid": job.id})
    row = result.fetchone()
    logger.info(f"Job {job.id}: {row.targets} targets / {row.total} analyzed")
    return row.targets or 0, row.total or 0


async def create_and_run(session, engine, phase, all_queries, batch_size=200):
    total_t, total_a = 0, 0
    job = SearchJob(
        company_id=COMPANY_ID, status=SearchJobStatus.PENDING,
        search_engine=engine, queries_total=0, project_id=PROJECT_ID,
        config={"source": "fo_mega_search", "phase": phase},
    )
    session.add(job)
    await session.commit()

    for i in range(0, len(all_queries), batch_size):
        batch = all_queries[i:i + batch_size]
        logger.info(f"[{phase}] Batch {i // batch_size + 1}/{(len(all_queries) + batch_size - 1) // batch_size}: {len(batch)} queries")
        t, a = await run_queries(session, job, batch)
        total_t += t; total_a += a
        logger.info(f"[{phase}] Running total: {total_t} targets, {total_a} analyzed")

    job.status = SearchJobStatus.COMPLETED
    await session.commit()
    logger.info(f"[{phase}] DONE — {total_t} targets from {total_a} analyzed (job {job.id})")
    return total_t, total_a


async def main():
    logger.info("=" * 70)
    logger.info("Deliryo MEGA Search — Рэй/Октан lookalikes — RU ONLY")
    logger.info("=" * 70)

    # Record baseline
    async with async_session_maker() as session:
        result = await session.execute(sql_text(
            "SELECT COUNT(*) FILTER (WHERE is_target) as targets, COUNT(*) as total "
            "FROM search_results WHERE project_id = :pid"
        ), {"pid": PROJECT_ID})
        baseline = result.fetchone()
        logger.info(f"BASELINE: {baseline.targets} targets / {baseline.total} analyzed")

    # Generate all queries
    yandex_q = generate_queries(YANDEX_QUERIES, "YANDEX")
    google_q = generate_queries(GOOGLE_QUERIES, "GOOGLE")
    logger.info(f"Total: {len(yandex_q)} Yandex + {len(google_q)} Google = {len(yandex_q) + len(google_q)} queries")

    est_yandex = len(yandex_q) * 0.25 / 1000
    est_google = len(google_q) * 3.50 / 1000
    logger.info(f"Estimated cost: Yandex ${est_yandex:.2f} + Google ${est_google:.2f} = ${est_yandex + est_google:.2f}")

    total_t, total_a = 0, 0

    # Phase 1: Yandex (cheap, run first)
    async with async_session_maker() as session:
        logger.info("=" * 50)
        logger.info(f"PHASE 1 — Yandex: {len(yandex_q)} queries")
        logger.info("=" * 50)
        t, a = await create_and_run(session, SearchEngine.YANDEX_API, "mega_yandex_ru", yandex_q)
        total_t += t; total_a += a
        logger.info(f"Yandex complete: {t} targets from {a} analyzed")

    # Phase 2: Google RU (different algo = different results)
    async with async_session_maker() as session:
        logger.info("=" * 50)
        logger.info(f"PHASE 2 — Google RU: {len(google_q)} queries")
        logger.info("=" * 50)
        t, a = await create_and_run(session, SearchEngine.GOOGLE_SERP, "mega_google_ru", google_q, batch_size=100)
        total_t += t; total_a += a
        logger.info(f"Google complete: {t} targets from {a} analyzed")

    # Final summary
    async with async_session_maker() as session:
        result = await session.execute(sql_text(
            "SELECT COUNT(*) FILTER (WHERE is_target) as targets, COUNT(*) as total "
            "FROM search_results WHERE project_id = :pid"
        ), {"pid": PROJECT_ID})
        final = result.fetchone()

    logger.info("=" * 70)
    logger.info("MEGA SEARCH COMPLETE — Рэй/Октан lookalikes")
    logger.info(f"Baseline: {baseline.targets} targets / {baseline.total} analyzed")
    logger.info(f"Final:    {final.targets} targets / {final.total} analyzed")
    logger.info(f"Net new:  +{final.targets - baseline.targets} targets / +{final.total - baseline.total} analyzed")
    logger.info(f"This run: {total_t} targets from {total_a} analyzed")
    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
