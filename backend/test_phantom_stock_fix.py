#!/usr/bin/env python3
"""
Test script to verify phantom stock fixes work correctly.

This script tests:
1. Database fixes applied correctly
2. Availability calculations are accurate
3. Production order validation works properly
4. Synchronization function works
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from decimal import Decimal
from datetime import datetime
from sqlalchemy import create_engine, and_, func
from sqlalchemy.orm import sessionmaker
from models.base import Base
from models.inventory import InventoryItem
from models.production import StockReservation
from models.master_data import Product
from app.services.mrp_analysis import MRPAnalysisService

# Database configuration
DATABASE_URL = "sqlite:///test_mrp.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def test_phantom_stock_fix():
    """Test that phantom stock issues have been resolved."""
    session = SessionLocal()
    try:
        print("=== PHANTOM STOCK FIX VERIFICATION ===\n")
        
        # Test 1: Check database state after fixes
        print("1. Checking database state after manual fixes...")
        
        # Check SF-FRAME and PK-BOX current state
        test_products = ['SF-FRAME', 'PK-BOX']
        
        for product_code in test_products:
            print(f"\n--- {product_code} Analysis ---")
            
            # Get product ID
            product = session.query(Product).filter(Product.product_code == product_code).first()
            if not product:
                print(f"ERROR: Product {product_code} not found!")
                continue
                
            # Get inventory items
            inventory_items = session.query(InventoryItem).filter(
                InventoryItem.product_id == product.product_id
            ).all()
            
            total_stock = sum(item.quantity_in_stock for item in inventory_items)
            total_reserved_inventory = sum(item.reserved_quantity for item in inventory_items)
            total_available_inventory = total_stock - total_reserved_inventory
            
            print(f"Inventory Items Total Stock: {total_stock}")
            print(f"Inventory Items Total Reserved: {total_reserved_inventory}")
            print(f"Inventory Items Total Available: {total_available_inventory}")
            
            # Get actual reservations
            actual_reserved = session.query(func.coalesce(func.sum(StockReservation.reserved_quantity), 0)).filter(
                and_(
                    StockReservation.product_id == product.product_id,
                    StockReservation.status == 'ACTIVE'
                )
            ).scalar() or Decimal('0')
            
            print(f"Active Reservations Total: {actual_reserved}")
            print(f"Synchronization Status: {'✓ SYNCED' if total_reserved_inventory == actual_reserved else '✗ OUT OF SYNC'}")
            
            if total_reserved_inventory != actual_reserved:
                print(f"SYNC ERROR: Inventory shows {total_reserved_inventory} reserved, but reservations total {actual_reserved}")
            
        # Test 2: Test MRP analysis service availability calculations
        print("\n2. Testing MRP Analysis Service...")
        
        mrp_service = MRPAnalysisService(session)
        
        # Test SF-FRAME availability analysis
        sf_frame_product = session.query(Product).filter(Product.product_code == 'SF-FRAME').first()
        if sf_frame_product:
            print(f"\n--- Testing {sf_frame_product.product_code} availability analysis ---")
            
            availability_analysis = mrp_service._analyze_component_availability(
                sf_frame_product.product_id, 
                Decimal('5')  # Test requiring 5 units
            )
            
            print(f"Product: {availability_analysis['product_code']}")
            print(f"Available Quantity: {availability_analysis['available_quantity']}")
            print(f"Required: 5")
            print(f"Can fulfill: {'✓ YES' if availability_analysis['available_quantity'] >= 5 else '✗ NO'}")
            
        # Test 3: Run validation and fix function
        print("\n3. Running comprehensive validation...")
        
        validation_results = mrp_service.validate_and_fix_reservation_sync()
        
        print(f"Total items checked: {validation_results['total_items_checked']}")
        print(f"Sync issues found: {validation_results['sync_issues_found']}")
        print(f"Fixes applied: {validation_results['fixes_applied']}")
        
        if validation_results['details']:
            print("\nDetailed results:")
            for detail in validation_results['details']:
                print(f"  - {detail}")
        
        # Test 4: Re-check state after validation
        print("\n4. Re-checking state after validation...")
        
        session.commit()  # Commit any fixes
        
        for product_code in test_products:
            print(f"\n--- {product_code} Post-Validation ---")
            
            product = session.query(Product).filter(Product.product_code == product_code).first()
            if not product:
                continue
                
            # Get current state
            inventory_items = session.query(InventoryItem).filter(
                InventoryItem.product_id == product.product_id
            ).all()
            
            total_reserved_inventory = sum(item.reserved_quantity for item in inventory_items)
            
            actual_reserved = session.query(func.coalesce(func.sum(StockReservation.reserved_quantity), 0)).filter(
                and_(
                    StockReservation.product_id == product.product_id,
                    StockReservation.status == 'ACTIVE'
                )
            ).scalar() or Decimal('0')
            
            print(f"Inventory Reserved: {total_reserved_inventory}")
            print(f"Actual Reservations: {actual_reserved}")
            print(f"Status: {'✓ SYNCED' if total_reserved_inventory == actual_reserved else '✗ STILL OUT OF SYNC'}")
        
        print("\n=== TEST COMPLETE ===")
        
        return validation_results['sync_issues_found'] == 0
        
    except Exception as e:
        print(f"ERROR during testing: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        session.close()

def test_production_order_analysis():
    """Test production order analysis with corrected availability."""
    session = SessionLocal()
    try:
        print("\n=== PRODUCTION ORDER ANALYSIS TEST ===\n")
        
        mrp_service = MRPAnalysisService(session)
        
        # Test analysis for a typical production order
        # Let's test FP-TABLE production analysis
        
        fp_table = session.query(Product).filter(Product.product_code == 'FP-TABLE').first()
        if not fp_table:
            print("ERROR: FP-TABLE product not found!")
            return False
            
        # Get its BOM
        from models.bom import BillOfMaterials
        bom = session.query(BillOfMaterials).filter(
            and_(
                BillOfMaterials.parent_product_id == fp_table.product_id,
                BillOfMaterials.status == 'ACTIVE'
            )
        ).first()
        
        if not bom:
            print("ERROR: Active BOM for FP-TABLE not found!")
            return False
            
        print(f"Testing production analysis for {fp_table.product_code}")
        print(f"Using BOM ID: {bom.bom_id}")
        print(f"Planned quantity: 5 units")
        
        # Perform stock analysis
        try:
            analysis_result = mrp_service.analyze_stock_availability(
                product_id=fp_table.product_id,
                bom_id=bom.bom_id,
                planned_quantity=Decimal('5'),
                warehouse_id=3  # Finished products warehouse
            )
            
            print(f"\nAnalysis Results:")
            print(f"Can produce: {'✓ YES' if analysis_result.can_produce else '✗ NO'}")
            print(f"Shortage exists: {'✓ YES' if analysis_result.shortage_exists else '✗ NO'}")
            print(f"Total estimated cost: ${analysis_result.total_estimated_cost}")
            
            print(f"\nComponent Requirements ({len(analysis_result.component_requirements)}):")
            for req in analysis_result.component_requirements:
                status = "✓ SUFFICIENT" if req.shortage_quantity == 0 else f"✗ SHORT {req.shortage_quantity}"
                print(f"  - {req.product_code}: Required={req.required_quantity}, Available={req.available_quantity}, {status}")
            
            if analysis_result.semi_finished_shortages:
                print(f"\nSemi-finished Shortages ({len(analysis_result.semi_finished_shortages)}):")
                for shortage in analysis_result.semi_finished_shortages:
                    print(f"  - {shortage.product_code}: Short {shortage.shortage_quantity} units")
            
            if analysis_result.raw_material_shortages:
                print(f"\nRaw Material Shortages ({len(analysis_result.raw_material_shortages)}):")
                for shortage in analysis_result.raw_material_shortages:
                    print(f"  - {shortage.product_code}: Short {shortage.shortage_quantity} units")
            
            return True
            
        except Exception as e:
            print(f"ERROR during production analysis: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    except Exception as e:
        print(f"ERROR during production order test: {e}")
        return False
        
    finally:
        session.close()

if __name__ == "__main__":
    print("Starting Phantom Stock Fix Verification Tests...\n")
    
    # Test 1: Basic phantom stock fix verification
    basic_test_passed = test_phantom_stock_fix()
    
    # Test 2: Production order analysis test
    production_test_passed = test_production_order_analysis()
    
    print(f"\n=== FINAL RESULTS ===")
    print(f"Basic phantom stock fix test: {'✓ PASSED' if basic_test_passed else '✗ FAILED'}")
    print(f"Production order analysis test: {'✓ PASSED' if production_test_passed else '✗ FAILED'}")
    
    if basic_test_passed and production_test_passed:
        print("\n🎉 ALL TESTS PASSED! Phantom stock issue is resolved.")
    else:
        print("\n❌ SOME TESTS FAILED! Issues still exist.")
    
    print("\nTesting complete.")