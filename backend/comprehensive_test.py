#!/usr/bin/env python3
"""
Comprehensive test that ensures stock reservation release is working correctly.
This test clears all existing reservations and starts from a clean state.
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
from app.services.mrp_analysis import MRPAnalysisService
from decimal import Decimal

BASE_URL = "http://localhost:8000/api/v1"
engine = create_engine("sqlite:///test_mrp.db")
Session = sessionmaker(bind=engine)

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

def clear_test_state():
    """Clear all reservations and reset inventory reserved quantities"""
    session = Session()
    
    try:
        # Clear all existing reservations
        session.query(StockReservation).delete()
        
        # Reset all inventory reserved quantities to 0
        inventory_items = session.query(InventoryItem).all()
        for item in inventory_items:
            item.reserved_quantity = Decimal('0')
        
        session.commit()
        print("✅ Cleared all reservations and reset inventory quantities")
        
    finally:
        session.close()

def get_inventory_state(product_id, warehouse_id):
    """Get current inventory and reservation state for a product/warehouse"""
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
    print("=== COMPREHENSIVE STOCK RESERVATION RELEASE TEST ===\n")
    
    # Step 1: Clear existing state
    print("1. Clearing existing test state...")
    clear_test_state()
    
    # Step 2: Create a test production order
    print("\n2. Creating test production order...")
    production_order_data = {
        "product_id": 301,    # Complete Table
        "bom_id": 3001,       # Complete Table BOM
        "warehouse_id": 3,    # Finished goods warehouse
        "planned_start_date": "2025-08-23",
        "planned_completion_date": "2025-08-25",
        "planned_quantity": 1,
        "priority": 5,
        "notes": "Comprehensive test"
    }
    
    created_order = api_call('POST', '/production-orders/', production_order_data)
    if not created_order:
        print("❌ Failed to create production order")
        return False
    
    order_id = created_order['id']
    print(f"✅ Created production order ID: {order_id}")
    
    # Step 3: Check reservations were created
    sleep(1)
    order_reservations = api_call('GET', f'/production-orders/{order_id}/reservations')
    if not order_reservations:
        print("❌ Failed to get order reservations")
        return False
    
    active_reservations_count = order_reservations['reservation_summary']['active_reservations']
    print(f"✅ Created {active_reservations_count} active reservations")
    
    if active_reservations_count == 0:
        print("❌ No active reservations created - cannot test deletion")
        return False
    
    # Step 4: Verify inventory state before deletion
    print(f"\n3. Checking inventory state before deletion:")
    product_states_before = []
    all_synced_before = True
    
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
        
        if not state['is_synced']:
            all_synced_before = False
    
    if not all_synced_before:
        print("❌ Inventory not synced before deletion - this indicates a reservation creation issue")
        return False
    
    # Step 5: Delete the production order
    print(f"\n4. Deleting production order {order_id}...")
    delete_result = api_call('DELETE', f'/production-orders/{order_id}')
    if not delete_result:
        print("❌ Failed to delete production order")
        return False
    
    print(f"✅ {delete_result['message']}")
    
    # Step 6: Verify inventory state after deletion
    sleep(1)  # Give time for async operations
    print(f"\n5. Checking inventory state after deletion:")
    all_synced_after = True
    all_zero_reservations = True
    
    for product_state in product_states_before:
        new_state = get_inventory_state(product_state['product_id'], product_state['warehouse_id'])
        
        sync_status = "✅ SYNCED" if new_state['is_synced'] else "❌ NOT SYNCED"
        print(f"   {product_state['product_code']}: Inventory={new_state['inventory_reserved']}, Active={new_state['active_reservations']} {sync_status}")
        
        if not new_state['is_synced']:
            all_synced_after = False
        
        if new_state['active_reservations'] != 0:
            print(f"      ❌ ERROR: Still has {new_state['active_reservations']} active reservations after deletion!")
            all_zero_reservations = False
        
        if new_state['inventory_reserved'] != 0:
            print(f"      ❌ ERROR: Still has {new_state['inventory_reserved']} inventory reserved after deletion!")
    
    # Step 7: Final verification
    print(f"\n6. COMPREHENSIVE TEST RESULT:")
    
    if all_synced_after and all_zero_reservations:
        print("✅ SUCCESS: Stock reservation release is working perfectly!")
        print("   - All reservations were marked as RELEASED")
        print("   - All inventory reserved quantities were reset to 0")
        print("   - All inventory items are synchronized with active reservations")
        return True
    else:
        print("❌ FAILED: Stock reservation release has issues")
        if not all_zero_reservations:
            print("   - Active reservations were not properly released")
        if not all_synced_after:
            print("   - Inventory reserved quantities were not properly synchronized")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)