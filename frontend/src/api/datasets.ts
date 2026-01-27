import api from './client';
import type { Dataset, DataRowsPage, Folder } from '../types';

export interface DatasetListResponse {
  datasets: Dataset[];
  total: number;
}

export const foldersApi = {
  list: async (): Promise<Folder[]> => {
    const response = await api.get('/folders');
    return response.data;
  },

  create: async (name: string, parentId?: number): Promise<Folder> => {
    const response = await api.post('/folders', { name, parent_id: parentId });
    return response.data;
  },

  update: async (id: number, data: { name?: string; parent_id?: number }): Promise<Folder> => {
    const response = await api.patch(`/folders/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/folders/${id}`);
  },
};

export const datasetsApi = {
  list: async (skip = 0, limit = 50): Promise<DatasetListResponse> => {
    const response = await api.get('/datasets', { params: { skip, limit } });
    return response.data;
  },

  get: async (id: number): Promise<Dataset> => {
    const response = await api.get(`/datasets/${id}`);
    return response.data;
  },

  uploadCsv: async (file: File, name?: string): Promise<Dataset> => {
    const formData = new FormData();
    formData.append('file', file);
    if (name) {
      formData.append('name', name);
    }
    const response = await api.post('/datasets/upload-csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  importGoogleSheets: async (url: string, name?: string): Promise<Dataset> => {
    const response = await api.post('/datasets/import-google-sheets', { url, name });
    return response.data;
  },

  getRows: async (
    datasetId: number,
    page = 1,
    pageSize = 50,
    statusFilter?: string
  ): Promise<DataRowsPage> => {
    const response = await api.get(`/datasets/${datasetId}/rows`, {
      params: { page, page_size: pageSize, status_filter: statusFilter },
    });
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/datasets/${id}`);
  },

  rename: async (id: number, name: string): Promise<void> => {
    await api.patch(`/datasets/${id}/rename`, null, { params: { name } });
  },

  deleteRows: async (datasetId: number, rowIds: number[]): Promise<void> => {
    // Convert array to repeated params for FastAPI
    const params = new URLSearchParams();
    rowIds.forEach(id => params.append('row_ids', id.toString()));
    await api.delete(`/datasets/${datasetId}/rows?${params.toString()}`);
  },

  renameColumn: async (datasetId: number, oldName: string, newName: string): Promise<void> => {
    await api.patch(`/datasets/${datasetId}/rename-column`, null, { 
      params: { old_name: oldName, new_name: newName } 
    });
  },

  deleteColumn: async (datasetId: number, columnName: string, isEnriched: boolean): Promise<void> => {
    await api.delete(`/datasets/${datasetId}/columns/${encodeURIComponent(columnName)}`, {
      params: { is_enriched: isEnriched }
    });
  },

  update: async (id: number, data: { name?: string; description?: string; folder_id?: number }): Promise<Dataset> => {
    const response = await api.patch(`/datasets/${id}`, data);
    return response.data;
  },

  markRowsExported: async (
    datasetId: number, 
    rowIds: number[], 
    columnName: string, 
    exportTarget: string
  ): Promise<{ success: boolean; rows_marked: number; column_name: string }> => {
    const response = await api.post(
      `/datasets/${datasetId}/mark-exported`,
      rowIds,
      { params: { column_name: columnName, export_target: exportTarget } }
    );
    return response.data;
  },
};
