"""
Tests for Reply Moderation Flow.

Covers:
1. Listing replies that need responses (needs_reply filter)
2. Conversation thread endpoint
3. Approve-and-send in DEBUG mode (dry_run — no SmartLead call)
4. Approve-and-send in production mode (mocked SmartLead)
5. Dismiss reply flow
6. Approval status filters (pending / approved / dismissed)
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from app.models.reply import ReplyAutomation, ProcessedReply
from app.models.contact import Contact, ContactActivity, Project
from app.core.config import settings as _settings


# ============= Helpers =============

async def _make_reply(
    db: AsyncSession,
    email: str = "lead@rizzult.com",
    campaign_name: str = "Rizzult Outreach Q1",
    category: str = "interested",
    approval_status: str | None = None,
    draft_reply: str | None = "Thanks for your interest!",
    received_at: datetime | None = None,
    automation_id: int | None = None,
) -> ProcessedReply:
    reply = ProcessedReply(
        automation_id=automation_id,
        campaign_id="camp_rizzult_001",
        campaign_name=campaign_name,
        lead_email=email,
        lead_first_name="John",
        lead_last_name="Doe",
        lead_company="Acme Corp",
        email_subject="Re: Partnership",
        email_body="I'm interested in your product.",
        reply_text="I'm interested in your product.",
        category=category,
        category_confidence="high",
        classification_reasoning="Explicit interest expressed",
        draft_reply=draft_reply,
        approval_status=approval_status,
        received_at=received_at or datetime.utcnow(),
        processed_at=datetime.utcnow(),
    )
    db.add(reply)
    await db.flush()
    await db.refresh(reply)
    return reply


async def _make_contact(
    db: AsyncSession,
    email: str = "lead@rizzult.com",
    smartlead_id: str | None = "sl_12345",
) -> Contact:
    contact = Contact(
        email=email,
        first_name="John",
        last_name="Doe",
        company_name="Acme Corp",
        source="smartlead",
        status="replied",
        smartlead_id=smartlead_id,
        campaigns=[{"source": "smartlead", "id": "camp_rizzult_001", "name": "Rizzult Outreach Q1"}],
    )
    db.add(contact)
    await db.flush()
    await db.refresh(contact)
    return contact


async def _make_activity(
    db: AsyncSession,
    contact_id: int,
    direction: str = "inbound",
    channel: str = "email",
    activity_type: str = "email_replied",
    body: str = "I'm interested",
    activity_at: datetime | None = None,
) -> ContactActivity:
    activity = ContactActivity(
        contact_id=contact_id,
        activity_type=activity_type,
        channel=channel,
        direction=direction,
        source="smartlead",
        subject="Re: Partnership",
        body=body,
        activity_at=activity_at or datetime.utcnow(),
    )
    db.add(activity)
    await db.flush()
    await db.refresh(activity)
    return activity


# ============= Test: Replies Needing Response (needs_reply filter) =============

class TestNeedsReplyFilter:
    """Test that needs_reply filter shows only pending replies with no outbound follow-up."""

    async def test_pending_reply_without_outbound_shows_up(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Pending reply with no outbound activity after it → needs_reply=true returns it."""
        contact = await _make_contact(db_session)
        reply = await _make_reply(db_session, approval_status=None)

        # Only inbound activity, no outbound
        await _make_activity(db_session, contact.id, direction="inbound", body="I'm interested")

        response = await client.get("/api/replies/", params={"needs_reply": True})
        assert response.status_code == 200
        data = response.json()
        emails = [r["lead_email"] for r in data["replies"]]
        assert "lead@rizzult.com" in emails

    async def test_replied_lead_with_outbound_hidden(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Reply that already has outbound activity after received_at → needs_reply hides it."""
        received = datetime.utcnow() - timedelta(hours=2)
        contact = await _make_contact(db_session)
        reply = await _make_reply(db_session, approval_status=None, received_at=received)

        # Outbound activity AFTER the reply was received
        await _make_activity(
            db_session,
            contact.id,
            direction="outbound",
            activity_type="email_sent",
            body="Thanks for getting back!",
            activity_at=datetime.utcnow(),
        )

        response = await client.get("/api/replies/", params={"needs_reply": True})
        assert response.status_code == 200
        data = response.json()
        emails = [r["lead_email"] for r in data["replies"]]
        assert "lead@rizzult.com" not in emails

    async def test_approved_reply_excluded_from_needs_reply(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Already-approved reply should not appear in needs_reply."""
        await _make_contact(db_session)
        await _make_reply(db_session, approval_status="approved")

        response = await client.get("/api/replies/", params={"needs_reply": True})
        assert response.status_code == 200
        data = response.json()
        emails = [r["lead_email"] for r in data["replies"]]
        assert "lead@rizzult.com" not in emails

    async def test_dismissed_reply_excluded_from_needs_reply(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Dismissed reply should not appear in needs_reply."""
        await _make_contact(db_session)
        await _make_reply(db_session, approval_status="dismissed")

        response = await client.get("/api/replies/", params={"needs_reply": True})
        assert response.status_code == 200
        data = response.json()
        emails = [r["lead_email"] for r in data["replies"]]
        assert "lead@rizzult.com" not in emails


# ============= Test: Conversation Thread =============

class TestConversationThread:
    """Test GET /replies/{reply_id}/conversation returns correct messages."""

    async def test_conversation_returns_chronological_messages(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Conversation endpoint returns inbound and outbound messages in order."""
        contact = await _make_contact(db_session)
        reply = await _make_reply(db_session)

        t1 = datetime.utcnow() - timedelta(hours=3)
        t2 = datetime.utcnow() - timedelta(hours=2)
        t3 = datetime.utcnow() - timedelta(hours=1)

        await _make_activity(db_session, contact.id, "outbound", body="Hi, want to chat?", activity_at=t1, activity_type="email_sent")
        await _make_activity(db_session, contact.id, "inbound", body="Yes, interested!", activity_at=t2, activity_type="email_replied")
        await _make_activity(db_session, contact.id, "outbound", body="Great, let's schedule.", activity_at=t3, activity_type="email_sent")

        response = await client.get(f"/api/replies/{reply.id}/conversation")
        assert response.status_code == 200
        data = response.json()

        assert len(data["messages"]) == 3
        assert data["contact_id"] == contact.id

        # Chronological order (oldest first)
        assert data["messages"][0]["direction"] == "outbound"
        assert data["messages"][0]["body"] == "Hi, want to chat?"
        assert data["messages"][1]["direction"] == "inbound"
        assert data["messages"][1]["body"] == "Yes, interested!"
        assert data["messages"][2]["direction"] == "outbound"
        assert data["messages"][2]["body"] == "Great, let's schedule."

    async def test_conversation_empty_when_no_contact(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Conversation returns empty when contact not found in DB."""
        reply = await _make_reply(db_session, email="unknown@example.com")

        response = await client.get(f"/api/replies/{reply.id}/conversation")
        assert response.status_code == 200
        data = response.json()
        assert data["messages"] == []

    async def test_conversation_404_for_missing_reply(
        self,
        client: AsyncClient,
    ):
        """Conversation returns 404 for non-existent reply."""
        response = await client.get("/api/replies/99999/conversation")
        assert response.status_code == 404


# ============= Test: Approve-and-Send (DEBUG = dry run) =============

class TestApproveAndSendDebug:
    """Test approve-and-send in DEBUG mode — no real SmartLead calls."""

    async def test_debug_mode_returns_dry_run(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """DEBUG=True → approval_status=approved_dry_run, dry_run=True, no SmartLead call."""
        reply = await _make_reply(db_session, approval_status=None)

        with patch.object(_settings, "DEBUG", True):
            with patch("app.api.replies._sync_approval_to_sheet", new_callable=AsyncMock):
                response = await client.post(f"/api/replies/{reply.id}/approve-and-send")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "approved_dry_run"
        assert data["dry_run"] is True
        assert data["reply_id"] == reply.id
        assert "SmartLead send skipped" in data["message"]

    async def test_debug_mode_updates_db_status(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """DEBUG=True → reply.approval_status is set to approved_dry_run in DB."""
        reply = await _make_reply(db_session, approval_status=None)

        with patch.object(_settings, "DEBUG", True):
            with patch("app.api.replies._sync_approval_to_sheet", new_callable=AsyncMock):
                await client.post(f"/api/replies/{reply.id}/approve-and-send")

        # Refresh from DB
        await db_session.refresh(reply)
        assert reply.approval_status == "approved_dry_run"
        assert reply.approved_at is not None

    async def test_debug_mode_no_smartlead_api_called(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """DEBUG=True → SmartleadService.send_reply is never called."""
        reply = await _make_reply(db_session, approval_status=None)

        with patch.object(_settings, "DEBUG", True):
            with patch("app.services.smartlead_service.SmartleadService") as mock_sl_class:
                with patch("app.api.replies._sync_approval_to_sheet", new_callable=AsyncMock):
                    response = await client.post(f"/api/replies/{reply.id}/approve-and-send")

        assert response.status_code == 200
        # SmartleadService should never be instantiated in debug mode
        mock_sl_class.assert_not_called()

    async def test_approve_twice_returns_400(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Approving an already-approved reply returns 400."""
        reply = await _make_reply(db_session, approval_status="approved_dry_run")

        response = await client.post(f"/api/replies/{reply.id}/approve-and-send")

        assert response.status_code == 400
        assert "already approved" in response.json()["detail"].lower()

    async def test_approve_without_draft_returns_400(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Approving a reply without a draft returns 400."""
        reply = await _make_reply(db_session, draft_reply=None, approval_status=None)

        response = await client.post(f"/api/replies/{reply.id}/approve-and-send")

        assert response.status_code == 400
        assert "no draft" in response.json()["detail"].lower()


# ============= Test: Approve-and-Send (Production) =============

class TestApproveAndSendProduction:
    """Test approve-and-send in production mode — SmartLead is called."""

    async def test_production_sends_via_smartlead(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Production mode: SmartLead send_reply is called, status=approved, dry_run=False."""
        contact = await _make_contact(db_session, smartlead_id="sl_99")
        reply = await _make_reply(db_session, approval_status=None)

        mock_sl_instance = MagicMock()
        mock_sl_instance.send_reply = AsyncMock(return_value={"message": "Sent successfully"})

        with patch.object(_settings, "DEBUG", False):
            with patch("app.services.smartlead_service.SmartleadService", return_value=mock_sl_instance):
                with patch("app.api.replies._sync_approval_to_sheet", new_callable=AsyncMock):
                    response = await client.post(f"/api/replies/{reply.id}/approve-and-send")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "approved"
        assert data["dry_run"] is False
        assert data["lead_email"] == "lead@rizzult.com"

        # Verify SmartLead was actually called
        mock_sl_instance.send_reply.assert_called_once()
        call_kwargs = mock_sl_instance.send_reply.call_args
        assert call_kwargs.kwargs["campaign_id"] == "camp_rizzult_001"
        assert call_kwargs.kwargs["lead_id"] == "sl_99"

    async def test_production_updates_db_to_approved(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Production: reply.approval_status=approved in DB."""
        contact = await _make_contact(db_session, smartlead_id="sl_99")
        reply = await _make_reply(db_session, approval_status=None)

        mock_sl_instance = MagicMock()
        mock_sl_instance.send_reply = AsyncMock(return_value={"message": "OK"})

        with patch.object(_settings, "DEBUG", False):
            with patch("app.services.smartlead_service.SmartleadService", return_value=mock_sl_instance):
                with patch("app.api.replies._sync_approval_to_sheet", new_callable=AsyncMock):
                    await client.post(f"/api/replies/{reply.id}/approve-and-send")

        await db_session.refresh(reply)
        assert reply.approval_status == "approved"
        assert reply.approved_at is not None

    async def test_production_no_contact_returns_400(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Production: if contact has no smartlead_id → 400 error."""
        # Contact without smartlead_id
        await _make_contact(db_session, smartlead_id=None)
        reply = await _make_reply(db_session, approval_status=None)

        with patch.object(_settings, "DEBUG", False):
            response = await client.post(f"/api/replies/{reply.id}/approve-and-send")

        assert response.status_code == 400
        assert "Contact not found" in response.json()["detail"] or "SmartLead ID" in response.json()["detail"]

    async def test_production_smartlead_error_returns_502(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Production: if SmartLead returns error → 502."""
        contact = await _make_contact(db_session, smartlead_id="sl_99")
        reply = await _make_reply(db_session, approval_status=None)

        mock_sl_instance = MagicMock()
        mock_sl_instance.send_reply = AsyncMock(return_value={"error": "API rate limited"})

        with patch.object(_settings, "DEBUG", False):
            with patch("app.services.smartlead_service.SmartleadService", return_value=mock_sl_instance):
                response = await client.post(f"/api/replies/{reply.id}/approve-and-send")

        assert response.status_code == 502
        assert "API rate limited" in response.json()["detail"]


# ============= Test: Dismiss Reply =============

class TestDismissReply:
    """Test dismissing a reply via PATCH /replies/{id}/status."""

    async def test_dismiss_sets_status(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Dismiss: sets approval_status to 'dismissed'."""
        reply = await _make_reply(db_session, approval_status=None)

        response = await client.patch(
            f"/api/replies/{reply.id}/status",
            params={"approval_status": "dismissed"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["approval_status"] == "dismissed"

    async def test_dismiss_updates_db(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Dismiss persists to DB."""
        reply = await _make_reply(db_session, approval_status=None)

        await client.patch(
            f"/api/replies/{reply.id}/status",
            params={"approval_status": "dismissed"},
        )

        await db_session.refresh(reply)
        assert reply.approval_status == "dismissed"

    async def test_dismiss_then_not_in_pending(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """After dismissing, reply no longer appears in pending filter."""
        reply = await _make_reply(db_session, approval_status=None)

        await client.patch(
            f"/api/replies/{reply.id}/status",
            params={"approval_status": "dismissed"},
        )

        response = await client.get("/api/replies/", params={"approval_status": "pending"})
        assert response.status_code == 200
        reply_ids = [r["id"] for r in response.json()["replies"]]
        assert reply.id not in reply_ids

    async def test_invalid_status_returns_400(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Invalid approval_status returns 400."""
        reply = await _make_reply(db_session, approval_status=None)

        response = await client.patch(
            f"/api/replies/{reply.id}/status",
            params={"approval_status": "invalid_status"},
        )

        assert response.status_code == 400


# ============= Test: Approval Status Filters =============

class TestApprovalStatusFilters:
    """Test that filtering by approval_status works correctly."""

    async def test_pending_filter_includes_null_and_pending(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """pending filter returns replies with null OR 'pending' status."""
        await _make_reply(db_session, email="null@test.com", approval_status=None)
        await _make_reply(db_session, email="pending@test.com", approval_status="pending")
        await _make_reply(db_session, email="approved@test.com", approval_status="approved")

        response = await client.get("/api/replies/", params={"approval_status": "pending"})
        assert response.status_code == 200
        data = response.json()

        emails = [r["lead_email"] for r in data["replies"]]
        assert "null@test.com" in emails
        assert "pending@test.com" in emails
        assert "approved@test.com" not in emails

    async def test_approved_filter(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """approved filter returns only approved replies."""
        await _make_reply(db_session, email="pending@test.com", approval_status=None)
        await _make_reply(db_session, email="approved@test.com", approval_status="approved")
        await _make_reply(db_session, email="dismissed@test.com", approval_status="dismissed")

        response = await client.get("/api/replies/", params={"approval_status": "approved"})
        assert response.status_code == 200
        data = response.json()

        emails = [r["lead_email"] for r in data["replies"]]
        assert "approved@test.com" in emails
        assert "pending@test.com" not in emails
        assert "dismissed@test.com" not in emails

    async def test_dismissed_filter(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """dismissed filter returns only dismissed replies."""
        await _make_reply(db_session, email="pending@test.com", approval_status=None)
        await _make_reply(db_session, email="dismissed@test.com", approval_status="dismissed")

        response = await client.get("/api/replies/", params={"approval_status": "dismissed"})
        assert response.status_code == 200
        data = response.json()

        emails = [r["lead_email"] for r in data["replies"]]
        assert "dismissed@test.com" in emails
        assert "pending@test.com" not in emails

    async def test_campaign_name_filter(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Filter by campaign_names returns only matching campaign's replies."""
        await _make_reply(db_session, email="rizzult@test.com", campaign_name="Rizzult Outreach Q1")
        await _make_reply(db_session, email="other@test.com", campaign_name="Other Campaign")

        response = await client.get("/api/replies/", params={"campaign_names": "Rizzult Outreach Q1"})
        assert response.status_code == 200
        data = response.json()

        emails = [r["lead_email"] for r in data["replies"]]
        assert "rizzult@test.com" in emails
        assert "other@test.com" not in emails
