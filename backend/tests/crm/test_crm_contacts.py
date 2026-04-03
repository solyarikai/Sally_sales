"""
Tests for CRM Contacts API endpoints
"""
import pytest
from httpx import AsyncClient


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
        assert "contacts" in data
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
        # Just check it returns valid response (may be empty)
        assert "contacts" in data

    @pytest.mark.anyio
    async def test_get_contact_stats(self, client: AsyncClient):
        """Test getting contact statistics."""
        response = await client.get("/api/contacts/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data

    @pytest.mark.anyio
    async def test_get_filter_options(self, client: AsyncClient):
        """Test getting filter options."""
        response = await client.get("/api/contacts/filters")
        assert response.status_code == 200
        data = response.json()
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
        # Should fail with 422 (missing body)
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_trigger_sync_with_body(self, client: AsyncClient):
        """Test triggering sync with proper body."""
        response = await client.post(
            "/api/crm-sync/trigger",
            headers={"X-Company-ID": "1"},
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
        response = await client.get("/api/contacts?search=test")
        assert response.status_code == 200
        data = response.json()
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
        assert "contacts" in data

    @pytest.mark.anyio
    async def test_sort_contacts_by_email(self, client: AsyncClient):
        """Test sorting contacts by email."""
        response = await client.get("/api/contacts?sort_by=email&sort_order=asc")
        assert response.status_code == 200
        data = response.json()
        assert "contacts" in data


class TestFollowUpFilter:
    """Tests for follow-up filter."""

    @pytest.mark.anyio
    async def test_filter_needs_followup(self, client: AsyncClient):
        """Test filtering contacts needing follow-up."""
        response = await client.get("/api/contacts?needs_followup=true")
        assert response.status_code == 200
        data = response.json()
        assert "contacts" in data


class TestCampaignFilter:
    """Tests for campaign filter and autocomplete."""

    @pytest.mark.anyio
    async def test_get_campaigns_list(self, client: AsyncClient):
        """Test getting campaigns list for autocomplete."""
        response = await client.get("/api/contacts/campaigns")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.anyio
    async def test_filter_by_campaign(self, client: AsyncClient):
        """Test filtering by campaign name."""
        response = await client.get("/api/contacts?campaign=test")
        assert response.status_code == 200
        data = response.json()
        assert "contacts" in data
