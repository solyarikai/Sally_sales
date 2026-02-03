/**
 * Tests for CRM Contacts API client
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the API client
vi.mock('../api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  }
}));

import { contactsApi } from '../api';

describe('ContactsAPI', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('list', () => {
    it('should call the correct endpoint', async () => {
      const { apiClient } = await import('../api/client');
      vi.mocked(apiClient.get).mockResolvedValue({
        data: { contacts: [], total: 0, page: 1, page_size: 50, total_pages: 0 }
      });

      await contactsApi.list({ page: 1, page_size: 50 });

      expect(apiClient.get).toHaveBeenCalledWith(
        '/contacts',
        expect.objectContaining({
          params: expect.objectContaining({ page: 1, page_size: 50 })
        })
      );
    });

    it('should handle filters correctly', async () => {
      const { apiClient } = await import('../api/client');
      vi.mocked(apiClient.get).mockResolvedValue({
        data: { contacts: [], total: 0, page: 1, page_size: 50, total_pages: 0 }
      });

      await contactsApi.list({ 
        page: 1, 
        page_size: 50,
        source: 'smartlead',
        has_replied: true
      });

      expect(apiClient.get).toHaveBeenCalledWith(
        '/contacts',
        expect.objectContaining({
          params: expect.objectContaining({ 
            source: 'smartlead',
            has_replied: true
          })
        })
      );
    });
  });

  describe('getStats', () => {
    it('should fetch contact statistics', async () => {
      const { apiClient } = await import('../api/client');
      vi.mocked(apiClient.get).mockResolvedValue({
        data: { total: 100, by_status: {}, by_source: {} }
      });

      const result = await contactsApi.getStats();

      expect(apiClient.get).toHaveBeenCalledWith('/contacts/stats');
      expect(result).toHaveProperty('total');
    });
  });
});

describe('Contact Types', () => {
  it('should have correct Contact interface', () => {
    // Type check - this will fail at compile time if types are wrong
    const contact = {
      id: 1,
      email: 'test@example.com',
      source: 'smartlead',
      status: 'lead',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      has_replied: false,
      campaigns: [{ name: 'Test Campaign', source: 'smartlead' }]
    };

    expect(contact.id).toBe(1);
    expect(contact.email).toBe('test@example.com');
    expect(contact.campaigns).toHaveLength(1);
  });
});
