"""
Tests for Reply Automation API endpoints.

Tests cover:
- Creating, listing, updating, and deleting automations
- Listing and filtering processed replies
- Stats endpoint
- Webhook endpoint
- Resend notification endpoint
- Regenerate-draft endpoint
"""

import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.models.reply import ReplyAutomation, ProcessedReply, ReplyCategory, ReplyPromptTemplateModel
from app.models.contact import Project


class TestReplyAutomations:
    """Tests for /api/replies/automations endpoints."""

    async def test_list_automations_empty(self, client: AsyncClient, db_session: AsyncSession):
        """Test listing automations when none exist."""
        response = await client.get("/api/replies/automations")
        assert response.status_code == 200
        data = response.json()
        assert data["automations"] == []
        assert data["total"] == 0

    async def test_create_automation(self, client: AsyncClient, db_session: AsyncSession):
        """Test creating a new automation."""
        payload = {
            "name": "Test Automation",
            "campaign_ids": ["camp_123", "camp_456"],
            "slack_webhook_url": "https://hooks.slack.com/services/test",
            "slack_channel": "#test-channel",
            "auto_classify": True,
            "auto_generate_reply": True,
            "active": True
        }
        
        response = await client.post("/api/replies/automations", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "Test Automation"
        assert data["campaign_ids"] == ["camp_123", "camp_456"]
        assert data["slack_webhook_url"] == "https://hooks.slack.com/services/test"
        assert data["auto_classify"] is True
        assert data["active"] is True
        assert "id" in data

    async def test_create_automation_minimal(self, client: AsyncClient, db_session: AsyncSession):
        """Test creating automation with minimal required fields."""
        payload = {
            "name": "Minimal Automation",
            "campaign_ids": ["camp_789"]
        }
        
        response = await client.post("/api/replies/automations", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "Minimal Automation"
        assert data["campaign_ids"] == ["camp_789"]
        # Check defaults
        assert data["auto_classify"] is True
        assert data["auto_generate_reply"] is True

    async def test_list_automations(self, client: AsyncClient, db_session: AsyncSession):
        """Test listing automations after creating some."""
        # Create two automations
        for i in range(2):
            automation = ReplyAutomation(
                name=f"Automation {i}",
                campaign_ids=[f"camp_{i}"],
                active=True
            )
            db_session.add(automation)
        await db_session.flush()
        
        response = await client.get("/api/replies/automations")
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 2
        assert len(data["automations"]) == 2

    async def test_get_automation(self, client: AsyncClient, db_session: AsyncSession):
        """Test getting a specific automation."""
        automation = ReplyAutomation(
            name="Test Get",
            campaign_ids=["camp_test"],
            active=True
        )
        db_session.add(automation)
        await db_session.flush()
        await db_session.refresh(automation)
        
        response = await client.get(f"/api/replies/automations/{automation.id}")
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == automation.id
        assert data["name"] == "Test Get"

    async def test_get_automation_not_found(self, client: AsyncClient, db_session: AsyncSession):
        """Test getting non-existent automation returns 404."""
        response = await client.get("/api/replies/automations/99999")
        assert response.status_code == 404

    async def test_update_automation(self, client: AsyncClient, db_session: AsyncSession):
        """Test updating an automation."""
        automation = ReplyAutomation(
            name="Original Name",
            campaign_ids=["camp_1"],
            active=True
        )
        db_session.add(automation)
        await db_session.flush()
        await db_session.refresh(automation)
        
        response = await client.patch(
            f"/api/replies/automations/{automation.id}",
            json={"name": "Updated Name", "active": False}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "Updated Name"
        assert data["active"] is False
        # Campaign IDs should remain unchanged
        assert data["campaign_ids"] == ["camp_1"]

    async def test_delete_automation(self, client: AsyncClient, db_session: AsyncSession):
        """Test soft-deleting an automation."""
        automation = ReplyAutomation(
            name="To Delete",
            campaign_ids=["camp_del"],
            active=True
        )
        db_session.add(automation)
        await db_session.flush()
        await db_session.refresh(automation)
        
        response = await client.delete(f"/api/replies/automations/{automation.id}")
        assert response.status_code == 200
        
        # Should not appear in list anymore
        response = await client.get("/api/replies/automations")
        data = response.json()
        assert data["total"] == 0


class TestProcessedReplies:
    """Tests for /api/replies endpoints."""

    @pytest_asyncio.fixture
    async def test_automation(self, db_session: AsyncSession) -> ReplyAutomation:
        """Create a test automation for reply tests."""
        automation = ReplyAutomation(
            name="Test Automation",
            campaign_ids=["camp_test"],
            active=True
        )
        db_session.add(automation)
        await db_session.flush()
        await db_session.refresh(automation)
        return automation

    @pytest_asyncio.fixture
    async def test_replies(
        self, 
        db_session: AsyncSession, 
        test_automation: ReplyAutomation
    ) -> list[ProcessedReply]:
        """Create test processed replies."""
        replies = []
        categories = [
            ReplyCategory.INTERESTED,
            ReplyCategory.NOT_INTERESTED,
            ReplyCategory.MEETING_REQUEST,
            ReplyCategory.QUESTION,
            ReplyCategory.OUT_OF_OFFICE
        ]
        
        for i, cat in enumerate(categories):
            reply = ProcessedReply(
                automation_id=test_automation.id,
                campaign_id="camp_test",
                campaign_name="Test Campaign",
                lead_email=f"lead{i}@example.com",
                lead_first_name=f"Lead{i}",
                lead_last_name="Test",
                lead_company=f"Company{i}",
                email_subject=f"Re: Test {i}",
                email_body=f"This is reply {i}",
                category=cat.value,
                category_confidence="high",
                draft_reply=f"Draft reply for {i}",
                received_at=datetime.utcnow()
            )
            db_session.add(reply)
            replies.append(reply)
        
        await db_session.flush()
        for r in replies:
            await db_session.refresh(r)
        return replies

    async def test_list_replies_empty(self, client: AsyncClient, db_session: AsyncSession):
        """Test listing replies when none exist."""
        response = await client.get("/api/replies/")
        assert response.status_code == 200
        data = response.json()
        assert data["replies"] == []
        assert data["total"] == 0

    async def test_list_replies(
        self, 
        client: AsyncClient, 
        db_session: AsyncSession,
        test_automation: ReplyAutomation,
        test_replies: list[ProcessedReply]
    ):
        """Test listing all replies."""
        response = await client.get("/api/replies/")
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 5
        assert len(data["replies"]) == 5

    async def test_list_replies_filter_by_category(
        self, 
        client: AsyncClient, 
        db_session: AsyncSession,
        test_automation: ReplyAutomation,
        test_replies: list[ProcessedReply]
    ):
        """Test filtering replies by category."""
        response = await client.get("/api/replies/?category=interested")
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 1
        assert data["replies"][0]["category"] == "interested"

    async def test_list_replies_filter_by_automation(
        self, 
        client: AsyncClient, 
        db_session: AsyncSession,
        test_automation: ReplyAutomation,
        test_replies: list[ProcessedReply]
    ):
        """Test filtering replies by automation ID."""
        response = await client.get(f"/api/replies/?automation_id={test_automation.id}")
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 5

    async def test_list_replies_pagination(
        self, 
        client: AsyncClient, 
        db_session: AsyncSession,
        test_automation: ReplyAutomation,
        test_replies: list[ProcessedReply]
    ):
        """Test pagination of replies."""
        response = await client.get("/api/replies/?page=1&page_size=2")
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 5
        assert len(data["replies"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2

    async def test_get_reply(
        self, 
        client: AsyncClient, 
        db_session: AsyncSession,
        test_automation: ReplyAutomation,
        test_replies: list[ProcessedReply]
    ):
        """Test getting a specific reply."""
        reply = test_replies[0]
        
        response = await client.get(f"/api/replies/{reply.id}")
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == reply.id
        assert data["lead_email"] == reply.lead_email

    async def test_get_reply_not_found(self, client: AsyncClient, db_session: AsyncSession):
        """Test getting non-existent reply returns 404."""
        response = await client.get("/api/replies/99999")
        assert response.status_code == 404


class TestReplyStats:
    """Tests for reply statistics endpoint."""

    @pytest_asyncio.fixture
    async def test_automation(self, db_session: AsyncSession) -> ReplyAutomation:
        """Create a test automation."""
        automation = ReplyAutomation(
            name="Stats Test Automation",
            campaign_ids=["camp_stats"],
            active=True
        )
        db_session.add(automation)
        await db_session.flush()
        await db_session.refresh(automation)
        return automation

    async def test_stats_empty(self, client: AsyncClient, db_session: AsyncSession):
        """Test stats when no replies exist."""
        response = await client.get("/api/replies/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 0
        assert data["today"] == 0
        assert data["this_week"] == 0
        assert data["sent_to_slack"] == 0
        assert data["by_category"] == {}
        assert data["by_automation"] == {}

    async def test_stats_with_data(
        self, 
        client: AsyncClient, 
        db_session: AsyncSession,
        test_automation: ReplyAutomation
    ):
        """Test stats with some replies."""
        # Create replies with different categories
        categories = ["interested", "interested", "not_interested", "question"]
        for i, cat in enumerate(categories):
            reply = ProcessedReply(
                automation_id=test_automation.id,
                lead_email=f"stat{i}@example.com",
                category=cat,
                sent_to_slack=(i % 2 == 0),  # Every other one sent
                received_at=datetime.utcnow()
            )
            db_session.add(reply)
        await db_session.flush()
        
        # Filter by automation to avoid data from other tests
        response = await client.get(f"/api/replies/stats?automation_id={test_automation.id}")
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 4
        assert data["by_category"]["interested"] == 2
        assert data["by_category"]["not_interested"] == 1
        assert data["by_category"]["question"] == 1
        assert data["sent_to_slack"] == 2
        
        # Test by_automation - when filtered by automation_id, only that automation is shown
        assert str(test_automation.id) in data["by_automation"]
        assert data["by_automation"][str(test_automation.id)]["count"] == 4
        assert data["by_automation"][str(test_automation.id)]["name"] == test_automation.name


class TestSmartleadWebhook:
    """Tests for Smartlead webhook endpoint."""

    async def test_webhook_receive(self, client: AsyncClient, db_session: AsyncSession):
        """Test receiving a webhook payload."""
        payload = {
            "event_type": "reply_received",
            "campaign_id": "camp_123",
            "lead_email": "lead@example.com",
            "email_subject": "Re: Test Subject",
            "email_body": "I'm interested in learning more.",
            "first_name": "John",
            "last_name": "Doe",
            "company_name": "Acme Inc"
        }
        
        response = await client.post("/api/smartlead/webhook", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "received"

    async def test_webhook_minimal_payload(self, client: AsyncClient, db_session: AsyncSession):
        """Test webhook with minimal payload."""
        payload = {
            "lead_email": "minimal@example.com"
        }
        
        response = await client.post("/api/smartlead/webhook", json=payload)
        assert response.status_code == 200

    async def test_webhook_empty_payload(self, client: AsyncClient, db_session: AsyncSession):
        """Test webhook with empty payload still succeeds (but logs warning)."""
        payload = {}

        response = await client.post("/api/smartlead/webhook", json=payload)
        assert response.status_code == 200


class TestRegenerateDraft:
    """Tests for POST /api/replies/{reply_id}/regenerate-draft endpoint."""

    @pytest_asyncio.fixture
    async def test_automation(self, db_session: AsyncSession) -> ReplyAutomation:
        automation = ReplyAutomation(
            name="Regen Test Automation",
            campaign_ids=["camp_regen"],
            active=True,
        )
        db_session.add(automation)
        await db_session.flush()
        await db_session.refresh(automation)
        return automation

    @pytest_asyncio.fixture
    async def failed_reply(
        self, db_session: AsyncSession, test_automation: ReplyAutomation
    ) -> ProcessedReply:
        reply = ProcessedReply(
            automation_id=test_automation.id,
            campaign_id="camp_regen",
            campaign_name="Test Campaign Regen",
            lead_email="regen@example.com",
            lead_first_name="Alice",
            lead_last_name="Regen",
            lead_company="RegenCorp",
            email_subject="Re: Partnership",
            email_body="I'm interested, let's talk.",
            category="interested",
            category_confidence="high",
            classification_reasoning="Lead expressed interest.",
            draft_reply="{Draft generation failed: OpenAI error}",
            draft_subject="Re: Partnership",
            received_at=datetime.utcnow(),
        )
        db_session.add(reply)
        await db_session.flush()
        await db_session.refresh(reply)
        return reply

    @patch("app.services.reply_processor.generate_draft_reply", new_callable=AsyncMock)
    @patch("app.services.reply_processor.classify_reply", new_callable=AsyncMock)
    async def test_happy_path(
        self,
        mock_classify,
        mock_generate,
        client: AsyncClient,
        db_session: AsyncSession,
        failed_reply: ProcessedReply,
    ):
        """Regenerate draft succeeds, updates draft_reply and draft_subject."""
        mock_generate.return_value = {"body": "New draft body", "subject": "Re: Partnership"}

        response = await client.post(f"/api/replies/{failed_reply.id}/regenerate-draft")
        assert response.status_code == 200
        data = response.json()

        assert data["draft_reply"] == "New draft body"
        assert data["draft_subject"] == "Re: Partnership"
        assert data["reply_id"] == failed_reply.id
        mock_classify.assert_not_called()  # classification was fine

    @patch("app.services.reply_processor.generate_draft_reply", new_callable=AsyncMock)
    @patch("app.services.reply_processor.classify_reply", new_callable=AsyncMock)
    async def test_reclassifies_when_failed(
        self,
        mock_classify,
        mock_generate,
        client: AsyncClient,
        db_session: AsyncSession,
        test_automation: ReplyAutomation,
    ):
        """When classification_reasoning contains failure marker, re-classifies first."""
        reply = ProcessedReply(
            automation_id=test_automation.id,
            campaign_id="camp_regen",
            lead_email="reclass@example.com",
            email_subject="Re: Hello",
            email_body="What services do you offer?",
            category="other",
            classification_reasoning="Classification failed after 3 attempts",
            draft_reply="{Draft generation failed}",
            received_at=datetime.utcnow(),
        )
        db_session.add(reply)
        await db_session.flush()
        await db_session.refresh(reply)

        mock_classify.return_value = {
            "category": "question",
            "reasoning": "Lead is asking about services.",
            "confidence": "high",
        }
        mock_generate.return_value = {"body": "We offer X, Y, Z.", "subject": "Re: Hello"}

        response = await client.post(f"/api/replies/{reply.id}/regenerate-draft")
        assert response.status_code == 200
        data = response.json()

        mock_classify.assert_called_once()
        assert data["category"] == "question"
        assert data["classification_reasoning"] == "Lead is asking about services."
        assert data["draft_reply"] == "We offer X, Y, Z."

    @patch("app.services.reply_processor.generate_draft_reply", new_callable=AsyncMock)
    @patch("app.services.reply_processor.classify_reply", new_callable=AsyncMock)
    async def test_skips_reclassification_when_ok(
        self,
        mock_classify,
        mock_generate,
        client: AsyncClient,
        db_session: AsyncSession,
        failed_reply: ProcessedReply,
    ):
        """When classification is fine, does NOT re-classify."""
        mock_generate.return_value = {"body": "Fresh draft", "subject": "Re: Partnership"}

        response = await client.post(f"/api/replies/{failed_reply.id}/regenerate-draft")
        assert response.status_code == 200

        mock_classify.assert_not_called()
        mock_generate.assert_called_once()

    async def test_404(self, client: AsyncClient, db_session: AsyncSession):
        """Returns 404 for non-existent reply."""
        response = await client.post("/api/replies/99999/regenerate-draft")
        assert response.status_code == 404

    @patch("app.services.reply_processor.generate_draft_reply", new_callable=AsyncMock)
    async def test_openai_failure(
        self,
        mock_generate,
        client: AsyncClient,
        db_session: AsyncSession,
        failed_reply: ProcessedReply,
    ):
        """Returns 500 when generate_draft_reply raises."""
        mock_generate.side_effect = Exception("OpenAI timeout")

        response = await client.post(f"/api/replies/{failed_reply.id}/regenerate-draft")
        assert response.status_code == 500
        assert "Draft generation failed" in response.json()["detail"]

    @patch("app.services.reply_processor.generate_draft_reply", new_callable=AsyncMock)
    @patch("app.services.reply_processor.classify_reply", new_callable=AsyncMock)
    async def test_project_sender_lookup(
        self,
        mock_classify,
        mock_generate,
        client: AsyncClient,
        db_session: AsyncSession,
        test_automation: ReplyAutomation,
    ):
        """Verifies generate_draft_reply receives sender/prompt kwargs.

        Note: The actual JSONB project lookup can't be tested with SQLite.
        We mock the DB layer to simulate a successful project match.
        """
        from unittest.mock import MagicMock

        # Create reply
        reply = ProcessedReply(
            automation_id=test_automation.id,
            campaign_id="camp_regen",
            campaign_name="My Campaign",
            lead_email="project_lookup@example.com",
            lead_first_name="Bob",
            lead_last_name="Tester",
            lead_company="TestCo",
            email_subject="Re: Intro",
            email_body="Tell me more.",
            category="interested",
            classification_reasoning="Lead is interested.",
            draft_reply="{Draft generation failed}",
            received_at=datetime.utcnow(),
        )
        db_session.add(reply)
        await db_session.flush()
        await db_session.refresh(reply)

        mock_generate.return_value = {"body": "Hi Bob, ...", "subject": "Re: Intro"}

        # Mock the project lookup query to return a fake project with sender info
        mock_project = MagicMock()
        mock_project.sender_name = "Pablo Medvedev"
        mock_project.sender_position = "BD Manager"
        mock_project.sender_company = "Rizzult"
        mock_project.reply_prompt_template_id = None  # skip template lookup

        original_execute = db_session.execute

        call_count = 0
        async def patched_execute(stmt, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            # The 2nd execute is the project lookup (1st is the reply fetch)
            if call_count == 2:
                mock_result = MagicMock()
                mock_result.scalar.return_value = mock_project
                return mock_result
            return await original_execute(stmt, *args, **kwargs)

        with patch.object(db_session, 'execute', side_effect=patched_execute):
            response = await client.post(f"/api/replies/{reply.id}/regenerate-draft")

        assert response.status_code == 200

        # Verify generate_draft_reply was called with project sender info
        _, kwargs = mock_generate.call_args
        assert kwargs["sender_name"] == "Pablo Medvedev"
        assert kwargs["sender_position"] == "BD Manager"
        assert kwargs["sender_company"] == "Rizzult"
