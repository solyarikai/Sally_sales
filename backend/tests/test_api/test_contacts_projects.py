"""
Tests for Contacts projects list endpoint.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Company, Environment
from app.models.contact import Project
from tests.conftest import get_auth_headers


class TestContactsProjectsList:
    """Test suite for GET /api/contacts/projects/list endpoint."""

    @pytest.mark.asyncio
    async def test_list_projects_no_header_returns_all(
        self,
        client: AsyncClient,
        test_project: Project,
    ):
        """Without X-Company-ID header, should return all non-deleted projects."""
        response = await client.get("/api/contacts/projects/list")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        names = [p["name"] for p in data]
        assert "Test Project" in names

    @pytest.mark.asyncio
    async def test_list_projects_with_header_filters(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_company: Company,
        test_project: Project,
    ):
        """With X-Company-ID header, should return only matching projects."""
        # Create a second company with its own project
        env2 = Environment(user_id=test_user.id, name="Env2", is_active=True)
        db_session.add(env2)
        await db_session.flush()
        other_company = Company(user_id=test_user.id, environment_id=env2.id, name="Other Co", is_active=True)
        db_session.add(other_company)
        await db_session.flush()
        other_project = Project(company_id=other_company.id, name="Other Project")
        db_session.add(other_project)
        await db_session.flush()

        # Filter by test_company — should only see Test Project
        response = await client.get(
            "/api/contacts/projects/list",
            headers=get_auth_headers(test_company.id),
        )
        assert response.status_code == 200
        data = response.json()
        names = [p["name"] for p in data]
        assert "Test Project" in names
        assert "Other Project" not in names

    @pytest.mark.asyncio
    async def test_list_projects_empty_db(self, client: AsyncClient, test_user: User):
        """With no projects at all, should return empty list."""
        response = await client.get("/api/contacts/projects/list")
        assert response.status_code == 200
        data = response.json()
        assert data == []
