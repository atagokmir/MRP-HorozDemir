# Frontend Integration Guide - Horoz Demir MRP System

**Version:** 1.0.0  
**Date:** August 15, 2025  
**Backend Status:** ✅ PRODUCTION READY  
**API Server:** http://localhost:8000  

---

## Quick Start for Frontend Team

### API Server Information
- **Base URL:** `http://localhost:8000/api/v1`
- **Documentation:** `http://localhost:8000/docs` (Swagger UI)
- **Health Check:** `http://localhost:8000/health`
- **Status:** 🟢 OPERATIONAL

### Authentication Requirements
All endpoints except system endpoints require JWT authentication:
```typescript
// Required Header for Protected Endpoints
Authorization: Bearer <access_token>
```

---

## Authentication Flow

### 1. User Login
```typescript
// POST /api/v1/auth/login
const loginRequest = {
  username: "user@example.com",
  password: "password123"
};

const loginResponse = {
  status: "success",
  data: {
    access_token: "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    refresh_token: "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    token_type: "bearer",
    expires_in: 900, // 15 minutes
    user: {
      id: 1,
      username: "user@example.com",
      full_name: "John Doe",
      role: "inventory_clerk",
      permissions: ["inventory_read", "inventory_write"],
      is_active: true
    }
  }
};
```

### 2. Token Refresh
```typescript
// POST /api/v1/auth/refresh
// Headers: Authorization: Bearer <refresh_token>
const refreshResponse = {
  status: "success",
  data: {
    access_token: "new_access_token_here",
    expires_in: 900
  }
};
```

### 3. Current User Info
```typescript
// GET /api/v1/auth/me
// Headers: Authorization: Bearer <access_token>
const userInfoResponse = {
  status: "success",
  data: {
    id: 1,
    username: "user@example.com",
    full_name: "John Doe",
    role: "inventory_clerk",
    permissions: ["inventory_read", "inventory_write"],
    last_login: "2025-08-15T14:30:00Z",
    is_active: true
  }
};
```

---

## Core Data Models

### Product Model
```typescript
interface Product {
  id: number;
  code: string; // Unique product code
  name: string;
  description?: string;
  category: 'RAW_MATERIALS' | 'SEMI_FINISHED' | 'FINISHED_PRODUCTS' | 'PACKAGING';
  unit_of_measure: string; // e.g., 'PIECES', 'METERS', 'KILOGRAMS'
  minimum_stock_level: number;
  critical_stock_level: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
```

### Warehouse Model
```typescript
interface Warehouse {
  id: number;
  code: string; // Unique warehouse code
  name: string;
  type: 'RAW_MATERIALS' | 'SEMI_FINISHED' | 'FINISHED_PRODUCTS' | 'PACKAGING';
  location?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
```

### Inventory Item Model
```typescript
interface InventoryItem {
  id: number;
  product_id: number;
  warehouse_id: number;
  quantity_in_stock: number;
  reserved_quantity: number;
  available_quantity: number; // Calculated: quantity_in_stock - reserved_quantity
  unit_cost: number;
  total_cost: number; // Calculated: quantity_in_stock * unit_cost
  batch_number?: string;
  entry_date: string; // ISO 8601 format
  expiry_date?: string;
  quality_status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'QUARANTINE';
  supplier_id?: number;
  
  // Related objects (when included)
  product?: Product;
  warehouse?: Warehouse;
  supplier?: Supplier;
}
```

### Stock Movement Model
```typescript
interface StockMovement {
  id: number;
  inventory_item_id: number;
  movement_type: 'IN' | 'OUT' | 'ADJUSTMENT' | 'TRANSFER';
  quantity: number;
  unit_cost?: number;
  reference_type?: string; // e.g., 'PRODUCTION_ORDER', 'PURCHASE_ORDER'
  reference_id?: string;
  notes?: string;
  movement_date: string;
  created_by: number;
  created_at: string;
}
```

---

## Key API Endpoints for Frontend

### Product Management
```typescript
// Get Products List
GET /api/v1/master-data/products
Query Parameters:
- page?: number (default: 1)
- page_size?: number (default: 20)
- search?: string
- category?: string
- is_active?: boolean

// Create Product
POST /api/v1/master-data/products
Body: {
  code: "PROD001",
  name: "Steel Rod 10mm",
  description: "High quality steel rod",
  category: "RAW_MATERIALS",
  unit_of_measure: "METERS",
  minimum_stock_level: 100,
  critical_stock_level: 50
}

// Update Product
PUT /api/v1/master-data/products/{id}
Body: Partial<Product>
```

### Inventory Operations
```typescript
// Get Inventory Items (FIFO Ordered)
GET /api/v1/inventory/items
Query Parameters:
- product_id?: number
- warehouse_id?: number
- quality_status?: string
- page?: number
- page_size?: number

// Check Stock Availability
GET /api/v1/inventory/availability/{product_id}
Query Parameters:
- warehouse_id?: number
- required_quantity?: number

Response: {
  status: "success",
  data: {
    product_id: 1,
    warehouse_id: 1,
    total_available: 500.0,
    fifo_batches: [
      {
        batch_number: "BATCH001",
        available_quantity: 200.0,
        unit_cost: 25.50,
        entry_date: "2025-08-10T00:00:00Z"
      },
      {
        batch_number: "BATCH002", 
        available_quantity: 300.0,
        unit_cost: 26.00,
        entry_date: "2025-08-12T00:00:00Z"
      }
    ],
    weighted_average_cost: 25.78
  }
}

// Stock In Operation
POST /api/v1/inventory/stock-in
Body: {
  product_id: 1,
  warehouse_id: 1,
  quantity: 100.0,
  unit_cost: 25.50,
  batch_number: "BATCH001",
  supplier_id: 1,
  quality_status: "APPROVED"
}

// Stock Out Operation (FIFO)
POST /api/v1/inventory/stock-out
Body: {
  product_id: 1,
  warehouse_id: 1,
  quantity: 50.0,
  reference_type: "PRODUCTION_ORDER",
  reference_id: "PO2025001",
  notes: "Production allocation"
}
```

---

## FIFO Logic Integration

### Understanding FIFO Responses
When performing stock operations, the API returns detailed FIFO allocation information:

```typescript
// Stock Out Response with FIFO Details
{
  status: "success",
  data: {
    total_quantity_allocated: 150.0,
    total_cost: 3850.0,
    weighted_average_cost: 25.67,
    fifo_allocations: [
      {
        inventory_item_id: 123,
        batch_number: "BATCH001",
        allocated_quantity: 100.0,
        unit_cost: 25.00,
        allocation_cost: 2500.0,
        entry_date: "2025-08-10T00:00:00Z"
      },
      {
        inventory_item_id: 124,
        batch_number: "BATCH002",
        allocated_quantity: 50.0,
        unit_cost: 27.00,
        allocation_cost: 1350.0,
        entry_date: "2025-08-12T00:00:00Z"
      }
    ],
    remaining_batches: [
      {
        batch_number: "BATCH002",
        remaining_quantity: 150.0,
        unit_cost: 27.00
      }
    ]
  }
}
```

### Displaying FIFO Information
Use this data to show users:
1. **Cost Breakdown:** How the total cost was calculated
2. **Batch Traceability:** Which batches were consumed
3. **Inventory Impact:** Remaining stock after operation

---

## Error Handling

### Standard Error Response Format
```typescript
interface APIError {
  status: "error";
  message: string;
  error_code: string;
  details?: any;
  timestamp: string;
  path: string;
}
```

### Common Error Codes
```typescript
// Authentication Errors
"AUTHENTICATION_FAILED" // Invalid credentials
"TOKEN_EXPIRED" // Access token expired
"INSUFFICIENT_PERMISSIONS" // User lacks required permissions

// Validation Errors  
"VALIDATION_ERROR" // Invalid input data
"DUPLICATE_CODE" // Product/warehouse code already exists
"INVALID_STOCK_LEVELS" // critical_stock_level > minimum_stock_level

// Business Logic Errors
"INSUFFICIENT_STOCK" // Not enough stock for operation
"INVALID_FIFO_ALLOCATION" // FIFO allocation failed
"PRODUCT_NOT_FOUND" // Product doesn't exist
"WAREHOUSE_NOT_FOUND" // Warehouse doesn't exist

// Example Error Response
{
  status: "error",
  message: "Insufficient stock for allocation",
  error_code: "INSUFFICIENT_STOCK",
  details: {
    requested_quantity: 500.0,
    available_quantity: 350.0,
    product_id: 1,
    warehouse_id: 1
  },
  timestamp: "2025-08-15T14:30:00Z",
  path: "/api/v1/inventory/stock-out"
}
```

### Frontend Error Handling Strategy
```typescript
const handleAPIError = (error: APIError) => {
  switch (error.error_code) {
    case 'AUTHENTICATION_FAILED':
      // Redirect to login page
      router.push('/login');
      break;
      
    case 'INSUFFICIENT_PERMISSIONS':
      // Show permission denied message
      showNotification('Access denied', 'error');
      break;
      
    case 'INSUFFICIENT_STOCK':
      // Show stock shortage with details
      const details = error.details;
      showNotification(
        `Insufficient stock: ${details.available_quantity} available, ${details.requested_quantity} requested`,
        'warning'
      );
      break;
      
    case 'VALIDATION_ERROR':
      // Show form validation errors
      setFormErrors(error.details);
      break;
      
    default:
      // Generic error handling
      showNotification(error.message, 'error');
  }
};
```

---

## Pagination and Filtering

### Standard Pagination Response
```typescript
interface PaginatedResponse<T> {
  status: "success";
  data: {
    items: T[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
    has_next: boolean;
    has_previous: boolean;
  };
}

// Example: Get Products with Pagination
GET /api/v1/master-data/products?page=2&page_size=10&search=steel&category=RAW_MATERIALS

Response: {
  status: "success",
  data: {
    items: [...], // Array of products
    total: 45,
    page: 2,
    page_size: 10,
    total_pages: 5,
    has_next: true,
    has_previous: true
  }
}
```

---

## Real-time Features

### WebSocket Integration (Future Enhancement)
The backend is prepared for real-time updates:
- Stock level changes
- Critical stock alerts
- Production order status updates
- System notifications

### Current Polling Recommendations
For real-time-like behavior, implement polling for:
```typescript
// Poll critical stock every 30 seconds
setInterval(() => {
  fetchCriticalStock();
}, 30000);

// Poll inventory availability before operations
const checkAvailability = async (productId: number) => {
  const response = await fetch(`/api/v1/inventory/availability/${productId}`);
  return response.json();
};
```

---

## Performance Optimization Tips

### Frontend Performance Best Practices

1. **Debounce Search Queries**
```typescript
const debouncedSearch = useMemo(
  () => debounce((searchTerm: string) => {
    fetchProducts({ search: searchTerm });
  }, 300),
  []
);
```

2. **Cache API Responses**
```typescript
// Use React Query or SWR for caching
const { data: products, isLoading } = useQuery(
  ['products', filters],
  () => fetchProducts(filters),
  { staleTime: 5 * 60 * 1000 } // 5 minutes
);
```

3. **Pagination with Infinite Scroll**
```typescript
const { data, fetchNextPage, hasNextPage } = useInfiniteQuery(
  ['inventory-items'],
  ({ pageParam = 1 }) => fetchInventoryItems({ page: pageParam }),
  {
    getNextPageParam: (lastPage) => 
      lastPage.has_next ? lastPage.page + 1 : undefined
  }
);
```

---

## Development Workflow

### API Client Setup
```typescript
// api/client.ts
class APIClient {
  private baseURL = 'http://localhost:8000/api/v1';
  
  private getAuthHeaders() {
    const token = localStorage.getItem('access_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }
  
  async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
        ...options.headers,
      },
      ...options,
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      throw new APIError(data);
    }
    
    return data;
  }
  
  // Convenience methods
  get<T>(endpoint: string) {
    return this.request<T>(endpoint);
  }
  
  post<T>(endpoint: string, body: any) {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }
  
  put<T>(endpoint: string, body: any) {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: JSON.stringify(body),
    });
  }
  
  delete<T>(endpoint: string) {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }
}

export const apiClient = new APIClient();
```

### Type-Safe API Hooks
```typescript
// hooks/useProducts.ts
export const useProducts = (filters?: ProductFilters) => {
  return useQuery({
    queryKey: ['products', filters],
    queryFn: () => apiClient.get<PaginatedResponse<Product>>('/master-data/products'),
    select: (data) => data.data,
  });
};

// hooks/useInventory.ts
export const useStockOut = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: StockOutRequest) => 
      apiClient.post('/inventory/stock-out', data),
    onSuccess: () => {
      // Invalidate relevant queries
      queryClient.invalidateQueries(['inventory-items']);
      queryClient.invalidateQueries(['stock-availability']);
    },
  });
};
```

---

## Testing the Integration

### API Testing Checklist
- [ ] Authentication flow (login, refresh, logout)
- [ ] Product CRUD operations
- [ ] Inventory stock operations (in, out, transfer)
- [ ] FIFO allocation accuracy
- [ ] Error handling for all scenarios
- [ ] Pagination and filtering
- [ ] Permission-based access control

### Sample Test Data
```typescript
// Test user credentials
const testUsers = {
  admin: { username: "admin@example.com", password: "admin123" },
  manager: { username: "manager@example.com", password: "manager123" },
  clerk: { username: "clerk@example.com", password: "clerk123" }
};

// Test products
const testProducts = [
  {
    code: "RAW001",
    name: "Steel Rod 10mm",
    category: "RAW_MATERIALS",
    unit_of_measure: "METERS"
  },
  {
    code: "SF001", 
    name: "Machined Component",
    category: "SEMI_FINISHED",
    unit_of_measure: "PIECES"
  }
];
```

---

## Support and Communication

### Backend Team Contacts
- **Backend Project Manager:** Available for architecture questions
- **Backend Developer:** Available for API-specific issues
- **Backend Debugger:** Available for troubleshooting

### Communication Channels
- **Technical Issues:** Report via GitHub issues or direct communication
- **Integration Questions:** Schedule pairing sessions for complex integrations
- **Performance Concerns:** Collaborate on optimization strategies

### Documentation Updates
- API documentation will be updated based on frontend feedback
- Integration guide will be enhanced during development
- Error handling will be refined based on user experience testing

---

## Next Steps

1. **Start with Authentication:** Implement login/logout flow first
2. **Basic CRUD Operations:** Products and warehouses management
3. **Inventory Operations:** Stock in/out with FIFO display
4. **Advanced Features:** Production orders and reporting
5. **Testing and Optimization:** Performance and user experience

**Backend Status:** ✅ Ready for Integration  
**Documentation:** ✅ Complete  
**Support:** ✅ Available  

The backend system is fully operational and ready to support frontend development. All endpoints are tested and documented, providing a solid foundation for building the user interface.