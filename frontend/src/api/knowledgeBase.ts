import api from './client';

const BASE = '/knowledge-base';

// ============ Document Folders ============

export interface DocumentFolder {
  id: number;
  name: string;
  parent_id?: number;
  created_at: string;
}

export const getFolders = async (): Promise<DocumentFolder[]> => {
  const response = await api.get(`${BASE}/folders`);
  return response.data;
};

export const createFolder = async (data: { name: string; parent_id?: number }): Promise<DocumentFolder> => {
  const response = await api.post(`${BASE}/folders`, data);
  return response.data;
};

export const deleteFolder = async (id: number): Promise<void> => {
  await api.delete(`${BASE}/folders/${id}`);
};

// ============ Documents ============

export interface KBDocument {
  id: number;
  name: string;
  original_filename?: string;
  document_type: string;
  folder_id?: number;
  content_md?: string;
  status: string;
  error_message?: string;
  created_at: string;
  updated_at?: string;
}

export const getDocuments = async (folderId?: number): Promise<KBDocument[]> => {
  const params = folderId !== undefined ? { folder_id: folderId } : {};
  const response = await api.get(`${BASE}/documents`, { params });
  return response.data;
};

export const uploadDocument = async (
  file: File,
  name?: string,
  documentType?: string,
  folderId?: number
): Promise<KBDocument> => {
  const formData = new FormData();
  formData.append('file', file);
  if (name) formData.append('name', name);
  if (documentType) formData.append('document_type', documentType);
  if (folderId) formData.append('folder_id', String(folderId));
  
  const response = await api.post(`${BASE}/documents/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
  return response.data;
};

export const updateDocument = async (id: number, data: Partial<KBDocument>): Promise<KBDocument> => {
  const response = await api.patch(`${BASE}/documents/${id}`, data);
  return response.data;
};

export const deleteDocument = async (id: number): Promise<void> => {
  await api.delete(`${BASE}/documents/${id}`);
};

export const regenerateSummary = async (): Promise<{ summary: string; document_count: number }> => {
  const response = await api.post(`${BASE}/documents/regenerate-summary`);
  return response.data;
};

// ============ Company Profile ============

export interface CompanyProfile {
  id: number;
  name?: string;
  website?: string;
  summary?: string;
  created_at: string;
  updated_at?: string;
}

export const getCompanyProfile = async (): Promise<CompanyProfile | null> => {
  const response = await api.get(`${BASE}/company`);
  return response.data;
};

export const saveCompanyProfile = async (data: Partial<CompanyProfile>): Promise<CompanyProfile> => {
  const response = await api.put(`${BASE}/company`, data);
  return response.data;
};

// ============ Products ============

export interface Product {
  id: number;
  name: string;
  description?: string;
  features?: string[];
  pricing?: Record<string, any>;
  target_segment_ids?: number[];
  email_snippet?: string;
  is_active: boolean;
  sort_order: number;
  created_at: string;
  updated_at?: string;
}

export const getProducts = async (): Promise<Product[]> => {
  const response = await api.get(`${BASE}/products`);
  return response.data;
};

export const createProduct = async (data: Partial<Product>): Promise<Product> => {
  const response = await api.post(`${BASE}/products`, data);
  return response.data;
};

export const updateProduct = async (id: number, data: Partial<Product>): Promise<Product> => {
  const response = await api.patch(`${BASE}/products/${id}`, data);
  return response.data;
};

export const deleteProduct = async (id: number): Promise<void> => {
  await api.delete(`${BASE}/products/${id}`);
};

// ============ Segment Columns ============

export interface SegmentColumn {
  id: number;
  name: string;
  display_name: string;
  column_type: 'text' | 'number' | 'list' | 'rich_text' | 'case_select';
  is_system: boolean;
  is_required: boolean;
  sort_order: number;
  options?: string[];
  created_at: string;
}

export const getSegmentColumns = async (): Promise<SegmentColumn[]> => {
  const response = await api.get(`${BASE}/segment-columns`);
  return response.data;
};

export const createSegmentColumn = async (data: Partial<SegmentColumn>): Promise<SegmentColumn> => {
  const response = await api.post(`${BASE}/segment-columns`, data);
  return response.data;
};

export const updateSegmentColumn = async (id: number, data: Partial<SegmentColumn>): Promise<SegmentColumn> => {
  const response = await api.patch(`${BASE}/segment-columns/${id}`, data);
  return response.data;
};

export const deleteSegmentColumn = async (id: number): Promise<void> => {
  await api.delete(`${BASE}/segment-columns/${id}`);
};

// ============ Segments ============

export interface Segment {
  id: number;
  name: string;
  data: Record<string, any>;
  is_active: boolean;
  sort_order: number;
  created_at: string;
  updated_at?: string;
}

export const getSegments = async (): Promise<Segment[]> => {
  const response = await api.get(`${BASE}/segments`);
  return response.data;
};

export const createSegment = async (data: Partial<Segment>): Promise<Segment> => {
  const response = await api.post(`${BASE}/segments`, data);
  return response.data;
};

export const updateSegment = async (id: number, data: Partial<Segment>): Promise<Segment> => {
  const response = await api.patch(`${BASE}/segments/${id}`, data);
  return response.data;
};

export const deleteSegment = async (id: number): Promise<void> => {
  await api.delete(`${BASE}/segments/${id}`);
};

export const importSegmentsCSV = async (file: File): Promise<CSVImportResult> => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await api.post(`${BASE}/segments/import-csv`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
  return response.data;
};

// ============ Competitors ============

export interface Competitor {
  id: number;
  name: string;
  website?: string;
  description?: string;
  their_strengths?: string[];
  their_weaknesses?: string[];
  our_advantages?: string[];
  their_positioning?: string;
  price_comparison?: string;
  notes?: string;
  created_at: string;
  updated_at?: string;
}

export const getCompetitors = async (): Promise<Competitor[]> => {
  const response = await api.get(`${BASE}/competitors`);
  return response.data;
};

export const createCompetitor = async (data: Partial<Competitor>): Promise<Competitor> => {
  const response = await api.post(`${BASE}/competitors`, data);
  return response.data;
};

export const updateCompetitor = async (id: number, data: Partial<Competitor>): Promise<Competitor> => {
  const response = await api.patch(`${BASE}/competitors/${id}`, data);
  return response.data;
};

export const deleteCompetitor = async (id: number): Promise<void> => {
  await api.delete(`${BASE}/competitors/${id}`);
};

export const importCompetitorsCSV = async (file: File): Promise<CSVImportResult> => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await api.post(`${BASE}/competitors/import-csv`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
  return response.data;
};

// ============ Case Studies ============

export interface CaseStudy {
  id: number;
  client_name: string;
  client_website?: string;
  client_industry?: string;
  client_size?: string;
  challenge?: string;
  solution?: string;
  results?: string;
  key_metrics?: Record<string, string>;
  testimonial?: string;
  testimonial_author?: string;
  testimonial_title?: string;
  email_snippet?: string;
  is_public: boolean;
  created_at: string;
  updated_at?: string;
}

export const getCaseStudies = async (): Promise<CaseStudy[]> => {
  const response = await api.get(`${BASE}/case-studies`);
  return response.data;
};

export const createCaseStudy = async (data: Partial<CaseStudy>): Promise<CaseStudy> => {
  const response = await api.post(`${BASE}/case-studies`, data);
  return response.data;
};

export const updateCaseStudy = async (id: number, data: Partial<CaseStudy>): Promise<CaseStudy> => {
  const response = await api.patch(`${BASE}/case-studies/${id}`, data);
  return response.data;
};

export const deleteCaseStudy = async (id: number): Promise<void> => {
  await api.delete(`${BASE}/case-studies/${id}`);
};

// ============ Voice Tones ============

export interface VoiceTone {
  id: number;
  name: string;
  description?: string;
  personality_traits?: string[];
  writing_style?: string;
  do_use?: string[];
  dont_use?: string[];
  example_messages?: string[];
  formality_level: number;
  emoji_usage: boolean;
  is_default: boolean;
  created_at: string;
  updated_at?: string;
}

export const getVoiceTones = async (): Promise<VoiceTone[]> => {
  const response = await api.get(`${BASE}/voice-tones`);
  return response.data;
};

export const createVoiceTone = async (data: Partial<VoiceTone>): Promise<VoiceTone> => {
  const response = await api.post(`${BASE}/voice-tones`, data);
  return response.data;
};

export const updateVoiceTone = async (id: number, data: Partial<VoiceTone>): Promise<VoiceTone> => {
  const response = await api.patch(`${BASE}/voice-tones/${id}`, data);
  return response.data;
};

export const deleteVoiceTone = async (id: number): Promise<void> => {
  await api.delete(`${BASE}/voice-tones/${id}`);
};

// ============ Booking Links ============

export interface BookingLink {
  id: number;
  name: string;
  url: string;
  when_to_use?: string;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

export const getBookingLinks = async (): Promise<BookingLink[]> => {
  const response = await api.get(`${BASE}/booking-links`);
  return response.data;
};

export const createBookingLink = async (data: Partial<BookingLink>): Promise<BookingLink> => {
  const response = await api.post(`${BASE}/booking-links`, data);
  return response.data;
};

export const updateBookingLink = async (id: number, data: Partial<BookingLink>): Promise<BookingLink> => {
  const response = await api.patch(`${BASE}/booking-links/${id}`, data);
  return response.data;
};

export const deleteBookingLink = async (id: number): Promise<void> => {
  await api.delete(`${BASE}/booking-links/${id}`);
};

// ============ Blocklist ============

export interface BlocklistEntry {
  id: number;
  domain?: string;
  email?: string;
  company_name?: string;
  reason?: string;
  created_at: string;
}

export const getBlocklist = async (): Promise<BlocklistEntry[]> => {
  const response = await api.get(`${BASE}/blocklist`);
  return response.data;
};

export const addToBlocklist = async (data: Partial<BlocklistEntry>): Promise<BlocklistEntry> => {
  const response = await api.post(`${BASE}/blocklist`, data);
  return response.data;
};

export const removeFromBlocklist = async (id: number): Promise<void> => {
  await api.delete(`${BASE}/blocklist/${id}`);
};

export const importBlocklistCSV = async (file: File): Promise<CSVImportResult> => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await api.post(`${BASE}/blocklist/import-csv`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
  return response.data;
};

// ============ Tags & Context ============

export interface KBTag {
  tag: string;
  label: string;
  description: string;
  type: 'summary' | 'company' | 'product' | 'segment' | 'voice' | 'case' | 'booking' | 'competitor' | 'document';
}

export const getAvailableTags = async (): Promise<{ tags: KBTag[] }> => {
  const response = await api.get(`${BASE}/tags`);
  return response.data;
};

// ============ Import ============

export interface CSVImportResult {
  success: boolean;
  imported_count: number;
  errors: string[];
}

export interface AIImportRequest {
  text: string;
  entity_type: string;
  save_to_db?: boolean;
  parse_multiple?: boolean;
}

export interface AIImportResponse {
  success: boolean;
  entity_type: string;
  data?: Record<string, any>;
  saved_ids?: number[];
  error?: string;
  tokens_used: number;
}

export const aiImport = async (request: AIImportRequest): Promise<AIImportResponse> => {
  const response = await api.post(`${BASE}/ai-import`, request);
  return response.data;
};

// ============ Export ============

export const exportKnowledgeBase = async () => {
  const response = await api.get(`${BASE}/export`);
  return response.data;
};
