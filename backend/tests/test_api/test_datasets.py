"""
Tests for Datasets API endpoints.
"""

import pytest
import io
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Company, Dataset, DataRow
from tests.conftest import get_auth_headers


class TestDatasetsAPI:
    """Test suite for /api/datasets endpoints."""
    
    @pytest.mark.asyncio
    async def test_list_datasets_empty(self, client: AsyncClient, test_company: Company):
        """Test listing datasets when none exist."""
        response = await client.get(
            "/api/datasets",
            headers=get_auth_headers(test_company.id)
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["datasets"] == []
        assert data["total"] == 0
    
    @pytest.mark.asyncio
    async def test_list_datasets(self, client: AsyncClient, test_company: Company, test_dataset: Dataset):
        """Test listing datasets."""
        response = await client.get(
            "/api/datasets",
            headers=get_auth_headers(test_company.id)
        )
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["datasets"]) == 1
        assert data["datasets"][0]["name"] == "Test Dataset"
        assert data["total"] == 1
    
    @pytest.mark.asyncio
    async def test_list_datasets_requires_company(self, client: AsyncClient):
        """Test that listing datasets requires X-Company-ID header."""
        response = await client.get("/api/datasets")
        assert response.status_code == 422  # Missing header
    
    @pytest.mark.asyncio
    async def test_get_dataset(self, client: AsyncClient, test_company: Company, test_dataset: Dataset):
        """Test getting a specific dataset."""
        response = await client.get(
            f"/api/datasets/{test_dataset.id}",
            headers=get_auth_headers(test_company.id)
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == test_dataset.id
        assert data["name"] == "Test Dataset"
        assert data["columns"] == ["email", "first_name", "last_name", "company"]
    
    @pytest.mark.asyncio
    async def test_get_dataset_not_found(self, client: AsyncClient, test_company: Company):
        """Test getting a non-existent dataset."""
        response = await client.get(
            "/api/datasets/99999",
            headers=get_auth_headers(test_company.id)
        )
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_get_dataset_rows(
        self, 
        client: AsyncClient, 
        test_company: Company, 
        test_dataset: Dataset,
        test_data_rows: list[DataRow]
    ):
        """Test getting rows from a dataset."""
        response = await client.get(
            f"/api/datasets/{test_dataset.id}/rows",
            headers=get_auth_headers(test_company.id)
        )
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["rows"]) == 3
        assert data["total"] == 3
        assert data["rows"][0]["data"]["email"] == "john@example.com"
    
    @pytest.mark.asyncio
    async def test_get_dataset_rows_pagination(
        self, 
        client: AsyncClient, 
        test_company: Company, 
        test_dataset: Dataset,
        test_data_rows: list[DataRow]
    ):
        """Test pagination when getting rows."""
        response = await client.get(
            f"/api/datasets/{test_dataset.id}/rows?page=1&page_size=2",
            headers=get_auth_headers(test_company.id)
        )
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["rows"]) == 2
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total_pages"] == 2
    
    @pytest.mark.asyncio
    async def test_rename_dataset(self, client: AsyncClient, test_company: Company, test_dataset: Dataset):
        """Test renaming a dataset."""
        response = await client.patch(
            f"/api/datasets/{test_dataset.id}/rename?name=Renamed Dataset",
            headers=get_auth_headers(test_company.id)
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == "Renamed Dataset"
    
    @pytest.mark.asyncio
    async def test_delete_dataset(self, client: AsyncClient, test_company: Company, test_dataset: Dataset):
        """Test deleting a dataset (soft delete)."""
        response = await client.delete(
            f"/api/datasets/{test_dataset.id}",
            headers=get_auth_headers(test_company.id)
        )
        assert response.status_code == 200
        
        # Verify dataset is no longer accessible
        response = await client.get(
            f"/api/datasets/{test_dataset.id}",
            headers=get_auth_headers(test_company.id)
        )
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_get_all_columns(
        self, 
        client: AsyncClient, 
        test_company: Company, 
        test_dataset: Dataset
    ):
        """Test getting all columns including enriched ones."""
        response = await client.get(
            f"/api/datasets/{test_dataset.id}/all-columns",
            headers=get_auth_headers(test_company.id)
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "original_columns" in data
        assert "enriched_columns" in data
        assert "all_columns" in data


class TestCSVUpload:
    """Test CSV file upload functionality."""
    
    @pytest.mark.asyncio
    async def test_upload_csv(self, client: AsyncClient, test_company: Company):
        """Test uploading a CSV file."""
        csv_content = "email,first_name,last_name\njohn@test.com,John,Doe\njane@test.com,Jane,Smith"
        
        response = await client.post(
            "/api/datasets/upload-csv",
            headers=get_auth_headers(test_company.id),
            files={"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == "test"
        assert data["source_type"] == "csv"
        assert data["row_count"] == 2
        assert "email" in data["columns"]
    
    @pytest.mark.asyncio
    async def test_upload_csv_with_name(self, client: AsyncClient, test_company: Company):
        """Test uploading a CSV file with custom name."""
        csv_content = "email,name\ntest@test.com,Test"
        
        response = await client.post(
            "/api/datasets/upload-csv?name=Custom Dataset",
            headers=get_auth_headers(test_company.id),
            files={"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == "Custom Dataset"
    
    @pytest.mark.asyncio
    async def test_upload_non_csv(self, client: AsyncClient, test_company: Company):
        """Test uploading a non-CSV file fails."""
        response = await client.post(
            "/api/datasets/upload-csv",
            headers=get_auth_headers(test_company.id),
            files={"file": ("test.txt", io.BytesIO(b"not a csv"), "text/plain")}
        )
        assert response.status_code == 400
