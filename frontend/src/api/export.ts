import api from './client';

export interface ExportRequest {
  format: 'csv' | 'instantly' | 'getsales';
  include_enriched?: boolean;
  selected_row_ids?: number[];
  email_column?: string;
  first_name_column?: string;
  last_name_column?: string;
  company_column?: string;
  linkedin_url_column?: string;
  message_column?: string;
  custom_columns?: Record<string, string>;
}

export interface ExportPreview {
  columns: string[];
  original_columns: string[];
  rows: Record<string, any>[];
  total_rows: number;
}

export const exportApi = {
  downloadCsv: async (datasetId: number, request: ExportRequest): Promise<Blob> => {
    const response = await api.post(`/export/${datasetId}/csv`, request, {
      responseType: 'blob',
    });
    return response.data;
  },

  preview: async (datasetId: number, format = 'csv', limit = 5): Promise<ExportPreview> => {
    const response = await api.get(`/export/${datasetId}/preview`, {
      params: { format, limit },
    });
    return response.data;
  },

  exportToGoogleSheets: async (
    datasetId: number,
    spreadsheetUrl: string,
    sheetName?: string,
    includeEnriched = true,
    selectedRowIds?: number[]
  ) => {
    const response = await api.post(`/export/${datasetId}/google-sheets`, {
      spreadsheet_url: spreadsheetUrl,
      sheet_name: sheetName,
      include_enriched: includeEnriched,
      selected_row_ids: selectedRowIds,
    });
    return response.data;
  },
};
