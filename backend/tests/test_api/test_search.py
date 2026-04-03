"""
Tests for Search API endpoints.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company
from app.models.contact import Project
from app.models.domain import SearchJob, SearchResult
from tests.conftest import get_auth_headers


class TestSearchHistory:
    """Test suite for /api/search/history endpoint."""

    @pytest.mark.asyncio
    async def test_search_history_without_company_header(self, client: AsyncClient, test_user):
        """Search history requires X-Company-ID header — should return 422."""
        response = await client.get("/api/search/history")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_search_history_with_company_header_empty(self, client: AsyncClient, test_company: Company):
        """Search history with valid company but no jobs — should return empty list."""
        response = await client.get(
            "/api/search/history",
            headers=get_auth_headers(test_company.id),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_search_history_with_job(
        self,
        client: AsyncClient,
        test_company: Company,
        test_project: Project,
        test_search_job: SearchJob,
        test_search_result: SearchResult,
    ):
        """Search history returns job with summary fields."""
        response = await client.get(
            "/api/search/history",
            headers=get_auth_headers(test_company.id),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

        item = data["items"][0]
        assert item["id"] == test_search_job.id
        assert item["status"] == "completed"
        assert item["domains_found"] == 50
        assert item["targets_found"] == 1  # one is_target=True result
        assert item["project_name"] == "Test Project"


class TestSearchJobFull:
    """Test suite for /api/search/jobs/{id}/full endpoint."""

    @pytest.mark.asyncio
    async def test_search_job_full_without_company(self, client: AsyncClient, test_user, test_search_job: SearchJob):
        """Job full detail requires X-Company-ID header."""
        response = await client.get(f"/api/search/jobs/{test_search_job.id}/full")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_search_job_full_with_company(
        self,
        client: AsyncClient,
        test_company: Company,
        test_search_job: SearchJob,
        test_search_result: SearchResult,
    ):
        """Job full detail returns extended info."""
        response = await client.get(
            f"/api/search/jobs/{test_search_job.id}/full",
            headers=get_auth_headers(test_company.id),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_search_job.id
        assert data["results_total"] == 1
        assert data["targets_found"] == 1
        assert "yandex_cost" in data
        assert "total_cost_estimate" in data

    @pytest.mark.asyncio
    async def test_search_job_full_wrong_company(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user,
        test_search_job: SearchJob,
    ):
        """Job full detail with wrong company ID returns 404."""
        from app.models import Environment
        # Create a second company
        env2 = Environment(user_id=test_user.id, name="Env2", is_active=True)
        db_session.add(env2)
        await db_session.flush()
        other_company = Company(user_id=test_user.id, environment_id=env2.id, name="Other Co", is_active=True)
        db_session.add(other_company)
        await db_session.flush()

        response = await client.get(
            f"/api/search/jobs/{test_search_job.id}/full",
            headers=get_auth_headers(other_company.id),
        )
        assert response.status_code == 404


class TestSearchReview:
    """Test suite for review endpoints."""

    @pytest.mark.asyncio
    async def test_review_result(
        self,
        client: AsyncClient,
        test_company: Company,
        test_search_result: SearchResult,
    ):
        """POST review updates the result verdict."""
        response = await client.post(
            f"/api/search/results/{test_search_result.id}/review",
            json={"verdict": "confirmed", "note": "test review"},
            headers=get_auth_headers(test_company.id),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["review_status"] == "confirmed"
        assert data["id"] == test_search_result.id

    @pytest.mark.asyncio
    async def test_review_summary(
        self,
        client: AsyncClient,
        test_company: Company,
        test_search_job: SearchJob,
        test_search_result: SearchResult,
    ):
        """GET review summary returns counts."""
        response = await client.get(
            f"/api/search/jobs/{test_search_job.id}/review-summary",
            headers=get_auth_headers(test_company.id),
        )
        assert response.status_code == 200
        data = response.json()
        assert "confirmed" in data
        assert "rejected" in data
        assert "flagged" in data
        assert "unreviewed" in data
        assert data["total"] == 1
