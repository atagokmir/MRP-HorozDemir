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
from models.inventory import InventoryItem, StockMovement
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
        
        # Explode BOM to get all component requirements (direct components only for validation)
        component_requirements = self._explode_bom_requirements_flat(
            bom_id, planned_quantity
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
        
        # Critical validation logic:
        # 1. If raw materials are missing, cannot produce at all
        # 2. If only semi-finished products are missing BUT they can be produced (have BOMs), allow with dependency creation
        # 3. If semi-finished products are missing and don't have BOMs, treat as raw material shortage
        
        # Check if semi-finished shortages can be resolved by production
        resolvable_semi_shortages = []
        unresolvable_semi_shortages = []
        
        for semi_shortage in semi_finished_shortages:
            if semi_shortage.has_bom and semi_shortage.bom_id:
                # Check if the semi-finished product itself can be produced (recursive check)
                try:
                    semi_analysis = self.analyze_stock_availability(
                        semi_shortage.product_id,
                        semi_shortage.bom_id,
                        semi_shortage.shortage_quantity,
                        warehouse_id
                    )
                    
                    # If this semi-finished product has raw material shortages, it's unresolvable
                    if len(semi_analysis.raw_material_shortages) > 0:
                        unresolvable_semi_shortages.append(semi_shortage)
                        # Add the underlying raw material shortages to our list
                        raw_material_shortages.extend(semi_analysis.raw_material_shortages)
                    else:
                        resolvable_semi_shortages.append(semi_shortage)
                except:
                    # If analysis fails, treat as unresolvable
                    unresolvable_semi_shortages.append(semi_shortage)
            else:
                # Semi-finished without BOM is essentially a raw material
                unresolvable_semi_shortages.append(semi_shortage)
                raw_material_shortages.append(semi_shortage)
        
        # Update semi_finished_shortages to only include resolvable ones
        semi_finished_shortages = resolvable_semi_shortages
        
        # Determine if production can proceed
        # Can produce if: no raw material shortages AND no unresolvable semi-finished shortages
        can_produce = len(raw_material_shortages) == 0
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
    
    def _explode_bom_requirements_flat(
        self,
        bom_id: int,
        quantity: Decimal
    ) -> List[ComponentRequirement]:
        """
        Explode BOM to get direct component requirements only (non-recursive).
        Used for production order validation.
        """
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
        
        return requirements
    
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
    
    def _get_source_warehouse_for_product(self, product: Product) -> Optional[int]:
        """
        Determine the appropriate source warehouse based on product type.
        
        Args:
            product: Product object
            
        Returns:
            Warehouse ID for the appropriate source warehouse, or None if not found
        """
        # Mapping of product types to warehouse types
        warehouse_type_mapping = {
            'RAW_MATERIAL': 'RAW_MATERIALS',
            'SEMI_FINISHED': 'SEMI_FINISHED', 
            'FINISHED_PRODUCT': 'FINISHED_PRODUCTS',
            'PACKAGING': 'PACKAGING'
        }
        
        required_warehouse_type = warehouse_type_mapping.get(product.product_type)
        if not required_warehouse_type:
            return None
            
        # Find the warehouse of the appropriate type
        warehouse = self.session.query(Warehouse).filter(
            and_(
                Warehouse.warehouse_type == required_warehouse_type,
                Warehouse.is_active == True
            )
        ).first()
        
        return warehouse.warehouse_id if warehouse else None

    def _analyze_component_availability(
        self,
        product_id: int,
        required_quantity: Decimal
    ) -> Dict:
        """
        Analyze stock availability for a specific component.
        CRITICAL FIX: Now searches in the appropriate warehouse based on product type.
        
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
        
        # CRITICAL FIX: Get the appropriate source warehouse for this product type
        source_warehouse_id = self._get_source_warehouse_for_product(product)
        
        # Build the base query filter
        base_query_filter = [
            InventoryItem.product_id == product_id,
            InventoryItem.quality_status == 'APPROVED',
            InventoryItem.quantity_in_stock > InventoryItem.reserved_quantity
        ]
        
        # First try the appropriate source warehouse if it exists
        available_items = []
        total_available = Decimal('0')
        
        if source_warehouse_id:
            # Try source warehouse first
            source_query_filter = base_query_filter + [InventoryItem.warehouse_id == source_warehouse_id]
            source_items = self.session.query(InventoryItem).filter(
                and_(*source_query_filter)
            ).order_by(InventoryItem.entry_date).all()
            
            available_items.extend(source_items)
            total_available += sum(item.available_quantity for item in source_items)
        
        # If not enough stock in source warehouse, search other warehouses (cross-warehouse allocation)
        if total_available < required_quantity or source_warehouse_id is None:
            # Search all warehouses except the one we already checked
            other_query_filter = base_query_filter.copy()
            if source_warehouse_id:
                other_query_filter.append(InventoryItem.warehouse_id != source_warehouse_id)
            
            other_items = self.session.query(InventoryItem).filter(
                and_(*other_query_filter)
            ).order_by(InventoryItem.entry_date).all()
            
            available_items.extend(other_items)
            total_available += sum(item.available_quantity for item in other_items)
        
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
        failed_components = []
        
        # Get all components for this production order
        components = self.session.query(ProductionOrderComponent).filter(
            ProductionOrderComponent.production_order_id == production_order_id
        ).all()
        
        # Process each component individually to ensure all are handled
        for component in components:
            try:
                # Reserve stock using FIFO for this component
                component_reservations = self._reserve_component_stock(
                    component.component_product_id,
                    component.required_quantity,
                    production_order.warehouse_id,
                    production_order_id,
                    reserved_by
                )
                reservations.extend(component_reservations)
                
            except ValueError as e:
                # Track failed components but continue processing others
                failed_components.append({
                    'component_product_id': component.component_product_id,
                    'required_quantity': component.required_quantity,
                    'error': str(e)
                })
                continue
        
        # If any components failed to reserve, include details in the error
        if failed_components:
            error_msg = f"Failed to reserve stock for {len(failed_components)} components: "
            for failed in failed_components:
                error_msg += f"Product {failed['component_product_id']} (qty: {failed['required_quantity']}) - {failed['error']}; "
            
            # If NO components were reserved successfully, raise an error
            if not reservations:
                raise ValueError(error_msg)
            
            # If SOME components were reserved, we still have partial success
            # The calling code can decide how to handle this
        
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
        CRITICAL FIX: Now sources from appropriate warehouse based on product type first.
        Updates the corresponding ProductionOrderComponent allocation status.
        SYNCHRONIZATION FIX: Ensures inventory_items.reserved_quantity stays in sync with stock_reservations.
        """
        reservations = []
        remaining_quantity = required_quantity
        
        # Get product information to determine correct source warehouse
        product = self.session.query(Product).get(product_id)
        if not product:
            raise ValueError(f"Product {product_id} not found")
        
        # CRITICAL FIX: Get the appropriate source warehouse for this product type
        source_warehouse_id = self._get_source_warehouse_for_product(product)
        
        # Priority order for warehouse searching:
        # 1. Appropriate source warehouse based on product type
        # 2. Target warehouse (if different from source)
        # 3. All other warehouses
        
        warehouses_to_check = []
        if source_warehouse_id:
            warehouses_to_check.append(source_warehouse_id)
        if warehouse_id != source_warehouse_id:
            warehouses_to_check.append(warehouse_id)
        
        # Try to reserve from warehouses in priority order
        for check_warehouse_id in warehouses_to_check:
            if remaining_quantity <= 0:
                break
                
            # Get available inventory items from this warehouse in FIFO order
            available_items = self.session.query(InventoryItem).filter(
                and_(
                    InventoryItem.product_id == product_id,
                    InventoryItem.warehouse_id == check_warehouse_id,
                    InventoryItem.quality_status == 'APPROVED',
                    InventoryItem.quantity_in_stock > InventoryItem.reserved_quantity
                )
            ).order_by(InventoryItem.entry_date).all()
            
            # Reserve from this warehouse
            for item in available_items:
                if remaining_quantity <= 0:
                    break
                
                available_qty = item.available_quantity
                if available_qty <= 0:
                    continue
                
                # Reserve as much as possible from this batch
                reserve_qty = min(remaining_quantity, available_qty)
                
                # Create reservation FIRST
                warehouse_note = "appropriate source warehouse" if check_warehouse_id == source_warehouse_id else "cross-warehouse allocation"
                reservation = StockReservation(
                    product_id=product_id,
                    warehouse_id=item.warehouse_id,  # Use the actual warehouse of the item
                    reserved_quantity=reserve_qty,
                    reserved_for_type='PRODUCTION_ORDER',
                    reserved_for_id=production_order_id,
                    reservation_date=datetime.now(),
                    status='ACTIVE',
                    reserved_by=reserved_by,
                    notes=f'Reserved for production order {production_order_id} from warehouse {item.warehouse_id} ({warehouse_note}, product type: {product.product_type})'
                )
                
                self.session.add(reservation)
                self.session.flush()  # Ensure reservation is created before updating inventory
                reservations.append(reservation)
                
                # SYNCHRONIZATION FIX: Update inventory item reserved quantity to match total active reservations
                self._sync_inventory_reserved_quantity(item.inventory_item_id)
                remaining_quantity -= reserve_qty
        
        # If we still need more stock, search ALL other warehouses as final fallback
        if remaining_quantity > 0:
            checked_warehouses = set(warehouses_to_check)
            
            # Get available inventory items from ALL other warehouses in FIFO order
            other_warehouse_items = self.session.query(InventoryItem).filter(
                and_(
                    InventoryItem.product_id == product_id,
                    ~InventoryItem.warehouse_id.in_(checked_warehouses),  # Exclude already checked warehouses
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
                
                # Create reservation FIRST
                reservation = StockReservation(
                    product_id=product_id,
                    warehouse_id=item.warehouse_id,  # Use the actual warehouse of the item
                    reserved_quantity=reserve_qty,
                    reserved_for_type='PRODUCTION_ORDER',
                    reserved_for_id=production_order_id,
                    reservation_date=datetime.now(),
                    status='ACTIVE',
                    reserved_by=reserved_by,
                    notes=f'Reserved for production order {production_order_id} from warehouse {item.warehouse_id} (emergency cross-warehouse allocation, product type: {product.product_type})'
                )
                
                self.session.add(reservation)
                self.session.flush()  # Ensure reservation is created before updating inventory
                reservations.append(reservation)
                
                # SYNCHRONIZATION FIX: Update inventory item reserved quantity to match total active reservations
                self._sync_inventory_reserved_quantity(item.inventory_item_id)
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
    
    def _sync_inventory_reserved_quantity(self, inventory_item_id: int):
        """
        Synchronize inventory_items.reserved_quantity with actual active reservations.
        
        CRITICAL FIX: This ensures data consistency between inventory_items.reserved_quantity 
        and the stock_reservations table to prevent phantom stock issues.
        
        Args:
            inventory_item_id: ID of the inventory item to synchronize
        """
        # Get the inventory item
        inventory_item = self.session.query(InventoryItem).get(inventory_item_id)
        if not inventory_item:
            return
        
        # Calculate total active reservations for this product in this warehouse
        # NOTE: We sync by product and warehouse, not by individual inventory item
        # because reservations are tracked at product/warehouse level
        total_reserved = self.session.query(func.coalesce(func.sum(StockReservation.reserved_quantity), 0)).filter(
            and_(
                StockReservation.product_id == inventory_item.product_id,
                StockReservation.warehouse_id == inventory_item.warehouse_id,
                StockReservation.status == 'ACTIVE'
            )
        ).scalar() or Decimal('0')
        
        # Debug output can be enabled for troubleshooting
        # print(f"DEBUG SYNC: Product {inventory_item.product_id}, Warehouse {inventory_item.warehouse_id}, Total active reserved: {total_reserved}")
        
        # Get all inventory items for this product in this warehouse
        inventory_items = self.session.query(InventoryItem).filter(
            and_(
                InventoryItem.product_id == inventory_item.product_id,
                InventoryItem.warehouse_id == inventory_item.warehouse_id,
                InventoryItem.quality_status == 'APPROVED'
            )
        ).order_by(InventoryItem.entry_date).all()
        
        # Distribute the total reserved quantity across inventory items using FIFO principle
        remaining_to_allocate = total_reserved
        
        for item in inventory_items:
            old_qty = item.reserved_quantity
            if remaining_to_allocate <= 0:
                # No more reservation to allocate
                item.reserved_quantity = Decimal('0')
            else:
                # Allocate as much as possible to this item (up to its total stock)
                max_reservable = item.quantity_in_stock
                allocate_to_item = min(remaining_to_allocate, max_reservable)
                item.reserved_quantity = allocate_to_item
                remaining_to_allocate -= allocate_to_item
            # Debug output can be enabled for troubleshooting
            # print(f"DEBUG SYNC ITEM: Item {item.inventory_item_id}: {old_qty} -> {item.reserved_quantity}")
        
        # If there's still remaining to allocate, it means we have a data inconsistency
        # This should not happen in normal operation, but we log it for debugging
        if remaining_to_allocate > 0:
            print(f"WARNING: Could not allocate {remaining_to_allocate} reserved quantity "
                  f"for product {inventory_item.product_id} in warehouse {inventory_item.warehouse_id}. "
                  f"This indicates a data inconsistency that should be investigated.")
        
        # CRITICAL FIX: Flush the changes to ensure they are persisted
        self.session.flush()
    
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
        # Get all reservations for this production order (both active and any other status)
        reservations = self.session.query(StockReservation).filter(
            and_(
                StockReservation.reserved_for_type == 'PRODUCTION_ORDER',
                StockReservation.reserved_for_id == production_order_id,
                StockReservation.status.in_(['ACTIVE', 'CONSUMED'])  # Include consumed ones for tracking
            )
        ).all()
        
        # Debug output can be enabled for troubleshooting
        # print(f"DEBUG RELEASE: Found {len(reservations)} reservations for production order {production_order_id}")
        
        released_count = 0
        errors = []
        
        # Track component products that need their allocation status reset
        component_products_released = set()
        
        # Track product/warehouse combinations that need inventory sync
        inventory_sync_needed = set()
        
        for reservation in reservations:
            try:
                # Only release active reservations
                if reservation.status != 'ACTIVE':
                    continue
                    
                # Track this component for allocation status reset
                component_products_released.add(reservation.product_id)
                
                # Track this product/warehouse for inventory sync
                inventory_sync_needed.add((reservation.product_id, reservation.warehouse_id))
                
                # Mark reservation as released
                reservation.release_reservation()
                released_count += 1
                    
            except Exception as e:
                errors.append(f"Error releasing reservation {reservation.reservation_id}: {str(e)}")
                continue
        
        # CRITICAL FIX: Flush changes to ensure reservations are marked as RELEASED before sync
        self.session.flush()
        
        # CRITICAL FIX: Synchronize inventory reserved quantities AFTER releasing all reservations
        # This prevents race conditions and ensures consistent state
        for product_id, warehouse_id in inventory_sync_needed:
            try:
                # Find any inventory item from this product/warehouse to trigger sync
                sample_item = self.session.query(InventoryItem).filter(
                    and_(
                        InventoryItem.product_id == product_id,
                        InventoryItem.warehouse_id == warehouse_id,
                        InventoryItem.quality_status == 'APPROVED'
                    )
                ).first()
                
                if sample_item:
                    old_reserved = sample_item.reserved_quantity
                    try:
                        self._sync_inventory_reserved_quantity(sample_item.inventory_item_id)
                        # Refresh the item to see the updated value
                        self.session.refresh(sample_item)
                        new_reserved = sample_item.reserved_quantity
                        # Optional: Debug output can be enabled for troubleshooting
                        # print(f"DEBUG: Synced inventory for product {product_id} in warehouse {warehouse_id}: {old_reserved} -> {new_reserved}")
                    except Exception as sync_error:
                        print(f"ERROR: Failed to sync inventory for product {product_id} in warehouse {warehouse_id}: {str(sync_error)}")
                        errors.append(f"Sync error for product {product_id}, warehouse {warehouse_id}: {str(sync_error)}")
                else:
                    print(f"WARNING: No inventory item found for sync - product {product_id}, warehouse {warehouse_id}")
                    
            except Exception as e:
                errors.append(f"Error syncing inventory for product {product_id}, warehouse {warehouse_id}: {str(e)}")
                continue
        
        # Reset allocation status for all affected components
        for component_product_id in component_products_released:
            try:
                self._update_component_allocation(production_order_id, component_product_id, Decimal('0'))
            except Exception as e:
                errors.append(f"Error resetting allocation for component {component_product_id}: {str(e)}")
        
        # Log errors if any occurred but don't fail the operation
        if errors:
            print(f"Warnings during reservation release for order {production_order_id}: {'; '.join(errors)}")
        
        return released_count
    
    def consume_stock_for_production(
        self,
        production_order_id: int
    ) -> List[Dict]:
        """
        Consume reserved stock for a production order using FIFO principles.
        This method is called when production order status changes to COMPLETED.
        
        CRITICAL FIX: Now properly consumes from reserved quantities and reduces
        reserved_quantity instead of quantity_in_stock directly.
        
        Args:
            production_order_id: ID of the production order
            
        Returns:
            List of consumption records
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Get all active reservations for this production order
        reservations = self.session.query(StockReservation).filter(
            and_(
                StockReservation.reserved_for_type == 'PRODUCTION_ORDER',
                StockReservation.reserved_for_id == production_order_id,
                StockReservation.status == 'ACTIVE'
            )
        ).all()
        
        logger.info(f"📦 FIFO CONSUMPTION: Found {len(reservations)} active reservations for order {production_order_id}")
        for i, res in enumerate(reservations):
            logger.info(f"  📋 Reservation {i+1}: Product {res.product_id}, Warehouse {res.warehouse_id}, Qty: {res.reserved_quantity}")
        
        if not reservations:
            logger.error(f"❌ FIFO CONSUMPTION: No active stock reservations found for production order {production_order_id}")
            raise ValueError(f"No active stock reservations found for production order {production_order_id}")
        
        consumption_records = []
        
        # Track component products that need their status updated
        component_products_consumed = set()
        
        for reservation in reservations:
            logger.info(f"🔄 Processing reservation for Product {reservation.product_id}, Warehouse {reservation.warehouse_id}")
            
            # Track this component for status update
            component_products_consumed.add(reservation.product_id)
            
            # FIXED: Find inventory items that have reserved quantity for this reservation
            # We need to consume from items that actually have reservations, in FIFO order
            inventory_items = self.session.query(InventoryItem).filter(
                and_(
                    InventoryItem.product_id == reservation.product_id,
                    InventoryItem.warehouse_id == reservation.warehouse_id,
                    InventoryItem.reserved_quantity > 0,  # Only items with reservations
                    InventoryItem.quantity_in_stock > 0   # That still have stock
                )
            ).order_by(InventoryItem.entry_date).all()  # FIFO order
            
            logger.info(f"  📦 Found {len(inventory_items)} inventory batches with reservations")
            for i, item in enumerate(inventory_items):
                logger.info(f"    🏷️ Batch {i+1}: ID {item.inventory_item_id}, Entry: {item.entry_date}, Stock: {item.quantity_in_stock}, Reserved: {item.reserved_quantity}")
            
            remaining_to_consume = reservation.reserved_quantity
            logger.info(f"  🎯 Need to consume: {remaining_to_consume}")
            
            for item in inventory_items:
                if remaining_to_consume <= 0:
                    break
                
                # FIXED: Calculate how much we can consume from this batch's reserved quantity
                # We can only consume up to what's reserved in this item
                consume_qty = min(remaining_to_consume, item.reserved_quantity)
                
                if consume_qty <= 0:
                    continue
                
                logger.info(f"    ✂️ Consuming {consume_qty} from batch {item.inventory_item_id} (Stock: {item.quantity_in_stock}, Reserved: {item.reserved_quantity})")
                
                # Store before values for logging
                before_stock = item.quantity_in_stock
                before_reserved = item.reserved_quantity
                
                # FIXED: Properly update inventory quantities
                # Reduce both reserved quantity and total stock
                item.reserved_quantity -= consume_qty
                item.quantity_in_stock -= consume_qty
                
                logger.info(f"    ✅ Updated batch {item.inventory_item_id}: Stock {before_stock}→{item.quantity_in_stock}, Reserved {before_reserved}→{item.reserved_quantity}")
                
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
                logger.info(f"    📉 Remaining to consume: {remaining_to_consume}")
            
            if remaining_to_consume > 0:
                raise ValueError(
                    f"Could not fully consume reservation for product {reservation.product_id}. "
                    f"Missing reserved quantity: {remaining_to_consume}. "
                    f"This indicates a synchronization issue between reservations and inventory."
                )
            
            # Mark reservation as consumed
            reservation.consume_reservation()
        
        # Update component status to CONSUMED
        for component_product_id in component_products_consumed:
            self._update_component_status_to_consumed(production_order_id, component_product_id)
        
        return consumption_records
    
    def create_finished_goods_inventory(
        self,
        production_order_id: int,
        completed_quantity: Decimal,
        consumption_records: List[Dict]
    ) -> Dict:
        """
        Create finished goods inventory entry after production completion.
        
        Args:
            production_order_id: ID of the completed production order
            completed_quantity: Quantity of finished goods produced
            consumption_records: Records from consume_stock_for_production for cost calculation
            
        Returns:
            Dictionary with created inventory item details
        """
        # Get production order details
        production_order = self.session.query(ProductionOrder).get(production_order_id)
        if not production_order:
            raise ValueError(f"Production order {production_order_id} not found")
        
        # Calculate total material cost from consumption records
        total_material_cost = sum(record['total_cost'] for record in consumption_records)
        
        # Calculate unit cost (material cost per unit produced)
        if completed_quantity > 0:
            unit_cost = total_material_cost / completed_quantity
        else:
            raise ValueError("Cannot create finished goods with zero completed quantity")
        
        # Determine appropriate warehouse based on product type
        product = self.session.query(Product).get(production_order.product_id)
        if not product:
            raise ValueError(f"Product {production_order.product_id} not found")
        
        # Find appropriate warehouse - prefer Finished Products, fallback to Semi-Finished
        finished_warehouse = self.session.query(Warehouse).filter(
            Warehouse.warehouse_type == 'FINISHED_PRODUCTS'
        ).first()
        
        semi_finished_warehouse = self.session.query(Warehouse).filter(
            Warehouse.warehouse_type == 'SEMI_FINISHED_PRODUCTS'
        ).first()
        
        # Choose warehouse based on product type or available warehouses
        if product.product_type == 'FINISHED' and finished_warehouse:
            target_warehouse = finished_warehouse
        elif product.product_type in ['SEMI_FINISHED', 'INTERMEDIATE'] and semi_finished_warehouse:
            target_warehouse = semi_finished_warehouse
        elif finished_warehouse:
            target_warehouse = finished_warehouse  # Default fallback
        elif semi_finished_warehouse:
            target_warehouse = semi_finished_warehouse  # Secondary fallback
        else:
            raise ValueError("No suitable warehouse found for finished goods")
        
        # Generate batch number for finished goods
        batch_number = f"PRD-{production_order.order_number}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Create inventory entry for finished goods
        finished_goods_item = InventoryItem(
            product_id=production_order.product_id,
            warehouse_id=target_warehouse.warehouse_id,
            batch_number=batch_number,
            entry_date=datetime.now(),
            quantity_in_stock=completed_quantity,
            reserved_quantity=Decimal('0'),
            unit_cost=unit_cost,
            supplier_id=None,  # Internal production
            purchase_order_id=None,  # Not from purchase
            location_in_warehouse=f"PROD-{production_order.order_number}",
            quality_status='APPROVED',  # Assume production is quality approved
            notes=f"Produced from production order {production_order.order_number}. Material cost: {total_material_cost}"
        )
        
        self.session.add(finished_goods_item)
        self.session.flush()  # Get the ID
        
        # Create stock movement record for the addition
        stock_movement = StockMovement(
            inventory_item_id=finished_goods_item.inventory_item_id,
            movement_type='PRODUCTION',
            quantity=completed_quantity,
            unit_cost=unit_cost,
            reference_type='PRODUCTION_ORDER',
            reference_id=production_order_id,
            created_by='SYSTEM',  # System generated
            notes=f"Finished goods from production order {production_order.order_number}"
        )
        
        self.session.add(stock_movement)
        
        return {
            'inventory_item_id': finished_goods_item.inventory_item_id,
            'product_id': production_order.product_id,
            'warehouse_id': target_warehouse.warehouse_id,
            'warehouse_name': target_warehouse.warehouse_name,
            'batch_number': batch_number,
            'quantity': completed_quantity,
            'unit_cost': unit_cost,
            'total_cost': total_material_cost,
            'entry_date': finished_goods_item.entry_date
        }
    
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
                
                # Update reservation quantity first
                reservation.reserved_quantity = new_reserved_qty
                
                # SYNCHRONIZATION FIX: Sync inventory reserved quantities after quantity change
                sample_item = self.session.query(InventoryItem).filter(
                    and_(
                        InventoryItem.product_id == reservation.product_id,
                        InventoryItem.warehouse_id == reservation.warehouse_id,
                        InventoryItem.quality_status == 'APPROVED'
                    )
                ).first()
                
                if sample_item:
                    self._sync_inventory_reserved_quantity(sample_item.inventory_item_id)
                
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
    
    def validate_and_fix_reservation_sync(self) -> Dict:
        """
        Validate and fix reservation synchronization across the entire system.
        
        This method checks for inconsistencies between inventory_items.reserved_quantity
        and stock_reservations table, and fixes them.
        
        Returns:
            Summary of validation results and fixes applied
        """
        validation_results = {
            'total_items_checked': 0,
            'sync_issues_found': 0,
            'fixes_applied': 0,
            'details': []
        }
        
        # Get all inventory items that have reserved quantity
        inventory_items_with_reserves = self.session.query(InventoryItem).filter(
            InventoryItem.reserved_quantity > 0
        ).all()
        
        validation_results['total_items_checked'] = len(inventory_items_with_reserves)
        
        for item in inventory_items_with_reserves:
            # Calculate actual reserved quantity from stock_reservations
            actual_reserved = self.session.query(func.coalesce(func.sum(StockReservation.reserved_quantity), 0)).filter(
                and_(
                    StockReservation.product_id == item.product_id,
                    StockReservation.warehouse_id == item.warehouse_id,
                    StockReservation.status == 'ACTIVE'
                )
            ).scalar() or Decimal('0')
            
            # Check if there's a mismatch
            current_reserved = item.reserved_quantity or Decimal('0')
            
            if current_reserved != actual_reserved:
                validation_results['sync_issues_found'] += 1
                
                # Apply fix
                self._sync_inventory_reserved_quantity(item.inventory_item_id)
                validation_results['fixes_applied'] += 1
                
                validation_results['details'].append({
                    'inventory_item_id': item.inventory_item_id,
                    'product_id': item.product_id,
                    'warehouse_id': item.warehouse_id,
                    'old_reserved_quantity': float(current_reserved),
                    'actual_reserved_quantity': float(actual_reserved),
                    'fixed': True
                })
        
        # Also check for products that have active reservations but no inventory reserved quantity
        # This can happen if reservations exist but inventory items have zero reserved_quantity
        products_with_reservations = self.session.query(
            StockReservation.product_id,
            StockReservation.warehouse_id,
            func.sum(StockReservation.reserved_quantity).label('total_reserved')
        ).filter(
            StockReservation.status == 'ACTIVE'
        ).group_by(
            StockReservation.product_id,
            StockReservation.warehouse_id
        ).all()
        
        for product_id, warehouse_id, total_reserved in products_with_reservations:
            # Get total inventory reserved quantity for this product/warehouse
            inventory_reserved = self.session.query(
                func.coalesce(func.sum(InventoryItem.reserved_quantity), 0)
            ).filter(
                and_(
                    InventoryItem.product_id == product_id,
                    InventoryItem.warehouse_id == warehouse_id,
                    InventoryItem.quality_status == 'APPROVED'
                )
            ).scalar() or Decimal('0')
            
            if inventory_reserved != total_reserved:
                validation_results['sync_issues_found'] += 1
                
                # Find a sample inventory item to trigger sync
                sample_item = self.session.query(InventoryItem).filter(
                    and_(
                        InventoryItem.product_id == product_id,
                        InventoryItem.warehouse_id == warehouse_id,
                        InventoryItem.quality_status == 'APPROVED'
                    )
                ).first()
                
                if sample_item:
                    self._sync_inventory_reserved_quantity(sample_item.inventory_item_id)
                    validation_results['fixes_applied'] += 1
                    
                    validation_results['details'].append({
                        'product_id': product_id,
                        'warehouse_id': warehouse_id,
                        'inventory_reserved_total': float(inventory_reserved),
                        'reservations_total': float(total_reserved),
                        'fixed': True
                    })
        
        return validation_results