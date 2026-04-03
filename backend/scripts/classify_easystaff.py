"""
One-time script: Classify 1000 most recent EasyStaff RU contacts by business segment,
then cross-match against Inxy ICP to find suitable leads.

Run inside the backend container:
  docker exec leadgen-backend python -m scripts.classify_easystaff
"""
import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Add parent to path for app imports
sys.path.insert(0, "/app")


async def main():
    from app.db import async_session_maker
    from app.services.segment_classifier import classify_contacts_for_project, cross_match_for_project

    EASYSTAFF_RU_PROJECT_ID = 40
    INXY_PROJECT_NAME = "inxy"
    LIMIT = 1000  # Test batch — hardcoded per task requirements

    async with async_session_maker() as session:
        # Step 1: Classify 1000 most recent unclassified contacts
        logger.info(f"Starting classification of {LIMIT} EasyStaff RU contacts...")
        result = await classify_contacts_for_project(
            session,
            project_id=EASYSTAFF_RU_PROJECT_ID,
            statuses=None,  # All statuses
            limit=LIMIT,
            only_unclassified=True,
        )
        logger.info(f"Classification result: {result}")

        # Step 2: Cross-match all classified contacts for Inxy suitability
        logger.info("Cross-matching classified contacts for Inxy...")
        cross_result = await cross_match_for_project(
            session,
            source_project_id=EASYSTAFF_RU_PROJECT_ID,
            target_project_name=INXY_PROJECT_NAME,
        )
        logger.info(f"Cross-match result: {cross_result}")

        print("\n" + "=" * 60)
        print(f"CLASSIFICATION: {result['classified']}/{result['total']} classified, "
              f"{result['skipped']} skipped, {result['errors']} errors, "
              f"{result['domains_scraped']} domains scraped")
        print(f"CROSS-MATCH: {cross_result['matched']}/{cross_result['total_classified']} "
              f"contacts suitable for {INXY_PROJECT_NAME}")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
