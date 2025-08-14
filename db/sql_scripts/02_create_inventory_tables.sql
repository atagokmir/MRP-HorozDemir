-- ==============================================================================
-- Horoz Demir MRP System - Inventory Management Tables
-- ==============================================================================
-- This script creates the inventory management tables with FIFO support
-- including inventory_items and stock_movements for complete audit trail
-- ==============================================================================

-- Drop tables if they exist (in reverse dependency order)
DROP TABLE IF EXISTS stock_movements CASCADE;
DROP TABLE IF EXISTS inventory_items CASCADE;

-- ==============================================================================
-- INVENTORY_ITEMS TABLE
-- ==============================================================================
-- Core FIFO inventory tracking table with batch-level stock management
-- Each record represents a specific batch/lot of inventory with entry date
-- for FIFO consumption ordering
-- ==============================================================================

CREATE TABLE inventory_items (
    inventory_item_id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL,
    warehouse_id INTEGER NOT NULL,
    batch_number VARCHAR(50) NOT NULL,
    entry_date TIMESTAMP NOT NULL,
    expiry_date TIMESTAMP,
    quantity_in_stock DECIMAL(15,4) NOT NULL DEFAULT 0,
    reserved_quantity DECIMAL(15,4) DEFAULT 0,
    available_quantity DECIMAL(15,4) GENERATED ALWAYS AS (quantity_in_stock - reserved_quantity) STORED,
    unit_cost DECIMAL(15,4) NOT NULL,
    total_cost DECIMAL(15,4) GENERATED ALWAYS AS (quantity_in_stock * unit_cost) STORED,
    supplier_id INTEGER,
    purchase_order_id INTEGER,
    location_in_warehouse VARCHAR(50),
    quality_status VARCHAR(20) DEFAULT 'APPROVED',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    CONSTRAINT fk_inventory_items_product 
        FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE,
    CONSTRAINT fk_inventory_items_warehouse 
        FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id) ON DELETE CASCADE,
    CONSTRAINT fk_inventory_items_supplier 
        FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id) ON DELETE SET NULL,
    
    -- Business rule constraints
    CONSTRAINT chk_inventory_quantities CHECK (
        quantity_in_stock >= 0 AND 
        reserved_quantity >= 0 AND 
        reserved_quantity <= quantity_in_stock
    ),
    CONSTRAINT chk_inventory_unit_cost CHECK (unit_cost >= 0),
    CONSTRAINT chk_inventory_quality_status CHECK (
        quality_status IN ('PENDING', 'APPROVED', 'REJECTED', 'QUARANTINE')
    ),
    CONSTRAINT chk_inventory_batch_format CHECK (
        batch_number ~ '^[A-Z0-9\-]{3,50}$'
    ),
    CONSTRAINT chk_inventory_entry_date CHECK (
        entry_date <= CURRENT_TIMESTAMP
    ),
    CONSTRAINT chk_inventory_expiry_date CHECK (
        expiry_date IS NULL OR expiry_date > entry_date
    ),
    
    -- Unique constraint for FIFO batch tracking
    CONSTRAINT uk_inventory_batch UNIQUE (product_id, warehouse_id, batch_number, entry_date)
);

-- Add table and column comments
COMMENT ON TABLE inventory_items IS 'FIFO inventory tracking with batch-level stock management';
COMMENT ON COLUMN inventory_items.entry_date IS 'Critical for FIFO ordering - first entry date consumed first';
COMMENT ON COLUMN inventory_items.available_quantity IS 'Calculated field: quantity_in_stock - reserved_quantity';
COMMENT ON COLUMN inventory_items.total_cost IS 'Calculated field: quantity_in_stock * unit_cost';
COMMENT ON COLUMN inventory_items.quality_status IS 'Quality control status: PENDING, APPROVED, REJECTED, QUARANTINE';
COMMENT ON COLUMN inventory_items.batch_number IS 'Unique batch identifier for traceability';

-- ==============================================================================
-- STOCK_MOVEMENTS TABLE
-- ==============================================================================
-- Complete audit trail of all stock movements for inventory tracking
-- Records every IN, OUT, TRANSFER, ADJUSTMENT, PRODUCTION, and RETURN operation
-- ==============================================================================

CREATE TABLE stock_movements (
    movement_id SERIAL PRIMARY KEY,
    inventory_item_id INTEGER NOT NULL,
    movement_type VARCHAR(20) NOT NULL,
    movement_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    quantity DECIMAL(15,4) NOT NULL,
    unit_cost DECIMAL(15,4) NOT NULL,
    total_cost DECIMAL(15,4) GENERATED ALWAYS AS (ABS(quantity) * unit_cost) STORED,
    reference_type VARCHAR(30),
    reference_id INTEGER,
    from_warehouse_id INTEGER,
    to_warehouse_id INTEGER,
    notes TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    CONSTRAINT fk_stock_movements_inventory_item 
        FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(inventory_item_id) ON DELETE CASCADE,
    CONSTRAINT fk_stock_movements_from_warehouse 
        FOREIGN KEY (from_warehouse_id) REFERENCES warehouses(warehouse_id) ON DELETE SET NULL,
    CONSTRAINT fk_stock_movements_to_warehouse 
        FOREIGN KEY (to_warehouse_id) REFERENCES warehouses(warehouse_id) ON DELETE SET NULL,
    
    -- Business rule constraints
    CONSTRAINT chk_movement_type CHECK (
        movement_type IN ('IN', 'OUT', 'TRANSFER', 'ADJUSTMENT', 'PRODUCTION', 'RETURN')
    ),
    CONSTRAINT chk_movement_quantity CHECK (quantity != 0),
    CONSTRAINT chk_movement_unit_cost CHECK (unit_cost >= 0),
    CONSTRAINT chk_movement_reference_type CHECK (
        reference_type IS NULL OR 
        reference_type IN ('PURCHASE_ORDER', 'PRODUCTION_ORDER', 'TRANSFER', 'ADJUSTMENT', 'RETURN', 'SALE')
    ),
    CONSTRAINT chk_movement_date CHECK (movement_date <= CURRENT_TIMESTAMP + INTERVAL '1 hour'),
    
    -- Transfer movements must have both warehouses
    CONSTRAINT chk_transfer_warehouses CHECK (
        (movement_type != 'TRANSFER') OR 
        (movement_type = 'TRANSFER' AND from_warehouse_id IS NOT NULL AND to_warehouse_id IS NOT NULL)
    )
);

-- Add table and column comments
COMMENT ON TABLE stock_movements IS 'Complete audit trail of all inventory movements';
COMMENT ON COLUMN stock_movements.movement_type IS 'Type of movement: IN, OUT, TRANSFER, ADJUSTMENT, PRODUCTION, RETURN';
COMMENT ON COLUMN stock_movements.quantity IS 'Positive for increases, negative for decreases';
COMMENT ON COLUMN stock_movements.total_cost IS 'Calculated field: ABS(quantity) * unit_cost';
COMMENT ON COLUMN stock_movements.reference_type IS 'Type of document causing movement: PURCHASE_ORDER, PRODUCTION_ORDER, etc.';
COMMENT ON COLUMN stock_movements.reference_id IS 'ID of the reference document';

-- ==============================================================================
-- TRIGGERS FOR INVENTORY MANAGEMENT
-- ==============================================================================

-- Updated timestamp trigger function (reuse from master data)
CREATE TRIGGER trg_inventory_items_updated_at
    BEFORE UPDATE ON inventory_items
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ==============================================================================
-- FIFO HELPER FUNCTIONS
-- ==============================================================================

-- Function to get available inventory in FIFO order
CREATE OR REPLACE FUNCTION get_fifo_inventory(
    p_product_id INTEGER,
    p_warehouse_id INTEGER,
    p_required_quantity DECIMAL(15,4) DEFAULT NULL
)
RETURNS TABLE (
    inventory_item_id INTEGER,
    batch_number VARCHAR(50),
    entry_date TIMESTAMP,
    available_quantity DECIMAL(15,4),
    unit_cost DECIMAL(15,4),
    running_total DECIMAL(15,4)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ii.inventory_item_id,
        ii.batch_number,
        ii.entry_date,
        ii.available_quantity,
        ii.unit_cost,
        SUM(ii.available_quantity) OVER (
            ORDER BY ii.entry_date, ii.inventory_item_id
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) as running_total
    FROM inventory_items ii
    WHERE ii.product_id = p_product_id
      AND ii.warehouse_id = p_warehouse_id
      AND ii.available_quantity > 0
      AND ii.quality_status = 'APPROVED'
    ORDER BY ii.entry_date, ii.inventory_item_id;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate FIFO cost for a given quantity
CREATE OR REPLACE FUNCTION calculate_fifo_cost(
    p_product_id INTEGER,
    p_warehouse_id INTEGER,
    p_quantity DECIMAL(15,4)
)
RETURNS DECIMAL(15,4) AS $$
DECLARE
    total_cost DECIMAL(15,4) := 0;
    remaining_qty DECIMAL(15,4) := p_quantity;
    batch_record RECORD;
    consume_qty DECIMAL(15,4);
BEGIN
    -- Loop through available inventory in FIFO order
    FOR batch_record IN 
        SELECT * FROM get_fifo_inventory(p_product_id, p_warehouse_id)
    LOOP
        -- Calculate quantity to consume from this batch
        consume_qty := LEAST(remaining_qty, batch_record.available_quantity);
        
        -- Add to total cost
        total_cost := total_cost + (consume_qty * batch_record.unit_cost);
        
        -- Reduce remaining quantity
        remaining_qty := remaining_qty - consume_qty;
        
        -- Exit if we've consumed enough
        EXIT WHEN remaining_qty <= 0;
    END LOOP;
    
    -- Return null if insufficient inventory
    IF remaining_qty > 0 THEN
        RETURN NULL;
    END IF;
    
    RETURN total_cost;
END;
$$ LANGUAGE plpgsql;

-- Function to check available inventory quantity
CREATE OR REPLACE FUNCTION get_available_inventory_quantity(
    p_product_id INTEGER,
    p_warehouse_id INTEGER
)
RETURNS DECIMAL(15,4) AS $$
BEGIN
    RETURN COALESCE(
        (SELECT SUM(available_quantity) 
         FROM inventory_items 
         WHERE product_id = p_product_id 
           AND warehouse_id = p_warehouse_id 
           AND quality_status = 'APPROVED'
           AND available_quantity > 0),
        0
    );
END;
$$ LANGUAGE plpgsql;

-- ==============================================================================
-- TRIGGERS FOR STOCK MOVEMENT TRACKING
-- ==============================================================================

-- Function to automatically create stock movements when inventory changes
CREATE OR REPLACE FUNCTION track_inventory_changes()
RETURNS TRIGGER AS $$
BEGIN
    -- Handle INSERT (new inventory)
    IF TG_OP = 'INSERT' THEN
        INSERT INTO stock_movements (
            inventory_item_id,
            movement_type,
            quantity,
            unit_cost,
            reference_type,
            reference_id,
            notes
        ) VALUES (
            NEW.inventory_item_id,
            'IN',
            NEW.quantity_in_stock,
            NEW.unit_cost,
            'PURCHASE_ORDER',
            NEW.purchase_order_id,
            'Initial inventory entry for batch ' || NEW.batch_number
        );
        RETURN NEW;
    END IF;
    
    -- Handle UPDATE (quantity changes)
    IF TG_OP = 'UPDATE' THEN
        -- Track quantity changes
        IF OLD.quantity_in_stock != NEW.quantity_in_stock THEN
            INSERT INTO stock_movements (
                inventory_item_id,
                movement_type,
                quantity,
                unit_cost,
                notes
            ) VALUES (
                NEW.inventory_item_id,
                CASE 
                    WHEN NEW.quantity_in_stock > OLD.quantity_in_stock THEN 'IN'
                    ELSE 'OUT'
                END,
                NEW.quantity_in_stock - OLD.quantity_in_stock,
                NEW.unit_cost,
                'Inventory adjustment - quantity changed from ' || 
                OLD.quantity_in_stock || ' to ' || NEW.quantity_in_stock
            );
        END IF;
        
        -- Track reservation changes
        IF OLD.reserved_quantity != NEW.reserved_quantity THEN
            INSERT INTO stock_movements (
                inventory_item_id,
                movement_type,
                quantity,
                unit_cost,
                reference_type,
                notes
            ) VALUES (
                NEW.inventory_item_id,
                'ADJUSTMENT',
                0, -- No quantity change, just reservation
                NEW.unit_cost,
                'RESERVATION',
                'Reserved quantity changed from ' || 
                OLD.reserved_quantity || ' to ' || NEW.reserved_quantity
            );
        END IF;
        
        RETURN NEW;
    END IF;
    
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for inventory change tracking
CREATE TRIGGER trg_inventory_items_track_changes
    AFTER INSERT OR UPDATE ON inventory_items
    FOR EACH ROW
    EXECUTE FUNCTION track_inventory_changes();

-- ==============================================================================
-- INDEXES FOR FIFO PERFORMANCE
-- ==============================================================================

-- Critical FIFO indexes
CREATE INDEX idx_inventory_fifo_order ON inventory_items(product_id, warehouse_id, entry_date, inventory_item_id)
    WHERE quality_status = 'APPROVED' AND available_quantity > 0;

CREATE INDEX idx_inventory_available ON inventory_items(product_id, warehouse_id, available_quantity)
    WHERE available_quantity > 0;

CREATE INDEX idx_inventory_quality ON inventory_items(quality_status, product_id, warehouse_id)
    WHERE quality_status = 'APPROVED';

CREATE INDEX idx_inventory_batch_lookup ON inventory_items(batch_number, entry_date);

-- Stock movement indexes
CREATE INDEX idx_stock_movements_item_date ON stock_movements(inventory_item_id, movement_date DESC);
CREATE INDEX idx_stock_movements_type_date ON stock_movements(movement_type, movement_date DESC);
CREATE INDEX idx_stock_movements_reference ON stock_movements(reference_type, reference_id);

-- Composite indexes for common queries
CREATE INDEX idx_inventory_product_warehouse ON inventory_items(product_id, warehouse_id, quality_status)
    WHERE quantity_in_stock > 0;

-- ==============================================================================
-- VIEWS FOR COMMON INVENTORY QUERIES
-- ==============================================================================

-- Current inventory summary by product and warehouse
CREATE VIEW current_inventory_summary AS
SELECT 
    ii.product_id,
    p.product_code,
    p.product_name,
    ii.warehouse_id,
    w.warehouse_code,
    w.warehouse_name,
    COUNT(*) as batch_count,
    SUM(ii.quantity_in_stock) as total_stock,
    SUM(ii.reserved_quantity) as total_reserved,
    SUM(ii.available_quantity) as total_available,
    MIN(ii.entry_date) as oldest_batch_date,
    MAX(ii.entry_date) as newest_batch_date,
    SUM(ii.total_cost) as total_value,
    CASE 
        WHEN SUM(ii.quantity_in_stock) > 0 
        THEN SUM(ii.total_cost) / SUM(ii.quantity_in_stock)
        ELSE 0 
    END as average_unit_cost
FROM inventory_items ii
JOIN products p ON ii.product_id = p.product_id
JOIN warehouses w ON ii.warehouse_id = w.warehouse_id
WHERE ii.quality_status = 'APPROVED' AND ii.quantity_in_stock > 0
GROUP BY ii.product_id, p.product_code, p.product_name, 
         ii.warehouse_id, w.warehouse_code, w.warehouse_name;

COMMENT ON VIEW current_inventory_summary IS 'Summary of current inventory levels by product and warehouse';

-- FIFO consumption view for next batch to consume
CREATE VIEW fifo_next_consumption AS
SELECT DISTINCT ON (ii.product_id, ii.warehouse_id)
    ii.product_id,
    p.product_code,
    ii.warehouse_id,
    w.warehouse_code,
    ii.inventory_item_id,
    ii.batch_number,
    ii.entry_date,
    ii.available_quantity,
    ii.unit_cost,
    ii.location_in_warehouse
FROM inventory_items ii
JOIN products p ON ii.product_id = p.product_id
JOIN warehouses w ON ii.warehouse_id = w.warehouse_id
WHERE ii.quality_status = 'APPROVED' 
  AND ii.available_quantity > 0
ORDER BY ii.product_id, ii.warehouse_id, ii.entry_date, ii.inventory_item_id;

COMMENT ON VIEW fifo_next_consumption IS 'Next batch to be consumed for each product-warehouse combination (FIFO order)';

-- ==============================================================================
-- GRANTS AND PERMISSIONS
-- ==============================================================================

-- Grant permissions to application roles (uncomment when roles are created)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON inventory_items TO mrp_admin;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON stock_movements TO mrp_admin;
-- GRANT USAGE ON SEQUENCE inventory_items_inventory_item_id_seq TO mrp_admin;
-- GRANT USAGE ON SEQUENCE stock_movements_movement_id_seq TO mrp_admin;

-- GRANT SELECT, INSERT, UPDATE ON inventory_items TO mrp_inventory_clerk;
-- GRANT SELECT, INSERT ON stock_movements TO mrp_inventory_clerk;

-- GRANT SELECT ON inventory_items TO mrp_readonly;
-- GRANT SELECT ON stock_movements TO mrp_readonly;
-- GRANT SELECT ON current_inventory_summary TO mrp_readonly;
-- GRANT SELECT ON fifo_next_consumption TO mrp_readonly;

-- ==============================================================================
-- SCRIPT COMPLETION
-- ==============================================================================

SELECT 'Inventory Management Tables Created Successfully' AS status,
       'FIFO functions and triggers installed' AS fifo_status,
       'Performance indexes created' AS index_status,
       'Audit trail tracking enabled' AS audit_status;