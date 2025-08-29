#!/usr/bin/env python3
"""
Debug reservation and inventory synchronization issues.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.production import ProductionOrder, StockReservation
from models.inventory import InventoryItem

def debug_reservations():
    engine = create_engine("sqlite:///test_mrp.db", echo=False)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    try:
        # Get the production order
        production_order = session.query(ProductionOrder).filter(
            ProductionOrder.status == 'IN_PROGRESS'
        ).first()
        
        print(f"Production Order: {production_order.order_number}")
        
        # Get reservations
        reservations = session.query(StockReservation).filter(
            StockReservation.reserved_for_type == 'PRODUCTION_ORDER',
            StockReservation.reserved_for_id == production_order.production_order_id,
            StockReservation.status == 'ACTIVE'
        ).all()
        
        print(f"Found {len(reservations)} reservations")
        
        # Group by product and warehouse
        reservation_summary = {}
        for res in reservations:
            key = (res.product_id, res.warehouse_id)
            if key not in reservation_summary:
                reservation_summary[key] = []
            reservation_summary[key].append(res)
        
        print("\nReservation Analysis:")
        for (product_id, warehouse_id), res_list in reservation_summary.items():
            total_reserved = sum(res.reserved_quantity for res in res_list)
            print(f"\nProduct {product_id}, Warehouse {warehouse_id}:")
            print(f"  Total reserved: {total_reserved}")
            
            # Get inventory items for this product/warehouse
            inventory_items = session.query(InventoryItem).filter(
                InventoryItem.product_id == product_id,
                InventoryItem.warehouse_id == warehouse_id
            ).all()
            
            total_inventory_reserved = sum(item.reserved_quantity for item in inventory_items)
            total_stock = sum(item.quantity_in_stock for item in inventory_items)
            
            print(f"  Inventory items: {len(inventory_items)}")
            print(f"  Total inventory reserved: {total_inventory_reserved}")
            print(f"  Total stock: {total_stock}")
            
            if total_reserved != total_inventory_reserved:
                print(f"  ❌ MISMATCH: Reservation total ({total_reserved}) != Inventory reserved ({total_inventory_reserved})")
                
                # Show detailed breakdown
                print(f"  Reservations:")
                for res in res_list:
                    print(f"    - ID {res.reservation_id}: {res.reserved_quantity}")
                
                print(f"  Inventory Items:")
                for item in inventory_items:
                    print(f"    - ID {item.inventory_item_id}: Stock={item.quantity_in_stock}, Reserved={item.reserved_quantity}")
            else:
                print(f"  ✅ Reservation totals match")
                
                # Check if we have enough reserved stock to consume from
                items_with_reservations = [item for item in inventory_items if item.reserved_quantity > 0]
                print(f"  Items with reservations: {len(items_with_reservations)}")
                
                if not items_with_reservations:
                    print(f"  ❌ No inventory items have reserved quantities!")
    
    finally:
        session.close()

if __name__ == "__main__":
    debug_reservations()