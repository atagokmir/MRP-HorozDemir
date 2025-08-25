#!/usr/bin/env python3
"""
Fix all inventory synchronization issues by manually syncing all products with reserved quantities.
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

def fix_all_inventory_sync():
    print("=== FIXING ALL INVENTORY SYNCHRONIZATION ISSUES ===\n")
    
    # Initialize MRP service
    mrp_service = MRPAnalysisService(session)
    
    # Get all product/warehouse combinations that have reserved quantities
    problematic_combinations = session.query(
        InventoryItem.product_id, 
        InventoryItem.warehouse_id
    ).filter(
        InventoryItem.reserved_quantity > 0
    ).distinct().all()
    
    print(f"Found {len(problematic_combinations)} product/warehouse combinations with reserved quantities")
    
    for product_id, warehouse_id in problematic_combinations:
        product = session.query(Product).get(product_id)
        warehouse = session.query(Warehouse).get(warehouse_id)
        
        # Get current reserved quantities
        current_inventory_reserved = session.query(func.sum(InventoryItem.reserved_quantity)).filter(
            and_(
                InventoryItem.product_id == product_id,
                InventoryItem.warehouse_id == warehouse_id
            )
        ).scalar() or Decimal('0')
        
        active_reservations_total = session.query(func.sum(StockReservation.reserved_quantity)).filter(
            and_(
                StockReservation.product_id == product_id,
                StockReservation.warehouse_id == warehouse_id,
                StockReservation.status == 'ACTIVE'
            )
        ).scalar() or Decimal('0')
        
        print(f"Product: {product.product_code} in {warehouse.warehouse_code}")
        print(f"  Current inventory reserved: {current_inventory_reserved}")
        print(f"  Active reservations total: {active_reservations_total}")
        
        # Get a sample inventory item to trigger sync
        sample_item = session.query(InventoryItem).filter(
            and_(
                InventoryItem.product_id == product_id,
                InventoryItem.warehouse_id == warehouse_id,
                InventoryItem.quality_status == 'APPROVED'
            )
        ).first()
        
        if sample_item:
            # Call the sync method
            mrp_service._sync_inventory_reserved_quantity(sample_item.inventory_item_id)
            
            # Check the result
            new_inventory_reserved = session.query(func.sum(InventoryItem.reserved_quantity)).filter(
                and_(
                    InventoryItem.product_id == product_id,
                    InventoryItem.warehouse_id == warehouse_id
                )
            ).scalar() or Decimal('0')
            
            print(f"  After sync inventory reserved: {new_inventory_reserved}")
            
            if new_inventory_reserved == active_reservations_total:
                print(f"  ✅ FIXED - Inventory now matches reservations")
            else:
                print(f"  ❌ STILL HAS ISSUES - Mismatch between inventory and reservations")
        else:
            print(f"  ❌ No approved inventory items found")
        
        print()
    
    # Commit all changes
    session.commit()
    print("All synchronization fixes committed to database.")

if __name__ == "__main__":
    try:
        fix_all_inventory_sync()
    finally:
        session.close()