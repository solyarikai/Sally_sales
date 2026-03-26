import { createContext } from 'react'

// Stub filters — AG Grid handles column filters natively
export const ContactsFilterContext = createContext<any>({})

export function CampaignColumnFilter() { return null }
export function StatusColumnFilter() { return null }
export function DateColumnFilter() { return null }
export function SegmentColumnFilter() { return null }
export function SourceColumnFilter() { return null }
export function RepliedColumnFilter() { return null }
export function GeoColumnFilter() { return null }
export function ReplyCategoryColumnFilter() { return null }
