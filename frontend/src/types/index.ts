export type EnrichmentStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'skipped' | 'cancelled';

// ============ User & Company Types ============

export interface User {
  id: number;
  email: string | null;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface Environment {
  id: number;
  user_id: number;
  name: string;
  description: string | null;
  color: string | null;
  icon: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface EnvironmentWithStats extends Environment {
  companies_count: number;
}

export interface Company {
  id: number;
  user_id: number;
  environment_id: number | null;
  name: string;
  description: string | null;
  website: string | null;
  logo_url: string | null;
  color: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface CompanyWithStats extends Company {
  prospects_count: number;
  datasets_count: number;
  documents_count: number;
}

export interface CurrentUserResponse {
  user: User;
  environments: Environment[];
  companies: Company[];
}

export interface Folder {
  id: number;
  name: string;
  parent_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface Dataset {
  id: number;
  name: string;
  description: string | null;
  source_type: 'csv' | 'google_sheets';
  source_url: string | null;
  original_filename: string | null;
  columns: string[];
  row_count: number;
  folder_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface DataRow {
  id: number;
  dataset_id: number;
  row_index: number;
  data: Record<string, any>;
  enriched_data: Record<string, any>;
  enrichment_status: EnrichmentStatus;
  last_enriched_at: string | null;
  error_message: string | null;
}

export interface DataRowsPage {
  rows: DataRow[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface PromptTemplate {
  id: number;
  name: string;
  description: string | null;
  category: string | null;
  tags: string[];
  prompt_template: string;
  output_column: string;
  system_prompt: string | null;
  is_system: boolean;
  created_at: string;
  updated_at: string;
}

export interface EnrichmentJob {
  id: number;
  dataset_id: number;
  prompt_template_id: number | null;
  custom_prompt: string | null;
  output_column: string;
  model: string;
  selected_row_ids: number[] | null;
  status: EnrichmentStatus;
  total_rows: number;
  processed_rows: number;
  failed_rows: number;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  created_at: string;
}

export interface OpenAISettings {
  has_api_key: boolean;
  default_model: string;
  available_models: string[];
}

export interface EnrichmentPreviewResult {
  row_id: number;
  success: boolean;
  result?: string;
  error?: string;
  tokens_used: number;
}

export interface EnrichmentPreviewResponse {
  results: EnrichmentPreviewResult[];
  model_used: string;
  tokens_used: number;
}
