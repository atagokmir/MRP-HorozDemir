#!/usr/bin/env python3
"""
Test script to verify production order deletion and stock reservation release.
This script tests the reported bug where stock reservations are not being released correctly.
"""

import requests
import json
from time import sleep

BASE_URL = "http://localhost:8000/api/v1"

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def api_call(method, endpoint, data=None):
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == 'GET':
            response = requests.get(url)
        elif method == 'POST':
            response = requests.post(url, json=data)
        elif method == 'DELETE':
            response = requests.delete(url)
        
        print(f"{method} {endpoint} -> Status: {response.status_code}")
        
        if response.status_code >= 400:
            print(f"ERROR Response: {response.text}")
            return None
            
        return response.json()
    except Exception as e:
        print(f"ERROR: {e}")
        return None

def get_inventory_summary(product_id, warehouse_id):
    """Get inventory info via database query using SQLAlchemy directly"""
    try:
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__)))
        
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from models.inventory import InventoryItem
        from models.master_data import Product, Warehouse
        from models.production import StockReservation
        from sqlalchemy import and_, func
        
        # Use the test database
        engine = create_engine("sqlite:///test_mrp.db")
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Get inventory items for this product/warehouse
        inventory_items = session.query(InventoryItem).filter(
            and_(
                InventoryItem.product_id == product_id,
                InventoryItem.warehouse_id == warehouse_id
            )
        ).all()
        
        # Get active reservations
        active_reservations = session.query(StockReservation).filter(
            and_(
                StockReservation.product_id == product_id,
                StockReservation.warehouse_id == warehouse_id,
                StockReservation.status == 'ACTIVE'
            )
        ).all()
        
        # Get released reservations
        released_reservations = session.query(StockReservation).filter(
            and_(
                StockReservation.product_id == product_id,
                StockReservation.warehouse_id == warehouse_id,
                StockReservation.status == 'RELEASED'
            )
        ).all()
        
        total_stock = sum(float(item.quantity_in_stock) for item in inventory_items)
        total_reserved = sum(float(item.reserved_quantity) for item in inventory_items)
        
        session.close()
        
        return {
            'total_stock': total_stock,
            'total_reserved': total_reserved,
            'inventory_items_count': len(inventory_items),
            'active_reservations_count': len(active_reservations),
            'released_reservations_count': len(released_reservations),
            'active_reservations_total': sum(float(res.reserved_quantity) for res in active_reservations),
            'released_reservations_total': sum(float(res.reserved_quantity) for res in released_reservations)
        }
    except Exception as e:
        return {'error': str(e)}

def main():
    print_section("PRODUCTION ORDER DELETION & RESERVATION RELEASE TEST")
    print("Testing the reported bug: Reservations not being released on order deletion")
    
    # Step 1: Check initial reservations state
    print_section("STEP 1: Check Initial Reservations State")
    reservations_before = api_call('GET', '/production-orders/reservations/all')
    
    if reservations_before:
        print(f"Total reservations before test: {reservations_before['summary']['total_reservations']}")
        print(f"Active reservations: {reservations_before['summary']['active_reservations']}")
        print(f"Released reservations: {reservations_before['summary']['released_reservations']}")
    
    # Step 2: Create a new production order
    print_section("STEP 2: Create Test Production Order")
    
    production_order_data = {
        "product_id": 301,    # Complete Table finished product
        "bom_id": 3001,       # Complete Table BOM v1.0
        "warehouse_id": 3,    # Finished goods warehouse
        "planned_start_date": "2025-08-23",
        "planned_completion_date": "2025-08-25",
        "planned_quantity": 1,
        "priority": 5,
        "notes": "Test order for reservation release testing"
    }
    
    created_order = api_call('POST', '/production-orders/', production_order_data)
    
    if not created_order:
        print("FAILED: Could not create production order")
        return
    
    order_id = created_order['id']
    print(f"✅ Created production order ID: {order_id}")
    
    # Step 3: Check reservations after creation
    print_section("STEP 3: Check Reservations After Order Creation")
    
    sleep(1)  # Give time for reservations to be created
    
    reservations_after_create = api_call('GET', '/production-orders/reservations/all')
    order_reservations = api_call('GET', f'/production-orders/{order_id}/reservations')
    
    if reservations_after_create:
        print(f"Total reservations after creation: {reservations_after_create['summary']['total_reservations']}")
        print(f"Active reservations: {reservations_after_create['summary']['active_reservations']}")
        print(f"Released reservations: {reservations_after_create['summary']['released_reservations']}")
    
    if order_reservations:
        print(f"Reservations for order {order_id}: {order_reservations['reservation_summary']['total_reservations']}")
        print(f"Active for this order: {order_reservations['reservation_summary']['active_reservations']}")
        
        # Sample some inventory data
        if order_reservations['reservations_by_product']:
            sample_product = order_reservations['reservations_by_product'][0]['product']
            sample_warehouse = 1  # Raw materials warehouse
            inventory_summary = get_inventory_summary(sample_product['product_id'], sample_warehouse)
            print(f"Sample inventory for {sample_product['product_code']}:")
            print(f"  Inventory Summary: {inventory_summary}")
    
    # Step 4: Delete the production order
    print_section("STEP 4: Delete Production Order")
    
    delete_result = api_call('DELETE', f'/production-orders/{order_id}')
    
    if delete_result:
        print(f"✅ Delete response: {delete_result['message']}")
    else:
        print("❌ Failed to delete production order")
        return
    
    # Step 5: Check reservations after deletion
    print_section("STEP 5: Check Reservations After Order Deletion")
    
    sleep(1)  # Give time for reservations to be released
    
    reservations_after_delete = api_call('GET', '/production-orders/reservations/all')
    
    if reservations_after_delete:
        print(f"Total reservations after deletion: {reservations_after_delete['summary']['total_reservations']}")
        print(f"Active reservations: {reservations_after_delete['summary']['active_reservations']}")
        print(f"Released reservations: {reservations_after_delete['summary']['released_reservations']}")
        
        # Check if any reservations still reference the deleted order
        deleted_order_reservations = [
            res for res in reservations_after_delete['reservations'] 
            if res['production_order'] and res['production_order']['production_order_id'] == order_id
        ]
        
        if deleted_order_reservations:
            print(f"❌ ERROR: Found {len(deleted_order_reservations)} reservations still referencing deleted order {order_id}")
        else:
            print(f"✅ No reservations reference deleted order {order_id}")
            
        # Check if new RELEASED reservations were created
        new_released = reservations_after_delete['summary']['released_reservations'] - reservations_before['summary']['released_reservations']
        if new_released > 0:
            print(f"✅ {new_released} new RELEASED reservations created")
        else:
            print(f"❌ No new RELEASED reservations found")
    
    # Step 6: Check inventory synchronization
    print_section("STEP 6: Check Inventory Synchronization")
    
    if order_reservations and order_reservations['reservations_by_product']:
        for product_reservation in order_reservations['reservations_by_product']:
            product = product_reservation['product']
            # Find the warehouse from the reservation details
            if product_reservation['reservations']:
                warehouse_id = product_reservation['reservations'][0]['warehouse_id']
                inventory_summary = get_inventory_summary(product['product_id'], warehouse_id)
                print(f"Post-deletion inventory for {product['product_code']} in warehouse {warehouse_id}:")
                print(f"  {inventory_summary}")
                
                if inventory_summary.get('total_reserved', 0) > 0:
                    print(f"  ❌ WARNING: Still has {inventory_summary['total_reserved']} reserved quantity")
                else:
                    print(f"  ✅ No reserved quantity remaining")
    
    # Step 7: Summary
    print_section("TEST RESULTS SUMMARY")
    
    reservation_release_working = (
        reservations_after_delete and 
        reservations_after_delete['summary']['released_reservations'] > reservations_before['summary']['released_reservations']
    )
    
    if reservation_release_working:
        print("✅ Reservation release mechanism: WORKING")
    else:
        print("❌ Reservation release mechanism: FAILED")
    
    print("\nTest completed. Review the results above to identify any issues.")

if __name__ == "__main__":
    main()