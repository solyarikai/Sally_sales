import { useState } from "react";

const feedbackItems = [
  {
    id: "F1",
    severity: "critical",
    area: "E2E Testing",
    raw: "E2E tests pass but don't test UI — only backend API. Must test from UI, not database.",
    requirement: "All E2E tests must operate throusyegh the browser UI, taking screenshots at every state transition.",
    round: 1,
  },
  {
    id: "F2",
    severity: "critical",
    area: "Conversation History",
    raw: "No conversation history for pn@getsally.io after redirect to contact page.",
    requirement: "After redirect to contact page, full conversation history for the contact must load and be visible.",
    round: 1,
  },
  {
    id: "F3",
    severity: "critical",
    area: "Campaign Selector",
    raw: "30+ campaigns shown but only 4 selectable.",
    requirement: "All displayed campaigns must be selectable. Implement pagination/virtual scroll for 100+ campaigns.",
    round: 1,
  },
  {
    id: "F4",
    severity: "critical",
    area: "Message Sending",
    raw: "Sending message to pn@getsally.io doesn't work from auto-reply flow.",
    requirement: "Auto-reply submission must succeed, reflect in UI immediately, and appear in conversation history.",
    round: 1,
  },
  {
    id: "F5",
    severity: "high",
    area: "URL / Navigation",
    raw: "URL mismatch between project page URL and selected project in top-left corner selector.",
    requirement: "Project selector state and URL must always be in sync.",
    round: 1,
  },
  {
    id: "F6",
    severity: "high",
    area: "Reply Counter",
    raw: "Number of contacts needing replies doesn't change after submitting a reply.",
    requirement: "Reply counter must decrement immediately (optimistic UI) upon successful reply submission.",
    round: 1,
  },
  {
    id: "F7",
    severity: "high",
    area: "SmartLead Integration",
    raw: "SmartLead link to inbox with the lead must be visible in top-right corner.",
    requirement: "Every contact detail view must show a SmartLead inbox deep-link in the top-right corner.",
    round: 1,
  },
  {
    id: "F8",
    severity: "medium",
    area: "Data Labeling",
    raw: "'Sent via E2E test' label visible in UI.",
    requirement: "E2E test metadata must never be visible in production UI.",
    round: 1,
  },
  {
    id: "F9",
    severity: "high",
    area: "UX Consistency",
    raw: "Conversation history, campaign list, reply components not reused across views.",
    requirement: "Single shared component library reused identically in CRM, Replies page, and Lead Details modal.",
    round: 1,
  },
  {
    id: "F10",
    severity: "medium",
    area: "Campaign History",
    raw: "Must show ALL campaigns a contact was engaged in historically.",
    requirement: "Contact detail view shows full historical campaign engagement with dates, sorted by recency, with pagination.",
    round: 1,
  },
  {
    id: "F11",
    severity: "critical",
    area: "Performance",
    raw: "Loading ALL campaigns at once is extremely slow. 'All company, all campaigns is crazy.'",
    requirement: "NEVER load all campaigns at once. Default to showing only the 5–10 most recent campaigns. Lazy-load older ones on scroll or explicit 'Load more'. No 'All' option that fetches everything.",
    round: 2,
  },
  {
    id: "F12",
    severity: "high",
    area: "Campaign Selector UX",
    raw: "Dropdown select was good before. Now it's different/worse. Bring back dropdown.",
    requirement: "Use a dropdown select for campaign picker (the previous pattern). Make it searchable, collapsible, sorted by date with most recent first. Hide campaign list by default — show compact summary, expand on click.",
    round: 2,
  },
  {
    id: "F13",
    severity: "high",
    area: "Campaign Selector UX",
    raw: "No datetime shown on campaigns. Need to see when each campaign was.",
    requirement: "Every campaign in the selector must show its date/time. Format: relative ('3 days ago') for recent, absolute date for older.",
    round: 2,
  },
  {
    id: "F14",
    severity: "critical",
    area: "Modal UX",
    raw: "Modal opens but shows details only — conversation is not visible. 'I don't see conversation opened.'",
    requirement: "When opening the contact/lead details modal, the conversation history panel must be visible by default — not hidden behind a tab or collapsed. Conversation is the primary content.",
    round: 2,
  },
  {
    id: "F15",
    severity: "critical",
    area: "Conversation History",
    raw: "Sent email not visible in the latest campaign view.",
    requirement: "User's own sent emails must appear in conversation history for the relevant campaign. Verify sent messages render immediately after sending.",
    round: 2,
  },
  {
    id: "F16",
    severity: "high",
    area: "UX Consistency",
    raw: "Campaign selection UI is different between CRM contacts URL view and other views.",
    requirement: "Campaign selector component must be IDENTICAL across CRM contacts page, Replies page, and Lead Details modal. Same component, same behavior, same sorting.",
    round: 2,
  },
  {
    id: "F17",
    severity: "high",
    area: "Campaign Selector UX",
    raw: "Campaign selector should be searchable and collapsible. Show recent first, hide the rest.",
    requirement: "Campaign dropdown: (1) searchable with text filter, (2) collapsible — default collapsed showing only active/most recent campaign, (3) sorted by date descending, (4) expand to browse all.",
    round: 2,
  },
  {
    id: "F18",
    severity: "critical",
    area: "Navigation",
    raw: "After closing modal, CRM should filter to show only that contact, but it doesn't.",
    requirement: "Closing the lead details modal must update CRM contacts view to filter/highlight the contact that was just viewed. URL should reflect the filtered state.",
    round: 2,
  },
];

const checklistGroups = [
  {
    title: "1. E2E Test Infrastructure",
    items: [
      { text: "All tests run in real browser (Playwright/Cypress), not API-only", priority: "P0", round: 1 },
      { text: "Screenshot captured at EVERY FSM state transition", priority: "P0", round: 1 },
      { text: "Screenshots auto-analyzed for regressions", priority: "P1", round: 1 },
      { text: "Test artifacts never leak into production UI", priority: "P0", round: 1 },
      { text: "Tests validate UI state, not just DB state", priority: "P0", round: 1 },
      { text: "Bug screenshots stored in tasks/test_project/autotest/bugs/", priority: "P1", round: 1 },
    ],
  },
  {
    title: "2. Auto-Reply Flow",
    items: [
      { text: "Replies page loads with correct count of contacts needing replies", priority: "P0", round: 1 },
      { text: "Selecting a contact shows full conversation history from UI", priority: "P0", round: 1 },
      { text: "Reply form submits successfully (no silent failures)", priority: "P0", round: 1 },
      { text: "Reply counter decrements immediately after submission", priority: "P0", round: 1 },
      { text: "New message appears in conversation history instantly", priority: "P0", round: 1 },
      { text: "Sent email visible in conversation history for the correct campaign", priority: "P0", round: 2 },
    ],
  },
  {
    title: "3. Campaign Selector (Revised R2)",
    items: [
      { text: "Use dropdown select pattern (not inline list) — restore previous good UX", priority: "P0", round: 2 },
      { text: "Dropdown is searchable — text filter narrows campaign list", priority: "P0", round: 2 },
      { text: "Dropdown is collapsible — default shows only most recent campaign", priority: "P0", round: 2 },
      { text: "Campaigns sorted by date descending (most recent first)", priority: "P0", round: 2 },
      { text: "Each campaign shows date/time (relative for recent, absolute for older)", priority: "P0", round: 2 },
      { text: "NEVER load all campaigns at once — lazy load, max 5–10 initially", priority: "P0", round: 2 },
      { text: "All listed campaigns are selectable (no count mismatch)", priority: "P0", round: 1 },
      { text: "Pagination or 'Load more' for contacts with 100+ campaigns", priority: "P1", round: 1 },
      { text: "SAME component used in CRM, Replies, and Lead Details modal", priority: "P0", round: 2 },
    ],
  },
  {
    title: "4. Conversation History",
    items: [
      { text: "History loads for every contact (pn@getsally.io verified)", priority: "P0", round: 1 },
      { text: "Default: show conversation for most recent campaign only (not all)", priority: "P0", round: 2 },
      { text: "Lazy-load older campaign conversations on demand", priority: "P0", round: 2 },
      { text: "Sent emails appear in history immediately after sending", priority: "P0", round: 2 },
      { text: "SmartLead campaign data included alongside internal data", priority: "P0", round: 1 },
      { text: "Same component in: Replies page, CRM, Lead Details modal", priority: "P0", round: 1 },
    ],
  },
  {
    title: "5. Lead Details Modal",
    items: [
      { text: "Modal opens with conversation history visible by default (not behind details tab)", priority: "P0", round: 2 },
      { text: "Conversation is primary content; contact details in sidebar/secondary", priority: "P0", round: 2 },
      { text: "Campaign selector inside modal uses same shared dropdown component", priority: "P0", round: 2 },
      { text: "SmartLead inbox link visible in top-right corner", priority: "P0", round: 1 },
      { text: "Closing modal → CRM filters to show that contact", priority: "P0", round: 2 },
      { text: "Closing modal → URL updates to reflect filtered state", priority: "P0", round: 2 },
    ],
  },
  {
    title: "6. Navigation & URL Sync",
    items: [
      { text: "Project page URL matches selected project in top-left selector", priority: "P0", round: 1 },
      { text: "Changing project in selector updates URL", priority: "P0", round: 1 },
      { text: "Navigating via URL updates selector state", priority: "P0", round: 1 },
      { text: "After modal close, CRM view filters to the viewed contact", priority: "P0", round: 2 },
      { text: "No stale state after browser back/forward", priority: "P1", round: 1 },
    ],
  },
  {
    title: "7. Performance",
    items: [
      { text: "Campaign list loads in < 500ms (only recent campaigns fetched)", priority: "P0", round: 2 },
      { text: "Conversation history for single campaign loads in < 1s", priority: "P0", round: 2 },
      { text: "No full-company campaign fetch on contact open — EVER", priority: "P0", round: 2 },
      { text: "Lazy loading for older campaigns — no upfront cost", priority: "P0", round: 2 },
      { text: "Loading indicators shown during async fetches", priority: "P1", round: 2 },
    ],
  },
];

const fsmStates = [
  { id: "S0", label: "IDLE", desc: "Test runner ready, browser launched", isNew: false },
  { id: "S1", label: "OPEN_REPLIES", desc: "Navigate to Replies page", isNew: false },
  { id: "S2", label: "VERIFY_COUNT", desc: "📸 Reply counter visible & > 0", isNew: false },
  { id: "S3", label: "SELECT_CONTACT", desc: "Click pn@getsally.io in queue", isNew: false },
  { id: "S4", label: "VERIFY_HISTORY", desc: "📸 Conversation loaded for MOST RECENT campaign only (not all!)", isNew: true },
  { id: "S4b", label: "VERIFY_PERF", desc: "📸 Load time < 1s · No all-company campaign fetch", isNew: true },
  { id: "S5", label: "VERIFY_SELECTOR", desc: "📸 Dropdown: searchable, dates shown, sorted recency, collapsed default", isNew: true },
  { id: "S5b", label: "SWITCH_CAMPAIGN", desc: "📸 Select different campaign → lazy loads conversation", isNew: true },
  { id: "S6", label: "COMPOSE_REPLY", desc: "Type reply in reply form", isNew: false },
  { id: "S7", label: "SUBMIT_REPLY", desc: "Click send", isNew: false },
  { id: "S8", label: "VERIFY_SENT_EMAIL", desc: "📸 Sent email visible in conversation history for this campaign", isNew: true },
  { id: "S9", label: "VERIFY_COUNTER", desc: "📸 Reply counter decremented immediately", isNew: false },
  { id: "S10", label: "OPEN_MODAL", desc: "Click contact → open Lead Details modal", isNew: false },
  { id: "S11", label: "VERIFY_MODAL_CONV", desc: "📸 Modal shows CONVERSATION by default (not details tab)", isNew: true },
  { id: "S11b", label: "VERIFY_MODAL_SELECTOR", desc: "📸 Same dropdown component as Replies page, identical behavior", isNew: true },
  { id: "S12", label: "VERIFY_SMARTLEAD", desc: "📸 SmartLead inbox link in top-right corner", isNew: false },
  { id: "S13", label: "CLOSE_MODAL", desc: "Close the modal", isNew: false },
  { id: "S14", label: "VERIFY_CRM_FILTER", desc: "📸 CRM filters to this contact · URL updated", isNew: true },
  { id: "S15", label: "VERIFY_URL_SYNC", desc: "📸 URL matches project selector", isNew: false },
  { id: "S16", label: "PASS", desc: "All assertions passed, screenshots archived", isNew: false },
];

const fsmTransitions = [
  { from: "S0", to: "S1", label: "launch" },
  { from: "S1", to: "S2", label: "page loaded" },
  { from: "S2", to: "S3", label: "count > 0 ✓" },
  { from: "S3", to: "S4", label: "contact loaded" },
  { from: "S4", to: "S4b", label: "recent history visible ✓" },
  { from: "S4b", to: "S5", label: "perf OK ✓" },
  { from: "S5", to: "S5b", label: "selector valid ✓" },
  { from: "S5b", to: "S6", label: "campaign switched ✓" },
  { from: "S6", to: "S7", label: "text entered" },
  { from: "S7", to: "S8", label: "sent ✓" },
  { from: "S8", to: "S9", label: "email in history ✓" },
  { from: "S9", to: "S10", label: "counter updated ✓" },
  { from: "S10", to: "S11", label: "modal opened" },
  { from: "S11", to: "S11b", label: "conversation default ✓" },
  { from: "S11b", to: "S12", label: "selector consistent ✓" },
  { from: "S12", to: "S13", label: "SmartLead link ✓" },
  { from: "S13", to: "S14", label: "modal closed" },
  { from: "S14", to: "S15", label: "CRM filtered ✓" },
  { from: "S15", to: "S16", label: "URL synced ✓" },
];

const failTransitions = [
  { from: "S2", label: "count = 0" },
  { from: "S4", label: "no history / loaded ALL" },
  { from: "S4b", label: "load > 1s / all-company fetch" },
  { from: "S5", label: "not searchable / no dates / wrong sort" },
  { from: "S5b", label: "lazy load failed" },
  { from: "S7", label: "send failed" },
  { from: "S8", label: "sent email missing from history" },
  { from: "S9", label: "counter stale" },
  { from: "S11", label: "shows details tab, not conversation" },
  { from: "S11b", label: "selector differs from Replies page" },
  { from: "S12", label: "SmartLead link missing" },
  { from: "S14", label: "CRM not filtered to contact" },
  { from: "S15", label: "URL mismatch" },
];

const useCases = [
  {
    id: "UC1",
    title: "Auto-Reply to Queued Contact",
    actor: "Sales Rep",
    precondition: "Contacts exist in reply queue with pending messages",
    flow: [
      "Open Replies page → counter shows pending contacts",
      "Select pn@getsally.io → conversation loads for MOST RECENT campaign (lazy, < 1s)",
      "Campaign dropdown available: searchable, sorted by date, collapsed by default",
      "Compose and send reply",
      "Sent email appears immediately in conversation history for this campaign",
      "Reply counter decrements immediately",
    ],
    postcondition: "Reply sent, visible in history, counter updated",
    bugs: ["F4", "F6", "F11", "F15"],
  },
  {
    id: "UC2",
    title: "Browse Contact Campaign History",
    actor: "Sales Rep",
    precondition: "Contact engaged in multiple campaigns over time",
    flow: [
      "Open contact detail (any view) → most recent campaign conversation shown by default",
      "Campaign dropdown: collapsed, shows current campaign name + date",
      "Click dropdown → expands, searchable text filter, sorted by date desc",
      "Each campaign shows date (relative for recent, absolute for old)",
      "Select older campaign → lazy-loads that campaign's conversation (no upfront all-fetch)",
      "100+ campaigns → 'Load more' at bottom of dropdown",
    ],
    postcondition: "Browse any campaign without performance hit, never load all at once",
    bugs: ["F3", "F10", "F11", "F12", "F13", "F17"],
  },
  {
    id: "UC3",
    title: "Open Lead Details Modal — Conversation First",
    actor: "Sales Rep",
    precondition: "Contact visible in CRM or Replies view",
    flow: [
      "Click contact name → Lead Details modal opens",
      "Conversation history is PRIMARY visible content (not hidden behind details tab)",
      "Contact details shown in sidebar or secondary panel",
      "Campaign selector is SAME dropdown component as Replies page — identical behavior",
      "SmartLead inbox link visible in top-right corner of modal",
    ],
    postcondition: "Conversation-first modal with consistent shared components",
    bugs: ["F14", "F16", "F7"],
  },
  {
    id: "UC4",
    title: "Close Modal → CRM Filters to Contact",
    actor: "Sales Rep",
    precondition: "Lead Details modal is open for a specific contact",
    flow: [
      "Close the modal (X button or click outside)",
      "CRM contacts view filters to show the contact just viewed",
      "URL updates to reflect the filtered state",
      "User can clear filter to return to full list",
    ],
    postcondition: "Context preserved between modal and CRM, no disorientation",
    bugs: ["F18", "F5"],
  },
  {
    id: "UC5",
    title: "E2E Screenshot-Driven Test Run",
    actor: "CI/CD Pipeline",
    precondition: "Test environment running, browser automation configured",
    flow: [
      "Launch browser → navigate through full FSM (S0 → S16)",
      "Screenshot at EVERY state transition (20 states = 20+ screenshots)",
      "Assert: only recent campaigns loaded (no all-company fetch) [NEW]",
      "Assert: sent email visible in conversation after reply [NEW]",
      "Assert: modal shows conversation by default, not details tab [NEW]",
      "Assert: CRM filters to contact after modal close [NEW]",
      "Assert: campaign selector identical in all views [NEW]",
      "On any failure → S_FAIL with screenshot + bug report",
    ],
    postcondition: "Full visual audit trail, all bugs caught at UI level",
    bugs: ["F1", "F8"],
  },
  {
    id: "UC6",
    title: "Access SmartLead Inbox for Contact",
    actor: "Sales Rep",
    precondition: "Contact exists in SmartLead and internal CRM",
    flow: [
      "Open any contact detail view or modal",
      "SmartLead inbox deep-link visible in top-right",
      "Click → opens SmartLead inbox filtered to this lead",
    ],
    postcondition: "One-click access to SmartLead from any contact view",
    bugs: ["F7"],
  },
];

/* ───── UI Components ───── */

const SeverityBadge = ({ severity }) => {
  const c = {
    critical: "bg-red-100 text-red-800 border-red-200",
    high: "bg-orange-100 text-orange-800 border-orange-200",
    medium: "bg-yellow-100 text-yellow-800 border-yellow-200",
  };
  return <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${c[severity]}`}>{severity.toUpperCase()}</span>;
};

const RoundBadge = ({ round }) => (
  <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${round === 2 ? "bg-purple-100 text-purple-700 border border-purple-200" : "bg-gray-100 text-gray-500"}`}>
    R{round}
  </span>
);

const PriorityBadge = ({ priority }) => {
  const c = { P0: "bg-red-600 text-white", P1: "bg-orange-500 text-white", P2: "bg-blue-500 text-white" };
  return <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${c[priority]}`}>{priority}</span>;
};

/* ───── Tabs ───── */

const FeedbackTab = () => {
  const [filterRound, setFilterRound] = useState(0);
  const filtered = filterRound === 0 ? feedbackItems : feedbackItems.filter((f) => f.round === filterRound);
  const crit = filtered.filter((f) => f.severity === "critical").length;
  const high = filtered.filter((f) => f.severity === "high").length;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex gap-2">
          {[0, 1, 2].map((r) => (
            <button key={r} onClick={() => setFilterRound(r)}
              className={`text-xs px-3 py-1.5 rounded-full font-medium transition-all ${filterRound === r ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}>
              {r === 0 ? `All (${feedbackItems.length})` : `Round ${r}${r === 2 ? " — NEW" : ""} (${feedbackItems.filter(f => f.round === r).length})`}
            </button>
          ))}
        </div>
        <div className="text-xs text-gray-500">
          <span className="text-red-600 font-semibold">{crit} critical</span>{" · "}
          <span className="text-orange-600 font-semibold">{high} high</span>{" · "}
          {filtered.length} total
        </div>
      </div>
      {filtered.map((f) => (
        <div key={f.id} className={`border rounded-lg p-4 bg-white ${f.round === 2 ? "border-purple-200 ring-1 ring-purple-100" : "border-gray-200"}`}>
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span className="font-mono text-xs text-gray-400">{f.id}</span>
            <SeverityBadge severity={f.severity} />
            <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">{f.area}</span>
            <RoundBadge round={f.round} />
          </div>
          <p className="text-sm text-gray-500 italic mb-2">"{f.raw}"</p>
          <p className="text-sm font-medium text-gray-900">{f.requirement}</p>
        </div>
      ))}
    </div>
  );
};

const ChecklistTab = () => {
  const [checked, setChecked] = useState({});
  const [showNewOnly, setShowNewOnly] = useState(false);
  const toggle = (gi, ii) => setChecked((p) => ({ ...p, [`${gi}-${ii}`]: !p[`${gi}-${ii}`] }));
  const total = checklistGroups.reduce((s, g) => s + g.items.length, 0);
  const done = Object.values(checked).filter(Boolean).length;
  const newCount = checklistGroups.reduce((s, g) => s + g.items.filter((i) => i.round === 2).length, 0);

  return (
    <div>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <p className="text-sm text-gray-500">{total} items · <span className="text-purple-600 font-medium">{newCount} new (R2)</span></p>
          <button onClick={() => setShowNewOnly(!showNewOnly)}
            className={`text-xs px-3 py-1 rounded-full font-medium ${showNewOnly ? "bg-purple-600 text-white" : "bg-purple-100 text-purple-700 hover:bg-purple-200"}`}>
            {showNewOnly ? "Showing R2 only" : "Filter R2 only"}
          </button>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-32 h-2 bg-gray-200 rounded-full overflow-hidden">
            <div className="h-full bg-green-500 rounded-full transition-all" style={{ width: `${total ? (done / total) * 100 : 0}%` }} />
          </div>
          <span className="text-xs text-gray-500">{done}/{total}</span>
        </div>
      </div>
      <div className="space-y-4">
        {checklistGroups.map((group, gi) => {
          const items = showNewOnly ? group.items.filter((i) => i.round === 2) : group.items;
          if (!items.length) return null;
          return (
            <div key={gi} className="border border-gray-200 rounded-lg bg-white overflow-hidden">
              <div className="bg-gray-50 px-4 py-2 border-b border-gray-200">
                <h3 className="text-sm font-semibold text-gray-800">{group.title}</h3>
              </div>
              <div className="divide-y divide-gray-100">
                {items.map((item) => {
                  const oi = group.items.indexOf(item);
                  const key = `${gi}-${oi}`;
                  return (
                    <label key={oi} className={`flex items-start gap-3 px-4 py-2.5 cursor-pointer hover:bg-gray-50 transition-colors ${checked[key] ? "bg-green-50" : item.round === 2 ? "bg-purple-50/40" : ""}`}>
                      <input type="checkbox" checked={!!checked[key]} onChange={() => toggle(gi, oi)} className="mt-0.5 rounded" />
                      <span className={`text-sm flex-1 ${checked[key] ? "line-through text-gray-400" : "text-gray-700"}`}>{item.text}</span>
                      <div className="flex gap-1 shrink-0">
                        {item.round === 2 && <RoundBadge round={2} />}
                        <PriorityBadge priority={item.priority} />
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const  loadiFSMTab = () => {
  const [hoveredState, setHoveredState] = useState(null);
  const stateH = 52;
  const gap = 10;
  const stateW = 430;
  const lm = 15;
  const totalH = fsmStates.length * (stateH + gap) + 60;
  const failX = 540;
  const failY = Math.floor(totalH / 2) - 25;
  const getY = (i) => 40 + i * (stateH + gap);

  return (
    <div>
      <p className="text-sm text-gray-500 mb-3">
        {fsmStates.length} states + FAIL · {fsmTransitions.length + failTransitions.length} transitions · 📸 = screenshot checkpoint ·
        <span className="text-purple-600 font-medium ml-1">Purple = new from Round 2</span>
      </p>
      <div className="border border-gray-200 rounded-lg bg-white overflow-x-auto">
        <svg width="770" viewBox={`0 0 770 ${totalH}`} className="w-full" style={{ minWidth: 650 }}>
          <defs>
            <marker id="arr" viewBox="0 0 10 7" refX="10" refY="3.5" markerWidth="8" markerHeight="6" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#6b7280" /></marker>
            <marker id="arrR" viewBox="0 0 10 7" refX="10" refY="3.5" markerWidth="8" markerHeight="6" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#ef4444" /></marker>
          </defs>

          {fsmTransitions.map((t, i) => {
            const fi = fsmStates.findIndex((s) => s.id === t.from);
            const ti = fsmStates.findIndex((s) => s.id === t.to);
            const y1 = getY(fi) + stateH - 4;
            const y2 = getY(ti);
            return (
              <g key={`t${i}`}>
                <line x1={lm + 30} y1={y1} x2={lm + 30} y2={y2} stroke="#9ca3af" strokeWidth={1.5} markerEnd="url(#arr)" />
                <text x={lm + 40} y={(y1 + y2) / 2 + 3} fontSize={8} fill="#6b7280">{t.label}</text>
              </g>
            );
          })}

          {failTransitions.map((ft, i) => {
            const fi = fsmStates.findIndex((s) => s.id === ft.from);
            const y1 = getY(fi) + stateH / 2;
            return (
              <g key={`f${i}`} opacity={0.35}>
                <path d={`M ${lm + stateW} ${y1} Q ${failX - 10} ${(y1 + failY + 20) / 2} ${failX} ${failY + 20}`}
                  stroke="#ef4444" strokeWidth={0.8} fill="none" strokeDasharray="3 2" markerEnd="url(#arrR)" />
              </g>
            );
          })}

          {fsmStates.map((s, i) => {
            const y = getY(i);
            const isStart = s.id === "S0";
            const isEnd = s.id === "S16";
            const fill = isStart ? "#dbeafe" : isEnd ? "#dcfce7" : s.isNew ? "#f3e8ff" : hoveredState === s.id ? "#f0f9ff" : "#fff";
            const stroke = isStart ? "#3b82f6" : isEnd ? "#22c55e" : s.isNew ? "#a855f7" : "#d1d5db";
            return (
              <g key={s.id} onMouseEnter={() => setHoveredState(s.id)} onMouseLeave={() => setHoveredState(null)} style={{ cursor: "pointer" }}>
                <rect x={lm} y={y} width={stateW} height={stateH} rx={6} fill={fill} stroke={stroke} strokeWidth={s.isNew ? 2 : 1.5} />
                <text x={lm + 8} y={y + 20} fontSize={9} fontWeight="bold" fill="#1f2937" fontFamily="monospace">{s.id}</text>
                <text x={lm + 48} y={y + 20} fontSize={9.5} fontWeight="600" fill="#374151">{s.label}</text>
                <text x={lm + 8} y={y + 36} fontSize={7.5} fill="#6b7280">{s.desc}</text>
                {s.isNew && <text x={lm + stateW - 28} y={y + 14} fontSize={7} fill="#a855f7" fontWeight="bold">R2</text>}
              </g>
            );
          })}

          <rect x={failX} y={failY} width={190} height={50} rx={8} fill="#fef2f2" stroke="#ef4444" strokeWidth={2} />
          <text x={failX + 95} y={failY + 22} fontSize={12} fontWeight="bold" fill="#dc2626" textAnchor="middle" fontFamily="monospace">S_FAIL</text>
          <text x={failX + 95} y={failY + 38} fontSize={8} fill="#dc2626" textAnchor="middle">📸 Screenshot + bug filed</text>

          <rect x={failX} y={40} width={200} height={108} rx={6} fill="#f9fafb" stroke="#e5e7eb" />
          <text x={failX + 12} y={58} fontSize={10} fontWeight="bold" fill="#374151">Legend</text>
          <line x1={failX + 12} y1={72} x2={failX + 42} y2={72} stroke="#9ca3af" strokeWidth={1.5} markerEnd="url(#arr)" />
          <text x={failX + 50} y={75} fontSize={9} fill="#6b7280">Happy path</text>
          <line x1={failX + 12} y1={90} x2={failX + 42} y2={90} stroke="#ef4444" strokeWidth={1} strokeDasharray="3 2" markerEnd="url(#arrR)" />
          <text x={failX + 50} y={93} fontSize={9} fill="#ef4444">Failure → bug</text>
          <rect x={failX + 12} y={102} width={30} height={14} rx={3} fill="#f3e8ff" stroke="#a855f7" strokeWidth={1.5} />
          <text x={failX + 50} y={113} fontSize={9} fill="#a855f7">New from Round 2</text>
          <circle cx={failX + 24} cy={134} r={5} fill="none" stroke="#9ca3af" strokeWidth={1} />
          <text x={failX + 22} y={137} fontSize={7} textAnchor="middle">📸</text>
          <text x={failX + 50} y={137} fontSize={9} fill="#6b7280">Screenshot checkpoint</text>
        </svg>
      </div>

      <div className="mt-4 bg-gray-50 border border-gray-200 rounded-lg p-4">
        <h4 className="text-sm font-semibold text-gray-700 mb-2">FSM Rules & Round 2 Additions</h4>
        <div className="text-xs text-gray-600 space-y-1.5">
          <p>1. Screenshot at every state transition — timestamp, state ID, DOM snapshot.</p>
          <p>2. Failure at ANY state → S_FAIL → screenshot + bug to <code className="bg-gray-200 px-1 rounded">tasks/test_project/autotest/bugs/</code></p>
          <p>3. All assertions are UI-based (DOM), never backend/DB queries.</p>
          <p className="text-purple-700 font-medium">4. R2 S4: Assert only RECENT campaign loaded (not all). Loading all = FAIL.</p>
          <p className="text-purple-700 font-medium">5. R2 S4b: Performance gate — campaign list &lt; 500ms, conversation &lt; 1s.</p>
          <p className="text-purple-700 font-medium">6. R2 S5: Campaign dropdown must be searchable, show dates, default collapsed.</p>
          <p className="text-purple-700 font-medium">7. R2 S8: Sent email must appear in conversation history (not just DB).</p>
          <p className="text-purple-700 font-medium">8. R2 S11: Modal default view = conversation (details tab showing = FAIL).</p>
          <p className="text-purple-700 font-medium">9. R2 S11b: Selector in modal must be identical to Replies page selector.</p>
          <p className="text-purple-700 font-medium">10. R2 S14: After modal close, CRM must filter to contact. No filter = FAIL.</p>
        </div>
      </div>
    </div>
  );
};

const UseCasesTab = () => (
  <div className="space-y-4">
    <p className="text-sm text-gray-500">{useCases.length} use cases. <span className="text-purple-600">Purple bug refs</span> = from Round 2 feedback.</p>
    {useCases.map((uc) => (
      <div key={uc.id} className="border border-gray-200 rounded-lg bg-white overflow-hidden">
        <div className="bg-gray-50 px-4 py-3 border-b border-gray-200 flex items-center gap-2">
          <span className="font-mono text-xs text-gray-400">{uc.id}</span>
          <h3 className="text-sm font-semibold text-gray-800">{uc.title}</h3>
        </div>
        <div className="p-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <span className="text-xs font-semibold text-gray-500 uppercase">Actor</span>
              <p className="text-sm text-gray-700">{uc.actor}</p>
            </div>
            <div>
              <span className="text-xs font-semibold text-gray-500 uppercase">Precondition</span>
              <p className="text-sm text-gray-700">{uc.precondition}</p>
            </div>
          </div>
          <div>
            <span className="text-xs font-semibold text-gray-500 uppercase">Main Flow</span>
            <ol className="mt-1 space-y-1">
              {uc.flow.map((step, i) => (
                <li key={i} className="text-sm text-gray-700 flex gap-2">
                  <span className="text-gray-400 font-mono text-xs mt-0.5 shrink-0">{i + 1}.</span>
                  {step}
                </li>
              ))}
            </ol>
          </div>
          <div>
            <span className="text-xs font-semibold text-gray-500 uppercase">Postcondition</span>
            <p className="text-sm text-gray-700">{uc.postcondition}</p>
          </div>
          <div>
            <span className="text-xs font-semibold text-gray-500 uppercase">Related Bugs</span>
            <div className="flex gap-1 mt-1 flex-wrap">
              {uc.bugs.map((b, i) => {
                const item = feedbackItems.find((f) => f.id === b);
                const isNew = item?.round === 2;
                return (
                  <span key={i} className={`text-xs px-2 py-0.5 rounded border ${isNew ? "bg-purple-50 text-purple-700 border-purple-200" : "bg-red-50 text-red-700 border-red-200"}`}>
                    {b} — {item?.area}
                  </span>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    ))}
  </div>
);

/* ───── App ───── */

export default function App() {
  const [activeTab, setActiveTab] = useState(0);

  const tabs = [
    { label: "Feedback", icon: "🔍", comp: <FeedbackTab /> },
    { label: "Checklist", icon: "✅", comp: <ChecklistTab /> },
    { label: "FSM", icon: "⚙️", comp: <FSMTab /> },
    { label: "Use Cases", icon: "📋", comp: <UseCasesTab /> },
  ];

  return (
    <div className="min-h-screen bg-gray-100 p-3">
      <div className="max-w-4xl mx-auto">
        <div className="mb-4">
          <h1 className="text-xl font-bold text-gray-900">System Analysis — E2E Auto-Reply Testing</h1>
          <p className="text-sm text-gray-500 mt-1">18 issues (8 new) · 7 checklist groups · 20-state FSM · 6 use cases</p>
          <div className="flex gap-2 mt-2">
            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">R1: 10 issues</span>
            <span className="text-xs bg-purple-100 text-purple-700 px-2 py-1 rounded font-medium">R2: 8 new issues — perf, modal UX, selector, nav</span>
          </div>
        </div>
        <div className="flex gap-1 mb-4 bg-white rounded-lg p-1 border border-gray-200">
          {tabs.map((t, i) => (
            <button key={i} onClick={() => setActiveTab(i)}
              className={`flex-1 text-sm py-2 px-3 rounded-md transition-all font-medium ${activeTab === i ? "bg-gray-900 text-white shadow-sm" : "text-gray-600 hover:bg-gray-100"}`}>
              {t.icon} {t.label}
            </button>
          ))}
        </div>
        {tabs[activeTab].comp}
      </div>
    </div>
  );
}
