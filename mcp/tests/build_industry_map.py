"""Build complete Apollo industry_tag_id map.
Strategy: enrich ONE well-known company per industry → extract tag_id.
LinkedIn has ~148 industries. We know them. Just need Apollo's internal IDs.

Run: docker exec mcp-backend python /app/build_industry_map.py
"""
import asyncio, httpx, sys, json, time
sys.path.insert(0, "/app")
from app.db import async_session_maker
from app.models.integration import MCPIntegrationSetting
from app.services.encryption import decrypt_value
from sqlalchemy import select

# One well-known company per LinkedIn industry (covers ~80 industries)
INDUSTRY_SAMPLES = {
    "accounting": "deloitte.com",
    "airlines / aviation": "delta.com",
    "alternative dispute resolution": "jamsadr.com",
    "alternative medicine": "mindbodygreen.com",
    "animation": "pixar.com",
    "apparel & fashion": "versace.com",
    "architecture & planning": "gensler.com",
    "arts & crafts": "etsy.com",
    "automotive": "toyota.com",
    "aviation & aerospace": "boeing.com",
    "banking": "jpmorgan.com",
    "biotechnology": "genentech.com",
    "broadcast media": "bbc.com",
    "building materials": "saint-gobain.com",
    "business supplies & equipment": "staples.com",
    "capital markets": "goldmansachs.com",
    "chemicals": "basf.com",
    "civic & social organization": "redcross.org",
    "civil engineering": "aecom.com",
    "commercial real estate": "cbre.com",
    "computer & network security": "crowdstrike.com",
    "computer games": "epicgames.com",
    "computer hardware": "dell.com",
    "computer networking": "cisco.com",
    "computer software": "microsoft.com",
    "construction": "bechtel.com",
    "consumer electronics": "apple.com",
    "consumer goods": "unilever.com",
    "consumer services": "marriott.com",
    "cosmetics": "loreal.com",
    "dairy": "danone.com",
    "defense & space": "lockheedmartin.com",
    "design": "ideo.com",
    "education management": "pearson.com",
    "e-learning": "coursera.org",
    "electrical / electronic manufacturing": "siemens.com",
    "entertainment": "netflix.com",
    "environmental services": "veolia.com",
    "events services": "eventbrite.com",
    "executive office": "whitehouse.gov",
    "facilities services": "iss-world.com",
    "farming": "cargill.com",
    "financial services": "visa.com",
    "fine art": "christies.com",
    "fishery": "mowi.com",
    "food & beverages": "coca-cola.com",
    "food production": "nestle.com",
    "fund-raising": "gofundme.com",
    "furniture": "ikea.com",
    "gambling & casinos": "mgmresorts.com",
    "glass, ceramics & concrete": "corning.com",
    "government administration": "usa.gov",
    "graphic design": "canva.com",
    "health, wellness & fitness": "peloton.com",
    "higher education": "harvard.edu",
    "hospital & health care": "mayoclinic.org",
    "hospitality": "hilton.com",
    "human resources": "adp.com",
    "import & export": "dhl.com",
    "individual & family services": "salvation.org",
    "industrial automation": "rockwellautomation.com",
    "information services": "bloomberg.com",
    "information technology & services": "accenture.com",
    "insurance": "allianz.com",
    "international affairs": "un.org",
    "international trade & development": "worldbank.org",
    "internet": "google.com",
    "investment banking": "morganstanley.com",
    "investment management": "blackrock.com",
    "judiciary": "uscourts.gov",
    "law enforcement": "fbi.gov",
    "law practice": "bakermckenzie.com",
    "legal services": "legalzoom.com",
    "leisure, travel & tourism": "booking.com",
    "libraries": "loc.gov",
    "logistics & supply chain": "fedex.com",
    "luxury goods & jewelry": "tiffany.com",
    "machinery": "caterpillar.com",
    "management consulting": "mckinsey.com",
    "maritime": "maersk.com",
    "market research": "nielsen.com",
    "marketing & advertising": "wpp.com",
    "mechanical or industrial engineering": "ge.com",
    "media production": "warnerbros.com",
    "medical devices": "medtronic.com",
    "medical practice": "clevelandclinic.org",
    "mental health care": "talkspace.com",
    "military": "army.mil",
    "mining & metals": "bhp.com",
    "motion pictures & film": "disney.com",
    "museums & institutions": "moma.org",
    "music": "spotify.com",
    "nanotechnology": "nano.gov",
    "newspapers": "nytimes.com",
    "nonprofit organization management": "unicef.org",
    "oil & energy": "shell.com",
    "online media": "buzzfeed.com",
    "outsourcing / offshoring": "tata.com",
    "package / freight delivery": "ups.com",
    "packaging & containers": "sealed-air.com",
    "paper & forest products": "internationalpaper.com",
    "performing arts": "cirquedusoleil.com",
    "pharmaceuticals": "pfizer.com",
    "philanthropy": "gatesfoundation.org",
    "photography": "gettyimages.com",
    "plastics": "dow.com",
    "political organization": "democrats.org",
    "primary / secondary education": "k12.com",
    "printing": "rfreid.com",
    "professional training & coaching": "linkedin.com",
    "program development": "github.com",
    "public policy": "brookings.edu",
    "public relations & communications": "edelman.com",
    "public safety": "nfpa.org",
    "publishing": "penguinrandomhouse.com",
    "railroad manufacture": "wabteccorp.com",
    "ranching": "jbs.com.br",
    "real estate": "zillow.com",
    "recreational facilities & services": "planetfitness.com",
    "religious institutions": "vatican.va",
    "renewables & environment": "nextera.com",
    "research": "mit.edu",
    "restaurants": "mcdonalds.com",
    "retail": "walmart.com",
    "security & investigations": "securitas.com",
    "semiconductors": "intel.com",
    "shipbuilding": "huntingtoningalls.com",
    "sporting goods": "nike.com",
    "sports": "nba.com",
    "staffing & recruiting": "randstad.com",
    "supermarkets": "kroger.com",
    "telecommunications": "att.com",
    "textiles": "cottonon.com",
    "think tanks": "rand.org",
    "tobacco": "pmi.com",
    "translation & localization": "transperfect.com",
    "transportation / trucking / railroad": "unionpacific.com",
    "utilities": "duke-energy.com",
    "venture capital & private equity": "sequoiacap.com",
    "veterinary": "banfield.com",
    "warehousing": "prologis.com",
    "wholesale": "sysco.com",
    "wine & spirits": "diageo.com",
    "wireless": "t-mobile.com",
    "writing & editing": "medium.com",
}


async def main():
    async with async_session_maker() as s:
        r = await s.execute(select(MCPIntegrationSetting).where(
            MCPIntegrationSetting.integration_name == "apollo", MCPIntegrationSetting.user_id == 181))
        row = r.scalar_one_or_none()
        key = decrypt_value(row.api_key_encrypted).strip()

    hdr = {"X-Api-Key": key, "Content-Type": "application/json"}
    industry_map = {}
    failed = []
    credits = 0

    print(f"Building industry map from {len(INDUSTRY_SAMPLES)} companies...")
    t0 = time.time()

    for expected_industry, domain in INDUSTRY_SAMPLES.items():
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                resp = await c.post("https://api.apollo.io/api/v1/organizations/enrich",
                                    headers=hdr, json={"domain": domain})
                data = resp.json()
                org = data.get("organization", {})
                tag_id = org.get("industry_tag_id")
                actual_industry = org.get("industry")
                credits += 1

                if tag_id:
                    industry_map[tag_id] = {
                        "industry": actual_industry,
                        "expected": expected_industry,
                        "sample_domain": domain,
                    }
                    match = "OK" if actual_industry and expected_industry.lower() in actual_industry.lower() else "DIFF"
                    print(f"  {match} {domain}: {actual_industry} ({tag_id})")
                else:
                    failed.append({"domain": domain, "expected": expected_industry})
                    print(f"  FAIL {domain}: no tag_id")
        except Exception as e:
            failed.append({"domain": domain, "expected": expected_industry, "error": str(e)[:50]})
            print(f"  ERR {domain}: {str(e)[:50]}")
        await asyncio.sleep(0.35)

    elapsed = time.time() - t0
    print(f"\nDone: {len(industry_map)} industries mapped, {len(failed)} failed, {credits} credits, {elapsed:.0f}s")

    # Save the map
    outfile = "/app/apollo_industry_map.json"
    with open(outfile, "w") as f:
        json.dump({
            "total_industries": len(industry_map),
            "credits_spent": credits,
            "map": {v["industry"]: {"tag_id": k, "sample": v["sample_domain"]}
                    for k, v in industry_map.items()},
            "by_tag_id": industry_map,
            "failed": failed,
        }, f, indent=2)
    print(f"Saved to {outfile}")

asyncio.run(main())
