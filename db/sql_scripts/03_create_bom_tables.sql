-- ==============================================================================
-- Horoz Demir MRP System - Bill of Materials (BOM) Tables
-- ==============================================================================
-- This script creates the BOM tables supporting nested hierarchies where
-- semi-finished products can contain other semi-finished products
-- ==============================================================================

-- Drop tables if they exist (in reverse dependency order)
DROP TABLE IF EXISTS bom_cost_calculations CASCADE;
DROP TABLE IF EXISTS bom_components CASCADE;
DROP TABLE IF EXISTS bill_of_materials CASCADE;

-- ==============================================================================
-- BILL_OF_MATERIALS TABLE
-- ==============================================================================
-- Header table defining BOMs for semi-finished and finished products
-- Supports versioning and effective date management
-- ==============================================================================

CREATE TABLE bill_of_materials (
    bom_id SERIAL PRIMARY KEY,
    parent_product_id INTEGER NOT NULL,
    bom_version VARCHAR(10) NOT NULL DEFAULT '1.0',
    bom_name VARCHAR(200) NOT NULL,
    effective_date DATE NOT NULL DEFAULT CURRENT_DATE,
    expiry_date DATE,
    status VARCHAR(20) DEFAULT 'ACTIVE',
    base_quantity DECIMAL(15,4) NOT NULL DEFAULT 1,
    yield_percentage DECIMAL(5,2) DEFAULT 100.00,
    labor_cost_per_unit DECIMAL(15,4) DEFAULT 0,
    overhead_cost_per_unit DECIMAL(15,4) DEFAULT 0,
    notes TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    CONSTRAINT fk_bom_parent_product 
        FOREIGN KEY (parent_product_id) REFERENCES products(product_id) ON DELETE CASCADE,
    
    -- Business rule constraints
    CONSTRAINT chk_bom_status CHECK (
        status IN ('DRAFT', 'ACTIVE', 'INACTIVE', 'OBSOLETE')
    ),
    CONSTRAINT chk_bom_base_quantity CHECK (base_quantity > 0),
    CONSTRAINT chk_bom_yield_percentage CHECK (
        yield_percentage > 0 AND yield_percentage <= 100
    ),
    CONSTRAINT chk_bom_labor_cost CHECK (labor_cost_per_unit >= 0),
    CONSTRAINT chk_bom_overhead_cost CHECK (overhead_cost_per_unit >= 0),
    CONSTRAINT chk_bom_version_format CHECK (
        bom_version ~ '^\d+\.\d+$'
    ),
    CONSTRAINT chk_bom_effective_dates CHECK (
        expiry_date IS NULL OR expiry_date > effective_date
    ),
    
    -- Only one active BOM per product
    CONSTRAINT uk_bom_product_version UNIQUE (parent_product_id, bom_version)
);

-- Add table and column comments
COMMENT ON TABLE bill_of_materials IS 'Bill of Materials header table supporting nested hierarchies';
COMMENT ON COLUMN bill_of_materials.parent_product_id IS 'Product that this BOM defines (semi-finished or finished product)';
COMMENT ON COLUMN bill_of_materials.base_quantity IS 'Base quantity for BOM calculations (typically 1)';
COMMENT ON COLUMN bill_of_materials.yield_percentage IS 'Expected yield percentage (accounts for production losses)';
COMMENT ON COLUMN bill_of_materials.bom_version IS 'Version number in format X.Y for BOM revisions';

-- ==============================================================================
-- BOM_COMPONENTS TABLE
-- ==============================================================================
-- Components within each BOM - supports nested semi-finished products
-- Each component can be raw material, semi-finished, or packaging
-- ==============================================================================

CREATE TABLE bom_components (
    bom_component_id SERIAL PRIMARY KEY,
    bom_id INTEGER NOT NULL,
    component_product_id INTEGER NOT NULL,
    sequence_number INTEGER NOT NULL,
    quantity_required DECIMAL(15,4) NOT NULL,
    unit_of_measure VARCHAR(20) NOT NULL,
    scrap_percentage DECIMAL(5,2) DEFAULT 0.00,
    effective_quantity DECIMAL(15,4) GENERATED ALWAYS AS (
        quantity_required * (1 + scrap_percentage/100)
    ) STORED,
    is_phantom BOOLEAN DEFAULT FALSE,
    substitute_group VARCHAR(20),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    CONSTRAINT fk_bom_components_bom 
        FOREIGN KEY (bom_id) REFERENCES bill_of_materials(bom_id) ON DELETE CASCADE,
    CONSTRAINT fk_bom_components_product 
        FOREIGN KEY (component_product_id) REFERENCES products(product_id) ON DELETE CASCADE,
    
    -- Business rule constraints
    CONSTRAINT chk_bom_component_quantity CHECK (quantity_required > 0),
    CONSTRAINT chk_bom_component_sequence CHECK (sequence_number > 0),
    CONSTRAINT chk_bom_component_scrap CHECK (
        scrap_percentage >= 0 AND scrap_percentage <= 50
    ),
    
    -- Prevent circular references (component cannot be same as parent)
    CONSTRAINT chk_no_self_reference_simple CHECK (
        component_product_id != (
            SELECT parent_product_id 
            FROM bill_of_materials 
            WHERE bom_id = bom_components.bom_id
        )
    ),
    
    -- Unique component per BOM (same component cannot appear twice in one BOM)
    CONSTRAINT uk_bom_component UNIQUE (bom_id, component_product_id)
);

-- Add table and column comments
COMMENT ON TABLE bom_components IS 'Individual components within BOMs supporting nested hierarchies';
COMMENT ON COLUMN bom_components.effective_quantity IS 'Calculated quantity including scrap percentage';
COMMENT ON COLUMN bom_components.is_phantom IS 'True for phantom assemblies that are not physically stocked';
COMMENT ON COLUMN bom_components.substitute_group IS 'Group identifier for alternative/substitute components';
COMMENT ON COLUMN bom_components.sequence_number IS 'Assembly sequence order for production';

-- ==============================================================================
-- BOM_COST_CALCULATIONS TABLE
-- ==============================================================================
-- Stores calculated costs for BOMs with rollup from component costs
-- Supports different costing methods (FIFO, Standard, Average)
-- ==============================================================================

CREATE TABLE bom_cost_calculations (
    bom_cost_id SERIAL PRIMARY KEY,
    bom_id INTEGER NOT NULL,
    calculation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    material_cost DECIMAL(15,4) NOT NULL DEFAULT 0,
    labor_cost DECIMAL(15,4) NOT NULL DEFAULT 0,
    overhead_cost DECIMAL(15,4) NOT NULL DEFAULT 0,
    total_cost DECIMAL(15,4) GENERATED ALWAYS AS (
        material_cost + labor_cost + overhead_cost
    ) STORED,
    cost_basis VARCHAR(20) DEFAULT 'FIFO',
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    CONSTRAINT fk_bom_cost_calculations_bom 
        FOREIGN KEY (bom_id) REFERENCES bill_of_materials(bom_id) ON DELETE CASCADE,
    
    -- Business rule constraints
    CONSTRAINT chk_bom_cost_values CHECK (
        material_cost >= 0 AND labor_cost >= 0 AND overhead_cost >= 0
    ),
    CONSTRAINT chk_bom_cost_basis CHECK (
        cost_basis IN ('FIFO', 'STANDARD', 'AVERAGE', 'ACTUAL')
    )
);

-- Add table and column comments
COMMENT ON TABLE bom_cost_calculations IS 'Calculated costs for BOMs with component cost rollup';
COMMENT ON COLUMN bom_cost_calculations.total_cost IS 'Calculated total: material + labor + overhead';
COMMENT ON COLUMN bom_cost_calculations.cost_basis IS 'Costing method used: FIFO, STANDARD, AVERAGE, ACTUAL';
COMMENT ON COLUMN bom_cost_calculations.is_current IS 'Indicates the current/active cost calculation';

-- ==============================================================================
-- TRIGGERS FOR BOM MANAGEMENT
-- ==============================================================================

-- Updated timestamp triggers
CREATE TRIGGER trg_bom_updated_at
    BEFORE UPDATE ON bill_of_materials
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_bom_components_updated_at
    BEFORE UPDATE ON bom_components
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger to ensure only one current cost calculation per BOM
CREATE OR REPLACE FUNCTION ensure_single_current_cost()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_current = TRUE THEN
        -- Set all other calculations for this BOM to non-current
        UPDATE bom_cost_calculations 
        SET is_current = FALSE 
        WHERE bom_id = NEW.bom_id 
          AND bom_cost_id != COALESCE(NEW.bom_cost_id, 0);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_bom_cost_single_current
    BEFORE INSERT OR UPDATE ON bom_cost_calculations
    FOR EACH ROW
    EXECUTE FUNCTION ensure_single_current_cost();

-- ==============================================================================
-- BOM HIERARCHY FUNCTIONS
-- ==============================================================================

-- Function for BOM explosion (recursive hierarchy traversal)
CREATE OR REPLACE FUNCTION explode_bom(
    p_parent_product_id INTEGER,
    p_quantity DECIMAL(15,4) DEFAULT 1,
    p_max_levels INTEGER DEFAULT 10
)
RETURNS TABLE (
    level_num INTEGER,
    parent_product_id INTEGER,
    parent_product_code VARCHAR(50),
    parent_product_name VARCHAR(200),
    component_product_id INTEGER,
    component_product_code VARCHAR(50),
    component_product_name VARCHAR(200),
    component_type VARCHAR(20),
    quantity_required DECIMAL(15,4),
    effective_quantity DECIMAL(15,4),
    extended_quantity DECIMAL(15,4),
    unit_of_measure VARCHAR(20),
    sequence_number INTEGER,
    is_phantom BOOLEAN,
    bom_path TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE bom_explosion AS (
        -- Base case: direct components of the specified product
        SELECT 
            1 as level_num,
            bom.parent_product_id,
            pp.product_code as parent_product_code,
            pp.product_name as parent_product_name,
            bc.component_product_id,
            cp.product_code as component_product_code,
            cp.product_name as component_product_name,
            cp.product_type as component_type,
            bc.quantity_required,
            bc.effective_quantity,
            bc.effective_quantity * p_quantity as extended_quantity,
            bc.unit_of_measure,
            bc.sequence_number,
            bc.is_phantom,
            pp.product_code || ' -> ' || cp.product_code as bom_path,
            ARRAY[bom.parent_product_id] as path_check
        FROM bill_of_materials bom
        JOIN bom_components bc ON bom.bom_id = bc.bom_id
        JOIN products pp ON bom.parent_product_id = pp.product_id
        JOIN products cp ON bc.component_product_id = cp.product_id
        WHERE bom.parent_product_id = p_parent_product_id
          AND bom.status = 'ACTIVE'
          AND CURRENT_DATE BETWEEN bom.effective_date AND COALESCE(bom.expiry_date, '2099-12-31')
        
        UNION ALL
        
        -- Recursive case: components of semi-finished components
        SELECT 
            be.level_num + 1,
            sub_bom.parent_product_id,
            sub_pp.product_code,
            sub_pp.product_name,
            sub_bc.component_product_id,
            sub_cp.product_code,
            sub_cp.product_name,
            sub_cp.product_type,
            sub_bc.quantity_required,
            sub_bc.effective_quantity,
            sub_bc.effective_quantity * be.extended_quantity as extended_quantity,
            sub_bc.unit_of_measure,
            sub_bc.sequence_number,
            sub_bc.is_phantom,
            be.bom_path || ' -> ' || sub_cp.product_code,
            be.path_check || sub_bom.parent_product_id
        FROM bom_explosion be
        JOIN bill_of_materials sub_bom ON be.component_product_id = sub_bom.parent_product_id
        JOIN bom_components sub_bc ON sub_bom.bom_id = sub_bc.bom_id
        JOIN products sub_pp ON sub_bom.parent_product_id = sub_pp.product_id
        JOIN products sub_cp ON sub_bc.component_product_id = sub_cp.product_id
        WHERE be.level_num < p_max_levels
          AND sub_bom.status = 'ACTIVE'
          AND CURRENT_DATE BETWEEN sub_bom.effective_date AND COALESCE(sub_bom.expiry_date, '2099-12-31')
          AND be.component_type IN ('SEMI_FINISHED') -- Only explode semi-finished components
          AND NOT (sub_bom.parent_product_id = ANY(be.path_check)) -- Prevent circular references
    )
    SELECT * FROM bom_explosion
    ORDER BY level_num, parent_product_id, sequence_number;
END;
$$ LANGUAGE plpgsql;

-- Function for BOM implosion (where-used analysis)
CREATE OR REPLACE FUNCTION implode_bom(
    p_component_product_id INTEGER,
    p_max_levels INTEGER DEFAULT 10
)
RETURNS TABLE (
    level_num INTEGER,
    parent_product_id INTEGER,
    parent_product_code VARCHAR(50),
    parent_product_name VARCHAR(200),
    parent_product_type VARCHAR(20),
    component_product_id INTEGER,
    component_product_code VARCHAR(50),
    component_product_name VARCHAR(200),
    quantity_required DECIMAL(15,4),
    bom_version VARCHAR(10)
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE bom_implosion AS (
        -- Base case: direct parents of the specified component
        SELECT 
            1 as level_num,
            bom.parent_product_id,
            pp.product_code as parent_product_code,
            pp.product_name as parent_product_name,
            pp.product_type as parent_product_type,
            bc.component_product_id,
            cp.product_code as component_product_code,
            cp.product_name as component_product_name,
            bc.quantity_required,
            bom.bom_version,
            ARRAY[bc.component_product_id] as path_check
        FROM bom_components bc
        JOIN bill_of_materials bom ON bc.bom_id = bom.bom_id
        JOIN products pp ON bom.parent_product_id = pp.product_id
        JOIN products cp ON bc.component_product_id = cp.product_id
        WHERE bc.component_product_id = p_component_product_id
          AND bom.status = 'ACTIVE'
          AND CURRENT_DATE BETWEEN bom.effective_date AND COALESCE(bom.expiry_date, '2099-12-31')
        
        UNION ALL
        
        -- Recursive case: parents of parent products
        SELECT 
            bi.level_num + 1,
            parent_bom.parent_product_id,
            parent_pp.product_code,
            parent_pp.product_name,
            parent_pp.product_type,
            parent_bc.component_product_id,
            parent_cp.product_code,
            parent_cp.product_name,
            parent_bc.quantity_required,
            parent_bom.bom_version,
            bi.path_check || parent_bc.component_product_id
        FROM bom_implosion bi
        JOIN bom_components parent_bc ON bi.parent_product_id = parent_bc.component_product_id
        JOIN bill_of_materials parent_bom ON parent_bc.bom_id = parent_bom.bom_id
        JOIN products parent_pp ON parent_bom.parent_product_id = parent_pp.product_id
        JOIN products parent_cp ON parent_bc.component_product_id = parent_cp.product_id
        WHERE bi.level_num < p_max_levels
          AND parent_bom.status = 'ACTIVE'
          AND CURRENT_DATE BETWEEN parent_bom.effective_date AND COALESCE(parent_bom.expiry_date, '2099-12-31')
          AND NOT (parent_bc.component_product_id = ANY(bi.path_check)) -- Prevent circular references
    )
    SELECT * FROM bom_implosion
    ORDER BY level_num, parent_product_id;
END;
$$ LANGUAGE plpgsql;

-- Function to calculate BOM cost with component rollup
CREATE OR REPLACE FUNCTION calculate_bom_cost(
    p_bom_id INTEGER,
    p_cost_basis VARCHAR(20) DEFAULT 'FIFO'
)
RETURNS DECIMAL(15,4) AS $$
DECLARE
    total_material_cost DECIMAL(15,4) := 0;
    labor_cost DECIMAL(15,4) := 0;
    overhead_cost DECIMAL(15,4) := 0;
    component_record RECORD;
    component_cost DECIMAL(15,4);
BEGIN
    -- Get labor and overhead costs from BOM header
    SELECT labor_cost_per_unit, overhead_cost_per_unit
    INTO labor_cost, overhead_cost
    FROM bill_of_materials
    WHERE bom_id = p_bom_id;
    
    -- Calculate material cost from components
    FOR component_record IN 
        SELECT bc.component_product_id, bc.effective_quantity, p.product_type
        FROM bom_components bc
        JOIN products p ON bc.component_product_id = p.product_id
        WHERE bc.bom_id = p_bom_id
    LOOP
        IF component_record.product_type = 'RAW_MATERIAL' THEN
            -- Use standard cost for raw materials
            SELECT COALESCE(standard_cost, 0) * component_record.effective_quantity
            INTO component_cost
            FROM products 
            WHERE product_id = component_record.component_product_id;
            
        ELSIF component_record.product_type = 'SEMI_FINISHED' THEN
            -- Recursively calculate cost for semi-finished products
            SELECT COALESCE(total_cost, 0) * component_record.effective_quantity
            INTO component_cost
            FROM bom_cost_calculations bcc
            JOIN bill_of_materials bom ON bcc.bom_id = bom.bom_id
            WHERE bom.parent_product_id = component_record.component_product_id
              AND bcc.is_current = TRUE
              AND bom.status = 'ACTIVE';
            
            -- If no BOM cost found, use standard cost
            IF component_cost IS NULL THEN
                SELECT COALESCE(standard_cost, 0) * component_record.effective_quantity
                INTO component_cost
                FROM products 
                WHERE product_id = component_record.component_product_id;
            END IF;
            
        ELSE
            -- Use standard cost for other product types
            SELECT COALESCE(standard_cost, 0) * component_record.effective_quantity
            INTO component_cost
            FROM products 
            WHERE product_id = component_record.component_product_id;
        END IF;
        
        total_material_cost := total_material_cost + COALESCE(component_cost, 0);
    END LOOP;
    
    RETURN total_material_cost + labor_cost + overhead_cost;
END;
$$ LANGUAGE plpgsql;

-- ==============================================================================
-- INDEXES FOR BOM PERFORMANCE
-- ==============================================================================

-- BOM hierarchy indexes
CREATE INDEX idx_bom_parent_product ON bill_of_materials(parent_product_id, status)
    WHERE status = 'ACTIVE';

CREATE INDEX idx_bom_effective_dates ON bill_of_materials(effective_date, expiry_date, status)
    WHERE status = 'ACTIVE';

CREATE INDEX idx_bom_components_bom ON bom_components(bom_id, sequence_number);

CREATE INDEX idx_bom_components_product ON bom_components(component_product_id);

-- BOM explosion optimization
CREATE INDEX idx_bom_explosion ON bom_components(component_product_id)
    WHERE component_product_id IN (
        SELECT product_id FROM products WHERE product_type = 'SEMI_FINISHED'
    );

-- Cost calculation indexes
CREATE INDEX idx_bom_cost_current ON bom_cost_calculations(bom_id, is_current)
    WHERE is_current = TRUE;

CREATE INDEX idx_bom_cost_date ON bom_cost_calculations(calculation_date DESC);

-- ==============================================================================
-- VIEWS FOR BOM REPORTING
-- ==============================================================================

-- Active BOMs summary
CREATE VIEW active_boms_summary AS
SELECT 
    bom.bom_id,
    bom.parent_product_id,
    p.product_code,
    p.product_name,
    p.product_type,
    bom.bom_version,
    bom.bom_name,
    bom.effective_date,
    bom.expiry_date,
    COUNT(bc.bom_component_id) as component_count,
    bom.base_quantity,
    bom.yield_percentage,
    COALESCE(bcc.total_cost, 0) as current_total_cost,
    bcc.calculation_date as cost_calculation_date
FROM bill_of_materials bom
JOIN products p ON bom.parent_product_id = p.product_id
LEFT JOIN bom_components bc ON bom.bom_id = bc.bom_id
LEFT JOIN bom_cost_calculations bcc ON bom.bom_id = bcc.bom_id AND bcc.is_current = TRUE
WHERE bom.status = 'ACTIVE'
  AND CURRENT_DATE BETWEEN bom.effective_date AND COALESCE(bom.expiry_date, '2099-12-31')
GROUP BY bom.bom_id, bom.parent_product_id, p.product_code, p.product_name, 
         p.product_type, bom.bom_version, bom.bom_name, bom.effective_date,
         bom.expiry_date, bom.base_quantity, bom.yield_percentage,
         bcc.total_cost, bcc.calculation_date;

COMMENT ON VIEW active_boms_summary IS 'Summary of all active BOMs with component counts and current costs';

-- ==============================================================================
-- CONSTRAINTS FOR CIRCULAR REFERENCE PREVENTION
-- ==============================================================================

-- Function to check for circular references in BOM hierarchy
CREATE OR REPLACE FUNCTION check_bom_circular_reference()
RETURNS TRIGGER AS $$
DECLARE
    circular_found BOOLEAN := FALSE;
BEGIN
    -- Check if adding this component would create a circular reference
    WITH RECURSIVE bom_check AS (
        -- Start with the new component
        SELECT 
            NEW.component_product_id as product_id,
            1 as level_num,
            ARRAY[NEW.component_product_id] as path
        
        UNION ALL
        
        -- Follow the BOM hierarchy
        SELECT 
            bc.component_product_id,
            bc_check.level_num + 1,
            bc_check.path || bc.component_product_id
        FROM bom_check bc_check
        JOIN bill_of_materials bom ON bc_check.product_id = bom.parent_product_id
        JOIN bom_components bc ON bom.bom_id = bc.bom_id
        WHERE bc_check.level_num < 20 -- Prevent infinite loops
          AND bom.status = 'ACTIVE'
          AND NOT (bc.component_product_id = ANY(bc_check.path))
    )
    SELECT TRUE INTO circular_found
    FROM bom_check
    JOIN bill_of_materials parent_bom ON NEW.bom_id = parent_bom.bom_id
    WHERE bom_check.product_id = parent_bom.parent_product_id
    LIMIT 1;
    
    IF circular_found THEN
        RAISE EXCEPTION 'Circular reference detected: Component % cannot be added to BOM % as it would create a circular dependency', 
            NEW.component_product_id, NEW.bom_id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_bom_circular_reference_check
    BEFORE INSERT OR UPDATE ON bom_components
    FOR EACH ROW
    EXECUTE FUNCTION check_bom_circular_reference();

-- ==============================================================================
-- GRANTS AND PERMISSIONS
-- ==============================================================================

-- Grant permissions to application roles (uncomment when roles are created)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON bill_of_materials TO mrp_admin;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON bom_components TO mrp_admin;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON bom_cost_calculations TO mrp_admin;

-- GRANT SELECT ON bill_of_materials TO mrp_readonly;
-- GRANT SELECT ON bom_components TO mrp_readonly;
-- GRANT SELECT ON bom_cost_calculations TO mrp_readonly;
-- GRANT SELECT ON active_boms_summary TO mrp_readonly;

-- ==============================================================================
-- SCRIPT COMPLETION
-- ==============================================================================

SELECT 'BOM Tables Created Successfully' AS status,
       'Nested hierarchy support enabled' AS hierarchy_status,
       'Circular reference prevention installed' AS circular_check_status,
       'Cost calculation functions ready' AS cost_calculation_status;