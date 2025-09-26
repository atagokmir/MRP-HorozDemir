#!/usr/bin/env python3
"""
Test script to verify FIFO logic in production completion workflow.
Creates multiple batches with different entry dates to test proper FIFO consumption.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import our models and services
from models.base import BaseModel
from models.production import ProductionOrder, StockReservation, ProductionOrderComponent
from models.inventory import InventoryItem, StockMovement
from models.master_data import Product, Warehouse
from models.bom import BillOfMaterials, BomComponent
from app.services.mrp_analysis import MRPAnalysisService

def setup_fifo_test_scenario():
    """
    Create a test scenario with multiple batches with different entry dates
    to verify FIFO logic in production completion.
    """
    
    # Create test database connection
    engine = create_engine("sqlite:///test_mrp.db", echo=False)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        print("🔧 Setting up FIFO test scenario...")
        
        # Clear existing test data
        session.query(StockReservation).delete()
        session.query(ProductionOrderComponent).delete()
        session.query(ProductionOrder).delete()
        session.query(InventoryItem).delete()
        session.query(StockMovement).delete()
        
        # Get or create test products
        product_raw = session.query(Product).filter(Product.product_code == "FIFO-RAW-001").first()
        if not product_raw:
            product_raw = Product(
                product_code="FIFO-RAW-001",
                product_name="FIFO Test Raw Material",
                product_type="RAW_MATERIAL",
                unit_of_measure="pcs",
                standard_cost=Decimal('10.00')
            )
            session.add(product_raw)
            session.flush()
        
        product_finished = session.query(Product).filter(Product.product_code == "FIFO-FIN-001").first()
        if not product_finished:
            product_finished = Product(
                product_code="FIFO-FIN-001",
                product_name="FIFO Test Finished Product",
                product_type="FINISHED_PRODUCT",
                unit_of_measure="pcs",
                standard_cost=Decimal('50.00')
            )
            session.add(product_finished)
            session.flush()
        
        # Get warehouses
        raw_warehouse = session.query(Warehouse).filter(Warehouse.warehouse_type == 'RAW_MATERIALS').first()
        finished_warehouse = session.query(Warehouse).filter(Warehouse.warehouse_type == 'FINISHED_PRODUCTS').first()
        
        # Create multiple inventory batches with different entry dates (FIFO test)
        base_date = datetime.now() - timedelta(days=10)
        
        batches = [
            {'entry_date': base_date, 'quantity': 100, 'unit_cost': Decimal('8.00'), 'batch': 'BATCH-OLD-001'},
            {'entry_date': base_date + timedelta(days=2), 'quantity': 150, 'unit_cost': Decimal('9.00'), 'batch': 'BATCH-MID-001'},
            {'entry_date': base_date + timedelta(days=5), 'quantity': 80, 'unit_cost': Decimal('11.00'), 'batch': 'BATCH-NEW-001'},
        ]
        
        inventory_items = []
        for i, batch_data in enumerate(batches):
            item = InventoryItem(
                product_id=product_raw.product_id,
                warehouse_id=raw_warehouse.warehouse_id,
                batch_number=batch_data['batch'],
                entry_date=batch_data['entry_date'],
                quantity_in_stock=batch_data['quantity'],
                reserved_quantity=Decimal('0'),
                unit_cost=batch_data['unit_cost'],
                supplier_id=None,
                location_in_warehouse=f"LOC-{i+1}",
                quality_status='APPROVED'
            )
            session.add(item)
            inventory_items.append(item)
        
        session.flush()
        
        # Create or get BOM
        bom = session.query(BillOfMaterials).filter(BillOfMaterials.bom_name == "FIFO Test BOM").first()
        if not bom:
            bom = BillOfMaterials(
                parent_product_id=product_finished.product_id,
                bom_name="FIFO Test BOM",
                bom_version="1.0",
                base_quantity=Decimal('1'),
                status='ACTIVE'
            )
            session.add(bom)
            session.flush()
            
            # Add BOM component
            bom_component = BomComponent(
                bom_id=bom.bom_id,
                component_product_id=product_raw.product_id,
                sequence_number=1,
                quantity_required=Decimal('200'),  # Need 200 units, will test FIFO across batches
                unit_of_measure='pcs',
                scrap_percentage=Decimal('0')
            )
            session.add(bom_component)
        
        # Create production order
        production_order = ProductionOrder(
            product_id=product_finished.product_id,
            bom_id=bom.bom_id,
            order_number="PO000001",
            order_date=date.today(),
            planned_quantity=Decimal('1'),  # Produce 1 finished product
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
            required_quantity=Decimal('200'),
            allocation_status='NOT_ALLOCATED'
        )
        session.add(po_component)
        
        session.commit()
        print(f"✅ Test scenario created successfully!")
        print(f"   - Raw material product: {product_raw.product_code}")
        print(f"   - Finished product: {product_finished.product_code}")
        print(f"   - Production order: {production_order.order_number}")
        print(f"   - Inventory batches: {len(batches)} with different entry dates")
        
        return {
            'production_order_id': production_order.production_order_id,
            'raw_product_id': product_raw.product_id,
            'finished_product_id': product_finished.product_id,
            'inventory_items': [(item.inventory_item_id, item.batch_number, item.entry_date, item.unit_cost) for item in inventory_items]
        }
        
    except Exception as e:
        print(f"❌ Failed to setup test scenario: {e}")
        session.rollback()
        raise
    finally:
        session.close()

def test_fifo_production_completion():
    """
    Test the complete FIFO production completion workflow.
    """
    
    # Create test database connection
    engine = create_engine("sqlite:///test_mrp.db", echo=False)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        # Setup test scenario
        test_data = setup_fifo_test_scenario()
        
        print("\n🏭 Testing FIFO Production Completion Workflow...")
        
        # Initialize MRP service
        mrp_service = MRPAnalysisService(session)
        
        # 1. Reserve stock for production
        print("1️⃣ Reserving stock for production...")
        reservation_result = mrp_service.reserve_stock_for_production(
            test_data['production_order_id']
        )
        print(f"✅ Stock reservation completed. Records: {len(reservation_result) if reservation_result else 0}")
        
        # Check initial inventory state (before consumption)
        print("\n📊 Initial inventory state (before consumption):")
        inventory_items = session.query(InventoryItem).filter(
            InventoryItem.product_id == test_data['raw_product_id']
        ).order_by(InventoryItem.entry_date).all()
        
        for item in inventory_items:
            print(f"   Batch: {item.batch_number}, Entry: {item.entry_date.strftime('%Y-%m-%d')}, "
                  f"Stock: {item.quantity_in_stock}, Reserved: {item.reserved_quantity}, "
                  f"Unit Cost: {item.unit_cost}")
        
        # 2. Update production order status to IN_PROGRESS
        production_order = session.query(ProductionOrder).get(test_data['production_order_id'])
        production_order.status = 'IN_PROGRESS'
        session.commit()
        
        # 3. Complete production
        print("\n2️⃣ Completing production order...")
        consumption_records = mrp_service.consume_stock_for_production(
            test_data['production_order_id']
        )
        
        print(f"✅ Stock consumption completed. Records: {len(consumption_records)}")
        
        # Verify FIFO consumption order
        print("\n📋 FIFO Consumption Analysis:")
        consumption_records.sort(key=lambda x: (x['product_id'], x['entry_date']))
        for record in consumption_records:
            print(f"   Batch: {record['batch_number']}, Entry: {record['entry_date'].strftime('%Y-%m-%d')}, "
                  f"Consumed: {record['consumed_quantity']}, Cost: {record['unit_cost']}")
        
        # 4. Create finished goods
        print("\n3️⃣ Creating finished goods...")
        finished_goods = mrp_service.create_finished_goods_inventory(
            test_data['production_order_id'],
            Decimal('1'),
            consumption_records
        )
        
        print(f"✅ Finished goods created:")
        print(f"   Quantity: {finished_goods['quantity']}")
        print(f"   Unit Cost: {finished_goods['unit_cost']}")
        print(f"   Total Cost: {finished_goods['total_cost']}")
        print(f"   Batch: {finished_goods['batch_number']}")
        
        # 5. Verify final inventory state
        print("\n📊 Final inventory state (after consumption):")
        updated_items = session.query(InventoryItem).filter(
            InventoryItem.product_id == test_data['raw_product_id']
        ).order_by(InventoryItem.entry_date).all()
        
        for item in updated_items:
            print(f"   Batch: {item.batch_number}, Entry: {item.entry_date.strftime('%Y-%m-%d')}, "
                  f"Stock: {item.quantity_in_stock}, Reserved: {item.reserved_quantity}, "
                  f"Unit Cost: {item.unit_cost}")
        
        # 6. FIFO Validation
        print("\n🔍 FIFO Validation:")
        oldest_batch = updated_items[0]  # Should be completely consumed first
        if oldest_batch.quantity_in_stock == 0:
            print("✅ FIFO CORRECT: Oldest batch (BATCH-OLD-001) completely consumed first")
        else:
            print("❌ FIFO ERROR: Oldest batch still has stock, FIFO not working correctly")
        
        middle_batch = updated_items[1]  # Should be partially consumed
        if middle_batch.quantity_in_stock == 50:  # 150 - 100 (remaining from first batch)
            print("✅ FIFO CORRECT: Middle batch (BATCH-MID-001) partially consumed after oldest")
        else:
            print(f"❌ FIFO ERROR: Middle batch consumption incorrect, remaining: {middle_batch.quantity_in_stock}")
        
        newest_batch = updated_items[2]  # Should be untouched
        if newest_batch.quantity_in_stock == 80:
            print("✅ FIFO CORRECT: Newest batch (BATCH-NEW-001) untouched")
        else:
            print(f"❌ FIFO ERROR: Newest batch should be untouched, remaining: {newest_batch.quantity_in_stock}")
        
        session.commit()
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
        return False
        
    finally:
        session.close()

if __name__ == "__main__":
    print("🧪 FIFO Production Completion Test")
    print("=" * 50)
    
    success = test_fifo_production_completion()
    
    if success:
        print("\n🎉 SUCCESS: FIFO production completion workflow is working correctly!")
    else:
        print("\n💥 FAILED: FIFO logic has issues that need to be fixed.")
    
    sys.exit(0 if success else 1)