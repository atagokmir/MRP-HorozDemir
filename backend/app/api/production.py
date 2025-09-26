"""
Production Management API endpoints for production orders and manufacturing workflows.
Handles production order lifecycle, component allocation, and completion processing.
"""

from typing import List, Optional, Dict, Set
from decimal import Decimal
from datetime import date, datetime
import logging
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


def _create_production_order_core(order_request: ProductionOrderCreate, allow_partial_stock: bool, session: Session) -> int:
    """
    Core business logic for creating a production order.
    Returns the created production order ID.
    """
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
    
    # Flush to ensure components are visible for stock reservation
    session.flush()
    
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
    
    return production_order.production_order_id


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


@router.get("/reservations/all", response_model=Dict)
def get_all_stock_reservations(
    status: Optional[str] = Query(None, description="Filter by reservation status"),
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    warehouse_id: Optional[int] = Query(None, description="Filter by warehouse ID"),
    production_order_id: Optional[int] = Query(None, description="Filter by production order ID"),
    pagination: PaginationParams = Depends(get_pagination_params),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("read:production"))  # Temporarily disabled for testing
):
    """
    Get all stock reservations with filtering and pagination.
    
    Returns comprehensive reservation data across all production orders.
    """
    try:
        # Build base query
        query = session.query(StockReservation).filter(
            StockReservation.reserved_for_type == 'PRODUCTION_ORDER'
        )
        
        # Apply filters
        if status:
            query = query.filter(StockReservation.status == status)
        if product_id:
            query = query.filter(StockReservation.product_id == product_id)
        if warehouse_id:
            query = query.filter(StockReservation.warehouse_id == warehouse_id)
        if production_order_id:
            query = query.filter(StockReservation.reserved_for_id == production_order_id)
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination and ordering
        reservations = query.order_by(desc(StockReservation.reservation_date)).offset(
            pagination.offset
        ).limit(pagination.page_size).all()
        
        # Build response with product and warehouse details
        reservation_details = []
        for res in reservations:
            # Get product details
            product = session.query(Product).get(res.product_id)
            warehouse = session.query(Warehouse).get(res.warehouse_id)
            production_order = session.query(ProductionOrder).get(res.reserved_for_id)
            
            reservation_details.append({
                'reservation_id': res.reservation_id,
                'product': {
                    'product_id': product.product_id,
                    'product_code': product.product_code,
                    'product_name': product.product_name,
                    'product_type': product.product_type
                } if product else None,
                'warehouse': {
                    'warehouse_id': warehouse.warehouse_id,
                    'warehouse_code': warehouse.warehouse_code,
                    'warehouse_name': warehouse.warehouse_name
                } if warehouse else None,
                'production_order': {
                    'production_order_id': production_order.production_order_id,
                    'order_number': production_order.order_number,
                    'status': production_order.status
                } if production_order else None,
                'reserved_quantity': float(res.reserved_quantity),
                'status': res.status,
                'reservation_date': res.reservation_date.isoformat() if res.reservation_date else None,
                'expiry_date': res.expiry_date.isoformat() if res.expiry_date else None,
                'reserved_by': res.reserved_by,
                'notes': res.notes
            })
        
        # Calculate pagination info
        total_pages = (total_count + pagination.page_size - 1) // pagination.page_size
        
        return {
            'reservations': reservation_details,
            'pagination': {
                'total_count': total_count,
                'page': pagination.page,
                'page_size': pagination.page_size,
                'total_pages': total_pages,
                'has_next': pagination.page < total_pages,
                'has_previous': pagination.page > 1
            },
            'summary': {
                'total_reservations': total_count,
                'active_reservations': len([r for r in reservations if r.status == 'ACTIVE']),
                'consumed_reservations': len([r for r in reservations if r.status == 'CONSUMED']),
                'released_reservations': len([r for r in reservations if r.status == 'RELEASED'])
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get reservations: {str(e)}")


@router.get("/component-allocation-status", response_model=Dict)
def get_component_allocation_status(
    status: Optional[str] = Query(None, description="Filter by allocation status"),
    product_id: Optional[int] = Query(None, description="Filter by component product ID"),
    pagination: PaginationParams = Depends(get_pagination_params),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("read:production"))  # Temporarily disabled for testing
):
    """
    Get component allocation status across all production orders.
    
    Returns detailed view of component allocation status for monitoring purposes.
    """
    try:
        # Build base query
        query = session.query(ProductionOrderComponent).options(
            joinedload(ProductionOrderComponent.component_product),
            joinedload(ProductionOrderComponent.production_order)
        )
        
        # Apply filters
        if status:
            query = query.filter(ProductionOrderComponent.allocation_status == status)
        if product_id:
            query = query.filter(ProductionOrderComponent.component_product_id == product_id)
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination and ordering
        components = query.order_by(
            desc(ProductionOrderComponent.production_order_id)
        ).offset(pagination.offset).limit(pagination.page_size).all()
        
        # Build response
        component_details = []
        status_summary = {'NOT_ALLOCATED': 0, 'PARTIALLY_ALLOCATED': 0, 'FULLY_ALLOCATED': 0, 'CONSUMED': 0}
        
        for comp in components:
            status_summary[comp.allocation_status] = status_summary.get(comp.allocation_status, 0) + 1
            
            component_details.append({
                'po_component_id': comp.po_component_id,
                'production_order': {
                    'production_order_id': comp.production_order.production_order_id,
                    'order_number': comp.production_order.order_number,
                    'status': comp.production_order.status,
                    'planned_quantity': float(comp.production_order.planned_quantity)
                } if comp.production_order else None,
                'component_product': {
                    'product_id': comp.component_product.product_id,
                    'product_code': comp.component_product.product_code,
                    'product_name': comp.component_product.product_name,
                    'product_type': comp.component_product.product_type
                } if comp.component_product else None,
                'required_quantity': float(comp.required_quantity),
                'allocated_quantity': float(comp.allocated_quantity),
                'consumed_quantity': float(comp.consumed_quantity),
                'unit_cost': float(comp.unit_cost),
                'allocation_status': comp.allocation_status,
                'allocation_percentage': float((comp.allocated_quantity / comp.required_quantity) * 100) if comp.required_quantity > 0 else 0
            })
        
        # Calculate pagination info
        total_pages = (total_count + pagination.page_size - 1) // pagination.page_size
        
        return {
            'components': component_details,
            'pagination': {
                'total_count': total_count,
                'page': pagination.page,
                'page_size': pagination.page_size,
                'total_pages': total_pages,
                'has_next': pagination.page < total_pages,
                'has_previous': pagination.page > 1
            },
            'allocation_summary': status_summary,
            'allocation_statistics': {
                'total_components': total_count,
                'fully_allocated_percentage': round((status_summary['FULLY_ALLOCATED'] / total_count) * 100, 2) if total_count > 0 else 0,
                'not_allocated_percentage': round((status_summary['NOT_ALLOCATED'] / total_count) * 100, 2) if total_count > 0 else 0
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get component allocation status: {str(e)}")


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
    allow_partial_stock: bool = Query(False, description="Allow creation with insufficient stock"),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("write:production"))  # Temporarily disabled for testing
):
    """
    Create new production order with mandatory stock validation.
    
    Performs BOM explosion, stock availability check, and creates component requirements.
    Only allows creation if raw materials are sufficient.
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
        
        # CRITICAL: Perform stock analysis BEFORE creating the order
        mrp_service = MRPAnalysisService(session)
        stock_analysis = mrp_service.analyze_stock_availability(
            product_id=order_request.product_id,
            bom_id=order_request.bom_id,
            planned_quantity=order_request.planned_quantity,
            warehouse_id=order_request.warehouse_id
        )
        
        # VALIDATION RULES:
        # 1. If raw materials are insufficient, BLOCK creation regardless of allow_partial_stock
        if len(stock_analysis.raw_material_shortages) > 0:
            shortage_details = [
                f"{shortage.product_code} ({shortage.product_name}): need {shortage.shortage_quantity} units"
                for shortage in stock_analysis.raw_material_shortages
            ]
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Cannot create production order: Raw materials insufficient",
                    "message": "You must add stock for raw materials before creating this production order.",
                    "shortage_type": "RAW_MATERIALS",
                    "missing_materials": shortage_details,
                    "can_create": False,
                    "suggestion": "Please add stock for the missing raw materials and try again."
                }
            )
        
        # 2. If only semi-finished products are missing, allow creation if allow_partial_stock=True
        if len(stock_analysis.semi_finished_shortages) > 0 and not allow_partial_stock:
            shortage_details = [
                f"{shortage.product_code} ({shortage.product_name}): need {shortage.shortage_quantity} units"
                for shortage in stock_analysis.semi_finished_shortages
            ]
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Semi-finished products insufficient",
                    "message": "Missing semi-finished products can be produced. Use 'add missing semi-products' option.",
                    "shortage_type": "SEMI_FINISHED",
                    "missing_materials": shortage_details,
                    "can_create": True,
                    "suggestion": "Enable 'allow_partial_stock' to create with missing semi-finished products, or add dependent production orders."
                }
            )
        
        # Create the production order using core business logic
        production_order_id = _create_production_order_core(order_request, allow_partial_stock, session)
        
        # CRITICAL FIX: Reserve stock immediately after creating production order
        # This is MANDATORY - if reservation fails, the order creation should fail
        mrp_service = MRPAnalysisService(session)
        reservations_created = []
        
        try:
            # Reserve stock for all components - this is mandatory for order creation
            reservations_created = mrp_service.reserve_stock_for_production(
                production_order_id, "SYSTEM"  # In real implementation, use current_user.username
            )
            print(f"DEBUG: Successfully created {len(reservations_created)} stock reservations")
            
            # Update component allocation status after successful reservation
            if reservations_created:
                # Get updated components to check allocation status
                updated_components = session.query(ProductionOrderComponent).filter(
                    ProductionOrderComponent.production_order_id == production_order_id
                ).all()
                
                allocated_count = sum(1 for comp in updated_components if comp.allocation_status == 'FULLY_ALLOCATED')
                print(f"DEBUG: {allocated_count}/{len(updated_components)} components are now fully allocated")
                
        except Exception as reservation_error:
            # CRITICAL CHANGE: If stock reservation fails, the entire order creation should fail
            session.rollback()
            error_msg = f"Failed to reserve stock for production order: {str(reservation_error)}"
            print(f"DEBUG: {error_msg}")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Production order creation failed",
                    "message": f"Could not reserve required stock: {str(reservation_error)}",
                    "suggestion": "Check stock availability and try again.",
                    "order_created": False
                }
            )
        
        # Get the order number for the response message  
        production_order = session.query(ProductionOrder).get(production_order_id)
        order_number = production_order.order_number
        
        session.commit()
        
        message = f"Production order {order_number} created successfully"
        if len(stock_analysis.semi_finished_shortages) > 0:
            message += f" (with {len(stock_analysis.semi_finished_shortages)} semi-finished product shortages)"
        if len(reservations_created) > 0:
            message += f" with {len(reservations_created)} stock reservations"
        
        return IDResponse(
            id=production_order_id,
            message=message
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
    allow_partial_stock: bool = Query(False, description="Allow update with insufficient stock"),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("write:production"))  # Temporarily disabled for testing
):
    """
    Update production order with stock validation for critical changes.
    
    Validates stock availability when critical fields are changed:
    - product_id, bom_id, planned_quantity, warehouse_id
    
    Non-critical updates (notes, dates, priority) proceed without validation.
    """
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
    
    # Additional validation for critical updates on IN_PROGRESS orders
    update_data = order_update.model_dump(exclude_unset=True)
    critical_fields = {'product_id', 'bom_id', 'planned_quantity', 'warehouse_id'}
    critical_changes = set(update_data.keys()).intersection(critical_fields)
    
    if production_order.status == 'IN_PROGRESS' and critical_changes:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot modify critical fields ({', '.join(critical_changes)}) for production orders in IN_PROGRESS status. Only notes, dates, and priority can be updated."
        )
    
    try:
        # Define critical fields that require stock validation  
        # (update_data already declared above for validation)
        
        # Store original values for potential rollback
        original_values = {}
        for field in critical_fields:
            if hasattr(production_order, field):
                original_values[field] = getattr(production_order, field)
        
        # If critical fields are being changed, perform stock validation
        if critical_changes:
            print(f"DEBUG: Critical fields being updated: {critical_changes}")
            
            # Validate new product and BOM if they're being changed
            new_product_id = update_data.get('product_id', production_order.product_id)
            new_bom_id = update_data.get('bom_id', production_order.bom_id)
            new_warehouse_id = update_data.get('warehouse_id', production_order.warehouse_id)
            new_planned_quantity = update_data.get('planned_quantity', production_order.planned_quantity)
            
            # Validate that new product and BOM are compatible if both are being changed
            if 'product_id' in update_data or 'bom_id' in update_data:
                try:
                    validate_bom_and_product(session, new_product_id, new_bom_id)
                except HTTPException as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid product/BOM combination: {e.detail}"
                    )
            
            # Validate warehouse exists if it's being changed
            if 'warehouse_id' in update_data:
                warehouse = session.query(Warehouse).filter(
                    Warehouse.warehouse_id == new_warehouse_id
                ).first()
                if not warehouse:
                    raise NotFoundError("Warehouse", new_warehouse_id)
            
            # Initialize MRP service for stock analysis
            mrp_service = MRPAnalysisService(session)
            
            # Release existing stock reservations before validation
            print(f"DEBUG: Releasing existing reservations for order {order_id}")
            try:
                released_count = mrp_service.release_stock_reservations(order_id)
                print(f"DEBUG: Released {released_count} existing reservations")
            except Exception as e:
                print(f"WARNING: Failed to release existing reservations: {str(e)}")
            
            # Perform stock analysis with new parameters
            try:
                stock_analysis = mrp_service.analyze_stock_availability(
                    product_id=new_product_id,
                    bom_id=new_bom_id,
                    planned_quantity=new_planned_quantity,
                    warehouse_id=new_warehouse_id,
                    production_order_id=order_id
                )
                
                # Apply same validation logic as creation endpoint
                if len(stock_analysis.raw_material_shortages) > 0:
                    shortage_details = [
                        f"{shortage.product_code} ({shortage.product_name}): need {shortage.shortage_quantity} units"
                        for shortage in stock_analysis.raw_material_shortages
                    ]
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": "Cannot update production order: Raw materials insufficient",
                            "message": "You must add stock for raw materials before making this update.",
                            "shortage_type": "RAW_MATERIALS", 
                            "missing_materials": shortage_details,
                            "can_update": False,
                            "suggestion": "Please add stock for the missing raw materials and try again."
                        }
                    )
                
                if len(stock_analysis.semi_finished_shortages) > 0 and not allow_partial_stock:
                    shortage_details = [
                        f"{shortage.product_code} ({shortage.product_name}): need {shortage.shortage_quantity} units"
                        for shortage in stock_analysis.semi_finished_shortages
                    ]
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": "Semi-finished products insufficient for update",
                            "message": "Missing semi-finished products can be produced. Use 'allow partial stock' option.",
                            "shortage_type": "SEMI_FINISHED",
                            "missing_materials": shortage_details,
                            "can_update": True,
                            "suggestion": "Enable 'allow_partial_stock' to update with missing semi-finished products."
                        }
                    )
                
                print(f"DEBUG: Stock validation passed for updated production plan")
                
            except HTTPException:
                # Re-raise HTTP exceptions (validation errors)
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to validate stock for updated production plan: {str(e)}"
                )
            
            # Update production order components if product/BOM/quantity changed
            if 'product_id' in update_data or 'bom_id' in update_data or 'planned_quantity' in update_data:
                print(f"DEBUG: Updating production order components due to critical field changes")
                
                # Only proceed if the order isn't in production to avoid data consistency issues
                if production_order.status in ['IN_PROGRESS']:
                    raise HTTPException(
                        status_code=400,
                        detail="Cannot change product, BOM, or quantity for production orders that are in progress"
                    )
                
                # Delete existing components
                deleted_components = session.query(ProductionOrderComponent).filter(
                    ProductionOrderComponent.production_order_id == order_id
                ).count()
                
                session.query(ProductionOrderComponent).filter(
                    ProductionOrderComponent.production_order_id == order_id
                ).delete()
                
                print(f"DEBUG: Deleted {deleted_components} existing components")
                
                # Apply the updates to the production order first
                for field, value in update_data.items():
                    if hasattr(production_order, field):
                        setattr(production_order, field, value)
                
                session.flush()  # Ensure changes are visible
                
                # Create new components based on updated BOM
                bom = session.query(BillOfMaterials).get(new_bom_id)
                if not bom:
                    raise HTTPException(
                        status_code=400,
                        detail=f"BOM with ID {new_bom_id} not found"
                    )
                
                new_components = create_production_order_components(session, production_order, bom)
                print(f"DEBUG: Created {len(new_components)} new components")
                
                # Recalculate estimated cost
                estimated_cost = Decimal('0')
                for component in new_components:
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
                print(f"DEBUG: Updated estimated cost to {estimated_cost}")
            
            else:
                # Apply critical field updates that don't affect components (e.g., warehouse_id only)
                for field, value in update_data.items():
                    if field in critical_fields and hasattr(production_order, field):
                        setattr(production_order, field, value)
                        print(f"DEBUG: Updated {field} to {value}")
            
            # Reserve stock for the updated production plan
            try:
                print(f"DEBUG: Creating new stock reservations for updated production plan")
                reservations_created = mrp_service.reserve_stock_for_production(
                    order_id, "SYSTEM"  # In real implementation, use current_user.username
                )
                print(f"DEBUG: Successfully created {len(reservations_created)} new stock reservations")
                
            except Exception as reservation_error:
                print(f"WARNING: Failed to reserve stock after update: {str(reservation_error)}")
                # For updates, we'll proceed but add a warning note
                current_notes = production_order.notes or ""
                warning_note = f"\n[WARNING] Stock reservation failed after update: {str(reservation_error)}"
                production_order.notes = current_notes + warning_note
        
        else:
            # No critical fields changed - simple update without validation
            print(f"DEBUG: Non-critical fields update: {set(update_data.keys())}")
        
        # Apply remaining updates that weren't handled in the critical section
        for field, value in update_data.items():
            if hasattr(production_order, field) and field not in critical_fields:
                setattr(production_order, field, value)
        
        production_order.updated_at = datetime.now()
        
        session.commit()
        
        # Return updated order
        return get_production_order(order_id, session)
        
    except Exception as e:
        session.rollback()
        if isinstance(e, (NotFoundError, HTTPException)):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to update production order: {str(e)}")


@router.delete("/{order_id}", response_model=MessageResponse)
def delete_production_order(
    order_id: int = Path(..., description="Production order ID"),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("delete:production"))  # Temporarily disabled for testing
):
    """
    Delete production order with stock reservation cleanup.
    
    Allows deletion (cancellation) of PLANNED and IN_PROGRESS orders.
    Prevents deletion of COMPLETED orders since production has already been done.
    Automatically releases associated stock reservations.
    """
    # Get production order
    production_order = session.query(ProductionOrder).filter(
        ProductionOrder.production_order_id == order_id
    ).first()
    
    if not production_order:
        raise NotFoundError("Production Order", order_id)
    
    # Check if order can be deleted (PLANNED and IN_PROGRESS can be cancelled, but COMPLETED cannot)
    if production_order.status == 'COMPLETED':
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete completed production order - production has already been completed and cannot be undone"
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
        logger = logging.getLogger(__name__)
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
                logger.info(f"🔨 FINISHED GOODS DEBUG: consumption_records={len(consumption_records) if consumption_records else 0}, planned_quantity={production_order.planned_quantity}")
                
                # Create finished goods inventory (assume full completion of planned quantity)
                if consumption_records and production_order.planned_quantity > 0:
                    logger.info(f"🔨 FINISHED GOODS: Creating finished goods for {production_order.planned_quantity} units")
                    finished_goods = mrp_service.create_finished_goods_inventory(
                        order_id,
                        production_order.planned_quantity,
                        consumption_records
                    )
                    logger.info(f"✅ FINISHED GOODS: Created finished goods result: {finished_goods}")
                    production_order.completed_quantity = production_order.planned_quantity
                else:
                    logger.warning(f"⚠️ FINISHED GOODS: Skipping creation - consumption_records={len(consumption_records) if consumption_records else 0}, planned_quantity={production_order.planned_quantity}")
                
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
        
        # IMPLEMENTED: FIFO stock consumption and finished goods creation
        mrp_service = MRPAnalysisService(session)
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"🏭 PRODUCTION COMPLETION: Starting completion for order {order_id}")
        logger.info(f"📊 Completed quantity: {completion_data.completed_quantity}, Scrapped: {completion_data.scrapped_quantity}")
        
        # 1. Consume allocated stock using FIFO
        logger.info(f"📦 STOCK CONSUMPTION: Starting FIFO consumption for order {order_id}")
        consumption_records = mrp_service.consume_stock_for_production(order_id)
        logger.info(f"✅ STOCK CONSUMPTION: Consumed {len(consumption_records)} stock records")
        
        # 2. Create finished goods inventory if we completed any quantity
        finished_goods_record = None
        if completion_data.completed_quantity > 0:
            logger.info(f"🔨 FINISHED GOODS: Creating finished goods inventory for quantity {completion_data.completed_quantity}")
            finished_goods_record = mrp_service.create_finished_goods_inventory(
                order_id,
                completion_data.completed_quantity,
                consumption_records
            )
            if finished_goods_record:
                logger.info(f"✅ FINISHED GOODS: Created inventory record - Quantity: {finished_goods_record.get('quantity', 'N/A')}, Cost: {finished_goods_record.get('unit_cost', 'N/A')}")
            else:
                logger.warning(f"⚠️ FINISHED GOODS: No inventory record created")
        
        logger.info(f"🎉 PRODUCTION COMPLETION: Successfully completed order {order_id}")
        
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
        
        # Create the main production order directly
        main_order_id = _create_production_order_core(order_request, False, session)
        main_order_response = IDResponse(id=main_order_id, message="Production order created successfully")
        
        dependent_orders = []
        nested_orders_created = []  # Frontend expects this
        production_tree = None
        warnings = []  # Frontend expects this
        
        # CRITICAL VALIDATION: Check for raw material shortages first
        if len(analysis_result.raw_material_shortages) > 0:
            shortage_details = [
                f"{shortage.product_code} ({shortage.product_name}): need {shortage.shortage_quantity} units"
                for shortage in analysis_result.raw_material_shortages
            ]
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Cannot create production order: Raw materials insufficient",
                    "message": "You must add stock for raw materials before creating this production order.",
                    "shortage_type": "RAW_MATERIALS",
                    "missing_materials": shortage_details,
                    "can_create": False,
                    "suggestion": "Please add stock for the missing raw materials and try again."
                }
            )
        
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
        
        # CRITICAL FIX: Reserve stock for the main production order
        reservations = []
        try:
            reservations = mrp_service.reserve_stock_for_production(
                main_order_id, "SYSTEM"
            )
            print(f"DEBUG: Reserved stock for main order {main_order_id}: {len(reservations)} reservations")
        except Exception as e:
            # For the enhanced endpoint, we'll track failures but not block order creation
            # since dependent orders may still provide the needed components
            warnings.append(f"Stock reservation failed for main order: {str(e)}")
        
        # Also attempt to reserve stock for dependent orders
        for dep_order in dependent_orders:
            try:
                dep_reservations = mrp_service.reserve_stock_for_production(
                    dep_order["production_order_id"], "SYSTEM"
                )
                reservations.extend(dep_reservations)
                print(f"DEBUG: Reserved stock for dependent order {dep_order['order_number']}: {len(dep_reservations)} reservations")
            except Exception as e:
                warnings.append(f"Stock reservation failed for dependent order {dep_order['order_number']}: {str(e)}")
        
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
        
        # Provide specific guidance based on shortage type
        production_guidance = {
            "can_create_order": len(analysis_result.raw_material_shortages) == 0,
            "can_create_with_dependencies": len(analysis_result.raw_material_shortages) == 0 and len(analysis_result.semi_finished_shortages) > 0,
            "must_add_stock": len(analysis_result.raw_material_shortages) > 0,
            "shortage_summary": {
                "raw_materials": len(analysis_result.raw_material_shortages),
                "semi_finished": len(analysis_result.semi_finished_shortages),
                "total_shortages": len(missing_materials)
            },
            "recommendations": []
        }
        
        if len(analysis_result.raw_material_shortages) > 0:
            production_guidance["recommendations"].append("Add stock for raw materials before creating production order")
        elif len(analysis_result.semi_finished_shortages) > 0:
            production_guidance["recommendations"].append("Enable 'add missing semi-products' to create dependent production orders")
        else:
            production_guidance["recommendations"].append("All materials available - can create production order immediately")
        
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
            "production_guidance": production_guidance,
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


@router.get("/reservations/all", response_model=Dict)
def get_all_stock_reservations(
    status: Optional[str] = Query(None, description="Filter by reservation status"),
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    warehouse_id: Optional[int] = Query(None, description="Filter by warehouse ID"),
    production_order_id: Optional[int] = Query(None, description="Filter by production order ID"),
    pagination: PaginationParams = Depends(get_pagination_params),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("read:production"))  # Temporarily disabled for testing
):
    """
    Get all stock reservations with filtering and pagination.
    
    Returns comprehensive reservation data across all production orders.
    """
    try:
        # Build base query
        query = session.query(StockReservation).filter(
            StockReservation.reserved_for_type == 'PRODUCTION_ORDER'
        )
        
        # Apply filters
        if status:
            query = query.filter(StockReservation.status == status)
        if product_id:
            query = query.filter(StockReservation.product_id == product_id)
        if warehouse_id:
            query = query.filter(StockReservation.warehouse_id == warehouse_id)
        if production_order_id:
            query = query.filter(StockReservation.reserved_for_id == production_order_id)
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination and ordering
        reservations = query.order_by(desc(StockReservation.reservation_date)).offset(
            pagination.offset
        ).limit(pagination.page_size).all()
        
        # Build response with product and warehouse details
        reservation_details = []
        for res in reservations:
            # Get product details
            product = session.query(Product).get(res.product_id)
            warehouse = session.query(Warehouse).get(res.warehouse_id)
            production_order = session.query(ProductionOrder).get(res.reserved_for_id)
            
            reservation_details.append({
                'reservation_id': res.reservation_id,
                'product': {
                    'product_id': product.product_id,
                    'product_code': product.product_code,
                    'product_name': product.product_name,
                    'product_type': product.product_type
                } if product else None,
                'warehouse': {
                    'warehouse_id': warehouse.warehouse_id,
                    'warehouse_code': warehouse.warehouse_code,
                    'warehouse_name': warehouse.warehouse_name
                } if warehouse else None,
                'production_order': {
                    'production_order_id': production_order.production_order_id,
                    'order_number': production_order.order_number,
                    'status': production_order.status
                } if production_order else None,
                'reserved_quantity': float(res.reserved_quantity),
                'status': res.status,
                'reservation_date': res.reservation_date.isoformat() if res.reservation_date else None,
                'expiry_date': res.expiry_date.isoformat() if res.expiry_date else None,
                'reserved_by': res.reserved_by,
                'notes': res.notes
            })
        
        # Calculate pagination info
        total_pages = (total_count + pagination.page_size - 1) // pagination.page_size
        
        return {
            'reservations': reservation_details,
            'pagination': {
                'total_count': total_count,
                'page': pagination.page,
                'page_size': pagination.page_size,
                'total_pages': total_pages,
                'has_next': pagination.page < total_pages,
                'has_previous': pagination.page > 1
            },
            'summary': {
                'total_reservations': total_count,
                'active_reservations': len([r for r in reservations if r.status == 'ACTIVE']),
                'consumed_reservations': len([r for r in reservations if r.status == 'CONSUMED']),
                'released_reservations': len([r for r in reservations if r.status == 'RELEASED'])
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get reservations: {str(e)}")


@router.get("/component-allocation-status", response_model=Dict)
def get_component_allocation_status(
    status: Optional[str] = Query(None, description="Filter by allocation status"),
    product_id: Optional[int] = Query(None, description="Filter by component product ID"),
    pagination: PaginationParams = Depends(get_pagination_params),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("read:production"))  # Temporarily disabled for testing
):
    """
    Get component allocation status across all production orders.
    
    Returns detailed view of component allocation status for monitoring purposes.
    """
    try:
        # Build base query
        query = session.query(ProductionOrderComponent).options(
            joinedload(ProductionOrderComponent.component_product),
            joinedload(ProductionOrderComponent.production_order)
        )
        
        # Apply filters
        if status:
            query = query.filter(ProductionOrderComponent.allocation_status == status)
        if product_id:
            query = query.filter(ProductionOrderComponent.component_product_id == product_id)
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination and ordering
        components = query.order_by(
            desc(ProductionOrderComponent.production_order_id)
        ).offset(pagination.offset).limit(pagination.page_size).all()
        
        # Build response
        component_details = []
        status_summary = {'NOT_ALLOCATED': 0, 'PARTIALLY_ALLOCATED': 0, 'FULLY_ALLOCATED': 0, 'CONSUMED': 0}
        
        for comp in components:
            status_summary[comp.allocation_status] = status_summary.get(comp.allocation_status, 0) + 1
            
            component_details.append({
                'po_component_id': comp.po_component_id,
                'production_order': {
                    'production_order_id': comp.production_order.production_order_id,
                    'order_number': comp.production_order.order_number,
                    'status': comp.production_order.status,
                    'planned_quantity': float(comp.production_order.planned_quantity)
                } if comp.production_order else None,
                'component_product': {
                    'product_id': comp.component_product.product_id,
                    'product_code': comp.component_product.product_code,
                    'product_name': comp.component_product.product_name,
                    'product_type': comp.component_product.product_type
                } if comp.component_product else None,
                'required_quantity': float(comp.required_quantity),
                'allocated_quantity': float(comp.allocated_quantity),
                'consumed_quantity': float(comp.consumed_quantity),
                'unit_cost': float(comp.unit_cost),
                'allocation_status': comp.allocation_status,
                'allocation_percentage': float((comp.allocated_quantity / comp.required_quantity) * 100) if comp.required_quantity > 0 else 0
            })
        
        # Calculate pagination info
        total_pages = (total_count + pagination.page_size - 1) // pagination.page_size
        
        return {
            'components': component_details,
            'pagination': {
                'total_count': total_count,
                'page': pagination.page,
                'page_size': pagination.page_size,
                'total_pages': total_pages,
                'has_next': pagination.page < total_pages,
                'has_previous': pagination.page > 1
            },
            'allocation_summary': status_summary,
            'allocation_statistics': {
                'total_components': total_count,
                'fully_allocated_percentage': round((status_summary['FULLY_ALLOCATED'] / total_count) * 100, 2) if total_count > 0 else 0,
                'not_allocated_percentage': round((status_summary['NOT_ALLOCATED'] / total_count) * 100, 2) if total_count > 0 else 0
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get component allocation status: {str(e)}")


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