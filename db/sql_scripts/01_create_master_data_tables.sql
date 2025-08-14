-- ==============================================================================
-- Horoz Demir MRP System - Master Data Tables
-- ==============================================================================
-- This script creates the master data tables for the MRP system including
-- warehouses, products, suppliers, and their relationships.
-- ==============================================================================

-- Drop tables if they exist (in reverse dependency order)
DROP TABLE IF EXISTS product_suppliers CASCADE;
DROP TABLE IF EXISTS suppliers CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS warehouses CASCADE;

-- ==============================================================================
-- WAREHOUSES TABLE
-- ==============================================================================
-- Defines the 4 main storage locations for different product types
-- Supports: RAW_MATERIALS, SEMI_FINISHED, FINISHED_PRODUCTS, PACKAGING
-- ==============================================================================

CREATE TABLE warehouses (
    warehouse_id SERIAL PRIMARY KEY,
    warehouse_code VARCHAR(10) UNIQUE NOT NULL,
    warehouse_name VARCHAR(100) NOT NULL,
    warehouse_type VARCHAR(20) NOT NULL,
    location VARCHAR(200),
    manager_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Business rule constraints
    CONSTRAINT chk_warehouse_type CHECK (
        warehouse_type IN ('RAW_MATERIALS', 'SEMI_FINISHED', 'FINISHED_PRODUCTS', 'PACKAGING')
    ),
    CONSTRAINT chk_warehouse_code_format CHECK (
        warehouse_code ~ '^[A-Z0-9]{2,10}$'
    )
);

-- Add table and column comments
COMMENT ON TABLE warehouses IS 'Master table for warehouse locations and types';
COMMENT ON COLUMN warehouses.warehouse_type IS 'Type of materials stored: RAW_MATERIALS, SEMI_FINISHED, FINISHED_PRODUCTS, PACKAGING';
COMMENT ON COLUMN warehouses.warehouse_code IS 'Unique warehouse identifier code (2-10 alphanumeric characters)';

-- ==============================================================================
-- PRODUCTS TABLE
-- ==============================================================================
-- Master catalog of all items including raw materials, semi-finished products,
-- finished products, and packaging materials
-- ==============================================================================

CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    product_code VARCHAR(50) UNIQUE NOT NULL,
    product_name VARCHAR(200) NOT NULL,
    product_type VARCHAR(20) NOT NULL,
    unit_of_measure VARCHAR(20) NOT NULL,
    minimum_stock_level DECIMAL(15,4) DEFAULT 0,
    critical_stock_level DECIMAL(15,4) DEFAULT 0,
    standard_cost DECIMAL(15,4) DEFAULT 0,
    description TEXT,
    specifications JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Business rule constraints
    CONSTRAINT chk_product_type CHECK (
        product_type IN ('RAW_MATERIAL', 'SEMI_FINISHED', 'FINISHED_PRODUCT', 'PACKAGING')
    ),
    CONSTRAINT chk_stock_levels CHECK (
        minimum_stock_level >= 0 AND 
        critical_stock_level >= 0 AND 
        critical_stock_level <= minimum_stock_level
    ),
    CONSTRAINT chk_standard_cost CHECK (standard_cost >= 0),
    CONSTRAINT chk_product_code_format CHECK (
        product_code ~ '^[A-Z0-9\-]{3,50}$'
    )
);

-- Add table and column comments
COMMENT ON TABLE products IS 'Master catalog of all products and materials in the system';
COMMENT ON COLUMN products.product_type IS 'Product category: RAW_MATERIAL, SEMI_FINISHED, FINISHED_PRODUCT, PACKAGING';
COMMENT ON COLUMN products.specifications IS 'JSON field for flexible product specifications and attributes';
COMMENT ON COLUMN products.minimum_stock_level IS 'Minimum stock level before reorder alert';
COMMENT ON COLUMN products.critical_stock_level IS 'Critical stock level for urgent reorder';

-- ==============================================================================
-- SUPPLIERS TABLE
-- ==============================================================================
-- Master table for vendor management and supplier information
-- Includes performance ratings and contact details
-- ==============================================================================

CREATE TABLE suppliers (
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
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Business rule constraints
    CONSTRAINT chk_lead_time CHECK (lead_time_days >= 0),
    CONSTRAINT chk_quality_rating CHECK (quality_rating >= 0.0 AND quality_rating <= 5.0),
    CONSTRAINT chk_delivery_rating CHECK (delivery_rating >= 0.0 AND delivery_rating <= 5.0),
    CONSTRAINT chk_price_rating CHECK (price_rating >= 0.0 AND price_rating <= 5.0),
    CONSTRAINT chk_email_format CHECK (
        email IS NULL OR email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
    ),
    CONSTRAINT chk_supplier_code_format CHECK (
        supplier_code ~ '^[A-Z0-9]{2,20}$'
    )
);

-- Add table and column comments
COMMENT ON TABLE suppliers IS 'Master table for supplier information and performance tracking';
COMMENT ON COLUMN suppliers.quality_rating IS 'Supplier quality rating from 0.0 to 5.0';
COMMENT ON COLUMN suppliers.delivery_rating IS 'Supplier delivery performance rating from 0.0 to 5.0';
COMMENT ON COLUMN suppliers.price_rating IS 'Supplier price competitiveness rating from 0.0 to 5.0';
COMMENT ON COLUMN suppliers.lead_time_days IS 'Standard lead time in days for this supplier';

-- ==============================================================================
-- PRODUCT_SUPPLIERS TABLE
-- ==============================================================================
-- Many-to-many relationship between products and suppliers
-- Manages supplier-specific pricing, lead times, and preferences
-- ==============================================================================

CREATE TABLE product_suppliers (
    product_supplier_id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    supplier_product_code VARCHAR(50),
    unit_price DECIMAL(15,4) NOT NULL,
    minimum_order_qty DECIMAL(15,4) DEFAULT 0,
    lead_time_days INTEGER DEFAULT 0,
    is_preferred BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Foreign key constraints
    CONSTRAINT fk_product_suppliers_product 
        FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE,
    CONSTRAINT fk_product_suppliers_supplier 
        FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id) ON DELETE CASCADE,
    
    -- Business rule constraints
    CONSTRAINT chk_unit_price CHECK (unit_price > 0),
    CONSTRAINT chk_minimum_order_qty CHECK (minimum_order_qty >= 0),
    CONSTRAINT chk_lead_time_days CHECK (lead_time_days >= 0),
    
    -- Unique constraint to prevent duplicate product-supplier combinations
    CONSTRAINT uk_product_supplier UNIQUE (product_id, supplier_id)
);

-- Add table and column comments
COMMENT ON TABLE product_suppliers IS 'Many-to-many relationship between products and suppliers with pricing and lead time information';
COMMENT ON COLUMN product_suppliers.supplier_product_code IS 'Product code used by the supplier for this product';
COMMENT ON COLUMN product_suppliers.is_preferred IS 'Indicates if this supplier is preferred for this product';
COMMENT ON COLUMN product_suppliers.unit_price IS 'Unit price from this supplier for this product';

-- ==============================================================================
-- TRIGGERS FOR UPDATED_AT TIMESTAMPS
-- ==============================================================================

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for all tables with updated_at columns
CREATE TRIGGER trg_warehouses_updated_at
    BEFORE UPDATE ON warehouses
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_products_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_suppliers_updated_at
    BEFORE UPDATE ON suppliers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_product_suppliers_updated_at
    BEFORE UPDATE ON product_suppliers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ==============================================================================
-- INITIAL DATA SEEDING
-- ==============================================================================

-- Insert the 4 required warehouse types
INSERT INTO warehouses (warehouse_code, warehouse_name, warehouse_type, location) VALUES
    ('RM01', 'Raw Materials Warehouse', 'RAW_MATERIALS', 'Building A - Ground Floor'),
    ('SF01', 'Semi-Finished Products Warehouse', 'SEMI_FINISHED', 'Building A - First Floor'),
    ('FP01', 'Finished Products Warehouse', 'FINISHED_PRODUCTS', 'Building B - Ground Floor'),
    ('PK01', 'Packaging Materials Warehouse', 'PACKAGING', 'Building C - Storage Area');

-- ==============================================================================
-- INDEXES FOR PERFORMANCE
-- ==============================================================================

-- Warehouse indexes
CREATE INDEX idx_warehouses_type ON warehouses(warehouse_type);
CREATE INDEX idx_warehouses_active ON warehouses(is_active) WHERE is_active = TRUE;

-- Product indexes
CREATE INDEX idx_products_type ON products(product_type);
CREATE INDEX idx_products_active ON products(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_products_stock_level ON products(product_type, minimum_stock_level) 
    WHERE is_active = TRUE;

-- Supplier indexes
CREATE INDEX idx_suppliers_active ON suppliers(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_suppliers_performance ON suppliers(quality_rating, delivery_rating, price_rating)
    WHERE is_active = TRUE;

-- Product-supplier relationship indexes
CREATE INDEX idx_product_suppliers_product ON product_suppliers(product_id) WHERE is_active = TRUE;
CREATE INDEX idx_product_suppliers_supplier ON product_suppliers(supplier_id) WHERE is_active = TRUE;
CREATE INDEX idx_product_suppliers_preferred ON product_suppliers(product_id, is_preferred) 
    WHERE is_preferred = TRUE AND is_active = TRUE;

-- ==============================================================================
-- GRANTS AND PERMISSIONS
-- ==============================================================================

-- Grant permissions to application roles (uncomment when roles are created)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON warehouses TO mrp_admin;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON products TO mrp_admin;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON suppliers TO mrp_admin;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON product_suppliers TO mrp_admin;

-- GRANT SELECT ON warehouses TO mrp_readonly;
-- GRANT SELECT ON products TO mrp_readonly;
-- GRANT SELECT ON suppliers TO mrp_readonly;
-- GRANT SELECT ON product_suppliers TO mrp_readonly;

-- ==============================================================================
-- SCRIPT COMPLETION
-- ==============================================================================

SELECT 'Master Data Tables Created Successfully' AS status,
       (SELECT COUNT(*) FROM warehouses) AS warehouses_count,
       (SELECT COUNT(*) FROM products) AS products_count,
       (SELECT COUNT(*) FROM suppliers) AS suppliers_count,
       (SELECT COUNT(*) FROM product_suppliers) AS product_suppliers_count;