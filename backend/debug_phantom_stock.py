#!/usr/bin/env python3
"""
Debug script to trace phantom stock issue in MRP analysis.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker
from decimal import Decimal

from models.inventory import InventoryItem
from models.master_data import Product, Warehouse
from app.services.mrp_analysis import MRPAnalysisService

# Database connection
DATABASE_URL = "sqlite:///test_mrp.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def debug_component_availability(product_id: int, required_quantity: Decimal):
    """Debug the _analyze_component_availability method step by step."""
    print(f"\n{'='*60}")
    print(f"DEBUGGING COMPONENT AVAILABILITY FOR PRODUCT {product_id}")
    print(f"{'='*60}")
    
    session = SessionLocal()
    mrp_service = MRPAnalysisService(session)
    
    try:
        # Step 1: Get product information
        product = session.query(Product).get(product_id)
        print(f"\n1. PRODUCT INFO:")
        if product:
            print(f"   Product ID: {product.product_id}")
            print(f"   Product Code: {product.product_code}")
            print(f"   Product Name: {product.product_name}")
            print(f"   Product Type: {product.product_type}")
        else:
            print(f"   ERROR: Product {product_id} not found!")
            return
        
        # Step 2: Get appropriate source warehouse
        source_warehouse_id = mrp_service._get_source_warehouse_for_product(product)
        print(f"\n2. SOURCE WAREHOUSE DETERMINATION:")
        print(f"   Determined source warehouse ID: {source_warehouse_id}")
        
        if source_warehouse_id:
            warehouse = session.query(Warehouse).get(source_warehouse_id)
            if warehouse:
                print(f"   Source warehouse: {warehouse.warehouse_code} - {warehouse.warehouse_name} ({warehouse.warehouse_type})")
        
        # Step 3: Build query filters 
        print(f"\n3. QUERY FILTERS:")
        query_filter = [
            InventoryItem.product_id == product_id,
            InventoryItem.quality_status == 'APPROVED',
            InventoryItem.quantity_in_stock > InventoryItem.reserved_quantity
        ]
        print(f"   Base filters: product_id={product_id}, quality_status='APPROVED', available>0")
        
        if source_warehouse_id:
            query_filter.append(InventoryItem.warehouse_id == source_warehouse_id)
            print(f"   Warehouse filter: warehouse_id={source_warehouse_id}")
        else:
            print(f"   No warehouse filter (searching all warehouses)")
        
        # Step 4: Execute query and show results
        print(f"\n4. INVENTORY QUERY RESULTS:")
        available_items = session.query(InventoryItem).filter(
            and_(*query_filter)
        ).order_by(InventoryItem.entry_date).all()
        
        print(f"   Found {len(available_items)} inventory items:")
        total_available = Decimal('0')
        for i, item in enumerate(available_items):
            available_qty = item.available_quantity
            total_available += available_qty
            print(f"   [{i+1}] Warehouse {item.warehouse_id}: Stock={item.quantity_in_stock}, Reserved={item.reserved_quantity}, Available={available_qty}, Cost={item.unit_cost}, Entry={item.entry_date}")
        
        print(f"\n   TOTAL AVAILABLE QUANTITY: {total_available}")
        print(f"   REQUIRED QUANTITY: {required_quantity}")
        print(f"   SUFFICIENT STOCK: {'YES' if total_available >= required_quantity else 'NO'}")
        print(f"   SHORTAGE: {max(Decimal('0'), required_quantity - total_available)}")
        
        # Step 5: Show what the MRP service actually returns
        print(f"\n5. MRP SERVICE RESULT:")
        result = mrp_service._analyze_component_availability(product_id, required_quantity)
        print(f"   Available quantity reported: {result['available_quantity']}")
        print(f"   Unit cost reported: {result['unit_cost']}")
        print(f"   Is semi-finished: {result['is_semi_finished']}")
        print(f"   Has BOM: {result['has_bom']}")
        
        # Step 6: Compare with expected
        print(f"\n6. COMPARISON:")
        if result['available_quantity'] == total_available:
            print(f"   ✅ Available quantity matches query result")
        else:
            print(f"   ❌ PHANTOM STOCK DETECTED!")
            print(f"      Expected: {total_available}")
            print(f"      Reported: {result['available_quantity']}")
            print(f"      Difference: {result['available_quantity'] - total_available}")
            
        return result
        
    finally:
        session.close()

def debug_all_warehouses_for_product(product_id: int):
    """Show all inventory across warehouses for a product."""
    print(f"\n{'='*60}")
    print(f"ALL WAREHOUSE INVENTORY FOR PRODUCT {product_id}")
    print(f"{'='*60}")
    
    session = SessionLocal()
    
    try:
        # Get all inventory items for this product
        all_items = session.query(InventoryItem).filter(
            InventoryItem.product_id == product_id
        ).order_by(InventoryItem.warehouse_id, InventoryItem.entry_date).all()
        
        print(f"Total inventory records: {len(all_items)}")
        
        by_warehouse = {}
        total_stock = Decimal('0')
        total_reserved = Decimal('0')
        total_available = Decimal('0')
        
        for item in all_items:
            wh_id = item.warehouse_id
            if wh_id not in by_warehouse:
                warehouse = session.query(Warehouse).get(wh_id)
                by_warehouse[wh_id] = {
                    'warehouse_name': warehouse.warehouse_name if warehouse else 'Unknown',
                    'warehouse_type': warehouse.warehouse_type if warehouse else 'Unknown',
                    'items': []
                }
            
            available = item.available_quantity
            by_warehouse[wh_id]['items'].append({
                'stock': item.quantity_in_stock,
                'reserved': item.reserved_quantity,
                'available': available,
                'quality': item.quality_status,
                'cost': item.unit_cost,
                'entry_date': item.entry_date
            })
            
            total_stock += item.quantity_in_stock
            total_reserved += item.reserved_quantity
            if item.quality_status == 'APPROVED':
                total_available += available
        
        for wh_id, data in by_warehouse.items():
            print(f"\n   WAREHOUSE {wh_id}: {data['warehouse_name']} ({data['warehouse_type']})")
            wh_stock = sum(i['stock'] for i in data['items'])
            wh_reserved = sum(i['reserved'] for i in data['items'])
            wh_available = sum(i['available'] for i in data['items'] if i['quality'] == 'APPROVED')
            
            print(f"      Total: Stock={wh_stock}, Reserved={wh_reserved}, Available={wh_available}")
            
            for item in data['items']:
                print(f"      - Stock={item['stock']}, Reserved={item['reserved']}, Available={item['available']}, Quality={item['quality']}, Entry={item['entry_date']}")
        
        print(f"\n   OVERALL TOTALS:")
        print(f"      Total Stock: {total_stock}")
        print(f"      Total Reserved: {total_reserved}")  
        print(f"      Total Available (APPROVED only): {total_available}")
        
    finally:
        session.close()

def main():
    """Main debug function."""
    print("MRP PHANTOM STOCK DEBUGGER")
    print("="*40)
    
    # Test the specific products from the production order
    product_ids = [201, 401]  # Steel Frame (Semi-finished) and Cardboard Box (Packaging)
    required_quantities = [Decimal('4.0'), Decimal('2.0')]  # From production order analysis
    
    for product_id, required_qty in zip(product_ids, required_quantities):
        debug_all_warehouses_for_product(product_id)
        debug_component_availability(product_id, required_qty)
    
    print(f"\n{'='*60}")
    print("DEBUGGING COMPLETE")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()