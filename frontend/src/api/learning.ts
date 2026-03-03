import { api } from './client';

// --- Types ---

export interface ICPEntry {
  id: number;
  key: string;
  title: string | null;
  value: any;
  source: string;
  updated_at: string | null;
}

export interface TemplateData {
  id: number;
  name: string;
  prompt_text: string;
  version: number;
  usage_count: number;
  last_used_at: string | null;
}

export interface LearningLogSummary {
  id: number;
  trigger: string;
  status: string;
  change_type: string | null;
  change_summary: string | null;
  conversations_analyzed: number | null;
  qualified_count?: number | null;
  conversations_email?: number | null;
  conversations_linkedin?: number | null;
  tokens_used?: number | null;
  cost_usd?: number | null;
  feedback_text?: string | null;
  created_at: string | null;
}

export interface LearningLogDetail extends LearningLogSummary {
  before_snapshot: any;
  after_snapshot: any;
  ai_reasoning: string | null;
  error_message: string | null;
  template_id: number | null;
}

export interface SetupWarning {
  field: string;
  message: string;
}

export interface LearningOverview {
  project_id: number;
  project_name: string;
  icp: ICPEntry[];
  template: TemplateData | null;
  recent_logs: LearningLogSummary[];
  corrections: { total: number; edited: number };
  setup_warnings?: SetupWarning[];
}

export interface TemplatesResponse {
  active_template_id: number | null;
  templates: Array<TemplateData & {
    prompt_type: string | null;
    is_default: boolean;
    created_at: string | null;
  }>;
  category_stats: Record<string, number>;
}

export interface AnalyzeResponse {
  learning_log_id: number;
  status: string;
  message: string;
}

export interface AnalyzeStatusResponse {
  id: number;
  status: string;
  change_summary: string | null;
  conversations_analyzed: number | null;
  error_message: string | null;
  can_force?: boolean;
  qualified_count?: number;
}

export interface LogsPage {
  items: LearningLogSummary[];
  total: number;
  page: number;
  page_size: number;
}

// --- API functions ---

export async function getLearningOverview(projectId: number): Promise<LearningOverview> {
  const response = await api.get(`/projects/${projectId}/learning/overview`);
  return response.data;
}

export async function getLearningLogs(projectId: number, page = 1, pageSize = 20): Promise<LogsPage> {
  const response = await api.get(`/projects/${projectId}/learning/logs`, {
    params: { page, page_size: pageSize },
  });
  return response.data;
}

export async function getLearningLogDetail(projectId: number, logId: number): Promise<LearningLogDetail> {
  const response = await api.get(`/projects/${projectId}/learning/logs/${logId}`);
  return response.data;
}

export async function getLearningTemplates(projectId: number): Promise<TemplatesResponse> {
  const response = await api.get(`/projects/${projectId}/learning/templates`);
  return response.data;
}

export async function triggerLearning(
  projectId: number,
  maxConversations = 100,
  forceAll = false,
): Promise<AnalyzeResponse> {
  const response = await api.post(`/projects/${projectId}/learning/analyze`, {
    max_conversations: maxConversations,
    force_all: forceAll,
  });
  return response.data;
}

export async function getLearningStatus(projectId: number, logId: number): Promise<AnalyzeStatusResponse> {
  const response = await api.get(`/projects/${projectId}/learning/analyze/${logId}/status`);
  return response.data;
}

export interface OperatorCorrection {
  id: number;
  action_type: string;
  was_edited: boolean;
  reply_category: string | null;
  channel: string | null;
  lead_company: string | null;
  lead_email: string | null;
  campaign_name: string | null;
  ai_draft_preview: string;
  ai_draft_full: string | null;
  sent_preview: string;
  sent_full: string | null;
  ai_draft_subject: string | null;
  sent_subject: string | null;
  created_at: string | null;
}

export interface CorrectionsPage {
  items: OperatorCorrection[];
  total: number;
  page: number;
  page_size: number;
}

export async function getOperatorCorrections(
  projectId: number, page = 1, pageSize = 30, actionType?: string
): Promise<CorrectionsPage> {
  const response = await api.get(`/projects/${projectId}/learning/corrections`, {
    params: { page, page_size: pageSize, ...(actionType ? { action_type: actionType } : {}) },
  });
  return response.data;
}

export async function submitFeedback(projectId: number, feedbackText: string): Promise<AnalyzeResponse> {
  const response = await api.post(`/projects/${projectId}/learning/feedback`, {
    feedback_text: feedbackText,
  });
  return response.data;
}
