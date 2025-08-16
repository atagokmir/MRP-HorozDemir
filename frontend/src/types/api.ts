// TypeScript interfaces matching backend API schemas

export interface APIResponse<T = any> {
  status: 'success' | 'error';
  data?: T;
  message?: string;
  error_code?: string;
  details?: any;
  timestamp?: string;
  path?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

// Authentication Types
export interface User {
  user_id: number;
  username: string;
  full_name: string;
  email: string;
  role: string;
  permissions: string[];
  is_active: boolean;
  last_login?: string;
  created_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface RefreshResponse {
  access_token: string;
  expires_in: number;
}

// Master Data Types
export type ProductCategory = 'RAW_MATERIALS' | 'SEMI_FINISHED' | 'FINISHED_PRODUCTS' | 'PACKAGING';
export type WarehouseType = 'RAW_MATERIALS' | 'SEMI_FINISHED' | 'FINISHED_PRODUCTS' | 'PACKAGING';
export type UnitOfMeasure = 'PIECES' | 'METERS' | 'KILOGRAMS' | 'LITERS' | 'BOXES';

export interface Product {
  product_id: number;
  id?: number; // For compatibility
  product_code: string;
  code?: string; // For compatibility
  product_name: string;
  name?: string; // For compatibility
  description?: string;
  product_type: ProductCategory;
  category?: ProductCategory; // For compatibility
  unit_of_measure: UnitOfMeasure;
  minimum_stock_level: number;
  critical_stock_level: number;
  standard_cost?: number;
  specifications?: any;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateProductRequest {
  code: string;
  name: string;
  description?: string;
  category: ProductCategory;
  unit_of_measure: UnitOfMeasure;
  minimum_stock_level: number;
  critical_stock_level: number;
}

export interface Warehouse {
  warehouse_id: number;
  id?: number; // For compatibility
  warehouse_code: string;
  code?: string; // For compatibility
  warehouse_name: string;
  name?: string; // For compatibility
  warehouse_type: WarehouseType;
  type?: WarehouseType; // For compatibility
  location?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateWarehouseRequest {
  code: string;
  name: string;
  type: WarehouseType;
  location?: string;
}

export interface Supplier {
  id: number;
  code: string;
  name: string;
  contact_person?: string;
  email?: string;
  phone?: string;
  address?: string;
  tax_number?: string;
  payment_terms?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateSupplierRequest {
  code: string;
  name: string;
  contact_person?: string;
  email?: string;
  phone?: string;
  address?: string;
  tax_number?: string;
  payment_terms?: string;
}

// Inventory Types
export type QualityStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'QUARANTINE';
export type MovementType = 'IN' | 'OUT' | 'ADJUSTMENT' | 'TRANSFER';

export interface InventoryItem {
  inventory_item_id: number;
  id?: number; // For compatibility
  product_id: number;
  warehouse_id: number;
  quantity_in_stock: string | number;
  reserved_quantity: string | number;
  available_quantity?: number; // Calculated
  unit_cost: string | number;
  total_cost?: number; // Calculated
  batch_number?: string;
  entry_date: string;
  expiry_date?: string;
  quality_status: QualityStatus;
  supplier_id?: number;
  notes?: string;
  created_at: string;
  updated_at: string;
  
  // Related objects (when included)
  product?: {
    product_id: number;
    product_code: string;
    product_name: string;
    product_type: string;
    unit_of_measure: string;
  };
  warehouse?: {
    warehouse_id: number;
    warehouse_code: string;
    warehouse_name: string;
    warehouse_type: string;
  };
  supplier?: Supplier;
}

export interface StockMovement {
  id: number;
  inventory_item_id: number;
  movement_type: MovementType;
  quantity: number;
  unit_cost?: number;
  reference_type?: string;
  reference_id?: string;
  notes?: string;
  movement_date: string;
  created_by: number;
  created_at: string;
}

export interface FIFOBatch {
  batch_number: string;
  available_quantity: number;
  unit_cost: number;
  entry_date: string;
}

export interface FIFOAllocation {
  inventory_item_id: number;
  batch_number: string;
  allocated_quantity: number;
  unit_cost: number;
  allocation_cost: number;
  entry_date: string;
}

export interface StockAvailabilityResponse {
  product_id: number;
  warehouse_id: number;
  total_available: number;
  fifo_batches: FIFOBatch[];
  weighted_average_cost: number;
}

export interface StockInRequest {
  product_id: number;
  warehouse_id: number;
  quantity: number;
  unit_cost: number;
  batch_number?: string;
  supplier_id?: number;
  quality_status: QualityStatus;
  entry_date?: string;
  expiry_date?: string;
  notes?: string;
}

export interface StockOutRequest {
  product_id: number;
  warehouse_id: number;
  quantity: number;
  reference_type?: string;
  reference_id?: string;
  notes?: string;
}

export interface StockOutResponse {
  total_quantity_allocated: number;
  total_cost: number;
  weighted_average_cost: number;
  fifo_allocations: FIFOAllocation[];
  remaining_batches: FIFOBatch[];
}

export interface StockAdjustmentRequest {
  product_id: number;
  warehouse_id: number;
  adjustment_quantity: number;
  reason: string;
  notes?: string;
}

// Query Parameters
export interface ProductFilters {
  page?: number;
  page_size?: number;
  search?: string;
  category?: ProductCategory;
  is_active?: boolean;
}

export interface InventoryFilters {
  page?: number;
  page_size?: number;
  product_id?: number;
  warehouse_id?: number;
  quality_status?: QualityStatus;
  search?: string;
}

export interface WarehouseFilters {
  page?: number;
  page_size?: number;
  search?: string;
  type?: WarehouseType;
  is_active?: boolean;
}

export interface SupplierFilters {
  page?: number;
  page_size?: number;
  search?: string;
  is_active?: boolean;
}

// Error Types
export class APIError extends Error {
  constructor(
    public response: APIResponse,
    public status?: number
  ) {
    super(response.message || 'API Error');
    this.name = 'APIError';
  }
}