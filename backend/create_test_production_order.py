#!/usr/bin/env python3
"""
Create a fresh production order with stock reservations for testing production completion.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import our models and services
from models.base import BaseModel
from models.production import ProductionOrder, ProductionOrderComponent
from models.inventory import InventoryItem, StockMovement
from models.master_data import Product, Warehouse
from models.bom import BillOfMaterials, BomComponent
from app.services.mrp_analysis import MRPAnalysisService

def create_fresh_production_order():
    """
    Create a fresh production order with stock reservations.
    """
    
    # Create test database connection
    engine = create_engine("sqlite:///test_mrp.db", echo=False)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        print("🔧 Creating fresh production order for testing...")
        
        # Use existing products and BOM from our test
        product_raw = session.query(Product).filter(Product.product_code == "FIFO-RAW-001").first()
        product_finished = session.query(Product).filter(Product.product_code == "FIFO-FIN-001").first()
        bom = session.query(BillOfMaterials).filter(BillOfMaterials.bom_name == "FIFO Test BOM").first()
        
        if not all([product_raw, product_finished, bom]):
            print("❌ Test products or BOM not found. Run the FIFO test first.")
            return False
            
        # Get warehouses
        finished_warehouse = session.query(Warehouse).filter(Warehouse.warehouse_type == 'FINISHED_PRODUCTS').first()
        
        # Create new production order with unique number
        from datetime import datetime
        timestamp = datetime.now().strftime("%H%M%S")
        order_number = f"PO{timestamp}"  # PO123456 based on time
        
        production_order = ProductionOrder(
            product_id=product_finished.product_id,
            bom_id=bom.bom_id,
            order_number=order_number,
            order_date=date.today(),
            planned_quantity=Decimal('0.05'),  # Produce 0.05 finished products (need 10 raw materials)
            warehouse_id=finished_warehouse.warehouse_id,
            status='PLANNED',
            priority=5
        )
        session.add(production_order)
        session.flush()
        
        # Create production order component
        po_component = ProductionOrderComponent(
            production_order_id=production_order.production_order_id,
            component_product_id=product_raw.product_id,
            required_quantity=Decimal('10'),  # Need 10 units (0.05 * 200 per BOM)
            allocation_status='NOT_ALLOCATED'
        )
        session.add(po_component)
        session.flush()
        
        print(f"✅ Created production order: {order_number} (ID: {production_order.production_order_id})")
        
        # Initialize MRP service and create reservations
        mrp_service = MRPAnalysisService(session)
        
        print("📦 Creating stock reservations...")
        reservations = mrp_service.reserve_stock_for_production(production_order.production_order_id)
        print(f"✅ Created {len(reservations) if reservations else 0} stock reservations")
        
        # Change status to IN_PROGRESS so it can be completed
        production_order.status = 'IN_PROGRESS'
        
        session.commit()
        
        print(f"🎯 Ready for testing!")
        print(f"   Order ID: {production_order.production_order_id}")
        print(f"   Order Number: {order_number}")
        print(f"   Status: {production_order.status}")
        print(f"   Planned Quantity: {production_order.planned_quantity}")
        print(f"   API Endpoint: POST /api/v1/production-orders/{production_order.production_order_id}/complete")
        print(f"   Example payload: {{'completed_quantity': 0.1, 'scrapped_quantity': 0, 'completion_notes': 'Test completion'}}")
        
        return {
            'order_id': production_order.production_order_id,
            'order_number': order_number,
            'status': production_order.status
        }
        
    except Exception as e:
        print(f"❌ Failed to create production order: {e}")
        session.rollback()
        return False
        
    finally:
        session.close()

if __name__ == "__main__":
    print("🏭 Creating Fresh Production Order for Testing")
    print("=" * 60)
    
    result = create_fresh_production_order()
    
    if result:
        print("\n🎉 SUCCESS: Fresh production order created and ready for completion testing!")
        print(f"\nNow try completing it via the frontend or API:")
        print(f"curl -X POST http://localhost:8000/api/v1/production-orders/{result['order_id']}/complete \\")
        print(f'  -H "Content-Type: application/json" \\')
        print(f"  -d '{{\"completed_quantity\": 0.1, \"scrapped_quantity\": 0, \"completion_notes\": \"Test completion\"}}'")
    else:
        print("\n💥 FAILED: Could not create fresh production order.")
    
    sys.exit(0 if result else 1)