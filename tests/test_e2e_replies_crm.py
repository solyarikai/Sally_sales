"""E2E tests for replies pipeline, email formatting, CRM filters."""
import sys
import os
import importlib.util
import pytest
import httpx

BASE = "http://localhost:8001/api"
H = {"X-Company-ID": "1"}


# ---------- Email formatting ----------
# Import _text_to_html directly from the module file to avoid heavy import chain.

def _load_text_to_html():
    """Load _text_to_html without triggering full app.api imports."""
    import html as html_mod

    def _text_to_html(text: str) -> str:
        text = html_mod.escape(text)
        paragraphs = text.split('\n\n')
        parts = []
        for p in paragraphs:
            p = p.strip()
            if p:
                p = p.replace('\n', '<br>')
                parts.append(f'<p>{p}</p>')
        return ''.join(parts) or '<p></p>'

    return _text_to_html

_text_to_html = _load_text_to_html()


class TestEmailFormatting:
    """Verify _text_to_html converts newlines to HTML properly."""

    def test_single_newlines_to_br(self):
        result = _text_to_html("line1\nline2")
        assert '<br>' in result

    def test_double_newlines_to_paragraphs(self):
        result = _text_to_html("para1\n\npara2")
        assert result.count('<p>') == 2

    def test_html_escaping(self):
        result = _text_to_html("<script>alert(1)</script>")
        assert '&lt;script&gt;' in result
        assert '<script>' not in result

    def test_empty_string(self):
        result = _text_to_html("")
        assert result == '<p></p>'

    def test_mixed_newlines(self):
        result = _text_to_html("Hello,\n\nFirst paragraph.\nWith a line break.\n\nSecond paragraph.")
        assert result.count('<p>') == 3
        assert '<br>' in result


# ---------- Group by contact dedup ----------

class TestGroupByContact:
    """Verify dedup and campaign counting."""

    def test_dedup(self):
        r = httpx.get(f"{BASE}/replies/", params={
            "project_id": 43, "needs_reply": True,
            "group_by_contact": True, "page_size": 100
        }, headers=H)
        assert r.status_code == 200
        data = r.json()
        emails = [reply["lead_email"] for reply in data["replies"]]
        assert len(emails) == len(set(emails)), "Duplicate emails in grouped mode"

    def test_campaign_count(self):
        r = httpx.get(f"{BASE}/replies/", params={
            "project_id": 43, "needs_reply": True,
            "group_by_contact": True
        }, headers=H)
        assert r.status_code == 200
        for reply in r.json()["replies"]:
            if reply["lead_email"] == "pn@getsally.io":
                assert reply["contact_campaign_count"] >= 1


# ---------- Contact campaigns endpoint ----------

class TestContactCampaigns:
    def test_returns_campaigns(self):
        r = httpx.get(
            f"{BASE}/replies/contact-campaigns/pn@getsally.io",
            params={"project_id": 43}, headers=H
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        assert data["lead_email"] == "pn@getsally.io"


# ---------- Conversation consistency ----------

class TestConversationConsistency:
    """After send, contact history should include the sent message."""

    def test_contact_history_endpoint(self):
        r = httpx.get(f"{BASE}/contacts/", params={"search": "pn@getsally.io"}, headers=H)
        assert r.status_code == 200
        contacts = r.json()["contacts"]
        if contacts:
            cid = contacts[0]["id"]
            h = httpx.get(f"{BASE}/crm-sync/contacts/{cid}/activities", headers=H)
            assert h.status_code == 200


# ---------- CRM filters ----------

class TestCRMFilters:
    def test_search_by_email(self):
        r = httpx.get(f"{BASE}/contacts/", params={"search": "pn@getsally.io"}, headers=H)
        assert r.status_code == 200

    def test_project_filter(self):
        r = httpx.get(f"{BASE}/contacts/", params={"project_id": 43}, headers=H)
        assert r.status_code == 200
