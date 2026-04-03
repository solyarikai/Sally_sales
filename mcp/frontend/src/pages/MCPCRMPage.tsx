// MCP CRM wrapper — reuses main app's ContactsPage UI (AG Grid)
// but points API calls to MCP backend (/api/pipeline/crm/contacts)
// This ensures same UI as CRM with MCP's own database

// For now, this file exists as a placeholder.
// The actual CRM page is imported from main app via @main alias in App.tsx.
// To make it read from MCP DB, the main app's contactsApi needs to be
// overridden to call /api/pipeline/crm/contacts instead of /api/contacts/.
// This requires either:
// (a) A prop on ContactsPage to override the API base URL
// (b) An environment/context switch that ContactsPage reads
// (c) Wrapping ContactsPage and intercepting fetch calls

export {}
