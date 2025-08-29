#!/usr/bin/env python3
"""
Fix the test scenario by properly synchronizing reservations and inventory.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.production import ProductionOrder, StockReservation
from models.inventory import InventoryItem

def fix_test_scenario():
    engine = create_engine("sqlite:///test_mrp.db", echo=False)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    try:
        print("🧹 Cleaning up existing test reservations...")
        
        # Get the production order
        production_order = session.query(ProductionOrder).filter(
            ProductionOrder.status == 'IN_PROGRESS'
        ).first()
        
        if not production_order:
            print("❌ No IN_PROGRESS production order found")
            return False
        
        # Delete all existing reservations for this order
        existing_reservations = session.query(StockReservation).filter(
            StockReservation.reserved_for_type == 'PRODUCTION_ORDER',
            StockReservation.reserved_for_id == production_order.production_order_id
        ).all()
        
        for res in existing_reservations:
            session.delete(res)
            
        print(f"🗑️ Deleted {len(existing_reservations)} existing reservations")
        
        # Reset all inventory reserved quantities to 0
        inventory_items = session.query(InventoryItem).all()
        for item in inventory_items:
            item.reserved_quantity = Decimal('0')
        
        print("🔄 Reset all inventory reserved quantities to 0")
        
        # Create proper synchronized reservations
        print("✨ Creating synchronized reservations...")
        
        # Get some inventory items with available stock
        available_items = session.query(InventoryItem).filter(
            InventoryItem.quantity_in_stock > 0
        ).limit(2).all()
        
        if not available_items:
            print("❌ No inventory items with available stock")
            return False
        
        total_reservations = 0
        for item in available_items:
            # Reserve some quantity (max 3 units)
            reserve_qty = min(Decimal('3'), item.quantity_in_stock)
            
            # Update inventory reserved quantity
            item.reserved_quantity = reserve_qty
            
            # Create matching reservation record
            reservation = StockReservation(
                product_id=item.product_id,
                warehouse_id=item.warehouse_id,
                reserved_quantity=reserve_qty,
                reserved_for_type='PRODUCTION_ORDER',
                reserved_for_id=production_order.production_order_id,
                status='ACTIVE',
                expiry_date=datetime.now().replace(hour=23, minute=59, second=59),
                notes=f'Synchronized reservation for production order {production_order.order_number}'
            )
            
            session.add(reservation)
            total_reservations += 1
            
            print(f"✅ Created synced reservation: Product {item.product_id}, {reserve_qty} units")
        
        session.commit()
        
        # Verify synchronization
        print("\n🔍 Verifying synchronization...")
        
        reservations = session.query(StockReservation).filter(
            StockReservation.reserved_for_type == 'PRODUCTION_ORDER',
            StockReservation.reserved_for_id == production_order.production_order_id,
            StockReservation.status == 'ACTIVE'
        ).all()
        
        all_synced = True
        for res in reservations:
            inventory_items = session.query(InventoryItem).filter(
                InventoryItem.product_id == res.product_id,
                InventoryItem.warehouse_id == res.warehouse_id
            ).all()
            
            total_inventory_reserved = sum(item.reserved_quantity for item in inventory_items)
            
            if res.reserved_quantity != total_inventory_reserved:
                print(f"❌ Still not synced: Product {res.product_id}, Reservation: {res.reserved_quantity}, Inventory: {total_inventory_reserved}")
                all_synced = False
            else:
                print(f"✅ Synced: Product {res.product_id}, {res.reserved_quantity} units")
        
        if all_synced:
            print(f"\n🎉 Success! Created {len(reservations)} properly synchronized reservations.")
            return True
        else:
            print("\n❌ Synchronization still has issues.")
            return False
        
    except Exception as e:
        print(f"❌ Failed to fix test scenario: {e}")
        session.rollback()
        return False
        
    finally:
        session.close()

if __name__ == "__main__":
    success = fix_test_scenario()
    sys.exit(0 if success else 1)