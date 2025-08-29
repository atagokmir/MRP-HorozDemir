#!/usr/bin/env python3
"""
Create a test scenario for production completion workflow testing.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.production import ProductionOrder, StockReservation
from models.inventory import InventoryItem
from models.master_data import Product, Warehouse

def create_test_scenario():
    """Create a test production order with reservations."""
    
    engine = create_engine("sqlite:///test_mrp.db", echo=False)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        print("🔧 Creating test scenario...")
        
        # Find a production order to reset
        production_order = session.query(ProductionOrder).first()
        if not production_order:
            print("❌ No production orders found")
            return False
            
        # Reset it to IN_PROGRESS
        production_order.status = 'IN_PROGRESS'
        production_order.completed_quantity = Decimal('0')
        production_order.scrapped_quantity = Decimal('0')
        
        print(f"✅ Reset production order {production_order.order_number} to IN_PROGRESS")
        
        # Find some inventory items to create reservations from
        inventory_items = session.query(InventoryItem).filter(
            InventoryItem.quantity_in_stock > 0
        ).limit(3).all()
        
        if not inventory_items:
            print("❌ No inventory items found")
            return False
        
        # Create test reservations
        for i, item in enumerate(inventory_items):
            # Reserve some quantity
            reserve_qty = min(Decimal('5'), item.quantity_in_stock)
            
            # Update inventory reserved quantity
            item.reserved_quantity = reserve_qty
            
            # Create reservation record
            reservation = StockReservation(
                product_id=item.product_id,
                warehouse_id=item.warehouse_id,
                reserved_quantity=reserve_qty,
                reserved_for_type='PRODUCTION_ORDER',
                reserved_for_id=production_order.production_order_id,
                status='ACTIVE',
                expiry_date=datetime.now().replace(hour=23, minute=59, second=59),
                notes=f'Test reservation {i+1} for production order {production_order.order_number}'
            )
            
            session.add(reservation)
            print(f"✅ Created reservation for product {item.product_id}: {reserve_qty} units")
        
        session.commit()
        print("✅ Test scenario created successfully!")
        
        # Show summary
        reservations = session.query(StockReservation).filter(
            StockReservation.reserved_for_type == 'PRODUCTION_ORDER',
            StockReservation.reserved_for_id == production_order.production_order_id,
            StockReservation.status == 'ACTIVE'
        ).all()
        
        print(f"\n📊 Test scenario summary:")
        print(f"   Production Order: {production_order.order_number} (Status: {production_order.status})")
        print(f"   Active Reservations: {len(reservations)}")
        for res in reservations:
            print(f"   - Product {res.product_id}: {res.reserved_quantity} units")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to create test scenario: {e}")
        session.rollback()
        return False
        
    finally:
        session.close()

if __name__ == "__main__":
    print("🧪 Creating Test Scenario for Production Completion")
    print("=" * 55)
    
    success = create_test_scenario()
    
    if success:
        print("\n🎉 Test scenario created! You can now run the production completion test.")
    else:
        print("\n💥 Failed to create test scenario.")
    
    sys.exit(0 if success else 1)