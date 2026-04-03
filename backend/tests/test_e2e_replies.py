"""
End-to-end tests for Reply Automation feature.

Tests the full wizard flow:
1. Campaigns load from Smartlead API (READ-ONLY)
2. Google Sheet creation works
3. Slack channel list works
4. Automation saves to database
5. Webhook receives reply and processes

These tests mock external APIs (Smartlead, Google Sheets, Slack) to verify
the integration logic works correctly without making real API calls.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from app.models.reply import ReplyAutomation, ProcessedReply


# ============= Mock Data =============

MOCK_CAMPAIGNS = [
    {
        "id": "camp_001",
        "name": "Sales Outreach Q1",
        "status": "active",
        "created_at": "2026-01-01T00:00:00Z"
    },
    {
        "id": "camp_002", 
        "name": "Product Launch",
        "status": "active",
        "created_at": "2026-01-15T00:00:00Z"
    },
    {
        "id": "camp_003",
        "name": "Follow-up Campaign",
        "status": "paused",
        "created_at": "2026-01-20T00:00:00Z"
    }
]

MOCK_SLACK_CHANNELS = [
    {
        "id": "C09ABC123",
        "name": "sales-team",
        "is_private": False,
        "is_member": True,
        "num_members": 12
    },
    {
        "id": "C09DEF456",
        "name": "replies-notifications",
        "is_private": False,
        "is_member": True,
        "num_members": 5
    },
    {
        "id": "C09GHI789",
        "name": "general",
        "is_private": False,
        "is_member": True,
        "num_members": 50
    }
]

MOCK_GOOGLE_SHEET = {
    "sheet_id": "1ABC123xyz",
    "sheet_url": "https://docs.google.com/spreadsheets/d/1ABC123xyz/edit"
}


# ============= Test: Campaigns Load (Smartlead READ-ONLY) =============

class TestCampaignsLoad:
    """Test that campaigns load correctly from Smartlead API (READ-ONLY)."""

    async def test_campaigns_load_successfully(
        self, 
        client: AsyncClient
    ):
        """Test: Smartlead campaigns load via GET /api/smartlead/campaigns."""
        with patch('app.services.smartlead_service.smartlead_service') as mock_service:
            mock_service.is_connected.return_value = True
            mock_service.get_campaigns = AsyncMock(return_value=MOCK_CAMPAIGNS)
            
            response = await client.get("/api/smartlead/campaigns")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "campaigns" in data
            assert data["total"] == 3
            assert len(data["campaigns"]) == 3
            
            # Verify campaign data
            campaign_names = [c["name"] for c in data["campaigns"]]
            assert "Sales Outreach Q1" in campaign_names
            assert "Product Launch" in campaign_names
            
    async def test_campaigns_returns_400_when_api_key_missing(
        self,
        client: AsyncClient
    ):
        """Test: Returns error when Smartlead API key not configured."""
        with patch('app.services.smartlead_service.smartlead_service') as mock_service:
            mock_service.is_connected.return_value = False
            
            response = await client.get("/api/smartlead/campaigns")
            
            assert response.status_code == 400
            data = response.json()
            assert "API key not configured" in data["detail"]

    async def test_campaigns_read_only_no_write_operations(
        self,
        client: AsyncClient
    ):
        """SAFETY: Verify we only READ from Smartlead, never WRITE."""
        with patch('app.services.smartlead_service.smartlead_service') as mock_service:
            mock_service.is_connected.return_value = True
            mock_service.get_campaigns = AsyncMock(return_value=MOCK_CAMPAIGNS)
            
            # GET should work
            response = await client.get("/api/smartlead/campaigns")
            assert response.status_code == 200
            
            # Verify only get_campaigns was called (read operation)
            mock_service.get_campaigns.assert_called_once()
            
            # Verify no write methods were called
            assert not hasattr(mock_service, 'add_leads_to_campaign') or \
                   not mock_service.add_leads_to_campaign.called


# ============= Test: Google Sheet Creation =============

class TestGoogleSheetCreation:
    """Test Google Sheet creation for reply logging."""

    async def test_google_sheets_status_check(
        self,
        client: AsyncClient
    ):
        """Test: Check Google Sheets configuration status."""
        with patch('app.services.google_sheets_service.google_sheets_service') as mock_service:
            mock_service.is_configured.return_value = True
            mock_service.get_service_account_email.return_value = "test@project.iam.gserviceaccount.com"
            
            response = await client.get("/api/replies/google-sheets/status")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["configured"] is True
            assert "service_account_email" in data

    async def test_google_sheet_creation(
        self,
        client: AsyncClient,
        db_session: AsyncSession
    ):
        """Test: Create new Google Sheet for reply logging."""
        with patch('app.services.google_sheets_service.google_sheets_service') as mock_service:
            mock_service.is_configured.return_value = True
            mock_service.create_reply_sheet.return_value = MOCK_GOOGLE_SHEET
            
            response = await client.post(
                "/api/replies/google-sheets/create",
                params={
                    "name": "Test Automation Sheet",
                    "share_with_email": "user@example.com"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert data["sheet_id"] == "1ABC123xyz"
            assert "sheet_url" in data
            
            # Verify create was called with correct params
            mock_service.create_reply_sheet.assert_called_once_with(
                "Test Automation Sheet",
                "user@example.com"
            )

    async def test_google_sheets_not_configured(
        self,
        client: AsyncClient
    ):
        """Test: Returns 503 when Google Sheets not configured."""
        with patch('app.services.google_sheets_service.google_sheets_service') as mock_service:
            mock_service.is_configured.return_value = False
            
            response = await client.post(
                "/api/replies/google-sheets/create",
                params={"name": "Test Sheet"}
            )
            
            assert response.status_code == 503
            data = response.json()
            assert "not configured" in data["detail"].lower()


# ============= Test: Slack Channel List =============

class TestSlackChannelList:
    """Test Slack channel listing for notification configuration."""

    async def test_slack_status_check(
        self,
        client: AsyncClient
    ):
        """Test: Check Slack Bot Token status."""
        with patch('app.services.notification_service.SLACK_BOT_TOKEN', 'xoxb-test-token'):
            with patch('app.services.notification_service.httpx.AsyncClient') as mock_client:
                # Mock auth.test response
                mock_response = MagicMock()
                mock_response.json.return_value = {"ok": True, "user_id": "U123", "team": "TestTeam"}
                
                # Mock conversations.list response
                mock_channels_response = MagicMock()
                mock_channels_response.json.return_value = {"ok": True, "channels": []}
                
                mock_client_instance = AsyncMock()
                mock_client_instance.get = AsyncMock(side_effect=[mock_response, mock_channels_response])
                mock_client.return_value.__aenter__.return_value = mock_client_instance
                
                response = await client.get("/api/replies/slack/status")
                
                assert response.status_code == 200
                data = response.json()
                
                assert data["configured"] is True
                assert data["bot_token"] is True

    async def test_slack_channels_list(
        self,
        client: AsyncClient
    ):
        """Test: List available Slack channels."""
        with patch('app.services.notification_service.SLACK_BOT_TOKEN', 'xoxb-test-token'):
            with patch('app.services.notification_service.list_slack_channels') as mock_list:
                mock_list.return_value = {
                    "success": True,
                    "channels": MOCK_SLACK_CHANNELS,
                    "total": len(MOCK_SLACK_CHANNELS),
                    "error": None,
                    "action_required": None
                }
                
                response = await client.get("/api/replies/slack/channels")
                
                assert response.status_code == 200
                data = response.json()
                
                assert data["success"] is True
                assert len(data["channels"]) == 3
                
                # Verify channel data
                channel_names = [c["name"] for c in data["channels"]]
                assert "sales-team" in channel_names
                assert "replies-notifications" in channel_names

    async def test_slack_channel_creation(
        self,
        client: AsyncClient
    ):
        """Test: Create new Slack channel."""
        with patch('app.services.notification_service.create_slack_channel') as mock_create:
            mock_create.return_value = {
                "success": True,
                "channel": {
                    "id": "C09NEW123",
                    "name": "new-replies-channel",
                    "is_private": False
                },
                "error": None
            }
            
            response = await client.post(
                "/api/replies/slack/channels/create",
                params={"name": "new-replies-channel", "is_private": False}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert data["channel"]["id"] == "C09NEW123"
            assert data["channel"]["name"] == "new-replies-channel"

    async def test_slack_test_message(
        self,
        client: AsyncClient
    ):
        """Test: Send test message to Slack channel."""
        with patch('app.services.notification_service.send_test_notification') as mock_send:
            mock_send.return_value = {
                "success": True,
                "message": "Test notification sent successfully via Bot Token"
            }
            
            response = await client.post("/api/replies/slack/test-channel/C09ABC123")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            mock_send.assert_called_once_with(channel_id="C09ABC123")


# ============= Test: Automation Saves to Database =============

class TestAutomationSaves:
    """Test that automation configuration saves correctly to database."""

    async def test_create_automation_full(
        self,
        client: AsyncClient,
        db_session: AsyncSession
    ):
        """Test: Create automation with all fields."""
        with patch('app.services.google_sheets_service.google_sheets_service') as mock_sheets:
            mock_sheets.is_configured.return_value = True
            mock_sheets.create_reply_sheet.return_value = MOCK_GOOGLE_SHEET
            
            payload = {
                "name": "Full Test Automation",
                "campaign_ids": ["camp_001", "camp_002"],
                "slack_channel": "C09ABC123",
                "create_google_sheet": True,
                "share_sheet_with_email": "team@example.com",
                "auto_classify": True,
                "auto_generate_reply": True,
                "active": True
            }
            
            response = await client.post("/api/replies/automations", json=payload)
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify saved fields
            assert data["name"] == "Full Test Automation"
            assert data["campaign_ids"] == ["camp_001", "camp_002"]
            assert data["slack_channel"] == "C09ABC123"
            assert data["auto_classify"] is True
            assert data["auto_generate_reply"] is True
            assert data["active"] is True
            assert "id" in data
            
            # Verify Google Sheet was created
            assert data["google_sheet_id"] == "1ABC123xyz"

    async def test_create_automation_minimal(
        self,
        client: AsyncClient,
        db_session: AsyncSession
    ):
        """Test: Create automation with minimal required fields."""
        payload = {
            "name": "Minimal Automation",
            "campaign_ids": ["camp_003"]
        }
        
        response = await client.post("/api/replies/automations", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "Minimal Automation"
        assert data["campaign_ids"] == ["camp_003"]
        # Check defaults
        assert data["auto_classify"] is True
        assert data["auto_generate_reply"] is True
        assert data["active"] is False  # Default to inactive when not specified

    async def test_list_automations(
        self,
        client: AsyncClient,
        db_session: AsyncSession
    ):
        """Test: List all automations."""
        # Create test automations
        for i in range(3):
            automation = ReplyAutomation(
                name=f"List Test {i}",
                campaign_ids=[f"camp_{i}"],
                active=True
            )
            db_session.add(automation)
        await db_session.flush()
        
        response = await client.get("/api/replies/automations")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] >= 3
        assert len(data["automations"]) >= 3

    async def test_update_automation(
        self,
        client: AsyncClient,
        db_session: AsyncSession
    ):
        """Test: Update an existing automation."""
        automation = ReplyAutomation(
            name="Update Test",
            campaign_ids=["camp_old"],
            slack_channel="C09OLD",
            active=True
        )
        db_session.add(automation)
        await db_session.flush()
        await db_session.refresh(automation)
        
        response = await client.patch(
            f"/api/replies/automations/{automation.id}",
            json={
                "name": "Updated Name",
                "slack_channel": "C09NEW",
                "active": False
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "Updated Name"
        assert data["slack_channel"] == "C09NEW"
        assert data["active"] is False
        # Unchanged fields preserved
        assert data["campaign_ids"] == ["camp_old"]

    async def test_delete_automation(
        self,
        client: AsyncClient,
        db_session: AsyncSession
    ):
        """Test: Soft delete an automation."""
        automation = ReplyAutomation(
            name="Delete Test",
            campaign_ids=["camp_del"],
            active=True
        )
        db_session.add(automation)
        await db_session.flush()
        await db_session.refresh(automation)
        
        response = await client.delete(f"/api/replies/automations/{automation.id}")
        
        assert response.status_code == 200
        
        # Should not appear in active list
        list_response = await client.get("/api/replies/automations")
        automation_ids = [a["id"] for a in list_response.json()["automations"]]
        assert automation.id not in automation_ids


# ============= Test: Webhook Receives and Processes Reply =============

class TestWebhookProcessing:
    """Test webhook endpoint receives and processes replies correctly."""

    async def test_webhook_receives_reply(
        self,
        client: AsyncClient,
        db_session: AsyncSession
    ):
        """Test: Webhook endpoint receives Smartlead reply."""
        payload = {
            "event_type": "reply_received",
            "campaign_id": "camp_001",
            "lead_email": "lead@example.com",
            "email_subject": "Re: Sales Offer",
            "email_body": "I'm interested in your services.",
            "first_name": "John",
            "last_name": "Doe",
            "company_name": "Acme Inc"
        }
        
        response = await client.post("/api/smartlead/webhook", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "received"

    async def test_simulate_reply_classification(
        self,
        client: AsyncClient,
        db_session: AsyncSession
    ):
        """Test: Simulate reply with AI classification."""
        with patch('app.services.reply_processor.classify_reply') as mock_classify:
            with patch('app.services.reply_processor.generate_draft_reply') as mock_draft:
                mock_classify.return_value = {
                    "category": "interested",
                    "confidence": "high",
                    "reasoning": "Lead explicitly expresses interest"
                }
                mock_draft.return_value = {
                    "subject": "Re: Your Interest",
                    "body": "Thank you for your interest! I'd love to schedule a call."
                }
                
                payload = {
                    "lead_email": "test@example.com",
                    "first_name": "Jane",
                    "last_name": "Smith",
                    "company_name": "Tech Corp",
                    "email_subject": "Re: Our Offer",
                    "email_body": "I'm very interested in learning more about your product."
                }
                
                response = await client.post("/api/smartlead/simulate-reply", json=payload)
                
                assert response.status_code == 200
                data = response.json()
                
                # Note: Actual success depends on reply_processor implementation
                # This test verifies the endpoint works

    async def test_processed_reply_saved_to_db(
        self,
        client: AsyncClient,
        db_session: AsyncSession
    ):
        """Test: Processed reply is saved to database."""
        # Create test automation
        automation = ReplyAutomation(
            name="Process Test",
            campaign_ids=["camp_process"],
            active=True
        )
        db_session.add(automation)
        await db_session.flush()
        
        # Create processed reply directly
        reply = ProcessedReply(
            automation_id=automation.id,
            campaign_id="camp_process",
            campaign_name="Process Test Campaign",
            lead_email="saved@example.com",
            lead_first_name="Saved",
            lead_last_name="Lead",
            lead_company="Save Corp",
            email_subject="Re: Test",
            email_body="This is a test reply to save",
            category="interested",
            category_confidence="high",
            classification_reasoning="Test reasoning",
            draft_reply="Test draft response",
            received_at=datetime.utcnow(),
            processed_at=datetime.utcnow()
        )
        db_session.add(reply)
        await db_session.flush()
        await db_session.refresh(reply)
        
        # Verify via API
        response = await client.get(f"/api/replies/{reply.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["lead_email"] == "saved@example.com"
        assert data["category"] == "interested"
        assert data["draft_reply"] == "Test draft response"

    async def test_reply_stats_accurate(
        self,
        client: AsyncClient,
        db_session: AsyncSession
    ):
        """Test: Reply statistics are accurate."""
        # Create automation and replies
        automation = ReplyAutomation(
            name="Stats Test",
            campaign_ids=["camp_stats"],
            active=True
        )
        db_session.add(automation)
        await db_session.flush()
        
        # Add replies with different categories
        categories = ["interested", "interested", "not_interested", "meeting_request"]
        for i, cat in enumerate(categories):
            reply = ProcessedReply(
                automation_id=automation.id,
                campaign_id="camp_stats",
                lead_email=f"stats{i}@example.com",
                category=cat,
                sent_to_slack=(i % 2 == 0),
                received_at=datetime.utcnow(),
                processed_at=datetime.utcnow()
            )
            db_session.add(reply)
        await db_session.flush()
        
        response = await client.get(
            "/api/replies/stats",
            params={"automation_id": automation.id}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 4
        assert data["by_category"]["interested"] == 2
        assert data["by_category"]["not_interested"] == 1
        assert data["by_category"]["meeting_request"] == 1
        assert data["sent_to_slack"] == 2


# ============= Test: Full Wizard Flow (Integration) =============

class TestFullWizardFlow:
    """Integration test for the full 4-step wizard flow."""

    async def test_complete_wizard_flow(
        self,
        client: AsyncClient,
        db_session: AsyncSession
    ):
        """Test: Complete wizard flow from campaigns to activation."""
        
        # Step 1: Load campaigns
        with patch('app.services.smartlead_service.smartlead_service') as mock_smartlead:
            mock_smartlead.is_connected.return_value = True
            mock_smartlead.get_campaigns = AsyncMock(return_value=MOCK_CAMPAIGNS)
            
            campaigns_response = await client.get("/api/smartlead/campaigns")
            assert campaigns_response.status_code == 200
            assert campaigns_response.json()["total"] == 3
        
        # Step 2: Check Google Sheets (skip creation for speed)
        with patch('app.services.google_sheets_service.google_sheets_service') as mock_sheets:
            mock_sheets.is_configured.return_value = True
            mock_sheets.get_service_account_email.return_value = "test@project.iam.gserviceaccount.com"
            
            sheets_response = await client.get("/api/replies/google-sheets/status")
            assert sheets_response.status_code == 200
            assert sheets_response.json()["configured"] is True
        
        # Step 3: Check Slack and list channels
        with patch('app.services.notification_service.list_slack_channels') as mock_channels:
            mock_channels.return_value = {
                "success": True,
                "channels": MOCK_SLACK_CHANNELS,
                "total": 3,
                "error": None,
                "action_required": None
            }
            
            channels_response = await client.get("/api/replies/slack/channels")
            assert channels_response.status_code == 200
            assert channels_response.json()["success"] is True
        
        # Step 4: Create automation
        automation_payload = {
            "name": "Wizard Test Automation",
            "campaign_ids": ["camp_001", "camp_002"],
            "slack_channel": "C09ABC123",
            "auto_classify": True,
            "auto_generate_reply": True,
            "active": True
        }
        
        create_response = await client.post(
            "/api/replies/automations",
            json=automation_payload
        )
        
        assert create_response.status_code == 200
        automation_data = create_response.json()
        
        assert automation_data["name"] == "Wizard Test Automation"
        assert automation_data["campaign_ids"] == ["camp_001", "camp_002"]
        assert automation_data["slack_channel"] == "C09ABC123"
        assert automation_data["active"] is True
        
        # Verify automation is listed
        list_response = await client.get("/api/replies/automations")
        automations = list_response.json()["automations"]
        automation_names = [a["name"] for a in automations]
        assert "Wizard Test Automation" in automation_names
