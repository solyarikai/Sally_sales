import axios from 'axios';
import { useAppStore } from '../store/appStore';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Determines if a request should skip the X-Company-ID header.
 * 
 * Endpoints that don't need X-Company-ID:
 * - /environments/* - environment management (user-level)
 * - /companies/* - all company management endpoints (they verify user ownership directly)
 * - /templates - shared across companies (user-level)
 * - /settings - shared across companies (user-level)
 */
function shouldSkipCompanyHeader(url: string | undefined): boolean {
  if (!url) return false;
  
  // Environment management endpoints - user-level, not company-level
  if (url === '/environments' || url.startsWith('/environments/')) {
    return true;
  }
  
  // All company management endpoints - they verify user ownership directly
  // Includes: /companies, /companies/me, /companies/{id}, /companies/{id}/activity
  if (url === '/companies' || url.startsWith('/companies/')) {
    return true;
  }
  
  // Templates are shared across companies (user-level, not company-level)
  if (url.startsWith('/templates')) {
    return true;
  }
  
  // Settings/integrations are shared across companies (user-level)
  if (url.startsWith('/settings')) {
    return true;
  }
  
  // Reply automation is user-level (monitors across all campaigns)
  if (url.startsWith('/replies') || url.startsWith('/smartlead')) {
    return true;
  }
  
  return false;
}

// Request interceptor - adds X-Company-ID header
api.interceptors.request.use(
  (config) => {
    // Get current company from store
    const currentCompany = useAppStore.getState().currentCompany;
    
    // Add X-Company-ID header if company is selected and endpoint needs it
    if (currentCompany && !shouldSkipCompanyHeader(config.url)) {
      config.headers['X-Company-ID'] = currentCompany.id.toString();
    }
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

// Helper function to set company ID for a specific request
export const withCompanyId = (companyId: number) => {
  return {
    headers: {
      'X-Company-ID': companyId.toString(),
    },
  };
};

export default api;
