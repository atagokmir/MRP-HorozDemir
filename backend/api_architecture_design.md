# Horoz Demir MRP System - FastAPI Architecture Design

**Backend Project Manager Report**  
**Date:** August 14, 2025  
**System:** Horoz Demir Material Requirements Planning System  
**Backend Framework:** FastAPI with PostgreSQL and SQLAlchemy ORM  
**Report Type:** Complete API Architecture and Implementation Plan  

---

## Executive Summary

This document defines the comprehensive FastAPI backend architecture for the Horoz Demir MRP system. Based on the validated database foundation, this design provides 28 REST endpoints across 7 functional modules, implementing sophisticated business logic for FIFO inventory management, nested BOM operations, production workflows, and comprehensive reporting.

### Key API Capabilities
- **RESTful Architecture**: 28 endpoints following OpenAPI 3.0 standards
- **FIFO Business Logic**: Automated inventory allocation and cost calculations
- **BOM Explosion**: Complex nested hierarchy processing
- **Production Workflows**: End-to-end manufacturing order management
- **Real-time Reporting**: Advanced analytics and alerting
- **Enterprise Security**: JWT-based authentication with role-based access control

---

## Table of Contents

1. [API Architecture Overview](#api-architecture-overview)
2. [Authentication and Authorization](#authentication-and-authorization)
3. [REST Endpoint Specifications](#rest-endpoint-specifications)
4. [Pydantic Schema Definitions](#pydantic-schema-definitions)
5. [Business Logic Workflows](#business-logic-workflows)
6. [Module Structure and Organization](#module-structure-and-organization)
7. [Data Flow Diagrams](#data-flow-diagrams)
8. [Error Handling Framework](#error-handling-framework)
9. [Performance and Optimization](#performance-and-optimization)
10. [Backend Team Task Assignments](#backend-team-task-assignments)

---

## API Architecture Overview

### Technology Stack
- **Framework**: FastAPI 0.104+ with Pydantic v2
- **Database**: PostgreSQL 15+ with SQLAlchemy 2.0+ ORM
- **Authentication**: JWT with refresh tokens
- **Documentation**: OpenAPI 3.0 (Swagger UI)
- **Testing**: pytest with async support
- **Validation**: Pydantic models with custom validators

### Core Design Principles
1. **Domain-Driven Design**: APIs organized by business domains
2. **FIFO-First**: All inventory operations respect FIFO logic
3. **Transaction Safety**: Critical operations wrapped in database transactions
4. **Real-time Data**: Minimal latency for inventory and production updates
5. **Audit Compliance**: Complete transaction history for all operations
6. **Scalability**: Optimized for concurrent user access

### Application Structure
```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application setup
│   ├── config.py                  # Configuration and environment
│   ├── dependencies.py            # Dependency injection
│   └── api/
│       ├── __init__.py
│       ├── auth/                  # Authentication endpoints
│       ├── master_data/           # Warehouses, products, suppliers
│       ├── inventory/             # FIFO inventory management
│       ├── bom/                   # Bill of materials operations
│       ├── production/            # Production order management
│       ├── procurement/           # Purchase order operations
│       └── reporting/             # Analytics and reports
├── models/                        # SQLAlchemy models (existing)
├── schemas/                       # Pydantic request/response models
├── services/                      # Business logic layer
├── utils/                         # Utility functions
└── tests/                         # Test suites
```

---

## Authentication and Authorization

### JWT Authentication System

#### Authentication Flow
1. **Login**: POST `/auth/login` - Username/password authentication
2. **Token Response**: JWT access token (15 min) + refresh token (7 days)
3. **Token Refresh**: POST `/auth/refresh` - Renew access token
4. **Logout**: POST `/auth/logout` - Invalidate tokens

#### User Roles and Permissions
```python
class UserRole(str, Enum):
    ADMIN = "admin"                # Full system access
    PRODUCTION_MANAGER = "prod_mgr" # Production and BOM management
    INVENTORY_CLERK = "inv_clerk"   # Inventory operations
    PROCUREMENT_OFFICER = "proc_off" # Purchase order management
    VIEWER = "viewer"               # Read-only access

class Permission(str, Enum):
    # Master Data
    READ_WAREHOUSES = "read:warehouses"
    WRITE_WAREHOUSES = "write:warehouses"
    READ_PRODUCTS = "read:products"
    WRITE_PRODUCTS = "write:products"
    READ_SUPPLIERS = "read:suppliers"
    WRITE_SUPPLIERS = "write:suppliers"
    
    # Inventory
    READ_INVENTORY = "read:inventory"
    WRITE_INVENTORY = "write:inventory"
    ALLOCATE_STOCK = "allocate:stock"
    
    # Production
    READ_PRODUCTION = "read:production"
    WRITE_PRODUCTION = "write:production"
    APPROVE_PRODUCTION = "approve:production"
    
    # BOM
    READ_BOM = "read:bom"
    WRITE_BOM = "write:bom"
    
    # Procurement
    READ_PROCUREMENT = "read:procurement"
    WRITE_PROCUREMENT = "write:procurement"
    
    # Reporting
    READ_REPORTS = "read:reports"
    GENERATE_REPORTS = "generate:reports"
```

#### Security Headers and Middleware
- **CORS**: Configured for frontend domain
- **Rate Limiting**: API endpoint throttling
- **Request ID**: Unique request tracking
- **Security Headers**: HSTS, content type protection

---

## REST Endpoint Specifications

### 1. Authentication Module (4 endpoints)

#### POST `/auth/login`
- **Purpose**: Authenticate user and return JWT tokens
- **Request**: `UserLogin` (username, password)
- **Response**: `TokenResponse` (access_token, refresh_token, user_info)
- **Business Logic**: Validate credentials, generate tokens

#### POST `/auth/refresh`
- **Purpose**: Refresh expired access token
- **Request**: `RefreshToken` (refresh_token)
- **Response**: `TokenResponse` (new access_token)
- **Business Logic**: Validate refresh token, issue new access token

#### POST `/auth/logout`
- **Purpose**: Invalidate user tokens
- **Request**: None (uses token from header)
- **Response**: `MessageResponse`
- **Business Logic**: Blacklist tokens

#### GET `/auth/me`
- **Purpose**: Get current user information
- **Request**: None (authenticated)
- **Response**: `UserInfo`
- **Business Logic**: Return user profile and permissions

### 2. Master Data Module (8 endpoints)

#### Warehouses (2 endpoints)
- **GET `/warehouses`**: List all warehouses with filtering
- **POST `/warehouses`**: Create new warehouse

#### Products (3 endpoints)
- **GET `/products`**: List products with pagination and search
- **POST `/products`**: Create new product
- **PUT `/products/{product_id}`**: Update product information

#### Suppliers (3 endpoints)
- **GET `/suppliers`**: List suppliers with performance metrics
- **POST `/suppliers`**: Create new supplier
- **PUT `/suppliers/{supplier_id}`**: Update supplier information

### 3. Inventory Management Module (6 endpoints)

#### GET `/inventory/items`
- **Purpose**: List inventory items with FIFO ordering
- **Parameters**: product_id, warehouse_id, quality_status, available_only
- **Response**: `InventoryItemList` with FIFO ordering
- **Business Logic**: Order by entry_date, inventory_item_id for FIFO

#### POST `/inventory/stock-in`
- **Purpose**: Add new inventory (purchases, production completion)
- **Request**: `StockInRequest` (product, warehouse, quantity, cost, batch_info)
- **Response**: `InventoryItem`
- **Business Logic**: Create inventory item, log stock movement

#### POST `/inventory/stock-out`
- **Purpose**: Manual stock removal
- **Request**: `StockOutRequest` (product, warehouse, quantity, reason)
- **Response**: `StockMovementResponse`
- **Business Logic**: FIFO allocation, update quantities, log movements

#### GET `/inventory/availability/{product_id}`
- **Purpose**: Check available quantity for production planning
- **Parameters**: warehouse_id (optional)
- **Response**: `InventoryAvailability`
- **Business Logic**: Sum available quantities across FIFO batches

#### POST `/inventory/reserve`
- **Purpose**: Reserve inventory for production orders
- **Request**: `ReservationRequest` (product, quantity, production_order)
- **Response**: `ReservationResponse`
- **Business Logic**: FIFO allocation, create stock_allocations

#### POST `/inventory/release-reservation`
- **Purpose**: Release reserved inventory
- **Request**: `ReleaseReservationRequest` (allocation_ids)
- **Response**: `MessageResponse`
- **Business Logic**: Update reserved quantities, remove allocations

### 4. BOM Management Module (5 endpoints)

#### GET `/bom/list`
- **Purpose**: List BOMs with filtering and search
- **Parameters**: product_id, status, effective_date
- **Response**: `BOMList`
- **Business Logic**: Filter active BOMs, include cost calculations

#### POST `/bom/create`
- **Purpose**: Create new BOM with components
- **Request**: `BOMCreateRequest` (product, components, labor_cost, version)
- **Response**: `BillOfMaterials`
- **Business Logic**: Validate components, check circular references

#### GET `/bom/{bom_id}/explosion`
- **Purpose**: Explode BOM to all raw material requirements
- **Parameters**: quantity (multiplication factor)
- **Response**: `BOMExplosion` (flattened materials list)
- **Business Logic**: Recursive BOM explosion with FIFO cost calculation

#### POST `/bom/{bom_id}/cost-calculation`
- **Purpose**: Calculate BOM cost based on current inventory
- **Request**: `CostCalculationRequest` (quantity)
- **Response**: `BOMCostCalculation`
- **Business Logic**: FIFO cost rollup, include labor and overhead

#### PUT `/bom/{bom_id}/status`
- **Purpose**: Update BOM status (activate, obsolete)
- **Request**: `BOMStatusUpdate` (status, effective_date)
- **Response**: `BillOfMaterials`
- **Business Logic**: Version management, status transitions

### 5. Production Management Module (5 endpoints)

#### GET `/production/orders`
- **Purpose**: List production orders with status filtering
- **Parameters**: status, product_id, date_range, priority
- **Response**: `ProductionOrderList`
- **Business Logic**: Include progress calculations, component status

#### POST `/production/orders`
- **Purpose**: Create new production order
- **Request**: `ProductionOrderRequest` (product, quantity, bom, priority, dates)
- **Response**: `ProductionOrder`
- **Business Logic**: BOM explosion, stock availability check, FIFO reservation

#### PUT `/production/orders/{order_id}/status`
- **Purpose**: Update production order status
- **Request**: `ProductionStatusUpdate` (status, completion_data)
- **Response**: `ProductionOrder`
- **Business Logic**: Status validation, stock movements on completion

#### GET `/production/orders/{order_id}/components`
- **Purpose**: Get component requirements and allocations
- **Response**: `ProductionComponentList`
- **Business Logic**: Show required vs allocated vs consumed quantities

#### POST `/production/orders/{order_id}/complete`
- **Purpose**: Complete production order
- **Request**: `ProductionCompletion` (completed_qty, scrapped_qty, actual_costs)
- **Response**: `ProductionOrder`
- **Business Logic**: FIFO consumption, stock-in finished goods, cost updates

### 6. Procurement Module (4 endpoints)

#### GET `/procurement/orders`
- **Purpose**: List purchase orders
- **Parameters**: status, supplier_id, date_range
- **Response**: `PurchaseOrderList`
- **Business Logic**: Include delivery status, pending items

#### POST `/procurement/orders`
- **Purpose**: Create purchase order
- **Request**: `PurchaseOrderRequest` (supplier, items, delivery_date)
- **Response**: `PurchaseOrder`
- **Business Logic**: Supplier validation, pricing lookup

#### PUT `/procurement/orders/{order_id}/receive`
- **Purpose**: Receive purchased items
- **Request**: `ReceiptRequest` (items_received, quality_status, costs)
- **Response**: `ReceiptResponse`
- **Business Logic**: Stock-in operation, quality status handling

#### GET `/procurement/suppliers/{supplier_id}/performance`
- **Purpose**: Get supplier performance metrics
- **Response**: `SupplierPerformance`
- **Business Logic**: Calculate delivery times, quality scores, pricing trends

### 7. Reporting Module (6 endpoints)

#### GET `/reports/inventory/summary`
- **Purpose**: Current inventory summary by warehouse
- **Parameters**: warehouse_type, product_category
- **Response**: `InventorySummary`
- **Business Logic**: Aggregate current stock levels, FIFO costs

#### GET `/reports/inventory/movements`
- **Purpose**: Stock movement history
- **Parameters**: date_range, product_id, movement_type
- **Response**: `StockMovementReport`
- **Business Logic**: Transaction history with running balances

#### GET `/reports/critical-stock`
- **Purpose**: Items below critical stock levels
- **Parameters**: warehouse_id, urgency_level
- **Response**: `CriticalStockReport`
- **Business Logic**: Compare current vs critical levels, suggest reorder quantities

#### GET `/reports/production/efficiency`
- **Purpose**: Production efficiency metrics
- **Parameters**: date_range, product_category
- **Response**: `ProductionEfficiencyReport`
- **Business Logic**: Planned vs actual quantities, timing analysis

#### GET `/reports/cost/fifo`
- **Purpose**: FIFO cost analysis
- **Parameters**: product_id, date_range
- **Response**: `FIFOCostReport`
- **Business Logic**: Historical cost trends, current FIFO valuations

#### POST `/reports/custom`
- **Purpose**: Generate custom reports
- **Request**: `CustomReportRequest` (filters, grouping, metrics)
- **Response**: `CustomReportResponse`
- **Business Logic**: Dynamic query building, data aggregation

---

## Pydantic Schema Definitions

### Base Schemas
```python
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, validator
from enum import Enum

class TimestampMixin(BaseModel):
    created_at: datetime
    updated_at: Optional[datetime] = None

class ResponseStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"

class BaseResponse(BaseModel):
    status: ResponseStatus
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)

class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    
class PaginatedResponse(BaseModel):
    items: List[BaseModel]
    total_count: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool
```

### Authentication Schemas
```python
class UserLogin(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)

class TokenResponse(BaseResponse):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_info: "UserInfo"

class UserInfo(BaseModel):
    user_id: int
    username: str
    full_name: str
    role: UserRole
    permissions: List[Permission]
    is_active: bool
```

### Master Data Schemas
```python
class WarehouseBase(BaseModel):
    warehouse_code: str = Field(..., regex=r"^[A-Z0-9]{2,10}$")
    warehouse_name: str = Field(..., min_length=1, max_length=100)
    warehouse_type: str = Field(..., regex=r"^(RAW_MATERIALS|SEMI_FINISHED|FINISHED_PRODUCTS|PACKAGING)$")
    location: Optional[str] = Field(None, max_length=200)
    manager_name: Optional[str] = Field(None, max_length=100)

class WarehouseCreate(WarehouseBase):
    pass

class Warehouse(WarehouseBase, TimestampMixin):
    warehouse_id: int
    is_active: bool
    
    class Config:
        from_attributes = True

class ProductBase(BaseModel):
    product_code: str = Field(..., regex=r"^[A-Z0-9\\-]{3,20}$")
    product_name: str = Field(..., min_length=1, max_length=200)
    product_type: str = Field(..., regex=r"^(RAW_MATERIAL|SEMI_FINISHED|FINISHED_PRODUCT|PACKAGING)$")
    unit_of_measure: str = Field(..., max_length=10)
    standard_cost: Optional[Decimal] = Field(None, ge=0, decimal_places=4)
    critical_stock_level: Optional[Decimal] = Field(None, ge=0, decimal_places=3)

class ProductCreate(ProductBase):
    pass

class Product(ProductBase, TimestampMixin):
    product_id: int
    is_active: bool
    
    class Config:
        from_attributes = True
```

### Inventory Schemas
```python
class StockInRequest(BaseModel):
    product_id: int
    warehouse_id: int
    quantity: Decimal = Field(..., gt=0, decimal_places=3)
    unit_cost: Decimal = Field(..., ge=0, decimal_places=4)
    batch_number: str = Field(..., regex=r"^[A-Z0-9\\-]{3,50}$")
    supplier_id: Optional[int] = None
    purchase_order_id: Optional[int] = None
    quality_status: str = Field("PENDING", regex=r"^(PENDING|APPROVED|REJECTED|QUARANTINE)$")
    expiry_date: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=500)

class StockOutRequest(BaseModel):
    product_id: int
    warehouse_id: int
    quantity: Decimal = Field(..., gt=0, decimal_places=3)
    reason: str = Field(..., min_length=1, max_length=200)
    reference_number: Optional[str] = Field(None, max_length=50)

class InventoryItem(BaseModel):
    inventory_item_id: int
    product_id: int
    warehouse_id: int
    batch_number: str
    quantity_in_stock: Decimal
    reserved_quantity: Decimal
    unit_cost: Decimal
    entry_date: datetime
    quality_status: str
    expiry_date: Optional[date]
    notes: Optional[str]
    
    # Computed fields
    available_quantity: Decimal
    total_value: Decimal
    
    class Config:
        from_attributes = True

class InventoryAvailability(BaseModel):
    product_id: int
    warehouse_id: Optional[int]
    total_available: Decimal
    total_reserved: Decimal
    batches: List[InventoryItem]
    weighted_average_cost: Decimal
```

### BOM Schemas
```python
class BOMComponentRequest(BaseModel):
    component_product_id: int
    quantity_required: Decimal = Field(..., gt=0, decimal_places=3)
    unit_of_measure: str = Field(..., max_length=10)
    scrap_percentage: Optional[Decimal] = Field(0, ge=0, le=100, decimal_places=2)

class BOMCreateRequest(BaseModel):
    parent_product_id: int
    bom_version: str = Field(..., regex=r"^\\d+\\.\\d+$")
    base_quantity: Decimal = Field(..., gt=0, decimal_places=3)
    labor_cost_per_unit: Optional[Decimal] = Field(0, ge=0, decimal_places=4)
    overhead_cost_per_unit: Optional[Decimal] = Field(0, ge=0, decimal_places=4)
    yield_percentage: Decimal = Field(100, gt=0, le=100, decimal_places=2)
    effective_date: date
    expiry_date: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=500)
    components: List[BOMComponentRequest]

class BOMExplosion(BaseModel):
    bom_id: int
    quantity_multiplier: Decimal
    raw_materials: List["BOMExplosionItem"]
    total_material_cost: Decimal
    total_labor_cost: Decimal
    total_overhead_cost: Decimal
    total_cost: Decimal

class BOMExplosionItem(BaseModel):
    product_id: int
    product_code: str
    product_name: str
    required_quantity: Decimal
    available_quantity: Decimal
    shortage_quantity: Decimal
    fifo_cost_per_unit: Decimal
    total_cost: Decimal
    level: int  # Nesting level in BOM hierarchy
```

### Production Schemas
```python
class ProductionOrderRequest(BaseModel):
    product_id: int
    bom_id: int
    warehouse_id: int
    planned_quantity: Decimal = Field(..., gt=0, decimal_places=3)
    priority: int = Field(5, ge=1, le=10)
    planned_start_date: Optional[date] = None
    planned_completion_date: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=500)

class ProductionOrder(BaseModel):
    production_order_id: int
    order_number: str
    product_id: int
    bom_id: int
    warehouse_id: int
    status: str
    planned_quantity: Decimal
    completed_quantity: Decimal
    scrapped_quantity: Decimal
    priority: int
    order_date: date
    planned_start_date: Optional[date]
    planned_completion_date: Optional[date]
    actual_start_date: Optional[datetime]
    actual_completion_date: Optional[datetime]
    estimated_cost: Decimal
    actual_cost: Decimal
    notes: Optional[str]
    
    # Related data
    product: Product
    bom: "BillOfMaterials"
    warehouse: Warehouse
    components: List["ProductionOrderComponent"]
    
    class Config:
        from_attributes = True

class ProductionCompletion(BaseModel):
    completed_quantity: Decimal = Field(..., ge=0, decimal_places=3)
    scrapped_quantity: Decimal = Field(0, ge=0, decimal_places=3)
    actual_labor_cost: Optional[Decimal] = Field(None, ge=0, decimal_places=4)
    actual_overhead_cost: Optional[Decimal] = Field(None, ge=0, decimal_places=4)
    completion_notes: Optional[str] = Field(None, max_length=500)
    
    @validator('completed_quantity', 'scrapped_quantity')
    def validate_quantities(cls, v, values):
        # Custom validation to ensure total doesn't exceed planned
        return v
```

---

## Business Logic Workflows

### 1. FIFO Inventory Allocation Algorithm

```python
async def allocate_fifo_inventory(
    session: AsyncSession,
    product_id: int,
    warehouse_id: int,
    required_quantity: Decimal,
    production_order_id: Optional[int] = None
) -> List[StockAllocation]:
    """
    Allocate inventory using FIFO logic.
    
    Process:
    1. Query available inventory ordered by entry_date, inventory_item_id
    2. Allocate quantities starting from oldest batches
    3. Create stock_allocation records
    4. Update reserved_quantity in inventory_items
    5. Return allocation details
    """
    allocations = []
    remaining_quantity = required_quantity
    
    # Get available inventory in FIFO order
    query = select(InventoryItem).where(
        InventoryItem.product_id == product_id,
        InventoryItem.warehouse_id == warehouse_id,
        InventoryItem.quality_status == 'APPROVED',
        InventoryItem.available_quantity > 0
    ).order_by(
        InventoryItem.entry_date,
        InventoryItem.inventory_item_id
    )
    
    inventory_items = await session.execute(query)
    
    for item in inventory_items.scalars():
        if remaining_quantity <= 0:
            break
            
        allocate_qty = min(item.available_quantity, remaining_quantity)
        
        # Create allocation record
        allocation = StockAllocation(
            production_order_id=production_order_id,
            inventory_item_id=item.inventory_item_id,
            allocated_quantity=allocate_qty,
            allocation_date=datetime.now()
        )
        
        # Update reserved quantity
        item.reserved_quantity += allocate_qty
        
        allocations.append(allocation)
        remaining_quantity -= allocate_qty
    
    if remaining_quantity > 0:
        raise InsufficientStockError(
            f"Cannot allocate {required_quantity} of product {product_id}. "
            f"Short by {remaining_quantity}"
        )
    
    session.add_all(allocations)
    return allocations
```

### 2. BOM Explosion Algorithm

```python
async def explode_bom(
    session: AsyncSession,
    bom_id: int,
    quantity_multiplier: Decimal,
    level: int = 0,
    processed_boms: set = None
) -> BOMExplosion:
    """
    Recursively explode BOM to raw material requirements.
    
    Process:
    1. Get BOM components
    2. For each component, check if it has its own BOM
    3. If component is semi-finished, recursively explode its BOM
    4. If component is raw material, add to requirements
    5. Calculate FIFO costs and availability
    6. Return flattened material requirements
    """
    if processed_boms is None:
        processed_boms = set()
    
    if bom_id in processed_boms:
        raise CircularBOMError(f"Circular reference detected in BOM {bom_id}")
    
    processed_boms.add(bom_id)
    
    # Get BOM and components
    bom = await session.get(BillOfMaterials, bom_id)
    components_query = select(BomComponent).where(
        BomComponent.bom_id == bom_id
    ).options(selectinload(BomComponent.component_product))
    
    components = await session.execute(components_query)
    
    raw_materials = []
    total_cost = Decimal('0')
    
    for component in components.scalars():
        required_qty = component.quantity_required * quantity_multiplier
        
        # Check if component has active BOM (semi-finished product)
        sub_bom_query = select(BillOfMaterials).where(
            BillOfMaterials.parent_product_id == component.component_product_id,
            BillOfMaterials.status == 'ACTIVE'
        )
        sub_bom = await session.execute(sub_bom_query)
        sub_bom = sub_bom.scalar_one_or_none()
        
        if sub_bom:
            # Recursively explode sub-BOM
            sub_explosion = await explode_bom(
                session, sub_bom.bom_id, required_qty, level + 1, processed_boms.copy()
            )
            raw_materials.extend(sub_explosion.raw_materials)
            total_cost += sub_explosion.total_cost
        else:
            # Raw material - calculate availability and cost
            availability = await get_inventory_availability(
                session, component.component_product_id
            )
            
            fifo_cost = await calculate_fifo_cost(
                session, component.component_product_id, required_qty
            )
            
            raw_material = BOMExplosionItem(
                product_id=component.component_product_id,
                product_code=component.component_product.product_code,
                product_name=component.component_product.product_name,
                required_quantity=required_qty,
                available_quantity=availability.total_available,
                shortage_quantity=max(Decimal('0'), required_qty - availability.total_available),
                fifo_cost_per_unit=fifo_cost.weighted_average_cost,
                total_cost=required_qty * fifo_cost.weighted_average_cost,
                level=level
            )
            
            raw_materials.append(raw_material)
            total_cost += raw_material.total_cost
    
    # Add labor and overhead costs
    labor_cost = bom.labor_cost_per_unit * quantity_multiplier
    overhead_cost = bom.overhead_cost_per_unit * quantity_multiplier
    
    return BOMExplosion(
        bom_id=bom_id,
        quantity_multiplier=quantity_multiplier,
        raw_materials=raw_materials,
        total_material_cost=total_cost,
        total_labor_cost=labor_cost,
        total_overhead_cost=overhead_cost,
        total_cost=total_cost + labor_cost + overhead_cost
    )
```

### 3. Production Order Workflow

```python
async def create_production_order(
    session: AsyncSession,
    request: ProductionOrderRequest,
    user_id: int
) -> ProductionOrder:
    """
    Create production order with automatic stock allocation.
    
    Process:
    1. Validate BOM and product compatibility
    2. Explode BOM to get material requirements
    3. Check material availability
    4. Allocate materials using FIFO logic
    5. Create production order and components
    6. Generate order number
    7. Return complete production order
    """
    # Validate BOM belongs to product
    bom = await session.get(BillOfMaterials, request.bom_id)
    if bom.parent_product_id != request.product_id:
        raise InvalidBOMError("BOM does not match specified product")
    
    # Explode BOM to get requirements
    explosion = await explode_bom(session, request.bom_id, request.planned_quantity)
    
    # Check for shortages
    shortages = [item for item in explosion.raw_materials if item.shortage_quantity > 0]
    if shortages:
        shortage_details = [
            f"{item.product_code}: short {item.shortage_quantity}"
            for item in shortages
        ]
        raise InsufficientStockError(
            f"Cannot create production order. Material shortages: {', '.join(shortage_details)}"
        )
    
    # Generate order number
    order_number = await generate_production_order_number(session)
    
    # Create production order
    production_order = ProductionOrder(
        order_number=order_number,
        product_id=request.product_id,
        bom_id=request.bom_id,
        warehouse_id=request.warehouse_id,
        status='PLANNED',
        planned_quantity=request.planned_quantity,
        completed_quantity=Decimal('0'),
        scrapped_quantity=Decimal('0'),
        priority=request.priority,
        order_date=date.today(),
        planned_start_date=request.planned_start_date,
        planned_completion_date=request.planned_completion_date,
        estimated_cost=explosion.total_cost,
        actual_cost=Decimal('0'),
        notes=request.notes,
        created_by=user_id
    )
    
    session.add(production_order)
    await session.flush()  # Get production_order_id
    
    # Create component requirements and allocations
    for material in explosion.raw_materials:
        # Create production order component
        component = ProductionOrderComponent(
            production_order_id=production_order.production_order_id,
            component_product_id=material.product_id,
            required_quantity=material.required_quantity,
            consumed_quantity=Decimal('0'),
            allocated_quantity=material.required_quantity,
            unit_cost=material.fifo_cost_per_unit
        )
        session.add(component)
        
        # Allocate inventory using FIFO
        allocations = await allocate_fifo_inventory(
            session,
            material.product_id,
            request.warehouse_id,  # or determine from component
            material.required_quantity,
            production_order.production_order_id
        )
    
    return production_order
```

---

## Module Structure and Organization

### 1. FastAPI Application Setup

#### `/backend/app/main.py`
```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from app.config import settings
from app.api.auth import router as auth_router
from app.api.master_data import router as master_data_router
from app.api.inventory import router as inventory_router
from app.api.bom import router as bom_router
from app.api.production import router as production_router
from app.api.procurement import router as procurement_router
from app.api.reporting import router as reporting_router
from app.exceptions import MRPException

app = FastAPI(
    title="Horoz Demir MRP System API",
    description="Material Requirements Planning System for Horoz Demir",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS
)

# Exception handlers
@app.exception_handler(MRPException)
async def mrp_exception_handler(request: Request, exc: MRPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": exc.message,
            "error_code": exc.error_code,
            "timestamp": datetime.now().isoformat()
        }
    )

# Include routers
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(master_data_router, prefix="/master-data", tags=["Master Data"])
app.include_router(inventory_router, prefix="/inventory", tags=["Inventory"])
app.include_router(bom_router, prefix="/bom", tags=["Bill of Materials"])
app.include_router(production_router, prefix="/production", tags=["Production"])
app.include_router(procurement_router, prefix="/procurement", tags=["Procurement"])
app.include_router(reporting_router, prefix="/reports", tags=["Reporting"])

@app.get("/")
async def root():
    return {"message": "Horoz Demir MRP System API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
```

#### `/backend/app/config.py`
```python
from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    DB_ECHO: bool = False
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # Application
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Horoz Demir MRP"
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### 2. Service Layer Architecture

#### `/backend/app/services/inventory_service.py`
```python
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload

from models import InventoryItem, StockMovement, Product, Warehouse
from schemas.inventory import StockInRequest, StockOutRequest, InventoryAvailability
from services.base import BaseService
from exceptions import InsufficientStockError, InvalidOperationError

class InventoryService(BaseService):
    """Service layer for inventory operations with FIFO logic."""
    
    async def stock_in(
        self,
        session: AsyncSession,
        request: StockInRequest,
        user_id: int
    ) -> InventoryItem:
        """Add new inventory with automatic FIFO entry."""
        
        # Validate product and warehouse
        await self._validate_product_warehouse(session, request.product_id, request.warehouse_id)
        
        # Create inventory item
        inventory_item = InventoryItem(
            product_id=request.product_id,
            warehouse_id=request.warehouse_id,
            batch_number=request.batch_number,
            quantity_in_stock=request.quantity,
            reserved_quantity=Decimal('0'),
            unit_cost=request.unit_cost,
            entry_date=datetime.now(),
            quality_status=request.quality_status,
            expiry_date=request.expiry_date,
            supplier_id=request.supplier_id,
            purchase_order_id=request.purchase_order_id,
            notes=request.notes
        )
        
        session.add(inventory_item)
        await session.flush()
        
        # Create stock movement record
        movement = StockMovement(
            inventory_item_id=inventory_item.inventory_item_id,
            movement_type='STOCK_IN',
            quantity=request.quantity,
            movement_date=datetime.now(),
            reference_type='MANUAL',
            reference_id=None,
            notes=f"Stock in: {request.quantity} units",
            created_by=user_id
        )
        
        session.add(movement)
        return inventory_item
    
    async def get_fifo_availability(
        self,
        session: AsyncSession,
        product_id: int,
        warehouse_id: Optional[int] = None
    ) -> InventoryAvailability:
        """Get available inventory in FIFO order with cost calculation."""
        
        query = select(InventoryItem).where(
            InventoryItem.product_id == product_id,
            InventoryItem.quality_status == 'APPROVED',
            InventoryItem.available_quantity > 0
        )
        
        if warehouse_id:
            query = query.where(InventoryItem.warehouse_id == warehouse_id)
        
        query = query.order_by(
            InventoryItem.entry_date,
            InventoryItem.inventory_item_id
        )
        
        result = await session.execute(query)
        batches = result.scalars().all()
        
        total_available = sum(batch.available_quantity for batch in batches)
        total_reserved = sum(batch.reserved_quantity for batch in batches)
        
        # Calculate weighted average cost
        total_value = sum(batch.available_quantity * batch.unit_cost for batch in batches)
        weighted_avg_cost = total_value / total_available if total_available > 0 else Decimal('0')
        
        return InventoryAvailability(
            product_id=product_id,
            warehouse_id=warehouse_id,
            total_available=total_available,
            total_reserved=total_reserved,
            batches=batches,
            weighted_average_cost=weighted_avg_cost
        )
```

### 3. Database Dependencies

#### `/backend/app/dependencies.py`
```python
from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt

from database import async_session
from config import settings
from models import User
from schemas.auth import UserInfo

security = HTTPBearer()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Database session dependency."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_db)
) -> UserInfo:
    """Get current authenticated user."""
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_exception
    
    return UserInfo.from_orm(user)

def require_permissions(*permissions: str):
    """Dependency factory for permission-based access control."""
    
    def permission_checker(current_user: UserInfo = Depends(get_current_user)):
        if not all(perm in current_user.permissions for perm in permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    
    return permission_checker
```

---

## Error Handling Framework

### Custom Exception Classes
```python
class MRPException(Exception):
    """Base exception class for MRP system."""
    
    def __init__(self, message: str, error_code: str = None, status_code: int = 400):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.status_code = status_code
        super().__init__(self.message)

class InsufficientStockError(MRPException):
    """Raised when there's insufficient stock for allocation."""
    
    def __init__(self, message: str):
        super().__init__(message, "INSUFFICIENT_STOCK", 409)

class CircularBOMError(MRPException):
    """Raised when circular reference detected in BOM."""
    
    def __init__(self, message: str):
        super().__init__(message, "CIRCULAR_BOM", 400)

class InvalidBOMError(MRPException):
    """Raised when BOM validation fails."""
    
    def __init__(self, message: str):
        super().__init__(message, "INVALID_BOM", 400)

class ProductionOrderError(MRPException):
    """Raised for production order related errors."""
    
    def __init__(self, message: str):
        super().__init__(message, "PRODUCTION_ORDER_ERROR", 400)
```

### Validation Middleware
```python
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError

@app.middleware("http")
async def validation_middleware(request: Request, call_next):
    """Global validation and error handling middleware."""
    
    try:
        response = await call_next(request)
        return response
    except ValidationError as e:
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "message": "Validation error",
                "details": e.errors(),
                "timestamp": datetime.now().isoformat()
            }
        )
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={
                "status": "error",
                "message": e.detail,
                "timestamp": datetime.now().isoformat()
            }
        )
```

---

## Performance and Optimization

### Database Query Optimization
1. **FIFO Queries**: Optimized with composite indexes on (product_id, warehouse_id, entry_date)
2. **BOM Explosion**: Recursive CTE queries for efficient hierarchy traversal
3. **Inventory Aggregation**: Materialized views for reporting dashboards
4. **Connection Pooling**: Async connection pool with proper sizing

### Caching Strategy
1. **Product Master Data**: Redis cache with 1-hour TTL
2. **BOM Hierarchies**: Cache explosion results for active BOMs
3. **User Permissions**: Session-based permission caching
4. **Report Data**: Cached aggregations for standard reports

### API Performance Targets
- **CRUD Operations**: < 100ms response time
- **FIFO Allocation**: < 200ms for typical quantities
- **BOM Explosion**: < 500ms for 3-level hierarchies
- **Report Generation**: < 2 seconds for standard reports
- **Concurrent Users**: Support 50+ simultaneous users

---

## Backend Team Task Assignments

### Backend API Developer (Primary Implementation)
**Duration**: 10 days  
**Deliverables**:

1. **FastAPI Application Setup** (Day 1-2)
   - Initialize FastAPI project structure
   - Configure database connections with SQLAlchemy
   - Set up environment configuration and settings
   - Implement health check and basic middleware

2. **Authentication System** (Day 2-3)
   - JWT token authentication with refresh tokens
   - User role and permission management
   - Security middleware and dependencies
   - Password hashing and validation

3. **Master Data APIs** (Day 3-4)
   - Warehouses, Products, Suppliers CRUD endpoints
   - Data validation with Pydantic schemas
   - Search and filtering capabilities
   - Relationship management APIs

4. **Inventory Management APIs** (Day 4-6)
   - Stock-in/stock-out operations
   - FIFO inventory querying and allocation
   - Inventory availability checks
   - Stock reservation and release operations

5. **BOM Management APIs** (Day 6-7)
   - BOM CRUD operations with version control
   - Component management and validation
   - BOM explosion endpoint implementation
   - Cost calculation APIs

6. **Production Order APIs** (Day 7-9)
   - Production order creation and management
   - Status transition workflows
   - Component allocation and consumption
   - Production completion processing

7. **Procurement and Reporting APIs** (Day 9-10)
   - Purchase order management
   - Supplier performance tracking
   - Standard report endpoints
   - Custom report generation

### Backend Business Logic Developer (Core Algorithms)
**Duration**: 8 days  
**Deliverables**:

1. **FIFO Logic Implementation** (Day 1-3)
   - FIFO allocation algorithm with database integration
   - Cost calculation functions
   - Stock reservation and consumption logic
   - Batch tracking and expiry handling

2. **BOM Processing Engine** (Day 3-5)
   - Recursive BOM explosion algorithm
   - Circular reference detection
   - Multi-level cost rollup calculations
   - Requirements planning logic

3. **Production Workflow Automation** (Day 5-7)
   - Production order status state machine
   - Automatic stock allocation on order creation
   - Production completion processing
   - Material consumption and finished goods receipt

4. **Cost Calculation System** (Day 7-8)
   - Real-time FIFO cost calculations
   - Standard cost vs actual cost variance
   - Cost history tracking and analysis
   - Production cost rollup algorithms

### Backend Testing Engineer (Quality Assurance)
**Duration**: 8 days  
**Deliverables**:

1. **Unit Test Suite** (Day 1-3)
   - Test all API endpoints with pytest
   - Mock database operations for isolated testing
   - Test authentication and authorization
   - Validate request/response schemas

2. **Integration Test Suite** (Day 3-5)
   - End-to-end workflow testing
   - Database transaction testing
   - FIFO logic validation with real data
   - BOM explosion accuracy testing

3. **Performance Testing** (Day 5-6)
   - Load testing for concurrent operations
   - FIFO allocation performance benchmarks
   - BOM explosion performance optimization
   - Database query performance analysis

4. **Business Logic Validation** (Day 6-8)
   - Complex production workflow scenarios
   - Multi-level BOM testing with sample data
   - Cost calculation accuracy validation
   - Error handling and edge case testing

### Backend Documentation Specialist (API Documentation)
**Duration**: 6 days  
**Deliverables**:

1. **OpenAPI Documentation** (Day 1-2)
   - Complete Swagger/OpenAPI specifications
   - Request/response examples for all endpoints
   - Authentication documentation
   - Error response documentation

2. **API Integration Guide** (Day 2-4)
   - Frontend integration patterns
   - Code examples for common operations
   - Authentication flow documentation
   - Error handling best practices

3. **Postman Collection** (Day 4-5)
   - Complete API collection with examples
   - Environment variables setup
   - Authentication configuration
   - Test scenarios and workflows

4. **Deployment Documentation** (Day 5-6)
   - Environment setup and configuration
   - Database migration procedures
   - Performance tuning guidelines
   - Monitoring and logging setup

---

## Success Criteria and Deliverables

### Sprint 2 Completion Requirements

#### Technical Deliverables
1. **Complete FastAPI Application** with all 28 endpoints implemented
2. **Comprehensive Test Suite** with >90% code coverage
3. **OpenAPI Documentation** with complete API specifications
4. **Postman Collection** for API testing and validation
5. **Integration Guide** for Frontend Team handoff

#### Business Logic Validation
1. **FIFO Allocation** working correctly with database integration
2. **BOM Explosion** handling complex 3-level hierarchies
3. **Production Workflows** supporting complete order lifecycle
4. **Cost Calculations** accurate and real-time
5. **Error Handling** comprehensive with meaningful messages

#### Performance Benchmarks
1. **Response Times**: All endpoints under target performance thresholds
2. **Concurrent Operations**: Support for 50+ simultaneous users
3. **Database Performance**: Optimized queries with proper indexing
4. **Memory Usage**: Efficient resource utilization

#### Quality Assurance
1. **Unit Tests**: All business logic thoroughly tested
2. **Integration Tests**: End-to-end workflows validated
3. **Error Scenarios**: Edge cases and error conditions handled
4. **Security Testing**: Authentication and authorization verified

---

## Conclusion

This comprehensive API architecture provides the foundation for the Horoz Demir MRP system backend implementation. The design emphasizes:

- **FIFO-centric operations** ensuring accurate inventory costing
- **Scalable architecture** supporting enterprise-level operations
- **Comprehensive business logic** handling complex manufacturing scenarios
- **Robust testing framework** ensuring system reliability
- **Clear documentation** facilitating team coordination

The Backend Team is now equipped with detailed specifications, task assignments, and success criteria to deliver a production-ready FastAPI backend system within Sprint 2 timeline.

**Next Steps**: Backend Team members should begin their assigned tasks immediately, following the specified development workflow and maintaining coordination through the designated reporting structure.