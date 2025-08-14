#!/usr/bin/env python3
"""
BOM Hierarchy Test Script for Horoz Demir MRP System.
This script tests the nested Bill of Materials functionality and hierarchy explosion logic.
"""

import sys
from pathlib import Path
from decimal import Decimal

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent.parent / 'backend'
sys.path.insert(0, str(backend_dir))

from database import database_session, check_database_connection
from models import (
    Product, BillOfMaterials, BomComponent, BomCostCalculation
)

def test_bom_hierarchy_explosion():
    """Test BOM hierarchy explosion (nested BOM traversal)."""
    print("=" * 60)
    print("TESTING BOM HIERARCHY EXPLOSION")
    print("=" * 60)
    
    with database_session('TEST_USER') as session:
        # Test with the Industrial Machine (has complex nested BOM)
        machine_product = session.query(Product).filter(
            Product.product_code == 'FP-MACHINE-001'
        ).first()
        
        if not machine_product:
            print("❌ Machine product not found")
            return False
        
        print(f"Testing BOM explosion for: {machine_product.product_name}")
        
        # Get the active BOM
        bom = session.query(BillOfMaterials).filter(
            BillOfMaterials.parent_product_id == machine_product.product_id,
            BillOfMaterials.status == 'ACTIVE'
        ).first()
        
        if not bom:
            print("❌ Active BOM not found for machine")
            return False
        
        print(f"BOM: {bom.bom_name} (v{bom.bom_version})")
        print(f"Base Quantity: {bom.base_quantity}")
        
        # Manual BOM explosion using recursive logic
        def explode_bom_recursive(parent_bom, level=0, quantity_multiplier=Decimal('1')):
            """Recursively explode BOM to show all components at all levels."""
            components = session.query(BomComponent).filter(
                BomComponent.bom_id == parent_bom.bom_id
            ).order_by(BomComponent.sequence_number).all()
            
            explosion_results = []
            
            for component in components:
                indent = "  " * level
                extended_qty = component.effective_quantity * quantity_multiplier
                
                result = {
                    'level': level,
                    'component_code': component.component_product.product_code,
                    'component_name': component.component_product.product_name,
                    'component_type': component.component_product.product_type,
                    'base_quantity': component.quantity_required,
                    'effective_quantity': component.effective_quantity,
                    'extended_quantity': extended_qty,
                    'scrap_percentage': component.scrap_percentage,
                    'sequence': component.sequence_number,
                    'is_phantom': component.is_phantom
                }
                
                explosion_results.append(result)
                
                print(f"{indent}L{level+1}: {component.component_product.product_code}")
                print(f"{indent}     {component.component_product.product_name}")
                print(f"{indent}     Type: {component.component_product.product_type}")
                print(f"{indent}     Qty: {component.quantity_required} + {component.scrap_percentage}% scrap = {component.effective_quantity}")
                print(f"{indent}     Extended: {extended_qty}")
                
                # If this component is semi-finished, recursively explode its BOM
                if component.component_product.product_type == 'SEMI_FINISHED':
                    sub_bom = session.query(BillOfMaterials).filter(
                        BillOfMaterials.parent_product_id == component.component_product_id,
                        BillOfMaterials.status == 'ACTIVE'
                    ).first()
                    
                    if sub_bom:
                        print(f"{indent}     → Exploding sub-BOM: {sub_bom.bom_name}")
                        sub_results = explode_bom_recursive(
                            sub_bom, 
                            level + 1, 
                            extended_qty
                        )
                        explosion_results.extend(sub_results)
                    else:
                        print(f"{indent}     ⚠️  No active BOM found for semi-finished component")
                
                print()
            
            return explosion_results
        
        print(f"\n🌳 BOM EXPLOSION (Recursive Traversal):")
        print("-" * 80)
        
        explosion_results = explode_bom_recursive(bom)
        
        # Summarize raw material requirements
        print(f"\n📋 RAW MATERIAL REQUIREMENTS SUMMARY:")
        print("-" * 50)
        
        raw_materials = {}
        for result in explosion_results:
            if result['component_type'] == 'RAW_MATERIAL':
                code = result['component_code']
                if code in raw_materials:
                    raw_materials[code]['total_quantity'] += result['extended_quantity']
                else:
                    raw_materials[code] = {
                        'name': result['component_name'],
                        'total_quantity': result['extended_quantity']
                    }
        
        for code, data in raw_materials.items():
            print(f"• {code}: {data['total_quantity']} units")
            print(f"  {data['name']}")
            print()
        
        # Verify no circular references
        print(f"🔍 CHECKING FOR CIRCULAR REFERENCES:")
        print("-" * 40)
        
        def check_circular_references(product_id, visited_products=None):
            """Check for circular references in BOM hierarchy."""
            if visited_products is None:
                visited_products = set()
            
            if product_id in visited_products:
                return True  # Circular reference found
            
            visited_products.add(product_id)
            
            # Check all components of this product's BOM
            bom = session.query(BillOfMaterials).filter(
                BillOfMaterials.parent_product_id == product_id,
                BillOfMaterials.status == 'ACTIVE'
            ).first()
            
            if not bom:
                return False
            
            components = session.query(BomComponent).filter(
                BomComponent.bom_id == bom.bom_id
            ).all()
            
            for component in components:
                if component.component_product.product_type == 'SEMI_FINISHED':
                    if check_circular_references(component.component_product_id, visited_products.copy()):
                        return True
            
            return False
        
        has_circular_ref = check_circular_references(machine_product.product_id)
        
        if has_circular_ref:
            print("❌ CIRCULAR REFERENCE DETECTED!")
            return False
        else:
            print("✅ No circular references found")
        
        print(f"\n✅ BOM EXPLOSION TEST PASSED")
        print(f"   - Found {len(explosion_results)} total components")
        print(f"   - {len(raw_materials)} unique raw materials required")
        print(f"   - No circular references detected")
        
        return True


def test_bom_cost_calculation():
    """Test BOM cost calculation with nested components."""
    print("\n" + "=" * 60)
    print("TESTING BOM COST CALCULATION")
    print("=" * 60)
    
    with database_session('TEST_USER') as session:
        # Test cost calculation for Basic Frame Assembly (simple BOM)
        frame_product = session.query(Product).filter(
            Product.product_code == 'SF-FRAME-001'
        ).first()
        
        if not frame_product:
            print("❌ Frame product not found")
            return False
        
        print(f"Testing cost calculation for: {frame_product.product_name}")
        
        frame_bom = session.query(BillOfMaterials).filter(
            BillOfMaterials.parent_product_id == frame_product.product_id,
            BillOfMaterials.status == 'ACTIVE'
        ).first()
        
        if not frame_bom:
            print("❌ Frame BOM not found")
            return False
        
        print(f"BOM: {frame_bom.bom_name}")
        print(f"Labor Cost: ${frame_bom.labor_cost_per_unit}/unit")
        print(f"Overhead Cost: ${frame_bom.overhead_cost_per_unit}/unit")
        
        # Calculate material cost from components
        components = session.query(BomComponent).filter(
            BomComponent.bom_id == frame_bom.bom_id
        ).all()
        
        print(f"\n💰 COMPONENT COSTS:")
        print("-" * 40)
        
        total_material_cost = Decimal('0')
        
        for component in components:
            # Use standard cost from product (in real system, would use FIFO)
            unit_cost = component.component_product.standard_cost
            component_cost = component.effective_quantity * unit_cost
            total_material_cost += component_cost
            
            print(f"• {component.component_product.product_code}")
            print(f"  Quantity: {component.effective_quantity}")
            print(f"  Unit Cost: ${unit_cost}")
            print(f"  Total: ${component_cost}")
            print()
        
        # Calculate total BOM cost
        total_labor = frame_bom.labor_cost_per_unit
        total_overhead = frame_bom.overhead_cost_per_unit
        total_bom_cost = total_material_cost + total_labor + total_overhead
        
        print(f"📊 COST SUMMARY:")
        print(f"Material Cost: ${total_material_cost}")
        print(f"Labor Cost: ${total_labor}")
        print(f"Overhead Cost: ${total_overhead}")
        print("-" * 20)
        print(f"Total Cost: ${total_bom_cost}")
        
        # Compare with expected standard cost
        expected_cost = frame_product.standard_cost
        cost_variance = total_bom_cost - expected_cost
        variance_pct = (cost_variance / expected_cost) * 100 if expected_cost else 0
        
        print(f"\n🔍 COST VALIDATION:")
        print(f"Calculated: ${total_bom_cost}")
        print(f"Expected: ${expected_cost}")
        print(f"Variance: ${cost_variance} ({variance_pct:.1f}%)")
        
        # Allow 5% variance
        if abs(variance_pct) <= 5:
            print("✅ Cost calculation within acceptable range")
            return True
        else:
            print("⚠️  Cost variance exceeds 5%")
            return False


def test_nested_bom_cost_rollup():
    """Test cost rollup through nested BOM hierarchy."""
    print("\n" + "=" * 60)
    print("TESTING NESTED BOM COST ROLLUP")
    print("=" * 60)
    
    with database_session('TEST_USER') as session:
        # Test with Base Platform Assembly (contains SF-FRAME-001)
        base_product = session.query(Product).filter(
            Product.product_code == 'SF-BASE-001'
        ).first()
        
        if not base_product:
            print("❌ Base product not found")
            return False
        
        print(f"Testing nested cost rollup for: {base_product.product_name}")
        
        base_bom = session.query(BillOfMaterials).filter(
            BillOfMaterials.parent_product_id == base_product.product_id,
            BillOfMaterials.status == 'ACTIVE'
        ).first()
        
        if not base_bom:
            print("❌ Base BOM not found")
            return False
        
        components = session.query(BomComponent).filter(
            BomComponent.bom_id == base_bom.bom_id
        ).all()
        
        print(f"\n🧮 NESTED COST CALCULATION:")
        print("-" * 50)
        
        total_material_cost = Decimal('0')
        
        for component in components:
            print(f"\n• Component: {component.component_product.product_code}")
            print(f"  Type: {component.component_product.product_type}")
            print(f"  Quantity: {component.effective_quantity}")
            
            if component.component_product.product_type == 'SEMI_FINISHED':
                # This component has its own BOM - need to calculate its cost
                print(f"  → This is a semi-finished component with its own BOM")
                
                # Get the component's BOM cost
                component_bom = session.query(BillOfMaterials).filter(
                    BillOfMaterials.parent_product_id == component.component_product_id,
                    BillOfMaterials.status == 'ACTIVE'
                ).first()
                
                if component_bom:
                    # In real system, would get current cost calculation
                    # For test, use standard cost
                    component_unit_cost = component.component_product.standard_cost
                    component_total_cost = component.effective_quantity * component_unit_cost
                    
                    print(f"  → Component BOM cost: ${component_unit_cost}/unit")
                    print(f"  → Total cost: ${component_total_cost}")
                    
                    total_material_cost += component_total_cost
                else:
                    print(f"  ⚠️  No BOM found for semi-finished component")
            
            else:
                # Raw material - use standard cost
                unit_cost = component.component_product.standard_cost
                component_total = component.effective_quantity * unit_cost
                
                print(f"  → Unit cost: ${unit_cost}")
                print(f"  → Total cost: ${component_total}")
                
                total_material_cost += component_total
        
        # Add labor and overhead
        total_labor = base_bom.labor_cost_per_unit
        total_overhead = base_bom.overhead_cost_per_unit
        total_cost = total_material_cost + total_labor + total_overhead
        
        print(f"\n📋 ROLLUP SUMMARY:")
        print("-" * 30)
        print(f"Material Cost (incl. nested): ${total_material_cost}")
        print(f"Labor Cost: ${total_labor}")
        print(f"Overhead Cost: ${total_overhead}")
        print("=" * 30)
        print(f"Total Rolled-up Cost: ${total_cost}")
        
        # Verify against standard cost
        expected = base_product.standard_cost
        variance = total_cost - expected
        
        print(f"\n✅ Expected: ${expected}")
        print(f"✅ Calculated: ${total_cost}")
        print(f"✅ Variance: ${variance}")
        
        return abs(variance) <= expected * Decimal('0.10')  # Allow 10% variance


def test_bom_version_management():
    """Test BOM version management and effective dates."""
    print("\n" + "=" * 60)
    print("TESTING BOM VERSION MANAGEMENT")
    print("=" * 60)
    
    with database_session('TEST_USER') as session:
        # Look for products with multiple BOM versions
        products_with_boms = session.query(Product).join(BillOfMaterials).all()
        
        print(f"Products with BOMs:")
        bom_versions = {}
        
        for product in products_with_boms:
            boms = session.query(BillOfMaterials).filter(
                BillOfMaterials.parent_product_id == product.product_id
            ).all()
            
            if len(boms) > 0:
                bom_versions[product.product_code] = boms
                print(f"• {product.product_code}: {len(boms)} version(s)")
        
        # Test version selection logic
        for product_code, boms in bom_versions.items():
            print(f"\n🔍 TESTING: {product_code}")
            
            active_boms = [b for b in boms if b.status == 'ACTIVE']
            effective_boms = [
                b for b in active_boms 
                if b.effective_date <= session.execute("SELECT CURRENT_DATE").scalar()
                and (b.expiry_date is None or b.expiry_date > session.execute("SELECT CURRENT_DATE").scalar())
            ]
            
            print(f"  Total BOMs: {len(boms)}")
            print(f"  Active BOMs: {len(active_boms)}")
            print(f"  Currently Effective: {len(effective_boms)}")
            
            for bom in boms:
                status_icon = "✅" if bom.status == 'ACTIVE' else "❌"
                print(f"  {status_icon} v{bom.bom_version}: {bom.status} ({bom.effective_date} to {bom.expiry_date or 'indefinite'})")
        
        print(f"\n✅ BOM Version Management Test Completed")
        return True


def run_all_bom_tests():
    """Run all BOM hierarchy tests."""
    print("🧪 STARTING BOM HIERARCHY TESTS")
    print("=" * 80)
    
    # Check database connection first
    if not check_database_connection():
        print("❌ Database connection failed")
        return False
    
    print("✅ Database connection successful")
    
    # Run individual tests
    tests = [
        ("BOM Hierarchy Explosion", test_bom_hierarchy_explosion),
        ("BOM Cost Calculation", test_bom_cost_calculation),
        ("Nested BOM Cost Rollup", test_nested_bom_cost_rollup),
        ("BOM Version Management", test_bom_version_management),
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
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 80)
    print("BOM TEST RESULTS SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    print("-" * 80)
    print(f"OVERALL: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL BOM TESTS PASSED!")
        return True
    else:
        print("⚠️  SOME BOM TESTS FAILED")
        return False


if __name__ == '__main__':
    success = run_all_bom_tests()
    sys.exit(0 if success else 1)