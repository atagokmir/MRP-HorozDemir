#!/usr/bin/env python3
"""
Debug script to check warehouse lookup logic.
"""

import sys
import os
from decimal import Decimal
from datetime import date, datetime

# Add the backend path to sys.path so we can import modules
backend_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_path)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.base import Base
from models.master_data import Product, Warehouse
from models.inventory import InventoryItem
from models.bom import BillOfMaterials, BomComponent
from app.services.mrp_analysis import MRPAnalysisService

# Database setup
DATABASE_URL = "sqlite:///test_mrp.db"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def debug_warehouse_lookup():
    """Debug warehouse lookup logic."""
    session = Session()
    
    try:
        print("=== DEBUGGING WAREHOUSE LOOKUP LOGIC ===")
        
        # Check warehouses
        print("\n1. Available Warehouses:")
        warehouses = session.query(Warehouse).all()
        for wh in warehouses:
            print(f"  ID: {wh.warehouse_id}, Code: {wh.warehouse_code}, Type: {wh.warehouse_type}, Active: {wh.is_active}")
        
        # Check products
        print("\n2. Available Products:")
        products = session.query(Product).all()
        for prod in products:
            print(f"  ID: {prod.product_id}, Code: {prod.product_code}, Type: {prod.product_type}")
        
        # Check inventory items
        print("\n3. Available Inventory Items:")
        items = session.query(InventoryItem).all()
        for item in items:
            print(f"  Product ID: {item.product_id}, Warehouse ID: {item.warehouse_id}, Stock: {item.quantity_in_stock}")
        
        # Test warehouse lookup for each product type
        print("\n4. Testing Warehouse Lookup:")
        mrp_service = MRPAnalysisService(session)
        
        for prod in products:
            warehouse_id = mrp_service._get_source_warehouse_for_product(prod)
            print(f"  Product {prod.product_code} ({prod.product_type}) -> Warehouse ID: {warehouse_id}")
            
            # Check if this product has inventory in that warehouse
            if warehouse_id:
                inventory_count = session.query(InventoryItem).filter(
                    InventoryItem.product_id == prod.product_id,
                    InventoryItem.warehouse_id == warehouse_id
                ).count()
                print(f"    Has {inventory_count} inventory items in warehouse {warehouse_id}")
        
        # Test specific cases
        print("\n5. Testing Specific Analysis Cases:")
        
        # Steel Bar (Raw Material)
        print("\nSteel Bar Analysis:")
        steel_product = session.query(Product).filter(Product.product_id == 101).first()
        if steel_product:
            steel_warehouse = mrp_service._get_source_warehouse_for_product(steel_product)
            print(f"  Steel Bar should use warehouse: {steel_warehouse}")
            
            analysis = mrp_service._analyze_component_availability(101, Decimal("10"))
            print(f"  Analysis result: {analysis['available_quantity']}")
        
        # Steel Frame (Semi-Finished)
        print("\nSteel Frame Analysis:")
        frame_product = session.query(Product).filter(Product.product_id == 201).first()
        if frame_product:
            frame_warehouse = mrp_service._get_source_warehouse_for_product(frame_product)
            print(f"  Steel Frame should use warehouse: {frame_warehouse}")
            
            analysis = mrp_service._analyze_component_availability(201, Decimal("5"))
            print(f"  Analysis result: {analysis['available_quantity']}")
            
    finally:
        session.close()

if __name__ == "__main__":
    debug_warehouse_lookup()