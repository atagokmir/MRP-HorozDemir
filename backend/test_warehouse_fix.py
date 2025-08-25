#!/usr/bin/env python3
"""
Test script to validate the cross-warehouse stock analysis bug fix.

This script tests the critical bug fix for warehouse sourcing logic in MRP analysis.
The bug was: stock analysis only looked in target warehouse, not appropriate source warehouses.

Expected behavior after fix:
- Raw materials sourced from RAW_MATERIALS warehouse
- Semi-finished products sourced from SEMI_FINISHED warehouse  
- Finished products sourced from FINISHED_PRODUCTS warehouse
- Packaging materials sourced from PACKAGING warehouse
"""

import sys
import os
from decimal import Decimal
from datetime import date, datetime

# Add the backend path to sys.path so we can import modules
backend_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_path)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.base import Base
from models.master_data import Product, Warehouse
from models.inventory import InventoryItem
from models.bom import BillOfMaterials, BomComponent
from app.services.mrp_analysis import MRPAnalysisService

# Database setup
DATABASE_URL = "sqlite:///test_mrp.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def create_test_data(session):
    """Create test data for warehouse sourcing tests."""
    print("Creating test data...")
    
    # First, let's make sure we have active warehouses of each type
    # Check existing warehouses and activate/create as needed
    raw_warehouse = session.query(Warehouse).filter(Warehouse.warehouse_type == "RAW_MATERIALS").first()
    if raw_warehouse:
        raw_warehouse.is_active = True
        raw_warehouse_id = raw_warehouse.warehouse_id
    else:
        raw_warehouse = Warehouse(warehouse_code="RAW-TEST", warehouse_name="Test Raw Materials Warehouse", warehouse_type="RAW_MATERIALS", is_active=True)
        session.add(raw_warehouse)
        session.flush()
        raw_warehouse_id = raw_warehouse.warehouse_id
    
    semi_warehouse = session.query(Warehouse).filter(Warehouse.warehouse_type == "SEMI_FINISHED", Warehouse.is_active == True).first()
    semi_warehouse_id = semi_warehouse.warehouse_id if semi_warehouse else None
    
    finished_warehouse = session.query(Warehouse).filter(Warehouse.warehouse_type == "FINISHED_PRODUCTS", Warehouse.is_active == True).first()
    finished_warehouse_id = finished_warehouse.warehouse_id if finished_warehouse else None
    
    packaging_warehouse = session.query(Warehouse).filter(Warehouse.warehouse_type == "PACKAGING", Warehouse.is_active == True).first()
    packaging_warehouse_id = packaging_warehouse.warehouse_id if packaging_warehouse else None
    
    print(f"Using warehouses - Raw: {raw_warehouse_id}, Semi: {semi_warehouse_id}, Finished: {finished_warehouse_id}, Packaging: {packaging_warehouse_id}")
    
    # Create products
    products = [
        Product(product_id=101, product_code="RM-STEEL", product_name="Steel Bar", product_type="RAW_MATERIAL", unit_of_measure="KG"),
        Product(product_id=102, product_code="RM-BOLT", product_name="Bolt M10", product_type="RAW_MATERIAL", unit_of_measure="PCS"),
        Product(product_id=201, product_code="SF-FRAME", product_name="Steel Frame", product_type="SEMI_FINISHED", unit_of_measure="PCS"),
        Product(product_id=301, product_code="FP-TABLE", product_name="Complete Table", product_type="FINISHED_PRODUCT", unit_of_measure="PCS"),
        Product(product_id=401, product_code="PK-BOX", product_name="Cardboard Box", product_type="PACKAGING", unit_of_measure="PCS"),
    ]
    
    # Add test data
    for product in products:
        session.merge(product)
    
    # Create inventory items in CORRECT warehouses using dynamic warehouse IDs
    inventory_items = [
        # Raw materials in RAW_MATERIALS warehouse (correct)
        InventoryItem(inventory_item_id=1001, product_id=101, warehouse_id=raw_warehouse_id, quantity_in_stock=Decimal("100"), 
                     reserved_quantity=Decimal("0"), unit_cost=Decimal("25.50"), batch_number="RM-STEEL-001",
                     entry_date=datetime(2023, 1, 1), quality_status="APPROVED"),
        InventoryItem(inventory_item_id=1002, product_id=102, warehouse_id=raw_warehouse_id, quantity_in_stock=Decimal("500"), 
                     reserved_quantity=Decimal("0"), unit_cost=Decimal("2.50"), batch_number="RM-BOLT-001",
                     entry_date=datetime(2023, 1, 2), quality_status="APPROVED"),
        
        # Semi-finished in SEMI_FINISHED warehouse (correct)
        InventoryItem(inventory_item_id=2001, product_id=201, warehouse_id=semi_warehouse_id, quantity_in_stock=Decimal("50"), 
                     reserved_quantity=Decimal("0"), unit_cost=Decimal("75.00"), batch_number="SF-FRAME-001",
                     entry_date=datetime(2023, 1, 3), quality_status="APPROVED"),
        
        # Finished products in FINISHED_PRODUCTS warehouse (correct)
        InventoryItem(inventory_item_id=3001, product_id=301, warehouse_id=finished_warehouse_id, quantity_in_stock=Decimal("20"), 
                     reserved_quantity=Decimal("0"), unit_cost=Decimal("150.00"), batch_number="FP-TABLE-001",
                     entry_date=datetime(2023, 1, 4), quality_status="APPROVED"),
        
        # Packaging in PACKAGING warehouse (correct)
        InventoryItem(inventory_item_id=4001, product_id=401, warehouse_id=packaging_warehouse_id, quantity_in_stock=Decimal("200"), 
                     reserved_quantity=Decimal("0"), unit_cost=Decimal("5.00"), batch_number="PK-BOX-001",
                     entry_date=datetime(2023, 1, 5), quality_status="APPROVED"),
        
        # Test items in WRONG warehouses to validate fix
        # Raw material in finished products warehouse (wrong location - should be ignored)
        InventoryItem(inventory_item_id=1003, product_id=101, warehouse_id=finished_warehouse_id, quantity_in_stock=Decimal("30"), 
                     reserved_quantity=Decimal("0"), unit_cost=Decimal("25.50"), batch_number="RM-STEEL-002",
                     entry_date=datetime(2023, 1, 6), quality_status="APPROVED"),
        
        # Semi-finished in raw materials warehouse (wrong location - should be ignored) 
        InventoryItem(inventory_item_id=2002, product_id=201, warehouse_id=raw_warehouse_id, quantity_in_stock=Decimal("10"), 
                     reserved_quantity=Decimal("0"), unit_cost=Decimal("75.00"), batch_number="SF-FRAME-002",
                     entry_date=datetime(2023, 1, 7), quality_status="APPROVED"),
    ]
    
    for item in inventory_items:
        session.merge(item)
    
    # Create BOM for semi-finished product (Steel Frame)
    bom_sf = BillOfMaterials(
        bom_id=2001,
        bom_name="Steel Frame BOM v1.0",
        parent_product_id=201,  # Steel Frame
        bom_version="1.0",
        base_quantity=Decimal("1"),  # 1 frame
        status="ACTIVE"
    )
    session.merge(bom_sf)
    
    # BOM components for Steel Frame
    bom_components_sf = [
        BomComponent(bom_component_id=20011, bom_id=2001, component_product_id=101, quantity_required=Decimal("5"), unit_of_measure="KG", sequence_number=1),  # 5 KG steel
        BomComponent(bom_component_id=20012, bom_id=2001, component_product_id=102, quantity_required=Decimal("8"), unit_of_measure="PCS", sequence_number=2),  # 8 bolts
    ]
    
    for comp in bom_components_sf:
        session.merge(comp)
    
    # Create BOM for finished product (Complete Table)
    bom_fp = BillOfMaterials(
        bom_id=3001,
        bom_name="Complete Table BOM v1.0",
        parent_product_id=301,  # Complete Table
        bom_version="1.0",
        base_quantity=Decimal("1"),  # 1 table
        status="ACTIVE"
    )
    session.merge(bom_fp)
    
    # BOM components for Complete Table
    bom_components_fp = [
        BomComponent(bom_component_id=30011, bom_id=3001, component_product_id=201, quantity_required=Decimal("2"), unit_of_measure="PCS", sequence_number=1),  # 2 frames
        BomComponent(bom_component_id=30012, bom_id=3001, component_product_id=401, quantity_required=Decimal("1"), unit_of_measure="PCS", sequence_number=2),  # 1 box
    ]
    
    for comp in bom_components_fp:
        session.merge(comp)
    
    session.commit()
    print("Test data created successfully.")


def test_warehouse_sourcing_logic(session):
    """Test the warehouse sourcing logic fix."""
    print("\n" + "="*80)
    print("TESTING WAREHOUSE SOURCING LOGIC FIX")
    print("="*80)
    
    mrp_service = MRPAnalysisService(session)
    
    # Test 1: Raw Material Analysis (should find stock in RAW_MATERIALS warehouse)
    print("\nTest 1: Raw Material Analysis")
    print("-" * 40)
    
    steel_analysis = mrp_service._analyze_component_availability(101, Decimal("10"))  # Steel Bar, need 10 KG
    print(f"Product: {steel_analysis['product_code']} - {steel_analysis['product_name']}")
    print(f"Available quantity: {steel_analysis['available_quantity']}")
    print(f"Expected: Should find 100 KG from RAW_MATERIALS warehouse, ignore 30 KG from wrong warehouse")
    
    if steel_analysis['available_quantity'] == Decimal("100"):
        print("✅ PASS: Correctly found stock in RAW_MATERIALS warehouse")
    else:
        print(f"❌ FAIL: Found {steel_analysis['available_quantity']}, expected 100")
    
    # Test 2: Semi-Finished Product Analysis (should find stock in SEMI_FINISHED warehouse)
    print("\nTest 2: Semi-Finished Product Analysis")
    print("-" * 40)
    
    frame_analysis = mrp_service._analyze_component_availability(201, Decimal("5"))  # Steel Frame, need 5 PCS
    print(f"Product: {frame_analysis['product_code']} - {frame_analysis['product_name']}")
    print(f"Available quantity: {frame_analysis['available_quantity']}")
    print(f"Expected: Should find 50 PCS from SEMI_FINISHED warehouse, ignore 10 PCS from wrong warehouse")
    
    if frame_analysis['available_quantity'] == Decimal("50"):
        print("✅ PASS: Correctly found stock in SEMI_FINISHED warehouse")
    else:
        print(f"❌ FAIL: Found {frame_analysis['available_quantity']}, expected 50")
    
    # Test 3: Finished Product Analysis (should find stock in FINISHED_PRODUCTS warehouse)
    print("\nTest 3: Finished Product Analysis")
    print("-" * 40)
    
    table_analysis = mrp_service._analyze_component_availability(301, Decimal("2"))  # Complete Table, need 2 PCS
    print(f"Product: {table_analysis['product_code']} - {table_analysis['product_name']}")
    print(f"Available quantity: {table_analysis['available_quantity']}")
    
    if table_analysis['available_quantity'] == Decimal("20"):
        print("✅ PASS: Correctly found stock in FINISHED_PRODUCTS warehouse")
    else:
        print(f"❌ FAIL: Found {table_analysis['available_quantity']}, expected 20")
    
    # Test 4: Packaging Material Analysis (should find stock in PACKAGING warehouse)
    print("\nTest 4: Packaging Material Analysis")
    print("-" * 40)
    
    box_analysis = mrp_service._analyze_component_availability(401, Decimal("10"))  # Box, need 10 PCS
    print(f"Product: {box_analysis['product_code']} - {box_analysis['product_name']}")
    print(f"Available quantity: {box_analysis['available_quantity']}")
    
    if box_analysis['available_quantity'] == Decimal("200"):
        print("✅ PASS: Correctly found stock in PACKAGING warehouse")
    else:
        print(f"❌ FAIL: Found {box_analysis['available_quantity']}, expected 200")


def test_production_order_analysis(session):
    """Test production order stock analysis with the fix."""
    print("\n" + "="*80)
    print("TESTING PRODUCTION ORDER STOCK ANALYSIS")
    print("="*80)
    
    mrp_service = MRPAnalysisService(session)
    
    # Test Production Order for Complete Table (uses semi-finished and packaging materials)
    print("\nTest: Complete Table Production Order Analysis")
    print("-" * 50)
    
    try:
        # Get the active finished products warehouse ID
        finished_warehouse = session.query(Warehouse).filter(Warehouse.warehouse_type == "FINISHED_PRODUCTS", Warehouse.is_active == True).first()
        target_warehouse_id = finished_warehouse.warehouse_id if finished_warehouse else 7
        
        analysis = mrp_service.analyze_stock_availability(
            product_id=301,  # Complete Table
            bom_id=3001,     # Complete Table BOM
            planned_quantity=Decimal("5"),  # Want to make 5 tables
            warehouse_id=target_warehouse_id   # Target finished products warehouse
        )
        
        print(f"Product: {analysis.product_code} - {analysis.product_name}")
        print(f"Planned quantity: {analysis.planned_quantity}")
        print(f"Can produce: {analysis.can_produce}")
        print(f"Shortage exists: {analysis.shortage_exists}")
        print(f"Total estimated cost: {analysis.total_estimated_cost}")
        
        print(f"\nComponent requirements:")
        for comp in analysis.component_requirements:
            print(f"  - {comp.product_code}: need {comp.required_quantity}, available {comp.available_quantity}")
            if comp.shortage_quantity > 0:
                print(f"    ❌ Shortage: {comp.shortage_quantity}")
            else:
                print(f"    ✅ Sufficient stock")
        
        print(f"\nSemi-finished shortages: {len(analysis.semi_finished_shortages)}")
        for shortage in analysis.semi_finished_shortages:
            print(f"  - {shortage.product_code}: short {shortage.shortage_quantity}")
        
        print(f"\nRaw material shortages: {len(analysis.raw_material_shortages)}")
        for shortage in analysis.raw_material_shortages:
            print(f"  - {shortage.product_code}: short {shortage.shortage_quantity}")
        
        # Validate results
        expected_frame_needed = Decimal("10")  # 5 tables * 2 frames each
        expected_box_needed = Decimal("5")     # 5 tables * 1 box each
        
        frame_component = next((c for c in analysis.component_requirements if c.product_id == 201), None)
        box_component = next((c for c in analysis.component_requirements if c.product_id == 401), None)
        
        if frame_component and frame_component.required_quantity == expected_frame_needed:
            print(f"\n✅ PASS: Steel Frame requirement calculated correctly: {frame_component.required_quantity}")
        else:
            print(f"\n❌ FAIL: Steel Frame requirement incorrect")
        
        if box_component and box_component.required_quantity == expected_box_needed:
            print(f"✅ PASS: Box requirement calculated correctly: {box_component.required_quantity}")
        else:
            print(f"❌ FAIL: Box requirement incorrect")
        
        # Check if the analysis correctly identifies available stock
        if frame_component and frame_component.available_quantity == Decimal("50"):
            print(f"✅ PASS: Steel Frame availability correctly found from SEMI_FINISHED warehouse: {frame_component.available_quantity}")
        else:
            print(f"❌ FAIL: Steel Frame availability incorrect")
        
        if box_component and box_component.available_quantity == Decimal("200"):
            print(f"✅ PASS: Box availability correctly found from PACKAGING warehouse: {box_component.available_quantity}")
        else:
            print(f"❌ FAIL: Box availability incorrect")
            
        # This should be possible to produce since all components are available
        if analysis.can_produce:
            print(f"\n✅ PASS: Analysis correctly determined production is possible")
        else:
            print(f"\n❌ FAIL: Analysis incorrectly determined production is not possible")
            
    except Exception as e:
        print(f"❌ ERROR: Production analysis failed: {str(e)}")


def test_reservation_logic(session):
    """Test stock reservation with warehouse sourcing fix."""
    print("\n" + "="*80)
    print("TESTING STOCK RESERVATION WITH WAREHOUSE SOURCING")
    print("="*80)
    
    mrp_service = MRPAnalysisService(session)
    
    print("\nTest: Reserve Steel Bar (Raw Material)")
    print("-" * 40)
    
    try:
        # Try to reserve steel bar - should get from RAW_MATERIALS warehouse
        reservations = mrp_service._reserve_component_stock(
            product_id=101,  # Steel Bar
            required_quantity=Decimal("20"),
            warehouse_id=3,  # Target: Finished Products (wrong type)
            production_order_id=999,  # Test order ID
            reserved_by="TEST_SYSTEM"
        )
        
        print(f"Created {len(reservations)} reservations")
        for res in reservations:
            print(f"  - Reserved {res.reserved_quantity} from warehouse {res.warehouse_id}")
            print(f"    Notes: {res.notes}")
            
            # Check if reservation was made from correct warehouse (RAW_MATERIALS = warehouse_id 1)
            if res.warehouse_id == 1:
                print(f"    ✅ PASS: Reserved from correct RAW_MATERIALS warehouse")
            else:
                print(f"    ❌ FAIL: Reserved from wrong warehouse {res.warehouse_id}, expected 1")
                
    except Exception as e:
        print(f"❌ ERROR: Reservation failed: {str(e)}")
    
    print("\nTest: Reserve Steel Frame (Semi-Finished)")
    print("-" * 40)
    
    try:
        # Try to reserve steel frame - should get from SEMI_FINISHED warehouse
        reservations = mrp_service._reserve_component_stock(
            product_id=201,  # Steel Frame
            required_quantity=Decimal("3"),
            warehouse_id=3,  # Target: Finished Products (wrong type)
            production_order_id=998,  # Test order ID
            reserved_by="TEST_SYSTEM"
        )
        
        print(f"Created {len(reservations)} reservations")
        for res in reservations:
            print(f"  - Reserved {res.reserved_quantity} from warehouse {res.warehouse_id}")
            print(f"    Notes: {res.notes}")
            
            # Check if reservation was made from correct warehouse (SEMI_FINISHED = warehouse_id 2)
            if res.warehouse_id == 2:
                print(f"    ✅ PASS: Reserved from correct SEMI_FINISHED warehouse")
            else:
                print(f"    ❌ FAIL: Reserved from wrong warehouse {res.warehouse_id}, expected 2")
                
    except Exception as e:
        print(f"❌ ERROR: Reservation failed: {str(e)}")


def main():
    """Main test function."""
    print("="*80)
    print("WAREHOUSE SOURCING BUG FIX VALIDATION TEST")
    print("="*80)
    print("Testing the critical bug fix for cross-warehouse stock analysis")
    print("Bug: Stock analysis only looked in target warehouse, not appropriate source warehouses")
    print("Fix: Now searches appropriate warehouses based on product type")
    
    session = Session()
    
    try:
        # Create test data
        create_test_data(session)
        
        # Run tests
        test_warehouse_sourcing_logic(session)
        test_production_order_analysis(session)
        test_reservation_logic(session)
        
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        print("All tests completed. Check the output above for PASS/FAIL results.")
        print("The fix should ensure materials are sourced from appropriate warehouses:")
        print("  - Raw materials from RAW_MATERIALS warehouse")
        print("  - Semi-finished from SEMI_FINISHED warehouse")
        print("  - Finished products from FINISHED_PRODUCTS warehouse") 
        print("  - Packaging from PACKAGING warehouse")
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        
    finally:
        session.rollback()  # Don't save test changes
        session.close()


if __name__ == "__main__":
    main()