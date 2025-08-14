# Horoz Demir MRP System - Entity Relationship Diagram (ERD) Specification

## ERD Overview
This document provides a detailed specification of the Entity Relationship Diagram for the Horoz Demir MRP system. The database is designed in 3rd Normal Form (3NF) to eliminate redundancy while optimizing for MRP operations.

## Entity Groups and Relationships

### 1. Master Data Entities

#### Warehouses
**Purpose**: Define the 4 main storage locations for different product types
- **Primary Key**: warehouse_id
- **Unique Keys**: warehouse_code
- **Business Rules**: 
  - Each warehouse must have a unique code and type
  - Only 4 warehouse types allowed: RAW_MATERIALS, SEMI_FINISHED, FINISHED_PRODUCTS, PACKAGING

#### Products  
**Purpose**: Master catalog of all items (raw materials, semi-finished, finished, packaging)
- **Primary Key**: product_id
- **Unique Keys**: product_code
- **Business Rules**:
  - Product type must match warehouse type for storage
  - Minimum and critical stock levels must be non-negative
  - Semi-finished and finished products require BOMs

#### Suppliers
**Purpose**: Vendor management and supplier information
- **Primary Key**: supplier_id
- **Unique Keys**: supplier_code
- **Business Rules**:
  - Supplier ratings (quality, delivery, price) range from 0.0 to 5.0
  - Lead time must be non-negative

### 2. Inventory Management Entities

#### Inventory Items (FIFO Core Table)
**Purpose**: Track individual inventory batches with FIFO support
- **Primary Key**: inventory_item_id
- **Unique Keys**: product_id + warehouse_id + batch_number + entry_date
- **Business Rules**:
  - Entry date is critical for FIFO ordering
  - Available quantity = quantity_in_stock - reserved_quantity
  - Each batch must have a unique combination of product, warehouse, batch number, and entry date
  - Unit cost must be positive

#### Stock Movements
**Purpose**: Complete audit trail of all inventory transactions
- **Primary Key**: movement_id
- **Foreign Keys**: 
  - inventory_item_id → inventory_items
  - from_warehouse_id → warehouses
  - to_warehouse_id → warehouses
- **Business Rules**:
  - Every stock change must create a movement record
  - Movement types: IN, OUT, TRANSFER, ADJUSTMENT, PRODUCTION, RETURN
  - Transfer movements require both from and to warehouses

### 3. BOM (Bill of Materials) Entities

#### Bill of Materials
**Purpose**: Define product composition and manufacturing recipes
- **Primary Key**: bom_id
- **Foreign Keys**: parent_product_id → products
- **Unique Keys**: parent_product_id + bom_version
- **Business Rules**:
  - Only one active BOM per product at a time
  - Base quantity defines the standard production batch
  - Yield percentage accounts for production losses

#### BOM Components
**Purpose**: Define individual components within each BOM
- **Primary Key**: bom_component_id
- **Foreign Keys**: 
  - bom_id → bill_of_materials
  - component_product_id → products
- **Business Rules**:
  - Components can reference other products (enabling nested BOMs)
  - Effective quantity includes scrap percentage
  - Sequence number defines assembly order

#### BOM Cost Calculations
**Purpose**: Store calculated costs for each BOM version
- **Primary Key**: bom_cost_id
- **Foreign Keys**: bom_id → bill_of_materials
- **Business Rules**:
  - Costs rolled up from component costs using FIFO pricing
  - Only one current calculation per BOM
  - Total cost = material + labor + overhead

### 4. Production Management Entities

#### Production Orders
**Purpose**: Track manufacturing orders and progress
- **Primary Key**: production_order_id
- **Foreign Keys**:
  - product_id → products
  - bom_id → bill_of_materials
  - warehouse_id → warehouses
- **Unique Keys**: order_number
- **Business Rules**:
  - Planned quantity must be positive
  - Completed + scrapped quantities cannot exceed planned
  - Status progression: PLANNED → RELEASED → IN_PROGRESS → COMPLETED

#### Production Order Components
**Purpose**: Track component requirements and consumption for each production order
- **Primary Key**: po_component_id
- **Foreign Keys**:
  - production_order_id → production_orders
  - component_product_id → products
- **Business Rules**:
  - Required quantity derived from BOM × production quantity
  - Consumed quantity cannot exceed allocated quantity
  - Allocation status tracks component availability

#### Stock Allocations
**Purpose**: Reserve specific inventory batches for production orders (FIFO implementation)
- **Primary Key**: allocation_id
- **Foreign Keys**:
  - production_order_id → production_orders
  - inventory_item_id → inventory_items
- **Business Rules**:
  - Allocations follow FIFO order (oldest inventory first)
  - Consumed quantity cannot exceed allocated quantity
  - Remaining allocation = allocated - consumed

### 5. Procurement Entities

#### Purchase Orders
**Purpose**: Track material procurement from suppliers
- **Primary Key**: purchase_order_id
- **Foreign Keys**:
  - supplier_id → suppliers
  - warehouse_id → warehouses
- **Unique Keys**: po_number
- **Business Rules**:
  - Total amount calculated from line items
  - Status progression: DRAFT → SENT → CONFIRMED → RECEIVED

#### Purchase Order Items
**Purpose**: Individual line items within purchase orders
- **Primary Key**: po_item_id
- **Foreign Keys**:
  - purchase_order_id → purchase_orders
  - product_id → products
- **Business Rules**:
  - Quantity received cannot exceed quantity ordered
  - Total price = quantity × unit price
  - Delivery status tracks receipt progress

### 6. Relationship Management Entities

#### Product Suppliers
**Purpose**: Many-to-many relationship between products and suppliers
- **Primary Key**: product_supplier_id
- **Foreign Keys**:
  - product_id → products
  - supplier_id → suppliers
- **Unique Keys**: product_id + supplier_id
- **Business Rules**:
  - Each product can have multiple suppliers
  - One supplier can be marked as preferred per product
  - Unit price and lead time specific to each product-supplier combination

### 7. Monitoring and Analytics Entities

#### Critical Stock Alerts
**Purpose**: Track products below minimum stock levels
- **Primary Key**: alert_id
- **Foreign Keys**:
  - product_id → products
  - warehouse_id → warehouses
- **Business Rules**:
  - Alert generated when stock falls below minimum or critical levels
  - Alert types: MINIMUM, CRITICAL, OUT_OF_STOCK
  - Resolved alerts marked with resolution date

#### Cost Calculation History
**Purpose**: Historical cost tracking for analysis and reporting
- **Primary Key**: cost_history_id
- **Foreign Keys**: product_id → products
- **Business Rules**:
  - Daily cost calculations stored for trend analysis
  - Multiple cost types supported: FIFO, STANDARD, AVERAGE, ACTUAL
  - Quantity basis normalizes costs to standard units

## Key Relationships and Cardinalities

### One-to-Many Relationships
1. **Warehouses → Inventory Items** (1:M)
   - One warehouse contains many inventory items
   
2. **Products → Inventory Items** (1:M)
   - One product can have multiple inventory batches
   
3. **Products → BOM (as parent)** (1:M)
   - One product can have multiple BOM versions
   
4. **BOM → BOM Components** (1:M)
   - One BOM contains multiple components
   
5. **Products → BOM Components** (1:M)
   - One product can be used in multiple BOMs as a component
   
6. **Suppliers → Purchase Orders** (1:M)
   - One supplier can have multiple purchase orders
   
7. **Production Orders → Production Order Components** (1:M)
   - One production order has multiple component requirements

### Many-to-Many Relationships
1. **Products ↔ Suppliers** (M:M via product_suppliers)
   - Products can have multiple suppliers
   - Suppliers can supply multiple products
   
2. **Production Orders ↔ Inventory Items** (M:M via stock_allocations)
   - Production orders can consume from multiple inventory batches
   - Inventory batches can be allocated to multiple production orders

### Self-Referencing Relationships
1. **Products → Products** (via BOM Components)
   - Semi-finished products can contain other semi-finished products
   - Creates hierarchical BOM structure

## FIFO Implementation in ERD

### FIFO-Critical Relationships
1. **Inventory Items**: `entry_date` provides FIFO ordering
2. **Stock Allocations**: Links production orders to specific batches in FIFO order
3. **Stock Movements**: Tracks exact consumption sequence
4. **Cost Calculations**: Uses FIFO batch costs for accurate costing

### FIFO Process Flow
```
Inventory Items (ordered by entry_date) 
    ↓
Stock Allocations (FIFO batch selection)
    ↓  
Production Order Components (consumption tracking)
    ↓
Stock Movements (audit trail)
    ↓
Cost Calculation History (FIFO costing)
```

## BOM Hierarchy in ERD

### Nested BOM Relationships
1. **Parent Product** → BOM → **Components**
2. **Semi-Finished Component** → BOM → **Sub-Components**
3. **Raw Material Components** (leaf nodes)

### BOM Explosion Path
```
Finished Product
    ↓ (BOM Level 1)
Semi-Finished Product A + Raw Material X
    ↓ (BOM Level 2)  
Semi-Finished Product B + Raw Material Y
    ↓ (BOM Level 3)
Raw Material Z + Raw Material W
```

## Data Flow and Integration Points

### Production Order Flow
1. **Order Creation**: Production Orders → BOM → Components
2. **Stock Check**: Components → Inventory Items (FIFO order)
3. **Allocation**: Stock Allocations (reserve batches)
4. **Consumption**: Stock Movements (track usage)
5. **Completion**: Update inventory, costs, and status

### Procurement Flow
1. **Purchase Order**: Purchase Orders → Items → Products
2. **Receipt**: Create Inventory Items with entry_date
3. **Quality Check**: Update quality_status
4. **Stock In**: Generate Stock Movements
5. **Cost Update**: Update unit costs and calculations

### Cost Calculation Flow
1. **Inventory Costs**: FIFO batch costs from Inventory Items
2. **BOM Costs**: Roll up from component costs
3. **Production Costs**: Actual consumption costs
4. **History**: Store in Cost Calculation History

## Constraints and Integrity Rules

### Referential Integrity
- All foreign keys enforce CASCADE DELETE where appropriate
- Orphaned records prevented through proper constraint design

### Business Rule Constraints
- Stock quantities must be non-negative
- Dates must be logical (start ≤ completion)
- Percentages within valid ranges (0-100%)
- Status transitions follow defined workflows

### Performance Considerations
- Indexes on FIFO queries (product_id, warehouse_id, entry_date)
- Indexes on BOM hierarchy traversal
- Indexes on production order status and dates
- Composite indexes for common query patterns

This ERD specification provides the foundation for implementing a robust MRP database that supports all required functionalities while maintaining data integrity and optimal performance for manufacturing operations.