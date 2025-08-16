# Frontend Component Documentation
**Horoz Demir MRP System - Component Usage Guide**

---

## Table of Contents
1. [Component Overview](#component-overview)
2. [Authentication Components](#authentication-components)
3. [Navigation Components](#navigation-components)
4. [Dashboard Components](#dashboard-components)
5. [Form Components](#form-components)
6. [Data Display Components](#data-display-components)
7. [Utility Components](#utility-components)
8. [API Integration](#api-integration)
9. [Usage Examples](#usage-examples)
10. [Best Practices](#best-practices)

---

## Component Overview

The Horoz Demir MRP System frontend contains 15+ production-ready React components built with TypeScript, React 19, and Tailwind CSS. All components follow modern React patterns with hooks, context, and TypeScript interfaces.

### Component Architecture
```
src/
├── app/                    # Next.js App Router pages
├── components/            # Reusable UI components
├── contexts/              # React Context providers
├── hooks/                 # Custom React hooks
├── lib/                   # Utility libraries
└── types/                 # TypeScript definitions
```

### Technology Stack
- **React 19** with latest features and concurrent rendering
- **TypeScript 5** with strict type checking
- **Tailwind CSS v4** with responsive design utilities
- **Heroicons v2** for consistent iconography
- **TanStack React Query v5** for state management
- **React Hook Form v7** for form validation

---

## Authentication Components

### 1. AuthProvider (Context)
**Location:** `/Users/atacetinel/Documents/Pyhton/MRP-HorozDemir/frontend/src/contexts/auth-context.tsx`

**Purpose:** Manages global authentication state with JWT token handling.

**Features:**
- JWT token storage and refresh
- User session persistence
- Role-based access control
- Automatic token refresh on expiry

**Usage:**
```tsx
// Wrap your app with AuthProvider
<AuthProvider>
  <YourApp />
</AuthProvider>

// Use the auth context in components
const { user, isAuthenticated, login, logout } = useAuth();
```

**API:**
- `user: User | null` - Current user information
- `isAuthenticated: boolean` - Authentication status
- `isLoading: boolean` - Loading state during auth checks
- `login(username, password): Promise<void>` - Login function
- `logout(): void` - Logout function

### 2. AuthGuard Component
**Location:** `/Users/atacetinel/Documents/Pyhton/MRP-HorozDemir/frontend/src/components/auth-guard.tsx`

**Purpose:** Protects routes and components from unauthorized access.

**Features:**
- Automatic redirection to login page
- Loading state management
- Route protection wrapper

**Usage:**
```tsx
<AuthGuard>
  <ProtectedComponent />
</AuthGuard>
```

### 3. Login Page
**Location:** `/Users/atacetinel/Documents/Pyhton/MRP-HorozDemir/frontend/src/app/login/page.tsx`

**Purpose:** User authentication interface with form validation.

**Features:**
- Form validation and error handling
- Loading states during authentication
- Test credentials display
- Responsive design

**Form Fields:**
- `username: string` - User login identifier
- `password: string` - User password

---

## Navigation Components

### 1. Navigation Component
**Location:** `/Users/atacetinel/Documents/Pyhton/MRP-HorozDemir/frontend/src/components/navigation.tsx`

**Purpose:** Main navigation sidebar with role-based menu items.

**Features:**
- Responsive mobile/desktop layouts
- Role-based menu visibility
- Active page highlighting
- User profile dropdown

**Navigation Items:**
- Dashboard - System overview and metrics
- Products - Product management interface
- Warehouses - Warehouse configuration
- Inventory - Stock management and FIFO operations
- Stock Operations - Stock in/out transactions
- Suppliers - Supplier management
- Reports - Analytics and reporting

### 2. Layout Components
**Location:** `/Users/atacetinel/Documents/Pyhton/MRP-HorozDemir/frontend/src/app/layout.tsx`

**Purpose:** Root layout with global providers and styling.

**Features:**
- Global CSS and font configuration
- React Query provider setup
- Authentication context provider
- Dev tools integration

---

## Dashboard Components

### 1. Dashboard Page
**Location:** `/Users/atacetinel/Documents/Pyhton/MRP-HorozDemir/frontend/src/app/dashboard/page.tsx`

**Purpose:** Main dashboard with business metrics and critical alerts.

**Features:**
- Real-time statistics cards
- Critical stock alert system
- Financial overview section
- Recent products display
- Interactive navigation links

**Metrics Displayed:**
- Total Products count
- Active Warehouses count
- Inventory Items count
- Critical Stock Items count
- Total Inventory Value

**Data Sources:**
- `useCriticalStock()` - Critical stock items
- `useInventoryItems()` - Inventory data
- `useProducts()` - Product information
- `useWarehouses()` - Warehouse data

### 2. Statistics Cards
**Purpose:** Reusable metric display components.

**Features:**
- Loading state animations
- Click-through navigation
- Color-coded alerts
- Responsive grid layout

**Usage:**
```tsx
const stats = [
  {
    name: 'Total Products',
    value: productsData?.total || 0,
    icon: ClipboardDocumentListIcon,
    href: '/products',
    loading: productsLoading,
  }
];
```

---

## Form Components

### 1. Product Management Forms
**Location:** `/Users/atacetinel/Documents/Pyhton/MRP-HorozDemir/frontend/src/app/products/page.tsx`

**Purpose:** Product creation, editing, and management interface.

**Features:**
- Form validation with React Hook Form
- Category and unit selection
- Stock level configuration
- Search and filtering

**Form Fields:**
- `code: string` - Product identifier
- `name: string` - Product name
- `description?: string` - Optional description
- `category: ProductCategory` - Product category
- `unit_of_measure: UnitOfMeasure` - Measurement unit
- `minimum_stock_level: number` - Minimum stock threshold
- `critical_stock_level: number` - Critical stock threshold

### 2. Warehouse Management Forms
**Location:** `/Users/atacetinel/Documents/Pyhton/MRP-HorozDemir/frontend/src/app/warehouses/page.tsx`

**Purpose:** Warehouse configuration and management.

**Features:**
- Warehouse type selection
- Location and contact information
- Active/inactive status management

**Form Fields:**
- `code: string` - Warehouse identifier
- `name: string` - Warehouse name
- `type: WarehouseType` - Warehouse type
- `location?: string` - Physical location

### 3. Stock Operation Forms
**Location:** `/Users/atacetinel/Documents/Pyhton/MRP-HorozDemir/frontend/src/app/stock-operations/page.tsx`

**Purpose:** Stock in/out operations with FIFO calculations.

**Features:**
- Stock in/out operation forms
- FIFO batch selection
- Quality status management
- Cost calculation display

**Stock In Fields:**
- `product_id: number` - Selected product
- `warehouse_id: number` - Target warehouse
- `quantity: number` - Stock quantity
- `unit_cost: number` - Cost per unit
- `supplier_id?: number` - Optional supplier
- `quality_status: QualityStatus` - Quality approval status

**Stock Out Fields:**
- `product_id: number` - Selected product
- `warehouse_id: number` - Source warehouse
- `quantity: number` - Required quantity
- `reference_type?: string` - Transaction reference
- `notes?: string` - Additional notes

---

## Data Display Components

### 1. Inventory Display
**Location:** `/Users/atacetinel/Documents/Pyhton/MRP-HorozDemir/frontend/src/app/inventory/page.tsx`

**Purpose:** Inventory item listing with FIFO information.

**Features:**
- Paginated inventory listing
- FIFO batch information
- Quality status indicators
- Search and filtering
- Sorting capabilities

**Display Fields:**
- Product information (name, code, category)
- Warehouse details
- Stock quantities (total, reserved, available)
- Cost information (unit cost, total cost)
- Batch details (entry date, expiry date)
- Quality status with color coding

### 2. Supplier Management
**Location:** `/Users/atacetinel/Documents/Pyhton/MRP-HorozDemir/frontend/src/app/suppliers/page.tsx`

**Purpose:** Supplier information display and management.

**Features:**
- Contact information display
- Performance metrics
- Payment terms tracking
- Active/inactive status

### 3. Reports Interface
**Location:** `/Users/atacetinel/Documents/Pyhton/MRP-HorozDemir/frontend/src/app/reports/page.tsx`

**Purpose:** Business intelligence and reporting dashboard.

**Features:**
- Report generation interface
- Export functionality preparation
- Filter and date range selection
- Chart and graph displays

---

## Utility Components

### 1. Notifications System
**Location:** `/Users/atacetinel/Documents/Pyhton/MRP-HorozDemir/frontend/src/components/notifications.tsx`

**Purpose:** Toast notifications and alert system.

**Features:**
- Success/error/warning notifications
- Auto-dismiss functionality
- Stacking multiple notifications
- Accessibility compliance

### 2. Loading States
**Purpose:** Consistent loading indicators across the application.

**Features:**
- Skeleton loading animations
- Spinner components
- Progress indicators
- Pulse animations

**Usage:**
```tsx
{isLoading ? (
  <div className="animate-pulse">
    <div className="h-4 bg-gray-200 rounded"></div>
  </div>
) : (
  <ActualContent />
)}
```

---

## API Integration

### 1. API Client
**Location:** `/Users/atacetinel/Documents/Pyhton/MRP-HorozDemir/frontend/src/lib/api-client.ts`

**Purpose:** HTTP client with authentication and error handling.

**Features:**
- Automatic JWT token management
- Request/response interceptors
- Error handling and retry logic
- Type-safe API calls

**Methods:**
- `get<T>(endpoint, params)` - GET requests
- `post<T>(endpoint, body)` - POST requests
- `put<T>(endpoint, body)` - PUT requests
- `delete<T>(endpoint)` - DELETE requests
- `login(username, password)` - Authentication
- `logout()` - Session termination

### 2. Custom Hooks
**Location:** `/Users/atacetinel/Documents/Pyhton/MRP-HorozDemir/frontend/src/hooks/`

**Purpose:** Data fetching and state management hooks.

#### useProducts Hook
```tsx
const {
  data: productsData,
  isLoading,
  error,
  refetch
} = useProducts({ 
  page: 1, 
  page_size: 20, 
  search: 'filter' 
});
```

#### useInventory Hook
```tsx
const {
  data: inventoryData,
  isLoading,
  error
} = useInventoryItems({ 
  warehouse_id: 1,
  quality_status: 'APPROVED'
});
```

#### useWarehouses Hook
```tsx
const {
  data: warehousesData,
  isLoading,
  error
} = useWarehouses({ 
  type: 'RAW_MATERIALS',
  is_active: true
});
```

---

## Usage Examples

### 1. Creating a New Product Form
```tsx
import { useForm } from 'react-hook-form';
import { useProducts } from '@/hooks/use-products';
import { CreateProductRequest } from '@/types/api';

function ProductForm() {
  const { register, handleSubmit, formState: { errors } } = useForm<CreateProductRequest>();
  const { createProduct, isCreating } = useProducts();

  const onSubmit = async (data: CreateProductRequest) => {
    try {
      await createProduct(data);
      // Handle success
    } catch (error) {
      // Handle error
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input
        {...register('code', { required: 'Product code is required' })}
        placeholder="Product Code"
      />
      {errors.code && <span>{errors.code.message}</span>}
      
      <input
        {...register('name', { required: 'Product name is required' })}
        placeholder="Product Name"
      />
      {errors.name && <span>{errors.name.message}</span>}
      
      <button type="submit" disabled={isCreating}>
        {isCreating ? 'Creating...' : 'Create Product'}
      </button>
    </form>
  );
}
```

### 2. Displaying Inventory with FIFO Information
```tsx
import { useInventoryItems } from '@/hooks/use-inventory';
import { formatCurrency, formatDate } from '@/lib/utils';

function InventoryList() {
  const { data, isLoading } = useInventoryItems();

  if (isLoading) return <div>Loading...</div>;

  return (
    <div className="space-y-4">
      {data?.items.map((item) => (
        <div key={item.id} className="bg-white p-4 rounded-lg shadow">
          <h3 className="font-medium">{item.product?.name}</h3>
          <p className="text-sm text-gray-600">
            Warehouse: {item.warehouse?.name}
          </p>
          <div className="mt-2 grid grid-cols-3 gap-4">
            <div>
              <span className="text-sm font-medium">Available:</span>
              <span className="ml-2">{item.available_quantity}</span>
            </div>
            <div>
              <span className="text-sm font-medium">Unit Cost:</span>
              <span className="ml-2">{formatCurrency(item.unit_cost)}</span>
            </div>
            <div>
              <span className="text-sm font-medium">Entry Date:</span>
              <span className="ml-2">{formatDate(item.entry_date)}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
```

### 3. Critical Stock Alert Component
```tsx
import { useCriticalStock } from '@/hooks/use-inventory';
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline';

function CriticalStockAlert() {
  const { data: criticalStock } = useCriticalStock();

  if (!criticalStock || criticalStock.length === 0) return null;

  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
      <div className="flex items-center">
        <ExclamationTriangleIcon className="h-5 w-5 text-red-600 mr-2" />
        <h3 className="text-lg font-medium text-red-800">
          Critical Stock Alert
        </h3>
      </div>
      <p className="text-sm text-red-700 mt-2">
        {criticalStock.length} items are below critical stock levels
      </p>
      <div className="mt-3 space-y-2">
        {criticalStock.slice(0, 3).map((item) => (
          <div key={item.id} className="bg-white p-2 rounded border">
            <span className="font-medium">{item.product?.name}</span>
            <span className="text-sm text-gray-600 ml-2">
              Current: {item.available_quantity} | 
              Critical: {item.product?.critical_stock_level}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## Best Practices

### 1. Component Design Principles
- **Single Responsibility:** Each component handles one specific functionality
- **Props Interface:** Always define TypeScript interfaces for component props
- **Error Boundaries:** Implement error handling for all data-fetching components
- **Loading States:** Provide visual feedback during asynchronous operations
- **Accessibility:** Use semantic HTML and ARIA attributes

### 2. State Management
- **React Query:** Use for server state management and caching
- **Local State:** Use useState for component-specific state
- **Context:** Use for global state like authentication
- **Form State:** Use React Hook Form for complex form management

### 3. Performance Optimization
- **Memoization:** Use useMemo and useCallback for expensive operations
- **Code Splitting:** Implement lazy loading for large components
- **Bundle Optimization:** Tree-shake unused dependencies
- **Image Optimization:** Use Next.js Image component for images

### 4. Type Safety
- **Strict TypeScript:** Enable strict mode in tsconfig.json
- **API Types:** Define interfaces for all API responses
- **Component Props:** Type all component props and state
- **Event Handlers:** Type event handlers and callbacks

### 5. Testing Guidelines
- **Unit Tests:** Test individual component functionality
- **Integration Tests:** Test component interactions
- **User Acceptance Tests:** Test complete user workflows
- **Accessibility Tests:** Validate WCAG compliance

### 6. Code Organization
- **Folder Structure:** Group related files in logical folders
- **File Naming:** Use consistent naming conventions
- **Import Organization:** Group imports by source (external, internal, relative)
- **Export Patterns:** Use named exports for components, default for pages

---

## Component API Reference

### Common Props Patterns
```tsx
// Standard component props
interface ComponentProps {
  className?: string;
  children?: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  loading?: boolean;
}

// Data display component props
interface DataComponentProps<T> {
  data: T[];
  loading?: boolean;
  error?: Error | null;
  onRefresh?: () => void;
  emptyMessage?: string;
}

// Form component props
interface FormComponentProps<T> {
  initialData?: T;
  onSubmit: (data: T) => Promise<void>;
  onCancel?: () => void;
  validationSchema?: any;
  disabled?: boolean;
}
```

### Utility Functions
**Location:** `/Users/atacetinel/Documents/Pyhton/MRP-HorozDemir/frontend/src/lib/utils.ts`

- `formatCurrency(amount: number): string` - Currency formatting
- `formatNumber(num: number, decimals?: number): string` - Number formatting
- `formatDate(date: string): string` - Date formatting
- `getCategoryColor(category: string): string` - Category color mapping
- `handleAPIError(error: unknown): string` - Error message extraction

---

## Browser Compatibility

### Supported Browsers
- **Chrome:** 88+
- **Firefox:** 85+
- **Safari:** 14+
- **Edge:** 88+

### Not Supported
- **Internet Explorer:** All versions
- **Legacy Mobile Browsers:** iOS < 14, Android < 88

### Fallbacks
- **CSS Grid:** Flexbox fallback for older browsers
- **Modern JavaScript:** Babel transpilation for compatibility
- **CSS Variables:** PostCSS fallback values

---

## Deployment Configuration

### Environment Variables
```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_APP_NAME=Horoz Demir MRP System
NEXT_PUBLIC_VERSION=1.0.0
```

### Build Commands
```bash
# Development
npm run dev

# Production build
npm run build

# Production start
npm run start

# Linting
npm run lint
```

### Docker Configuration
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
CMD ["npm", "start"]
```

---

**Document Version:** 1.0  
**Last Updated:** August 16, 2025  
**File Location:** `/Users/atacetinel/Documents/Pyhton/MRP-HorozDemir/docs/Frontend_Component_Documentation.md`