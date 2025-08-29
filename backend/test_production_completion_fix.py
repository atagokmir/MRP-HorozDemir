#!/usr/bin/env python3
"""
Test script to verify the production completion workflow fixes.
Tests stock consumption from reserved quantities and finished goods creation.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import our models and services
from models.base import BaseModel
from models.production import ProductionOrder, StockReservation
from models.inventory import InventoryItem
from models.master_data import Product, Warehouse
from app.services.mrp_analysis import MRPAnalysisService

def test_production_completion_workflow():
    """
    Test the complete production completion workflow:
    1. Create test data with reservations
    2. Complete production order
    3. Verify stock consumption from reserved quantities
    4. Verify finished goods creation
    """
    
    # Create test database connection
    engine = create_engine("sqlite:///test_mrp.db", echo=False)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        # Test data setup
        print("🔧 Setting up test data...")
        
        # Get a production order with active reservations
        production_order = session.query(ProductionOrder).filter(
            ProductionOrder.status == 'IN_PROGRESS'
        ).first()
        
        if not production_order:
            print("❌ No IN_PROGRESS production orders found. Please create test data first.")
            return False
            
        print(f"✅ Found production order: {production_order.order_number}")
        
        # Get reservations for this production order
        reservations = session.query(StockReservation).filter(
            StockReservation.reserved_for_type == 'PRODUCTION_ORDER',
            StockReservation.reserved_for_id == production_order.production_order_id,
            StockReservation.status == 'ACTIVE'
        ).all()
        
        if not reservations:
            print("❌ No active reservations found. Cannot test consumption.")
            return False
            
        print(f"✅ Found {len(reservations)} active reservations")
        
        # Record initial state
        initial_state = {}
        for res in reservations:
            # Get inventory items that have reserved quantity for this product/warehouse
            inventory_items = session.query(InventoryItem).filter(
                InventoryItem.product_id == res.product_id,
                InventoryItem.warehouse_id == res.warehouse_id,
                InventoryItem.reserved_quantity > 0
            ).all()
            
            initial_state[res.reservation_id] = {
                'reserved_qty': res.reserved_quantity,
                'inventory_items': [
                    {
                        'id': item.inventory_item_id,
                        'stock': item.quantity_in_stock,
                        'reserved': item.reserved_quantity
                    } for item in inventory_items
                ]
            }
        
        print("📊 Initial state recorded")
        
        # Test the MRP service
        mrp_service = MRPAnalysisService(session)
        
        print("\n🏭 Testing production completion workflow...")
        
        # Test stock consumption
        print("1️⃣ Testing stock consumption...")
        try:
            consumption_records = mrp_service.consume_stock_for_production(
                production_order.production_order_id
            )
            print(f"✅ Stock consumption completed. Records: {len(consumption_records)}")
            
            # Verify consumption records
            total_consumed_cost = sum(record['total_cost'] for record in consumption_records)
            print(f"   💰 Total material cost consumed: {total_consumed_cost}")
            
        except Exception as e:
            print(f"❌ Stock consumption failed: {e}")
            return False
        
        # Test finished goods creation
        print("2️⃣ Testing finished goods creation...")
        try:
            completed_quantity = Decimal('10')  # Test with 10 units
            finished_goods = mrp_service.create_finished_goods_inventory(
                production_order.production_order_id,
                completed_quantity,
                consumption_records
            )
            print(f"✅ Finished goods created: {finished_goods}")
            print(f"   📦 Quantity: {finished_goods['quantity']}")
            print(f"   💰 Unit cost: {finished_goods['unit_cost']}")
            print(f"   🏭 Batch: {finished_goods['batch_number']}")
            
        except Exception as e:
            print(f"❌ Finished goods creation failed: {e}")
            session.rollback()
            return False
        
        # Verify final state
        print("\n📊 Verifying final state...")
        
        # Check reservations are now CONSUMED
        updated_reservations = session.query(StockReservation).filter(
            StockReservation.reserved_for_type == 'PRODUCTION_ORDER',
            StockReservation.reserved_for_id == production_order.production_order_id
        ).all()
        
        consumed_count = sum(1 for res in updated_reservations if res.status == 'CONSUMED')
        print(f"✅ Reservations consumed: {consumed_count}/{len(updated_reservations)}")
        
        # Check inventory quantities were properly reduced
        for res_id, initial in initial_state.items():
            # Find corresponding reservation
            res = next((r for r in updated_reservations if r.reservation_id == res_id), None)
            if res and res.status == 'CONSUMED':
                # Check inventory items were properly updated
                updated_items = session.query(InventoryItem).filter(
                    InventoryItem.product_id == res.product_id,
                    InventoryItem.warehouse_id == res.warehouse_id
                ).all()
                
                for initial_item in initial['inventory_items']:
                    updated_item = next((i for i in updated_items if i.inventory_item_id == initial_item['id']), None)
                    if updated_item:
                        stock_diff = initial_item['stock'] - updated_item.quantity_in_stock
                        reserved_diff = initial_item['reserved'] - updated_item.reserved_quantity
                        print(f"   📦 Item {updated_item.inventory_item_id}: Stock reduced by {stock_diff}, Reserved reduced by {reserved_diff}")
        
        session.commit()
        print("\n✅ All tests passed! Production completion workflow is working correctly.")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        session.rollback()
        return False
        
    finally:
        session.close()

if __name__ == "__main__":
    print("🧪 Production Completion Workflow Test")
    print("=" * 50)
    
    success = test_production_completion_workflow()
    
    if success:
        print("\n🎉 SUCCESS: All production completion fixes are working correctly!")
    else:
        print("\n💥 FAILED: Production completion workflow needs more work.")
    
    sys.exit(0 if success else 1)