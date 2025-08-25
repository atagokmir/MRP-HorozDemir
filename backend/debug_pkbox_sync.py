#!/usr/bin/env python3
"""
Debug why PK-BOX sync is not working correctly.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__)))

from sqlalchemy import create_engine, and_, func
from sqlalchemy.orm import sessionmaker
from models.inventory import InventoryItem
from models.production import StockReservation
from models.master_data import Product, Warehouse
from app.services.mrp_analysis import MRPAnalysisService
from decimal import Decimal

# Use the test database
engine = create_engine("sqlite:///test_mrp.db")
Session = sessionmaker(bind=engine)
session = Session()

def debug_pkbox_sync():
    print("=== DEBUG: PK-BOX SYNCHRONIZATION ISSUE ===\n")
    
    # Find PK-BOX product
    pkbox = session.query(Product).filter(Product.product_code == 'PK-BOX').first()
    if not pkbox:
        print("PK-BOX product not found")
        return
    
    print(f"PK-BOX Product ID: {pkbox.product_id}")
    
    # Find warehouse 4 (PACK-01)
    warehouse = session.query(Warehouse).filter(Warehouse.warehouse_id == 4).first()
    print(f"Warehouse: {warehouse.warehouse_code} - {warehouse.warehouse_name}")
    
    # Get all inventory items for PK-BOX in warehouse 4
    inventory_items = session.query(InventoryItem).filter(
        and_(
            InventoryItem.product_id == pkbox.product_id,
            InventoryItem.warehouse_id == 4,
            InventoryItem.quality_status == 'APPROVED'
        )
    ).order_by(InventoryItem.entry_date).all()
    
    print(f"Inventory items found: {len(inventory_items)}")
    for item in inventory_items:
        print(f"  Item ID: {item.inventory_item_id}")
        print(f"  Stock: {item.quantity_in_stock}, Reserved: {item.reserved_quantity}")
        print(f"  Entry Date: {item.entry_date}")
        print()
    
    # Get active reservations for PK-BOX in warehouse 4
    active_reservations = session.query(StockReservation).filter(
        and_(
            StockReservation.product_id == pkbox.product_id,
            StockReservation.warehouse_id == 4,
            StockReservation.status == 'ACTIVE'
        )
    ).all()
    
    print(f"Active reservations: {len(active_reservations)}")
    total_active_reserved = Decimal('0')
    for res in active_reservations:
        print(f"  Reservation ID: {res.reservation_id}")
        print(f"  Quantity: {res.reserved_quantity}")
        print(f"  For Order: {res.reserved_for_id}")
        total_active_reserved += res.reserved_quantity
        print()
    
    print(f"Total active reserved: {total_active_reserved}")
    
    # Calculate what the reserved quantities should be
    print("\n=== MANUAL SYNC SIMULATION ===")
    
    remaining_to_allocate = total_active_reserved
    print(f"Total to allocate: {remaining_to_allocate}")
    
    for item in inventory_items:
        print(f"Item {item.inventory_item_id}:")
        print(f"  Current reserved: {item.reserved_quantity}")
        
        if remaining_to_allocate <= 0:
            new_reserved = Decimal('0')
        else:
            max_reservable = item.quantity_in_stock
            allocate_to_item = min(remaining_to_allocate, max_reservable)
            new_reserved = allocate_to_item
            remaining_to_allocate -= allocate_to_item
        
        print(f"  Should be reserved: {new_reserved}")
        print(f"  Remaining to allocate: {remaining_to_allocate}")
        print()
    
    # Test the actual sync method
    print("\n=== ACTUAL SYNC METHOD TEST ===")
    
    if inventory_items:
        mrp_service = MRPAnalysisService(session)
        sample_item = inventory_items[0]
        
        print(f"Testing sync on item {sample_item.inventory_item_id}")
        print(f"Before sync - Reserved: {sample_item.reserved_quantity}")
        
        # Call the sync method
        mrp_service._sync_inventory_reserved_quantity(sample_item.inventory_item_id)
        
        # Refresh and check all items
        for item in inventory_items:
            session.refresh(item)
            print(f"After sync - Item {item.inventory_item_id} Reserved: {item.reserved_quantity}")
        
        session.commit()

if __name__ == "__main__":
    try:
        debug_pkbox_sync()
    finally:
        session.close()