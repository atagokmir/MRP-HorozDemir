#!/usr/bin/env python3
"""
Debug script to understand why inventory reserved quantities aren't being synchronized
after releasing stock reservations.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__)))

from sqlalchemy import create_engine, and_, func
from sqlalchemy.orm import sessionmaker
from models.inventory import InventoryItem
from models.production import StockReservation
from models.master_data import Product, Warehouse
from decimal import Decimal

# Use the test database
engine = create_engine("sqlite:///test_mrp.db")
Session = sessionmaker(bind=engine)
session = Session()

def debug_inventory_sync_issue():
    print("=== DEBUG: INVENTORY SYNCHRONIZATION ISSUE ===\n")
    
    # Find inventory items with reserved quantities
    print("1. Inventory items with reserved quantities:")
    items_with_reservations = session.query(InventoryItem).filter(
        InventoryItem.reserved_quantity > 0
    ).all()
    
    for item in items_with_reservations:
        product = session.query(Product).get(item.product_id)
        warehouse = session.query(Warehouse).get(item.warehouse_id)
        
        print(f"   Item ID: {item.inventory_item_id}")
        print(f"   Product: {product.product_code} - {product.product_name}")
        print(f"   Warehouse: {warehouse.warehouse_code} - {warehouse.warehouse_name}")
        print(f"   Stock: {item.quantity_in_stock}, Reserved: {item.reserved_quantity}")
        print(f"   Quality Status: {item.quality_status}")
        print()
        
        # Check active reservations for this product/warehouse
        active_reservations = session.query(StockReservation).filter(
            and_(
                StockReservation.product_id == item.product_id,
                StockReservation.warehouse_id == item.warehouse_id,
                StockReservation.status == 'ACTIVE'
            )
        ).all()
        
        total_active_reserved = sum(float(res.reserved_quantity) for res in active_reservations)
        
        print(f"   Active reservations for this product/warehouse: {len(active_reservations)}")
        print(f"   Total active reserved quantity: {total_active_reserved}")
        print(f"   Inventory reserved quantity: {item.reserved_quantity}")
        print(f"   SYNC ISSUE: {'Yes' if total_active_reserved != float(item.reserved_quantity) else 'No'}")
        print()
        
        # Show the reservations
        if active_reservations:
            print("   Active reservations:")
            for res in active_reservations:
                print(f"     - Reservation ID: {res.reservation_id}, Qty: {res.reserved_quantity}, "
                      f"For Order: {res.reserved_for_id}, Status: {res.status}")
        else:
            print("   No active reservations found!")
        
        print("-" * 80)
    
    print(f"\n2. Total inventory items with reservation issues: {len(items_with_reservations)}")
    
    # Check released reservations
    print("\n3. Recently released reservations:")
    released_reservations = session.query(StockReservation).filter(
        StockReservation.status == 'RELEASED'
    ).order_by(StockReservation.updated_at.desc()).limit(10).all()
    
    for res in released_reservations:
        product = session.query(Product).get(res.product_id)
        warehouse = session.query(Warehouse).get(res.warehouse_id)
        print(f"   Released Reservation ID: {res.reservation_id}")
        print(f"   Product: {product.product_code}, Warehouse: {warehouse.warehouse_code}")
        print(f"   Quantity: {res.reserved_quantity}, For Order: {res.reserved_for_id}")
        print(f"   Status: {res.status}, Updated: {res.updated_at}")
        print()

def test_sync_method():
    print("\n=== TEST: MANUAL SYNC METHOD ===\n")
    
    # Find an inventory item with reservation issues
    problematic_item = session.query(InventoryItem).filter(
        InventoryItem.reserved_quantity > 0
    ).first()
    
    if not problematic_item:
        print("No problematic inventory items found.")
        return
    
    print(f"Testing sync for item ID: {problematic_item.inventory_item_id}")
    print(f"Product ID: {problematic_item.product_id}, Warehouse ID: {problematic_item.warehouse_id}")
    print(f"Current reserved quantity: {problematic_item.reserved_quantity}")
    
    # Calculate what the reserved quantity should be
    active_reservations_total = session.query(func.coalesce(func.sum(StockReservation.reserved_quantity), 0)).filter(
        and_(
            StockReservation.product_id == problematic_item.product_id,
            StockReservation.warehouse_id == problematic_item.warehouse_id,
            StockReservation.status == 'ACTIVE'
        )
    ).scalar() or Decimal('0')
    
    print(f"Total active reservations: {active_reservations_total}")
    
    # Manually test the sync logic
    inventory_items = session.query(InventoryItem).filter(
        and_(
            InventoryItem.product_id == problematic_item.product_id,
            InventoryItem.warehouse_id == problematic_item.warehouse_id,
            InventoryItem.quality_status == 'APPROVED'
        )
    ).order_by(InventoryItem.entry_date).all()
    
    print(f"Inventory items found for sync: {len(inventory_items)}")
    
    # Apply the sync logic
    remaining_to_allocate = active_reservations_total
    
    for item in inventory_items:
        old_reserved = item.reserved_quantity
        
        if remaining_to_allocate <= 0:
            # No more reservation to allocate
            item.reserved_quantity = Decimal('0')
        else:
            # Allocate as much as possible to this item (up to its total stock)
            max_reservable = item.quantity_in_stock
            allocate_to_item = min(remaining_to_allocate, max_reservable)
            item.reserved_quantity = allocate_to_item
            remaining_to_allocate -= allocate_to_item
        
        print(f"Item {item.inventory_item_id}: {old_reserved} -> {item.reserved_quantity}")
    
    print(f"Remaining to allocate after sync: {remaining_to_allocate}")
    
    # Apply changes
    session.commit()
    print("Changes committed to database.")

if __name__ == "__main__":
    try:
        debug_inventory_sync_issue()
        test_sync_method()
    finally:
        session.close()