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
export type ProductType = 'RAW_MATERIAL' | 'SEMI_FINISHED' | 'FINISHED_PRODUCT' | 'PACKAGING';
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
  product_code: string;
  product_name: string;
  description?: string;
  product_type: ProductType;
  unit_of_measure: string;
  minimum_stock_level?: number;
  critical_stock_level?: number;
  standard_cost?: number;
  specifications?: string;
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
  supplier_id?: number;
  id: number;
  supplier_code?: string;
  code: string;
  supplier_name?: string;
  name: string;
  contact_person?: string;
  email?: string;
  phone?: string;
  address?: string;
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
    // Compatibility fields
    code?: string;
    name?: string;
    category?: ProductCategory;
    minimum_stock_level?: number;
    critical_stock_level?: number;
  };
  warehouse?: {
    warehouse_id: number;
    warehouse_code: string;
    warehouse_name: string;
    warehouse_type: string;
    // Compatibility fields
    code?: string;
    name?: string;
    type?: WarehouseType;
    location?: string;
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
  status: string;
  message: string;
  data: {
    quantity_removed: number;
    total_cost: number;
    batches_affected: number;
    fifo_breakdown: {
      quantity: number;
      unit_cost: number;
      batch_cost: number;
    }[];
  };
  timestamp: string;
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

// BOM (Bill of Materials) Types
export interface BOMItem {
  bom_item_id: number;
  bom_id: number;
  product_id: number;
  quantity: number;
  unit_cost?: number;
  total_cost?: number;
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
}

export interface BOM {
  bom_id: number;
  id?: number; // For compatibility
  product_id: number;
  bom_code: string;
  code?: string; // For compatibility
  bom_name: string;
  name?: string; // For compatibility
  description?: string;
  version: string;
  total_cost?: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  
  // Related objects
  product?: {
    product_id: number;
    product_code: string;
    product_name: string;
    product_type: string;
    unit_of_measure: string;
  };
  bom_items?: BOMItem[];
}

export interface CreateBOMRequest {
  product_id: number;
  bom_code: string;
  bom_name: string;
  description?: string;
  version: string;
  bom_items: {
    product_id: number;
    quantity: number;
    notes?: string;
  }[];
}

export interface UpdateBOMRequest {
  bom_code?: string;
  bom_name?: string;
  description?: string;
  version?: string;
  bom_items?: {
    product_id: number;
    quantity: number;
    notes?: string;
  }[];
}

// FIFO batch information
export interface FifoBatch {
  batch_number: string;
  quantity_used: number;
  unit_cost: number;
  entry_date: string;
}

// Individual component cost details
export interface ComponentCost {
  product_id: number;
  product_name: string;
  product_code: string;
  quantity_required: number;
  quantity_available: number;
  unit_cost: number;
  total_cost: number;
  has_sufficient_stock: boolean;
  fifo_batches: FifoBatch[];
}

// Missing component information
export interface MissingComponent {
  product_id: number;
  product_name: string;
  product_code: string;
  quantity_required: number;
  quantity_available: number;
  quantity_missing: number;
}

// Enhanced BOM cost calculation response (matches backend)
export interface BOMCostCalculation {
  bom_id: number;
  quantity: number;
  calculable: boolean;
  total_material_cost: number;
  component_costs: ComponentCost[];
  missing_components: MissingComponent[];
  calculation_date: string;
  cost_basis: string;
  components_with_stock: number;
  components_missing_stock: number;
  stock_coverage_percentage: number;
}

// Legacy cost calculation schema (kept for backward compatibility)
export interface LegacyBOMCostCalculation {
  bom_id: number;
  total_cost: number;
  detailed_costs: {
    bom_item_id: number;
    product_id: number;
    product_name: string;
    quantity: number;
    unit_cost: number;
    total_cost: number;
  }[];
}

// Production Order Types
export type ProductionOrderStatus = 'PLANNED' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED';

export interface ProductionOrder {
  production_order_id: number;
  id?: number; // For compatibility
  order_number: string;
  bom_id: number;
  product_id: number;
  quantity_to_produce: number;
  quantity_produced?: number;
  status: ProductionOrderStatus;
  priority?: string;
  planned_start_date?: string;
  planned_end_date?: string;
  actual_start_date?: string;
  actual_end_date?: string;
  notes?: string;
  created_by: number;
  created_at: string;
  updated_at: string;
  
  // Related objects
  bom?: {
    bom_id: number;
    bom_code: string;
    bom_name: string;
    version: string;
  };
  product?: {
    product_id: number;
    product_code: string;
    product_name: string;
    product_type: string;
    unit_of_measure: string;
  };
  created_by_user?: {
    user_id: number;
    username: string;
    full_name: string;
  };
}

export interface ProductionOrderItem {
  product_id: number;
  bom_id: number;
  planned_quantity: number;
}

export interface CreateProductionOrderRequest {
  product_id: number;
  bom_id: number;
  warehouse_id: number;
  planned_quantity: number;
  priority?: number;
  planned_start_date?: string;
  planned_completion_date?: string;
  notes?: string;
}

// Multiple products in single production order
export interface CreateMultipleProductionOrderRequest {
  warehouse_id: number;
  products: ProductionOrderItem[];
  priority?: number;
  planned_start_date?: string;
  planned_completion_date?: string;
  notes?: string;
  auto_create_missing?: boolean;
}

// Enhanced production order creation with analysis
export interface CreateProductionOrderWithAnalysisRequest {
  product_id: number;
  bom_id: number;
  warehouse_id: number;
  planned_quantity: number;
  priority?: number;
  planned_start_date?: string;
  planned_completion_date?: string;
  notes?: string;
  auto_create_missing?: boolean; // Whether to create nested orders for missing semi-products
}

export interface UpdateProductionOrderRequest {
  quantity_to_produce?: number;
  status?: ProductionOrderStatus;
  priority?: string;
  planned_start_date?: string;
  planned_end_date?: string;
  actual_start_date?: string;
  actual_end_date?: string;
  notes?: string;
}

export interface BOMFilters {
  page?: number;
  page_size?: number;
  search?: string;
  product_id?: number;
  is_active?: boolean;
}

export interface ProductionOrderFilters {
  page?: number;
  page_size?: number;
  search?: string;
  status?: ProductionOrderStatus;
  bom_id?: number;
  product_id?: number;
  created_by?: number;
}

// Advanced MRP Types

// Stock Analysis for Production Orders
export interface StockAnalysisItem {
  product_id: number;
  product_code: string;
  product_name: string;
  required_quantity: number;
  available_quantity: number;
  sufficient_stock: boolean;
  shortage_quantity?: number;
  unit_cost?: number;
  total_cost?: number;
  product_type: string;
  is_semi_finished?: boolean;
}

export interface ProductionOrderStockAnalysis {
  production_order_id?: number;
  bom_id: number;
  bom_name: string;
  quantity_to_produce: number;
  warehouse_id: number;
  warehouse_name: string;
  analysis_items: StockAnalysisItem[];
  can_produce: boolean;
  missing_materials: StockAnalysisItem[];
  total_material_cost: number;
  analysis_date: string;
  // Enhanced validation fields from backend
  shortage_type?: 'RAW_MATERIALS' | 'SEMI_FINISHED' | 'MIXED';
  can_create?: boolean;
  must_add_stock?: boolean;
  production_guidance?: {
    can_create_order: boolean;
    can_create_with_dependencies: boolean;
    must_add_stock: boolean;
    shortage_summary: {
      raw_materials: number;
      semi_finished: number;
      total_shortages: number;
    };
    recommendations: string[];
  };
  auto_create_available?: boolean;
}

// Component-level progress tracking
export type ComponentStatus = 'PENDING' | 'ALLOCATED' | 'CONSUMED' | 'COMPLETED';

export interface ProductionOrderComponent {
  component_id: number;
  production_order_id: number;
  product_id: number;
  product_code: string;
  product_name: string;
  required_quantity: number;
  allocated_quantity: number;
  consumed_quantity: number;
  status: ComponentStatus;
  unit_cost?: number;
  total_cost?: number;
  notes?: string;
  updated_at: string;
}

export interface UpdateComponentStatusRequest {
  component_id: number;
  status: ComponentStatus;
  consumed_quantity?: number;
  notes?: string;
}

// Stock Reservation Management
export interface StockReservation {
  reservation_id: number;
  production_order_id: number;
  product_id: number;
  product_code: string;
  product_name: string;
  reserved_quantity: number;
  warehouse_id: number;
  warehouse_name: string;
  reservation_date: string;
  status: 'ACTIVE' | 'CONSUMED' | 'RELEASED';
  expiry_date?: string;
  batch_number?: string;
  unit_cost?: number;
}

// Production Tree Structure
export interface ProductionTreeNode {
  production_order_id: number;
  order_number: string;
  product_id: number;
  product_code: string;
  product_name: string;
  quantity_to_produce: number;
  status: ProductionOrderStatus;
  level: number;
  parent_order_id?: number;
  children: ProductionTreeNode[];
  dependencies?: ProductionTreeNode[];
}

// Enhanced Production Order with advanced features
export interface EnhancedProductionOrder extends ProductionOrder {
  components?: ProductionOrderComponent[];
  stock_reservations?: StockReservation[];
  nested_orders?: ProductionOrder[];
  production_tree?: ProductionTreeNode;
  warehouse?: {
    warehouse_id: number;
    warehouse_code: string;
    warehouse_name: string;
    warehouse_type: string;
  };
  completion_percentage?: number;
  estimated_cost?: number;
  actual_cost?: number;
}

// Advanced production order creation response
export interface CreateProductionOrderWithAnalysisResponse {
  production_order: EnhancedProductionOrder;
  stock_analysis: ProductionOrderStockAnalysis;
  nested_orders_created?: ProductionOrder[];
  warnings?: string[];
  suggestions?: string[];
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