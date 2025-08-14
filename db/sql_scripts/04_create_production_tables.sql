-- ==============================================================================
-- Horoz Demir MRP System - Production Management Tables
-- ==============================================================================
-- This script creates the production management tables including production
-- orders, component requirements, and FIFO-based stock allocations
-- ==============================================================================

-- Drop tables if they exist (in reverse dependency order)
DROP TABLE IF EXISTS stock_allocations CASCADE;
DROP TABLE IF EXISTS production_order_components CASCADE;
DROP TABLE IF EXISTS production_orders CASCADE;

-- ==============================================================================
-- PRODUCTION_ORDERS TABLE
-- ==============================================================================
-- Main production order tracking table for manufacturing semi-finished
-- and finished products with status and progress tracking
-- ==============================================================================

CREATE TABLE production_orders (
    production_order_id SERIAL PRIMARY KEY,
    order_number VARCHAR(50) UNIQUE NOT NULL,
    product_id INTEGER NOT NULL,
    bom_id INTEGER NOT NULL,
    warehouse_id INTEGER NOT NULL,
    order_date DATE NOT NULL DEFAULT CURRENT_DATE,
    planned_start_date DATE,
    planned_completion_date DATE,
    actual_start_date DATE,
    actual_completion_date DATE,
    planned_quantity DECIMAL(15,4) NOT NULL,
    completed_quantity DECIMAL(15,4) DEFAULT 0,
    scrapped_quantity DECIMAL(15,4) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'PLANNED',
    priority INTEGER DEFAULT 5,
    estimated_cost DECIMAL(15,4) DEFAULT 0,
    actual_cost DECIMAL(15,4) DEFAULT 0,
    notes TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    CONSTRAINT fk_production_orders_product 
        FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE,
    CONSTRAINT fk_production_orders_bom 
        FOREIGN KEY (bom_id) REFERENCES bill_of_materials(bom_id) ON DELETE CASCADE,
    CONSTRAINT fk_production_orders_warehouse 
        FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id) ON DELETE CASCADE,
    
    -- Business rule constraints
    CONSTRAINT chk_production_order_status CHECK (
        status IN ('PLANNED', 'RELEASED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'ON_HOLD')
    ),
    CONSTRAINT chk_production_order_quantities CHECK (
        planned_quantity > 0 AND 
        completed_quantity >= 0 AND 
        scrapped_quantity >= 0 AND
        (completed_quantity + scrapped_quantity) <= planned_quantity
    ),
    CONSTRAINT chk_production_order_priority CHECK (
        priority >= 1 AND priority <= 10
    ),
    CONSTRAINT chk_production_order_costs CHECK (
        estimated_cost >= 0 AND actual_cost >= 0
    ),
    CONSTRAINT chk_production_order_dates CHECK (
        (planned_start_date IS NULL OR planned_start_date >= order_date) AND
        (planned_completion_date IS NULL OR planned_start_date IS NULL OR 
         planned_completion_date >= planned_start_date) AND
        (actual_start_date IS NULL OR actual_start_date >= order_date) AND
        (actual_completion_date IS NULL OR actual_start_date IS NULL OR 
         actual_completion_date >= actual_start_date)
    ),
    CONSTRAINT chk_production_order_number_format CHECK (
        order_number ~ '^PO[0-9]{6}$'
    )
);

-- Add table and column comments
COMMENT ON TABLE production_orders IS 'Production orders for manufacturing semi-finished and finished products';
COMMENT ON COLUMN production_orders.order_number IS 'Unique production order number in format PO######';
COMMENT ON COLUMN production_orders.status IS 'Order status: PLANNED, RELEASED, IN_PROGRESS, COMPLETED, CANCELLED, ON_HOLD';
COMMENT ON COLUMN production_orders.priority IS 'Production priority from 1 (highest) to 10 (lowest)';
COMMENT ON COLUMN production_orders.estimated_cost IS 'Estimated production cost based on BOM';
COMMENT ON COLUMN production_orders.actual_cost IS 'Actual production cost based on material consumption';

-- ==============================================================================
-- PRODUCTION_ORDER_COMPONENTS TABLE
-- ==============================================================================
-- Tracks component requirements and consumption for each production order
-- Links production orders to specific material requirements
-- ==============================================================================

CREATE TABLE production_order_components (
    po_component_id SERIAL PRIMARY KEY,
    production_order_id INTEGER NOT NULL,
    component_product_id INTEGER NOT NULL,
    required_quantity DECIMAL(15,4) NOT NULL,
    allocated_quantity DECIMAL(15,4) DEFAULT 0,
    consumed_quantity DECIMAL(15,4) DEFAULT 0,
    unit_cost DECIMAL(15,4) DEFAULT 0,
    total_cost DECIMAL(15,4) GENERATED ALWAYS AS (consumed_quantity * unit_cost) STORED,
    allocation_status VARCHAR(20) DEFAULT 'NOT_ALLOCATED',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    CONSTRAINT fk_po_components_production_order 
        FOREIGN KEY (production_order_id) REFERENCES production_orders(production_order_id) ON DELETE CASCADE,
    CONSTRAINT fk_po_components_product 
        FOREIGN KEY (component_product_id) REFERENCES products(product_id) ON DELETE CASCADE,
    
    -- Business rule constraints
    CONSTRAINT chk_po_component_quantities CHECK (
        required_quantity > 0 AND 
        allocated_quantity >= 0 AND 
        consumed_quantity >= 0 AND
        consumed_quantity <= allocated_quantity AND
        allocated_quantity <= required_quantity
    ),
    CONSTRAINT chk_po_component_allocation_status CHECK (
        allocation_status IN ('NOT_ALLOCATED', 'PARTIALLY_ALLOCATED', 'FULLY_ALLOCATED', 'CONSUMED')
    ),
    CONSTRAINT chk_po_component_unit_cost CHECK (unit_cost >= 0),
    
    -- Unique constraint to prevent duplicate components per production order
    CONSTRAINT uk_po_component UNIQUE (production_order_id, component_product_id)
);

-- Add table and column comments
COMMENT ON TABLE production_order_components IS 'Component requirements and consumption tracking for production orders';
COMMENT ON COLUMN production_order_components.required_quantity IS 'Total quantity required based on BOM and production quantity';
COMMENT ON COLUMN production_order_components.allocated_quantity IS 'Quantity allocated from inventory (FIFO)';
COMMENT ON COLUMN production_order_components.consumed_quantity IS 'Actual quantity consumed during production';
COMMENT ON COLUMN production_order_components.allocation_status IS 'Allocation status: NOT_ALLOCATED, PARTIALLY_ALLOCATED, FULLY_ALLOCATED, CONSUMED';
COMMENT ON COLUMN production_order_components.total_cost IS 'Calculated field: consumed_quantity * unit_cost';

-- ==============================================================================
-- STOCK_ALLOCATIONS TABLE
-- ==============================================================================
-- FIFO-based stock allocation tracking - reserves specific inventory batches
-- for production orders based on entry date (first in, first out)
-- ==============================================================================

CREATE TABLE stock_allocations (
    allocation_id SERIAL PRIMARY KEY,
    production_order_id INTEGER NOT NULL,
    inventory_item_id INTEGER NOT NULL,
    allocated_quantity DECIMAL(15,4) NOT NULL,
    consumed_quantity DECIMAL(15,4) DEFAULT 0,
    remaining_allocation DECIMAL(15,4) GENERATED ALWAYS AS (allocated_quantity - consumed_quantity) STORED,
    allocation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    consumption_date TIMESTAMP,
    status VARCHAR(20) DEFAULT 'ALLOCATED',
    
    -- Foreign key constraints
    CONSTRAINT fk_stock_allocations_production_order 
        FOREIGN KEY (production_order_id) REFERENCES production_orders(production_order_id) ON DELETE CASCADE,
    CONSTRAINT fk_stock_allocations_inventory_item 
        FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(inventory_item_id) ON DELETE CASCADE,
    
    -- Business rule constraints
    CONSTRAINT chk_stock_allocation_quantities CHECK (
        allocated_quantity > 0 AND 
        consumed_quantity >= 0 AND
        consumed_quantity <= allocated_quantity
    ),
    CONSTRAINT chk_stock_allocation_status CHECK (
        status IN ('ALLOCATED', 'PARTIALLY_CONSUMED', 'FULLY_CONSUMED', 'RELEASED')
    ),
    CONSTRAINT chk_stock_allocation_dates CHECK (
        consumption_date IS NULL OR consumption_date >= allocation_date
    )
);

-- Add table and column comments
COMMENT ON TABLE stock_allocations IS 'FIFO-based stock allocations linking production orders to specific inventory batches';
COMMENT ON COLUMN stock_allocations.remaining_allocation IS 'Calculated field: allocated_quantity - consumed_quantity';
COMMENT ON COLUMN stock_allocations.status IS 'Allocation status: ALLOCATED, PARTIALLY_CONSUMED, FULLY_CONSUMED, RELEASED';
COMMENT ON COLUMN stock_allocations.consumption_date IS 'Date when allocation was consumed (set when status changes to consumed)';

-- ==============================================================================
-- TRIGGERS FOR PRODUCTION MANAGEMENT
-- ==============================================================================

-- Updated timestamp triggers
CREATE TRIGGER trg_production_orders_updated_at
    BEFORE UPDATE ON production_orders
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_po_components_updated_at
    BEFORE UPDATE ON production_order_components
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger to update allocation status based on quantities
CREATE OR REPLACE FUNCTION update_allocation_status()
RETURNS TRIGGER AS $$
BEGIN
    -- Update allocation status based on quantities
    IF NEW.allocated_quantity = 0 THEN
        NEW.allocation_status := 'NOT_ALLOCATED';
    ELSIF NEW.allocated_quantity < NEW.required_quantity THEN
        NEW.allocation_status := 'PARTIALLY_ALLOCATED';
    ELSIF NEW.consumed_quantity = NEW.allocated_quantity THEN
        NEW.allocation_status := 'CONSUMED';
    ELSE
        NEW.allocation_status := 'FULLY_ALLOCATED';
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_po_component_allocation_status
    BEFORE INSERT OR UPDATE ON production_order_components
    FOR EACH ROW
    EXECUTE FUNCTION update_allocation_status();

-- Trigger to update stock allocation status
CREATE OR REPLACE FUNCTION update_stock_allocation_status()
RETURNS TRIGGER AS $$
BEGIN
    -- Update stock allocation status based on consumption
    IF NEW.consumed_quantity = 0 THEN
        NEW.status := 'ALLOCATED';
    ELSIF NEW.consumed_quantity < NEW.allocated_quantity THEN
        NEW.status := 'PARTIALLY_CONSUMED';
        IF NEW.consumption_date IS NULL THEN
            NEW.consumption_date := CURRENT_TIMESTAMP;
        END IF;
    ELSE
        NEW.status := 'FULLY_CONSUMED';
        NEW.consumption_date := CURRENT_TIMESTAMP;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_stock_allocation_status
    BEFORE INSERT OR UPDATE ON stock_allocations
    FOR EACH ROW
    EXECUTE FUNCTION update_stock_allocation_status();

-- Trigger to synchronize reserved quantities in inventory_items
CREATE OR REPLACE FUNCTION sync_reserved_quantities()
RETURNS TRIGGER AS $$
DECLARE
    total_allocated DECIMAL(15,4);
BEGIN
    -- Calculate total allocated quantity for this inventory item
    SELECT COALESCE(SUM(remaining_allocation), 0)
    INTO total_allocated
    FROM stock_allocations
    WHERE inventory_item_id = COALESCE(NEW.inventory_item_id, OLD.inventory_item_id)
      AND status IN ('ALLOCATED', 'PARTIALLY_CONSUMED');
    
    -- Update reserved quantity in inventory_items
    UPDATE inventory_items
    SET reserved_quantity = total_allocated,
        updated_at = CURRENT_TIMESTAMP
    WHERE inventory_item_id = COALESCE(NEW.inventory_item_id, OLD.inventory_item_id);
    
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_reserved_quantities
    AFTER INSERT OR UPDATE OR DELETE ON stock_allocations
    FOR EACH ROW
    EXECUTE FUNCTION sync_reserved_quantities();

-- ==============================================================================
-- PRODUCTION MANAGEMENT FUNCTIONS
-- ==============================================================================

-- Function to allocate stock for production order (FIFO)
CREATE OR REPLACE FUNCTION allocate_production_order_stock(
    p_production_order_id INTEGER
)
RETURNS TEXT AS $$
DECLARE
    po_record RECORD;
    component_record RECORD;
    inventory_record RECORD;
    remaining_qty DECIMAL(15,4);
    allocate_qty DECIMAL(15,4);
    allocation_log TEXT := '';
BEGIN
    -- Get production order details
    SELECT po.*, p.product_code
    INTO po_record
    FROM production_orders po
    JOIN products p ON po.product_id = p.product_id
    WHERE po.production_order_id = p_production_order_id;
    
    IF po_record IS NULL THEN
        RETURN 'ERROR: Production order not found';
    END IF;
    
    IF po_record.status NOT IN ('PLANNED', 'RELEASED') THEN
        RETURN 'ERROR: Production order must be in PLANNED or RELEASED status';
    END IF;
    
    allocation_log := 'Allocating stock for Production Order ' || po_record.order_number || E'\n';
    
    -- Process each component
    FOR component_record IN
        SELECT poc.*, p.product_code, p.product_name
        FROM production_order_components poc
        JOIN products p ON poc.component_product_id = p.product_id
        WHERE poc.production_order_id = p_production_order_id
        ORDER BY poc.po_component_id
    LOOP
        remaining_qty := component_record.required_quantity - component_record.allocated_quantity;
        
        IF remaining_qty > 0 THEN
            allocation_log := allocation_log || 'Component: ' || component_record.product_code || 
                            ' - Need: ' || remaining_qty || E'\n';
            
            -- Get available inventory in FIFO order
            FOR inventory_record IN
                SELECT * FROM get_fifo_inventory(
                    component_record.component_product_id, 
                    po_record.warehouse_id
                )
                WHERE available_quantity > 0
                ORDER BY entry_date, inventory_item_id
            LOOP
                allocate_qty := LEAST(remaining_qty, inventory_record.available_quantity);
                
                -- Create stock allocation
                INSERT INTO stock_allocations (
                    production_order_id,
                    inventory_item_id,
                    allocated_quantity
                ) VALUES (
                    p_production_order_id,
                    inventory_record.inventory_item_id,
                    allocate_qty
                );
                
                -- Update component allocated quantity
                UPDATE production_order_components
                SET allocated_quantity = allocated_quantity + allocate_qty
                WHERE po_component_id = component_record.po_component_id;
                
                allocation_log := allocation_log || '  Allocated: ' || allocate_qty || 
                                ' from batch ' || inventory_record.batch_number || E'\n';
                
                remaining_qty := remaining_qty - allocate_qty;
                
                EXIT WHEN remaining_qty <= 0;
            END LOOP;
            
            IF remaining_qty > 0 THEN
                allocation_log := allocation_log || '  WARNING: Short ' || remaining_qty || 
                                ' units for ' || component_record.product_code || E'\n';
            END IF;
        END IF;
    END LOOP;
    
    -- Update production order status if fully allocated
    IF NOT EXISTS (
        SELECT 1 FROM production_order_components 
        WHERE production_order_id = p_production_order_id 
          AND allocation_status IN ('NOT_ALLOCATED', 'PARTIALLY_ALLOCATED')
    ) THEN
        UPDATE production_orders 
        SET status = 'RELEASED'
        WHERE production_order_id = p_production_order_id;
        allocation_log := allocation_log || 'Production order status updated to RELEASED' || E'\n';
    END IF;
    
    RETURN allocation_log;
END;
$$ LANGUAGE plpgsql;

-- Function to consume allocated stock (actual production consumption)
CREATE OR REPLACE FUNCTION consume_allocated_stock(
    p_production_order_id INTEGER,
    p_component_product_id INTEGER,
    p_consume_quantity DECIMAL(15,4)
)
RETURNS TEXT AS $$
DECLARE
    allocation_record RECORD;
    remaining_consume DECIMAL(15,4) := p_consume_quantity;
    consume_from_allocation DECIMAL(15,4);
    consumption_log TEXT := '';
    component_unit_cost DECIMAL(15,4);
BEGIN
    consumption_log := 'Consuming ' || p_consume_quantity || ' units for component ' || 
                      p_component_product_id || E'\n';
    
    -- Process allocations in FIFO order
    FOR allocation_record IN
        SELECT sa.*, ii.unit_cost, ii.batch_number
        FROM stock_allocations sa
        JOIN inventory_items ii ON sa.inventory_item_id = ii.inventory_item_id
        WHERE sa.production_order_id = p_production_order_id
          AND ii.product_id = p_component_product_id
          AND sa.remaining_allocation > 0
        ORDER BY ii.entry_date, sa.allocation_id
    LOOP
        consume_from_allocation := LEAST(remaining_consume, allocation_record.remaining_allocation);
        
        -- Update stock allocation
        UPDATE stock_allocations
        SET consumed_quantity = consumed_quantity + consume_from_allocation
        WHERE allocation_id = allocation_record.allocation_id;
        
        -- Update inventory item
        UPDATE inventory_items
        SET quantity_in_stock = quantity_in_stock - consume_from_allocation
        WHERE inventory_item_id = allocation_record.inventory_item_id;
        
        -- Track unit cost for component
        component_unit_cost := allocation_record.unit_cost;
        
        consumption_log := consumption_log || '  Consumed: ' || consume_from_allocation || 
                          ' from batch ' || allocation_record.batch_number || 
                          ' at cost ' || allocation_record.unit_cost || E'\n';
        
        remaining_consume := remaining_consume - consume_from_allocation;
        
        EXIT WHEN remaining_consume <= 0;
    END LOOP;
    
    -- Update production order component
    UPDATE production_order_components
    SET consumed_quantity = consumed_quantity + (p_consume_quantity - remaining_consume),
        unit_cost = COALESCE(component_unit_cost, unit_cost)
    WHERE production_order_id = p_production_order_id
      AND component_product_id = p_component_product_id;
    
    IF remaining_consume > 0 THEN
        consumption_log := consumption_log || 'WARNING: Could not consume ' || remaining_consume || 
                          ' units - insufficient allocation' || E'\n';
    END IF;
    
    RETURN consumption_log;
END;
$$ LANGUAGE plpgsql;

-- Function to complete production order
CREATE OR REPLACE FUNCTION complete_production_order(
    p_production_order_id INTEGER,
    p_completed_quantity DECIMAL(15,4),
    p_scrapped_quantity DECIMAL(15,4) DEFAULT 0
)
RETURNS TEXT AS $$
DECLARE
    po_record RECORD;
    completion_log TEXT := '';
    total_material_cost DECIMAL(15,4) := 0;
BEGIN
    -- Get production order details
    SELECT * INTO po_record
    FROM production_orders
    WHERE production_order_id = p_production_order_id;
    
    IF po_record IS NULL THEN
        RETURN 'ERROR: Production order not found';
    END IF;
    
    -- Calculate total material cost
    SELECT COALESCE(SUM(total_cost), 0)
    INTO total_material_cost
    FROM production_order_components
    WHERE production_order_id = p_production_order_id;
    
    -- Update production order
    UPDATE production_orders
    SET completed_quantity = p_completed_quantity,
        scrapped_quantity = p_scrapped_quantity,
        actual_completion_date = CURRENT_DATE,
        actual_cost = total_material_cost + 
                     (labor_cost_per_unit * p_completed_quantity) + 
                     (overhead_cost_per_unit * p_completed_quantity),
        status = CASE 
            WHEN (p_completed_quantity + p_scrapped_quantity) >= planned_quantity THEN 'COMPLETED'
            ELSE 'IN_PROGRESS'
        END
    FROM bill_of_materials bom
    WHERE production_orders.production_order_id = p_production_order_id
      AND production_orders.bom_id = bom.bom_id;
    
    -- Add completed quantity to inventory
    IF p_completed_quantity > 0 THEN
        INSERT INTO inventory_items (
            product_id,
            warehouse_id,
            batch_number,
            entry_date,
            quantity_in_stock,
            unit_cost,
            supplier_id,
            location_in_warehouse
        )
        SELECT 
            po_record.product_id,
            po_record.warehouse_id,
            'PROD-' || po_record.order_number,
            CURRENT_TIMESTAMP,
            p_completed_quantity,
            (total_material_cost + 
             (COALESCE(bom.labor_cost_per_unit, 0) * p_completed_quantity) +
             (COALESCE(bom.overhead_cost_per_unit, 0) * p_completed_quantity)) / p_completed_quantity,
            NULL,
            'PRODUCTION'
        FROM bill_of_materials bom
        WHERE bom.bom_id = po_record.bom_id;
        
        completion_log := completion_log || 'Added ' || p_completed_quantity || 
                         ' units to inventory' || E'\n';
    END IF;
    
    completion_log := completion_log || 'Production order completed with cost: ' || 
                     total_material_cost || E'\n';
    
    RETURN completion_log;
END;
$$ LANGUAGE plpgsql;

-- ==============================================================================
-- INDEXES FOR PRODUCTION PERFORMANCE
-- ==============================================================================

-- Production order indexes
CREATE INDEX idx_production_orders_status ON production_orders(status, planned_start_date);
CREATE INDEX idx_production_orders_product ON production_orders(product_id, order_date);
CREATE INDEX idx_production_orders_dates ON production_orders(planned_start_date, planned_completion_date)
    WHERE status IN ('PLANNED', 'RELEASED', 'IN_PROGRESS');
CREATE INDEX idx_production_orders_priority ON production_orders(priority, status)
    WHERE status IN ('PLANNED', 'RELEASED', 'IN_PROGRESS');

-- Production order components indexes
CREATE INDEX idx_po_components_production_order ON production_order_components(production_order_id);
CREATE INDEX idx_po_components_product ON production_order_components(component_product_id);
CREATE INDEX idx_po_components_allocation_status ON production_order_components(allocation_status)
    WHERE allocation_status IN ('NOT_ALLOCATED', 'PARTIALLY_ALLOCATED');

-- Stock allocations indexes
CREATE INDEX idx_stock_allocations_production_order ON stock_allocations(production_order_id);
CREATE INDEX idx_stock_allocations_inventory_item ON stock_allocations(inventory_item_id);
CREATE INDEX idx_stock_allocations_status ON stock_allocations(status)
    WHERE status IN ('ALLOCATED', 'PARTIALLY_CONSUMED');

-- Composite indexes for common queries
CREATE INDEX idx_production_fifo_lookup ON stock_allocations(production_order_id, inventory_item_id)
    WHERE status IN ('ALLOCATED', 'PARTIALLY_CONSUMED');

-- ==============================================================================
-- VIEWS FOR PRODUCTION REPORTING
-- ==============================================================================

-- Production order status summary
CREATE VIEW production_order_status_summary AS
SELECT 
    po.production_order_id,
    po.order_number,
    p.product_code,
    p.product_name,
    w.warehouse_name,
    po.status,
    po.planned_quantity,
    po.completed_quantity,
    po.scrapped_quantity,
    po.planned_start_date,
    po.planned_completion_date,
    po.actual_start_date,
    po.actual_completion_date,
    po.estimated_cost,
    po.actual_cost,
    COUNT(poc.po_component_id) as component_count,
    COUNT(CASE WHEN poc.allocation_status = 'FULLY_ALLOCATED' THEN 1 END) as fully_allocated_components,
    CASE 
        WHEN COUNT(poc.po_component_id) = COUNT(CASE WHEN poc.allocation_status = 'FULLY_ALLOCATED' THEN 1 END) 
        THEN 'READY'
        WHEN COUNT(CASE WHEN poc.allocation_status IN ('PARTIALLY_ALLOCATED', 'FULLY_ALLOCATED') THEN 1 END) > 0
        THEN 'PARTIALLY_READY'
        ELSE 'NOT_READY'
    END as readiness_status
FROM production_orders po
JOIN products p ON po.product_id = p.product_id
JOIN warehouses w ON po.warehouse_id = w.warehouse_id
LEFT JOIN production_order_components poc ON po.production_order_id = poc.production_order_id
GROUP BY po.production_order_id, po.order_number, p.product_code, p.product_name,
         w.warehouse_name, po.status, po.planned_quantity, po.completed_quantity,
         po.scrapped_quantity, po.planned_start_date, po.planned_completion_date,
         po.actual_start_date, po.actual_completion_date, po.estimated_cost, po.actual_cost;

COMMENT ON VIEW production_order_status_summary IS 'Comprehensive production order status with material readiness';

-- ==============================================================================
-- GRANTS AND PERMISSIONS
-- ==============================================================================

-- Grant permissions to application roles (uncomment when roles are created)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON production_orders TO mrp_admin;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON production_order_components TO mrp_admin;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON stock_allocations TO mrp_admin;

-- GRANT SELECT, INSERT, UPDATE ON production_orders TO mrp_production_manager;
-- GRANT SELECT, INSERT, UPDATE ON production_order_components TO mrp_production_manager;
-- GRANT SELECT, INSERT, UPDATE ON stock_allocations TO mrp_production_manager;

-- GRANT SELECT ON production_orders TO mrp_readonly;
-- GRANT SELECT ON production_order_components TO mrp_readonly;
-- GRANT SELECT ON stock_allocations TO mrp_readonly;
-- GRANT SELECT ON production_order_status_summary TO mrp_readonly;

-- ==============================================================================
-- SCRIPT COMPLETION
-- ==============================================================================

SELECT 'Production Management Tables Created Successfully' AS status,
       'FIFO stock allocation system enabled' AS allocation_status,
       'Production tracking and costing ready' AS tracking_status,
       'Automated status management installed' AS automation_status;