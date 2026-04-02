"""
Fix accounts that have Android fingerprints (Samsung SM-G998B / SDK 33 / 10.6.2)
while using Desktop api_id=2040. This mismatch causes Telegram to flag accounts.

Assigns each affected account a unique Desktop fingerprint from our device pool.
"""
import asyncio
import sys
import os

sys.path.insert(0, "/app")
os.chdir("/app")

from sqlalchemy import select, or_
from app.database import async_session
from app.models.telegram_outreach import TgAccount
from app.services.device_fingerprints import generate_fingerprint


async def main():
    async with async_session() as session:
        # Find accounts with Android fingerprints
        result = await session.execute(
            select(TgAccount).where(
                or_(
                    TgAccount.device_model == "Samsung SM-G998B",
                    TgAccount.system_version == "SDK 33",
                    TgAccount.app_version == "10.6.2",
                )
            )
        )
        accounts = result.scalars().all()

        if not accounts:
            print("No accounts with Android fingerprints found.")
            return

        print(f"Found {len(accounts)} accounts with Android fingerprints")

        # Collect already-used models to maximize uniqueness
        all_result = await session.execute(
            select(TgAccount.device_model).where(
                TgAccount.device_model.isnot(None),
                TgAccount.device_model != "Samsung SM-G998B",
                TgAccount.device_model != "PC 64bit",
            )
        )
        used_models = {row[0] for row in all_result.all()}

        updated = 0
        for account in accounts:
            fp = generate_fingerprint(exclude_models=used_models)
            used_models.add(fp["device_model"])

            old = f"{account.device_model}/{account.system_version}/{account.app_version}"
            account.device_model = fp["device_model"]
            account.system_version = fp["system_version"]
            account.app_version = fp["app_version"]
            # Keep existing lang_code if set, otherwise don't change
            new = f"{account.device_model}/{account.system_version}/{account.app_version}"
            print(f"  {account.phone}: {old} -> {new}")
            updated += 1

        await session.commit()
        print(f"\nUpdated {updated} accounts")


if __name__ == "__main__":
    asyncio.run(main())
