import api from './client';
import type { Company, CompanyWithStats, CurrentUserResponse } from '../types';

export interface CompanyCreate {
  name: string;
  description?: string;
  website?: string;
  logo_url?: string;
  color?: string;
  environment_id?: number;
}

export interface CompanyUpdate {
  name?: string;
  description?: string;
  website?: string;
  logo_url?: string;
  color?: string;
  environment_id?: number | null;  // null to remove from environment
}

/**
 * Get current user info with their companies
 */
export async function getCurrentUser(): Promise<CurrentUserResponse> {
  const response = await api.get('/companies/me');
  return response.data;
}

/**
 * List all companies for the current user
 */
export async function listCompanies(): Promise<CompanyWithStats[]> {
  const response = await api.get('/companies');
  return response.data;
}

/**
 * Get a single company by ID
 */
export async function getCompany(id: number): Promise<CompanyWithStats> {
  const response = await api.get(`/companies/${id}`);
  return response.data;
}

/**
 * Create a new company
 */
export async function createCompany(data: CompanyCreate): Promise<Company> {
  const response = await api.post('/companies', data);
  return response.data;
}

/**
 * Update a company
 */
export async function updateCompany(id: number, data: CompanyUpdate): Promise<Company> {
  const response = await api.put(`/companies/${id}`, data);
  return response.data;
}

/**
 * Delete a company (soft delete)
 */
export async function deleteCompany(id: number): Promise<{ message: string }> {
  const response = await api.delete(`/companies/${id}`);
  return response.data;
}

/**
 * Get activity logs for a company
 */
export async function getCompanyActivity(
  companyId: number,
  limit: number = 50,
  offset: number = 0
): Promise<Array<{
  id: number;
  action: string;
  entity_type: string | null;
  entity_id: number | null;
  details: Record<string, any> | null;
  created_at: string;
}>> {
  const response = await api.get(`/companies/${companyId}/activity`, {
    params: { limit, offset },
  });
  return response.data;
}

/**
 * Fetch and set company favicon from website
 */
export async function fetchCompanyFavicon(id: number): Promise<Company> {
  const response = await api.post(`/companies/${id}/fetch-favicon`);
  return response.data;
}
