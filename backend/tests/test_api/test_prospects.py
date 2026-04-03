"""
Tests for Prospects API endpoints.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, Prospect, Dataset, DataRow
from tests.conftest import get_auth_headers


class TestProspectsAPI:
    """Test suite for /api/prospects endpoints."""
    
    @pytest.mark.asyncio
    async def test_list_prospects_empty(self, client: AsyncClient, test_company: Company):
        """Test listing prospects when none exist."""
        response = await client.get(
            "/api/prospects",
            headers=get_auth_headers(test_company.id)
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["prospects"] == []
        assert data["total"] == 0
    
    @pytest.mark.asyncio
    async def test_list_prospects(self, client: AsyncClient, test_company: Company, test_prospect: Prospect):
        """Test listing prospects."""
        response = await client.get(
            "/api/prospects",
            headers=get_auth_headers(test_company.id)
        )
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["prospects"]) == 1
        assert data["prospects"][0]["email"] == "prospect@example.com"
        assert data["total"] == 1
    
    @pytest.mark.asyncio
    async def test_list_prospects_pagination(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company
    ):
        """Test pagination when listing prospects."""
        # Create multiple prospects
        for i in range(15):
            prospect = Prospect(
                company_id=test_company.id,
                email=f"prospect{i}@example.com",
                first_name=f"Prospect{i}",
                sources=[]
            )
            db_session.add(prospect)
        await db_session.flush()
        
        response = await client.get(
            "/api/prospects?page=1&page_size=10",
            headers=get_auth_headers(test_company.id)
        )
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["prospects"]) == 10
        assert data["total"] == 15
        assert data["total_pages"] == 2
    
    @pytest.mark.asyncio
    async def test_list_prospects_search(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company
    ):
        """Test searching prospects."""
        # Create prospects with different names
        prospect1 = Prospect(
            company_id=test_company.id,
            email="alice@example.com",
            first_name="Alice",
            sources=[]
        )
        prospect2 = Prospect(
            company_id=test_company.id,
            email="bob@example.com",
            first_name="Bob",
            sources=[]
        )
        db_session.add_all([prospect1, prospect2])
        await db_session.flush()
        
        response = await client.get(
            "/api/prospects?search=alice",
            headers=get_auth_headers(test_company.id)
        )
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["prospects"]) == 1
        assert data["prospects"][0]["first_name"] == "Alice"
    
    @pytest.mark.asyncio
    async def test_get_prospect(self, client: AsyncClient, test_company: Company, test_prospect: Prospect):
        """Test getting a specific prospect."""
        response = await client.get(
            f"/api/prospects/{test_prospect.id}",
            headers=get_auth_headers(test_company.id)
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == test_prospect.id
        assert data["email"] == "prospect@example.com"
        assert data["first_name"] == "Test"
    
    @pytest.mark.asyncio
    async def test_get_prospect_not_found(self, client: AsyncClient, test_company: Company):
        """Test getting a non-existent prospect."""
        response = await client.get(
            "/api/prospects/99999",
            headers=get_auth_headers(test_company.id)
        )
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_update_prospect(self, client: AsyncClient, test_company: Company, test_prospect: Prospect):
        """Test updating a prospect."""
        response = await client.patch(
            f"/api/prospects/{test_prospect.id}",
            headers=get_auth_headers(test_company.id),
            json={
                "first_name": "Updated",
                "job_title": "CTO"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["first_name"] == "Updated"
        assert data["job_title"] == "CTO"
    
    @pytest.mark.asyncio
    async def test_delete_prospect(self, client: AsyncClient, test_company: Company, test_prospect: Prospect):
        """Test deleting a prospect (soft delete)."""
        response = await client.delete(
            f"/api/prospects/{test_prospect.id}",
            headers=get_auth_headers(test_company.id)
        )
        assert response.status_code == 200
        
        # Verify prospect is no longer accessible
        response = await client.get(
            f"/api/prospects/{test_prospect.id}",
            headers=get_auth_headers(test_company.id)
        )
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_update_prospect_tags(
        self, 
        client: AsyncClient, 
        test_company: Company, 
        test_prospect: Prospect
    ):
        """Test updating prospect tags."""
        response = await client.post(
            f"/api/prospects/{test_prospect.id}/tags",
            headers=get_auth_headers(test_company.id),
            json={"tags": ["hot", "priority"]}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "hot" in data["tags"]
        assert "priority" in data["tags"]
    
    @pytest.mark.asyncio
    async def test_update_prospect_status(
        self, 
        client: AsyncClient, 
        test_company: Company, 
        test_prospect: Prospect
    ):
        """Test updating prospect status."""
        response = await client.patch(
            f"/api/prospects/{test_prospect.id}/status",
            headers=get_auth_headers(test_company.id),
            json={"status": "contacted"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "contacted"
    
    @pytest.mark.asyncio
    async def test_get_prospect_stats(self, client: AsyncClient, test_company: Company, test_prospect: Prospect):
        """Test getting prospect statistics."""
        response = await client.get(
            "/api/prospects/stats",
            headers=get_auth_headers(test_company.id)
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["total_prospects"] == 1
        assert data["prospects_with_email"] == 1
    
    @pytest.mark.asyncio
    async def test_get_core_fields(self, client: AsyncClient, test_company: Company):
        """Test getting list of core fields."""
        response = await client.get(
            "/api/prospects/core-fields",
            headers=get_auth_headers(test_company.id)
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "email" in data
        assert "first_name" in data


class TestProspectImport:
    """Test prospect import functionality."""
    
    @pytest.mark.asyncio
    async def test_add_from_dataset(
        self,
        client: AsyncClient,
        test_company: Company,
        test_dataset: Dataset,
        test_data_rows: list[DataRow]
    ):
        """Test adding prospects from a dataset."""
        response = await client.post(
            "/api/prospects/add-from-dataset",
            headers=get_auth_headers(test_company.id),
            json={
                "dataset_id": test_dataset.id,
                "field_mappings": [
                    {"source_column": "email", "target_field": "email"},
                    {"source_column": "first_name", "target_field": "first_name"},
                    {"source_column": "last_name", "target_field": "last_name"},
                    {"source_column": "company", "target_field": "company_name"}
                ]
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert data["new_prospects"] == 3
        assert data["updated_prospects"] == 0


class TestProspectExport:
    """Test prospect export functionality."""
    
    @pytest.mark.asyncio
    async def test_export_csv(
        self,
        client: AsyncClient,
        test_company: Company,
        test_prospect: Prospect
    ):
        """Test exporting prospects as CSV."""
        response = await client.post(
            "/api/prospects/export/csv",
            headers=get_auth_headers(test_company.id),
            json={}
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
    
    @pytest.mark.asyncio
    async def test_export_clipboard(
        self,
        client: AsyncClient,
        test_company: Company,
        test_prospect: Prospect
    ):
        """Test exporting prospects for clipboard."""
        response = await client.post(
            "/api/prospects/export/clipboard",
            headers=get_auth_headers(test_company.id),
            json={}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["row_count"] == 1
        assert "data" in data
