"""
Infatica.io residential proxy integration for Telegram accounts.

Generates geo-targeted SOCKS5 proxy configs with sticky sessions so each
Telegram account always exits through a consistent IP in its country.

Proxy URL format:
  socks5://user_c_{CC}_s_{id}_ttl_1h_rotm_2:pass@pool.infatica.io:10609
"""

import logging
from typing import Optional

import phonenumbers

from app.core.config import settings

logger = logging.getLogger(__name__)


class InfaticaProxyService:

    @property
    def is_configured(self) -> bool:
        return bool(settings.INFATICA_PROXY_USERNAME and settings.INFATICA_PROXY_PASSWORD)

    # ── Country detection ─────────────────────────────────────────────

    @staticmethod
    def get_country_for_phone(phone: str) -> str:
        """ISO 3166-1 alpha-2 country code from phone number.

        Special rule: +7 (Russia/Kazakhstan) always maps to BY (Belarus).
        """
        normalized = phone if phone.startswith("+") else f"+{phone}"
        try:
            parsed = phonenumbers.parse(normalized, None)
        except phonenumbers.NumberParseException:
            logger.warning(f"[PROXY] Cannot parse phone {phone}, defaulting to US")
            return "US"

        if parsed.country_code == 7:
            return "BY"

        region = phonenumbers.region_code_for_number(parsed)
        if region:
            return region.upper()

        # Fallback: first region for the country calling code
        regions = phonenumbers.region_codes_for_country_code(parsed.country_code)
        if regions:
            return regions[0].upper()

        return "US"

    # ── Proxy generation ──────────────────────────────────────────────

    def get_proxy_for_account(
        self,
        phone: str,
        account_id: Optional[int] = None,
    ) -> dict:
        """Generate Infatica proxy config for a Telegram account.

        Args:
            phone: Phone number with country code (e.g. "+351912345678").
            account_id: Account ID for sticky session (recommended).

        Returns:
            Proxy config dict with keys: protocol, host, port, username, password.
            Compatible with telegram_engine._proxy_to_tuple().
        """
        if not self.is_configured:
            raise RuntimeError("Infatica proxy not configured — set INFATICA_PROXY_USERNAME / PASSWORD")

        country = self.get_country_for_phone(phone)

        # Build username: base_c_{CC}[_s_{id}_ttl_1h_rotm_2]
        parts = [settings.INFATICA_PROXY_USERNAME, f"c_{country}"]
        if account_id is not None:
            parts.extend([f"s_{account_id}", "ttl_1h", "rotm_2"])
        proxy_username = "_".join(parts)

        proxy_config = {
            "protocol": "socks5",
            "host": settings.INFATICA_PROXY_HOST,
            "port": settings.INFATICA_PROXY_PORT,
            "username": proxy_username,
            "password": settings.INFATICA_PROXY_PASSWORD,
        }

        logger.info(
            f"[PROXY] Infatica proxy for {phone}: "
            f"country={country}, sticky={'yes' if account_id else 'no'}"
        )
        return proxy_config

    # ── Proxy testing ─────────────────────────────────────────────────

    async def test_proxy(self, proxy_url: str) -> bool:
        """Test if a proxy URL is reachable (returns external IP on success)."""
        import socks
        import socket

        try:
            proto, rest = proxy_url.split("://", 1)
            creds, hostport = rest.rsplit("@", 1)
            username, password = creds.split(":", 1)
            host, port_str = hostport.split(":", 1)
            port = int(port_str)
        except (ValueError, AttributeError):
            logger.error(f"[PROXY] Cannot parse proxy URL: {proxy_url}")
            return False

        try:
            s = socks.socksocket()
            s.set_proxy(socks.SOCKS5, host, port, rdns=True, username=username, password=password)
            s.settimeout(15)
            s.connect(("api.ipify.org", 80))
            s.sendall(b"GET /?format=text HTTP/1.1\r\nHost: api.ipify.org\r\nConnection: close\r\n\r\n")
            data = s.recv(4096).decode()
            s.close()
            # Extract IP from HTTP response body
            ip = data.split("\r\n\r\n", 1)[-1].strip()
            logger.info(f"[PROXY] Test OK: {host}:{port} → IP {ip}")
            return True
        except Exception as e:
            logger.warning(f"[PROXY] Test FAILED: {proxy_url} → {e}")
            return False

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def proxy_config_to_url(proxy_config: dict) -> str:
        """Convert proxy config dict to URL string."""
        proto = proxy_config.get("protocol", "socks5")
        host = proxy_config["host"]
        port = proxy_config["port"]
        username = proxy_config.get("username", "")
        password = proxy_config.get("password", "")
        if username and password:
            return f"{proto}://{username}:{password}@{host}:{port}"
        return f"{proto}://{host}:{port}"


infatica_proxy_service = InfaticaProxyService()
