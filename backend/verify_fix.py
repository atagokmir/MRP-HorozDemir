#!/usr/bin/env python3
"""
Verify that the stock reservation release fix is working correctly
by testing a complete create/delete cycle.
"""

import requests
import json
from time import sleep
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__)))

from sqlalchemy import create_engine, and_, func
from sqlalchemy.orm import sessionmaker
from models.inventory import InventoryItem
from models.production import StockReservation
from models.master_data import Product, Warehouse
from decimal import Decimal

BASE_URL = "http://localhost:8000/api/v1"

def api_call(method, endpoint, data=None):
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == 'GET':
            response = requests.get(url)
        elif method == 'POST':
            response = requests.post(url, json=data)
        elif method == 'DELETE':
            response = requests.delete(url)
        
        if response.status_code >= 400:
            print(f"ERROR {method} {endpoint}: {response.text}")
            return None
            
        return response.json()
    except Exception as e:
        print(f"ERROR: {e}")
        return None

def get_inventory_state(product_id, warehouse_id):
    """Get current inventory and reservation state for a product/warehouse"""
    engine = create_engine("sqlite:///test_mrp.db")
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Get total reserved in inventory
        inventory_reserved = session.query(func.sum(InventoryItem.reserved_quantity)).filter(
            and_(
                InventoryItem.product_id == product_id,
                InventoryItem.warehouse_id == warehouse_id
            )
        ).scalar() or Decimal('0')
        
        # Get total active reservations
        active_reserved = session.query(func.sum(StockReservation.reserved_quantity)).filter(
            and_(
                StockReservation.product_id == product_id,
                StockReservation.warehouse_id == warehouse_id,
                StockReservation.status == 'ACTIVE'
            )
        ).scalar() or Decimal('0')
        
        return {
            'inventory_reserved': float(inventory_reserved),
            'active_reservations': float(active_reserved),
            'is_synced': inventory_reserved == active_reserved
        }
    finally:
        session.close()

def main():
    print("=== STOCK RESERVATION RELEASE FIX VERIFICATION ===\n")
    
    # Create a test production order
    print("1. Creating test production order...")
    production_order_data = {
        "product_id": 301,    # Complete Table
        "bom_id": 3001,       # Complete Table BOM
        "warehouse_id": 3,    # Finished goods warehouse
        "planned_start_date": "2025-08-23",
        "planned_completion_date": "2025-08-25",
        "planned_quantity": 1,
        "priority": 5,
        "notes": "Fix verification test"
    }
    
    created_order = api_call('POST', '/production-orders/', production_order_data)
    if not created_order:
        print("❌ Failed to create production order")
        return False
    
    order_id = created_order['id']
    print(f"✅ Created production order ID: {order_id}")
    
    # Get reservations for this order
    sleep(1)
    order_reservations = api_call('GET', f'/production-orders/{order_id}/reservations')
    if not order_reservations:
        print("❌ Failed to get order reservations")
        return False
    
    print(f"✅ Created {order_reservations['reservation_summary']['active_reservations']} active reservations")
    
    # Check inventory state for each reserved product before deletion
    print("\n2. Checking inventory state before deletion:")
    product_states_before = []
    
    for product_res in order_reservations['reservations_by_product']:
        product = product_res['product']
        warehouse_id = product_res['reservations'][0]['warehouse_id']
        
        state = get_inventory_state(product['product_id'], warehouse_id)
        product_states_before.append({
            'product_id': product['product_id'],
            'product_code': product['product_code'],
            'warehouse_id': warehouse_id,
            'state': state
        })
        
        sync_status = "✅ SYNCED" if state['is_synced'] else "❌ NOT SYNCED"
        print(f"   {product['product_code']}: Inventory={state['inventory_reserved']}, Active={state['active_reservations']} {sync_status}")
    
    # Delete the production order
    print(f"\n3. Deleting production order {order_id}...")
    delete_result = api_call('DELETE', f'/production-orders/{order_id}')
    if not delete_result:
        print("❌ Failed to delete production order")
        return False
    
    print(f"✅ {delete_result['message']}")
    
    # Check inventory state after deletion
    print("\n4. Checking inventory state after deletion:")
    all_synced = True
    
    for product_state in product_states_before:
        new_state = get_inventory_state(product_state['product_id'], product_state['warehouse_id'])
        
        sync_status = "✅ SYNCED" if new_state['is_synced'] else "❌ NOT SYNCED"
        print(f"   {product_state['product_code']}: Inventory={new_state['inventory_reserved']}, Active={new_state['active_reservations']} {sync_status}")
        
        if not new_state['is_synced']:
            all_synced = False
        
        if new_state['active_reservations'] != 0:
            print(f"      ❌ ERROR: Still has {new_state['active_reservations']} active reservations after deletion!")
            all_synced = False
    
    # Final result
    print(f"\n5. VERIFICATION RESULT:")
    if all_synced:
        print("✅ SUCCESS: Stock reservation release is working correctly!")
        print("   - All reservations were marked as RELEASED")
        print("   - All inventory reserved quantities were synchronized")
        return True
    else:
        print("❌ FAILED: Stock reservation release has issues")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)