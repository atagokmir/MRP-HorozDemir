"""
Production Management API endpoints for production orders and manufacturing workflows.
Handles production order lifecycle, component allocation, and completion processing.
"""

from typing import List, Optional, Dict, Set
from decimal import Decimal
from datetime import date, datetime
from fastapi import APIRouter, Depends, Query, Path, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc

from app.dependencies import (
    get_db, get_current_active_user, require_permissions,
    get_pagination_params, PaginationParams
)
from app.schemas.base import MessageResponse, IDResponse, PaginatedResponse
from app.schemas.auth import UserInfo
from app.schemas.production import (
    ProductionOrderCreate, ProductionOrderUpdate, ProductionOrderResponse,
    ProductionOrderStatusUpdate, ProductionOrderCompletion, ProductionOrderFilters,
    ProductionComponentList, ProductionOrderComponentResponse, StockAnalysisRequest
)
from app.services.mrp_analysis import MRPAnalysisService, StockAnalysisResult, ProductionPlanNode
from app.exceptions import NotFoundError, ProductionOrderError
from models.production import ProductionOrder, ProductionOrderComponent, StockAllocation, StockReservation
from models.bom import BillOfMaterials, BomComponent
from models.master_data import Product, Warehouse
from models.inventory import InventoryItem


router = APIRouter()


def generate_production_order_number(session: Session) -> str:
    """Generate unique production order number in format PO######."""
    # Get the latest order number
    latest_order = session.query(ProductionOrder).order_by(
        desc(ProductionOrder.production_order_id)
    ).first()
    
    if latest_order and latest_order.order_number:
        # Extract number from format PO######
        try:
            last_num = int(latest_order.order_number[2:])
            new_num = last_num + 1
        except (ValueError, IndexError):
            new_num = 1
    else:
        new_num = 1
    
    return f"PO{new_num:06d}"


def validate_bom_and_product(session: Session, product_id: int, bom_id: int) -> tuple:
    """Validate that BOM exists and matches the product."""
    # Check if product exists
    product = session.query(Product).filter(Product.product_id == product_id).first()
    if not product:
        raise NotFoundError("Product", product_id)
    
    # Check if BOM exists and belongs to the product
    bom = session.query(BillOfMaterials).filter(
        and_(
            BillOfMaterials.bom_id == bom_id,
            BillOfMaterials.parent_product_id == product_id,
            BillOfMaterials.status == 'ACTIVE'
        )
    ).first()
    
    if not bom:
        raise HTTPException(
            status_code=400,
            detail=f"Active BOM with ID {bom_id} not found for product {product_id}"
        )
    
    return product, bom


def create_production_order_components(session: Session, production_order: ProductionOrder, bom: BillOfMaterials) -> List[ProductionOrderComponent]:
    """Create production order components based on BOM."""
    components = []
    
    # Get all BOM components
    bom_components = session.query(BomComponent).filter(
        BomComponent.bom_id == bom.bom_id
    ).all()
    
    if not bom_components:
        raise HTTPException(
            status_code=400,
            detail=f"BOM {bom.bom_id} has no components defined"
        )
    
    for bom_comp in bom_components:
        # Calculate required quantity based on production quantity (convert to Decimal)
        required_qty = (Decimal(str(bom_comp.quantity_required)) * production_order.planned_quantity) / Decimal(str(bom.base_quantity))
        
        # Apply scrap percentage if defined
        if bom_comp.scrap_percentage and bom_comp.scrap_percentage > 0:
            scrap_multiplier = Decimal('1') + (Decimal(str(bom_comp.scrap_percentage)) / Decimal('100'))
            required_qty = required_qty * scrap_multiplier
        
        po_component = ProductionOrderComponent(
            production_order_id=production_order.production_order_id,
            component_product_id=bom_comp.component_product_id,
            required_quantity=required_qty,
            allocated_quantity=Decimal('0'),
            consumed_quantity=Decimal('0'),
            unit_cost=Decimal('0'),
            allocation_status='NOT_ALLOCATED'
        )
        
        session.add(po_component)
        components.append(po_component)
    
    return components


@router.get("/", response_model=PaginatedResponse[ProductionOrderResponse])
def list_production_orders(
    pagination: PaginationParams = Depends(get_pagination_params),
    status: Optional[str] = Query(None, description="Filter by status"),
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    bom_id: Optional[int] = Query(None, description="Filter by BOM ID"),
    warehouse_id: Optional[int] = Query(None, description="Filter by warehouse ID"),
    priority: Optional[int] = Query(None, ge=1, le=10, description="Filter by priority"),
    order_date_from: Optional[date] = Query(None, description="Filter orders from date"),
    order_date_to: Optional[date] = Query(None, description="Filter orders to date"),
    planned_start_from: Optional[date] = Query(None, description="Filter by planned start from date"),
    planned_start_to: Optional[date] = Query(None, description="Filter by planned start to date"),
    is_overdue: Optional[bool] = Query(None, description="Filter overdue orders"),
    search: Optional[str] = Query(None, description="Search in order number, notes"),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("read:production"))  # Temporarily disabled for testing
):
    """
    List production orders with status filtering and pagination.
    
    Shows production orders with progress and component status.
    """
    # Build base query with joins for efficiency
    query = session.query(ProductionOrder).options(
        joinedload(ProductionOrder.product),
        joinedload(ProductionOrder.bom),
        joinedload(ProductionOrder.warehouse)
    )
    
    # Apply filters
    if status:
        query = query.filter(ProductionOrder.status == status)
    
    if product_id:
        query = query.filter(ProductionOrder.product_id == product_id)
    
    if bom_id:
        query = query.filter(ProductionOrder.bom_id == bom_id)
    
    if warehouse_id:
        query = query.filter(ProductionOrder.warehouse_id == warehouse_id)
    
    if priority:
        query = query.filter(ProductionOrder.priority == priority)
    
    if order_date_from:
        query = query.filter(ProductionOrder.order_date >= order_date_from)
    
    if order_date_to:
        query = query.filter(ProductionOrder.order_date <= order_date_to)
    
    if planned_start_from:
        query = query.filter(ProductionOrder.planned_start_date >= planned_start_from)
    
    if planned_start_to:
        query = query.filter(ProductionOrder.planned_start_date <= planned_start_to)
    
    if is_overdue is not None:
        if is_overdue:
            query = query.filter(
                and_(
                    ProductionOrder.planned_completion_date < date.today(),
                    ProductionOrder.status.notin_(['COMPLETED', 'CANCELLED'])
                )
            )
        else:
            query = query.filter(
                or_(
                    ProductionOrder.planned_completion_date >= date.today(),
                    ProductionOrder.status.in_(['COMPLETED', 'CANCELLED'])
                )
            )
    
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                ProductionOrder.order_number.ilike(search_pattern),
                ProductionOrder.notes.ilike(search_pattern)
            )
        )
    
    # Get total count for pagination
    total_count = query.count()
    
    # Apply pagination and ordering
    query = query.order_by(desc(ProductionOrder.created_at))
    items = query.offset(pagination.offset).limit(pagination.page_size).all()
    
    # Calculate pagination info
    total_pages = (total_count + pagination.page_size - 1) // pagination.page_size
    has_next = pagination.page < total_pages
    has_previous = pagination.page > 1
    
    # Convert to response format
    production_orders = []
    for order in items:
        order_dict = {
            **order.__dict__,
            'remaining_quantity': order.remaining_quantity,
            'completion_percentage': order.completion_percentage,
            'is_overdue': order.is_overdue,
            'is_ready_for_production': order.is_ready_for_production,
            'product': {
                'product_id': order.product.product_id,
                'product_code': order.product.product_code,
                'product_name': order.product.product_name
            } if order.product else None,
            'bom': {
                'bom_id': order.bom.bom_id,
                'bom_name': order.bom.bom_name,
                'bom_version': order.bom.bom_version
            } if order.bom else None,
            'warehouse': {
                'warehouse_id': order.warehouse.warehouse_id,
                'warehouse_code': order.warehouse.warehouse_code,
                'warehouse_name': order.warehouse.warehouse_name
            } if order.warehouse else None
        }
        production_orders.append(ProductionOrderResponse(**order_dict))
    
    return PaginatedResponse(
        items=production_orders,
        pagination={
            "total_count": total_count,
            "page": pagination.page,
            "page_size": pagination.page_size,
            "total_pages": total_pages,
            "has_next": has_next,
            "has_previous": has_previous
        }
    )


@router.get("/{order_id}", response_model=ProductionOrderResponse)
def get_production_order(
    order_id: int = Path(..., description="Production order ID"),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("read:production"))  # Temporarily disabled for testing
):
    """Get production order by ID with full details."""
    # Query with all related data
    production_order = session.query(ProductionOrder).options(
        joinedload(ProductionOrder.product),
        joinedload(ProductionOrder.bom),
        joinedload(ProductionOrder.warehouse),
        joinedload(ProductionOrder.production_order_components).joinedload(
            ProductionOrderComponent.component_product
        ),
        joinedload(ProductionOrder.stock_allocations).joinedload(
            StockAllocation.inventory_item
        )
    ).filter(ProductionOrder.production_order_id == order_id).first()
    
    if not production_order:
        raise NotFoundError("Production Order", order_id)
    
    # Build comprehensive response
    order_dict = {
        **production_order.__dict__,
        'remaining_quantity': production_order.remaining_quantity,
        'completion_percentage': production_order.completion_percentage,
        'is_overdue': production_order.is_overdue,
        'is_ready_for_production': production_order.is_ready_for_production,
        'product': {
            'product_id': production_order.product.product_id,
            'product_code': production_order.product.product_code,
            'product_name': production_order.product.product_name,
            'unit_of_measure': production_order.product.unit_of_measure
        } if production_order.product else None,
        'bom': {
            'bom_id': production_order.bom.bom_id,
            'bom_name': production_order.bom.bom_name,
            'bom_version': production_order.bom.bom_version,
            'base_quantity': production_order.bom.base_quantity
        } if production_order.bom else None,
        'warehouse': {
            'warehouse_id': production_order.warehouse.warehouse_id,
            'warehouse_code': production_order.warehouse.warehouse_code,
            'warehouse_name': production_order.warehouse.warehouse_name
        } if production_order.warehouse else None,
        'production_order_components': [
            {
                **comp.__dict__,
                'component_product': {
                    'product_id': comp.component_product.product_id,
                    'product_code': comp.component_product.product_code,
                    'product_name': comp.component_product.product_name,
                    'unit_of_measure': comp.component_product.unit_of_measure
                } if comp.component_product else None
            }
            for comp in production_order.production_order_components
        ],
        'stock_allocations': [
            {
                **alloc.__dict__,
                'inventory_item': {
                    'inventory_item_id': alloc.inventory_item.inventory_item_id,
                    'batch_number': alloc.inventory_item.batch_number,
                    'quantity_in_stock': alloc.inventory_item.quantity_in_stock
                } if alloc.inventory_item else None
            }
            for alloc in production_order.stock_allocations
        ]
    }
    
    return ProductionOrderResponse(**order_dict)


@router.post("/", response_model=IDResponse)
def create_production_order(
    order_request: ProductionOrderCreate,
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("write:production"))  # Temporarily disabled for testing
):
    """
    Create new production order.
    
    Performs BOM explosion, stock availability check, and creates component requirements.
    """
    try:
        # Validate product and BOM
        product, bom = validate_bom_and_product(
            session, order_request.product_id, order_request.bom_id
        )
        
        # Check warehouse exists
        warehouse = session.query(Warehouse).filter(
            Warehouse.warehouse_id == order_request.warehouse_id
        ).first()
        if not warehouse:
            raise NotFoundError("Warehouse", order_request.warehouse_id)
        
        # Generate unique order number
        order_number = generate_production_order_number(session)
        
        # Create production order
        production_order = ProductionOrder(
            order_number=order_number,
            product_id=order_request.product_id,
            bom_id=order_request.bom_id,
            warehouse_id=order_request.warehouse_id,
            order_date=date.today(),
            planned_start_date=order_request.planned_start_date,
            planned_completion_date=order_request.planned_completion_date,
            planned_quantity=order_request.planned_quantity,
            completed_quantity=Decimal('0'),
            scrapped_quantity=Decimal('0'),
            status='PLANNED',
            priority=order_request.priority,
            estimated_cost=Decimal('0'),
            actual_cost=Decimal('0'),
            notes=order_request.notes
        )
        
        session.add(production_order)
        session.flush()  # Get the ID
        
        # Create components based on BOM
        components = create_production_order_components(session, production_order, bom)
        
        # Calculate estimated cost (basic calculation)
        estimated_cost = Decimal('0')
        for component in components:
            # Get average cost from inventory for this component
            avg_cost = session.query(func.avg(InventoryItem.unit_cost)).filter(
                and_(
                    InventoryItem.product_id == component.component_product_id,
                    InventoryItem.quantity_in_stock > 0
                )
            ).scalar() or Decimal('0')
            
            component.unit_cost = avg_cost
            estimated_cost += Decimal(str(avg_cost)) * component.required_quantity
        
        # Add labor and overhead costs from BOM
        if bom.labor_cost_per_unit:
            estimated_cost += Decimal(str(bom.labor_cost_per_unit)) * production_order.planned_quantity
        
        if bom.overhead_cost_per_unit:
            estimated_cost += Decimal(str(bom.overhead_cost_per_unit)) * production_order.planned_quantity
        
        production_order.estimated_cost = estimated_cost
        
        session.commit()
        
        return IDResponse(
            id=production_order.production_order_id,
            message=f"Production order {order_number} created successfully"
        )
        
    except Exception as e:
        session.rollback()
        if isinstance(e, (NotFoundError, HTTPException)):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to create production order: {str(e)}")


@router.put("/{order_id}", response_model=ProductionOrderResponse)
def update_production_order(
    order_id: int = Path(..., description="Production order ID"),
    order_update: ProductionOrderUpdate = ...,
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("write:production"))  # Temporarily disabled for testing
):
    """Update production order information."""
    # Get existing production order
    production_order = session.query(ProductionOrder).filter(
        ProductionOrder.production_order_id == order_id
    ).first()
    
    if not production_order:
        raise NotFoundError("Production Order", order_id)
    
    # Check if order can be updated (only PLANNED and RELEASED orders can be modified)
    if production_order.status in ['COMPLETED', 'CANCELLED']:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update production order in {production_order.status} status"
        )
    
    try:
        # Update fields that are provided
        update_data = order_update.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            if hasattr(production_order, field):
                setattr(production_order, field, value)
        
        production_order.updated_at = datetime.now()
        
        session.commit()
        
        # Return updated order
        return get_production_order(order_id, session)
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update production order: {str(e)}")


@router.delete("/{order_id}", response_model=MessageResponse)
def delete_production_order(
    order_id: int = Path(..., description="Production order ID"),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("delete:production"))  # Temporarily disabled for testing
):
    """Delete production order with stock reservation cleanup."""
    # Get production order
    production_order = session.query(ProductionOrder).filter(
        ProductionOrder.production_order_id == order_id
    ).first()
    
    if not production_order:
        raise NotFoundError("Production Order", order_id)
    
    # Check if order can be deleted (only PLANNED orders can be deleted)
    if production_order.status not in ['PLANNED', 'CANCELLED']:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete production order in {production_order.status} status"
        )
    
    try:
        # Initialize MRP service for stock operations
        mrp_service = MRPAnalysisService(session)
        
        # Release any stock reservations before deleting
        released_count = 0
        try:
            released_count = mrp_service.release_stock_reservations(order_id)
        except Exception as e:
            print(f"Warning: Failed to release reservations for order {order_id}: {str(e)}")
        
        # Delete the order (cascading will handle components and allocations)
        session.delete(production_order)
        session.commit()
        
        message = f"Production order {production_order.order_number} deleted successfully"
        if released_count > 0:
            message += f" with {released_count} stock reservations released"
        
        return MessageResponse(message=message)
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete production order: {str(e)}")


@router.put("/{order_id}/status", response_model=ProductionOrderResponse)
def update_production_order_status(
    order_id: int = Path(..., description="Production order ID"),
    status_update: ProductionOrderStatusUpdate = ...,
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("write:production"))  # Temporarily disabled for testing
):
    """
    Update production order status with stock operations.
    
    Manages status transitions and triggers appropriate workflows including:
    - Stock consumption when status changes to COMPLETED
    - Stock reservations when status changes to RELEASED
    """
    # Get production order
    production_order = session.query(ProductionOrder).filter(
        ProductionOrder.production_order_id == order_id
    ).first()
    
    if not production_order:
        raise NotFoundError("Production Order", order_id)
    
    try:
        new_status = status_update.status.value
        old_status = production_order.status
        
        # Validate status transition
        valid_transitions = {
            'PLANNED': ['RELEASED', 'CANCELLED'],
            'RELEASED': ['IN_PROGRESS', 'ON_HOLD', 'CANCELLED'],
            'IN_PROGRESS': ['COMPLETED', 'ON_HOLD', 'CANCELLED'],
            'ON_HOLD': ['RELEASED', 'CANCELLED'],
            'COMPLETED': [],  # Final state
            'CANCELLED': []   # Final state
        }
        
        if new_status not in valid_transitions.get(old_status, []):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status transition from {old_status} to {new_status}"
            )
        
        # Initialize MRP service for stock operations
        mrp_service = MRPAnalysisService(session)
        
        # Handle specific status changes with stock operations
        if new_status == 'COMPLETED' and old_status in ['IN_PROGRESS', 'RELEASED']:
            # Consume reserved stock using FIFO
            try:
                consumption_records = mrp_service.consume_stock_for_production(order_id)
                
                # Add consumption note
                consumption_summary = f"Consumed {len(consumption_records)} stock batches"
                if status_update.notes:
                    status_update.notes += f" | {consumption_summary}"
                else:
                    status_update.notes = consumption_summary
                    
                # Mark production as completed
                production_order.actual_completion_date = date.today()
                
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot complete production: {str(e)}"
                )
        
        elif new_status == 'RELEASED' and old_status == 'PLANNED':
            # Reserve stock when releasing for production
            try:
                reservations = mrp_service.reserve_stock_for_production(order_id, "SYSTEM")
                
                # Add reservation note
                reservation_summary = f"Reserved stock for {len(reservations)} components"
                if status_update.notes:
                    status_update.notes += f" | {reservation_summary}"
                else:
                    status_update.notes = reservation_summary
                    
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot reserve stock for production: {str(e)}"
                )
        
        elif new_status == 'IN_PROGRESS' and old_status == 'RELEASED':
            production_order.start_production()
            production_order.actual_start_date = date.today()
        
        elif new_status == 'CANCELLED' and old_status in ['PLANNED', 'RELEASED', 'IN_PROGRESS', 'ON_HOLD']:
            # Release stock reservations when cancelling
            try:
                released_count = mrp_service.release_stock_reservations(order_id)
                if released_count > 0:
                    cancellation_summary = f"Released {released_count} stock reservations"
                    if status_update.notes:
                        status_update.notes += f" | {cancellation_summary}"
                    else:
                        status_update.notes = cancellation_summary
            except Exception as e:
                # Don't fail the cancellation if reservation release fails
                print(f"Warning: Failed to release reservations for order {order_id}: {str(e)}")
        
        # Update the status
        production_order.status = new_status
        
        # Add notes if provided
        if status_update.notes:
            current_notes = production_order.notes or ""
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status_note = f"\n[{timestamp}] Status changed to {new_status}: {status_update.notes}"
            production_order.notes = current_notes + status_note
        
        production_order.updated_at = datetime.now()
        
        session.commit()
        
        # Return updated order
        return get_production_order(order_id, session)
        
    except Exception as e:
        session.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to update production order status: {str(e)}")


@router.get("/{order_id}/components", response_model=ProductionComponentList)
def get_production_order_components(
    order_id: int = Path(..., description="Production order ID"),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("read:production"))  # Temporarily disabled for testing
):
    """
    Get component requirements and allocations for production order.
    
    Shows required vs allocated vs consumed quantities.
    """
    # Check if production order exists
    production_order = session.query(ProductionOrder).filter(
        ProductionOrder.production_order_id == order_id
    ).first()
    
    if not production_order:
        raise NotFoundError("Production Order", order_id)
    
    # Get components with related data
    components = session.query(ProductionOrderComponent).options(
        joinedload(ProductionOrderComponent.component_product)
    ).filter(
        ProductionOrderComponent.production_order_id == order_id
    ).all()
    
    # Convert to response format
    component_responses = []
    fully_allocated_count = 0
    not_allocated_count = 0
    
    for comp in components:
        comp_dict = {
            **comp.__dict__,
            'component_product': {
                'product_id': comp.component_product.product_id,
                'product_code': comp.component_product.product_code,
                'product_name': comp.component_product.product_name,
                'unit_of_measure': comp.component_product.unit_of_measure
            } if comp.component_product else None
        }
        component_responses.append(ProductionOrderComponentResponse(**comp_dict))
        
        # Count allocation status
        if comp.allocation_status == 'FULLY_ALLOCATED':
            fully_allocated_count += 1
        elif comp.allocation_status == 'NOT_ALLOCATED':
            not_allocated_count += 1
    
    return ProductionComponentList(
        components=component_responses,
        order_id=order_id,
        total_components=len(components),
        fully_allocated_count=fully_allocated_count,
        not_allocated_count=not_allocated_count
    )


@router.post("/{order_id}/complete", response_model=ProductionOrderResponse)
def complete_production_order(
    order_id: int = Path(..., description="Production order ID"),
    completion_data: ProductionOrderCompletion = ...,
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("approve:production"))  # Temporarily disabled for testing
):
    """
    Complete production order.
    
    Processes FIFO consumption, creates finished goods inventory, and updates costs.
    """
    # Get production order
    production_order = session.query(ProductionOrder).filter(
        ProductionOrder.production_order_id == order_id
    ).first()
    
    if not production_order:
        raise NotFoundError("Production Order", order_id)
    
    # Validate order can be completed
    if production_order.status not in ['IN_PROGRESS', 'RELEASED']:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot complete production order in {production_order.status} status"
        )
    
    try:
        # Complete the production order
        production_order.complete_production(
            completion_data.completed_quantity,
            completion_data.scrapped_quantity
        )
        
        # Add completion notes
        if completion_data.notes:
            current_notes = production_order.notes or ""
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            completion_note = f"\n[{timestamp}] Production completed - Completed: {completion_data.completed_quantity}, Scrapped: {completion_data.scrapped_quantity}: {completion_data.notes}"
            production_order.notes = current_notes + completion_note
        
        production_order.updated_at = datetime.now()
        
        # TODO: Implement FIFO stock consumption and finished goods creation
        # This would involve:
        # 1. Consume allocated stock using FIFO
        # 2. Create finished goods inventory
        # 3. Calculate actual costs
        # 4. Update component consumption records
        
        session.commit()
        
        # Return updated order
        return get_production_order(order_id, session)
        
    except Exception as e:
        session.rollback()
        if isinstance(e, (ValueError, HTTPException)):
            raise HTTPException(status_code=400, detail=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to complete production order: {str(e)}")


@router.get("/{order_id}/stock-analysis", response_model=Dict)
def analyze_production_stock(
    order_id: int = Path(..., description="Production order ID"),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("read:production"))  # Temporarily disabled for testing
):
    """
    Analyze stock availability for production order with nested BOM explosion.
    
    Performs comprehensive analysis of component requirements, stock availability,
    and identifies missing materials or semi-finished products.
    """
    # Get production order
    production_order = session.query(ProductionOrder).filter(
        ProductionOrder.production_order_id == order_id
    ).first()
    
    if not production_order:
        raise NotFoundError("Production Order", order_id)
    
    try:
        # Initialize MRP analysis service
        mrp_service = MRPAnalysisService(session)
        
        # Perform stock analysis
        analysis_result = mrp_service.analyze_stock_availability(
            product_id=production_order.product_id,
            bom_id=production_order.bom_id,
            planned_quantity=production_order.planned_quantity,
            warehouse_id=production_order.warehouse_id,
            production_order_id=order_id
        )
        
        # Convert to response format
        return {
            "production_order_id": analysis_result.production_order_id,
            "product": {
                "product_id": analysis_result.product_id,
                "product_code": analysis_result.product_code,
                "product_name": analysis_result.product_name,
            },
            "planned_quantity": analysis_result.planned_quantity,
            "can_produce": analysis_result.can_produce,
            "shortage_exists": analysis_result.shortage_exists,
            "component_requirements": [
                {
                    "product_id": comp.product_id,
                    "product_code": comp.product_code,
                    "product_name": comp.product_name,
                    "required_quantity": comp.required_quantity,
                    "available_quantity": comp.available_quantity,
                    "shortage_quantity": comp.shortage_quantity,
                    "unit_cost": comp.unit_cost,
                    "total_cost": comp.total_cost,
                    "is_semi_finished": comp.is_semi_finished,
                    "has_bom": comp.has_bom,
                    "bom_id": comp.bom_id
                }
                for comp in analysis_result.component_requirements
            ],
            "semi_finished_shortages": [
                {
                    "product_id": comp.product_id,
                    "product_code": comp.product_code,
                    "product_name": comp.product_name,
                    "shortage_quantity": comp.shortage_quantity,
                    "has_bom": comp.has_bom,
                    "bom_id": comp.bom_id
                }
                for comp in analysis_result.semi_finished_shortages
            ],
            "raw_material_shortages": [
                {
                    "product_id": comp.product_id,
                    "product_code": comp.product_code,
                    "product_name": comp.product_name,
                    "shortage_quantity": comp.shortage_quantity,
                    "unit_cost": comp.unit_cost
                }
                for comp in analysis_result.raw_material_shortages
            ],
            "total_estimated_cost": analysis_result.total_estimated_cost,
            "analysis_date": analysis_result.analysis_date
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze production stock: {str(e)}")


@router.post("/create-with-analysis", response_model=Dict)
def create_production_order_with_analysis(
    order_request: ProductionOrderCreate,
    auto_create_dependencies: bool = Query(True, description="Automatically create dependent production orders"),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("write:production"))  # Temporarily disabled for testing
):
    """
    Create production order with automatic stock analysis and nested production planning.
    
    Performs BOM explosion, analyzes stock availability, and optionally creates
    dependent production orders for missing semi-finished products.
    """
    try:
        # Initialize MRP analysis service
        mrp_service = MRPAnalysisService(session)
        
        # First perform stock analysis
        analysis_result = mrp_service.analyze_stock_availability(
            product_id=order_request.product_id,
            bom_id=order_request.bom_id,
            planned_quantity=order_request.planned_quantity,
            warehouse_id=order_request.warehouse_id
        )
        
        # Create the main production order
        main_order_response = create_production_order(order_request, session)
        main_order_id = main_order_response.id
        
        dependent_orders = []
        nested_orders_created = []  # Frontend expects this
        production_tree = None
        warnings = []  # Frontend expects this
        
        # Add warnings for shortages
        if analysis_result.shortage_exists:
            if analysis_result.semi_finished_shortages:
                warnings.append(f"{len(analysis_result.semi_finished_shortages)} semi-finished products are short")
            if analysis_result.raw_material_shortages:
                warnings.append(f"{len(analysis_result.raw_material_shortages)} raw materials are short")
        
        if auto_create_dependencies and analysis_result.semi_finished_shortages:
            # Create nested production plan
            production_tree = mrp_service.create_nested_production_plan(
                product_id=order_request.product_id,
                bom_id=order_request.bom_id,
                planned_quantity=order_request.planned_quantity,
                warehouse_id=order_request.warehouse_id,
                target_date=order_request.planned_completion_date,
                priority=order_request.priority
            )
            
            # Create dependent production orders for semi-finished shortages
            dependent_orders = _create_dependent_orders(
                production_tree, session, main_order_id
            )
            
            # Format nested orders for frontend
            nested_orders_created = [{
                "production_order_id": order["production_order_id"],
                "order_number": order["order_number"],
                "product_name": order["product_name"],
                "planned_quantity": float(order["planned_quantity"])
            } for order in dependent_orders]
        
        # Try to reserve stock for the main production order
        reservations = []
        try:
            reservations = mrp_service.reserve_stock_for_production(
                main_order_id, "SYSTEM"
            )
        except ValueError as e:
            warnings.append(f"Stock reservation failed: {str(e)}")
        
        session.commit()
        
        return {
            "main_production_order": {
                "production_order_id": main_order_id,
                "message": f"Production order created successfully"
            },
            "stock_analysis": {
                "can_produce": analysis_result.can_produce,
                "shortage_exists": analysis_result.shortage_exists,
                "semi_finished_shortages": len(analysis_result.semi_finished_shortages),
                "raw_material_shortages": len(analysis_result.raw_material_shortages),
                "total_estimated_cost": analysis_result.total_estimated_cost
            },
            "dependent_orders": dependent_orders,
            "nested_orders_created": nested_orders_created,  # Frontend expects this
            "warnings": warnings,  # Frontend expects this
            "stock_reservations": len(reservations),
            "production_tree": _format_production_tree(production_tree) if production_tree else None
        }
        
    except Exception as e:
        session.rollback()
        if isinstance(e, (NotFoundError, HTTPException)):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to create production order with analysis: {str(e)}")


@router.post("/analyze-stock", response_model=Dict)
def analyze_stock_availability(
    request: StockAnalysisRequest,
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("read:production"))  # Temporarily disabled for testing
):
    """
    Analyze stock availability for production without creating a production order.
    
    This endpoint performs BOM explosion and stock analysis to determine if 
    sufficient materials are available for production.
    """
    try:
        # Initialize MRP analysis service
        mrp_service = MRPAnalysisService(session)
        
        # Get the BOM and product information
        bom = session.query(BillOfMaterials).filter(
            BillOfMaterials.bom_id == request.bom_id
        ).first()
        
        if not bom:
            raise NotFoundError("BOM", request.bom_id)
        
        # Get warehouse information
        warehouse = session.query(Warehouse).filter(
            Warehouse.warehouse_id == request.warehouse_id
        ).first()
        
        if not warehouse:
            raise NotFoundError("Warehouse", request.warehouse_id)
        
        # Perform stock analysis
        analysis_result = mrp_service.analyze_stock_availability(
            product_id=bom.parent_product_id,
            bom_id=request.bom_id,
            planned_quantity=request.quantity_to_produce,
            warehouse_id=request.warehouse_id
        )
        
        # Format the response to match frontend expectations
        analysis_items = []
        missing_materials = []
        
        # Process raw material shortages
        for shortage in analysis_result.raw_material_shortages:
            item = {
                "product_id": shortage.product_id,
                "product_code": shortage.product_code,
                "product_name": shortage.product_name,
                "required_quantity": float(shortage.required_quantity),
                "available_quantity": float(shortage.available_quantity),
                "sufficient_stock": False,
                "shortage_quantity": float(shortage.shortage_quantity),
                "unit_cost": float(shortage.unit_cost) if shortage.unit_cost else 0,
                "total_cost": float(shortage.total_cost) if shortage.total_cost else 0,
                "product_type": "RAW_MATERIAL",
                "is_semi_finished": False
            }
            analysis_items.append(item)
            missing_materials.append(item)
        
        # Process semi-finished shortages
        for shortage in analysis_result.semi_finished_shortages:
            item = {
                "product_id": shortage.product_id,
                "product_code": shortage.product_code,
                "product_name": shortage.product_name,
                "required_quantity": float(shortage.required_quantity),
                "available_quantity": float(shortage.available_quantity),
                "sufficient_stock": False,
                "shortage_quantity": float(shortage.shortage_quantity),
                "unit_cost": float(shortage.unit_cost) if shortage.unit_cost else 0,
                "total_cost": float(shortage.total_cost) if shortage.total_cost else 0,
                "product_type": "SEMI_FINISHED",
                "is_semi_finished": True
            }
            analysis_items.append(item)
            missing_materials.append(item)
        
        # Process available materials (those with sufficient stock)  
        for comp in analysis_result.component_requirements:
            if comp.available_quantity >= comp.required_quantity:
                item = {
                    "product_id": comp.product_id,
                    "product_code": comp.product_code,
                    "product_name": comp.product_name,
                    "required_quantity": float(comp.required_quantity),
                    "available_quantity": float(comp.available_quantity),
                    "sufficient_stock": True,
                    "unit_cost": float(comp.unit_cost) if comp.unit_cost else 0,
                    "total_cost": float(comp.total_cost) if comp.total_cost else 0,
                    "product_type": "SEMI_FINISHED" if comp.is_semi_finished else "RAW_MATERIAL",
                    "is_semi_finished": comp.is_semi_finished
                }
                analysis_items.append(item)
        
        return {
            "bom_id": request.bom_id,
            "bom_name": bom.bom_name,
            "quantity_to_produce": float(request.quantity_to_produce),
            "warehouse_id": request.warehouse_id,
            "warehouse_name": warehouse.warehouse_name,
            "analysis_items": analysis_items,
            "can_produce": analysis_result.can_produce,
            "missing_materials": missing_materials,
            "total_material_cost": float(analysis_result.total_estimated_cost),
            "analysis_date": datetime.now().isoformat()
        }
        
    except Exception as e:
        if isinstance(e, (NotFoundError, HTTPException)):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to analyze stock: {str(e)}")


@router.put("/{order_id}/reserve-stock", response_model=Dict)
def reserve_production_stock(
    order_id: int = Path(..., description="Production order ID"),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("write:production"))  # Temporarily disabled for testing
):
    """
    Reserve stock for production order using FIFO allocation.
    
    Creates stock reservations for all components required by the production order.
    """
    # Check if production order exists
    production_order = session.query(ProductionOrder).filter(
        ProductionOrder.production_order_id == order_id
    ).first()
    
    if not production_order:
        raise NotFoundError("Production Order", order_id)
    
    if production_order.status not in ['PLANNED', 'RELEASED']:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reserve stock for production order in {production_order.status} status"
        )
    
    try:
        # Initialize MRP analysis service
        mrp_service = MRPAnalysisService(session)
        
        # Reserve stock using FIFO
        reservations = mrp_service.reserve_stock_for_production(
            order_id, "SYSTEM"  # In real implementation, get from current_user
        )
        
        session.commit()
        
        return {
            "production_order_id": order_id,
            "reservations_created": len(reservations),
            "reserved_items": [
                {
                    "reservation_id": res.reservation_id,
                    "product_id": res.product_id,
                    "reserved_quantity": res.reserved_quantity,
                    "warehouse_id": res.warehouse_id
                }
                for res in reservations
            ],
            "message": f"Successfully reserved stock for {len(reservations)} components"
        }
        
    except Exception as e:
        session.rollback()
        if isinstance(e, ValueError):
            raise HTTPException(status_code=400, detail=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to reserve stock: {str(e)}")


@router.post("/{order_id}/cancel", response_model=MessageResponse)
def cancel_production_order_with_cleanup(
    order_id: int = Path(..., description="Production order ID"),
    cascade_cancel: bool = Query(False, description="Cancel dependent production orders"),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("write:production"))  # Temporarily disabled for testing
):
    """
    Cancel production order with stock reservation cleanup.
    
    Cancels the production order and releases all associated stock reservations.
    Optionally cancels dependent production orders in cascade.
    """
    # Get production order
    production_order = session.query(ProductionOrder).filter(
        ProductionOrder.production_order_id == order_id
    ).first()
    
    if not production_order:
        raise NotFoundError("Production Order", order_id)
    
    if production_order.status in ['COMPLETED', 'CANCELLED']:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel production order in {production_order.status} status"
        )
    
    try:
        # Initialize MRP analysis service
        mrp_service = MRPAnalysisService(session)
        
        # Release stock reservations
        released_reservations = mrp_service.release_stock_reservations(order_id)
        
        # Cancel the production order
        production_order.status = 'CANCELLED'
        
        cancelled_dependencies = 0
        if cascade_cancel:
            # Cancel dependent production orders
            from models.production import ProductionDependency
            dependencies = session.query(ProductionDependency).filter(
                ProductionDependency.parent_production_order_id == order_id
            ).all()
            
            for dep in dependencies:
                dependent_order = session.query(ProductionOrder).get(
                    dep.dependent_production_order_id
                )
                if dependent_order and dependent_order.status not in ['COMPLETED', 'CANCELLED']:
                    # Recursively cancel dependent order
                    mrp_service.release_stock_reservations(dep.dependent_production_order_id)
                    dependent_order.status = 'CANCELLED'
                    dep.cancel_dependency()
                    cancelled_dependencies += 1
        
        # Add cancellation note
        current_notes = production_order.notes or ""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cancellation_note = f"\n[{timestamp}] Production order cancelled with cleanup"
        production_order.notes = current_notes + cancellation_note
        production_order.updated_at = datetime.now()
        
        session.commit()
        
        message = f"Production order {production_order.order_number} cancelled successfully"
        if released_reservations > 0:
            message += f" with {released_reservations} stock reservations released"
        if cancelled_dependencies > 0:
            message += f" and {cancelled_dependencies} dependent orders cancelled"
        
        return MessageResponse(message=message)
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to cancel production order: {str(e)}")


@router.get("/{order_id}/enhanced", response_model=Dict)
def get_enhanced_production_order(
    order_id: int = Path(..., description="Production order ID"),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("read:production"))  # Temporarily disabled for testing
):
    """
    Get enhanced production order details with comprehensive information.
    
    Returns production order with stock analysis, reservations, and component details.
    """
    # Get production order with all related data
    production_order = session.query(ProductionOrder).options(
        joinedload(ProductionOrder.product),
        joinedload(ProductionOrder.bom),
        joinedload(ProductionOrder.warehouse),
        joinedload(ProductionOrder.production_order_components).joinedload(
            ProductionOrderComponent.component_product
        )
    ).filter(ProductionOrder.production_order_id == order_id).first()
    
    if not production_order:
        raise NotFoundError("Production Order", order_id)
    
    try:
        # Initialize MRP analysis service
        mrp_service = MRPAnalysisService(session)
        
        # Get stock analysis for current state
        analysis_result = mrp_service.analyze_stock_availability(
            product_id=production_order.product_id,
            bom_id=production_order.bom_id,
            planned_quantity=production_order.planned_quantity,
            warehouse_id=production_order.warehouse_id,
            production_order_id=order_id
        )
        
        # Get active stock reservations
        reservations = session.query(StockReservation).filter(
            and_(
                StockReservation.reserved_for_type == 'PRODUCTION_ORDER',
                StockReservation.reserved_for_id == order_id,
                StockReservation.status == 'ACTIVE'
            )
        ).all()
        
        # Build enhanced response
        enhanced_order = {
            'production_order_id': production_order.production_order_id,
            'order_number': production_order.order_number,
            'product_id': production_order.product_id,
            'bom_id': production_order.bom_id,
            'warehouse_id': production_order.warehouse_id,
            'order_date': production_order.order_date.isoformat() if production_order.order_date else None,
            'planned_start_date': production_order.planned_start_date.isoformat() if production_order.planned_start_date else None,
            'planned_completion_date': production_order.planned_completion_date.isoformat() if production_order.planned_completion_date else None,
            'actual_start_date': production_order.actual_start_date.isoformat() if production_order.actual_start_date else None,
            'actual_completion_date': production_order.actual_completion_date.isoformat() if production_order.actual_completion_date else None,
            'planned_quantity': float(production_order.planned_quantity),
            'completed_quantity': float(production_order.completed_quantity),
            'scrapped_quantity': float(production_order.scrapped_quantity),
            'status': production_order.status,
            'priority': production_order.priority,
            'estimated_cost': float(production_order.estimated_cost),
            'actual_cost': float(production_order.actual_cost),
            'notes': production_order.notes,
            'created_at': production_order.created_at.isoformat() if production_order.created_at else None,
            'updated_at': production_order.updated_at.isoformat() if production_order.updated_at else None,
            'remaining_quantity': float(production_order.remaining_quantity) if production_order.remaining_quantity else 0.0,
            'completion_percentage': float(production_order.completion_percentage) if production_order.completion_percentage else 0.0,
            'is_overdue': production_order.is_overdue,
            'is_ready_for_production': production_order.is_ready_for_production,
            'product': {
                'product_id': production_order.product.product_id,
                'product_code': production_order.product.product_code,
                'product_name': production_order.product.product_name,
                'unit_of_measure': production_order.product.unit_of_measure
            } if production_order.product else None,
            'bom': {
                'bom_id': production_order.bom.bom_id,
                'bom_name': production_order.bom.bom_name,
                'bom_version': production_order.bom.bom_version,
                'base_quantity': production_order.bom.base_quantity
            } if production_order.bom else None,
            'warehouse': {
                'warehouse_id': production_order.warehouse.warehouse_id,
                'warehouse_code': production_order.warehouse.warehouse_code,
                'warehouse_name': production_order.warehouse.warehouse_name
            } if production_order.warehouse else None,
            'stock_analysis': {
                'can_produce': analysis_result.can_produce,
                'shortage_exists': analysis_result.shortage_exists,
                'component_requirements': [{
                    'product_id': comp.product_id,
                    'product_code': comp.product_code,
                    'product_name': comp.product_name,
                    'required_quantity': float(comp.required_quantity),
                    'available_quantity': float(comp.available_quantity),
                    'shortage_quantity': float(comp.shortage_quantity),
                    'unit_cost': float(comp.unit_cost),
                    'is_semi_finished': comp.is_semi_finished
                } for comp in analysis_result.component_requirements],
                'total_estimated_cost': float(analysis_result.total_estimated_cost)
            },
            'stock_reservations': [{
                'reservation_id': res.reservation_id,
                'product_id': res.product_id,
                'warehouse_id': res.warehouse_id,
                'reserved_quantity': float(res.reserved_quantity),
                'status': res.status,
                'reservation_date': res.reservation_date.isoformat() if res.reservation_date else None,
                'reserved_by': res.reserved_by
            } for res in reservations],
            'production_order_components': [{
                'po_component_id': comp.po_component_id,
                'component_product_id': comp.component_product_id,
                'required_quantity': float(comp.required_quantity),
                'allocated_quantity': float(comp.allocated_quantity),
                'consumed_quantity': float(comp.consumed_quantity),
                'unit_cost': float(comp.unit_cost),
                'allocation_status': comp.allocation_status,
                'component_product': {
                    'product_id': comp.component_product.product_id,
                    'product_code': comp.component_product.product_code,
                    'product_name': comp.component_product.product_name,
                    'unit_of_measure': comp.component_product.unit_of_measure
                } if comp.component_product else None
            } for comp in production_order.production_order_components]
        }
        
        return enhanced_order
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get enhanced production order: {str(e)}")


@router.get("/{order_id}/reservations", response_model=Dict)
def get_production_order_reservations(
    order_id: int = Path(..., description="Production order ID"),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("read:production"))  # Temporarily disabled for testing
):
    """
    Get stock reservations for a production order.
    
    Returns detailed information about stock reservations including inventory items.
    """
    # Check if production order exists
    production_order = session.query(ProductionOrder).filter(
        ProductionOrder.production_order_id == order_id
    ).first()
    
    if not production_order:
        raise NotFoundError("Production Order", order_id)
    
    try:
        # Get all reservations for this production order
        reservations = session.query(StockReservation).filter(
            and_(
                StockReservation.reserved_for_type == 'PRODUCTION_ORDER',
                StockReservation.reserved_for_id == order_id
            )
        ).order_by(StockReservation.reservation_date).all()
        
        # Group reservations by product
        reservations_by_product = {}
        total_reservations = 0
        active_reservations = 0
        consumed_reservations = 0
        
        for res in reservations:
            product_id = res.product_id
            
            if product_id not in reservations_by_product:
                # Get product information
                product = session.query(Product).get(product_id)
                reservations_by_product[product_id] = {
                    'product': {
                        'product_id': product_id,
                        'product_code': product.product_code if product else 'UNKNOWN',
                        'product_name': product.product_name if product else 'Unknown Product'
                    },
                    'reservations': [],
                    'total_reserved': Decimal('0'),
                    'total_consumed': Decimal('0'),
                    'active_count': 0,
                    'consumed_count': 0
                }
            
            # Add reservation details
            reservations_by_product[product_id]['reservations'].append({
                'reservation_id': res.reservation_id,
                'warehouse_id': res.warehouse_id,
                'reserved_quantity': float(res.reserved_quantity),
                'status': res.status,
                'reservation_date': res.reservation_date.isoformat() if res.reservation_date else None,
                'expiry_date': res.expiry_date.isoformat() if res.expiry_date else None,
                'reserved_by': res.reserved_by,
                'notes': res.notes
            })
            
            # Update totals
            if res.status == 'ACTIVE':
                reservations_by_product[product_id]['total_reserved'] += res.reserved_quantity
                reservations_by_product[product_id]['active_count'] += 1
                active_reservations += 1
            elif res.status == 'CONSUMED':
                reservations_by_product[product_id]['total_consumed'] += res.reserved_quantity
                reservations_by_product[product_id]['consumed_count'] += 1
                consumed_reservations += 1
            
            total_reservations += 1
        
        # Convert to list format
        reservation_details = [{
            **details,
            'total_reserved': float(details['total_reserved']),
            'total_consumed': float(details['total_consumed'])
        } for details in reservations_by_product.values()]
        
        return {
            'production_order_id': order_id,
            'order_number': production_order.order_number,
            'status': production_order.status,
            'reservation_summary': {
                'total_reservations': total_reservations,
                'active_reservations': active_reservations,
                'consumed_reservations': consumed_reservations,
                'products_with_reservations': len(reservations_by_product)
            },
            'reservations_by_product': reservation_details
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get production order reservations: {str(e)}")


@router.get("/{order_id}/production-tree", response_model=Dict)
def get_production_dependency_tree(
    order_id: int = Path(..., description="Production order ID"),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("read:production"))  # Temporarily disabled for testing
):
    """
    Get production dependency tree showing nested production order relationships.
    
    Returns hierarchical view of production dependencies and their status.
    """
    # Get production order
    production_order = session.query(ProductionOrder).filter(
        ProductionOrder.production_order_id == order_id
    ).first()
    
    if not production_order:
        raise NotFoundError("Production Order", order_id)
    
    try:
        # Build dependency tree
        tree = _build_dependency_tree(order_id, session, set())
        
        return {
            "production_order_id": order_id,
            "root_product": {
                "product_id": production_order.product_id,
                "product_code": production_order.product.product_code,
                "product_name": production_order.product.product_name,
                "planned_quantity": production_order.planned_quantity,
                "status": production_order.status
            },
            "dependency_tree": tree,
            "total_dependencies": _count_dependencies(tree)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get production tree: {str(e)}")


def _create_dependent_orders(production_tree: ProductionPlanNode, session: Session, parent_order_id: int) -> List[Dict]:
    """Create dependent production orders based on production tree."""
    dependent_orders = []
    
    for dependency in production_tree.dependencies:
        # Create production order for this dependency
        order_number = generate_production_order_number(session)
        
        dependent_order = ProductionOrder(
            order_number=order_number,
            product_id=dependency.product_id,
            bom_id=dependency.bom_id,
            warehouse_id=dependency.warehouse_id,
            order_date=date.today(),
            planned_quantity=dependency.required_quantity,
            status='PLANNED',
            priority=dependency.priority,
            estimated_cost=dependency.estimated_cost,
            notes=f'Auto-created dependency for production order {parent_order_id}'
        )
        
        session.add(dependent_order)
        session.flush()
        
        # Create dependency relationship
        from models.production import ProductionDependency
        dep_relationship = ProductionDependency(
            parent_production_order_id=parent_order_id,
            dependent_production_order_id=dependent_order.production_order_id,
            dependency_type='COMPONENT',
            dependency_quantity=dependency.required_quantity,
            status='PENDING'
        )
        
        session.add(dep_relationship)
        
        # Create components for the dependent order
        bom = session.query(BillOfMaterials).get(dependency.bom_id)
        create_production_order_components(session, dependent_order, bom)
        
        dependent_orders.append({
            "production_order_id": dependent_order.production_order_id,
            "order_number": order_number,
            "product_code": dependency.product_code,
            "product_name": dependency.product_name,
            "planned_quantity": dependency.required_quantity,
            "priority": dependency.priority
        })
        
        # Recursively create orders for nested dependencies
        nested_orders = _create_dependent_orders(dependency, session, dependent_order.production_order_id)
        dependent_orders.extend(nested_orders)
    
    return dependent_orders


def _format_production_tree(tree: ProductionPlanNode) -> Dict:
    """Format production tree for API response."""
    return {
        "product_id": tree.product_id,
        "product_code": tree.product_code,
        "product_name": tree.product_name,
        "required_quantity": tree.required_quantity,
        "bom_id": tree.bom_id,
        "warehouse_id": tree.warehouse_id,
        "priority": tree.priority,
        "estimated_cost": tree.estimated_cost,
        "dependencies": [_format_production_tree(dep) for dep in tree.dependencies]
    }


def _build_dependency_tree(order_id: int, session: Session, visited: Set[int]) -> Dict:
    """Build dependency tree recursively."""
    if order_id in visited:
        return {"error": "Circular dependency detected"}
    
    visited.add(order_id)
    
    # Get production order
    order = session.query(ProductionOrder).get(order_id)
    if not order:
        return {}
    
    # Get dependencies
    from models.production import ProductionDependency
    dependencies = session.query(ProductionDependency).filter(
        ProductionDependency.parent_production_order_id == order_id
    ).all()
    
    tree = {
        "production_order_id": order_id,
        "order_number": order.order_number,
        "product_code": order.product.product_code,
        "product_name": order.product.product_name,
        "planned_quantity": order.planned_quantity,
        "status": order.status,
        "dependencies": []
    }
    
    for dep in dependencies:
        dependent_tree = _build_dependency_tree(
            dep.dependent_production_order_id, session, visited.copy()
        )
        if dependent_tree:
            dependent_tree["dependency_info"] = {
                "dependency_type": dep.dependency_type,
                "dependency_quantity": dep.dependency_quantity,
                "status": dep.status,
                "required_by_date": dep.required_by_date
            }
            tree["dependencies"].append(dependent_tree)
    
    return tree


def _count_dependencies(tree: Dict) -> int:
    """Count total dependencies in tree."""
    count = len(tree.get("dependencies", []))
    for dep in tree.get("dependencies", []):
        count += _count_dependencies(dep)
    return count