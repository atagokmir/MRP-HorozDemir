-- ==============================================================================
-- Horoz Demir MRP System - Sample Data Insertion Script
-- ==============================================================================
-- This script inserts comprehensive sample data for testing FIFO logic,
-- nested BOM functionality, and all MRP system operations
-- ==============================================================================

-- Enable better error reporting
\set ON_ERROR_STOP on
\set VERBOSITY verbose

BEGIN;

-- ==============================================================================
-- SAMPLE PRODUCTS
-- ==============================================================================

-- Raw Materials
INSERT INTO products (product_code, product_name, product_type, unit_of_measure, minimum_stock_level, critical_stock_level, standard_cost, description) VALUES
('RM-STEEL-001', 'Steel Sheet 2mm', 'RAW_MATERIAL', 'M2', 1000.0000, 200.0000, 15.5000, 'High quality steel sheet for manufacturing'),
('RM-ALUM-001', 'Aluminum Rod 10mm', 'RAW_MATERIAL', 'M', 500.0000, 100.0000, 8.2500, 'Aluminum rod for structural components'),
('RM-PLASTIC-001', 'ABS Plastic Pellets', 'RAW_MATERIAL', 'KG', 2000.0000, 500.0000, 3.7500, 'High-grade ABS plastic for injection molding'),
('RM-RUBBER-001', 'EPDM Rubber Sheet', 'RAW_MATERIAL', 'M2', 300.0000, 50.0000, 12.0000, 'Weather-resistant rubber sheeting'),
('RM-PAINT-001', 'Industrial Paint Red', 'RAW_MATERIAL', 'LITER', 100.0000, 20.0000, 25.0000, 'High-durability industrial paint'),
('RM-BOLT-001', 'Stainless Steel Bolts M8', 'RAW_MATERIAL', 'PCS', 5000.0000, 1000.0000, 0.5500, 'Stainless steel bolts for assembly'),
('RM-WIRE-001', 'Copper Wire 2.5mm', 'RAW_MATERIAL', 'M', 1000.0000, 200.0000, 2.1500, 'Electrical copper wire'),
('RM-GLASS-001', 'Tempered Glass 5mm', 'RAW_MATERIAL', 'M2', 200.0000, 40.0000, 35.0000, 'Safety tempered glass panels');

-- Semi-Finished Products (can contain other semi-finished products)
INSERT INTO products (product_code, product_name, product_type, unit_of_measure, minimum_stock_level, critical_stock_level, standard_cost, description) VALUES
('SF-FRAME-001', 'Basic Frame Assembly', 'SEMI_FINISHED', 'PCS', 100.0000, 20.0000, 85.0000, 'Basic structural frame for products'),
('SF-PANEL-001', 'Painted Panel Assembly', 'SEMI_FINISHED', 'PCS', 150.0000, 30.0000, 65.0000, 'Painted panel with mounting hardware'),
('SF-MOTOR-001', 'Motor Sub-Assembly', 'SEMI_FINISHED', 'PCS', 50.0000, 10.0000, 125.0000, 'Complete motor assembly with wiring'),
('SF-CONTROL-001', 'Control Unit Assembly', 'SEMI_FINISHED', 'PCS', 75.0000, 15.0000, 95.0000, 'Electronic control unit with housing'),
('SF-BASE-001', 'Base Platform Assembly', 'SEMI_FINISHED', 'PCS', 80.0000, 16.0000, 155.0000, 'Structural base platform (contains SF-FRAME-001)');

-- Finished Products
INSERT INTO products (product_code, product_name, product_type, unit_of_measure, minimum_stock_level, critical_stock_level, standard_cost, description) VALUES
('FP-MACHINE-001', 'Industrial Machine Model A', 'FINISHED_PRODUCT', 'PCS', 10.0000, 2.0000, 750.0000, 'Complete industrial machine with all assemblies'),
('FP-MACHINE-002', 'Industrial Machine Model B', 'FINISHED_PRODUCT', 'PCS', 8.0000, 2.0000, 950.0000, 'Advanced industrial machine with enhanced features'),
('FP-DEVICE-001', 'Portable Device Unit', 'FINISHED_PRODUCT', 'PCS', 25.0000, 5.0000, 450.0000, 'Compact portable device for field use');

-- Packaging Materials
INSERT INTO products (product_code, product_name, product_type, unit_of_measure, minimum_stock_level, critical_stock_level, standard_cost, description) VALUES
('PK-BOX-001', 'Large Cardboard Box', 'PACKAGING', 'PCS', 200.0000, 50.0000, 2.5000, 'Large shipping box for finished products'),
('PK-BOX-002', 'Medium Cardboard Box', 'PACKAGING', 'PCS', 300.0000, 75.0000, 1.8000, 'Medium box for semi-finished items'),
('PK-FOAM-001', 'Protective Foam Insert', 'PACKAGING', 'PCS', 150.0000, 30.0000, 3.2000, 'Custom foam inserts for protection'),
('PK-TAPE-001', 'Packaging Tape', 'PACKAGING', 'ROLL', 50.0000, 10.0000, 4.5000, 'Heavy-duty packaging tape'),
('PK-LABEL-001', 'Shipping Labels', 'PACKAGING', 'PCS', 1000.0000, 200.0000, 0.1000, 'Pre-printed shipping labels');

-- ==============================================================================
-- SAMPLE SUPPLIERS
-- ==============================================================================

INSERT INTO suppliers (supplier_code, supplier_name, contact_person, email, phone, address, city, country, payment_terms, lead_time_days, quality_rating, delivery_rating, price_rating) VALUES
('SUP001', 'Metro Steel Industries', 'John Anderson', 'j.anderson@metrosteel.com', '+1-555-0101', '1234 Industrial Blvd', 'Detroit', 'USA', 'Net 30', 7, 4.5, 4.2, 3.8),
('SUP002', 'Advanced Aluminum Corp', 'Sarah Chen', 's.chen@advancedalum.com', '+1-555-0102', '5678 Manufacturing Ave', 'Chicago', 'USA', 'Net 45', 10, 4.8, 4.1, 4.0),
('SUP003', 'Polymer Solutions Ltd', 'Mike Roberts', 'm.roberts@polymersol.com', '+1-555-0103', '9012 Chemical Lane', 'Houston', 'USA', '2/10 Net 30', 14, 4.3, 3.9, 4.2),
('SUP004', 'Rubber Dynamics Inc', 'Lisa Martinez', 'l.martinez@rubberdyn.com', '+1-555-0104', '3456 Elastomer St', 'Akron', 'USA', 'Net 30', 12, 4.1, 4.3, 3.7),
('SUP005', 'ElectroTech Components', 'David Kim', 'd.kim@electrotech.com', '+1-555-0105', '7890 Circuit Way', 'San Jose', 'USA', 'Net 15', 5, 4.7, 4.6, 3.9),
('SUP006', 'Global Packaging Solutions', 'Emma Johnson', 'e.johnson@globalpkg.com', '+1-555-0106', '2468 Packaging Pkwy', 'Atlanta', 'USA', 'Net 30', 8, 4.0, 4.4, 4.1);

-- ==============================================================================
-- PRODUCT-SUPPLIER RELATIONSHIPS
-- ==============================================================================

INSERT INTO product_suppliers (product_id, supplier_id, supplier_product_code, unit_price, minimum_order_qty, lead_time_days, is_preferred) VALUES
-- Steel from Metro Steel Industries
((SELECT product_id FROM products WHERE product_code = 'RM-STEEL-001'), (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP001'), 'MS-ST2MM-001', 15.5000, 100.0000, 7, true),
-- Aluminum from Advanced Aluminum Corp
((SELECT product_id FROM products WHERE product_code = 'RM-ALUM-001'), (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP002'), 'AA-ROD10-001', 8.2500, 50.0000, 10, true),
-- Plastic from Polymer Solutions
((SELECT product_id FROM products WHERE product_code = 'RM-PLASTIC-001'), (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP003'), 'PS-ABS-001', 3.7500, 500.0000, 14, true),
-- Rubber from Rubber Dynamics
((SELECT product_id FROM products WHERE product_code = 'RM-RUBBER-001'), (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP004'), 'RD-EPDM-001', 12.0000, 25.0000, 12, true),
-- Wire from ElectroTech
((SELECT product_id FROM products WHERE product_code = 'RM-WIRE-001'), (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP005'), 'ET-CU25-001', 2.1500, 100.0000, 5, true),
-- Bolts from Metro Steel (alternative supplier)
((SELECT product_id FROM products WHERE product_code = 'RM-BOLT-001'), (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP001'), 'MS-BOLT-M8', 0.5500, 1000.0000, 7, true),
-- Packaging from Global Packaging
((SELECT product_id FROM products WHERE product_code = 'PK-BOX-001'), (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP006'), 'GP-LBOX-001', 2.5000, 50.0000, 8, true),
((SELECT product_id FROM products WHERE product_code = 'PK-BOX-002'), (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP006'), 'GP-MBOX-001', 1.8000, 100.0000, 8, true),
((SELECT product_id FROM products WHERE product_code = 'PK-FOAM-001'), (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP006'), 'GP-FOAM-001', 3.2000, 25.0000, 8, true);

-- ==============================================================================
-- SAMPLE INVENTORY DATA (FIFO Testing)
-- ==============================================================================

-- Multiple batches with different entry dates for FIFO testing
-- Raw Material Steel - Multiple batches with different costs and dates
INSERT INTO inventory_items (product_id, warehouse_id, batch_number, entry_date, quantity_in_stock, unit_cost, supplier_id) VALUES
-- Older batches (should be consumed first in FIFO)
((SELECT product_id FROM products WHERE product_code = 'RM-STEEL-001'), (SELECT warehouse_id FROM warehouses WHERE warehouse_code = 'RM01'), 'STEEL-2024001', '2024-01-15 08:00:00', 500.0000, 15.0000, (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP001')),
((SELECT product_id FROM products WHERE product_code = 'RM-STEEL-001'), (SELECT warehouse_id FROM warehouses WHERE warehouse_code = 'RM01'), 'STEEL-2024002', '2024-02-01 09:30:00', 750.0000, 15.2500, (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP001')),
-- Newer batches (should be consumed later)
((SELECT product_id FROM products WHERE product_code = 'RM-STEEL-001'), (SELECT warehouse_id FROM warehouses WHERE warehouse_code = 'RM01'), 'STEEL-2024003', '2024-02-15 14:15:00', 600.0000, 15.8000, (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP001')),
((SELECT product_id FROM products WHERE product_code = 'RM-STEEL-001'), (SELECT warehouse_id FROM warehouses WHERE warehouse_code = 'RM01'), 'STEEL-2024004', '2024-03-01 10:45:00', 400.0000, 16.0000, (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP001'));

-- Aluminum batches for FIFO testing
INSERT INTO inventory_items (product_id, warehouse_id, batch_number, entry_date, quantity_in_stock, unit_cost, supplier_id) VALUES
((SELECT product_id FROM products WHERE product_code = 'RM-ALUM-001'), (SELECT warehouse_id FROM warehouses WHERE warehouse_code = 'RM01'), 'ALUM-2024001', '2024-01-20 11:00:00', 300.0000, 8.0000, (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP002')),
((SELECT product_id FROM products WHERE product_code = 'RM-ALUM-001'), (SELECT warehouse_id FROM warehouses WHERE warehouse_code = 'RM01'), 'ALUM-2024002', '2024-02-10 13:20:00', 400.0000, 8.5000, (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP002')),
((SELECT product_id FROM products WHERE product_code = 'RM-ALUM-001'), (SELECT warehouse_id FROM warehouses WHERE warehouse_code = 'RM01'), 'ALUM-2024003', '2024-02-25 16:30:00', 350.0000, 8.3000, (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP002'));

-- Other raw materials
INSERT INTO inventory_items (product_id, warehouse_id, batch_number, entry_date, quantity_in_stock, unit_cost, supplier_id) VALUES
((SELECT product_id FROM products WHERE product_code = 'RM-PLASTIC-001'), (SELECT warehouse_id FROM warehouses WHERE warehouse_code = 'RM01'), 'PLASTIC-2024001', '2024-01-25 12:00:00', 1500.0000, 3.5000, (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP003')),
((SELECT product_id FROM products WHERE product_code = 'RM-RUBBER-001'), (SELECT warehouse_id FROM warehouses WHERE warehouse_code = 'RM01'), 'RUBBER-2024001', '2024-02-05 14:30:00', 200.0000, 11.5000, (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP004')),
((SELECT product_id FROM products WHERE product_code = 'RM-BOLT-001'), (SELECT warehouse_id FROM warehouses WHERE warehouse_code = 'RM01'), 'BOLTS-2024001', '2024-01-30 09:15:00', 8000.0000, 0.5200, (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP001')),
((SELECT product_id FROM products WHERE product_code = 'RM-WIRE-001'), (SELECT warehouse_id FROM warehouses WHERE warehouse_code = 'RM01'), 'WIRE-2024001', '2024-02-12 11:45:00', 800.0000, 2.0000, (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP005'));

-- Semi-finished products inventory
INSERT INTO inventory_items (product_id, warehouse_id, batch_number, entry_date, quantity_in_stock, unit_cost, supplier_id) VALUES
((SELECT product_id FROM products WHERE product_code = 'SF-FRAME-001'), (SELECT warehouse_id FROM warehouses WHERE warehouse_code = 'SF01'), 'FRAME-2024001', '2024-02-20 10:00:00', 80.0000, 82.0000, NULL),
((SELECT product_id FROM products WHERE product_code = 'SF-PANEL-001'), (SELECT warehouse_id FROM warehouses WHERE warehouse_code = 'SF01'), 'PANEL-2024001', '2024-02-22 15:30:00', 120.0000, 63.5000, NULL),
((SELECT product_id FROM products WHERE product_code = 'SF-MOTOR-001'), (SELECT warehouse_id FROM warehouses WHERE warehouse_code = 'SF01'), 'MOTOR-2024001', '2024-02-18 13:15:00', 40.0000, 122.0000, NULL);

-- Packaging materials inventory
INSERT INTO inventory_items (product_id, warehouse_id, batch_number, entry_date, quantity_in_stock, unit_cost, supplier_id) VALUES
((SELECT product_id FROM products WHERE product_code = 'PK-BOX-001'), (SELECT warehouse_id FROM warehouses WHERE warehouse_code = 'PK01'), 'BOX-L-2024001', '2024-02-08 12:00:00', 150.0000, 2.4000, (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP006')),
((SELECT product_id FROM products WHERE product_code = 'PK-BOX-002'), (SELECT warehouse_id FROM warehouses WHERE warehouse_code = 'PK01'), 'BOX-M-2024001', '2024-02-10 14:20:00', 250.0000, 1.7500, (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP006')),
((SELECT product_id FROM products WHERE product_code = 'PK-FOAM-001'), (SELECT warehouse_id FROM warehouses WHERE warehouse_code = 'PK01'), 'FOAM-2024001', '2024-02-12 16:45:00', 100.0000, 3.1000, (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP006'));

-- ==============================================================================
-- BILL OF MATERIALS (NESTED BOM TESTING)
-- ==============================================================================

-- BOM for Basic Frame Assembly (SF-FRAME-001) - Uses raw materials
INSERT INTO bill_of_materials (parent_product_id, bom_version, bom_name, effective_date, status, base_quantity, yield_percentage, labor_cost_per_unit, overhead_cost_per_unit) VALUES
((SELECT product_id FROM products WHERE product_code = 'SF-FRAME-001'), '1.0', 'Basic Frame Assembly BOM v1.0', '2024-01-01', 'ACTIVE', 1.0000, 95.00, 15.0000, 8.0000);

-- Components for Basic Frame Assembly
INSERT INTO bom_components (bom_id, component_product_id, sequence_number, quantity_required, unit_of_measure, scrap_percentage) VALUES
((SELECT bom_id FROM bill_of_materials bom JOIN products p ON bom.parent_product_id = p.product_id WHERE p.product_code = 'SF-FRAME-001'), (SELECT product_id FROM products WHERE product_code = 'RM-STEEL-001'), 1, 2.5000, 'M2', 5.00),
((SELECT bom_id FROM bill_of_materials bom JOIN products p ON bom.parent_product_id = p.product_id WHERE p.product_code = 'SF-FRAME-001'), (SELECT product_id FROM products WHERE product_code = 'RM-ALUM-001'), 2, 3.0000, 'M', 3.00),
((SELECT bom_id FROM bill_of_materials bom JOIN products p ON bom.parent_product_id = p.product_id WHERE p.product_code = 'SF-FRAME-001'), (SELECT product_id FROM products WHERE product_code = 'RM-BOLT-001'), 3, 12.0000, 'PCS', 2.00);

-- BOM for Base Platform Assembly (SF-BASE-001) - Uses other semi-finished product (NESTED BOM)
INSERT INTO bill_of_materials (parent_product_id, bom_version, bom_name, effective_date, status, base_quantity, yield_percentage, labor_cost_per_unit, overhead_cost_per_unit) VALUES
((SELECT product_id FROM products WHERE product_code = 'SF-BASE-001'), '1.0', 'Base Platform Assembly BOM v1.0', '2024-01-01', 'ACTIVE', 1.0000, 92.00, 25.0000, 12.0000);

-- Components for Base Platform Assembly (includes nested SF-FRAME-001)
INSERT INTO bom_components (bom_id, component_product_id, sequence_number, quantity_required, unit_of_measure, scrap_percentage) VALUES
((SELECT bom_id FROM bill_of_materials bom JOIN products p ON bom.parent_product_id = p.product_id WHERE p.product_code = 'SF-BASE-001'), (SELECT product_id FROM products WHERE product_code = 'SF-FRAME-001'), 1, 2.0000, 'PCS', 1.00), -- NESTED BOM!
((SELECT bom_id FROM bill_of_materials bom JOIN products p ON bom.parent_product_id = p.product_id WHERE p.product_code = 'SF-BASE-001'), (SELECT product_id FROM products WHERE product_code = 'RM-STEEL-001'), 2, 4.0000, 'M2', 3.00),
((SELECT bom_id FROM bill_of_materials bom JOIN products p ON bom.parent_product_id = p.product_id WHERE p.product_code = 'SF-BASE-001'), (SELECT product_id FROM products WHERE product_code = 'RM-RUBBER-001'), 3, 1.5000, 'M2', 2.00);

-- BOM for Painted Panel Assembly (SF-PANEL-001)
INSERT INTO bill_of_materials (parent_product_id, bom_version, bom_name, effective_date, status, base_quantity, yield_percentage, labor_cost_per_unit, overhead_cost_per_unit) VALUES
((SELECT product_id FROM products WHERE product_code = 'SF-PANEL-001'), '1.0', 'Painted Panel Assembly BOM v1.0', '2024-01-01', 'ACTIVE', 1.0000, 90.00, 12.0000, 6.0000);

INSERT INTO bom_components (bom_id, component_product_id, sequence_number, quantity_required, unit_of_measure, scrap_percentage) VALUES
((SELECT bom_id FROM bill_of_materials bom JOIN products p ON bom.parent_product_id = p.product_id WHERE p.product_code = 'SF-PANEL-001'), (SELECT product_id FROM products WHERE product_code = 'RM-STEEL-001'), 1, 1.5000, 'M2', 4.00),
((SELECT bom_id FROM bill_of_materials bom JOIN products p ON bom.parent_product_id = p.product_id WHERE p.product_code = 'SF-PANEL-001'), (SELECT product_id FROM products WHERE product_code = 'RM-PAINT-001'), 2, 0.5000, 'LITER', 10.00),
((SELECT bom_id FROM bill_of_materials bom JOIN products p ON bom.parent_product_id = p.product_id WHERE p.product_code = 'SF-PANEL-001'), (SELECT product_id FROM products WHERE product_code = 'RM-BOLT-001'), 3, 8.0000, 'PCS', 2.00);

-- BOM for Motor Sub-Assembly (SF-MOTOR-001)
INSERT INTO bill_of_materials (parent_product_id, bom_version, bom_name, effective_date, status, base_quantity, yield_percentage, labor_cost_per_unit, overhead_cost_per_unit) VALUES
((SELECT product_id FROM products WHERE product_code = 'SF-MOTOR-001'), '1.0', 'Motor Sub-Assembly BOM v1.0', '2024-01-01', 'ACTIVE', 1.0000, 88.00, 18.0000, 10.0000);

INSERT INTO bom_components (bom_id, component_product_id, sequence_number, quantity_required, unit_of_measure, scrap_percentage) VALUES
((SELECT bom_id FROM bill_of_materials bom JOIN products p ON bom.parent_product_id = p.product_id WHERE p.product_code = 'SF-MOTOR-001'), (SELECT product_id FROM products WHERE product_code = 'RM-ALUM-001'), 1, 2.0000, 'M', 2.00),
((SELECT bom_id FROM bill_of_materials bom JOIN products p ON bom.parent_product_id = p.product_id WHERE p.product_code = 'SF-MOTOR-001'), (SELECT product_id FROM products WHERE product_code = 'RM-WIRE-001'), 2, 15.0000, 'M', 5.00),
((SELECT bom_id FROM bill_of_materials bom JOIN products p ON bom.parent_product_id = p.product_id WHERE p.product_code = 'SF-MOTOR-001'), (SELECT product_id FROM products WHERE product_code = 'RM-PLASTIC-001'), 3, 2.5000, 'KG', 3.00);

-- BOM for Industrial Machine Model A (FP-MACHINE-001) - Complex nested BOM
INSERT INTO bill_of_materials (parent_product_id, bom_version, bom_name, effective_date, status, base_quantity, yield_percentage, labor_cost_per_unit, overhead_cost_per_unit) VALUES
((SELECT product_id FROM products WHERE product_code = 'FP-MACHINE-001'), '1.0', 'Industrial Machine Model A BOM v1.0', '2024-01-01', 'ACTIVE', 1.0000, 85.00, 75.0000, 45.0000);

INSERT INTO bom_components (bom_id, component_product_id, sequence_number, quantity_required, unit_of_measure, scrap_percentage) VALUES
((SELECT bom_id FROM bill_of_materials bom JOIN products p ON bom.parent_product_id = p.product_id WHERE p.product_code = 'FP-MACHINE-001'), (SELECT product_id FROM products WHERE product_code = 'SF-BASE-001'), 1, 1.0000, 'PCS', 1.00), -- NESTED!
((SELECT bom_id FROM bill_of_materials bom JOIN products p ON bom.parent_product_id = p.product_id WHERE p.product_code = 'FP-MACHINE-001'), (SELECT product_id FROM products WHERE product_code = 'SF-PANEL-001'), 2, 3.0000, 'PCS', 2.00), -- NESTED!
((SELECT bom_id FROM bill_of_materials bom JOIN products p ON bom.parent_product_id = p.product_id WHERE p.product_code = 'FP-MACHINE-001'), (SELECT product_id FROM products WHERE product_code = 'SF-MOTOR-001'), 3, 2.0000, 'PCS', 1.00), -- NESTED!
((SELECT bom_id FROM bill_of_materials bom JOIN products p ON bom.parent_product_id = p.product_id WHERE p.product_code = 'FP-MACHINE-001'), (SELECT product_id FROM products WHERE product_code = 'RM-GLASS-001'), 4, 2.0000, 'M2', 5.00);

-- ==============================================================================
-- SAMPLE PRODUCTION ORDERS (FIFO ALLOCATION TESTING)
-- ==============================================================================

-- Production order for Basic Frame Assembly
INSERT INTO production_orders (order_number, product_id, bom_id, warehouse_id, order_date, planned_start_date, planned_completion_date, planned_quantity, status, priority, estimated_cost) VALUES
('PO000001', 
 (SELECT product_id FROM products WHERE product_code = 'SF-FRAME-001'),
 (SELECT bom_id FROM bill_of_materials bom JOIN products p ON bom.parent_product_id = p.product_id WHERE p.product_code = 'SF-FRAME-001'),
 (SELECT warehouse_id FROM warehouses WHERE warehouse_code = 'SF01'),
 '2024-03-01', '2024-03-05', '2024-03-08', 20.0000, 'PLANNED', 3, 1800.0000);

-- Production order components for Frame Assembly (will test FIFO allocation)
INSERT INTO production_order_components (production_order_id, component_product_id, required_quantity, unit_cost) VALUES
-- Steel requirement (20 frames × 2.5 M2 × 1.05 scrap = 52.5 M2)
((SELECT production_order_id FROM production_orders WHERE order_number = 'PO000001'), 
 (SELECT product_id FROM products WHERE product_code = 'RM-STEEL-001'), 52.5000, 15.5000),
-- Aluminum requirement (20 frames × 3.0 M × 1.03 scrap = 61.8 M)
((SELECT production_order_id FROM production_orders WHERE order_number = 'PO000001'), 
 (SELECT product_id FROM products WHERE product_code = 'RM-ALUM-001'), 61.8000, 8.2500),
-- Bolts requirement (20 frames × 12 PCS × 1.02 scrap = 244.8 ≈ 245 PCS)
((SELECT production_order_id FROM production_orders WHERE order_number = 'PO000001'), 
 (SELECT product_id FROM products WHERE product_code = 'RM-BOLT-001'), 245.0000, 0.5500);

-- Production order for Industrial Machine (tests nested BOM allocation)
INSERT INTO production_orders (order_number, product_id, bom_id, warehouse_id, order_date, planned_start_date, planned_completion_date, planned_quantity, status, priority, estimated_cost) VALUES
('PO000002', 
 (SELECT product_id FROM products WHERE product_code = 'FP-MACHINE-001'),
 (SELECT bom_id FROM bill_of_materials bom JOIN products p ON bom.parent_product_id = p.product_id WHERE p.product_code = 'FP-MACHINE-001'),
 (SELECT warehouse_id FROM warehouses WHERE warehouse_code = 'FP01'),
 '2024-03-02', '2024-03-10', '2024-03-20', 5.0000, 'PLANNED', 1, 4250.0000);

-- ==============================================================================
-- SAMPLE PURCHASE ORDERS
-- ==============================================================================

-- Purchase order for steel replenishment
INSERT INTO purchase_orders (po_number, supplier_id, warehouse_id, order_date, expected_delivery_date, total_amount, currency, status) VALUES
('PUR000001', 
 (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP001'),
 (SELECT warehouse_id FROM warehouses WHERE warehouse_code = 'RM01'),
 '2024-03-01', '2024-03-08', 7750.0000, 'USD', 'SENT');

INSERT INTO purchase_order_items (purchase_order_id, product_id, quantity_ordered, unit_price) VALUES
((SELECT purchase_order_id FROM purchase_orders WHERE po_number = 'PUR000001'),
 (SELECT product_id FROM products WHERE product_code = 'RM-STEEL-001'), 500.0000, 15.5000);

-- Purchase order for multiple items
INSERT INTO purchase_orders (po_number, supplier_id, warehouse_id, order_date, expected_delivery_date, total_amount, currency, status) VALUES
('PUR000002', 
 (SELECT supplier_id FROM suppliers WHERE supplier_code = 'SUP006'),
 (SELECT warehouse_id FROM warehouses WHERE warehouse_code = 'PK01'),
 '2024-02-28', '2024-03-07', 425.0000, 'USD', 'CONFIRMED');

INSERT INTO purchase_order_items (purchase_order_id, product_id, quantity_ordered, unit_price) VALUES
((SELECT purchase_order_id FROM purchase_orders WHERE po_number = 'PUR000002'),
 (SELECT product_id FROM products WHERE product_code = 'PK-BOX-001'), 100.0000, 2.5000),
((SELECT purchase_order_id FROM purchase_orders WHERE po_number = 'PUR000002'),
 (SELECT product_id FROM products WHERE product_code = 'PK-FOAM-001'), 50.0000, 3.2000),
((SELECT purchase_order_id FROM purchase_orders WHERE po_number = 'PUR000002'),
 (SELECT product_id FROM products WHERE product_code = 'PK-TAPE-001'), 5.0000, 4.5000);

-- ==============================================================================
-- SAMPLE CRITICAL STOCK ALERTS
-- ==============================================================================

-- Create some critical stock alerts for testing
INSERT INTO critical_stock_alerts (product_id, warehouse_id, current_stock, minimum_level, critical_level, alert_type, alert_date) VALUES
-- Paint is running low (not in inventory above, so stock is 0)
((SELECT product_id FROM products WHERE product_code = 'RM-PAINT-001'), 
 (SELECT warehouse_id FROM warehouses WHERE warehouse_code = 'RM01'), 
 0.0000, 100.0000, 20.0000, 'OUT_OF_STOCK', '2024-03-01 09:00:00'),
-- Glass is below critical level (not in inventory above)
((SELECT product_id FROM products WHERE product_code = 'RM-GLASS-001'), 
 (SELECT warehouse_id FROM warehouses WHERE warehouse_code = 'RM01'), 
 15.0000, 200.0000, 40.0000, 'CRITICAL', '2024-03-01 10:30:00');

-- ==============================================================================
-- COST CALCULATION HISTORY SAMPLES
-- ==============================================================================

-- Sample cost calculations for products with BOMs
INSERT INTO cost_calculation_history (product_id, calculation_date, cost_type, material_cost, labor_cost, overhead_cost, total_unit_cost, source_type, calculation_method) VALUES
((SELECT product_id FROM products WHERE product_code = 'SF-FRAME-001'), '2024-03-01', 'FIFO', 62.0000, 15.0000, 8.0000, 85.0000, 'BOM_CALCULATION', 'Rolled up from BOM component costs using FIFO inventory costs'),
((SELECT product_id FROM products WHERE product_code = 'SF-FRAME-001'), '2024-03-01', 'STANDARD', 60.0000, 15.0000, 8.0000, 83.0000, 'BOM_CALCULATION', 'Standard costs from product master data'),
((SELECT product_id FROM products WHERE product_code = 'FP-MACHINE-001'), '2024-03-01', 'FIFO', 630.0000, 75.0000, 45.0000, 750.0000, 'BOM_CALCULATION', 'Complex nested BOM with FIFO component costs');

COMMIT;

-- ==============================================================================
-- DATA VERIFICATION QUERIES
-- ==============================================================================

-- Summary of inserted data
SELECT 'Sample Data Insertion Complete!' as status;

SELECT 'Products by Type:' as summary;
SELECT product_type, COUNT(*) as count 
FROM products 
GROUP BY product_type 
ORDER BY product_type;

SELECT 'Inventory Items by Warehouse:' as summary;
SELECT w.warehouse_name, COUNT(ii.inventory_item_id) as items, 
       SUM(ii.quantity_in_stock) as total_quantity,
       SUM(ii.total_cost) as total_value
FROM warehouses w
LEFT JOIN inventory_items ii ON w.warehouse_id = ii.warehouse_id
GROUP BY w.warehouse_id, w.warehouse_name
ORDER BY w.warehouse_name;

SELECT 'BOMs with Component Counts:' as summary;
SELECT p.product_code, b.bom_name, COUNT(bc.bom_component_id) as component_count
FROM bill_of_materials b
JOIN products p ON b.parent_product_id = p.product_id
LEFT JOIN bom_components bc ON b.bom_id = bc.bom_id
GROUP BY b.bom_id, p.product_code, b.bom_name
ORDER BY p.product_code;

SELECT 'FIFO Test - Steel Inventory Ordered by Entry Date:' as summary;
SELECT ii.batch_number, ii.entry_date, ii.quantity_in_stock, ii.unit_cost,
       ROW_NUMBER() OVER (ORDER BY ii.entry_date, ii.inventory_item_id) as fifo_order
FROM inventory_items ii
JOIN products p ON ii.product_id = p.product_id
WHERE p.product_code = 'RM-STEEL-001'
ORDER BY ii.entry_date, ii.inventory_item_id;

-- Show nested BOM structure
SELECT 'Nested BOM Test - Machine Components:' as summary;
WITH RECURSIVE bom_explosion AS (
    -- Direct components
    SELECT 
        1 as level,
        p_parent.product_code as parent_code,
        p_comp.product_code as component_code,
        p_comp.product_type,
        bc.quantity_required,
        CAST(p_parent.product_code || ' -> ' || p_comp.product_code AS TEXT) as path
    FROM bill_of_materials bom
    JOIN products p_parent ON bom.parent_product_id = p_parent.product_id
    JOIN bom_components bc ON bom.bom_id = bc.bom_id
    JOIN products p_comp ON bc.component_product_id = p_comp.product_id
    WHERE p_parent.product_code = 'FP-MACHINE-001'
    
    UNION ALL
    
    -- Recursive components
    SELECT 
        be.level + 1,
        be.parent_code,
        p_comp.product_code,
        p_comp.product_type,
        bc.quantity_required * be.quantity_required,
        be.path || ' -> ' || p_comp.product_code
    FROM bom_explosion be
    JOIN bill_of_materials bom ON be.component_code = (
        SELECT product_code FROM products WHERE product_id = bom.parent_product_id
    )
    JOIN bom_components bc ON bom.bom_id = bc.bom_id
    JOIN products p_comp ON bc.component_product_id = p_comp.product_id
    WHERE be.level < 5 -- Prevent infinite loops
      AND p_comp.product_type IN ('RAW_MATERIAL', 'SEMI_FINISHED')
)
SELECT level, component_code, product_type, quantity_required, path
FROM bom_explosion
ORDER BY level, component_code;

SELECT '=== Sample data insertion completed successfully! ===' as final_status;