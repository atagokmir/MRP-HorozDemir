-- ==============================================================================
-- Horoz Demir MRP System - Performance Indexes and Additional Constraints
-- ==============================================================================
-- This script creates comprehensive indexes for optimal query performance
-- and additional constraints for data integrity across all MRP operations
-- ==============================================================================

-- ==============================================================================
-- MASTER DATA INDEXES
-- ==============================================================================

-- Warehouses indexes (if not already created)
CREATE INDEX IF NOT EXISTS idx_warehouses_type ON warehouses(warehouse_type);
CREATE INDEX IF NOT EXISTS idx_warehouses_active ON warehouses(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_warehouses_code_lookup ON warehouses(warehouse_code) WHERE is_active = TRUE;

-- Products indexes (enhanced)
CREATE INDEX IF NOT EXISTS idx_products_type_active ON products(product_type, is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_products_stock_levels ON products(product_type, minimum_stock_level, critical_stock_level) 
    WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_products_cost ON products(standard_cost) WHERE standard_cost > 0;
CREATE INDEX IF NOT EXISTS idx_products_search ON products USING gin(to_tsvector('english', product_name || ' ' || COALESCE(description, '')));

-- Suppliers indexes (enhanced)
CREATE INDEX IF NOT EXISTS idx_suppliers_performance_rating ON suppliers(quality_rating, delivery_rating, price_rating)
    WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_suppliers_lead_time ON suppliers(lead_time_days) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_suppliers_search ON suppliers USING gin(to_tsvector('english', supplier_name || ' ' || COALESCE(city, '') || ' ' || COALESCE(country, '')));

-- Product-supplier relationship indexes (enhanced)
CREATE INDEX IF NOT EXISTS idx_product_suppliers_price ON product_suppliers(product_id, unit_price) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_product_suppliers_preferred_active ON product_suppliers(product_id, is_preferred, unit_price) 
    WHERE is_preferred = TRUE AND is_active = TRUE;

-- ==============================================================================
-- INVENTORY FIFO OPTIMIZATION INDEXES
-- ==============================================================================

-- Critical FIFO performance indexes
CREATE INDEX IF NOT EXISTS idx_inventory_fifo_consumption ON inventory_items(product_id, warehouse_id, entry_date, inventory_item_id)
    WHERE quality_status = 'APPROVED' AND available_quantity > 0;

CREATE INDEX IF NOT EXISTS idx_inventory_batch_tracking ON inventory_items(batch_number, entry_date, product_id);

CREATE INDEX IF NOT EXISTS idx_inventory_expiry_tracking ON inventory_items(expiry_date, product_id, warehouse_id)
    WHERE expiry_date IS NOT NULL AND quality_status = 'APPROVED';

-- Composite indexes for complex FIFO queries
CREATE INDEX IF NOT EXISTS idx_inventory_fifo_complex ON inventory_items(warehouse_id, product_id, quality_status, entry_date, available_quantity)
    WHERE quantity_in_stock > 0;

-- Stock movements performance indexes
CREATE INDEX IF NOT EXISTS idx_stock_movements_audit_trail ON stock_movements(movement_date DESC, movement_type, inventory_item_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_reference_lookup ON stock_movements(reference_type, reference_id, movement_date DESC);

-- ==============================================================================
-- BOM HIERARCHY OPTIMIZATION INDEXES
-- ==============================================================================

-- BOM explosion performance indexes
CREATE INDEX IF NOT EXISTS idx_bom_hierarchy_parent ON bill_of_materials(parent_product_id, status, effective_date)
    WHERE status = 'ACTIVE';

CREATE INDEX IF NOT EXISTS idx_bom_components_hierarchy ON bom_components(component_product_id, bom_id);

-- Recursive BOM traversal optimization
CREATE INDEX IF NOT EXISTS idx_bom_explosion_optimization ON bom_components(bom_id, component_product_id, sequence_number);

-- BOM cost calculation indexes
CREATE INDEX IF NOT EXISTS idx_bom_cost_current_lookup ON bom_cost_calculations(bom_id, is_current, calculation_date DESC)
    WHERE is_current = TRUE;

-- Semi-finished product BOM lookup (for nested BOMs)
CREATE INDEX IF NOT EXISTS idx_bom_semi_finished_lookup ON bill_of_materials(parent_product_id, status)
    WHERE parent_product_id IN (
        SELECT product_id FROM products WHERE product_type = 'SEMI_FINISHED'
    );

-- ==============================================================================
-- PRODUCTION MANAGEMENT INDEXES
-- ==============================================================================

-- Production order status and scheduling indexes
CREATE INDEX IF NOT EXISTS idx_production_orders_scheduling ON production_orders(status, planned_start_date, priority)
    WHERE status IN ('PLANNED', 'RELEASED', 'IN_PROGRESS');

CREATE INDEX IF NOT EXISTS idx_production_orders_completion_tracking ON production_orders(actual_completion_date DESC, status)
    WHERE status IN ('COMPLETED', 'IN_PROGRESS');

-- Production order component allocation indexes
CREATE INDEX IF NOT EXISTS idx_po_components_allocation_lookup ON production_order_components(component_product_id, allocation_status)
    WHERE allocation_status IN ('NOT_ALLOCATED', 'PARTIALLY_ALLOCATED');

-- Stock allocation FIFO optimization
CREATE INDEX IF NOT EXISTS idx_stock_allocations_fifo_lookup ON stock_allocations(inventory_item_id, status, allocation_date);

-- Production capacity planning indexes
CREATE INDEX IF NOT EXISTS idx_production_capacity_planning ON production_orders(warehouse_id, planned_start_date, planned_completion_date, status)
    WHERE status IN ('PLANNED', 'RELEASED', 'IN_PROGRESS');

-- ==============================================================================
-- PROCUREMENT PERFORMANCE INDEXES
-- ==============================================================================

-- Purchase order delivery tracking indexes
CREATE INDEX IF NOT EXISTS idx_purchase_orders_delivery_tracking ON purchase_orders(expected_delivery_date, status)
    WHERE status IN ('SENT', 'CONFIRMED', 'PARTIALLY_RECEIVED');

CREATE INDEX IF NOT EXISTS idx_purchase_orders_overdue ON purchase_orders(expected_delivery_date, status)
    WHERE expected_delivery_date < CURRENT_DATE AND status NOT IN ('FULLY_RECEIVED', 'CANCELLED');

-- Purchase order item receiving optimization
CREATE INDEX IF NOT EXISTS idx_po_items_receiving ON purchase_order_items(purchase_order_id, delivery_status, product_id)
    WHERE delivery_status IN ('PENDING', 'PARTIALLY_RECEIVED');

-- Supplier performance analysis indexes
CREATE INDEX IF NOT EXISTS idx_supplier_performance_analysis ON purchase_orders(supplier_id, order_date DESC, status, actual_delivery_date);

-- ==============================================================================
-- REPORTING AND ANALYTICS INDEXES
-- ==============================================================================

-- Critical stock alerts performance indexes
CREATE INDEX IF NOT EXISTS idx_critical_stock_dashboard ON critical_stock_alerts(is_resolved, alert_type, alert_date DESC);
CREATE INDEX IF NOT EXISTS idx_critical_stock_product_summary ON critical_stock_alerts(product_id, warehouse_id, is_resolved);

-- Cost calculation history analysis indexes
CREATE INDEX IF NOT EXISTS idx_cost_history_trending ON cost_calculation_history(product_id, cost_type, calculation_date DESC);
CREATE INDEX IF NOT EXISTS idx_cost_history_variance_analysis ON cost_calculation_history(calculation_date, cost_type, total_unit_cost);

-- ==============================================================================
-- CROSS-MODULE PERFORMANCE INDEXES
-- ==============================================================================

-- Product lifecycle management
CREATE INDEX IF NOT EXISTS idx_product_lifecycle ON products(product_type, created_at, is_active);

-- Inventory turnover analysis
CREATE INDEX IF NOT EXISTS idx_inventory_turnover ON inventory_items(product_id, warehouse_id, entry_date, quantity_in_stock)
    WHERE quantity_in_stock > 0;

-- Production to inventory integration
CREATE INDEX IF NOT EXISTS idx_production_inventory_integration ON production_orders(product_id, warehouse_id, status, actual_completion_date);

-- Procurement to inventory integration
CREATE INDEX IF NOT EXISTS idx_procurement_inventory_integration ON purchase_order_items(product_id, delivery_status, updated_at);

-- ==============================================================================
-- ADDITIONAL DATA INTEGRITY CONSTRAINTS
-- ==============================================================================

-- Cross-table business rule constraints

-- Ensure warehouse type matches product type for inventory
CREATE OR REPLACE FUNCTION validate_warehouse_product_compatibility()
RETURNS TRIGGER AS $$
DECLARE
    warehouse_type VARCHAR(20);
    product_type VARCHAR(20);
BEGIN
    -- Get warehouse and product types
    SELECT w.warehouse_type, p.product_type
    INTO warehouse_type, product_type
    FROM warehouses w, products p
    WHERE w.warehouse_id = NEW.warehouse_id
      AND p.product_id = NEW.product_id;
    
    -- Validate compatibility
    IF (warehouse_type = 'RAW_MATERIALS' AND product_type != 'RAW_MATERIAL') OR
       (warehouse_type = 'SEMI_FINISHED' AND product_type != 'SEMI_FINISHED') OR
       (warehouse_type = 'FINISHED_PRODUCTS' AND product_type != 'FINISHED_PRODUCT') OR
       (warehouse_type = 'PACKAGING' AND product_type != 'PACKAGING') THEN
        RAISE EXCEPTION 'Product type % is not compatible with warehouse type %', product_type, warehouse_type;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply warehouse-product compatibility check
CREATE TRIGGER trg_inventory_warehouse_product_check
    BEFORE INSERT OR UPDATE ON inventory_items
    FOR EACH ROW
    EXECUTE FUNCTION validate_warehouse_product_compatibility();

-- Ensure BOM components don't reference finished products as components
CREATE OR REPLACE FUNCTION validate_bom_component_type()
RETURNS TRIGGER AS $$
DECLARE
    component_type VARCHAR(20);
BEGIN
    -- Get component product type
    SELECT product_type INTO component_type
    FROM products
    WHERE product_id = NEW.component_product_id;
    
    -- Finished products cannot be components in BOMs
    IF component_type = 'FINISHED_PRODUCT' THEN
        RAISE EXCEPTION 'Finished products cannot be used as BOM components';
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply BOM component type validation
CREATE TRIGGER trg_bom_component_type_check
    BEFORE INSERT OR UPDATE ON bom_components
    FOR EACH ROW
    EXECUTE FUNCTION validate_bom_component_type();

-- Ensure production orders are for producible items (semi-finished or finished)
CREATE OR REPLACE FUNCTION validate_production_order_product()
RETURNS TRIGGER AS $$
DECLARE
    product_type VARCHAR(20);
BEGIN
    -- Get product type
    SELECT product_type INTO product_type
    FROM products
    WHERE product_id = NEW.product_id;
    
    -- Only semi-finished and finished products can have production orders
    IF product_type NOT IN ('SEMI_FINISHED', 'FINISHED_PRODUCT') THEN
        RAISE EXCEPTION 'Production orders can only be created for semi-finished or finished products';
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply production order product validation
CREATE TRIGGER trg_production_order_product_check
    BEFORE INSERT OR UPDATE ON production_orders
    FOR EACH ROW
    EXECUTE FUNCTION validate_production_order_product();

-- ==============================================================================
-- PARTIAL INDEXES FOR SPECIFIC USE CASES
-- ==============================================================================

-- Active records only indexes (space-efficient)
CREATE INDEX IF NOT EXISTS idx_products_active_only ON products(product_id) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_suppliers_active_only ON suppliers(supplier_id) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_warehouses_active_only ON warehouses(warehouse_id) WHERE is_active = TRUE;

-- Status-specific indexes
CREATE INDEX IF NOT EXISTS idx_production_orders_active_only ON production_orders(production_order_id, priority)
    WHERE status IN ('PLANNED', 'RELEASED', 'IN_PROGRESS');

CREATE INDEX IF NOT EXISTS idx_purchase_orders_active_only ON purchase_orders(purchase_order_id, expected_delivery_date)
    WHERE status NOT IN ('FULLY_RECEIVED', 'CANCELLED');

-- Quality status specific indexes
CREATE INDEX IF NOT EXISTS idx_inventory_approved_only ON inventory_items(product_id, warehouse_id, entry_date)
    WHERE quality_status = 'APPROVED';

-- ==============================================================================
-- EXPRESSION INDEXES FOR COMPUTED VALUES
-- ==============================================================================

-- Inventory value calculations
CREATE INDEX IF NOT EXISTS idx_inventory_value ON inventory_items((quantity_in_stock * unit_cost))
    WHERE quantity_in_stock > 0;

-- Production order completion percentage
CREATE INDEX IF NOT EXISTS idx_production_completion_pct ON production_orders(
    (COALESCE(completed_quantity, 0) * 100.0 / GREATEST(planned_quantity, 1))
) WHERE status IN ('IN_PROGRESS', 'COMPLETED');

-- Purchase order delivery delay
CREATE INDEX IF NOT EXISTS idx_purchase_delivery_delay ON purchase_orders(
    (COALESCE(actual_delivery_date, CURRENT_DATE) - expected_delivery_date)
) WHERE expected_delivery_date IS NOT NULL;

-- ==============================================================================
-- COVERING INDEXES FOR READ-HEAVY QUERIES
-- ==============================================================================

-- Inventory summary covering index
CREATE INDEX IF NOT EXISTS idx_inventory_summary_covering ON inventory_items(product_id, warehouse_id)
    INCLUDE (quantity_in_stock, reserved_quantity, unit_cost, entry_date, batch_number)
    WHERE quality_status = 'APPROVED';

-- Production order dashboard covering index
CREATE INDEX IF NOT EXISTS idx_production_dashboard_covering ON production_orders(status, planned_start_date)
    INCLUDE (order_number, product_id, planned_quantity, completed_quantity, priority)
    WHERE status IN ('PLANNED', 'RELEASED', 'IN_PROGRESS');

-- Purchase order monitoring covering index
CREATE INDEX IF NOT EXISTS idx_purchase_monitoring_covering ON purchase_orders(status, expected_delivery_date)
    INCLUDE (po_number, supplier_id, total_amount, order_date)
    WHERE status NOT IN ('FULLY_RECEIVED', 'CANCELLED');

-- ==============================================================================
-- TEXT SEARCH INDEXES
-- ==============================================================================

-- Full-text search for products
CREATE INDEX IF NOT EXISTS idx_products_fulltext ON products 
    USING gin(to_tsvector('english', product_name || ' ' || COALESCE(product_code, '') || ' ' || COALESCE(description, '')));

-- Full-text search for suppliers
CREATE INDEX IF NOT EXISTS idx_suppliers_fulltext ON suppliers 
    USING gin(to_tsvector('english', supplier_name || ' ' || COALESCE(supplier_code, '') || ' ' || COALESCE(city, '') || ' ' || COALESCE(country, '')));

-- ==============================================================================
-- CONSTRAINT ENHANCEMENTS
-- ==============================================================================

-- Add check constraint for reasonable date ranges
ALTER TABLE production_orders ADD CONSTRAINT IF NOT EXISTS chk_reasonable_production_dates 
    CHECK (
        planned_start_date IS NULL OR 
        (planned_start_date >= order_date AND planned_start_date <= order_date + INTERVAL '2 years')
    );

ALTER TABLE purchase_orders ADD CONSTRAINT IF NOT EXISTS chk_reasonable_delivery_dates 
    CHECK (
        expected_delivery_date IS NULL OR 
        (expected_delivery_date >= order_date AND expected_delivery_date <= order_date + INTERVAL '1 year')
    );

-- Add constraint for reasonable inventory quantities
ALTER TABLE inventory_items ADD CONSTRAINT IF NOT EXISTS chk_reasonable_inventory_quantities 
    CHECK (
        quantity_in_stock <= 1000000 AND -- Max 1 million units
        unit_cost <= 100000 -- Max cost per unit
    );

-- Add constraint for reasonable BOM quantities
ALTER TABLE bom_components ADD CONSTRAINT IF NOT EXISTS chk_reasonable_bom_quantities 
    CHECK (
        quantity_required <= 10000 AND -- Max 10,000 units per component
        scrap_percentage <= 50 -- Max 50% scrap
    );

-- ==============================================================================
-- INDEX MAINTENANCE FUNCTIONS
-- ==============================================================================

-- Function to rebuild indexes for performance
CREATE OR REPLACE FUNCTION rebuild_mrp_indexes()
RETURNS TEXT AS $$
DECLARE
    index_name TEXT;
    result_log TEXT := '';
BEGIN
    result_log := 'Index rebuild started at ' || CURRENT_TIMESTAMP || E'\n';
    
    -- Reindex critical FIFO indexes
    REINDEX INDEX CONCURRENTLY idx_inventory_fifo_consumption;
    result_log := result_log || 'Rebuilt FIFO consumption index' || E'\n';
    
    -- Reindex BOM hierarchy indexes
    REINDEX INDEX CONCURRENTLY idx_bom_hierarchy_parent;
    result_log := result_log || 'Rebuilt BOM hierarchy index' || E'\n';
    
    -- Reindex production scheduling indexes
    REINDEX INDEX CONCURRENTLY idx_production_orders_scheduling;
    result_log := result_log || 'Rebuilt production scheduling index' || E'\n';
    
    result_log := result_log || 'Index rebuild completed at ' || CURRENT_TIMESTAMP;
    RETURN result_log;
END;
$$ LANGUAGE plpgsql;

-- Function to analyze index usage statistics
CREATE OR REPLACE FUNCTION analyze_index_usage()
RETURNS TABLE (
    index_name TEXT,
    table_name TEXT,
    index_size TEXT,
    index_scans BIGINT,
    tuples_read BIGINT,
    tuples_fetched BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        indexrelname::TEXT as index_name,
        tablename::TEXT as table_name,
        pg_size_pretty(pg_relation_size(indexrelid))::TEXT as index_size,
        idx_scan as index_scans,
        idx_tup_read as tuples_read,
        idx_tup_fetch as tuples_fetched
    FROM pg_stat_user_indexes
    WHERE schemaname = 'public'
      AND indexrelname LIKE 'idx_%'
    ORDER BY idx_scan DESC;
END;
$$ LANGUAGE plpgsql;

-- ==============================================================================
-- PERFORMANCE MONITORING VIEWS
-- ==============================================================================

-- Index usage monitoring view
CREATE VIEW index_usage_stats AS
SELECT 
    schemaname,
    tablename,
    indexrelname as index_name,
    idx_scan as scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched,
    pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;

COMMENT ON VIEW index_usage_stats IS 'Monitor index usage statistics for performance optimization';

-- ==============================================================================
-- SCRIPT COMPLETION AND VALIDATION
-- ==============================================================================

-- Validate that critical indexes exist
DO $$
DECLARE
    missing_indexes TEXT[] := ARRAY[]::TEXT[];
    critical_indexes TEXT[] := ARRAY[
        'idx_inventory_fifo_consumption',
        'idx_bom_hierarchy_parent', 
        'idx_production_orders_scheduling',
        'idx_purchase_orders_delivery_tracking',
        'idx_critical_stock_dashboard'
    ];
    idx TEXT;
BEGIN
    FOREACH idx IN ARRAY critical_indexes LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = idx) THEN
            missing_indexes := array_append(missing_indexes, idx);
        END IF;
    END LOOP;
    
    IF array_length(missing_indexes, 1) > 0 THEN
        RAISE WARNING 'Missing critical indexes: %', array_to_string(missing_indexes, ', ');
    END IF;
END $$;

-- Performance optimization summary
SELECT 
    'Performance Indexes Created Successfully' AS status,
    COUNT(*) as total_indexes_created,
    'FIFO, BOM, Production, Procurement optimized' AS optimization_areas,
    'Cross-table integrity constraints enabled' AS integrity_status
FROM pg_indexes 
WHERE schemaname = 'public' AND indexname LIKE 'idx_%';