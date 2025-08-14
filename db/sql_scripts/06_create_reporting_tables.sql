-- ==============================================================================
-- Horoz Demir MRP System - Reporting and Analytics Tables
-- ==============================================================================
-- This script creates the reporting tables for critical stock monitoring
-- and cost calculation history tracking
-- ==============================================================================

-- Drop tables if they exist (in reverse dependency order)
DROP TABLE IF EXISTS cost_calculation_history CASCADE;
DROP TABLE IF EXISTS critical_stock_alerts CASCADE;

-- ==============================================================================
-- CRITICAL_STOCK_ALERTS TABLE
-- ==============================================================================
-- Monitors products that fall below minimum or critical stock levels
-- Generates alerts for procurement and inventory management
-- ==============================================================================

CREATE TABLE critical_stock_alerts (
    alert_id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL,
    warehouse_id INTEGER NOT NULL,
    current_stock DECIMAL(15,4) NOT NULL,
    minimum_level DECIMAL(15,4) NOT NULL,
    critical_level DECIMAL(15,4) NOT NULL,
    alert_type VARCHAR(20) NOT NULL,
    alert_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_resolved BOOLEAN DEFAULT FALSE,
    resolved_date TIMESTAMP,
    resolved_by VARCHAR(100),
    resolution_notes TEXT,
    
    -- Foreign key constraints
    CONSTRAINT fk_critical_stock_alerts_product 
        FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE,
    CONSTRAINT fk_critical_stock_alerts_warehouse 
        FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id) ON DELETE CASCADE,
    
    -- Business rule constraints
    CONSTRAINT chk_critical_stock_alert_type CHECK (
        alert_type IN ('MINIMUM', 'CRITICAL', 'OUT_OF_STOCK')
    ),
    CONSTRAINT chk_critical_stock_levels CHECK (
        current_stock >= 0 AND 
        minimum_level >= 0 AND 
        critical_level >= 0 AND
        critical_level <= minimum_level
    ),
    CONSTRAINT chk_critical_stock_resolution CHECK (
        (is_resolved = FALSE AND resolved_date IS NULL AND resolved_by IS NULL) OR
        (is_resolved = TRUE AND resolved_date IS NOT NULL)
    ),
    CONSTRAINT chk_critical_stock_alert_dates CHECK (
        resolved_date IS NULL OR resolved_date >= alert_date
    )
);

-- Add table and column comments
COMMENT ON TABLE critical_stock_alerts IS 'Critical stock level monitoring and alerting system';
COMMENT ON COLUMN critical_stock_alerts.alert_type IS 'Alert severity: MINIMUM (below min level), CRITICAL (below critical level), OUT_OF_STOCK (zero stock)';
COMMENT ON COLUMN critical_stock_alerts.current_stock IS 'Current available stock level when alert was generated';
COMMENT ON COLUMN critical_stock_alerts.minimum_level IS 'Minimum stock level threshold for this product';
COMMENT ON COLUMN critical_stock_alerts.critical_level IS 'Critical stock level threshold for this product';

-- ==============================================================================
-- COST_CALCULATION_HISTORY TABLE
-- ==============================================================================
-- Historical cost calculations for trend analysis and reporting
-- Supports multiple cost calculation methods (FIFO, Standard, Average, Actual)
-- ==============================================================================

CREATE TABLE cost_calculation_history (
    cost_history_id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL,
    calculation_date DATE NOT NULL,
    cost_type VARCHAR(20) NOT NULL,
    material_cost DECIMAL(15,4) DEFAULT 0,
    labor_cost DECIMAL(15,4) DEFAULT 0,
    overhead_cost DECIMAL(15,4) DEFAULT 0,
    total_unit_cost DECIMAL(15,4) GENERATED ALWAYS AS (material_cost + labor_cost + overhead_cost) STORED,
    quantity_basis DECIMAL(15,4) NOT NULL DEFAULT 1,
    source_type VARCHAR(30),
    source_id INTEGER,
    calculation_method TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    CONSTRAINT fk_cost_calculation_history_product 
        FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE,
    
    -- Business rule constraints
    CONSTRAINT chk_cost_calculation_type CHECK (
        cost_type IN ('FIFO', 'STANDARD', 'AVERAGE', 'ACTUAL')
    ),
    CONSTRAINT chk_cost_calculation_values CHECK (
        material_cost >= 0 AND 
        labor_cost >= 0 AND 
        overhead_cost >= 0 AND
        quantity_basis > 0
    ),
    CONSTRAINT chk_cost_calculation_source_type CHECK (
        source_type IS NULL OR 
        source_type IN ('BOM_CALCULATION', 'INVENTORY_VALUATION', 'PRODUCTION_ORDER', 'PURCHASE_ORDER', 'MANUAL_ENTRY')
    ),
    CONSTRAINT chk_cost_calculation_date CHECK (
        calculation_date <= CURRENT_DATE
    ),
    
    -- Unique constraint to prevent duplicate calculations per product per date per type
    CONSTRAINT uk_cost_calculation UNIQUE (product_id, calculation_date, cost_type)
);

-- Add table and column comments
COMMENT ON TABLE cost_calculation_history IS 'Historical cost calculations for trend analysis and reporting';
COMMENT ON COLUMN cost_calculation_history.cost_type IS 'Cost calculation method: FIFO, STANDARD, AVERAGE, ACTUAL';
COMMENT ON COLUMN cost_calculation_history.total_unit_cost IS 'Calculated total unit cost: material + labor + overhead';
COMMENT ON COLUMN cost_calculation_history.quantity_basis IS 'Quantity basis for cost calculation (usually 1 for per-unit costs)';
COMMENT ON COLUMN cost_calculation_history.source_type IS 'Source of cost calculation: BOM_CALCULATION, INVENTORY_VALUATION, etc.';
COMMENT ON COLUMN cost_calculation_history.calculation_method IS 'Description of calculation method or formula used';

-- ==============================================================================
-- TRIGGERS FOR REPORTING SYSTEM
-- ==============================================================================

-- Function to automatically generate critical stock alerts
CREATE OR REPLACE FUNCTION generate_critical_stock_alerts()
RETURNS TRIGGER AS $$
DECLARE
    product_record RECORD;
    current_available DECIMAL(15,4);
    alert_type_needed VARCHAR(20);
BEGIN
    -- Get product details
    SELECT p.*, w.warehouse_id, w.warehouse_code
    INTO product_record
    FROM products p
    CROSS JOIN warehouses w
    WHERE p.product_id = NEW.product_id 
      AND w.warehouse_id = NEW.warehouse_id;
    
    -- Calculate current available stock
    current_available := NEW.available_quantity;
    
    -- Determine alert type needed
    IF current_available <= 0 THEN
        alert_type_needed := 'OUT_OF_STOCK';
    ELSIF current_available <= product_record.critical_stock_level THEN
        alert_type_needed := 'CRITICAL';
    ELSIF current_available <= product_record.minimum_stock_level THEN
        alert_type_needed := 'MINIMUM';
    ELSE
        alert_type_needed := NULL;
    END IF;
    
    -- Create alert if needed and doesn't already exist
    IF alert_type_needed IS NOT NULL THEN
        INSERT INTO critical_stock_alerts (
            product_id,
            warehouse_id,
            current_stock,
            minimum_level,
            critical_level,
            alert_type
        )
        SELECT 
            NEW.product_id,
            NEW.warehouse_id,
            current_available,
            product_record.minimum_stock_level,
            product_record.critical_stock_level,
            alert_type_needed
        WHERE NOT EXISTS (
            SELECT 1 FROM critical_stock_alerts 
            WHERE product_id = NEW.product_id 
              AND warehouse_id = NEW.warehouse_id 
              AND alert_type = alert_type_needed
              AND is_resolved = FALSE
        );
    ELSE
        -- Resolve existing alerts if stock is now adequate
        UPDATE critical_stock_alerts
        SET is_resolved = TRUE,
            resolved_date = CURRENT_TIMESTAMP,
            resolved_by = 'SYSTEM',
            resolution_notes = 'Stock level restored to above minimum threshold'
        WHERE product_id = NEW.product_id
          AND warehouse_id = NEW.warehouse_id
          AND is_resolved = FALSE;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to generate alerts when inventory changes
CREATE TRIGGER trg_generate_critical_stock_alerts
    AFTER INSERT OR UPDATE ON inventory_items
    FOR EACH ROW
    EXECUTE FUNCTION generate_critical_stock_alerts();

-- Function to calculate and store daily cost history
CREATE OR REPLACE FUNCTION calculate_daily_costs()
RETURNS TEXT AS $$
DECLARE
    product_record RECORD;
    cost_record RECORD;
    calculation_log TEXT := '';
    total_products INTEGER := 0;
BEGIN
    calculation_log := 'Daily cost calculation started at ' || CURRENT_TIMESTAMP || E'\n';
    
    -- Calculate costs for all active products
    FOR product_record IN
        SELECT p.* FROM products p WHERE p.is_active = TRUE
    LOOP
        total_products := total_products + 1;
        
        -- FIFO Cost Calculation
        BEGIN
            SELECT 
                COALESCE(SUM(ii.total_cost) / NULLIF(SUM(ii.quantity_in_stock), 0), p.standard_cost) as fifo_cost
            INTO cost_record
            FROM inventory_items ii
            JOIN products p ON ii.product_id = p.product_id
            WHERE ii.product_id = product_record.product_id
              AND ii.quality_status = 'APPROVED'
              AND ii.quantity_in_stock > 0;
            
            INSERT INTO cost_calculation_history (
                product_id,
                calculation_date,
                cost_type,
                material_cost,
                source_type,
                calculation_method
            ) VALUES (
                product_record.product_id,
                CURRENT_DATE,
                'FIFO',
                COALESCE(cost_record.fifo_cost, product_record.standard_cost),
                'INVENTORY_VALUATION',
                'Weighted average of available inventory based on FIFO order'
            )
            ON CONFLICT (product_id, calculation_date, cost_type) 
            DO UPDATE SET
                material_cost = EXCLUDED.material_cost,
                calculation_method = EXCLUDED.calculation_method,
                created_at = CURRENT_TIMESTAMP;
                
        EXCEPTION WHEN OTHERS THEN
            calculation_log := calculation_log || 'ERROR calculating FIFO cost for product ' || 
                              product_record.product_code || ': ' || SQLERRM || E'\n';
        END;
        
        -- Standard Cost (from product master)
        INSERT INTO cost_calculation_history (
            product_id,
            calculation_date,
            cost_type,
            material_cost,
            source_type,
            calculation_method
        ) VALUES (
            product_record.product_id,
            CURRENT_DATE,
            'STANDARD',
            product_record.standard_cost,
            'MANUAL_ENTRY',
            'Standard cost from product master data'
        )
        ON CONFLICT (product_id, calculation_date, cost_type) 
        DO UPDATE SET
            material_cost = EXCLUDED.material_cost,
            created_at = CURRENT_TIMESTAMP;
        
        -- BOM-based cost calculation for semi-finished and finished products
        IF product_record.product_type IN ('SEMI_FINISHED', 'FINISHED_PRODUCT') THEN
            BEGIN
                SELECT 
                    COALESCE(bcc.total_cost, 0) as bom_cost
                INTO cost_record
                FROM bill_of_materials bom
                LEFT JOIN bom_cost_calculations bcc ON bom.bom_id = bcc.bom_id AND bcc.is_current = TRUE
                WHERE bom.parent_product_id = product_record.product_id
                  AND bom.status = 'ACTIVE'
                ORDER BY bom.effective_date DESC
                LIMIT 1;
                
                IF cost_record.bom_cost > 0 THEN
                    INSERT INTO cost_calculation_history (
                        product_id,
                        calculation_date,
                        cost_type,
                        material_cost,
                        source_type,
                        calculation_method
                    ) VALUES (
                        product_record.product_id,
                        CURRENT_DATE,
                        'ACTUAL',
                        cost_record.bom_cost,
                        'BOM_CALCULATION',
                        'Cost rolled up from BOM component costs'
                    )
                    ON CONFLICT (product_id, calculation_date, cost_type) 
                    DO UPDATE SET
                        material_cost = EXCLUDED.material_cost,
                        calculation_method = EXCLUDED.calculation_method,
                        created_at = CURRENT_TIMESTAMP;
                END IF;
                
            EXCEPTION WHEN OTHERS THEN
                calculation_log := calculation_log || 'ERROR calculating BOM cost for product ' || 
                                  product_record.product_code || ': ' || SQLERRM || E'\n';
            END;
        END IF;
    END LOOP;
    
    calculation_log := calculation_log || 'Processed ' || total_products || ' products';
    RETURN calculation_log;
END;
$$ LANGUAGE plpgsql;

-- ==============================================================================
-- REPORTING FUNCTIONS
-- ==============================================================================

-- Function to get critical stock alert summary
CREATE OR REPLACE FUNCTION get_critical_stock_alert_summary()
RETURNS TABLE (
    alert_type VARCHAR(20),
    total_alerts BIGINT,
    unresolved_alerts BIGINT,
    oldest_alert_date TIMESTAMP,
    avg_resolution_time INTERVAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        csa.alert_type,
        COUNT(*) as total_alerts,
        COUNT(CASE WHEN csa.is_resolved = FALSE THEN 1 END) as unresolved_alerts,
        MIN(csa.alert_date) as oldest_alert_date,
        AVG(CASE WHEN csa.is_resolved = TRUE THEN csa.resolved_date - csa.alert_date END) as avg_resolution_time
    FROM critical_stock_alerts csa
    WHERE csa.alert_date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY csa.alert_type
    ORDER BY 
        CASE csa.alert_type 
            WHEN 'OUT_OF_STOCK' THEN 1
            WHEN 'CRITICAL' THEN 2
            WHEN 'MINIMUM' THEN 3
        END;
END;
$$ LANGUAGE plpgsql;

-- Function to get cost trend analysis
CREATE OR REPLACE FUNCTION get_cost_trend_analysis(
    p_product_id INTEGER,
    p_days_back INTEGER DEFAULT 30
)
RETURNS TABLE (
    calculation_date DATE,
    fifo_cost DECIMAL(15,4),
    standard_cost DECIMAL(15,4),
    actual_cost DECIMAL(15,4),
    cost_variance_pct DECIMAL(8,2)
) AS $$
BEGIN
    RETURN QUERY
    WITH daily_costs AS (
        SELECT 
            cch.calculation_date,
            MAX(CASE WHEN cch.cost_type = 'FIFO' THEN cch.total_unit_cost END) as fifo_cost,
            MAX(CASE WHEN cch.cost_type = 'STANDARD' THEN cch.total_unit_cost END) as standard_cost,
            MAX(CASE WHEN cch.cost_type = 'ACTUAL' THEN cch.total_unit_cost END) as actual_cost
        FROM cost_calculation_history cch
        WHERE cch.product_id = p_product_id
          AND cch.calculation_date >= CURRENT_DATE - INTERVAL '1 day' * p_days_back
        GROUP BY cch.calculation_date
    )
    SELECT 
        dc.calculation_date,
        dc.fifo_cost,
        dc.standard_cost,
        dc.actual_cost,
        CASE 
            WHEN dc.standard_cost > 0 AND dc.fifo_cost > 0
            THEN ROUND(((dc.fifo_cost - dc.standard_cost) / dc.standard_cost * 100), 2)
            ELSE NULL
        END as cost_variance_pct
    FROM daily_costs dc
    ORDER BY dc.calculation_date DESC;
END;
$$ LANGUAGE plpgsql;

-- ==============================================================================
-- INDEXES FOR REPORTING PERFORMANCE
-- ==============================================================================

-- Critical stock alerts indexes
CREATE INDEX idx_critical_stock_alerts_product_warehouse ON critical_stock_alerts(product_id, warehouse_id);
CREATE INDEX idx_critical_stock_alerts_unresolved ON critical_stock_alerts(alert_type, is_resolved, alert_date)
    WHERE is_resolved = FALSE;
CREATE INDEX idx_critical_stock_alerts_date ON critical_stock_alerts(alert_date DESC);
CREATE INDEX idx_critical_stock_alerts_resolution ON critical_stock_alerts(resolved_date DESC)
    WHERE is_resolved = TRUE;

-- Cost calculation history indexes
CREATE INDEX idx_cost_calculation_history_product_date ON cost_calculation_history(product_id, calculation_date DESC);
CREATE INDEX idx_cost_calculation_history_type_date ON cost_calculation_history(cost_type, calculation_date DESC);
CREATE INDEX idx_cost_calculation_history_source ON cost_calculation_history(source_type, source_id);

-- Performance optimization indexes
CREATE INDEX idx_cost_trend_analysis ON cost_calculation_history(product_id, calculation_date DESC, cost_type);

-- ==============================================================================
-- VIEWS FOR REPORTING DASHBOARD
-- ==============================================================================

-- Current critical stock alerts view
CREATE VIEW current_critical_stock_alerts AS
SELECT 
    csa.alert_id,
    p.product_code,
    p.product_name,
    p.product_type,
    w.warehouse_code,
    w.warehouse_name,
    csa.current_stock,
    csa.minimum_level,
    csa.critical_level,
    csa.alert_type,
    csa.alert_date,
    EXTRACT(DAYS FROM (CURRENT_TIMESTAMP - csa.alert_date)) as days_outstanding,
    CASE csa.alert_type
        WHEN 'OUT_OF_STOCK' THEN 1
        WHEN 'CRITICAL' THEN 2
        WHEN 'MINIMUM' THEN 3
    END as priority_order
FROM critical_stock_alerts csa
JOIN products p ON csa.product_id = p.product_id
JOIN warehouses w ON csa.warehouse_id = w.warehouse_id
WHERE csa.is_resolved = FALSE
ORDER BY priority_order, csa.alert_date;

COMMENT ON VIEW current_critical_stock_alerts IS 'Current unresolved critical stock alerts with priority ordering';

-- Cost analysis dashboard view
CREATE VIEW cost_analysis_dashboard AS
SELECT 
    p.product_id,
    p.product_code,
    p.product_name,
    p.product_type,
    p.standard_cost,
    cch_fifo.total_unit_cost as current_fifo_cost,
    cch_actual.total_unit_cost as current_actual_cost,
    CASE 
        WHEN p.standard_cost > 0 AND cch_fifo.total_unit_cost > 0
        THEN ROUND(((cch_fifo.total_unit_cost - p.standard_cost) / p.standard_cost * 100), 2)
        ELSE NULL
    END as fifo_variance_pct,
    CASE 
        WHEN p.standard_cost > 0 AND cch_actual.total_unit_cost > 0
        THEN ROUND(((cch_actual.total_unit_cost - p.standard_cost) / p.standard_cost * 100), 2)
        ELSE NULL
    END as actual_variance_pct,
    cch_fifo.calculation_date as last_fifo_calculation,
    cch_actual.calculation_date as last_actual_calculation
FROM products p
LEFT JOIN LATERAL (
    SELECT total_unit_cost, calculation_date
    FROM cost_calculation_history
    WHERE product_id = p.product_id AND cost_type = 'FIFO'
    ORDER BY calculation_date DESC LIMIT 1
) cch_fifo ON true
LEFT JOIN LATERAL (
    SELECT total_unit_cost, calculation_date
    FROM cost_calculation_history
    WHERE product_id = p.product_id AND cost_type = 'ACTUAL'
    ORDER BY calculation_date DESC LIMIT 1
) cch_actual ON true
WHERE p.is_active = TRUE;

COMMENT ON VIEW cost_analysis_dashboard IS 'Cost analysis dashboard showing current costs and variances from standard';

-- ==============================================================================
-- SCHEDULED MAINTENANCE PROCEDURES
-- ==============================================================================

-- Function to archive old cost calculation history
CREATE OR REPLACE FUNCTION archive_old_cost_history(p_days_to_keep INTEGER DEFAULT 365)
RETURNS TEXT AS $$
DECLARE
    archive_count INTEGER;
BEGIN
    -- Archive records older than specified days
    WITH archived AS (
        DELETE FROM cost_calculation_history
        WHERE calculation_date < CURRENT_DATE - INTERVAL '1 day' * p_days_to_keep
        RETURNING *
    )
    SELECT COUNT(*) INTO archive_count FROM archived;
    
    RETURN 'Archived ' || archive_count || ' cost calculation records older than ' || 
           p_days_to_keep || ' days';
END;
$$ LANGUAGE plpgsql;

-- Function to clean up resolved alerts
CREATE OR REPLACE FUNCTION cleanup_resolved_alerts(p_days_to_keep INTEGER DEFAULT 90)
RETURNS TEXT AS $$
DECLARE
    cleanup_count INTEGER;
BEGIN
    -- Delete resolved alerts older than specified days
    WITH cleaned AS (
        DELETE FROM critical_stock_alerts
        WHERE is_resolved = TRUE 
          AND resolved_date < CURRENT_DATE - INTERVAL '1 day' * p_days_to_keep
        RETURNING *
    )
    SELECT COUNT(*) INTO cleanup_count FROM cleaned;
    
    RETURN 'Cleaned up ' || cleanup_count || ' resolved alerts older than ' || 
           p_days_to_keep || ' days';
END;
$$ LANGUAGE plpgsql;

-- ==============================================================================
-- GRANTS AND PERMISSIONS
-- ==============================================================================

-- Grant permissions to application roles (uncomment when roles are created)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON critical_stock_alerts TO mrp_admin;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON cost_calculation_history TO mrp_admin;

-- GRANT SELECT, UPDATE ON critical_stock_alerts TO mrp_inventory_clerk;
-- GRANT SELECT ON cost_calculation_history TO mrp_inventory_clerk;

-- GRANT SELECT ON critical_stock_alerts TO mrp_readonly;
-- GRANT SELECT ON cost_calculation_history TO mrp_readonly;
-- GRANT SELECT ON current_critical_stock_alerts TO mrp_readonly;
-- GRANT SELECT ON cost_analysis_dashboard TO mrp_readonly;

-- ==============================================================================
-- SCRIPT COMPLETION
-- ==============================================================================

SELECT 'Reporting Tables Created Successfully' AS status,
       'Critical stock monitoring system enabled' AS alert_status,
       'Cost history tracking system ready' AS cost_tracking_status,
       'Automated alert generation installed' AS automation_status;