// API Client for MRP System

import { APIResponse, APIError } from '@/types/api';

export class APIClient {
  private baseURL: string;
  private tokenRefreshPromise: Promise<string> | null = null;

  constructor(baseURL = 'http://localhost:8000/api/v1') {
    this.baseURL = baseURL;
  }

  private getAuthHeaders(): Record<string, string> {
    const token = this.getAccessToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  private getAccessToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('access_token');
  }

  private getRefreshToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('refresh_token');
  }

  private setTokens(accessToken: string, refreshToken?: string): void {
    if (typeof window === 'undefined') return;
    localStorage.setItem('access_token', accessToken);
    if (refreshToken) {
      localStorage.setItem('refresh_token', refreshToken);
    }
  }

  private clearTokens(): void {
    if (typeof window === 'undefined') return;
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
  }

  private async refreshAccessToken(): Promise<string> {
    if (this.tokenRefreshPromise) {
      return this.tokenRefreshPromise;
    }

    this.tokenRefreshPromise = this.performTokenRefresh();
    
    try {
      const newToken = await this.tokenRefreshPromise;
      return newToken;
    } finally {
      this.tokenRefreshPromise = null;
    }
  }

  private async performTokenRefresh(): Promise<string> {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await fetch(`${this.baseURL}/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${refreshToken}`,
      },
    });

    const data = await response.json();

    if (!response.ok) {
      this.clearTokens();
      throw new APIError(data, response.status);
    }

    this.setTokens(data.data.access_token);
    return data.data.access_token;
  }

  async request<T>(endpoint: string, options: RequestInit = {}): Promise<APIResponse<T>> {
    const url = `${this.baseURL}${endpoint}`;
    
    let headers = {
      'Content-Type': 'application/json',
      ...this.getAuthHeaders(),
      ...options.headers,
    };

    let response = await fetch(url, {
      ...options,
      headers,
    });

    // If unauthorized and we have a refresh token, try to refresh and retry
    if (response.status === 401 && this.getRefreshToken()) {
      try {
        const newToken = await this.refreshAccessToken();
        headers = {
          ...headers,
          Authorization: `Bearer ${newToken}`,
        };

        response = await fetch(url, {
          ...options,
          headers,
        });
      } catch (refreshError) {
        // Refresh failed, clear tokens and throw the original error
        this.clearTokens();
      }
    }

    const data = await response.json();

    if (!response.ok) {
      throw new APIError(data, response.status);
    }

    // Backend returns different formats, normalize to frontend expectation
    if ((data.status === 'success' && !data.data) || (data.items && !data.status)) {
      // Backend format: { items: [...], pagination: {...}, status: "success" }
      // OR: { items: [...], total_count: N } (inventory items)
      // Transform to: { status: "success", data: { items: [...], total: ..., page: ... } }
      const { items, pagination, total_count, status, message, timestamp, ...rest } = data;
      
      if (items) {
        // Normalize field names for compatibility
        const normalizedItems = items.map((item: any) => {
          const normalized = { ...item };
          
          // Warehouse field normalization (top-level)
          if (item.warehouse_id && !item.inventory_item_id) {
            normalized.id = item.warehouse_id;
            normalized.code = item.warehouse_code;
            normalized.name = item.warehouse_name;
            normalized.type = item.warehouse_type;
          }
          
          // Product field normalization (top-level)
          if (item.product_id && !item.inventory_item_id) {
            normalized.id = item.product_id;
            normalized.code = item.product_code;
            normalized.name = item.product_name;
            normalized.category = item.product_type;
          }
          
          // Inventory item field normalization
          if (item.inventory_item_id) {
            normalized.id = item.inventory_item_id;
            normalized.available_quantity = parseFloat(item.quantity_in_stock || 0) - parseFloat(item.reserved_quantity || 0);
            normalized.total_cost = parseFloat(item.quantity_in_stock || 0) * parseFloat(item.unit_cost || 0);
            
            // Normalize nested product object
            if (item.product) {
              normalized.product = {
                ...item.product,
                id: item.product.product_id,
                code: item.product.product_code,
                name: item.product.product_name,
                category: item.product.product_type,
              };
            }
            
            // Normalize nested warehouse object
            if (item.warehouse) {
              normalized.warehouse = {
                ...item.warehouse,
                id: item.warehouse.warehouse_id,
                code: item.warehouse.warehouse_code,
                name: item.warehouse.warehouse_name,
                type: item.warehouse.warehouse_type,
              };
            }
          }
          
          return normalized;
        });

        if (pagination) {
          // Full pagination response (warehouses, products, etc.)
          return {
            status,
            data: {
              items: normalizedItems,
              total: pagination.total_count,
              page: pagination.page,
              page_size: pagination.page_size,
              total_pages: pagination.total_pages,
              has_next: pagination.has_next,
              has_previous: pagination.has_previous,
            },
            message,
            timestamp
          };
        } else if (total_count !== undefined) {
          // Simple pagination response (inventory items)
          return {
            status: status || 'success',
            data: {
              items: normalizedItems,
              total: total_count,
              page: 1,
              page_size: normalizedItems.length,
              total_pages: 1,
              has_next: false,
              has_previous: false,
            },
            message: message || 'Data retrieved successfully',
            timestamp: timestamp || new Date().toISOString()
          };
        }
      } else {
        // Single item or other response
        return {
          status,
          data: rest,
          message,
          timestamp
        };
      }
    }

    return data;
  }

  // Convenience methods
  async get<T>(endpoint: string, params?: Record<string, any>): Promise<APIResponse<T>> {
    if (params) {
      // Filter out undefined values to avoid sending "undefined" as string
      const filteredParams = Object.entries(params)
        .filter(([_, value]) => value !== undefined && value !== null && value !== '')
        .reduce((acc, [key, value]) => ({ ...acc, [key]: value }), {});
      
      const queryString = new URLSearchParams(filteredParams).toString();
      const url = queryString ? `${endpoint}?${queryString}` : endpoint;
      return this.request<T>(url);
    }
    return this.request<T>(endpoint);
  }

  async post<T>(endpoint: string, body?: any): Promise<APIResponse<T>> {
    // Transform frontend field names to backend field names for creation
    let transformedBody = body;
    if (body && endpoint.includes('/master-data/products')) {
      // Check if body already has backend field names (product_code, product_name, product_type)
      // If so, use as-is. Otherwise, transform from frontend field names.
      if (body.product_code && body.product_name && body.product_type) {
        // Body already has correct backend field names
        transformedBody = body;
      } else {
        // Transform from frontend field names
        transformedBody = {
          product_code: body.code,
          product_name: body.name,
          product_type: body.category,
          unit_of_measure: body.unit_of_measure,
          minimum_stock_level: body.minimum_stock_level,
          critical_stock_level: body.critical_stock_level,
          description: body.description,
        };
      }
    } else if (body && endpoint.includes('/master-data/warehouses')) {
      transformedBody = {
        warehouse_code: body.code,
        warehouse_name: body.name,
        warehouse_type: body.type,
        location: body.location,
      };
    } else if (body && endpoint.includes('/master-data/suppliers')) {
      // Transform supplier field names from frontend to backend
      // Note: tax_number is excluded as it's not in the actual database model
      transformedBody = {
        supplier_code: body.code,
        supplier_name: body.name,
        contact_person: body.contact_person,
        email: body.email,
        phone: body.phone,
        address: body.address,
        payment_terms: body.payment_terms,
      };
    }
    
    return this.request<T>(endpoint, {
      method: 'POST',
      body: transformedBody ? JSON.stringify(transformedBody) : undefined,
    });
  }

  async put<T>(endpoint: string, body?: any): Promise<APIResponse<T>> {
    // Transform frontend field names to backend field names for updates
    let transformedBody = body;
    if (body && endpoint.includes('/master-data/products')) {
      // Check if body already has backend field names (product_name, product_type)
      // If so, use as-is. Otherwise, transform from frontend field names.
      if (body.product_name && body.product_type) {
        // Body already has correct backend field names
        transformedBody = body;
      } else {
        // Transform from frontend field names
        transformedBody = {
          product_code: body.code,
          product_name: body.name,
          product_type: body.category,
          unit_of_measure: body.unit_of_measure,
          minimum_stock_level: body.minimum_stock_level,
          critical_stock_level: body.critical_stock_level,
          description: body.description,
        };
      }
    } else if (body && endpoint.includes('/master-data/warehouses')) {
      transformedBody = {
        warehouse_code: body.code,
        warehouse_name: body.name,
        warehouse_type: body.type,
        location: body.location,
      };
    } else if (body && endpoint.includes('/master-data/suppliers')) {
      // Transform supplier field names from frontend to backend
      // Note: tax_number is excluded as it's not in the actual database model
      transformedBody = {
        supplier_code: body.code,
        supplier_name: body.name,
        contact_person: body.contact_person,
        email: body.email,
        phone: body.phone,
        address: body.address,
        payment_terms: body.payment_terms,
      };
    }
    
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: transformedBody ? JSON.stringify(transformedBody) : undefined,
    });
  }

  async patch<T>(endpoint: string, body?: any): Promise<APIResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'PATCH',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  async delete<T>(endpoint: string): Promise<APIResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'DELETE',
    });
  }

  // Auth methods
  async login(username: string, password: string) {
    // Login endpoint returns data directly, not wrapped in APIResponse
    const url = `${this.baseURL}/auth/login`;
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new APIError({ status: 'error', message: data.detail || 'Login failed' }, response.status);
    }

    // Store tokens and user data
    this.setTokens(data.access_token, data.refresh_token);
    if (typeof window !== 'undefined') {
      // Backend returns user_info, normalize to user for frontend
      const userData = data.user_info || data.user;
      localStorage.setItem('user', JSON.stringify(userData));
    }

    // Return in expected APIResponse format
    return {
      status: 'success' as const,
      data: {
        ...data,
        user: data.user_info || data.user
      }
    };
  }

  logout() {
    this.clearTokens();
  }

  getCurrentUser() {
    if (typeof window === 'undefined') return null;
    const userStr = localStorage.getItem('user');
    return userStr ? JSON.parse(userStr) : null;
  }

  isAuthenticated(): boolean {
    return !!this.getAccessToken();
  }
}

// Export singleton instance
export const apiClient = new APIClient();