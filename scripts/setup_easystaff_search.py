"""
Setup EasyStaff Global (project 9) search config: 2 segments.
  1. us_latam — US companies hiring contractors/teams in Latin America
  2. pakistan_corridor — Companies anywhere hiring in Pakistan

Run on Hetzner:
  docker run -d --name easystaff-setup --network repo_default \
    -v ~/magnum-opus-project/repo/backend:/app \
    -v ~/magnum-opus-project/repo/scripts:/scripts \
    -e DATABASE_URL=... -e OPENAI_API_KEY=... \
    python:3.11 bash -c 'pip install -q -r /app/requirements.txt && python /scripts/setup_easystaff_search.py'
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, "/app")
os.chdir("/app")

PROJECT_ID = 9
COMPANY_ID = 1

TARGET_SEGMENTS = """EasyStaff Global: international freelancer/contractor payment platform.
Find companies that hire international freelancers or remote contractors abroad — they need a payment solution.

Segment 1: US companies with Latin America teams
US companies (any industry) that hire contractors, developers, or remote workers in Mexico, Colombia, Brazil, Argentina, Honduras, Dominican Republic, Philippines. Includes nearshore dev shops, biotech, manufacturing, consulting, water tech, SaaS — any US company with LatAm operations.
Company size: 10-500 employees.

Segment 2: Companies hiring in Pakistan
Companies from anywhere (US, UK, UAE, EU, Canada, Australia) that hire remote workers, developers, designers, or contractors in Pakistan. Includes tech companies, startups, agencies, e-commerce brands with Pakistani teams.
Company size: 10-500 employees.

NOT looking for: enterprise (1000+ employees), EOR/PEO service providers, recruitment agencies, staffing firms.
"""

SEARCH_CONFIG = {
    "segments": {
        "us_latam": {
            "priority": 1,
            "label_en": "US Companies with LatAm Teams",
            "geos": {
                "mexico": {
                    "cities_en": ["Mexico City", "Guadalajara", "Monterrey", "Tijuana", "Puebla", "Queretaro"],
                    "country_en": "Mexico",
                },
                "colombia": {
                    "cities_en": ["Bogota", "Medellin", "Cali", "Barranquilla", "Cartagena"],
                    "country_en": "Colombia",
                },
                "brazil": {
                    "cities_en": ["Sao Paulo", "Rio de Janeiro", "Curitiba", "Belo Horizonte", "Porto Alegre", "Florianopolis"],
                    "country_en": "Brazil",
                },
                "argentina": {
                    "cities_en": ["Buenos Aires", "Cordoba", "Rosario", "Mendoza"],
                    "country_en": "Argentina",
                },
                "honduras": {
                    "cities_en": ["Tegucigalpa", "San Pedro Sula"],
                    "country_en": "Honduras",
                },
                "dominican_republic": {
                    "cities_en": ["Santo Domingo", "Santiago de los Caballeros"],
                    "country_en": "Dominican Republic",
                },
                "latam_general": {
                    "cities_en": ["Lima", "Santiago", "San Jose", "Panama City"],
                    "country_en": "Latin America",
                },
            },
            "vars": {
                "industry_en": [
                    "tech", "SaaS", "biotech", "fintech", "healthtech",
                    "manufacturing", "consulting", "edtech", "e-commerce",
                    "software", "logistics", "engineering",
                ],
                "role_en": [
                    "developers", "engineers", "contractors", "remote workers",
                    "designers", "customer support", "virtual assistants",
                ],
            },
            "templates_en": [
                "US company with office in {city}",
                "US company hiring {role} in {country}",
                "American company {city} office",
                "nearshore development {city}",
                "nearshore development {country}",
                "{industry} company {city}",
                "{industry} company with {country} team",
                "outsource {role} {country}",
                "hire {role} {city}",
                "company with remote team in {country}",
                "US startup with {country} office",
            ],
            "templates_ru": [],
        },
        "pakistan_corridor": {
            "priority": 2,
            "label_en": "Companies Hiring in Pakistan",
            "geos": {
                "pakistan": {
                    "cities_en": ["Lahore", "Karachi", "Islamabad", "Rawalpindi", "Faisalabad", "Peshawar", "Multan"],
                    "country_en": "Pakistan",
                },
                "pk_remote": {
                    "cities_en": ["Lahore", "Karachi", "Islamabad"],
                    "country_en": "Pakistan",
                },
            },
            "vars": {
                "industry_en": [
                    "tech", "SaaS", "software", "e-commerce", "fintech",
                    "startup", "digital marketing", "IT services",
                    "mobile app", "web development",
                ],
                "source_en": [
                    "US", "UK", "UAE", "Dubai", "Canadian", "Australian",
                    "European", "German", "Singapore",
                ],
                "role_en": [
                    "developers", "engineers", "designers", "contractors",
                    "remote workers", "QA testers", "data entry",
                    "customer support", "virtual assistants",
                ],
            },
            "templates_en": [
                "{source} company hiring {role} in {country}",
                "{source} company with {country} team",
                "{source} company with office in {city}",
                "hire {role} {city}",
                "{industry} company {city}",
                "{industry} company hiring in {country}",
                "outsource {role} {country}",
                "remote {role} {country}",
                "{source} startup with {country} developers",
                "offshore development {city}",
                "company with {country} office",
            ],
            "templates_ru": [],
        },
    },
    "doc_keywords": [
        # US-LatAm: proven keyword phrases
        ["us_latam", "mexico", "en", [
            "US companies with offices in Mexico",
            "American companies in Mexico City",
            "nearshore software development Mexico",
            "US startups hiring in Mexico",
            "tech companies Guadalajara",
            "IT outsourcing Mexico",
            "companies with nearshore teams Mexico",
            "silicon valley of Mexico Guadalajara",
        ]],
        ["us_latam", "colombia", "en", [
            "US companies with offices in Colombia",
            "American companies in Medellin",
            "nearshore development Colombia",
            "tech companies Bogota",
            "US startups hiring Colombia",
            "software development outsourcing Colombia",
            "remote tech teams Colombia",
        ]],
        ["us_latam", "brazil", "en", [
            "US companies with offices in Brazil",
            "American companies Sao Paulo",
            "nearshore development Brazil",
            "tech companies hiring in Brazil",
            "US startups with Brazil teams",
            "software outsourcing Brazil",
        ]],
        ["us_latam", "argentina", "en", [
            "US companies with offices in Argentina",
            "tech companies Buenos Aires",
            "nearshore development Argentina",
            "US startups hiring Argentina",
            "remote developers Argentina",
        ]],
        ["us_latam", "honduras", "en", [
            "US companies with offices in Honduras",
            "American companies Honduras",
            "manufacturing companies Honduras",
            "outsourcing Honduras",
        ]],
        ["us_latam", "dominican_republic", "en", [
            "US companies in Dominican Republic",
            "American companies Santo Domingo",
            "nearshore call center Dominican Republic",
            "tech outsourcing Dominican Republic",
        ]],
        ["us_latam", None, "en", [
            "US companies with Latin America offices",
            "American companies hiring in Latin America",
            "nearshore outsourcing companies",
            "companies with nearshore development teams",
            "US startups with LATAM teams",
            "remote teams Latin America",
            "hire remote developers Latin America",
            "best countries for nearshoring",
            "companies using nearshore development",
            "US companies offshoring to Latin America",
        ]],
        # Pakistan corridor: proven keyword phrases
        ["pakistan_corridor", "pakistan", "en", [
            "companies hiring developers in Pakistan",
            "US companies with Pakistan office",
            "UK companies hiring in Pakistan",
            "UAE companies with Pakistan team",
            "Dubai companies hiring Pakistan developers",
            "tech companies Lahore",
            "IT companies Karachi",
            "software companies Islamabad",
            "outsource development Pakistan",
            "hire remote developers Pakistan",
            "offshore development Pakistan",
            "companies with teams in Pakistan",
            "Australian companies hiring Pakistan",
            "Canadian companies with Pakistan developers",
            "European companies outsourcing to Pakistan",
            "startup hiring developers Lahore",
            "software house Lahore",
            "IT outsourcing Karachi",
            "remote workers Pakistan",
            "best IT companies Pakistan",
        ]],
        ["pakistan_corridor", None, "en", [
            "hire developers Pakistan",
            "outsource to Pakistan",
            "Pakistan IT industry companies",
            "Pakistan software development outsourcing",
            "companies hiring remote workers Pakistan",
            "Pakistan tech talent",
            "offshore teams Pakistan",
            "foreign companies with Pakistan offices",
        ]],
    ],
}


async def main():
    from app.db import async_session_maker
    from sqlalchemy import text, select
    from app.models.contact import Project
    from app.models.domain import ProjectSearchKnowledge

    async with async_session_maker() as session:
        # 1. Update target_segments on project
        result = await session.execute(
            select(Project).where(Project.id == PROJECT_ID)
        )
        project = result.scalar_one_or_none()
        if not project:
            print(f"ERROR: Project {PROJECT_ID} not found!")
            return

        project.target_segments = TARGET_SEGMENTS
        print(f"[1/3] Updated target_segments on project '{project.name}' (id={PROJECT_ID})")

        # 2. Upsert ProjectSearchKnowledge with search_config
        result = await session.execute(
            select(ProjectSearchKnowledge).where(
                ProjectSearchKnowledge.project_id == PROJECT_ID
            )
        )
        knowledge = result.scalar_one_or_none()

        if not knowledge:
            knowledge = ProjectSearchKnowledge(project_id=PROJECT_ID)
            session.add(knowledge)
            print("[2/3] Created new ProjectSearchKnowledge row")
        else:
            print("[2/3] Updating existing ProjectSearchKnowledge row")

        knowledge.search_config = SEARCH_CONFIG

        await session.commit()
        print("[3/3] Committed to DB")

        # 3. Verify
        print("\n--- Verification ---")
        result = await session.execute(
            text("SELECT target_segments FROM projects WHERE id = :pid"),
            {"pid": PROJECT_ID},
        )
        ts = result.scalar()
        print(f"target_segments length: {len(ts)} chars")

        result = await session.execute(
            text("SELECT search_config FROM project_search_knowledge WHERE project_id = :pid"),
            {"pid": PROJECT_ID},
        )
        config = result.scalar()
        segments = config["segments"]
        doc_kw = config["doc_keywords"]

        total_templates = 0
        total_doc_phrases = sum(len(entry[3]) for entry in doc_kw)

        for seg_key, seg in segments.items():
            geos = list(seg["geos"].keys())
            n_en = len(seg.get("templates_en", []))
            n_cities = sum(len(g["cities_en"]) for g in seg["geos"].values())
            n_vars = sum(len(v) for v in seg.get("vars", {}).values())
            # Rough query estimate: templates × cities × var_combinations
            est = n_en * n_cities * (n_vars // max(len(seg.get("vars", {})), 1))
            total_templates += n_en
            print(f"  {seg_key} (priority {seg['priority']}): {len(geos)} geos, {n_cities} cities, {n_en} templates, ~{est} template queries")

        print(f"  doc_keywords: {len(doc_kw)} groups, {total_doc_phrases} phrases total")
        print(f"\nDone! Project {PROJECT_ID} is ready for search.")
        print("Next: trigger search via chat or API:")
        print("  POST /search/projects/9/run {\"max_queries\": 1000, \"target_goal\": 300}")


if __name__ == "__main__":
    asyncio.run(main())
