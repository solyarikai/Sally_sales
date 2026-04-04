"""
Test Infatica proxy integration (magnum-82y.5).

Tests:
1. Proxy connectivity + exit IP geolocation
2. Country routing: +7 → BY, +351 → PT
3. Sticky sessions: same session ID → same IP
4. Telethon SOCKS5 connection through proxy
5. Optional: send test message through proxy

Run inside backend container:
  docker exec leadgen-backend python /tmp/test_infatica.py
"""

import asyncio
import json
import logging
import os
import socket
import sys
import time

sys.path.insert(0, "/app")
os.chdir("/app")

import socks
from app.core.config import settings
from app.services.infatica_proxy_service import infatica_proxy_service

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

DIVIDER = "=" * 60

# ── Helpers ──────────────────────────────────────────────────

def fetch_ip_via_socks5(host, port, username, password, timeout=25) -> str:
    """Connect through SOCKS5 proxy and return exit IP via HTTPS."""
    import re
    import ssl

    s = socks.socksocket(socket.AF_INET, socket.SOCK_STREAM)
    s.set_proxy(socks.SOCKS5, host, port, rdns=True, username=username, password=password)
    s.settimeout(timeout)
    try:
        s.connect(("api.ipify.org", 443))
        ctx = ssl.create_default_context()
        ss = ctx.wrap_socket(s, server_hostname="api.ipify.org")
        ss.sendall(b"GET /?format=text HTTP/1.0\r\nHost: api.ipify.org\r\nConnection: close\r\n\r\n")
        data = b""
        while True:
            chunk = ss.recv(4096)
            if not chunk:
                break
            data += chunk
        ss.close()
        decoded = data.decode(errors="replace")
        if "\r\n\r\n" in decoded:
            body = decoded.split("\r\n\r\n", 1)[1].strip()
        else:
            body = decoded.strip()
        # Extract IP from response
        m = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', body)
        if m:
            return m.group(1)
        return body
    finally:
        try:
            s.close()
        except Exception:
            pass


def geolocate_ip(ip: str) -> dict:
    """Get country info for an IP via ip-api.com (no auth needed)."""
    import http.client
    conn = http.client.HTTPConnection("ip-api.com", timeout=10)
    try:
        conn.request("GET", f"/json/{ip}?fields=status,country,countryCode,city,isp")
        resp = conn.getresponse()
        return json.loads(resp.read().decode())
    finally:
        conn.close()


def test_tcp_via_socks5(host, port, username, password, target_host, target_port, timeout=15) -> float:
    """Test TCP connectivity through SOCKS5 proxy. Returns latency in ms."""
    s = socks.socksocket(socket.AF_INET, socket.SOCK_STREAM)
    s.set_proxy(socks.SOCKS5, host, port, rdns=True, username=username, password=password)
    s.settimeout(timeout)
    t0 = time.time()
    try:
        s.connect((target_host, target_port))
        latency = (time.time() - t0) * 1000
        return latency
    finally:
        s.close()


# ── Test 1: Country routing + exit IP ────────────────────────

def test_country_routing():
    log.info(f"\n{DIVIDER}")
    log.info("TEST 1: Country routing + exit IP geolocation")
    log.info(DIVIDER)

    test_cases = [
        ("+79120556339", "BY", "Russian +7 → Belarus"),
        ("+351912345678", "PT", "Portuguese +351 → Portugal"),
    ]

    results = []
    for phone, expected_country, label in test_cases:
        log.info(f"\n--- {label} ---")

        # Check country detection
        detected = infatica_proxy_service.get_country_for_phone(phone)
        country_ok = detected == expected_country
        log.info(f"  Country detection: {detected} (expected {expected_country}) → {'OK' if country_ok else 'FAIL'}")

        # Generate proxy config (no account_id = no sticky)
        proxy = infatica_proxy_service.get_proxy_for_account(phone)
        log.info(f"  Proxy: socks5://{proxy['username']}@{proxy['host']}:{proxy['port']}")

        # Fetch exit IP
        try:
            ip = fetch_ip_via_socks5(proxy["host"], proxy["port"], proxy["username"], proxy["password"])
            geo = geolocate_ip(ip)
            geo_country = geo.get("countryCode", "??")
            geo_ok = geo_country == expected_country
            log.info(f"  Exit IP: {ip}")
            log.info(f"  Geo: {geo.get('country')} ({geo_country}), {geo.get('city')}, ISP: {geo.get('isp')}")
            log.info(f"  Geo match: {geo_country} vs {expected_country} → {'OK' if geo_ok else 'FAIL'}")
            results.append({"label": label, "country_ok": country_ok, "ip": ip, "geo_ok": geo_ok, "geo": geo})
        except Exception as e:
            log.info(f"  PROXY CONNECTION FAILED: {e}")
            results.append({"label": label, "country_ok": country_ok, "ip": None, "geo_ok": False, "error": str(e)})

    return results


# ── Test 2: Sticky sessions ─────────────────────────────────

def test_sticky_sessions():
    log.info(f"\n{DIVIDER}")
    log.info("TEST 2: Sticky sessions (same session ID → same IP)")
    log.info(DIVIDER)

    phone = "+79120556339"
    account_id = 9999  # Fake account_id for testing

    proxy = infatica_proxy_service.get_proxy_for_account(phone, account_id=account_id)
    log.info(f"  Proxy (sticky): socks5://{proxy['username']}@{proxy['host']}:{proxy['port']}")

    ips = []
    for i in range(3):
        try:
            ip = fetch_ip_via_socks5(proxy["host"], proxy["port"], proxy["username"], proxy["password"])
            ips.append(ip)
            log.info(f"  Request {i+1}: IP = {ip}")
        except Exception as e:
            log.info(f"  Request {i+1}: FAILED — {e}")
            ips.append(None)
        time.sleep(1)

    valid_ips = [ip for ip in ips if ip]
    sticky_ok = len(set(valid_ips)) == 1 and len(valid_ips) >= 2
    log.info(f"  Sticky session: {'OK — all same IP' if sticky_ok else 'FAIL — IPs differ'}")

    return {"ips": ips, "sticky_ok": sticky_ok}


# ── Test 3: Telegram DC connectivity ────────────────────────

def test_telegram_dc():
    log.info(f"\n{DIVIDER}")
    log.info("TEST 3: Telegram DC connectivity through SOCKS5")
    log.info(DIVIDER)

    # Telegram DCs
    dcs = [
        ("149.154.175.53", 443, "DC1"),
        ("149.154.167.51", 443, "DC2"),
        ("149.154.175.100", 443, "DC3"),
        ("149.154.167.91", 443, "DC4"),
        ("91.108.56.130", 443, "DC5"),
    ]

    phone = "+79120556339"
    proxy = infatica_proxy_service.get_proxy_for_account(phone, account_id=56)

    results = []
    for dc_ip, dc_port, dc_name in dcs:
        try:
            latency = test_tcp_via_socks5(
                proxy["host"], proxy["port"], proxy["username"], proxy["password"],
                dc_ip, dc_port
            )
            log.info(f"  {dc_name} ({dc_ip}:{dc_port}): OK — {latency:.0f}ms")
            results.append({"dc": dc_name, "ok": True, "latency": latency})
        except Exception as e:
            log.info(f"  {dc_name} ({dc_ip}:{dc_port}): FAIL — {e}")
            results.append({"dc": dc_name, "ok": False, "error": str(e)})

    return results


# ── Test 4: Telethon client connection ───────────────────────

async def test_telethon_connect():
    log.info(f"\n{DIVIDER}")
    log.info("TEST 4: Telethon client connection through Infatica SOCKS5")
    log.info(DIVIDER)

    from app.db import async_session_maker
    from app.models.telegram_outreach import TgAccount
    from sqlalchemy import select

    # Find active accounts to test with (try multiple)
    async with async_session_maker() as session:
        accs = (await session.execute(
            select(TgAccount).where(TgAccount.status == "active").limit(5)
        )).scalars().all()

        if not accs:
            log.info("  No active accounts found — skipping Telethon test")
            return {"ok": False, "reason": "no active accounts"}

        log.info(f"  Found {len(accs)} active accounts, testing each...")

    from app.services.telegram_engine import telegram_engine

    for acc in accs:
        log.info(f"\n  --- Account id={acc.id}, phone={acc.phone} ---")
        proxy = infatica_proxy_service.get_proxy_for_account(acc.phone, account_id=acc.id)
        log.info(f"  Proxy: socks5://{proxy['username'][:40]}...@{proxy['host']}:{proxy['port']}")

        try:
            client = await telegram_engine.connect(
                acc.id,
                phone=acc.phone,
                api_id=acc.api_id,
                api_hash=acc.api_hash,
                proxy=proxy,
            )

            if client and client.is_connected():
                try:
                    me = await client.get_me()
                    if me:
                        log.info(f"  Telethon connected! User: {me.first_name} (@{me.username})")
                        log.info(f"  Premium: {getattr(me, 'premium', False)}")
                        await client.disconnect()
                        return {"ok": True, "user": me.username, "account_id": acc.id}
                    else:
                        log.info("  Connected but get_me() returned None (session expired?)")
                except Exception as e:
                    log.info(f"  Connected but get_me() failed: {e}")
                finally:
                    try:
                        await client.disconnect()
                    except Exception:
                        pass
            else:
                log.info("  Connection returned None or not connected")

        except Exception as e:
            log.info(f"  Connection FAILED: {e}")

    log.info("  No account could authenticate via Infatica SOCKS5")
    return {"ok": False, "reason": "all accounts failed auth"}


# ── Test 5: Send test message ────────────────────────────────

async def test_send_message(working_account_id=None):
    log.info(f"\n{DIVIDER}")
    log.info("TEST 5: Send test message through Infatica proxy")
    log.info(DIVIDER)

    from app.db import async_session_maker
    from app.models.telegram_outreach import TgAccount
    from sqlalchemy import select

    async with async_session_maker() as session:
        if working_account_id:
            acc = await session.get(TgAccount, working_account_id)
        else:
            acc = (await session.execute(
                select(TgAccount).where(TgAccount.status == "active").limit(1)
            )).scalar_one_or_none()

        if not acc:
            log.info("  No account available — skipping send test")
            return {"ok": False, "reason": "no account"}

        log.info(f"  Using account: id={acc.id}, phone={acc.phone}")

    proxy = infatica_proxy_service.get_proxy_for_account(acc.phone, account_id=acc.id)

    from app.services.telegram_engine import telegram_engine

    try:
        client = await telegram_engine.connect(
            acc.id,
            phone=acc.phone,
            api_id=acc.api_id,
            api_hash=acc.api_hash,
            proxy=proxy,
        )

        if not client or not client.is_connected():
            log.info("  Cannot connect — skipping send")
            return {"ok": False, "reason": "cannot connect"}

        # Send to Saved Messages (self)
        me = await client.get_me()
        if not me:
            log.info("  Connected but not authenticated — skipping send")
            await client.disconnect()
            return {"ok": False, "reason": "not authenticated"}

        await client.send_message("me", f"Infatica proxy test — {time.strftime('%Y-%m-%d %H:%M:%S')}")
        log.info(f"  Message sent to Saved Messages via @{me.username}")
        await client.disconnect()
        return {"ok": True}

    except Exception as e:
        log.info(f"  Send FAILED: {e}")
        return {"ok": False, "error": str(e)}


# ── Main ─────────────────────────────────────────────────────

async def main():
    log.info(f"\n{'#' * 60}")
    log.info("  INFATICA PROXY INTEGRATION TEST")
    log.info(f"{'#' * 60}")

    # Check config
    if not infatica_proxy_service.is_configured:
        log.info("\nFATAL: Infatica not configured (INFATICA_PROXY_USERNAME / PASSWORD missing)")
        return

    log.info(f"\nInfatica configured: host={settings.INFATICA_PROXY_HOST}, port={settings.INFATICA_PROXY_PORT}")
    log.info(f"Username prefix: {settings.INFATICA_PROXY_USERNAME[:10]}...")

    # Run tests
    r1 = test_country_routing()
    r2 = test_sticky_sessions()
    r3 = test_telegram_dc()
    r4 = await test_telethon_connect()
    working_id = r4.get("account_id")
    r5 = await test_send_message(working_account_id=working_id)

    # Summary
    log.info(f"\n{'#' * 60}")
    log.info("  SUMMARY")
    log.info(f"{'#' * 60}")

    all_ok = True

    # T1: Country routing
    for r in r1:
        ok = r.get("country_ok") and r.get("geo_ok")
        status = "PASS" if ok else "FAIL"
        log.info(f"  [{status}] Country routing: {r['label']}")
        if not ok:
            all_ok = False

    # T2: Sticky sessions
    status = "PASS" if r2["sticky_ok"] else "FAIL"
    log.info(f"  [{status}] Sticky sessions")
    if not r2["sticky_ok"]:
        all_ok = False

    # T3: Telegram DC
    dc_ok = sum(1 for r in r3 if r["ok"])
    status = "PASS" if dc_ok >= 3 else "FAIL"
    log.info(f"  [{status}] Telegram DC connectivity: {dc_ok}/{len(r3)} DCs reachable")
    if dc_ok < 3:
        all_ok = False

    # T4: Telethon
    status = "PASS" if r4.get("ok") else "FAIL"
    log.info(f"  [{status}] Telethon connection")
    if not r4.get("ok"):
        all_ok = False

    # T5: Send
    status = "PASS" if r5.get("ok") else "FAIL"
    log.info(f"  [{status}] Send test message")
    if not r5.get("ok"):
        all_ok = False

    log.info(f"\n  Overall: {'ALL TESTS PASSED' if all_ok else 'SOME TESTS FAILED'}")
    log.info(DIVIDER)


if __name__ == "__main__":
    asyncio.run(main())
