import api from './client';
import type { Environment, EnvironmentWithStats } from '../types';

export interface EnvironmentCreate {
  name: string;
  description?: string;
  color?: string;
  icon?: string;
}

export interface EnvironmentUpdate {
  name?: string;
  description?: string;
  color?: string;
  icon?: string;
}

/**
 * List all environments for the current user
 */
export async function listEnvironments(): Promise<EnvironmentWithStats[]> {
  const response = await api.get('/environments');
  return response.data;
}

/**
 * Get a single environment by ID
 */
export async function getEnvironment(id: number): Promise<EnvironmentWithStats> {
  const response = await api.get(`/environments/${id}`);
  return response.data;
}

/**
 * Create a new environment
 */
export async function createEnvironment(data: EnvironmentCreate): Promise<Environment> {
  const response = await api.post('/environments', data);
  return response.data;
}

/**
 * Update an environment
 */
export async function updateEnvironment(id: number, data: EnvironmentUpdate): Promise<Environment> {
  const response = await api.put(`/environments/${id}`, data);
  return response.data;
}

/**
 * Delete an environment (soft delete)
 */
export async function deleteEnvironment(id: number): Promise<{ message: string }> {
  const response = await api.delete(`/environments/${id}`);
  return response.data;
}

/**
 * Get companies in an environment
 */
export async function getEnvironmentCompanies(environmentId: number): Promise<Array<{
  id: number;
  name: string;
  description: string | null;
  color: string | null;
  created_at: string;
}>> {
  const response = await api.get(`/environments/${environmentId}/companies`);
  return response.data;
}
