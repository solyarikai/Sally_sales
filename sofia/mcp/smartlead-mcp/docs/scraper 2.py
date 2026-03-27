#!/usr/bin/env python3
"""
Smartlead API Documentation Scraper
Scrapes all pages from https://smartlead.readme.io/reference/
and saves each as a separate markdown file organized by section.
"""

import os
import re
import time
import json
import urllib.request
import urllib.error
from html.parser import HTMLParser

BASE_URL = "https://smartlead.readme.io/reference"
DOCS_DIR = os.path.dirname(os.path.abspath(__file__))

# All pages grouped by section (folder name -> list of (slug, title))
SECTIONS = {
    "01-getting-started": [
        ("welcome", "Welcome"),
        ("authentication", "Authentication"),
        ("references", "References"),
        ("rate-limits", "Rate Limits"),
    ],
    "02-campaign-management": [
        ("create-campaign", "Create Campaign"),
        ("update-campaign-schedule", "Update Campaign Schedule"),
        ("update-campaign-general-settings", "Update Campaign General Settings"),
        ("get-campaign-by-id", "Get Campaign By Id"),
        ("save-campaign-sequence", "Save Campaign Sequence"),
        ("list-all-campaigns", "List all Campaigns"),
        ("patch-campaign-status", "Patch campaign status"),
        ("fetch-campaign-sequence-by-campaign-id", "Fetch Campaign Sequence By Campaign ID"),
        ("fetch-all-campaigns-using-lead-id", "Fetch all Campaigns Using Lead ID"),
        ("export-data-from-a-campaign", "Export data from a campaign"),
        ("delete-campaign", "Delete Campaign"),
        ("fetch-campaign-analytics-by-date-range", "[DEPRECATED] Fetch Campaign Analytics by Date range"),
        ("get-campaign-sequence-analytics", "Get Campaign Sequence Analytics"),
        ("create-subsequence", "Create Subsequence"),
    ],
    "03-lead-management": [
        ("fetch-lead-categori-1", "Move Leads to Inactive from All Leads Page"),
        ("fetch-lead-categori-1-2", "Move leads to Inactive from Campaign lead list page"),
        ("push-leadslist-to-campaign", "Push Leads/List to Campaign"),
        ("get-leads-campaign-overview", "Get leads- Campaign Overview"),
        ("get-lead-sequence-details", "Get Lead Sequence Details"),
        ("list-all-leads-by-campaign-id", "List all leads by Campaign ID"),
        ("fetch-lead-categori", "Fetch Lead Categories"),
        ("fetch-lead-by-email-address", "Fetch Lead by email address"),
        ("add-leads-to-a-campaign-by-id", "Add leads to a campaign by ID"),
        ("resume-lead-by-campaign-id", "Resume Lead By Campaign ID"),
        ("pause-lead-by-campaign-id", "Pause Lead By Campaign ID"),
        ("delete-lead-by-campaign-id", "Delete Lead By Campaign ID"),
        ("unsubscribepause-lead-from-campaign", "Unsubscribe/Pause Lead From Campaign"),
        ("unsubscribe-lead-from-all-campaigns", "Unsubscribe Lead From All Campaigns"),
        ("global-leads", "Fetch All Leads From Entire Account"),
        ("fetch-leads-from-global-block-list", "Fetch Leads From Global Block List"),
        ("add-leaddomain-to-global-block-list", "Add Lead/Domain to Global Block List"),
        ("delete-leaddomain-from-global-block-list", "Delete Lead/Domain to Global Block List"),
        ("update-lead-using-the-lead-id", "Update lead using the Lead ID"),
        ("update-a-leads-category-based-on-their-campaign", "Update a lead's category based on their campaign"),
        ("fetch-lead-message-history-based-on-campaign", "Fetch Lead Message History Based on Campaign"),
    ],
    "04-email-accounts": [
        ("create-an-email-account", "Create an Email Account"),
        ("remove-email-account-from-a-campaign", "Remove Email Account from a Campaign"),
        ("fetch-all-email-accounts-associated-to-a-user", "Fetch all email accounts associated to a user"),
        ("list-all-email-accounts-per-campaign", "List all email accounts per campaign"),
        ("fetch-email-account-by-id", "Fetch Email Account By ID"),
        ("add-email-account-to-a-campaign", "Add Email Account to a Campaign"),
        ("addupdate-warmup-to-email-account", "Add/Update Warmup To Email Account"),
        ("reconnect-failed-email-accounts-1", "Reconnect failed email accounts"),
        ("fetch-warmup-stats-by-email-account-id", "Fetch Warmup Stats By Email Account ID"),
        ("update-email-account-tag", "Update Email Account Tag"),
        ("update-email-account", "Update Email Account"),
        ("post_email-accounts-account-id-fetch-messages", "Fetch Messages for Email Account"),
        ("post_email-accounts-multi-fetch-messages", "Bulk Fetch Messages for Multiple Email Accounts"),
        ("email-accounts", "Email Accounts"),
        ("post_v1-email-accounts-tag-mapping", "Add Tags to Email Accounts"),
        ("delete_v1-email-accounts-tag-mapping", "Remove Tags from Email Accounts"),
        ("getemailaccounttaglist", "Get Tag List by Email Addresses"),
    ],
    "05-campaign-statistics": [
        ("fetch-campaign-statistics-by-campaign-id", "Fetch Campaign Statistics By Campaign ID"),
        ("fetch-campaign-statistics-by-campaign-id-and-date-range", "Fetch Campaign Statistics By Campaign Id And Date Range"),
        ("fetch-campaign-top-level-analytics", "Fetch campaign top level analytics"),
        ("fetch-campaign-top-level-analytics-by-date-range", "Fetch Campaign Top Level Analytics By Date Range"),
        ("lead-statistics", "Fetch Campaign Lead Statistics"),
        ("fetch-campaign-mailbox-statistics", "Fetch Campaign Mailbox Statistics"),
    ],
    "06-smart-delivery": [
        ("region-wise-provider-ids", "Region wise Provider IDs"),
        ("create-a-manual-placement", "Create a Manual Placement Test"),
        ("create-an-automated-placement-test", "Create an Automated Placement Test"),
        ("spam-test-details", "Spam Test Details"),
        ("delete-smart-delivery-test-in-bulk", "Delete Smart Delivery Tests in Bulk"),
        ("stop-an-automated-test", "Stop an Automated Smart Delivery Test"),
        ("list-tests", "List all Tests"),
        ("provider-wise-results", "Provider wise report"),
        ("geo-wise-report", "Geo wise report"),
        ("sender-account-wise-report", "Sender Account wise report"),
        ("spam-filter-report", "Spam filter report"),
        ("dkim-details-copy", "DKIM Details"),
        ("spf-details", "SPF Details"),
        ("rdns-report", "rDNS report"),
        ("sender-account-list", "Sender Account List"),
        ("spam-test-seed-account-list-copy", "Blacklists"),
        ("domain-blacklist", "Domain Blacklist"),
        ("test-email-content", "Spam Test Email Content"),
        ("ip-blacklist-count", "Spam test IP Blacklist Count"),
        ("email-headers-per-email", "Email reply headers"),
        ("schedule-history-for-automated-tests", "Schedule history for Automated Tests"),
        ("ip-details", "IP details"),
        ("mail-box-summary", "Mailbox Summary"),
        ("mailbox-count", "Mailbox Count API"),
        ("get-all-folders", "Get All Folders"),
        ("create-folder", "Create Folders"),
        ("get-folder-by-id", "Get folder by ID"),
        ("delete-folder", "Delete folder"),
    ],
    "07-webhooks": [
        ("fetch-webhooks-by-campaign-id", "Fetch Webhooks By Campaign ID"),
        ("email-reply-webhooks", "Capturing Email Replies"),
        ("add-update-campaign-webhook", "Add / Update Campaign Webhook"),
        ("delete-campaign-webhook", "Delete Campaign Webhook"),
        ("get-webhooks-publish-summary", "Get Webhooks Publish Summary"),
        ("retrigger-failed-events", "Retrigger Failed Events"),
    ],
    "08-client-management": [
        ("add-client-to-system-whitelabel-or-not", "Add Client To System (Whitelabel or not)"),
        ("fetch-all-clients", "Fetch all clients"),
        ("create-new-client-api-key", "Create New Client API Key"),
        ("get-clients-api-keys", "Get Clients API Keys"),
        ("delete-client-api-key", "Delete Client API Key"),
        ("reset-client-api-key", "Reset Client API Key"),
    ],
    "09-smart-senders": [
        ("get-mailbox-otp", "Get one-time password for an admin mailbox"),
        ("get_new-endpoint", "Auto Generate Mailboxes API"),
        ("search-domain", "Search Domain"),
        ("get-vendors", "Get Vendors"),
        ("save-domain-mailbox-info", "Place Order API"),
        ("get-domain-list", "Get Purchased Domain List API"),
        ("get-order-details-api", "Get Order Details API"),
    ],
    "10-global-analytics": [
        ("get_v1-analytics-campaign-list", "Get Campaign List"),
        ("get_v1-analytics-client-list", "Get Client List"),
        ("get_v1-analytics-client-month-wise-count", "Get Month-wise Client Count"),
        ("get_v1-analytics-overall-stats-v2", "Get Overall Stats"),
        ("get_v1-analytics-day-wise-overall-stats", "Get Day-wise Overall Stats"),
        ("get_v1-analytics-day-wise-overall-stats-by-sent-time", "Get Day-wise Overall Stats by Sent Time"),
        ("get_v1-analytics-day-wise-positive-reply-stats", "Get Day-wise Positive Reply Stats"),
        ("get_v1-analytics-day-wise-positive-reply-stats-by-sent-time", "Get Day-wise Positive Reply Stats by Sent Time"),
        ("get_v1-analytics-campaign-overall-stats", "Get Campaign Overall Stats"),
        ("get_v1-analytics-client-overall-stats", "Get Client Overall Stats"),
        ("get_v1-analytics-mailbox-name-wise-health-metrics", "Get Email-Id-wise Health Metrics"),
        ("get_v1-analytics-mailbox-domain-wise-health-metrics", "Get Domain-wise Health Metrics"),
        ("get_v1-analytics-mailbox-provider-wise-overall-performance", "Get Provider-wise Overall Performance"),
        ("get_v1-analytics-team-board-overall-stats", "Get Team Board Overall Stats"),
        ("get_v1-analytics-lead-overall-stats", "Get Lead Overall Stats"),
        ("get_v1-analytics-lead-category-wise-response", "Get Lead Category-wise Response"),
        ("get_v1-analytics-campaign-leads-take-for-first-reply", "Get Leads Take for First Reply"),
        ("get_v1-analytics-campaign-follow-up-reply-rate", "Get Follow-up Reply Rate"),
        ("get_v1-analytics-campaign-lead-to-reply-time", "Get Lead to Reply Time"),
        ("get_v1-analytics-campaign-response-stats", "Get Campaign Response Stats"),
        ("get_v1-analytics-campaign-status-stats", "Get Campaign Status Stats"),
        ("get_v1-analytics-mailbox-overall-stats", "Get Mailbox Overall Stats"),
    ],
    "11-master-inbox": [
        ("fetch-inbox-replies", "Fetch Inbox Replies"),
        ("fetch-unread-replies", "Fetch Unread Replies"),
        ("fetch-snoozed-messages", "Fetch Snoozed Messages"),
        ("fetch-important-marked-messages", "Fetch Important Marked Messages"),
        ("fetch-scheduled-messages", "Fetch Scheduled Messages"),
        ("fetch-messages-with-reminders", "Fetch Messages with Reminders"),
        ("fetched-archived-messages", "Fetched Archived Messages"),
        ("fetch-master-inbox-lead-by-id", "Fetch Master Inbox Lead by ID"),
        ("fetch-untracked-replies", "Fetch Untracked Replies"),
        ("reply-to-lead-from-master-inbox-via-api", "Reply To Lead From Master Inbox via API"),
        ("forward-reply", "Forward a Reply"),
        ("update-lead-revenue", "Update Lead Revenue"),
        ("update-lead-category", "Update Lead Category"),
        ("create-lead-task", "Create Lead Task"),
        ("create-lead-note", "Create Lead Note"),
        ("block-domains-1", "Block Domains"),
        ("resume-lead-1", "Resume Lead"),
        ("change-read-status", "Change Read Status"),
        ("set-reminder", "Set Reminder"),
        ("push-lead-to-subsequence", "Push Lead To Subsequence"),
        ("update-team-member-to-lead", "Update Team Member To Lead"),
    ],
    "12-smart-prospect": [
        ("getdepartments", "Get departments"),
        ("getcities", "Get cities"),
        ("getcountries", "Get countries"),
        ("getstates", "Get states"),
        ("getindustries", "Get industries"),
        ("getsubindustries", "Get sub-industries"),
        ("getheadcounts", "Get head counts"),
        ("getlevels", "Get levels"),
        ("getrevenue", "Get revenue options"),
        ("getcompanies", "Get companies"),
        ("getdomains", "Get domains"),
        ("getjobtitles", "Get job titles"),
        ("getkeywords", "Get keywords"),
        ("searchcontacts", "Search contacts"),
        ("fetchcontacts", "Fetch contacts"),
        ("getcontacts", "Get contacts"),
        ("reviewcontacts", "Review contacts"),
        ("getsavedsearches", "Get saved searches"),
        ("getrecentsearches", "Get recent searches"),
        ("getfetchedsearches", "Get fetched searches"),
        ("savesearch", "Save search"),
        ("updatesavedsearch", "Update saved search"),
        ("updatefetchedlead", "Update fetched lead"),
        ("getsearchanalytics", "Get search analytics"),
        ("getreplyanalytics", "Get reply analytics"),
        ("findemails", "Find emails"),
    ],
}


def fetch_page(slug: str) -> str:
    """Fetch raw HTML content from a readme.io reference page."""
    url = f"{BASE_URL}/{slug}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} for {slug}")
        return ""
    except Exception as e:
        print(f"  Error fetching {slug}: {e}")
        return ""


class ReadmeHTMLParser(HTMLParser):
    """Extract main content from readme.io reference pages."""

    def __init__(self):
        super().__init__()
        self.in_main = False
        self.depth = 0
        self.content_parts = []
        self.current_tag = None
        self.skip_tags = {"script", "style", "nav", "svg", "iframe"}
        self.skip_depth = 0
        self.in_skip = False
        self.in_code = False
        self.code_content = []
        self.in_pre = False
        self.list_depth = 0
        self.in_table = False
        self.table_rows = []
        self.current_row = []
        self.current_cell = []
        self.in_cell = False
        self.is_header_row = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        classes = attrs_dict.get("class", "")

        # Skip navigation, scripts, etc.
        if tag in self.skip_tags:
            self.in_skip = True
            self.skip_depth = 1
            return
        if self.in_skip:
            self.skip_depth += 1
            return

        # Detect main content area
        if not self.in_main:
            if tag == "div" and ("rm-Article" in classes or "markdown-body" in classes or "content-body" in classes):
                self.in_main = True
                self.depth = 1
                return
            # Also try article tag
            if tag == "article":
                self.in_main = True
                self.depth = 1
                return

        if not self.in_main:
            return

        if tag == "div":
            self.depth += 1

        # Headings
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            self.content_parts.append(f"\n{'#' * level} ")

        # Paragraphs
        if tag == "p":
            self.content_parts.append("\n\n")

        # Code blocks
        if tag == "pre":
            self.in_pre = True
            self.code_content = []

        if tag == "code":
            if self.in_pre:
                lang = classes.split()[0] if classes else ""
                # Try to extract language from class like "language-json"
                if lang.startswith("language-"):
                    lang = lang[9:]
                elif lang.startswith("lang-"):
                    lang = lang[5:]
                self.content_parts.append(f"\n```{lang}\n")
                self.in_code = True
            else:
                self.content_parts.append("`")
                self.in_code = True

        # Lists
        if tag in ("ul", "ol"):
            self.list_depth += 1
            self.content_parts.append("\n")

        if tag == "li":
            indent = "  " * (self.list_depth - 1)
            self.content_parts.append(f"\n{indent}- ")

        # Tables
        if tag == "table":
            self.in_table = True
            self.table_rows = []

        if tag == "tr":
            self.current_row = []

        if tag == "th":
            self.in_cell = True
            self.current_cell = []
            self.is_header_row = True

        if tag == "td":
            self.in_cell = True
            self.current_cell = []

        # Bold / italic
        if tag in ("strong", "b"):
            self.content_parts.append("**")
        if tag in ("em", "i"):
            self.content_parts.append("*")

        # Links
        if tag == "a":
            href = attrs_dict.get("href", "")
            self.content_parts.append("[")
            self._pending_href = href

        # Line breaks
        if tag == "br":
            self.content_parts.append("\n")

        # Blockquote
        if tag == "blockquote":
            self.content_parts.append("\n> ")

    def handle_endtag(self, tag):
        if tag in self.skip_tags and self.in_skip:
            self.skip_depth -= 1
            if self.skip_depth <= 0:
                self.in_skip = False
            return
        if self.in_skip:
            self.skip_depth -= 1
            if self.skip_depth <= 0:
                self.in_skip = False
            return

        if not self.in_main:
            return

        if tag == "div":
            self.depth -= 1
            if self.depth <= 0:
                self.in_main = False

        if tag == "code":
            if self.in_pre:
                self.content_parts.append("\n```\n")
            else:
                self.content_parts.append("`")
            self.in_code = False

        if tag == "pre":
            self.in_pre = False

        if tag in ("ul", "ol"):
            self.list_depth = max(0, self.list_depth - 1)
            self.content_parts.append("\n")

        if tag in ("strong", "b"):
            self.content_parts.append("**")
        if tag in ("em", "i"):
            self.content_parts.append("*")

        if tag == "a":
            href = getattr(self, "_pending_href", "")
            self.content_parts.append(f"]({href})")

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.content_parts.append("\n")

        # Table cells
        if tag in ("th", "td") and self.in_cell:
            self.in_cell = False
            self.current_row.append("".join(self.current_cell).strip())

        if tag == "tr" and self.in_table:
            if self.current_row:
                self.table_rows.append((self.current_row, self.is_header_row))
            self.is_header_row = False

        if tag == "table" and self.in_table:
            self.in_table = False
            self._render_table()

    def _render_table(self):
        if not self.table_rows:
            return
        self.content_parts.append("\n\n")
        for i, (row, is_header) in enumerate(self.table_rows):
            self.content_parts.append("| " + " | ".join(row) + " |\n")
            if is_header or i == 0:
                self.content_parts.append("| " + " | ".join(["---"] * len(row)) + " |\n")
        self.content_parts.append("\n")

    def handle_data(self, data):
        if self.in_skip:
            return
        if self.in_cell:
            self.current_cell.append(data)
            return
        if self.in_main:
            self.content_parts.append(data)

    def get_content(self) -> str:
        text = "".join(self.content_parts)
        # Clean up excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()


def html_to_markdown_simple(html: str, title: str) -> str:
    """Convert HTML to markdown using our parser."""
    parser = ReadmeHTMLParser()
    parser.feed(html)
    content = parser.get_content()

    if not content or len(content) < 50:
        # Fallback: extract all text between common content markers
        # Try to get JSON/code blocks at minimum
        content = fallback_extract(html)

    return f"# {title}\n\n{content}"


def fallback_extract(html: str) -> str:
    """Fallback extraction when main parser doesn't find content."""
    # Remove script/style tags
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)

    # Try to find the API content section
    # readme.io often has content in specific div structures
    patterns = [
        r'<div[^>]*class="[^"]*markdown-body[^"]*"[^>]*>(.*?)</div>',
        r'<article[^>]*>(.*?)</article>',
        r'<div[^>]*id="content"[^>]*>(.*?)</div>',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            text = match.group(1)
            # Strip remaining HTML tags
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text)
            if len(text.strip()) > 50:
                return text.strip()

    # Last resort: strip all HTML
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)
    # Try to find the useful part (skip nav, etc.)
    return text.strip()[:5000] if text.strip() else "(No content extracted)"


def scrape_page(slug: str, title: str, section_dir: str) -> bool:
    """Scrape a single page and save as markdown."""
    filename = f"{slug}.md"
    filepath = os.path.join(section_dir, filename)

    html = fetch_page(slug)
    if not html:
        return False

    md = html_to_markdown_simple(html, title)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md)

    return True


def main():
    total = sum(len(pages) for pages in SECTIONS.values())
    print(f"Smartlead API Docs Scraper")
    print(f"Total pages to scrape: {total}")
    print(f"Output directory: {DOCS_DIR}")
    print("=" * 50)

    success = 0
    failed = 0

    for section_name, pages in SECTIONS.items():
        section_dir = os.path.join(DOCS_DIR, section_name)
        os.makedirs(section_dir, exist_ok=True)

        print(f"\n📁 {section_name} ({len(pages)} pages)")

        for slug, title in pages:
            print(f"  ⏳ {title}...", end=" ", flush=True)

            if scrape_page(slug, title, section_dir):
                success += 1
                print("✅")
            else:
                failed += 1
                print("❌")

            # Be polite to the server
            time.sleep(0.5)

    print(f"\n{'=' * 50}")
    print(f"Done! ✅ {success} scraped, ❌ {failed} failed")
    print(f"Files saved to: {DOCS_DIR}")


if __name__ == "__main__":
    main()
