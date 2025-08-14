#!/usr/bin/env python3
"""
FIFO Functionality Test Script for Horoz Demir MRP System.
This script tests the FIFO (First-In-First-Out) inventory allocation and consumption logic.
"""

import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent.parent / 'backend'
sys.path.insert(0, str(backend_dir))

from database import database_session, check_database_connection
from models import (
    InventoryItem, Product, Warehouse, ProductionOrder, 
    ProductionOrderComponent, StockAllocation, StockMovement
)

def test_fifo_inventory_allocation():
    """Test FIFO inventory allocation logic."""
    print("=" * 60)
    print("TESTING FIFO INVENTORY ALLOCATION")
    print("=" * 60)
    
    with database_session('TEST_USER') as session:
        # Get steel product and raw materials warehouse
        steel_product = session.query(Product).filter(
            Product.product_code == 'RM-STEEL-001'
        ).first()
        
        rm_warehouse = session.query(Warehouse).filter(
            Warehouse.warehouse_code == 'RM01'
        ).first()
        
        if not steel_product or not rm_warehouse:
            print("❌ Required test data not found")
            return False
        
        print(f"Testing FIFO allocation for: {steel_product.product_name}")
        print(f"Warehouse: {rm_warehouse.warehouse_name}")
        
        # Get all inventory items ordered by FIFO (entry_date)
        inventory_items = session.query(InventoryItem).filter(
            InventoryItem.product_id == steel_product.product_id,
            InventoryItem.warehouse_id == rm_warehouse.warehouse_id,
            InventoryItem.quality_status == 'APPROVED',
            InventoryItem.available_quantity > 0
        ).order_by(
            InventoryItem.entry_date, 
            InventoryItem.inventory_item_id
        ).all()
        
        print(f"\nAvailable inventory batches (FIFO order):")
        print("-" * 80)
        total_available = Decimal('0')
        
        for i, item in enumerate(inventory_items, 1):
            print(f"{i}. Batch: {item.batch_number}")
            print(f"   Entry Date: {item.entry_date}")
            print(f"   Available: {item.available_quantity} @ ${item.unit_cost}/unit")
            print(f"   Total Value: ${item.available_quantity * item.unit_cost}")
            total_available += item.available_quantity
            print()
        
        print(f"Total Available: {total_available} units")
        
        # Simulate FIFO allocation for 800 units (should consume from multiple batches)
        allocation_quantity = Decimal('800')
        print(f"\n🧪 TESTING: Allocate {allocation_quantity} units using FIFO logic")
        print("-" * 80)
        
        remaining_to_allocate = allocation_quantity
        fifo_allocations = []
        total_fifo_cost = Decimal('0')
        
        for item in inventory_items:
            if remaining_to_allocate <= 0:
                break
            
            # Calculate how much to allocate from this batch
            allocate_from_batch = min(remaining_to_allocate, item.available_quantity)
            batch_cost = allocate_from_batch * item.unit_cost
            
            fifo_allocations.append({
                'batch': item.batch_number,
                'entry_date': item.entry_date,
                'quantity': allocate_from_batch,
                'unit_cost': item.unit_cost,
                'batch_cost': batch_cost,
                'remaining_in_batch': item.available_quantity - allocate_from_batch
            })
            
            total_fifo_cost += batch_cost
            remaining_to_allocate -= allocate_from_batch
            
            print(f"✅ Allocate {allocate_from_batch} from {item.batch_number}")
            print(f"   @ ${item.unit_cost}/unit = ${batch_cost}")
            print(f"   Remaining in batch: {item.available_quantity - allocate_from_batch}")
            print(f"   Still need: {remaining_to_allocate}")
            print()
        
        if remaining_to_allocate > 0:
            print(f"❌ INSUFFICIENT INVENTORY: Short by {remaining_to_allocate} units")
            return False
        
        average_fifo_cost = total_fifo_cost / allocation_quantity
        print(f"✅ FIFO ALLOCATION SUCCESSFUL")
        print(f"Total Cost: ${total_fifo_cost}")
        print(f"Average Cost per Unit: ${average_fifo_cost}")
        print(f"Used {len(fifo_allocations)} different batches")
        
        # Verify FIFO order (older batches should be consumed first)
        print(f"\n🔍 VERIFYING FIFO ORDER:")
        print("-" * 40)
        
        dates_in_order = True
        prev_date = None
        
        for allocation in fifo_allocations:
            if prev_date is not None and allocation['entry_date'] < prev_date:
                dates_in_order = False
                print(f"❌ FIFO ORDER VIOLATION: {allocation['entry_date']} < {prev_date}")
            
            print(f"✅ {allocation['batch']}: {allocation['entry_date']} - {allocation['quantity']} units")
            prev_date = allocation['entry_date']
        
        if dates_in_order:
            print("✅ FIFO order is correct - older inventory consumed first!")
        
        return dates_in_order


def test_production_order_fifo_allocation():
    """Test FIFO allocation in context of production orders."""
    print("\n" + "=" * 60)
    print("TESTING PRODUCTION ORDER FIFO ALLOCATION")
    print("=" * 60)
    
    with database_session('TEST_USER') as session:
        # Find a production order that needs steel
        production_order = session.query(ProductionOrder).filter(
            ProductionOrder.order_number == 'PO000001'
        ).first()
        
        if not production_order:
            print("❌ Test production order not found")
            return False
        
        print(f"Production Order: {production_order.order_number}")
        print(f"Product: {production_order.product.product_name}")
        print(f"Planned Quantity: {production_order.planned_quantity}")
        print(f"Status: {production_order.status}")
        
        # Get steel component requirement
        steel_component = session.query(ProductionOrderComponent).filter(
            ProductionOrderComponent.production_order_id == production_order.production_order_id,
            ProductionOrderComponent.component_product_id == (
                session.query(Product.product_id).filter(
                    Product.product_code == 'RM-STEEL-001'
                ).scalar()
            )
        ).first()
        
        if not steel_component:
            print("❌ Steel component requirement not found")
            return False
        
        print(f"\n📋 COMPONENT REQUIREMENT:")
        print(f"Component: {steel_component.component_product.product_name}")
        print(f"Required: {steel_component.required_quantity} units")
        print(f"Current Allocation: {steel_component.allocated_quantity} units")
        print(f"Allocation Status: {steel_component.allocation_status}")
        
        # Simulate stock allocation using FIFO
        print(f"\n🔄 SIMULATING FIFO STOCK ALLOCATION:")
        print("-" * 50)
        
        # Get available inventory in FIFO order
        available_inventory = session.query(InventoryItem).filter(
            InventoryItem.product_id == steel_component.component_product_id,
            InventoryItem.quality_status == 'APPROVED',
            InventoryItem.available_quantity > 0
        ).order_by(
            InventoryItem.entry_date,
            InventoryItem.inventory_item_id
        ).all()
        
        remaining_need = steel_component.required_quantity - steel_component.allocated_quantity
        print(f"Need to allocate: {remaining_need} units")
        
        simulated_allocations = []
        total_allocated = Decimal('0')
        
        for inventory_item in available_inventory:
            if remaining_need <= 0:
                break
            
            # Calculate allocation from this batch
            allocate_qty = min(remaining_need, inventory_item.available_quantity)
            
            simulated_allocations.append({
                'inventory_item_id': inventory_item.inventory_item_id,
                'batch': inventory_item.batch_number,
                'entry_date': inventory_item.entry_date,
                'allocated_quantity': allocate_qty,
                'unit_cost': inventory_item.unit_cost
            })
            
            total_allocated += allocate_qty
            remaining_need -= allocate_qty
            
            print(f"✅ Would allocate {allocate_qty} from batch {inventory_item.batch_number}")
            print(f"   Entry date: {inventory_item.entry_date}")
            print(f"   Cost: ${inventory_item.unit_cost}/unit")
            print(f"   Remaining need: {remaining_need}")
            print()
        
        if remaining_need > 0:
            print(f"❌ INSUFFICIENT STOCK: Short by {remaining_need} units")
            return False
        
        print(f"✅ ALLOCATION SIMULATION SUCCESSFUL")
        print(f"Total allocated: {total_allocated} units from {len(simulated_allocations)} batches")
        
        # Verify FIFO order in allocations
        fifo_correct = True
        prev_date = None
        
        for allocation in simulated_allocations:
            if prev_date and allocation['entry_date'] < prev_date:
                fifo_correct = False
                print(f"❌ FIFO violation: {allocation['entry_date']} < {prev_date}")
            prev_date = allocation['entry_date']
        
        if fifo_correct:
            print("✅ Simulated allocations follow FIFO order correctly!")
        
        return fifo_correct


def test_fifo_cost_calculation():
    """Test FIFO cost calculation accuracy."""
    print("\n" + "=" * 60)
    print("TESTING FIFO COST CALCULATION")
    print("=" * 60)
    
    with database_session('TEST_USER') as session:
        # Get aluminum inventory for cost calculation test
        aluminum_product = session.query(Product).filter(
            Product.product_code == 'RM-ALUM-001'
        ).first()
        
        if not aluminum_product:
            print("❌ Aluminum product not found")
            return False
        
        print(f"Testing FIFO cost calculation for: {aluminum_product.product_name}")
        
        # Get inventory batches in FIFO order
        batches = session.query(InventoryItem).filter(
            InventoryItem.product_id == aluminum_product.product_id,
            InventoryItem.quality_status == 'APPROVED',
            InventoryItem.available_quantity > 0
        ).order_by(
            InventoryItem.entry_date,
            InventoryItem.inventory_item_id
        ).all()
        
        if not batches:
            print("❌ No aluminum inventory found")
            return False
        
        print(f"\nAvailable batches:")
        for batch in batches:
            print(f"- {batch.batch_number}: {batch.available_quantity} @ ${batch.unit_cost}")
        
        # Test different consumption quantities
        test_quantities = [Decimal('150'), Decimal('350'), Decimal('600'), Decimal('1000')]
        
        for test_qty in test_quantities:
            print(f"\n🧪 TESTING: Cost for consuming {test_qty} units")
            print("-" * 40)
            
            remaining_qty = test_qty
            total_cost = Decimal('0')
            batches_used = 0
            
            for batch in batches:
                if remaining_qty <= 0:
                    break
                
                consume_from_batch = min(remaining_qty, batch.available_quantity)
                batch_cost = consume_from_batch * batch.unit_cost
                total_cost += batch_cost
                batches_used += 1
                
                print(f"  Use {consume_from_batch} from {batch.batch_number} @ ${batch.unit_cost} = ${batch_cost}")
                remaining_qty -= consume_from_batch
            
            if remaining_qty > 0:
                print(f"  ❌ Insufficient inventory - short by {remaining_qty}")
                continue
            
            average_cost = total_cost / test_qty
            print(f"  ✅ Total cost: ${total_cost}")
            print(f"  ✅ Average cost: ${average_cost}/unit")
            print(f"  ✅ Used {batches_used} batches")
            
            # Compare with simple average cost
            simple_avg_cost = sum(b.unit_cost for b in batches) / len(batches)
            simple_total = test_qty * simple_avg_cost
            
            print(f"  📊 vs Simple Average: ${simple_avg_cost}/unit = ${simple_total} total")
            cost_difference = total_cost - simple_total
            print(f"  📊 FIFO Difference: ${cost_difference} ({'higher' if cost_difference > 0 else 'lower'})")
        
        return True


def run_all_fifo_tests():
    """Run all FIFO functionality tests."""
    print("🧪 STARTING FIFO FUNCTIONALITY TESTS")
    print("=" * 80)
    
    # Check database connection first
    if not check_database_connection():
        print("❌ Database connection failed")
        return False
    
    print("✅ Database connection successful")
    
    # Run individual tests
    tests = [
        ("FIFO Inventory Allocation", test_fifo_inventory_allocation),
        ("Production Order FIFO Allocation", test_production_order_fifo_allocation),
        ("FIFO Cost Calculation", test_fifo_cost_calculation),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🏃 Running: {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
            
            if result:
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
                
        except Exception as e:
            print(f"💥 {test_name}: ERROR - {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 80)
    print("FIFO TEST RESULTS SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    print("-" * 80)
    print(f"OVERALL: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL FIFO TESTS PASSED!")
        return True
    else:
        print("⚠️  SOME FIFO TESTS FAILED")
        return False


if __name__ == '__main__':
    success = run_all_fifo_tests()
    sys.exit(0 if success else 1)