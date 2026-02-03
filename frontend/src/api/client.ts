import axios from 'axios';
import { useAppStore } from '../store/appStore';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

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
  
  // CRM is cross-company (unified view)
  if (url.startsWith('/contacts') || url.startsWith('/crm-sync')) {
    return true;
  }
  
  // Data search is user-level (not company-scoped)
  if (url.startsWith('/data-search')) {
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

// Response interceptor with improved error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Extract user-friendly error message
    let userMessage = 'An unexpected error occurred';
    let technicalDetails = '';
    
    if (error.response) {
      // Server responded with error status
      const status = error.response.status;
      const data = error.response.data;
      
      // Extract message from various response formats
      if (data?.detail) {
        userMessage = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      } else if (data?.message) {
        userMessage = data.message;
      } else if (data?.error) {
        userMessage = data.error;
      }
      
      // Map status codes to user-friendly messages
      if (status === 401) {
        userMessage = 'Please log in to continue';
      } else if (status === 403) {
        userMessage = 'You do not have permission to perform this action';
      } else if (status === 404) {
        userMessage = userMessage === 'An unexpected error occurred' ? 'The requested resource was not found' : userMessage;
      } else if (status === 422) {
        userMessage = 'Please check your input and try again';
        if (data?.detail && Array.isArray(data.detail)) {
          technicalDetails = data.detail.map((d: any) => d.msg || d.message).join(', ');
        }
      } else if (status >= 500) {
        userMessage = 'Server error. Please try again later';
      }
      
      technicalDetails = technicalDetails || `Status: ${status}`;
    } else if (error.request) {
      // Request made but no response
      userMessage = 'Unable to connect to server. Please check your internet connection';
      technicalDetails = 'No response received';
    } else {
      // Request setup error
      userMessage = 'Failed to make request';
      technicalDetails = error.message;
    }
    
    // Log to console for debugging
    console.error('API Error:', {
      message: userMessage,
      technical: technicalDetails,
      url: error.config?.url,
      method: error.config?.method,
      status: error.response?.status,
      data: error.response?.data,
    });
    
    // Attach user-friendly message to error for components to use
    error.userMessage = userMessage;
    error.technicalDetails = technicalDetails;
    
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
