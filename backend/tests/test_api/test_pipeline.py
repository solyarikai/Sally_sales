"""
Tests for Pipeline API endpoints.
"""

import pytest
from httpx import AsyncClient

from app.models import Company
from tests.conftest import get_auth_headers


class TestPipelineAPI:
    """Test suite for /api/pipeline endpoints."""

    @pytest.mark.asyncio
    async def test_list_discovered_companies_without_company(self, client: AsyncClient, test_user):
        """Discovered companies list requires X-Company-ID header — should return 422."""
        response = await client.get("/api/pipeline/discovered-companies")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_discovered_companies_with_company(self, client: AsyncClient, test_company: Company):
        """Discovered companies list with valid company but no data — should return empty."""
        response = await client.get(
            "/api/pipeline/discovered-companies",
            headers=get_auth_headers(test_company.id),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_pipeline_stats_without_company(self, client: AsyncClient, test_user):
        """Pipeline stats requires X-Company-ID header — should return 422."""
        response = await client.get("/api/pipeline/stats")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_pipeline_stats_with_company(self, client: AsyncClient, test_company: Company):
        """Pipeline stats with valid company — should return zeroed stats."""
        response = await client.get(
            "/api/pipeline/stats",
            headers=get_auth_headers(test_company.id),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_discovered"] == 0
        assert data["targets"] == 0
