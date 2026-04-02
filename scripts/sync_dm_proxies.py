"""
Sync proxy_config for telegram_dm_accounts.

For each DM account with NULL proxy_config:
1. If matching TgAccount exists (by phone) → copy its assigned_proxy
2. If no matching TgAccount → assign an unassigned proxy from the pool
"""
import asyncio
import sys
import os

sys.path.insert(0, "/app")
os.chdir("/app")

from app.db import async_session_maker
from app.models.telegram_dm import TelegramDMAccount
from app.models.telegram_outreach import TgAccount, TgProxy
from sqlalchemy import select


async def main():
    async with async_session_maker() as session:
        # Load DM accounts with NULL proxy_config
        dm_accs = (await session.execute(
            select(TelegramDMAccount).where(TelegramDMAccount.proxy_config == None)
        )).scalars().all()

        if not dm_accs:
            print("All DM accounts already have proxy_config. Nothing to do.")
            return

        print(f"Found {len(dm_accs)} DM accounts with NULL proxy_config")

        # Load all assigned proxy IDs (used by TgAccounts)
        assigned_ids = set()
        tg_rows = (await session.execute(
            select(TgAccount.assigned_proxy_id).where(TgAccount.assigned_proxy_id != None)
        )).all()
        for r in tg_rows:
            assigned_ids.add(r[0])

        # Also exclude proxies already assigned to other DM accounts
        dm_with_proxy = (await session.execute(
            select(TelegramDMAccount.proxy_config).where(TelegramDMAccount.proxy_config != None)
        )).scalars().all()
        used_proxy_keys = set()
        for pc in dm_with_proxy:
            if isinstance(pc, dict):
                used_proxy_keys.add(f"{pc.get('host')}:{pc.get('port')}")

        # Load unassigned proxies for orphaned accounts
        all_proxies = (await session.execute(
            select(TgProxy).order_by(TgProxy.id)
        )).scalars().all()
        unassigned = [p for p in all_proxies
                      if p.id not in assigned_ids
                      and f"{p.host}:{p.port}" not in used_proxy_keys]
        unassigned_iter = iter(unassigned)

        synced = 0
        assigned_new = 0
        skipped = 0

        for dm in dm_accs:
            if not dm.phone:
                print(f"  SKIP DM#{dm.id}: no phone")
                skipped += 1
                continue

            # Try to find matching TgAccount
            tg = (await session.execute(
                select(TgAccount).where(TgAccount.phone == dm.phone)
            )).scalar_one_or_none()

            if tg and tg.assigned_proxy_id:
                proxy = await session.get(TgProxy, tg.assigned_proxy_id)
                if proxy:
                    dm.proxy_config = {
                        "type": proxy.protocol.value if proxy.protocol else "socks5",
                        "host": proxy.host,
                        "port": proxy.port,
                        "username": proxy.username,
                        "password": proxy.password,
                    }
                    print(f"  SYNC DM#{dm.id} phone={dm.phone} <- TgAccount#{tg.id} proxy={proxy.host}:{proxy.port}")
                    synced += 1
                    continue

            # No matching TgAccount or no proxy — assign from pool
            proxy = next(unassigned_iter, None)
            if proxy:
                dm.proxy_config = {
                    "type": proxy.protocol.value if proxy.protocol else "socks5",
                    "host": proxy.host,
                    "port": proxy.port,
                    "username": proxy.username,
                    "password": proxy.password,
                }
                print(f"  ASSIGN DM#{dm.id} phone={dm.phone} <- pool proxy={proxy.host}:{proxy.port}")
                assigned_new += 1
            else:
                print(f"  SKIP DM#{dm.id} phone={dm.phone}: no unassigned proxies left")
                skipped += 1

        await session.commit()
        print(f"\nDone: synced={synced}, assigned_new={assigned_new}, skipped={skipped}")


if __name__ == "__main__":
    asyncio.run(main())
