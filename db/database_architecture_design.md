# Horoz Demir MRP System - Database Architecture Design

## Overview
This document presents the comprehensive database schema design for the Horoz Demir Material Requirements Planning (MRP) system. The design follows 3rd Normal Form (3NF) principles and supports all core MRP functionalities including FIFO inventory management, nested Bill of Materials, and comprehensive production tracking.

## System Requirements Summary
- **4 Warehouse Types**: Raw Materials, Semi-Finished Products, Finished Products, Packaging Materials
- **FIFO Logic**: First-in-first-out inventory management with entry date tracking
- **Nested BOMs**: Semi-finished products can contain other semi-finished products
- **Production Management**: Order creation, stock validation, and automatic deductions
- **Supplier Integration**: Multi-supplier support with performance tracking
- **Cost Calculations**: Automated FIFO-based cost rollup calculations
- **Audit Trails**: Complete stock movement and transaction logging

## Core Database Architecture

### 1. Master Data Tables

#### 1.1 Warehouse Management
```sql
-- Warehouses table for the 4 main storage types
warehouses (
    warehouse_id SERIAL PRIMARY KEY,
    warehouse_code VARCHAR(10) UNIQUE NOT NULL,
    warehouse_name VARCHAR(100) NOT NULL,
    warehouse_type VARCHAR(20) NOT NULL CHECK (warehouse_type IN ('RAW_MATERIALS', 'SEMI_FINISHED', 'FINISHED_PRODUCTS', 'PACKAGING')),
    location VARCHAR(200),
    manager_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);
```

#### 1.2 Product Management
```sql
-- Products master table for all item types
products (
    product_id SERIAL PRIMARY KEY,
    product_code VARCHAR(50) UNIQUE NOT NULL,
    product_name VARCHAR(200) NOT NULL,
    product_type VARCHAR(20) NOT NULL CHECK (product_type IN ('RAW_MATERIAL', 'SEMI_FINISHED', 'FINISHED_PRODUCT', 'PACKAGING')),
    unit_of_measure VARCHAR(20) NOT NULL,
    minimum_stock_level DECIMAL(15,4) DEFAULT 0,
    critical_stock_level DECIMAL(15,4) DEFAULT 0,
    standard_cost DECIMAL(15,4) DEFAULT 0,
    description TEXT,
    specifications JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);
```

#### 1.3 Supplier Management
```sql
-- Suppliers master table
suppliers (
    supplier_id SERIAL PRIMARY KEY,
    supplier_code VARCHAR(20) UNIQUE NOT NULL,
    supplier_name VARCHAR(200) NOT NULL,
    contact_person VARCHAR(100),
    email VARCHAR(100),
    phone VARCHAR(20),
    address TEXT,
    city VARCHAR(50),
    country VARCHAR(50),
    payment_terms VARCHAR(100),
    lead_time_days INTEGER DEFAULT 0,
    quality_rating DECIMAL(3,2) DEFAULT 0.0,
    delivery_rating DECIMAL(3,2) DEFAULT 0.0,
    price_rating DECIMAL(3,2) DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Product-Supplier relationship (many-to-many)
product_suppliers (
    product_supplier_id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(product_id) ON DELETE CASCADE,
    supplier_id INTEGER REFERENCES suppliers(supplier_id) ON DELETE CASCADE,
    supplier_product_code VARCHAR(50),
    unit_price DECIMAL(15,4) NOT NULL,
    minimum_order_qty DECIMAL(15,4) DEFAULT 0,
    lead_time_days INTEGER DEFAULT 0,
    is_preferred BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(product_id, supplier_id)
);
```

### 2. Inventory Management Tables (FIFO Support)

#### 2.1 Inventory Items with FIFO Tracking
```sql
-- Inventory items with FIFO support through entry_date and batch tracking
inventory_items (
    inventory_item_id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(product_id) ON DELETE CASCADE,
    warehouse_id INTEGER REFERENCES warehouses(warehouse_id) ON DELETE CASCADE,
    batch_number VARCHAR(50) NOT NULL,
    entry_date TIMESTAMP NOT NULL,
    expiry_date TIMESTAMP,
    quantity_in_stock DECIMAL(15,4) NOT NULL DEFAULT 0,
    reserved_quantity DECIMAL(15,4) DEFAULT 0,
    available_quantity DECIMAL(15,4) GENERATED ALWAYS AS (quantity_in_stock - reserved_quantity) STORED,
    unit_cost DECIMAL(15,4) NOT NULL,
    total_cost DECIMAL(15,4) GENERATED ALWAYS AS (quantity_in_stock * unit_cost) STORED,
    supplier_id INTEGER REFERENCES suppliers(supplier_id),
    purchase_order_id INTEGER,
    location_in_warehouse VARCHAR(50),
    quality_status VARCHAR(20) DEFAULT 'APPROVED' CHECK (quality_status IN ('PENDING', 'APPROVED', 'REJECTED', 'QUARANTINE')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product_id, warehouse_id, batch_number, entry_date)
);
```

#### 2.2 Stock Movement Audit Trail
```sql
-- Complete audit trail of all stock movements
stock_movements (
    movement_id SERIAL PRIMARY KEY,
    inventory_item_id INTEGER REFERENCES inventory_items(inventory_item_id) ON DELETE CASCADE,
    movement_type VARCHAR(20) NOT NULL CHECK (movement_type IN ('IN', 'OUT', 'TRANSFER', 'ADJUSTMENT', 'PRODUCTION', 'RETURN')),
    movement_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    quantity DECIMAL(15,4) NOT NULL,
    unit_cost DECIMAL(15,4) NOT NULL,
    total_cost DECIMAL(15,4) GENERATED ALWAYS AS (quantity * unit_cost) STORED,
    reference_type VARCHAR(30), -- 'PURCHASE_ORDER', 'PRODUCTION_ORDER', 'TRANSFER', 'ADJUSTMENT'
    reference_id INTEGER,
    from_warehouse_id INTEGER REFERENCES warehouses(warehouse_id),
    to_warehouse_id INTEGER REFERENCES warehouses(warehouse_id),
    notes TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3. Bill of Materials (BOM) - Nested Structure

#### 3.1 BOM Headers
```sql
-- BOM header table for both semi-finished and finished products
bill_of_materials (
    bom_id SERIAL PRIMARY KEY,
    parent_product_id INTEGER REFERENCES products(product_id) ON DELETE CASCADE,
    bom_version VARCHAR(10) NOT NULL DEFAULT '1.0',
    bom_name VARCHAR(200) NOT NULL,
    effective_date DATE NOT NULL DEFAULT CURRENT_DATE,
    expiry_date DATE,
    status VARCHAR(20) DEFAULT 'ACTIVE' CHECK (status IN ('DRAFT', 'ACTIVE', 'INACTIVE', 'OBSOLETE')),
    base_quantity DECIMAL(15,4) NOT NULL DEFAULT 1, -- Base quantity for calculations
    yield_percentage DECIMAL(5,2) DEFAULT 100.00,
    labor_cost_per_unit DECIMAL(15,4) DEFAULT 0,
    overhead_cost_per_unit DECIMAL(15,4) DEFAULT 0,
    notes TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(parent_product_id, bom_version)
);
```

#### 3.2 BOM Components (Nested Support)
```sql
-- BOM components supporting nested semi-finished products
bom_components (
    bom_component_id SERIAL PRIMARY KEY,
    bom_id INTEGER REFERENCES bill_of_materials(bom_id) ON DELETE CASCADE,
    component_product_id INTEGER REFERENCES products(product_id) ON DELETE CASCADE,
    sequence_number INTEGER NOT NULL,
    quantity_required DECIMAL(15,4) NOT NULL,
    unit_of_measure VARCHAR(20) NOT NULL,
    scrap_percentage DECIMAL(5,2) DEFAULT 0.00,
    effective_quantity DECIMAL(15,4) GENERATED ALWAYS AS (quantity_required * (1 + scrap_percentage/100)) STORED,
    is_phantom BOOLEAN DEFAULT FALSE, -- For phantom assemblies
    substitute_group VARCHAR(20), -- For alternative components
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 3.3 BOM Cost Calculations
```sql
-- BOM cost rollup calculations
bom_cost_calculations (
    bom_cost_id SERIAL PRIMARY KEY,
    bom_id INTEGER REFERENCES bill_of_materials(bom_id) ON DELETE CASCADE,
    calculation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    material_cost DECIMAL(15,4) NOT NULL DEFAULT 0,
    labor_cost DECIMAL(15,4) NOT NULL DEFAULT 0,
    overhead_cost DECIMAL(15,4) NOT NULL DEFAULT 0,
    total_cost DECIMAL(15,4) GENERATED ALWAYS AS (material_cost + labor_cost + overhead_cost) STORED,
    cost_basis VARCHAR(20) DEFAULT 'FIFO' CHECK (cost_basis IN ('FIFO', 'STANDARD', 'AVERAGE')),
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4. Production Management

#### 4.1 Production Orders
```sql
-- Production orders for semi-finished and finished products
production_orders (
    production_order_id SERIAL PRIMARY KEY,
    order_number VARCHAR(50) UNIQUE NOT NULL,
    product_id INTEGER REFERENCES products(product_id) ON DELETE CASCADE,
    bom_id INTEGER REFERENCES bill_of_materials(bom_id),
    warehouse_id INTEGER REFERENCES warehouses(warehouse_id) ON DELETE CASCADE,
    order_date DATE NOT NULL DEFAULT CURRENT_DATE,
    planned_start_date DATE,
    planned_completion_date DATE,
    actual_start_date DATE,
    actual_completion_date DATE,
    planned_quantity DECIMAL(15,4) NOT NULL,
    completed_quantity DECIMAL(15,4) DEFAULT 0,
    scrapped_quantity DECIMAL(15,4) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'PLANNED' CHECK (status IN ('PLANNED', 'RELEASED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'ON_HOLD')),
    priority INTEGER DEFAULT 5,
    estimated_cost DECIMAL(15,4) DEFAULT 0,
    actual_cost DECIMAL(15,4) DEFAULT 0,
    notes TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 4.2 Production Order Components
```sql
-- Components required for production orders
production_order_components (
    po_component_id SERIAL PRIMARY KEY,
    production_order_id INTEGER REFERENCES production_orders(production_order_id) ON DELETE CASCADE,
    component_product_id INTEGER REFERENCES products(product_id) ON DELETE CASCADE,
    required_quantity DECIMAL(15,4) NOT NULL,
    allocated_quantity DECIMAL(15,4) DEFAULT 0,
    consumed_quantity DECIMAL(15,4) DEFAULT 0,
    unit_cost DECIMAL(15,4) DEFAULT 0,
    total_cost DECIMAL(15,4) GENERATED ALWAYS AS (consumed_quantity * unit_cost) STORED,
    allocation_status VARCHAR(20) DEFAULT 'NOT_ALLOCATED' CHECK (allocation_status IN ('NOT_ALLOCATED', 'PARTIALLY_ALLOCATED', 'FULLY_ALLOCATED', 'CONSUMED')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 4.3 Stock Allocations and Consumption
```sql
-- Stock allocations for production orders (FIFO-based)
stock_allocations (
    allocation_id SERIAL PRIMARY KEY,
    production_order_id INTEGER REFERENCES production_orders(production_order_id) ON DELETE CASCADE,
    inventory_item_id INTEGER REFERENCES inventory_items(inventory_item_id) ON DELETE CASCADE,
    allocated_quantity DECIMAL(15,4) NOT NULL,
    consumed_quantity DECIMAL(15,4) DEFAULT 0,
    remaining_allocation DECIMAL(15,4) GENERATED ALWAYS AS (allocated_quantity - consumed_quantity) STORED,
    allocation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    consumption_date TIMESTAMP,
    status VARCHAR(20) DEFAULT 'ALLOCATED' CHECK (status IN ('ALLOCATED', 'PARTIALLY_CONSUMED', 'FULLY_CONSUMED', 'RELEASED'))
);
```

### 5. Purchasing and Procurement

#### 5.1 Purchase Orders
```sql
-- Purchase orders for material procurement
purchase_orders (
    purchase_order_id SERIAL PRIMARY KEY,
    po_number VARCHAR(50) UNIQUE NOT NULL,
    supplier_id INTEGER REFERENCES suppliers(supplier_id) ON DELETE CASCADE,
    warehouse_id INTEGER REFERENCES warehouses(warehouse_id) ON DELETE CASCADE,
    order_date DATE NOT NULL DEFAULT CURRENT_DATE,
    expected_delivery_date DATE,
    actual_delivery_date DATE,
    total_amount DECIMAL(15,4) NOT NULL DEFAULT 0,
    currency VARCHAR(3) DEFAULT 'USD',
    payment_terms VARCHAR(100),
    status VARCHAR(20) DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'SENT', 'CONFIRMED', 'PARTIALLY_RECEIVED', 'FULLY_RECEIVED', 'CANCELLED')),
    notes TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 5.2 Purchase Order Items
```sql
-- Purchase order line items
purchase_order_items (
    po_item_id SERIAL PRIMARY KEY,
    purchase_order_id INTEGER REFERENCES purchase_orders(purchase_order_id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(product_id) ON DELETE CASCADE,
    quantity_ordered DECIMAL(15,4) NOT NULL,
    quantity_received DECIMAL(15,4) DEFAULT 0,
    unit_price DECIMAL(15,4) NOT NULL,
    total_price DECIMAL(15,4) GENERATED ALWAYS AS (quantity_ordered * unit_price) STORED,
    delivery_status VARCHAR(20) DEFAULT 'PENDING' CHECK (delivery_status IN ('PENDING', 'PARTIALLY_RECEIVED', 'FULLY_RECEIVED', 'CANCELLED')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 6. Reporting and Analytics Tables

#### 6.1 Critical Stock Alerts
```sql
-- Critical stock level monitoring
critical_stock_alerts (
    alert_id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(product_id) ON DELETE CASCADE,
    warehouse_id INTEGER REFERENCES warehouses(warehouse_id) ON DELETE CASCADE,
    current_stock DECIMAL(15,4) NOT NULL,
    minimum_level DECIMAL(15,4) NOT NULL,
    critical_level DECIMAL(15,4) NOT NULL,
    alert_type VARCHAR(20) NOT NULL CHECK (alert_type IN ('MINIMUM', 'CRITICAL', 'OUT_OF_STOCK')),
    alert_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_resolved BOOLEAN DEFAULT FALSE,
    resolved_date TIMESTAMP,
    notes TEXT
);
```

#### 6.2 Cost Calculations History
```sql
-- Historical cost calculations for reporting
cost_calculation_history (
    cost_history_id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(product_id) ON DELETE CASCADE,
    calculation_date DATE NOT NULL,
    cost_type VARCHAR(20) NOT NULL CHECK (cost_type IN ('FIFO', 'STANDARD', 'AVERAGE', 'ACTUAL')),
    material_cost DECIMAL(15,4) DEFAULT 0,
    labor_cost DECIMAL(15,4) DEFAULT 0,
    overhead_cost DECIMAL(15,4) DEFAULT 0,
    total_unit_cost DECIMAL(15,4) GENERATED ALWAYS AS (material_cost + labor_cost + overhead_cost) STORED,
    quantity_basis DECIMAL(15,4) NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Database Indexes for Performance

### Critical Indexes
```sql
-- FIFO inventory queries
CREATE INDEX idx_inventory_fifo ON inventory_items(product_id, warehouse_id, entry_date, quantity_in_stock);

-- BOM hierarchy lookups
CREATE INDEX idx_bom_parent ON bill_of_materials(parent_product_id, status);
CREATE INDEX idx_bom_components ON bom_components(bom_id, component_product_id);

-- Production order tracking
CREATE INDEX idx_production_orders_status ON production_orders(status, planned_start_date);
CREATE INDEX idx_production_orders_product ON production_orders(product_id, order_date);

-- Stock movement audit
CREATE INDEX idx_stock_movements_item ON stock_movements(inventory_item_id, movement_date);
CREATE INDEX idx_stock_movements_type ON stock_movements(movement_type, movement_date);

-- Supplier performance
CREATE INDEX idx_product_suppliers_perf ON product_suppliers(supplier_id, is_preferred);

-- Critical stock monitoring
CREATE INDEX idx_critical_stock ON critical_stock_alerts(product_id, warehouse_id, is_resolved);
```

## FIFO Implementation Strategy

### 1. FIFO Stock Consumption
The FIFO logic is implemented through:
- `entry_date` timestamp in `inventory_items`
- Ordered consumption based on earliest entry dates
- `stock_allocations` table tracks which batches are consumed first
- `available_quantity` calculated field excludes reserved stock

### 2. Cost Calculation Method
```sql
-- Sample FIFO cost calculation query
WITH fifo_consumption AS (
    SELECT 
        inventory_item_id,
        product_id,
        entry_date,
        unit_cost,
        quantity_in_stock,
        SUM(quantity_in_stock) OVER (
            PARTITION BY product_id 
            ORDER BY entry_date 
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) as running_total
    FROM inventory_items 
    WHERE product_id = ? AND quantity_in_stock > 0
    ORDER BY entry_date
)
SELECT * FROM fifo_consumption 
WHERE running_total >= ?; -- Required quantity
```

## BOM Hierarchy Implementation

### Nested BOM Support
- Recursive relationships through `bom_components.component_product_id`
- Semi-finished products can contain other semi-finished products
- Cost rollup calculations cascade through hierarchy
- Production orders handle nested requirements automatically

### BOM Explosion Query
```sql
-- Recursive CTE for BOM explosion
WITH RECURSIVE bom_explosion AS (
    -- Base case: direct components
    SELECT 
        bc.bom_id,
        bc.component_product_id,
        bc.quantity_required,
        1 as level,
        ARRAY[bom.parent_product_id] as path
    FROM bom_components bc
    JOIN bill_of_materials bom ON bc.bom_id = bom.bom_id
    WHERE bom.parent_product_id = ?
    
    UNION ALL
    
    -- Recursive case: sub-components
    SELECT 
        bc.bom_id,
        bc.component_product_id,
        be.quantity_required * bc.quantity_required,
        be.level + 1,
        be.path || bom.parent_product_id
    FROM bom_explosion be
    JOIN bill_of_materials bom ON be.component_product_id = bom.parent_product_id
    JOIN bom_components bc ON bom.bom_id = bc.bom_id
    WHERE NOT (bom.parent_product_id = ANY(be.path)) -- Prevent infinite loops
)
SELECT * FROM bom_explosion ORDER BY level, component_product_id;
```

## Data Integrity Constraints

### Critical Business Rules
1. **Stock Consistency**: Available quantity cannot exceed total stock
2. **FIFO Ordering**: Entry dates must be properly sequenced
3. **BOM Validity**: Components cannot reference their parent products
4. **Production Logic**: Cannot consume more than allocated
5. **Supplier Relationships**: All purchases must reference valid suppliers

### Triggers and Constraints
```sql
-- Ensure FIFO integrity
ALTER TABLE inventory_items ADD CONSTRAINT chk_positive_stock 
CHECK (quantity_in_stock >= 0 AND reserved_quantity >= 0);

-- BOM circular reference prevention
ALTER TABLE bom_components ADD CONSTRAINT chk_no_self_reference 
CHECK (component_product_id != (
    SELECT parent_product_id FROM bill_of_materials 
    WHERE bom_id = bom_components.bom_id
));

-- Production order quantity validation
ALTER TABLE production_orders ADD CONSTRAINT chk_positive_quantities 
CHECK (planned_quantity > 0 AND completed_quantity >= 0 AND scrapped_quantity >= 0);
```

## Database Security and Access Control

### Role-Based Access
```sql
-- Database roles
CREATE ROLE mrp_admin;
CREATE ROLE mrp_production_manager;
CREATE ROLE mrp_inventory_clerk;
CREATE ROLE mrp_readonly;

-- Grant appropriate permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO mrp_admin;
GRANT SELECT, INSERT, UPDATE ON production_orders, stock_movements TO mrp_production_manager;
GRANT SELECT, INSERT, UPDATE ON inventory_items, stock_movements TO mrp_inventory_clerk;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mrp_readonly;
```

## Backup and Maintenance Strategy

### Regular Maintenance Tasks
1. **Daily**: Update cost calculations, process critical stock alerts
2. **Weekly**: Archive completed production orders, clean up old stock movements
3. **Monthly**: Recalculate inventory valuations, supplier performance metrics
4. **Quarterly**: Full database backup, index optimization

### Archive Strategy
- Move completed production orders older than 2 years to archive tables
- Retain stock movements for 5 years for audit compliance
- Compress historical cost calculations after 1 year

This database architecture provides a robust foundation for the Horoz Demir MRP system, supporting all core requirements while maintaining data integrity, performance, and scalability for future growth.