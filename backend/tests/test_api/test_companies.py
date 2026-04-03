"""
Tests for Companies API endpoints.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Company, Environment
from tests.conftest import get_auth_headers


class TestCompaniesAPI:
    """Test suite for /api/companies endpoints."""
    
    @pytest.mark.asyncio
    async def test_list_companies_empty(self, client: AsyncClient, test_user: User):
        """Test listing companies when none exist."""
        response = await client.get("/api/companies")
        assert response.status_code == 200
        assert response.json() == []
    
    @pytest.mark.asyncio
    async def test_list_companies(self, client: AsyncClient, test_company: Company):
        """Test listing companies."""
        response = await client.get("/api/companies")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test Company"
        assert data[0]["prospects_count"] == 0
        assert data[0]["datasets_count"] == 0
    
    @pytest.mark.asyncio
    async def test_create_company(self, client: AsyncClient, test_user: User, test_environment: Environment):
        """Test creating a new company."""
        response = await client.post(
            "/api/companies",
            json={
                "name": "New Company",
                "description": "A new test company",
                "website": "https://newcompany.com",
                "color": "#FF5733",
                "environment_id": test_environment.id
            }
        )
        assert response.status_code == 201
        
        data = response.json()
        assert data["name"] == "New Company"
        assert data["description"] == "A new test company"
        assert data["website"] == "https://newcompany.com"
        assert data["color"] == "#FF5733"
        assert data["environment_id"] == test_environment.id
    
    @pytest.mark.asyncio
    async def test_create_company_minimal(self, client: AsyncClient, test_user: User):
        """Test creating a company with minimal data."""
        response = await client.post(
            "/api/companies",
            json={"name": "Minimal Company"}
        )
        assert response.status_code == 201
        
        data = response.json()
        assert data["name"] == "Minimal Company"
        assert data["color"] == "#3B82F6"  # Default color
    
    @pytest.mark.asyncio
    async def test_get_company(self, client: AsyncClient, test_company: Company):
        """Test getting a specific company."""
        response = await client.get(f"/api/companies/{test_company.id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == test_company.id
        assert data["name"] == "Test Company"
    
    @pytest.mark.asyncio
    async def test_get_company_not_found(self, client: AsyncClient, test_user: User):
        """Test getting a non-existent company."""
        response = await client.get("/api/companies/99999")
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_update_company(self, client: AsyncClient, test_company: Company):
        """Test updating a company."""
        response = await client.put(
            f"/api/companies/{test_company.id}",
            json={
                "name": "Updated Company",
                "description": "Updated description"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == "Updated Company"
        assert data["description"] == "Updated description"
    
    @pytest.mark.asyncio
    async def test_delete_company(self, client: AsyncClient, test_company: Company):
        """Test deleting a company (soft delete)."""
        response = await client.delete(f"/api/companies/{test_company.id}")
        assert response.status_code == 200
        
        # Verify company is no longer accessible
        response = await client.get(f"/api/companies/{test_company.id}")
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_get_current_user(self, client: AsyncClient, test_user: User):
        """Test getting current user info."""
        response = await client.get("/api/companies/me")
        assert response.status_code == 200
        
        data = response.json()
        assert data["user"]["name"] == "Test User"
        assert data["user"]["email"] == "test@example.com"


class TestCompanyFiltering:
    """Test company filtering by environment."""
    
    @pytest.mark.asyncio
    async def test_filter_by_environment(
        self, 
        client: AsyncClient, 
        db_session: AsyncSession,
        test_user: User,
        test_environment: Environment,
        test_company: Company
    ):
        """Test filtering companies by environment ID."""
        # Create another environment with a company
        env2 = Environment(
            user_id=test_user.id,
            name="Second Environment",
            is_active=True
        )
        db_session.add(env2)
        await db_session.flush()
        
        company2 = Company(
            user_id=test_user.id,
            environment_id=env2.id,
            name="Company in Env 2",
            is_active=True
        )
        db_session.add(company2)
        await db_session.flush()
        
        # Filter by first environment
        response = await client.get(f"/api/companies?environment_id={test_environment.id}")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test Company"
