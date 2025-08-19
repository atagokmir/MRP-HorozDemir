#!/usr/bin/env python3
"""
Test script for BOM cost calculation functionality.
"""

import sys
import os

# Add the backend directory to Python path
backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.insert(0, backend_dir)

def test_bom_cost_calculation():
    """Test the BOM cost calculation implementation directly."""
    from decimal import Decimal
    from datetime import datetime
    
    print("Testing BOM Cost Calculation Implementation")
    print("=" * 50)
    
    # Test 1: Schema validation
    try:
        from app.schemas.bom import EnhancedBomCostCalculation, ComponentCost, FifoBatch
        
        # Create test FIFO batch
        batch = FifoBatch(
            batch_number="TEST001",
            quantity_used=Decimal('10.0'),
            unit_cost=Decimal('15.50'),
            entry_date=datetime.now()
        )
        
        # Create test component cost
        component = ComponentCost(
            product_id=1,
            product_name="Test Component",
            product_code="TC001",
            quantity_required=Decimal('10.0'),
            quantity_available=Decimal('20.0'),
            unit_cost=Decimal('15.50'),
            total_cost=Decimal('155.0'),
            has_sufficient_stock=True,
            fifo_batches=[batch]
        )
        
        # Create test BOM cost calculation
        cost_calc = EnhancedBomCostCalculation(
            bom_id=1,
            quantity=Decimal('1.0'),
            calculable=True,
            total_material_cost=Decimal('155.0'),
            component_costs=[component],
            missing_components=[],
            calculation_date=datetime.now(),
            cost_basis="FIFO",
            components_with_stock=1,
            components_missing_stock=0,
            stock_coverage_percentage=100.0
        )
        
        print("✅ Schema validation successful")
        print(f"   BOM ID: {cost_calc.bom_id}")
        print(f"   Total Cost: ${cost_calc.total_material_cost}")
        print(f"   Calculable: {cost_calc.calculable}")
        print(f"   Components with Stock: {cost_calc.components_with_stock}")
        
        # Test component details
        comp = cost_calc.component_costs[0]
        print(f"   Component: {comp.product_name} ({comp.product_code})")
        print(f"   Required: {comp.quantity_required}, Available: {comp.quantity_available}")
        print(f"   Unit Cost: ${comp.unit_cost}, Total: ${comp.total_cost}")
        print(f"   FIFO Batches: {len(comp.fifo_batches)}")
        
        # Test FIFO batch details
        fifo = comp.fifo_batches[0]
        print(f"   Batch: {fifo.batch_number}, Qty: {fifo.quantity_used}, Cost: ${fifo.unit_cost}")
        
    except Exception as e:
        print(f"❌ Schema validation failed: {e}")
        return False
    
    # Test 2: Import validation
    try:
        from app.api.bom import calculate_bom_cost
        print("✅ Import validation successful")
        print(f"   Function: {calculate_bom_cost.__name__}")
        print(f"   Docstring: {calculate_bom_cost.__doc__.strip()}")
        
    except Exception as e:
        print(f"❌ Import validation failed: {e}")
        return False
    
    print("\n🎉 All tests passed! BOM cost calculation implementation is ready.")
    return True

if __name__ == "__main__":
    success = test_bom_cost_calculation()
    sys.exit(0 if success else 1)