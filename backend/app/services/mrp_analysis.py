"""
Advanced MRP Analysis Services for Horoz Demir MRP System.
Handles stock analysis, BOM explosion, and production planning logic.
"""

from typing import Dict, List, Optional, Set, Tuple
from decimal import Decimal
from datetime import datetime, date
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc

from models.production import ProductionOrder, ProductionOrderComponent, StockReservation, ProductionDependency
from models.bom import BillOfMaterials, BomComponent
from models.inventory import InventoryItem
from models.master_data import Product, Warehouse


@dataclass
class ComponentRequirement:
    """Represents a component requirement from BOM explosion."""
    product_id: int
    product_code: str
    product_name: str
    required_quantity: Decimal
    available_quantity: Decimal
    shortage_quantity: Decimal
    unit_cost: Decimal
    total_cost: Decimal
    is_semi_finished: bool
    has_bom: bool
    bom_id: Optional[int] = None


@dataclass
class StockAnalysisResult:
    """Result of stock availability analysis."""
    production_order_id: Optional[int]
    product_id: int
    product_code: str
    product_name: str
    planned_quantity: Decimal
    can_produce: bool
    shortage_exists: bool
    component_requirements: List[ComponentRequirement]
    semi_finished_shortages: List[ComponentRequirement]
    raw_material_shortages: List[ComponentRequirement]
    total_estimated_cost: Decimal
    analysis_date: datetime


@dataclass
class ProductionPlanNode:
    """Node in the production planning tree."""
    product_id: int
    product_code: str
    product_name: str
    required_quantity: Decimal
    bom_id: int
    warehouse_id: int
    priority: int
    dependencies: List['ProductionPlanNode']
    estimated_cost: Decimal


class MRPAnalysisService:
    """Advanced MRP analysis and planning service."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def analyze_stock_availability(
        self,
        product_id: int,
        bom_id: int,
        planned_quantity: Decimal,
        warehouse_id: int,
        production_order_id: Optional[int] = None
    ) -> StockAnalysisResult:
        """
        Perform comprehensive stock availability analysis with nested BOM explosion.
        
        Args:
            product_id: ID of product to produce
            bom_id: ID of BOM to use
            planned_quantity: Quantity to produce
            warehouse_id: Target warehouse ID
            production_order_id: Optional production order ID for existing orders
            
        Returns:
            StockAnalysisResult with detailed component analysis
        """
        # Get product and BOM information
        product = self.session.query(Product).get(product_id)
        bom = self.session.query(BillOfMaterials).get(bom_id)
        
        if not product or not bom:
            raise ValueError("Product or BOM not found")
        
        # Explode BOM to get all component requirements
        component_requirements = self._explode_bom_requirements(
            bom_id, planned_quantity, set()
        )
        
        # Analyze stock availability for each component
        analyzed_components = []
        semi_finished_shortages = []
        raw_material_shortages = []
        total_estimated_cost = Decimal('0')
        
        for req in component_requirements:
            component_analysis = self._analyze_component_availability(
                req.product_id, req.required_quantity
            )
            
            analyzed_component = ComponentRequirement(
                product_id=req.product_id,
                product_code=component_analysis['product_code'],
                product_name=component_analysis['product_name'],
                required_quantity=req.required_quantity,
                available_quantity=component_analysis['available_quantity'],
                shortage_quantity=max(Decimal('0'), 
                                    req.required_quantity - component_analysis['available_quantity']),
                unit_cost=component_analysis['unit_cost'],
                total_cost=component_analysis['unit_cost'] * req.required_quantity,
                is_semi_finished=component_analysis['is_semi_finished'],
                has_bom=component_analysis['has_bom'],
                bom_id=component_analysis.get('bom_id')
            )
            
            analyzed_components.append(analyzed_component)
            total_estimated_cost += analyzed_component.total_cost
            
            # Categorize shortages
            if analyzed_component.shortage_quantity > 0:
                if analyzed_component.is_semi_finished:
                    semi_finished_shortages.append(analyzed_component)
                else:
                    raw_material_shortages.append(analyzed_component)
        
        # Determine if production can proceed
        can_produce = len(semi_finished_shortages) == 0 and len(raw_material_shortages) == 0
        shortage_exists = len(semi_finished_shortages) > 0 or len(raw_material_shortages) > 0
        
        return StockAnalysisResult(
            production_order_id=production_order_id,
            product_id=product_id,
            product_code=product.product_code,
            product_name=product.product_name,
            planned_quantity=planned_quantity,
            can_produce=can_produce,
            shortage_exists=shortage_exists,
            component_requirements=analyzed_components,
            semi_finished_shortages=semi_finished_shortages,
            raw_material_shortages=raw_material_shortages,
            total_estimated_cost=total_estimated_cost,
            analysis_date=datetime.now()
        )
    
    def _explode_bom_requirements(
        self,
        bom_id: int,
        quantity: Decimal,
        visited_boms: Set[int]
    ) -> List[ComponentRequirement]:
        """
        Recursively explode BOM to get all component requirements.
        Handles nested semi-finished products and prevents infinite loops.
        """
        if bom_id in visited_boms:
            raise ValueError(f"Circular BOM reference detected for BOM {bom_id}")
        
        visited_boms.add(bom_id)
        requirements = []
        
        # Get BOM and its components
        bom = self.session.query(BillOfMaterials).get(bom_id)
        if not bom:
            return requirements
        
        bom_components = self.session.query(BomComponent).filter(
            BomComponent.bom_id == bom_id
        ).order_by(BomComponent.sequence_number).all()
        
        for component in bom_components:
            # Calculate required quantity based on BOM scaling
            scale_factor = quantity / bom.base_quantity
            component_qty = component.effective_quantity * scale_factor
            
            # Add direct requirement
            requirement = ComponentRequirement(
                product_id=component.component_product_id,
                product_code="",  # Will be filled in analysis
                product_name="",  # Will be filled in analysis
                required_quantity=component_qty,
                available_quantity=Decimal('0'),
                shortage_quantity=Decimal('0'),
                unit_cost=Decimal('0'),
                total_cost=Decimal('0'),
                is_semi_finished=False,
                has_bom=False
            )
            requirements.append(requirement)
            
            # Check if component is semi-finished with its own BOM
            component_product = self.session.query(Product).get(
                component.component_product_id
            )
            
            if (component_product and 
                component_product.product_type == 'SEMI_FINISHED'):
                
                # Find active BOM for this semi-finished product
                component_bom = self.session.query(BillOfMaterials).filter(
                    and_(
                        BillOfMaterials.parent_product_id == component.component_product_id,
                        BillOfMaterials.status == 'ACTIVE'
                    )
                ).first()
                
                if component_bom:
                    # Recursively explode the component's BOM
                    nested_requirements = self._explode_bom_requirements(
                        component_bom.bom_id, component_qty, visited_boms.copy()
                    )
                    requirements.extend(nested_requirements)
        
        return requirements
    
    def _analyze_component_availability(
        self,
        product_id: int,
        required_quantity: Decimal
    ) -> Dict:
        """
        Analyze stock availability for a specific component.
        
        Args:
            product_id: ID of the component product
            required_quantity: Required quantity
            
        Returns:
            Dictionary with availability analysis
        """
        # Get product information
        product = self.session.query(Product).get(product_id)
        if not product:
            return {
                'product_code': 'UNKNOWN',
                'product_name': 'Unknown Product',
                'available_quantity': Decimal('0'),
                'unit_cost': Decimal('0'),
                'is_semi_finished': False,
                'has_bom': False
            }
        
        # Calculate available quantity using FIFO ordering
        available_items = self.session.query(InventoryItem).filter(
            and_(
                InventoryItem.product_id == product_id,
                InventoryItem.quality_status == 'APPROVED',
                InventoryItem.quantity_in_stock > InventoryItem.reserved_quantity
            )
        ).order_by(InventoryItem.entry_date).all()
        
        total_available = sum(item.available_quantity for item in available_items)
        
        # Calculate average unit cost using FIFO
        weighted_cost = Decimal('0')
        total_quantity = Decimal('0')
        
        for item in available_items:
            if item.available_quantity > 0:
                weighted_cost += item.unit_cost * item.available_quantity
                total_quantity += item.available_quantity
        
        avg_unit_cost = weighted_cost / total_quantity if total_quantity > 0 else Decimal('0')
        
        # Check if product has BOM (for semi-finished products)
        has_bom = False
        bom_id = None
        if product.product_type == 'SEMI_FINISHED':
            active_bom = self.session.query(BillOfMaterials).filter(
                and_(
                    BillOfMaterials.parent_product_id == product_id,
                    BillOfMaterials.status == 'ACTIVE'
                )
            ).first()
            
            if active_bom:
                has_bom = True
                bom_id = active_bom.bom_id
        
        return {
            'product_code': product.product_code,
            'product_name': product.product_name,
            'available_quantity': total_available,
            'unit_cost': avg_unit_cost,
            'is_semi_finished': product.product_type == 'SEMI_FINISHED',
            'has_bom': has_bom,
            'bom_id': bom_id
        }
    
    def create_nested_production_plan(
        self,
        product_id: int,
        bom_id: int,
        planned_quantity: Decimal,
        warehouse_id: int,
        target_date: Optional[date] = None,
        priority: int = 5
    ) -> ProductionPlanNode:
        """
        Create a nested production plan for complex products with dependencies.
        
        Args:
            product_id: ID of product to produce
            bom_id: ID of BOM to use
            planned_quantity: Quantity to produce
            warehouse_id: Target warehouse ID
            target_date: Target completion date
            priority: Production priority
            
        Returns:
            ProductionPlanNode with nested dependencies
        """
        # First analyze stock availability
        analysis = self.analyze_stock_availability(
            product_id, bom_id, planned_quantity, warehouse_id
        )
        
        # Get product information
        product = self.session.query(Product).get(product_id)
        
        # Create root plan node
        plan_node = ProductionPlanNode(
            product_id=product_id,
            product_code=product.product_code,
            product_name=product.product_name,
            required_quantity=planned_quantity,
            bom_id=bom_id,
            warehouse_id=warehouse_id,
            priority=priority,
            dependencies=[],
            estimated_cost=analysis.total_estimated_cost
        )
        
        # Create production plans for semi-finished product shortages
        for shortage in analysis.semi_finished_shortages:
            if shortage.has_bom and shortage.bom_id:
                # Find appropriate warehouse for semi-finished production
                semi_warehouse = self.session.query(Warehouse).filter(
                    Warehouse.warehouse_type == 'SEMI_FINISHED'
                ).first()
                
                if semi_warehouse:
                    # Recursively create production plan for semi-finished product
                    dependency_plan = self.create_nested_production_plan(
                        shortage.product_id,
                        shortage.bom_id,
                        shortage.shortage_quantity,
                        semi_warehouse.warehouse_id,
                        target_date,
                        priority + 1  # Higher priority for dependencies
                    )
                    plan_node.dependencies.append(dependency_plan)
        
        return plan_node
    
    def reserve_stock_for_production(
        self,
        production_order_id: int,
        reserved_by: str = "SYSTEM"
    ) -> List[StockReservation]:
        """
        Reserve stock for a production order using FIFO allocation.
        
        Args:
            production_order_id: ID of the production order
            reserved_by: User who is making the reservation
            
        Returns:
            List of created stock reservations
        """
        # Get production order and its components
        production_order = self.session.query(ProductionOrder).get(production_order_id)
        if not production_order:
            raise ValueError(f"Production order {production_order_id} not found")
        
        reservations = []
        
        # Get all components for this production order
        components = self.session.query(ProductionOrderComponent).filter(
            ProductionOrderComponent.production_order_id == production_order_id
        ).all()
        
        for component in components:
            # Reserve stock using FIFO for this component
            component_reservations = self._reserve_component_stock(
                component.component_product_id,
                component.required_quantity,
                production_order.warehouse_id,
                production_order_id,
                reserved_by
            )
            reservations.extend(component_reservations)
        
        return reservations
    
    def _reserve_component_stock(
        self,
        product_id: int,
        required_quantity: Decimal,
        warehouse_id: int,
        production_order_id: int,
        reserved_by: str
    ) -> List[StockReservation]:
        """
        Reserve stock for a specific component using FIFO allocation.
        First tries to reserve from the target warehouse, then from other warehouses if needed.
        Updates the corresponding ProductionOrderComponent allocation status.
        """
        reservations = []
        remaining_quantity = required_quantity
        
        # First, try to get available inventory items from the target warehouse in FIFO order
        available_items = self.session.query(InventoryItem).filter(
            and_(
                InventoryItem.product_id == product_id,
                InventoryItem.warehouse_id == warehouse_id,
                InventoryItem.quality_status == 'APPROVED',
                InventoryItem.quantity_in_stock > InventoryItem.reserved_quantity
            )
        ).order_by(InventoryItem.entry_date).all()
        
        # Reserve from target warehouse first
        for item in available_items:
            if remaining_quantity <= 0:
                break
            
            available_qty = item.available_quantity
            if available_qty <= 0:
                continue
            
            # Reserve as much as possible from this batch
            reserve_qty = min(remaining_quantity, available_qty)
            
            # Create reservation
            reservation = StockReservation(
                product_id=product_id,
                warehouse_id=item.warehouse_id,  # Use the actual warehouse of the item
                reserved_quantity=reserve_qty,
                reserved_for_type='PRODUCTION_ORDER',
                reserved_for_id=production_order_id,
                reservation_date=datetime.now(),
                status='ACTIVE',
                reserved_by=reserved_by,
                notes=f'Reserved for production order {production_order_id} from warehouse {item.warehouse_id}'
            )
            
            self.session.add(reservation)
            reservations.append(reservation)
            
            # Update inventory item reserved quantity
            item.reserved_quantity += reserve_qty
            remaining_quantity -= reserve_qty
        
        # If we still need more stock, search other warehouses (cross-warehouse allocation)
        if remaining_quantity > 0:
            # Get available inventory items from ALL other warehouses in FIFO order
            other_warehouse_items = self.session.query(InventoryItem).filter(
                and_(
                    InventoryItem.product_id == product_id,
                    InventoryItem.warehouse_id != warehouse_id,  # Exclude target warehouse (already checked)
                    InventoryItem.quality_status == 'APPROVED',
                    InventoryItem.quantity_in_stock > InventoryItem.reserved_quantity
                )
            ).order_by(InventoryItem.entry_date).all()
            
            # Reserve from other warehouses if needed
            for item in other_warehouse_items:
                if remaining_quantity <= 0:
                    break
                
                available_qty = item.available_quantity
                if available_qty <= 0:
                    continue
                
                # Reserve as much as possible from this batch
                reserve_qty = min(remaining_quantity, available_qty)
                
                # Create reservation
                reservation = StockReservation(
                    product_id=product_id,
                    warehouse_id=item.warehouse_id,  # Use the actual warehouse of the item
                    reserved_quantity=reserve_qty,
                    reserved_for_type='PRODUCTION_ORDER',
                    reserved_for_id=production_order_id,
                    reservation_date=datetime.now(),
                    status='ACTIVE',
                    reserved_by=reserved_by,
                    notes=f'Reserved for production order {production_order_id} from warehouse {item.warehouse_id} (cross-warehouse allocation)'
                )
                
                self.session.add(reservation)
                reservations.append(reservation)
                
                # Update inventory item reserved quantity
                item.reserved_quantity += reserve_qty
                remaining_quantity -= reserve_qty
        
        if remaining_quantity > 0:
            # Could not fully reserve required quantity even with cross-warehouse search
            raise ValueError(
                f"Insufficient stock for product {product_id}. "
                f"Required: {required_quantity}, Available: {required_quantity - remaining_quantity}"
            )
        
        # Update the corresponding ProductionOrderComponent allocation status
        total_reserved = required_quantity - remaining_quantity  # This should equal required_quantity if successful
        self._update_component_allocation(production_order_id, product_id, total_reserved)
        
        return reservations
    
    def _update_component_allocation(
        self,
        production_order_id: int,
        component_product_id: int,
        allocated_quantity: Decimal
    ):
        """
        Update ProductionOrderComponent allocation status when stock is reserved.
        
        Args:
            production_order_id: ID of the production order
            component_product_id: ID of the component product
            allocated_quantity: Quantity that was successfully allocated/reserved
        """
        # Find the corresponding ProductionOrderComponent record
        component = self.session.query(ProductionOrderComponent).filter(
            and_(
                ProductionOrderComponent.production_order_id == production_order_id,
                ProductionOrderComponent.component_product_id == component_product_id
            )
        ).first()
        
        if not component:
            raise ValueError(
                f"ProductionOrderComponent not found for production order {production_order_id} "
                f"and component product {component_product_id}"
            )
        
        # Update the allocated quantity
        component.allocated_quantity = allocated_quantity
        
        # Update allocation status based on quantities
        if allocated_quantity == Decimal('0'):
            component.allocation_status = 'NOT_ALLOCATED'
        elif allocated_quantity < component.required_quantity:
            component.allocation_status = 'PARTIALLY_ALLOCATED'
        elif allocated_quantity == component.required_quantity:
            component.allocation_status = 'FULLY_ALLOCATED'
        else:
            # This shouldn't happen in normal operation, but handle it gracefully
            component.allocation_status = 'FULLY_ALLOCATED'
        
        # Update the component record in the session
        self.session.add(component)
    
    def release_stock_reservations(
        self,
        production_order_id: int
    ) -> int:
        """
        Release all stock reservations for a production order and reset component allocation status.
        
        Args:
            production_order_id: ID of the production order
            
        Returns:
            Number of reservations released
        """
        # Get all active reservations for this production order
        reservations = self.session.query(StockReservation).filter(
            and_(
                StockReservation.reserved_for_type == 'PRODUCTION_ORDER',
                StockReservation.reserved_for_id == production_order_id,
                StockReservation.status == 'ACTIVE'
            )
        ).all()
        
        released_count = 0
        
        # Track component products that need their allocation status reset
        component_products_released = set()
        
        for reservation in reservations:
            # Track this component for allocation status reset
            component_products_released.add(reservation.product_id)
            
            # Update inventory item to reduce reserved quantity
            inventory_items = self.session.query(InventoryItem).filter(
                and_(
                    InventoryItem.product_id == reservation.product_id,
                    InventoryItem.warehouse_id == reservation.warehouse_id,
                    InventoryItem.reserved_quantity >= reservation.reserved_quantity
                )
            ).order_by(InventoryItem.entry_date).all()
            
            remaining_to_release = reservation.reserved_quantity
            
            for item in inventory_items:
                if remaining_to_release <= 0:
                    break
                    
                release_qty = min(remaining_to_release, item.reserved_quantity)
                item.reserved_quantity -= release_qty
                remaining_to_release -= release_qty
            
            # Mark reservation as released
            reservation.release_reservation()
            released_count += 1
        
        # Reset allocation status for all affected components
        for component_product_id in component_products_released:
            self._update_component_allocation(production_order_id, component_product_id, Decimal('0'))
        
        return released_count
    
    def consume_stock_for_production(
        self,
        production_order_id: int
    ) -> List[Dict]:
        """
        Consume reserved stock for a production order using FIFO principles.
        This method is called when production order status changes to COMPLETED.
        
        Args:
            production_order_id: ID of the production order
            
        Returns:
            List of consumption records
        """
        # Get all active reservations for this production order
        reservations = self.session.query(StockReservation).filter(
            and_(
                StockReservation.reserved_for_type == 'PRODUCTION_ORDER',
                StockReservation.reserved_for_id == production_order_id,
                StockReservation.status == 'ACTIVE'
            )
        ).all()
        
        if not reservations:
            raise ValueError(f"No active stock reservations found for production order {production_order_id}")
        
        consumption_records = []
        
        # Track component products that need their status updated
        component_products_consumed = set()
        
        for reservation in reservations:
            # Track this component for status update
            component_products_consumed.add(reservation.product_id)
            
            # Find inventory items to consume from in FIFO order
            inventory_items = self.session.query(InventoryItem).filter(
                and_(
                    InventoryItem.product_id == reservation.product_id,
                    InventoryItem.warehouse_id == reservation.warehouse_id,
                    InventoryItem.reserved_quantity >= reservation.reserved_quantity
                )
            ).order_by(InventoryItem.entry_date).all()
            
            remaining_to_consume = reservation.reserved_quantity
            
            for item in inventory_items:
                if remaining_to_consume <= 0:
                    break
                
                # Calculate how much we can consume from this batch
                consume_qty = min(remaining_to_consume, item.reserved_quantity)
                
                # Update inventory item quantities (FIFO consumption)
                item.quantity_in_stock -= consume_qty
                item.reserved_quantity -= consume_qty
                
                # Record consumption for audit trail
                consumption_record = {
                    'product_id': reservation.product_id,
                    'warehouse_id': item.warehouse_id,
                    'inventory_item_id': item.inventory_item_id,
                    'consumed_quantity': consume_qty,
                    'unit_cost': item.unit_cost,
                    'total_cost': item.unit_cost * consume_qty,
                    'batch_number': item.batch_number,
                    'entry_date': item.entry_date,
                    'consumption_date': datetime.now()
                }
                consumption_records.append(consumption_record)
                
                remaining_to_consume -= consume_qty
            
            if remaining_to_consume > 0:
                raise ValueError(
                    f"Could not fully consume reservation for product {reservation.product_id}. "
                    f"Missing quantity: {remaining_to_consume}"
                )
            
            # Mark reservation as consumed
            reservation.consume_reservation()
        
        # Update component status to CONSUMED
        for component_product_id in component_products_consumed:
            self._update_component_status_to_consumed(production_order_id, component_product_id)
        
        return consumption_records
    
    def adjust_stock_reservations_for_quantity_change(
        self,
        production_order_id: int,
        old_quantity: Decimal,
        new_quantity: Decimal
    ) -> Dict:
        """
        Adjust stock reservations when production order quantity changes.
        
        Args:
            production_order_id: ID of the production order
            old_quantity: Previous planned quantity
            new_quantity: New planned quantity
            
        Returns:
            Summary of adjustments made
        """
        if old_quantity == new_quantity:
            return {'message': 'No quantity change detected'}
        
        # Get production order to validate
        production_order = self.session.query(ProductionOrder).get(production_order_id)
        if not production_order:
            raise ValueError(f"Production order {production_order_id} not found")
        
        if production_order.status not in ['PLANNED', 'RELEASED']:
            raise ValueError(f"Cannot adjust reservations for production order in {production_order.status} status")
        
        quantity_ratio = new_quantity / old_quantity
        
        # Get all active reservations for this production order
        reservations = self.session.query(StockReservation).filter(
            and_(
                StockReservation.reserved_for_type == 'PRODUCTION_ORDER',
                StockReservation.reserved_for_id == production_order_id,
                StockReservation.status == 'ACTIVE'
            )
        ).all()
        
        adjustments = []
        
        if new_quantity > old_quantity:
            # Quantity increased - need to reserve more stock
            for reservation in reservations:
                old_reserved_qty = reservation.reserved_quantity
                new_reserved_qty = old_reserved_qty * quantity_ratio
                additional_qty_needed = new_reserved_qty - old_reserved_qty
                
                try:
                    # Try to reserve additional stock for this product
                    additional_reservations = self._reserve_component_stock(
                        reservation.product_id,
                        additional_qty_needed,
                        production_order.warehouse_id,
                        production_order_id,
                        reservation.reserved_by
                    )
                    
                    adjustments.append({
                        'product_id': reservation.product_id,
                        'action': 'INCREASED',
                        'old_quantity': old_reserved_qty,
                        'new_quantity': new_reserved_qty,
                        'additional_reservations': len(additional_reservations)
                    })
                    
                except ValueError as e:
                    # Could not reserve additional stock
                    adjustments.append({
                        'product_id': reservation.product_id,
                        'action': 'INSUFFICIENT_STOCK',
                        'old_quantity': old_reserved_qty,
                        'requested_quantity': new_reserved_qty,
                        'error': str(e)
                    })
        
        else:
            # Quantity decreased - release excess stock
            for reservation in reservations:
                old_reserved_qty = reservation.reserved_quantity
                new_reserved_qty = old_reserved_qty * quantity_ratio
                excess_qty = old_reserved_qty - new_reserved_qty
                
                # Release excess quantity from inventory items
                inventory_items = self.session.query(InventoryItem).filter(
                    and_(
                        InventoryItem.product_id == reservation.product_id,
                        InventoryItem.warehouse_id == reservation.warehouse_id,
                        InventoryItem.reserved_quantity > 0
                    )
                ).order_by(InventoryItem.entry_date.desc()).all()  # LIFO for release (release most recent first)
                
                remaining_to_release = excess_qty
                
                for item in inventory_items:
                    if remaining_to_release <= 0:
                        break
                    
                    release_qty = min(remaining_to_release, item.reserved_quantity)
                    item.reserved_quantity -= release_qty
                    remaining_to_release -= release_qty
                
                # Update reservation quantity
                reservation.reserved_quantity = new_reserved_qty
                
                adjustments.append({
                    'product_id': reservation.product_id,
                    'action': 'DECREASED',
                    'old_quantity': old_reserved_qty,
                    'new_quantity': new_reserved_qty,
                    'released_quantity': excess_qty
                })
        
        # Update component allocations based on new quantities
        components = self.session.query(ProductionOrderComponent).filter(
            ProductionOrderComponent.production_order_id == production_order_id
        ).all()
        
        for component in components:
            # Recalculate required quantity based on new production quantity
            bom = self.session.query(BillOfMaterials).get(production_order.bom_id)
            bom_component = self.session.query(BomComponent).filter(
                and_(
                    BomComponent.bom_id == bom.bom_id,
                    BomComponent.component_product_id == component.component_product_id
                )
            ).first()
            
            if bom_component:
                new_required_qty = (Decimal(str(bom_component.quantity_required)) * new_quantity) / Decimal(str(bom.base_quantity))
                
                # Apply scrap percentage if defined
                if bom_component.scrap_percentage and bom_component.scrap_percentage > 0:
                    scrap_multiplier = Decimal('1') + (Decimal(str(bom_component.scrap_percentage)) / Decimal('100'))
                    new_required_qty = new_required_qty * scrap_multiplier
                
                component.required_quantity = new_required_qty
                
                # Update allocation quantities proportionally
                if component.allocated_quantity > 0:
                    component.allocated_quantity = component.allocated_quantity * quantity_ratio
                    component._update_allocation_status()
        
        return {
            'production_order_id': production_order_id,
            'old_quantity': old_quantity,
            'new_quantity': new_quantity,
            'quantity_ratio': float(quantity_ratio),
            'adjustments': adjustments
        }
    
    def _update_component_status_to_consumed(
        self,
        production_order_id: int,
        component_product_id: int
    ):
        """
        Update ProductionOrderComponent status to CONSUMED when stock is consumed.
        
        Args:
            production_order_id: ID of the production order
            component_product_id: ID of the component product
        """
        component = self.session.query(ProductionOrderComponent).filter(
            and_(
                ProductionOrderComponent.production_order_id == production_order_id,
                ProductionOrderComponent.component_product_id == component_product_id
            )
        ).first()
        
        if component:
            component.consumed_quantity = component.allocated_quantity
            component.allocation_status = 'CONSUMED'
            self.session.add(component)