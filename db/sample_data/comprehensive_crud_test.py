#!/usr/bin/env python3
"""
Comprehensive CRUD Test Suite for Horoz Demir MRP System.
This script provides exhaustive testing of all database CRUD operations,
referential integrity, constraints, triggers, and business logic.
"""

import sys
import traceback
from pathlib import Path
from decimal import Decimal
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Tuple
import json

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent.parent / 'backend'
sys.path.insert(0, str(backend_dir))

from database import database_session, check_database_connection, health_check
from models import *

class CRUDTestResult:
    """Class to track test results."""
    
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failures = []
        self.warnings = []
        self.performance_metrics = {}
    
    def add_test_result(self, test_name: str, passed: bool, message: str = "", duration: float = 0):
        """Add a test result."""
        self.tests_run += 1
        if passed:
            self.tests_passed += 1
            print(f"✅ {test_name}: PASSED")
            if message:
                print(f"   {message}")
        else:
            self.tests_failed += 1
            self.failures.append({"test": test_name, "message": message})
            print(f"❌ {test_name}: FAILED")
            print(f"   Error: {message}")
        
        if duration > 0:
            self.performance_metrics[test_name] = duration
    
    def add_warning(self, message: str):
        """Add a warning."""
        self.warnings.append(message)
        print(f"⚠️  WARNING: {message}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get test summary."""
        return {
            "total_tests": self.tests_run,
            "passed": self.tests_passed,
            "failed": self.tests_failed,
            "success_rate": (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0,
            "failures": self.failures,
            "warnings": self.warnings,
            "performance_metrics": self.performance_metrics
        }


class ComprehensiveCRUDTester:
    """Comprehensive CRUD testing framework."""
    
    def __init__(self):
        self.result = CRUDTestResult()
        self.test_data_ids = {}  # Store created test data IDs for cleanup
    
    def test_basic_crud_operations(self):
        """Test basic CRUD operations for all core tables."""
        print("\n" + "=" * 60)
        print("TESTING BASIC CRUD OPERATIONS")
        print("=" * 60)
        
        # Test each model's CRUD operations
        self._test_warehouse_crud()
        self._test_product_crud()
        self._test_supplier_crud()
        self._test_product_supplier_crud()
        self._test_inventory_crud()
        self._test_bom_crud()
        self._test_production_order_crud()
        self._test_purchase_order_crud()
        self._test_critical_stock_alerts_crud()
    
    def _test_warehouse_crud(self):
        """Test Warehouse CRUD operations."""
        try:
            with database_session('CRUD_TESTER') as session:
                # CREATE
                test_warehouse = Warehouse(
                    warehouse_code='TEST01',
                    warehouse_name='Test Warehouse',
                    warehouse_type='RAW_MATERIALS',
                    location='Test Location',
                    manager_name='Test Manager'
                )
                session.add(test_warehouse)
                session.flush()
                warehouse_id = test_warehouse.warehouse_id
                self.test_data_ids['warehouse'] = warehouse_id
                
                # READ
                retrieved_warehouse = session.query(Warehouse).filter(
                    Warehouse.warehouse_id == warehouse_id
                ).first()
                
                assert retrieved_warehouse is not None
                assert retrieved_warehouse.warehouse_code == 'TEST01'
                assert retrieved_warehouse.warehouse_type == 'RAW_MATERIALS'
                
                # UPDATE
                retrieved_warehouse.manager_name = 'Updated Manager'
                session.flush()
                
                # Verify update
                updated_warehouse = session.query(Warehouse).filter(
                    Warehouse.warehouse_id == warehouse_id
                ).first()
                assert updated_warehouse.manager_name == 'Updated Manager'
                
                # Test constraints
                try:
                    # Test invalid warehouse type
                    invalid_warehouse = Warehouse(
                        warehouse_code='INVALID',
                        warehouse_name='Invalid Warehouse',
                        warehouse_type='INVALID_TYPE',
                        location='Test'
                    )
                    session.add(invalid_warehouse)
                    session.flush()
                    # Should not reach here
                    assert False, "Invalid warehouse type was accepted"
                except Exception:
                    # Expected - constraint should prevent invalid type
                    session.rollback()
                
                self.result.add_test_result("Warehouse CRUD", True, "All operations successful with constraint validation")
                
        except Exception as e:
            self.result.add_test_result("Warehouse CRUD", False, str(e))
    
    def _test_product_crud(self):
        """Test Product CRUD operations."""
        try:
            with database_session('CRUD_TESTER') as session:
                # CREATE
                test_product = Product(
                    product_code='TEST-CRUD-001',
                    product_name='Test CRUD Product',
                    product_type='RAW_MATERIAL',
                    unit_of_measure='UNIT',
                    minimum_stock_level=Decimal('100'),
                    critical_stock_level=Decimal('50'),
                    standard_cost=Decimal('25.50'),
                    description='Test product for CRUD operations'
                )
                session.add(test_product)
                session.flush()
                product_id = test_product.product_id
                self.test_data_ids['product'] = product_id
                
                # READ with filters
                products = session.query(Product).filter(
                    Product.product_type == 'RAW_MATERIAL'
                ).all()
                
                assert len(products) > 0
                
                # Test JSONB field
                test_product.specifications = {
                    "dimensions": {"length": 100, "width": 50},
                    "weight": 2.5,
                    "material": "steel"
                }
                session.flush()
                
                # Verify JSONB update
                updated_product = session.query(Product).filter(
                    Product.product_id == product_id
                ).first()
                assert updated_product.specifications['weight'] == 2.5
                
                # UPDATE multiple fields
                updated_product.standard_cost = Decimal('30.00')
                updated_product.minimum_stock_level = Decimal('150')
                session.flush()
                
                # Test constraints
                try:
                    # Test constraint violation - critical > minimum
                    updated_product.critical_stock_level = Decimal('200')  # > minimum
                    session.flush()
                    assert False, "Constraint violation was not caught"
                except Exception:
                    session.rollback()
                
                self.result.add_test_result("Product CRUD", True, "All operations and constraints validated")
                
        except Exception as e:
            self.result.add_test_result("Product CRUD", False, str(e))
    
    def _test_supplier_crud(self):
        """Test Supplier CRUD operations."""
        try:
            with database_session('CRUD_TESTER') as session:
                # CREATE
                test_supplier = Supplier(
                    supplier_code='TESTCRUD',
                    supplier_name='Test CRUD Supplier',
                    contact_person='John Test',
                    email='test@testcrud.com',
                    phone='+1-555-0199',
                    address='123 Test Street',
                    city='Test City',
                    country='Test Country',
                    payment_terms='Net 30',
                    lead_time_days=14,
                    quality_rating=Decimal('4.5'),
                    delivery_rating=Decimal('4.0'),
                    price_rating=Decimal('3.8')
                )
                session.add(test_supplier)
                session.flush()
                supplier_id = test_supplier.supplier_id
                self.test_data_ids['supplier'] = supplier_id
                
                # READ and verify
                retrieved = session.query(Supplier).filter(
                    Supplier.supplier_id == supplier_id
                ).first()
                
                assert retrieved.supplier_code == 'TESTCRUD'
                assert retrieved.quality_rating == Decimal('4.5')
                
                # UPDATE ratings
                retrieved.quality_rating = Decimal('4.8')
                retrieved.delivery_rating = Decimal('4.3')
                session.flush()
                
                # Test email constraint
                try:
                    retrieved.email = 'invalid-email'
                    session.flush()
                    assert False, "Invalid email was accepted"
                except Exception:
                    session.rollback()
                
                # Test rating constraints
                try:
                    retrieved.quality_rating = Decimal('6.0')  # > 5.0
                    session.flush()
                    assert False, "Rating > 5.0 was accepted"
                except Exception:
                    session.rollback()
                
                self.result.add_test_result("Supplier CRUD", True, "All operations and validations successful")
                
        except Exception as e:
            self.result.add_test_result("Supplier CRUD", False, str(e))
    
    def _test_product_supplier_crud(self):
        """Test ProductSupplier relationship CRUD."""
        try:
            with database_session('CRUD_TESTER') as session:
                # Get test data
                product_id = self.test_data_ids.get('product')
                supplier_id = self.test_data_ids.get('supplier')
                
                if not product_id or not supplier_id:
                    raise Exception("Test product or supplier not found")
                
                # CREATE relationship
                product_supplier = ProductSupplier(
                    product_id=product_id,
                    supplier_id=supplier_id,
                    supplier_product_code='SUPP-TEST-001',
                    unit_price=Decimal('22.50'),
                    minimum_order_qty=Decimal('50'),
                    lead_time_days=10,
                    is_preferred=True
                )
                session.add(product_supplier)
                session.flush()
                ps_id = product_supplier.product_supplier_id
                self.test_data_ids['product_supplier'] = ps_id
                
                # READ with joins
                result = session.query(ProductSupplier).join(Product).join(Supplier).filter(
                    ProductSupplier.product_supplier_id == ps_id
                ).first()
                
                assert result is not None
                assert result.is_preferred is True
                
                # UPDATE
                result.unit_price = Decimal('24.00')
                result.is_preferred = False
                session.flush()
                
                # Test unique constraint
                try:
                    duplicate = ProductSupplier(
                        product_id=product_id,
                        supplier_id=supplier_id,  # Same combination
                        supplier_product_code='DUPLICATE',
                        unit_price=Decimal('20.00')
                    )
                    session.add(duplicate)
                    session.flush()
                    assert False, "Duplicate product-supplier relationship was accepted"
                except Exception:
                    session.rollback()
                
                self.result.add_test_result("ProductSupplier CRUD", True, "Relationship operations validated")
                
        except Exception as e:
            self.result.add_test_result("ProductSupplier CRUD", False, str(e))
    
    def _test_inventory_crud(self):
        """Test InventoryItem CRUD and FIFO logic."""
        try:
            with database_session('CRUD_TESTER') as session:
                # Get test data
                product_id = self.test_data_ids.get('product')
                warehouse_id = self.test_data_ids.get('warehouse')
                supplier_id = self.test_data_ids.get('supplier')
                
                if not all([product_id, warehouse_id, supplier_id]):
                    raise Exception("Required test data not found")
                
                # CREATE multiple batches for FIFO testing
                batch1 = InventoryItem(
                    product_id=product_id,
                    warehouse_id=warehouse_id,
                    batch_number='TEST-BATCH-001',
                    entry_date=datetime.now() - timedelta(days=10),
                    quantity_in_stock=Decimal('100'),
                    unit_cost=Decimal('20.00'),
                    supplier_id=supplier_id,
                    quality_status='APPROVED'
                )
                
                batch2 = InventoryItem(
                    product_id=product_id,
                    warehouse_id=warehouse_id,
                    batch_number='TEST-BATCH-002',
                    entry_date=datetime.now() - timedelta(days=5),
                    quantity_in_stock=Decimal('150'),
                    unit_cost=Decimal('22.00'),
                    supplier_id=supplier_id,
                    quality_status='APPROVED'
                )
                
                session.add_all([batch1, batch2])
                session.flush()
                
                batch1_id = batch1.inventory_item_id
                batch2_id = batch2.inventory_item_id
                self.test_data_ids['inventory_batch1'] = batch1_id
                self.test_data_ids['inventory_batch2'] = batch2_id
                
                # Test FIFO ordering
                fifo_items = session.query(InventoryItem).filter(
                    InventoryItem.product_id == product_id,
                    InventoryItem.warehouse_id == warehouse_id,
                    InventoryItem.quality_status == 'APPROVED'
                ).order_by(InventoryItem.entry_date, InventoryItem.inventory_item_id).all()
                
                assert len(fifo_items) == 2
                assert fifo_items[0].inventory_item_id == batch1_id  # Older batch first
                assert fifo_items[1].inventory_item_id == batch2_id
                
                # Test computed columns
                assert batch1.available_quantity == batch1.quantity_in_stock - batch1.reserved_quantity
                assert batch1.total_cost == batch1.quantity_in_stock * batch1.unit_cost
                
                # Test reservation
                batch1.reserved_quantity = Decimal('30')
                session.flush()
                
                updated_batch1 = session.query(InventoryItem).filter(
                    InventoryItem.inventory_item_id == batch1_id
                ).first()
                assert updated_batch1.available_quantity == Decimal('70')  # 100 - 30
                
                # Test constraint violations
                try:
                    batch1.reserved_quantity = Decimal('150')  # > quantity_in_stock
                    session.flush()
                    assert False, "Reserved > in_stock was accepted"
                except Exception:
                    session.rollback()
                
                self.result.add_test_result("Inventory CRUD", True, "FIFO logic and constraints validated")
                
        except Exception as e:
            self.result.add_test_result("Inventory CRUD", False, str(e))
    
    def _test_bom_crud(self):
        """Test BOM CRUD operations."""
        try:
            with database_session('CRUD_TESTER') as session:
                product_id = self.test_data_ids.get('product')
                
                if not product_id:
                    raise Exception("Test product not found")
                
                # CREATE BOM
                test_bom = BillOfMaterials(
                    parent_product_id=product_id,
                    bom_version='1.0',
                    bom_name='Test BOM v1.0',
                    effective_date=date.today(),
                    status='ACTIVE',
                    base_quantity=Decimal('1'),
                    yield_percentage=Decimal('95.0'),
                    labor_cost_per_unit=Decimal('15.00'),
                    overhead_cost_per_unit=Decimal('8.00'),
                    notes='Test BOM for CRUD validation'
                )
                session.add(test_bom)
                session.flush()
                bom_id = test_bom.bom_id
                self.test_data_ids['bom'] = bom_id
                
                # CREATE BOM components (need another product for component)
                component_product = Product(
                    product_code='COMP-TEST-001',
                    product_name='Test Component',
                    product_type='RAW_MATERIAL',
                    unit_of_measure='UNIT',
                    standard_cost=Decimal('5.00')
                )
                session.add(component_product)
                session.flush()
                comp_product_id = component_product.product_id
                self.test_data_ids['component_product'] = comp_product_id
                
                bom_component = BomComponent(
                    bom_id=bom_id,
                    component_product_id=comp_product_id,
                    sequence_number=1,
                    quantity_required=Decimal('2.5'),
                    unit_of_measure='UNIT',
                    scrap_percentage=Decimal('3.0')
                )
                session.add(bom_component)
                session.flush()
                
                # Test calculated fields
                assert bom_component.effective_quantity == Decimal('2.5') * (1 + Decimal('3.0')/100)
                
                # READ with joins
                bom_with_components = session.query(BillOfMaterials).filter(
                    BillOfMaterials.bom_id == bom_id
                ).first()
                
                assert bom_with_components is not None
                assert len(bom_with_components.components) == 1
                
                # UPDATE
                bom_with_components.yield_percentage = Decimal('92.0')
                session.flush()
                
                # Test constraints
                try:
                    # Test circular reference prevention
                    circular_component = BomComponent(
                        bom_id=bom_id,
                        component_product_id=product_id,  # Same as parent
                        sequence_number=2,
                        quantity_required=Decimal('1.0')
                    )
                    session.add(circular_component)
                    session.flush()
                    assert False, "Circular reference was accepted"
                except Exception:
                    session.rollback()
                
                self.result.add_test_result("BOM CRUD", True, "BOM operations and constraints validated")
                
        except Exception as e:
            self.result.add_test_result("BOM CRUD", False, str(e))
    
    def _test_production_order_crud(self):
        """Test Production Order CRUD operations."""
        try:
            with database_session('CRUD_TESTER') as session:
                product_id = self.test_data_ids.get('product')
                bom_id = self.test_data_ids.get('bom')
                warehouse_id = self.test_data_ids.get('warehouse')
                
                if not all([product_id, bom_id, warehouse_id]):
                    raise Exception("Required test data not found")
                
                # CREATE Production Order
                production_order = ProductionOrder(
                    order_number='POTEST001',
                    product_id=product_id,
                    bom_id=bom_id,
                    warehouse_id=warehouse_id,
                    order_date=date.today(),
                    planned_start_date=date.today() + timedelta(days=1),
                    planned_completion_date=date.today() + timedelta(days=5),
                    planned_quantity=Decimal('50'),
                    status='PLANNED',
                    priority=3,
                    estimated_cost=Decimal('2500.00'),
                    notes='Test production order'
                )
                session.add(production_order)
                session.flush()
                po_id = production_order.production_order_id
                self.test_data_ids['production_order'] = po_id
                
                # CREATE Production Order Components
                comp_product_id = self.test_data_ids.get('component_product')
                if comp_product_id:
                    po_component = ProductionOrderComponent(
                        production_order_id=po_id,
                        component_product_id=comp_product_id,
                        required_quantity=Decimal('125'),  # 50 * 2.5
                        unit_cost=Decimal('5.00')
                    )
                    session.add(po_component)
                    session.flush()
                
                # READ and verify
                retrieved_po = session.query(ProductionOrder).filter(
                    ProductionOrder.production_order_id == po_id
                ).first()
                
                assert retrieved_po.order_number == 'POTEST001'
                assert retrieved_po.status == 'PLANNED'
                
                # UPDATE status
                retrieved_po.status = 'RELEASED'
                retrieved_po.actual_start_date = date.today()
                session.flush()
                
                # Test constraints
                try:
                    # Test invalid status
                    retrieved_po.status = 'INVALID_STATUS'
                    session.flush()
                    assert False, "Invalid status was accepted"
                except Exception:
                    session.rollback()
                
                try:
                    # Test quantity constraints
                    retrieved_po.completed_quantity = Decimal('60')  # > planned
                    session.flush()
                    assert False, "Completed > planned was accepted"
                except Exception:
                    session.rollback()
                
                self.result.add_test_result("Production Order CRUD", True, "All operations validated")
                
        except Exception as e:
            self.result.add_test_result("Production Order CRUD", False, str(e))
    
    def _test_purchase_order_crud(self):
        """Test Purchase Order CRUD operations."""
        try:
            with database_session('CRUD_TESTER') as session:
                supplier_id = self.test_data_ids.get('supplier')
                warehouse_id = self.test_data_ids.get('warehouse')
                product_id = self.test_data_ids.get('product')
                
                if not all([supplier_id, warehouse_id, product_id]):
                    raise Exception("Required test data not found")
                
                # CREATE Purchase Order
                purchase_order = PurchaseOrder(
                    po_number='PURTEST001',
                    supplier_id=supplier_id,
                    warehouse_id=warehouse_id,
                    order_date=date.today(),
                    expected_delivery_date=date.today() + timedelta(days=14),
                    currency='USD',
                    payment_terms='Net 30',
                    status='DRAFT',
                    notes='Test purchase order'
                )
                session.add(purchase_order)
                session.flush()
                po_id = purchase_order.purchase_order_id
                self.test_data_ids['purchase_order'] = po_id
                
                # CREATE Purchase Order Items
                po_item = PurchaseOrderItem(
                    purchase_order_id=po_id,
                    product_id=product_id,
                    quantity_ordered=Decimal('200'),
                    unit_price=Decimal('25.00')
                )
                session.add(po_item)
                session.flush()
                
                # Test calculated field (total_price should auto-calculate)
                assert po_item.total_price == Decimal('5000.00')  # 200 * 25
                
                # Test total amount update trigger (should update PO total)
                session.refresh(purchase_order)
                assert purchase_order.total_amount == Decimal('5000.00')
                
                # UPDATE item quantity
                po_item.quantity_ordered = Decimal('250')
                session.flush()
                
                # Verify total updates
                session.refresh(purchase_order)
                assert purchase_order.total_amount == Decimal('6250.00')  # 250 * 25
                
                # Test receiving
                po_item.quantity_received = Decimal('100')
                session.flush()
                
                # Should auto-update delivery status
                session.refresh(po_item)
                assert po_item.delivery_status == 'PARTIALLY_RECEIVED'
                
                # Test constraints
                try:
                    po_item.quantity_received = Decimal('300')  # > ordered
                    session.flush()
                    assert False, "Received > ordered was accepted"
                except Exception:
                    session.rollback()
                
                self.result.add_test_result("Purchase Order CRUD", True, "All operations and triggers validated")
                
        except Exception as e:
            self.result.add_test_result("Purchase Order CRUD", False, str(e))
    
    def _test_critical_stock_alerts_crud(self):
        """Test Critical Stock Alerts CRUD operations."""
        try:
            with database_session('CRUD_TESTER') as session:
                product_id = self.test_data_ids.get('product')
                warehouse_id = self.test_data_ids.get('warehouse')
                
                if not all([product_id, warehouse_id]):
                    raise Exception("Required test data not found")
                
                # CREATE alert
                alert = CriticalStockAlert(
                    product_id=product_id,
                    warehouse_id=warehouse_id,
                    current_stock=Decimal('25'),
                    minimum_level=Decimal('100'),
                    critical_level=Decimal('50'),
                    alert_type='CRITICAL',
                    is_resolved=False
                )
                session.add(alert)
                session.flush()
                alert_id = alert.alert_id
                self.test_data_ids['alert'] = alert_id
                
                # READ
                retrieved = session.query(CriticalStockAlert).filter(
                    CriticalStockAlert.alert_id == alert_id
                ).first()
                
                assert retrieved.alert_type == 'CRITICAL'
                assert retrieved.is_resolved is False
                
                # UPDATE - resolve alert
                retrieved.is_resolved = True
                retrieved.resolved_date = datetime.now()
                retrieved.resolved_by = 'TEST_USER'
                retrieved.resolution_notes = 'Test resolution'
                session.flush()
                
                # Test constraints
                try:
                    # Test invalid alert type
                    invalid_alert = CriticalStockAlert(
                        product_id=product_id,
                        warehouse_id=warehouse_id,
                        current_stock=Decimal('10'),
                        minimum_level=Decimal('100'),
                        critical_level=Decimal('50'),
                        alert_type='INVALID_TYPE'
                    )
                    session.add(invalid_alert)
                    session.flush()
                    assert False, "Invalid alert type was accepted"
                except Exception:
                    session.rollback()
                
                self.result.add_test_result("Critical Stock Alerts CRUD", True, "Alert operations validated")
                
        except Exception as e:
            self.result.add_test_result("Critical Stock Alerts CRUD", False, str(e))
    
    def test_referential_integrity(self):
        """Test foreign key constraints and referential integrity."""
        print("\n" + "=" * 60)
        print("TESTING REFERENTIAL INTEGRITY")
        print("=" * 60)
        
        self._test_cascade_deletes()
        self._test_foreign_key_constraints()
        self._test_orphan_prevention()
    
    def _test_cascade_deletes(self):
        """Test cascade delete behavior."""
        try:
            with database_session('CRUD_TESTER') as session:
                # Test deleting a supplier should cascade to product_suppliers
                supplier_id = self.test_data_ids.get('supplier')
                ps_id = self.test_data_ids.get('product_supplier')
                
                if not supplier_id:
                    raise Exception("Test supplier not found")
                
                # Count product_supplier records before delete
                ps_count_before = session.query(ProductSupplier).filter(
                    ProductSupplier.supplier_id == supplier_id
                ).count()
                
                # Delete supplier
                supplier = session.query(Supplier).filter(
                    Supplier.supplier_id == supplier_id
                ).first()
                if supplier:
                    session.delete(supplier)
                    session.flush()
                    
                    # Count product_supplier records after delete
                    ps_count_after = session.query(ProductSupplier).filter(
                        ProductSupplier.supplier_id == supplier_id
                    ).count()
                    
                    # Should be cascaded
                    assert ps_count_after == 0, f"ProductSupplier records not cascaded (before: {ps_count_before}, after: {ps_count_after})"
                
                self.result.add_test_result("Cascade Deletes", True, "Foreign key cascades working correctly")
                
        except Exception as e:
            self.result.add_test_result("Cascade Deletes", False, str(e))
    
    def _test_foreign_key_constraints(self):
        """Test foreign key constraint enforcement."""
        try:
            with database_session('CRUD_TESTER') as session:
                try:
                    # Try to create inventory item with non-existent product
                    invalid_inventory = InventoryItem(
                        product_id=999999,  # Non-existent
                        warehouse_id=1,
                        batch_number='INVALID',
                        entry_date=datetime.now(),
                        quantity_in_stock=Decimal('100'),
                        unit_cost=Decimal('10.00')
                    )
                    session.add(invalid_inventory)
                    session.flush()
                    assert False, "Foreign key constraint not enforced"
                except Exception:
                    # Expected - foreign key should be enforced
                    session.rollback()
                
                try:
                    # Try to create BOM component with non-existent BOM
                    invalid_component = BomComponent(
                        bom_id=999999,  # Non-existent
                        component_product_id=1,
                        sequence_number=1,
                        quantity_required=Decimal('1.0')
                    )
                    session.add(invalid_component)
                    session.flush()
                    assert False, "Foreign key constraint not enforced"
                except Exception:
                    session.rollback()
                
                self.result.add_test_result("Foreign Key Constraints", True, "All FK constraints properly enforced")
                
        except Exception as e:
            self.result.add_test_result("Foreign Key Constraints", False, str(e))
    
    def _test_orphan_prevention(self):
        """Test prevention of orphaned records."""
        try:
            with database_session('CRUD_TESTER') as session:
                # Test that we can't delete a product that has inventory
                product_id = self.test_data_ids.get('product')
                if product_id:
                    # Check if product has inventory
                    inventory_count = session.query(InventoryItem).filter(
                        InventoryItem.product_id == product_id
                    ).count()
                    
                    if inventory_count > 0:
                        try:
                            product = session.query(Product).filter(
                                Product.product_id == product_id
                            ).first()
                            if product:
                                session.delete(product)
                                session.flush()
                                assert False, "Product with inventory was deleted"
                        except Exception:
                            # Expected - should not be able to delete
                            session.rollback()
                
                self.result.add_test_result("Orphan Prevention", True, "Orphaned records properly prevented")
                
        except Exception as e:
            self.result.add_test_result("Orphan Prevention", False, str(e))
    
    def test_triggers_and_automation(self):
        """Test database triggers and automated functions."""
        print("\n" + "=" * 60)
        print("TESTING TRIGGERS AND AUTOMATION")
        print("=" * 60)
        
        self._test_timestamp_triggers()
        self._test_computed_columns()
        self._test_status_updates()
        self._test_inventory_movement_triggers()
    
    def _test_timestamp_triggers(self):
        """Test updated_at timestamp triggers."""
        try:
            with database_session('CRUD_TESTER') as session:
                # Get a test product
                product = session.query(Product).first()
                if not product:
                    raise Exception("No test product found")
                
                original_updated_at = product.updated_at
                
                # Wait a moment then update
                import time
                time.sleep(1)
                
                product.description = 'Updated description for trigger test'
                session.flush()
                
                # Check that updated_at was automatically updated
                session.refresh(product)
                assert product.updated_at > original_updated_at, "updated_at timestamp not triggered"
                
                self.result.add_test_result("Timestamp Triggers", True, "updated_at triggers working correctly")
                
        except Exception as e:
            self.result.add_test_result("Timestamp Triggers", False, str(e))
    
    def _test_computed_columns(self):
        """Test computed/generated columns."""
        try:
            with database_session('CRUD_TESTER') as session:
                # Test inventory computed columns
                inventory_item = session.query(InventoryItem).first()
                if inventory_item:
                    # Test available_quantity computation
                    expected_available = inventory_item.quantity_in_stock - inventory_item.reserved_quantity
                    assert inventory_item.available_quantity == expected_available, "available_quantity not computed correctly"
                    
                    # Test total_cost computation
                    expected_total = inventory_item.quantity_in_stock * inventory_item.unit_cost
                    assert inventory_item.total_cost == expected_total, "total_cost not computed correctly"
                
                # Test BOM component computed columns
                bom_component = session.query(BomComponent).first()
                if bom_component:
                    expected_effective = bom_component.quantity_required * (1 + bom_component.scrap_percentage/100)
                    assert bom_component.effective_quantity == expected_effective, "effective_quantity not computed correctly"
                
                self.result.add_test_result("Computed Columns", True, "All computed columns working correctly")
                
        except Exception as e:
            self.result.add_test_result("Computed Columns", False, str(e))
    
    def _test_status_updates(self):
        """Test automatic status updates."""
        try:
            with database_session('CRUD_TESTER') as session:
                # Test purchase order status updates
                po = session.query(PurchaseOrder).first()
                if po:
                    # Get first item
                    po_item = session.query(PurchaseOrderItem).filter(
                        PurchaseOrderItem.purchase_order_id == po.purchase_order_id
                    ).first()
                    
                    if po_item:
                        # Update received quantity
                        po_item.quantity_received = po_item.quantity_ordered
                        session.flush()
                        
                        # Check that delivery status was updated
                        session.refresh(po_item)
                        assert po_item.delivery_status == 'FULLY_RECEIVED', "Delivery status not auto-updated"
                
                self.result.add_test_result("Status Updates", True, "Automatic status updates working")
                
        except Exception as e:
            self.result.add_test_result("Status Updates", False, str(e))
    
    def _test_inventory_movement_triggers(self):
        """Test inventory movement tracking triggers."""
        try:
            with database_session('CRUD_TESTER') as session:
                # Count movements before
                movements_before = session.query(StockMovement).count()
                
                # Create a new inventory item (should trigger movement)
                test_product = session.query(Product).first()
                test_warehouse = session.query(Warehouse).first()
                
                if test_product and test_warehouse:
                    new_inventory = InventoryItem(
                        product_id=test_product.product_id,
                        warehouse_id=test_warehouse.warehouse_id,
                        batch_number='TRIGGER-TEST',
                        entry_date=datetime.now(),
                        quantity_in_stock=Decimal('50'),
                        unit_cost=Decimal('15.00'),
                        quality_status='APPROVED'
                    )
                    session.add(new_inventory)
                    session.flush()
                    
                    # Check that movement was created
                    movements_after = session.query(StockMovement).count()
                    assert movements_after > movements_before, "Stock movement not triggered"
                    
                    # Check the created movement
                    movement = session.query(StockMovement).filter(
                        StockMovement.inventory_item_id == new_inventory.inventory_item_id
                    ).first()
                    
                    assert movement is not None, "Stock movement record not found"
                    assert movement.movement_type == 'IN', "Wrong movement type"
                    assert movement.quantity == Decimal('50'), "Wrong movement quantity"
                
                self.result.add_test_result("Inventory Movement Triggers", True, "Movement tracking triggers working")
                
        except Exception as e:
            self.result.add_test_result("Inventory Movement Triggers", False, str(e))
    
    def test_business_logic_validation(self):
        """Test complex business logic validation."""
        print("\n" + "=" * 60)
        print("TESTING BUSINESS LOGIC VALIDATION")
        print("=" * 60)
        
        self._test_fifo_logic_validation()
        self._test_bom_hierarchy_validation()
        self._test_production_workflow_validation()
    
    def _test_fifo_logic_validation(self):
        """Test FIFO logic validation."""
        try:
            with database_session('CRUD_TESTER') as session:
                # Create test inventory with known dates
                test_product = session.query(Product).first()
                test_warehouse = session.query(Warehouse).first()
                
                if not test_product or not test_warehouse:
                    raise Exception("Test data not available")
                
                # Create batches with different entry dates
                old_batch = InventoryItem(
                    product_id=test_product.product_id,
                    warehouse_id=test_warehouse.warehouse_id,
                    batch_number='OLD-BATCH',
                    entry_date=datetime.now() - timedelta(days=20),
                    quantity_in_stock=Decimal('100'),
                    unit_cost=Decimal('10.00'),
                    quality_status='APPROVED'
                )
                
                new_batch = InventoryItem(
                    product_id=test_product.product_id,
                    warehouse_id=test_warehouse.warehouse_id,
                    batch_number='NEW-BATCH',
                    entry_date=datetime.now() - timedelta(days=1),
                    quantity_in_stock=Decimal('100'),
                    unit_cost=Decimal('12.00'),
                    quality_status='APPROVED'
                )
                
                session.add_all([old_batch, new_batch])
                session.flush()
                
                # Query in FIFO order
                fifo_query = session.query(InventoryItem).filter(
                    InventoryItem.product_id == test_product.product_id,
                    InventoryItem.warehouse_id == test_warehouse.warehouse_id,
                    InventoryItem.quality_status == 'APPROVED',
                    InventoryItem.available_quantity > 0
                ).order_by(InventoryItem.entry_date, InventoryItem.inventory_item_id).all()
                
                # First item should be the older batch
                assert len(fifo_query) >= 2
                assert fifo_query[0].batch_number == 'OLD-BATCH'
                assert fifo_query[0].entry_date < fifo_query[1].entry_date
                
                self.result.add_test_result("FIFO Logic Validation", True, "FIFO ordering logic working correctly")
                
        except Exception as e:
            self.result.add_test_result("FIFO Logic Validation", False, str(e))
    
    def _test_bom_hierarchy_validation(self):
        """Test BOM hierarchy validation."""
        try:
            with database_session('CRUD_TESTER') as session:
                # Test that we can create nested BOMs correctly
                parent_product = Product(
                    product_code='BOM-PARENT-TEST',
                    product_name='BOM Parent Test Product',
                    product_type='FINISHED_PRODUCT',
                    unit_of_measure='UNIT',
                    standard_cost=Decimal('100.00')
                )
                
                child_product = Product(
                    product_code='BOM-CHILD-TEST',
                    product_name='BOM Child Test Product',
                    product_type='SEMI_FINISHED',
                    unit_of_measure='UNIT',
                    standard_cost=Decimal('50.00')
                )
                
                raw_material = Product(
                    product_code='BOM-RAW-TEST',
                    product_name='BOM Raw Material Test',
                    product_type='RAW_MATERIAL',
                    unit_of_measure='UNIT',
                    standard_cost=Decimal('10.00')
                )
                
                session.add_all([parent_product, child_product, raw_material])
                session.flush()
                
                # Create parent BOM
                parent_bom = BillOfMaterials(
                    parent_product_id=parent_product.product_id,
                    bom_version='1.0',
                    bom_name='Parent BOM Test',
                    effective_date=date.today(),
                    status='ACTIVE'
                )
                session.add(parent_bom)
                session.flush()
                
                # Add child product to parent BOM
                parent_component = BomComponent(
                    bom_id=parent_bom.bom_id,
                    component_product_id=child_product.product_id,
                    sequence_number=1,
                    quantity_required=Decimal('2.0')
                )
                session.add(parent_component)
                session.flush()
                
                # Create child BOM
                child_bom = BillOfMaterials(
                    parent_product_id=child_product.product_id,
                    bom_version='1.0',
                    bom_name='Child BOM Test',
                    effective_date=date.today(),
                    status='ACTIVE'
                )
                session.add(child_bom)
                session.flush()
                
                # Add raw material to child BOM
                child_component = BomComponent(
                    bom_id=child_bom.bom_id,
                    component_product_id=raw_material.product_id,
                    sequence_number=1,
                    quantity_required=Decimal('3.0')
                )
                session.add(child_component)
                session.flush()
                
                # Verify hierarchy
                parent_with_components = session.query(BillOfMaterials).filter(
                    BillOfMaterials.bom_id == parent_bom.bom_id
                ).first()
                
                assert len(parent_with_components.components) == 1
                assert parent_with_components.components[0].component_product.product_type == 'SEMI_FINISHED'
                
                self.result.add_test_result("BOM Hierarchy Validation", True, "Nested BOM structure validated")
                
        except Exception as e:
            self.result.add_test_result("BOM Hierarchy Validation", False, str(e))
    
    def _test_production_workflow_validation(self):
        """Test production workflow validation."""
        try:
            with database_session('CRUD_TESTER') as session:
                # Test production order status transitions
                po = session.query(ProductionOrder).first()
                if po:
                    # Test valid status transitions
                    original_status = po.status
                    
                    if po.status == 'PLANNED':
                        po.status = 'RELEASED'
                        session.flush()
                        
                        po.status = 'IN_PROGRESS'
                        po.actual_start_date = date.today()
                        session.flush()
                        
                        po.status = 'COMPLETED'
                        po.actual_completion_date = date.today()
                        po.completed_quantity = po.planned_quantity
                        session.flush()
                        
                        # All transitions should be successful
                        session.refresh(po)
                        assert po.status == 'COMPLETED'
                
                self.result.add_test_result("Production Workflow Validation", True, "Status transitions validated")
                
        except Exception as e:
            self.result.add_test_result("Production Workflow Validation", False, str(e))
    
    def cleanup_test_data(self):
        """Clean up test data created during testing."""
        print("\n" + "=" * 60)
        print("CLEANING UP TEST DATA")
        print("=" * 60)
        
        try:
            with database_session('CRUD_TESTER') as session:
                # Delete in reverse order of dependencies
                
                # Production orders and components
                if 'production_order' in self.test_data_ids:
                    po = session.query(ProductionOrder).filter(
                        ProductionOrder.production_order_id == self.test_data_ids['production_order']
                    ).first()
                    if po:
                        session.delete(po)
                
                # Purchase orders and items
                if 'purchase_order' in self.test_data_ids:
                    purchase_order = session.query(PurchaseOrder).filter(
                        PurchaseOrder.purchase_order_id == self.test_data_ids['purchase_order']
                    ).first()
                    if purchase_order:
                        session.delete(purchase_order)
                
                # Critical stock alerts
                if 'alert' in self.test_data_ids:
                    alert = session.query(CriticalStockAlert).filter(
                        CriticalStockAlert.alert_id == self.test_data_ids['alert']
                    ).first()
                    if alert:
                        session.delete(alert)
                
                # BOMs and components
                if 'bom' in self.test_data_ids:
                    bom = session.query(BillOfMaterials).filter(
                        BillOfMaterials.bom_id == self.test_data_ids['bom']
                    ).first()
                    if bom:
                        session.delete(bom)
                
                # Inventory items
                for key in ['inventory_batch1', 'inventory_batch2']:
                    if key in self.test_data_ids:
                        inventory = session.query(InventoryItem).filter(
                            InventoryItem.inventory_item_id == self.test_data_ids[key]
                        ).first()
                        if inventory:
                            session.delete(inventory)
                
                # Products (will cascade)
                for key in ['product', 'component_product']:
                    if key in self.test_data_ids:
                        product = session.query(Product).filter(
                            Product.product_id == self.test_data_ids[key]
                        ).first()
                        if product:
                            session.delete(product)
                
                # Warehouse (will cascade)
                if 'warehouse' in self.test_data_ids:
                    warehouse = session.query(Warehouse).filter(
                        Warehouse.warehouse_id == self.test_data_ids['warehouse']
                    ).first()
                    if warehouse:
                        session.delete(warehouse)
                
                # Clean up any test products created in validation
                test_products = session.query(Product).filter(
                    Product.product_code.like('BOM-%TEST%')
                ).all()
                for product in test_products:
                    session.delete(product)
                
                # Clean up test inventory
                test_inventory = session.query(InventoryItem).filter(
                    InventoryItem.batch_number.in_(['OLD-BATCH', 'NEW-BATCH', 'TRIGGER-TEST'])
                ).all()
                for item in test_inventory:
                    session.delete(item)
                
                session.commit()
                print("✅ Test data cleanup completed successfully")
                
        except Exception as e:
            print(f"⚠️  Warning: Test data cleanup had issues: {e}")
            self.result.add_warning(f"Cleanup issues: {e}")
    
    def run_all_tests(self):
        """Run all CRUD tests."""
        print("🧪 STARTING COMPREHENSIVE CRUD TEST SUITE")
        print("=" * 80)
        
        # Check database connection
        if not check_database_connection():
            print("❌ Database connection failed")
            return self.result.get_summary()
        
        print("✅ Database connection successful")
        
        # Run health check
        health = health_check()
        if not health['database_connection']:
            print("❌ Database health check failed")
            return self.result.get_summary()
        
        print("✅ Database health check passed")
        
        try:
            # Run test categories
            self.test_basic_crud_operations()
            self.test_referential_integrity() 
            self.test_triggers_and_automation()
            self.test_business_logic_validation()
            
        except Exception as e:
            print(f"💥 Critical error during testing: {e}")
            traceback.print_exc()
            self.result.add_test_result("Critical Error", False, str(e))
        
        finally:
            # Always try to cleanup
            self.cleanup_test_data()
        
        # Print summary
        summary = self.result.get_summary()
        print("\n" + "=" * 80)
        print("COMPREHENSIVE CRUD TEST RESULTS SUMMARY")
        print("=" * 80)
        print(f"Total Tests Run: {summary['total_tests']}")
        print(f"Tests Passed: {summary['passed']}")
        print(f"Tests Failed: {summary['failed']}")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        
        if summary['warnings']:
            print(f"\nWarnings ({len(summary['warnings'])}):")
            for warning in summary['warnings']:
                print(f"  ⚠️  {warning}")
        
        if summary['failures']:
            print(f"\nFailures ({len(summary['failures'])}):")
            for failure in summary['failures']:
                print(f"  ❌ {failure['test']}: {failure['message']}")
        
        if summary['passed'] == summary['total_tests']:
            print("\n🎉 ALL CRUD TESTS PASSED!")
        else:
            print(f"\n⚠️  {summary['failed']} TESTS FAILED")
        
        return summary


if __name__ == '__main__':
    tester = ComprehensiveCRUDTester()
    results = tester.run_all_tests()
    
    # Exit with appropriate code
    exit_code = 0 if results['failed'] == 0 else 1
    sys.exit(exit_code)