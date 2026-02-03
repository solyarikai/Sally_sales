"""
Tests for CRM Contacts API endpoints
"""
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.db import get_session
from app.models.contact import Contact
from datetime import datetime


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Create test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestContactsAPI:
    """Tests for the contacts API."""

    @pytest.mark.anyio
    async def test_list_contacts_without_company(self, client: AsyncClient):
        """Test that contacts can be listed without X-Company-ID header."""
        response = await client.get("/api/contacts")
        assert response.status_code == 200
        data = response.json()
        assert "contacts" in data
        assert "total" in data
        assert isinstance(data["contacts"], list)

    @pytest.mark.anyio
    async def test_list_contacts_with_pagination(self, client: AsyncClient):
        """Test pagination parameters."""
        response = await client.get("/api/contacts?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["contacts"]) <= 10

    @pytest.mark.anyio
    async def test_list_contacts_filter_by_source(self, client: AsyncClient):
        """Test filtering by source."""
        response = await client.get("/api/contacts?source=smartlead")
        assert response.status_code == 200
        data = response.json()
        for contact in data["contacts"]:
            assert "smartlead" in contact["source"]

    @pytest.mark.anyio
    async def test_list_contacts_filter_by_has_replied(self, client: AsyncClient):
        """Test filtering by has_replied status."""
        response = await client.get("/api/contacts?has_replied=true")
        assert response.status_code == 200
        data = response.json()
        for contact in data["contacts"]:
            assert contact.get("has_replied") == True

    @pytest.mark.anyio
    async def test_get_contact_stats(self, client: AsyncClient):
        """Test getting contact statistics."""
        response = await client.get("/api/contacts/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "by_status" in data or "by_source" in data

    @pytest.mark.anyio
    async def test_get_filter_options(self, client: AsyncClient):
        """Test getting filter options."""
        response = await client.get("/api/contacts/filters")
        assert response.status_code == 200
        data = response.json()
        # Should contain available filter values
        assert isinstance(data, dict)


class TestCRMSyncAPI:
    """Tests for the CRM sync API."""

    @pytest.mark.anyio
    async def test_get_sync_status(self, client: AsyncClient):
        """Test getting sync status."""
        response = await client.get(
            "/api/crm-sync/status",
            headers={"X-Company-ID": "1"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_contacts" in data
        assert "by_source" in data

    @pytest.mark.anyio
    async def test_trigger_sync_requires_body(self, client: AsyncClient):
        """Test that trigger sync requires a request body."""
        response = await client.post(
            "/api/crm-sync/trigger",
            headers={"X-Company-ID": "1"}
        )
        # Should fail with missing body
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_trigger_sync_with_body(self, client: AsyncClient):
        """Test triggering sync with proper body."""
        response = await client.post(
            "/api/crm-sync/trigger",
            headers={"X-Company-ID": "1", "Content-Type": "application/json"},
            json={"sources": ["smartlead"], "full_sync": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True


class TestContactSearch:
    """Tests for contact search functionality."""

    @pytest.mark.anyio
    async def test_search_contacts_by_email(self, client: AsyncClient):
        """Test searching contacts by email."""
        response = await client.get("/api/contacts?search=test@example.com")
        assert response.status_code == 200
        data = response.json()
        # Search should work even if no results
        assert "contacts" in data

    @pytest.mark.anyio
    async def test_search_contacts_by_name(self, client: AsyncClient):
        """Test searching contacts by name."""
        response = await client.get("/api/contacts?search=John")
        assert response.status_code == 200
        data = response.json()
        assert "contacts" in data


class TestContactSorting:
    """Tests for contact sorting."""

    @pytest.mark.anyio
    async def test_sort_contacts_by_created_at(self, client: AsyncClient):
        """Test sorting contacts by created_at."""
        response = await client.get("/api/contacts?sort_by=created_at&sort_order=desc")
        assert response.status_code == 200
        data = response.json()
        contacts = data["contacts"]
        if len(contacts) >= 2:
            # Verify descending order
            dates = [c["created_at"] for c in contacts]
            assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_sort_contacts_by_email(self, client: AsyncClient):
        """Test sorting contacts by email."""
        response = await client.get("/api/contacts?sort_by=email&sort_order=asc")
        assert response.status_code == 200
        data = response.json()
        assert "contacts" in data
