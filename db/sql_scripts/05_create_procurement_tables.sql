-- ==============================================================================
-- Horoz Demir MRP System - Procurement Tables
-- ==============================================================================
-- This script creates the procurement tables for managing purchase orders
-- and supplier relationships for material acquisition
-- ==============================================================================

-- Drop tables if they exist (in reverse dependency order)
DROP TABLE IF EXISTS purchase_order_items CASCADE;
DROP TABLE IF EXISTS purchase_orders CASCADE;

-- ==============================================================================
-- PURCHASE_ORDERS TABLE
-- ==============================================================================
-- Main purchase order tracking table for material procurement from suppliers
-- Supports multiple currencies and delivery tracking
-- ==============================================================================

CREATE TABLE purchase_orders (
    purchase_order_id SERIAL PRIMARY KEY,
    po_number VARCHAR(50) UNIQUE NOT NULL,
    supplier_id INTEGER NOT NULL,
    warehouse_id INTEGER NOT NULL,
    order_date DATE NOT NULL DEFAULT CURRENT_DATE,
    expected_delivery_date DATE,
    actual_delivery_date DATE,
    total_amount DECIMAL(15,4) NOT NULL DEFAULT 0,
    currency VARCHAR(3) DEFAULT 'USD',
    payment_terms VARCHAR(100),
    status VARCHAR(20) DEFAULT 'DRAFT',
    notes TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    CONSTRAINT fk_purchase_orders_supplier 
        FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id) ON DELETE CASCADE,
    CONSTRAINT fk_purchase_orders_warehouse 
        FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id) ON DELETE CASCADE,
    
    -- Business rule constraints
    CONSTRAINT chk_purchase_order_status CHECK (
        status IN ('DRAFT', 'SENT', 'CONFIRMED', 'PARTIALLY_RECEIVED', 'FULLY_RECEIVED', 'CANCELLED')
    ),
    CONSTRAINT chk_purchase_order_total CHECK (total_amount >= 0),
    CONSTRAINT chk_purchase_order_currency CHECK (
        currency ~ '^[A-Z]{3}$'
    ),
    CONSTRAINT chk_purchase_order_dates CHECK (
        (expected_delivery_date IS NULL OR expected_delivery_date >= order_date) AND
        (actual_delivery_date IS NULL OR actual_delivery_date >= order_date)
    ),
    CONSTRAINT chk_purchase_order_number_format CHECK (
        po_number ~ '^PUR[0-9]{6}$'
    )
);

-- Add table and column comments
COMMENT ON TABLE purchase_orders IS 'Purchase orders for material procurement from suppliers';
COMMENT ON COLUMN purchase_orders.po_number IS 'Unique purchase order number in format PUR######';
COMMENT ON COLUMN purchase_orders.status IS 'Order status: DRAFT, SENT, CONFIRMED, PARTIALLY_RECEIVED, FULLY_RECEIVED, CANCELLED';
COMMENT ON COLUMN purchase_orders.currency IS '3-letter ISO currency code (e.g., USD, EUR, GBP)';
COMMENT ON COLUMN purchase_orders.total_amount IS 'Total order amount calculated from line items';

-- ==============================================================================
-- PURCHASE_ORDER_ITEMS TABLE
-- ==============================================================================
-- Individual line items within purchase orders with quantity and pricing details
-- Tracks ordering, receiving, and delivery status for each item
-- ==============================================================================

CREATE TABLE purchase_order_items (
    po_item_id SERIAL PRIMARY KEY,
    purchase_order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity_ordered DECIMAL(15,4) NOT NULL,
    quantity_received DECIMAL(15,4) DEFAULT 0,
    unit_price DECIMAL(15,4) NOT NULL,
    total_price DECIMAL(15,4) GENERATED ALWAYS AS (quantity_ordered * unit_price) STORED,
    delivery_status VARCHAR(20) DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    CONSTRAINT fk_po_items_purchase_order 
        FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(purchase_order_id) ON DELETE CASCADE,
    CONSTRAINT fk_po_items_product 
        FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE,
    
    -- Business rule constraints
    CONSTRAINT chk_po_item_quantities CHECK (
        quantity_ordered > 0 AND 
        quantity_received >= 0 AND 
        quantity_received <= quantity_ordered
    ),
    CONSTRAINT chk_po_item_unit_price CHECK (unit_price > 0),
    CONSTRAINT chk_po_item_delivery_status CHECK (
        delivery_status IN ('PENDING', 'PARTIALLY_RECEIVED', 'FULLY_RECEIVED', 'CANCELLED')
    ),
    
    -- Unique constraint to prevent duplicate products per purchase order
    CONSTRAINT uk_po_item_product UNIQUE (purchase_order_id, product_id)
);

-- Add table and column comments
COMMENT ON TABLE purchase_order_items IS 'Individual line items within purchase orders';
COMMENT ON COLUMN purchase_order_items.quantity_ordered IS 'Quantity ordered from supplier';
COMMENT ON COLUMN purchase_order_items.quantity_received IS 'Quantity actually received';
COMMENT ON COLUMN purchase_order_items.total_price IS 'Calculated field: quantity_ordered * unit_price';
COMMENT ON COLUMN purchase_order_items.delivery_status IS 'Delivery status: PENDING, PARTIALLY_RECEIVED, FULLY_RECEIVED, CANCELLED';

-- ==============================================================================
-- TRIGGERS FOR PROCUREMENT MANAGEMENT
-- ==============================================================================

-- Updated timestamp triggers
CREATE TRIGGER trg_purchase_orders_updated_at
    BEFORE UPDATE ON purchase_orders
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_po_items_updated_at
    BEFORE UPDATE ON purchase_order_items
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger to update purchase order total amount
CREATE OR REPLACE FUNCTION update_purchase_order_total()
RETURNS TRIGGER AS $$
DECLARE
    new_total DECIMAL(15,4);
BEGIN
    -- Calculate total from all items
    SELECT COALESCE(SUM(total_price), 0)
    INTO new_total
    FROM purchase_order_items
    WHERE purchase_order_id = COALESCE(NEW.purchase_order_id, OLD.purchase_order_id);
    
    -- Update purchase order total
    UPDATE purchase_orders
    SET total_amount = new_total,
        updated_at = CURRENT_TIMESTAMP
    WHERE purchase_order_id = COALESCE(NEW.purchase_order_id, OLD.purchase_order_id);
    
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_po_total
    AFTER INSERT OR UPDATE OR DELETE ON purchase_order_items
    FOR EACH ROW
    EXECUTE FUNCTION update_purchase_order_total();

-- Trigger to update delivery status based on quantities
CREATE OR REPLACE FUNCTION update_delivery_status()
RETURNS TRIGGER AS $$
BEGIN
    -- Update item delivery status
    IF NEW.quantity_received = 0 THEN
        NEW.delivery_status := 'PENDING';
    ELSIF NEW.quantity_received < NEW.quantity_ordered THEN
        NEW.delivery_status := 'PARTIALLY_RECEIVED';
    ELSE
        NEW.delivery_status := 'FULLY_RECEIVED';
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_po_item_delivery_status
    BEFORE INSERT OR UPDATE ON purchase_order_items
    FOR EACH ROW
    EXECUTE FUNCTION update_delivery_status();

-- Trigger to update purchase order status based on items
CREATE OR REPLACE FUNCTION update_purchase_order_status()
RETURNS TRIGGER AS $$
DECLARE
    total_items INTEGER;
    pending_items INTEGER;
    fully_received_items INTEGER;
    new_status VARCHAR(20);
BEGIN
    -- Get item counts
    SELECT 
        COUNT(*),
        COUNT(CASE WHEN delivery_status = 'PENDING' THEN 1 END),
        COUNT(CASE WHEN delivery_status = 'FULLY_RECEIVED' THEN 1 END)
    INTO total_items, pending_items, fully_received_items
    FROM purchase_order_items
    WHERE purchase_order_id = COALESCE(NEW.purchase_order_id, OLD.purchase_order_id);
    
    -- Determine new status
    IF fully_received_items = total_items AND total_items > 0 THEN
        new_status := 'FULLY_RECEIVED';
    ELSIF fully_received_items > 0 THEN
        new_status := 'PARTIALLY_RECEIVED';
    ELSE
        -- Keep existing status if no items received
        SELECT status INTO new_status
        FROM purchase_orders
        WHERE purchase_order_id = COALESCE(NEW.purchase_order_id, OLD.purchase_order_id);
    END IF;
    
    -- Update purchase order status
    UPDATE purchase_orders
    SET status = new_status,
        updated_at = CURRENT_TIMESTAMP,
        actual_delivery_date = CASE 
            WHEN new_status = 'FULLY_RECEIVED' AND actual_delivery_date IS NULL 
            THEN CURRENT_DATE
            ELSE actual_delivery_date
        END
    WHERE purchase_order_id = COALESCE(NEW.purchase_order_id, OLD.purchase_order_id);
    
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_purchase_order_status
    AFTER INSERT OR UPDATE ON purchase_order_items
    FOR EACH ROW
    EXECUTE FUNCTION update_purchase_order_status();

-- ==============================================================================
-- PROCUREMENT MANAGEMENT FUNCTIONS
-- ==============================================================================

-- Function to receive materials from purchase order
CREATE OR REPLACE FUNCTION receive_purchase_order_items(
    p_po_item_id INTEGER,
    p_quantity_received DECIMAL(15,4),
    p_batch_number VARCHAR(50) DEFAULT NULL,
    p_quality_status VARCHAR(20) DEFAULT 'APPROVED'
)
RETURNS TEXT AS $$
DECLARE
    po_item_record RECORD;
    po_record RECORD;
    new_batch_number VARCHAR(50);
    receiving_log TEXT := '';
BEGIN
    -- Get purchase order item details
    SELECT poi.*, po.supplier_id, po.warehouse_id, po.po_number, p.product_code
    INTO po_item_record
    FROM purchase_order_items poi
    JOIN purchase_orders po ON poi.purchase_order_id = po.purchase_order_id
    JOIN products p ON poi.product_id = p.product_id
    WHERE poi.po_item_id = p_po_item_id;
    
    IF po_item_record IS NULL THEN
        RETURN 'ERROR: Purchase order item not found';
    END IF;
    
    -- Check if quantity is valid
    IF p_quantity_received <= 0 THEN
        RETURN 'ERROR: Received quantity must be greater than zero';
    END IF;
    
    IF (po_item_record.quantity_received + p_quantity_received) > po_item_record.quantity_ordered THEN
        RETURN 'ERROR: Cannot receive more than ordered quantity';
    END IF;
    
    -- Generate batch number if not provided
    IF p_batch_number IS NULL THEN
        new_batch_number := 'PO-' || po_item_record.po_number || '-' || 
                           EXTRACT(YEAR FROM CURRENT_DATE) || 
                           LPAD(EXTRACT(DOY FROM CURRENT_DATE)::TEXT, 3, '0');
    ELSE
        new_batch_number := p_batch_number;
    END IF;
    
    -- Update purchase order item
    UPDATE purchase_order_items
    SET quantity_received = quantity_received + p_quantity_received
    WHERE po_item_id = p_po_item_id;
    
    -- Add to inventory
    INSERT INTO inventory_items (
        product_id,
        warehouse_id,
        batch_number,
        entry_date,
        quantity_in_stock,
        unit_cost,
        supplier_id,
        purchase_order_id,
        quality_status,
        location_in_warehouse
    ) VALUES (
        po_item_record.product_id,
        po_item_record.warehouse_id,
        new_batch_number,
        CURRENT_TIMESTAMP,
        p_quantity_received,
        po_item_record.unit_price,
        po_item_record.supplier_id,
        po_item_record.purchase_order_id,
        p_quality_status,
        'RECEIVING'
    );
    
    receiving_log := 'Received ' || p_quantity_received || ' units of ' || 
                    po_item_record.product_code || ' into batch ' || new_batch_number;
    
    -- Update product standard cost if this is a better price
    UPDATE products
    SET standard_cost = CASE 
        WHEN standard_cost = 0 OR po_item_record.unit_price < standard_cost 
        THEN po_item_record.unit_price
        ELSE standard_cost
    END
    WHERE product_id = po_item_record.product_id;
    
    RETURN receiving_log;
END;
$$ LANGUAGE plpgsql;

-- Function to create purchase order from requirements
CREATE OR REPLACE FUNCTION create_purchase_order_from_requirements(
    p_supplier_id INTEGER,
    p_warehouse_id INTEGER,
    p_product_requirements JSONB -- Format: [{"product_id": 1, "quantity": 100}, ...]
)
RETURNS TEXT AS $$
DECLARE
    new_po_number VARCHAR(50);
    new_po_id INTEGER;
    requirement JSONB;
    product_record RECORD;
    supplier_record RECORD;
    creation_log TEXT := '';
    total_items INTEGER := 0;
BEGIN
    -- Get supplier details
    SELECT * INTO supplier_record
    FROM suppliers
    WHERE supplier_id = p_supplier_id AND is_active = TRUE;
    
    IF supplier_record IS NULL THEN
        RETURN 'ERROR: Supplier not found or inactive';
    END IF;
    
    -- Generate PO number
    new_po_number := 'PUR' || LPAD(nextval('purchase_orders_purchase_order_id_seq')::TEXT, 6, '0');
    
    -- Create purchase order
    INSERT INTO purchase_orders (
        po_number,
        supplier_id,
        warehouse_id,
        expected_delivery_date,
        payment_terms,
        status,
        created_by
    ) VALUES (
        new_po_number,
        p_supplier_id,
        p_warehouse_id,
        CURRENT_DATE + INTERVAL '1 day' * supplier_record.lead_time_days,
        supplier_record.payment_terms,
        'DRAFT',
        'SYSTEM'
    ) RETURNING purchase_order_id INTO new_po_id;
    
    creation_log := 'Created Purchase Order ' || new_po_number || ' for supplier ' || 
                   supplier_record.supplier_name || E'\n';
    
    -- Add items to purchase order
    FOR requirement IN SELECT * FROM jsonb_array_elements(p_product_requirements)
    LOOP
        -- Get product and supplier pricing
        SELECT p.*, ps.unit_price, ps.minimum_order_qty
        INTO product_record
        FROM products p
        LEFT JOIN product_suppliers ps ON p.product_id = ps.product_id AND ps.supplier_id = p_supplier_id
        WHERE p.product_id = (requirement->>'product_id')::INTEGER
          AND p.is_active = TRUE;
        
        IF product_record IS NULL THEN
            creation_log := creation_log || 'WARNING: Product ' || (requirement->>'product_id') || ' not found or inactive' || E'\n';
            CONTINUE;
        END IF;
        
        IF product_record.unit_price IS NULL THEN
            creation_log := creation_log || 'WARNING: No pricing found for product ' || 
                           product_record.product_code || ' from supplier ' || supplier_record.supplier_name || E'\n';
            CONTINUE;
        END IF;
        
        -- Insert purchase order item
        INSERT INTO purchase_order_items (
            purchase_order_id,
            product_id,
            quantity_ordered,
            unit_price
        ) VALUES (
            new_po_id,
            product_record.product_id,
            GREATEST((requirement->>'quantity')::DECIMAL(15,4), product_record.minimum_order_qty),
            product_record.unit_price
        );
        
        total_items := total_items + 1;
        creation_log := creation_log || 'Added ' || (requirement->>'quantity') || ' units of ' || 
                       product_record.product_code || ' at ' || product_record.unit_price || ' each' || E'\n';
    END LOOP;
    
    IF total_items = 0 THEN
        -- Delete empty purchase order
        DELETE FROM purchase_orders WHERE purchase_order_id = new_po_id;
        RETURN 'ERROR: No valid items could be added to purchase order';
    END IF;
    
    creation_log := creation_log || 'Purchase order created with ' || total_items || ' items';
    RETURN creation_log;
END;
$$ LANGUAGE plpgsql;

-- Function to get purchase order summary
CREATE OR REPLACE FUNCTION get_purchase_order_summary(p_purchase_order_id INTEGER)
RETURNS TABLE (
    po_number VARCHAR(50),
    supplier_name VARCHAR(200),
    warehouse_name VARCHAR(100),
    status VARCHAR(20),
    order_date DATE,
    expected_delivery_date DATE,
    actual_delivery_date DATE,
    total_amount DECIMAL(15,4),
    currency VARCHAR(3),
    item_count INTEGER,
    items_fully_received INTEGER,
    completion_percentage DECIMAL(5,2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        po.po_number,
        s.supplier_name,
        w.warehouse_name,
        po.status,
        po.order_date,
        po.expected_delivery_date,
        po.actual_delivery_date,
        po.total_amount,
        po.currency,
        COUNT(poi.po_item_id)::INTEGER as item_count,
        COUNT(CASE WHEN poi.delivery_status = 'FULLY_RECEIVED' THEN 1 END)::INTEGER as items_fully_received,
        CASE 
            WHEN COUNT(poi.po_item_id) > 0 
            THEN (COUNT(CASE WHEN poi.delivery_status = 'FULLY_RECEIVED' THEN 1 END) * 100.0 / COUNT(poi.po_item_id))
            ELSE 0
        END as completion_percentage
    FROM purchase_orders po
    JOIN suppliers s ON po.supplier_id = s.supplier_id
    JOIN warehouses w ON po.warehouse_id = w.warehouse_id
    LEFT JOIN purchase_order_items poi ON po.purchase_order_id = poi.purchase_order_id
    WHERE po.purchase_order_id = p_purchase_order_id
    GROUP BY po.po_number, s.supplier_name, w.warehouse_name, po.status,
             po.order_date, po.expected_delivery_date, po.actual_delivery_date,
             po.total_amount, po.currency;
END;
$$ LANGUAGE plpgsql;

-- ==============================================================================
-- INDEXES FOR PROCUREMENT PERFORMANCE
-- ==============================================================================

-- Purchase order indexes
CREATE INDEX idx_purchase_orders_supplier ON purchase_orders(supplier_id, order_date);
CREATE INDEX idx_purchase_orders_status ON purchase_orders(status, order_date);
CREATE INDEX idx_purchase_orders_delivery_date ON purchase_orders(expected_delivery_date)
    WHERE status IN ('SENT', 'CONFIRMED', 'PARTIALLY_RECEIVED');
CREATE INDEX idx_purchase_orders_warehouse ON purchase_orders(warehouse_id, status);

-- Purchase order items indexes
CREATE INDEX idx_po_items_purchase_order ON purchase_order_items(purchase_order_id);
CREATE INDEX idx_po_items_product ON purchase_order_items(product_id);
CREATE INDEX idx_po_items_delivery_status ON purchase_order_items(delivery_status)
    WHERE delivery_status IN ('PENDING', 'PARTIALLY_RECEIVED');

-- Performance optimization indexes
CREATE INDEX idx_procurement_performance ON purchase_order_items(product_id, delivery_status, updated_at);

-- ==============================================================================
-- VIEWS FOR PROCUREMENT REPORTING
-- ==============================================================================

-- Purchase order summary view
CREATE VIEW purchase_order_summary AS
SELECT 
    po.purchase_order_id,
    po.po_number,
    s.supplier_name,
    s.supplier_code,
    w.warehouse_name,
    w.warehouse_code,
    po.status,
    po.order_date,
    po.expected_delivery_date,
    po.actual_delivery_date,
    po.total_amount,
    po.currency,
    COUNT(poi.po_item_id) as item_count,
    COUNT(CASE WHEN poi.delivery_status = 'FULLY_RECEIVED' THEN 1 END) as items_fully_received,
    COUNT(CASE WHEN poi.delivery_status = 'PENDING' THEN 1 END) as items_pending,
    CASE 
        WHEN COUNT(poi.po_item_id) > 0 
        THEN ROUND((COUNT(CASE WHEN poi.delivery_status = 'FULLY_RECEIVED' THEN 1 END) * 100.0 / COUNT(poi.po_item_id)), 2)
        ELSE 0
    END as completion_percentage,
    CASE 
        WHEN po.expected_delivery_date < CURRENT_DATE AND po.status NOT IN ('FULLY_RECEIVED', 'CANCELLED')
        THEN TRUE
        ELSE FALSE
    END as is_overdue
FROM purchase_orders po
JOIN suppliers s ON po.supplier_id = s.supplier_id
JOIN warehouses w ON po.warehouse_id = w.warehouse_id
LEFT JOIN purchase_order_items poi ON po.purchase_order_id = poi.purchase_order_id
GROUP BY po.purchase_order_id, po.po_number, s.supplier_name, s.supplier_code,
         w.warehouse_name, w.warehouse_code, po.status, po.order_date,
         po.expected_delivery_date, po.actual_delivery_date, po.total_amount, po.currency;

COMMENT ON VIEW purchase_order_summary IS 'Comprehensive purchase order summary with delivery status and completion metrics';

-- Supplier performance view
CREATE VIEW supplier_performance_summary AS
SELECT 
    s.supplier_id,
    s.supplier_code,
    s.supplier_name,
    COUNT(po.purchase_order_id) as total_orders,
    COUNT(CASE WHEN po.status = 'FULLY_RECEIVED' THEN 1 END) as completed_orders,
    COUNT(CASE WHEN po.expected_delivery_date < po.actual_delivery_date THEN 1 END) as late_deliveries,
    COUNT(CASE WHEN po.expected_delivery_date < CURRENT_DATE AND po.status NOT IN ('FULLY_RECEIVED', 'CANCELLED') THEN 1 END) as overdue_orders,
    SUM(po.total_amount) as total_order_value,
    AVG(CASE WHEN po.actual_delivery_date IS NOT NULL AND po.expected_delivery_date IS NOT NULL 
             THEN po.actual_delivery_date - po.expected_delivery_date END) as avg_delivery_delay_days,
    CASE 
        WHEN COUNT(po.purchase_order_id) > 0 
        THEN ROUND((COUNT(CASE WHEN po.status = 'FULLY_RECEIVED' THEN 1 END) * 100.0 / COUNT(po.purchase_order_id)), 2)
        ELSE 0
    END as completion_rate,
    CASE 
        WHEN COUNT(CASE WHEN po.actual_delivery_date IS NOT NULL THEN 1 END) > 0 
        THEN ROUND((COUNT(CASE WHEN po.actual_delivery_date <= po.expected_delivery_date THEN 1 END) * 100.0 / 
                   COUNT(CASE WHEN po.actual_delivery_date IS NOT NULL THEN 1 END)), 2)
        ELSE 0
    END as on_time_delivery_rate
FROM suppliers s
LEFT JOIN purchase_orders po ON s.supplier_id = po.supplier_id
WHERE s.is_active = TRUE
GROUP BY s.supplier_id, s.supplier_code, s.supplier_name;

COMMENT ON VIEW supplier_performance_summary IS 'Supplier performance metrics including completion rates and delivery performance';

-- ==============================================================================
-- GRANTS AND PERMISSIONS
-- ==============================================================================

-- Grant permissions to application roles (uncomment when roles are created)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON purchase_orders TO mrp_admin;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON purchase_order_items TO mrp_admin;

-- GRANT SELECT, INSERT, UPDATE ON purchase_orders TO mrp_procurement_manager;
-- GRANT SELECT, INSERT, UPDATE ON purchase_order_items TO mrp_procurement_manager;

-- GRANT SELECT ON purchase_orders TO mrp_readonly;
-- GRANT SELECT ON purchase_order_items TO mrp_readonly;
-- GRANT SELECT ON purchase_order_summary TO mrp_readonly;
-- GRANT SELECT ON supplier_performance_summary TO mrp_readonly;

-- ==============================================================================
-- SCRIPT COMPLETION
-- ==============================================================================

SELECT 'Procurement Tables Created Successfully' AS status,
       'Purchase order management system ready' AS po_status,
       'Supplier performance tracking enabled' AS performance_status,
       'Automated receiving workflow installed' AS receiving_status;