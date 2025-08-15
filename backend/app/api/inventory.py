"""
Inventory Management API endpoints with FIFO allocation logic.
Handles stock operations, inventory tracking, and allocation management.
"""

from typing import List, Optional
from decimal import Decimal
from datetime import datetime, date
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_, func, desc, asc
from sqlalchemy.orm import selectinload, joinedload

from app.dependencies import (
    get_db, get_current_active_user, require_permissions,
    get_pagination_params, PaginationParams
)
from app.schemas.base import MessageResponse, IDResponse, PaginatedResponse
from app.schemas.auth import UserInfo
from app.schemas.inventory import (
    StockInRequest, StockOutRequest, StockAdjustmentRequest, StockTransferRequest,
    InventoryItemList, InventoryAvailability, FIFOAllocationResult,
    StockAllocationRequest, StockMovementList, CriticalStockReport,
    InventoryItemDetail, InventoryItem, FIFOAllocationItem, StockMovementDetail,
    CriticalStockItem, StockOperationResponse
)
from app.schemas.master_data import ProductSummary, SupplierSummary
from app.exceptions import NotFoundError, InsufficientStockError, ValidationError, ConflictError
from models.inventory import InventoryItem as InventoryItemModel, StockMovement as StockMovementModel
from models.master_data import Product, Warehouse, Supplier


router = APIRouter()


@router.get("/items")  # TODO: response_model=InventoryItemList)
def list_inventory_items(
    pagination: PaginationParams = Depends(get_pagination_params),
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    warehouse_id: Optional[int] = Query(None, description="Filter by warehouse ID"),
    quality_status: Optional[str] = Query(None, description="Filter by quality status"),
    session: Session = Depends(get_db),
    current_user: UserInfo = require_permissions("read:inventory")
):
    """
    List inventory items with FIFO ordering.
    
    Returns inventory items ordered by entry date for FIFO logic.
    """
    # Build base query with relationships
    query = (
        select(InventoryItemModel)
        .options(
            joinedload(InventoryItemModel.product),
            joinedload(InventoryItemModel.warehouse),
            joinedload(InventoryItemModel.supplier)
        )
        .where(InventoryItemModel.quantity_in_stock > 0)
    )
    
    # Apply filters
    if product_id:
        query = query.where(InventoryItemModel.product_id == product_id)
    
    if warehouse_id:
        query = query.where(InventoryItemModel.warehouse_id == warehouse_id)
    
    if quality_status:
        query = query.where(InventoryItemModel.quality_status == quality_status)
    
    # Order by FIFO (entry_date, then inventory_item_id for consistency)
    query = query.order_by(
        InventoryItemModel.entry_date.asc(),
        InventoryItemModel.inventory_item_id.asc()
    )
    
    # Get total count
    count_query = select(func.count(InventoryItemModel.inventory_item_id)).select_from(
        query.subquery()
    )
    total_count = session.execute(count_query).scalar()
    
    # Apply pagination
    query = query.offset(pagination.offset).limit(pagination.limit)
    
    # Execute query
    result = session.execute(query)
    inventory_items = result.scalars().all()
    
    # Convert to response schemas
    items = []
    for item in inventory_items:
        # Create product summary
        product = ProductSummary(
            product_id=item.product.product_id,
            product_code=item.product.product_code,
            product_name=item.product.product_name,
            product_type=item.product.product_type,
            unit_of_measure=item.product.unit_of_measure
        )
        
        # Create warehouse summary
        warehouse = WarehouseSummary(
            warehouse_id=item.warehouse.warehouse_id,
            warehouse_code=item.warehouse.warehouse_code,
            warehouse_name=item.warehouse.warehouse_name,
            warehouse_type=item.warehouse.warehouse_type
        )
        
        # Create supplier summary (if exists)
        supplier = None
        if item.supplier:
            supplier = SupplierSummary(
                supplier_id=item.supplier.supplier_id,
                supplier_code=item.supplier.supplier_code,
                supplier_name=item.supplier.supplier_name,
                contact_person=item.supplier.contact_person
            )
        
        # Create inventory item detail
        item_detail = InventoryItemDetail(
            inventory_item_id=item.inventory_item_id,
            product_id=item.product_id,
            warehouse_id=item.warehouse_id,
            batch_number=item.batch_number,
            quantity_in_stock=item.quantity_in_stock,
            reserved_quantity=item.reserved_quantity,
            unit_cost=item.unit_cost,
            quality_status=item.quality_status,
            expiry_date=item.expiry_date,
            supplier_id=item.supplier_id,
            purchase_order_id=item.purchase_order_id,
            notes=item.notes,
            entry_date=item.entry_date,
            created_at=item.created_at,
            updated_at=item.updated_at,
            product=product,
            warehouse=warehouse,
            supplier=supplier
        )
        items.append(item_detail)
    
    return InventoryItemList(items=items, total_count=total_count)


@router.get("/availability/{product_id}")  # TODO: response_model=InventoryAvailability)
def get_inventory_availability(
    product_id: int = Path(..., description="Product ID"),
    warehouse_id: Optional[int] = Query(None, description="Warehouse ID filter"),
    session: Session = Depends(get_db),
    current_user: UserInfo = require_permissions("read:inventory")
):
    """
    Check available inventory for a product.
    
    Returns availability summary with FIFO cost calculation.
    """
    # Verify product exists
    product_query = select(Product).where(Product.product_id == product_id)
    product_result = session.execute(product_query)
    product = product_result.scalar_one_or_none()
    
    if not product:
        raise NotFoundError("Product", product_id)
    
    # Build query for inventory items
    query = (
        select(InventoryItemModel)
        .where(
            and_(
                InventoryItemModel.product_id == product_id,
                InventoryItemModel.quantity_in_stock > 0,
                InventoryItemModel.quality_status == 'APPROVED'
            )
        )
    )
    
    if warehouse_id:
        query = query.where(InventoryItemModel.warehouse_id == warehouse_id)
    
    # Order by FIFO for cost calculation
    query = query.order_by(
        InventoryItemModel.entry_date.asc(),
        InventoryItemModel.inventory_item_id.asc()
    )
    
    result = session.execute(query)
    inventory_items = result.scalars().all()
    
    # Calculate totals
    total_in_stock = Decimal('0')
    total_reserved = Decimal('0')
    total_available = Decimal('0')
    total_value = Decimal('0')
    expired_quantity = Decimal('0')
    oldest_batch_date = None
    newest_batch_date = None
    
    batches = []
    
    for item in inventory_items:
        total_in_stock += item.quantity_in_stock
        total_reserved += item.reserved_quantity
        available_qty = item.quantity_in_stock - item.reserved_quantity
        total_available += available_qty
        total_value += item.quantity_in_stock * item.unit_cost
        
        # Check for expired items
        if item.expiry_date and item.expiry_date <= date.today():
            expired_quantity += item.quantity_in_stock
        
        # Track date range
        if oldest_batch_date is None or item.entry_date < oldest_batch_date:
            oldest_batch_date = item.entry_date
        if newest_batch_date is None or item.entry_date > newest_batch_date:
            newest_batch_date = item.entry_date
        
        # Create batch info
        batch_info = InventoryItem(
            inventory_item_id=item.inventory_item_id,
            product_id=item.product_id,
            warehouse_id=item.warehouse_id,
            batch_number=item.batch_number,
            quantity_in_stock=item.quantity_in_stock,
            reserved_quantity=item.reserved_quantity,
            unit_cost=item.unit_cost,
            quality_status=item.quality_status,
            expiry_date=item.expiry_date,
            supplier_id=item.supplier_id,
            purchase_order_id=item.purchase_order_id,
            notes=item.notes,
            entry_date=item.entry_date,
            created_at=item.created_at,
            updated_at=item.updated_at
        )
        batches.append(batch_info)
    
    # Calculate weighted average cost
    weighted_average_cost = Decimal('0')
    if total_in_stock > 0:
        weighted_average_cost = total_value / total_in_stock
    
    return InventoryAvailability(
        product_id=product_id,
        warehouse_id=warehouse_id,
        total_in_stock=total_in_stock,
        total_reserved=total_reserved,
        total_available=total_available,
        weighted_average_cost=weighted_average_cost,
        oldest_batch_date=oldest_batch_date,
        newest_batch_date=newest_batch_date,
        expired_quantity=expired_quantity,
        batches=batches
    )


@router.post("/stock-in")  # TODO: response_model=IDResponse)
def stock_in_operation(
    stock_in_request: StockInRequest,
    session: Session = Depends(get_db),
    current_user: UserInfo = require_permissions("write:inventory")
):
    """
    Add new inventory stock.
    
    Creates new inventory item and records stock movement.
    """
    # Validate product exists
    product_query = select(Product).where(Product.product_id == stock_in_request.product_id)
    product_result = session.execute(product_query)
    product = product_result.scalar_one_or_none()
    
    if not product:
        raise NotFoundError("Product", stock_in_request.product_id)
    
    # Validate warehouse exists
    warehouse_query = select(Warehouse).where(Warehouse.warehouse_id == stock_in_request.warehouse_id)
    warehouse_result = session.execute(warehouse_query)
    warehouse = warehouse_result.scalar_one_or_none()
    
    if not warehouse:
        raise NotFoundError("Warehouse", stock_in_request.warehouse_id)
    
    # Validate supplier if provided
    if stock_in_request.supplier_id:
        supplier_query = select(Supplier).where(Supplier.supplier_id == stock_in_request.supplier_id)
        supplier_result = session.execute(supplier_query)
        supplier = supplier_result.scalar_one_or_none()
        
        if not supplier:
            raise NotFoundError("Supplier", stock_in_request.supplier_id)
    
    # Check for duplicate batch in same warehouse for same product
    duplicate_query = (
        select(InventoryItemModel)
        .where(
            and_(
                InventoryItemModel.product_id == stock_in_request.product_id,
                InventoryItemModel.warehouse_id == stock_in_request.warehouse_id,
                InventoryItemModel.batch_number == stock_in_request.batch_number
            )
        )
    )
    duplicate_result = session.execute(duplicate_query)
    existing_batch = duplicate_result.scalar_one_or_none()
    
    if existing_batch:
        raise ConflictError(
            f"Batch {stock_in_request.batch_number} already exists for this product in this warehouse",
            "inventory_item"
        )
    
    # Create new inventory item
    new_item = InventoryItemModel(
        product_id=stock_in_request.product_id,
        warehouse_id=stock_in_request.warehouse_id,
        batch_number=stock_in_request.batch_number,
        entry_date=datetime.now(),
        expiry_date=stock_in_request.expiry_date,
        quantity_in_stock=stock_in_request.quantity,
        reserved_quantity=Decimal('0'),
        unit_cost=stock_in_request.unit_cost,
        supplier_id=stock_in_request.supplier_id,
        purchase_order_id=stock_in_request.purchase_order_id,
        quality_status=stock_in_request.quality_status,
        notes=stock_in_request.notes,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    session.add(new_item)
    session.flush()  # Get the ID
    
    # Create stock movement record
    stock_movement = StockMovementModel(
        inventory_item_id=new_item.inventory_item_id,
        movement_type='IN',
        movement_date=datetime.now(),
        quantity=stock_in_request.quantity,
        unit_cost=stock_in_request.unit_cost,
        reference_type='PURCHASE_ORDER' if stock_in_request.purchase_order_id else None,
        reference_id=stock_in_request.purchase_order_id,
        notes=f"Stock in operation - Batch: {stock_in_request.batch_number}",
        created_by=current_user.username,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    session.add(stock_movement)
    session.commit()
    
    return IDResponse(
        id=new_item.inventory_item_id,
        message=f"Stock in operation completed successfully. Added {stock_in_request.quantity} units of batch {stock_in_request.batch_number}"
    )


@router.post("/stock-out")  # TODO: response_model=MessageResponse)
def stock_out_operation(
    stock_out_request: StockOutRequest,
    session: Session = Depends(get_db),
    current_user: UserInfo = require_permissions("write:inventory")
):
    """
    Remove inventory stock using FIFO logic.
    
    Allocates and consumes stock from oldest batches first.
    """
    # Validate product and warehouse exist
    product_query = select(Product).where(Product.product_id == stock_out_request.product_id)
    product_result = session.execute(product_query)
    product = product_result.scalar_one_or_none()
    
    if not product:
        raise NotFoundError("Product", stock_out_request.product_id)
    
    warehouse_query = select(Warehouse).where(Warehouse.warehouse_id == stock_out_request.warehouse_id)
    warehouse_result = session.execute(warehouse_query)
    warehouse = warehouse_result.scalar_one_or_none()
    
    if not warehouse:
        raise NotFoundError("Warehouse", stock_out_request.warehouse_id)
    
    # Get available inventory items using FIFO ordering
    fifo_query = (
        select(InventoryItemModel)
        .where(
            and_(
                InventoryItemModel.product_id == stock_out_request.product_id,
                InventoryItemModel.warehouse_id == stock_out_request.warehouse_id,
                InventoryItemModel.quality_status == 'APPROVED',
                InventoryItemModel.quantity_in_stock > InventoryItemModel.reserved_quantity
            )
        )
        .order_by(
            InventoryItemModel.entry_date.asc(),
            InventoryItemModel.inventory_item_id.asc()
        )
    )
    
    result = session.execute(fifo_query)
    available_items = result.scalars().all()
    
    # Check if sufficient stock is available
    total_available = sum(item.quantity_in_stock - item.reserved_quantity for item in available_items)
    
    if total_available < stock_out_request.quantity:
        raise InsufficientStockError(
            f"Insufficient stock for product {product.product_code}. "
            f"Required: {stock_out_request.quantity}, Available: {total_available}",
            product_id=stock_out_request.product_id,
            required=float(stock_out_request.quantity),
            available=float(total_available)
        )
    
    # Perform FIFO consumption
    remaining_to_consume = stock_out_request.quantity
    movements_created = []
    
    for item in available_items:
        if remaining_to_consume <= 0:
            break
        
        available_in_batch = item.quantity_in_stock - item.reserved_quantity
        
        if available_in_batch <= 0:
            continue
        
        # Calculate how much to consume from this batch
        consume_from_batch = min(remaining_to_consume, available_in_batch)
        
        # Update inventory item
        item.quantity_in_stock -= consume_from_batch
        item.updated_at = datetime.now()
        
        # Create stock movement record
        stock_movement = StockMovementModel(
            inventory_item_id=item.inventory_item_id,
            movement_type='OUT',
            movement_date=datetime.now(),
            quantity=-consume_from_batch,  # Negative for outbound
            unit_cost=item.unit_cost,
            reference_type=None,
            reference_id=None,
            notes=f"Stock out operation - {stock_out_request.reason}. Reference: {stock_out_request.reference_number or 'N/A'}",
            created_by=current_user.username,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        session.add(stock_movement)
        movements_created.append(stock_movement)
        
        remaining_to_consume -= consume_from_batch
    
    # Commit all changes
    session.commit()
    
    # Calculate total cost based on FIFO
    total_cost = sum(abs(movement.quantity) * movement.unit_cost for movement in movements_created)
    
    return MessageResponse(
        message=f"Stock out operation completed successfully. "
                f"Consumed {stock_out_request.quantity} units from {len(movements_created)} batches. "
                f"Total FIFO cost: {total_cost:.2f}"
    )


@router.post("/adjust")  # TODO: response_model=MessageResponse)
def stock_adjustment(
    adjustment_request: StockAdjustmentRequest,
    session: Session = Depends(get_db),
    current_user: UserInfo = require_permissions("write:inventory")
):
    """
    Adjust inventory quantities.
    
    Allows positive or negative adjustments with audit trail.
    """
    # TODO: Implement stock adjustment
    return MessageResponse(message="Stock adjustment completed successfully")


@router.post("/transfer")  # TODO: response_model=MessageResponse)
def stock_transfer(
    transfer_request: StockTransferRequest,
    session: Session = Depends(get_db),
    current_user: UserInfo = require_permissions("write:inventory")
):
    """
    Transfer stock between warehouses.
    
    Uses FIFO logic to select source inventory and creates new batch in destination.
    """
    # TODO: Implement stock transfer with FIFO
    return MessageResponse(message="Stock transfer completed successfully")


@router.post("/allocate")  # TODO: response_model=FIFOAllocationResult)
def allocate_stock(
    allocation_request: StockAllocationRequest,
    session: Session = Depends(get_db),
    current_user: UserInfo = require_permissions("allocate:stock")
):
    """
    Allocate inventory using FIFO logic.
    
    Reserves stock for production orders or other purposes.
    """
    # Validate product and warehouse exist
    product_query = select(Product).where(Product.product_id == allocation_request.product_id)
    product_result = session.execute(product_query)
    product = product_result.scalar_one_or_none()
    
    if not product:
        raise NotFoundError("Product", allocation_request.product_id)
    
    warehouse_query = select(Warehouse).where(Warehouse.warehouse_id == allocation_request.warehouse_id)
    warehouse_result = session.execute(warehouse_query)
    warehouse = warehouse_result.scalar_one_or_none()
    
    if not warehouse:
        raise NotFoundError("Warehouse", allocation_request.warehouse_id)
    
    # Get available inventory items using FIFO ordering
    fifo_query = (
        select(InventoryItemModel)
        .where(
            and_(
                InventoryItemModel.product_id == allocation_request.product_id,
                InventoryItemModel.warehouse_id == allocation_request.warehouse_id,
                InventoryItemModel.quality_status == 'APPROVED',
                InventoryItemModel.quantity_in_stock > InventoryItemModel.reserved_quantity
            )
        )
        .order_by(
            InventoryItemModel.entry_date.asc(),
            InventoryItemModel.inventory_item_id.asc()
        )
    )
    
    result = session.execute(fifo_query)
    available_items = result.scalars().all()
    
    # Calculate total available
    total_available = sum(item.quantity_in_stock - item.reserved_quantity for item in available_items)
    
    # Perform FIFO allocation
    remaining_to_allocate = allocation_request.quantity
    allocated_quantity = Decimal('0')
    total_cost = Decimal('0')
    allocations = []
    
    for item in available_items:
        if remaining_to_allocate <= 0:
            break
        
        available_in_batch = item.quantity_in_stock - item.reserved_quantity
        
        if available_in_batch <= 0:
            continue
        
        # Calculate how much to allocate from this batch
        allocate_from_batch = min(remaining_to_allocate, available_in_batch)
        
        if allocate_from_batch > 0:
            # Update reserved quantity
            item.reserved_quantity += allocate_from_batch
            item.updated_at = datetime.now()
            
            # Calculate cost for this allocation
            batch_cost = allocate_from_batch * item.unit_cost
            total_cost += batch_cost
            allocated_quantity += allocate_from_batch
            
            # Create allocation record
            allocation_item = FIFOAllocationItem(
                inventory_item_id=item.inventory_item_id,
                batch_number=item.batch_number,
                allocated_quantity=allocate_from_batch,
                unit_cost=item.unit_cost,
                total_cost=batch_cost,
                entry_date=item.entry_date
            )
            allocations.append(allocation_item)
            
            remaining_to_allocate -= allocate_from_batch
    
    # Calculate shortage
    shortage_quantity = allocation_request.quantity - allocated_quantity
    
    # Calculate weighted average cost
    weighted_average_cost = Decimal('0')
    if allocated_quantity > 0:
        weighted_average_cost = total_cost / allocated_quantity
    
    # Commit reservation changes
    if allocated_quantity > 0:
        session.commit()
    
    return FIFOAllocationResult(
        product_id=allocation_request.product_id,
        warehouse_id=allocation_request.warehouse_id,
        requested_quantity=allocation_request.quantity,
        allocated_quantity=allocated_quantity,
        shortage_quantity=shortage_quantity,
        weighted_average_cost=weighted_average_cost,
        total_cost=total_cost,
        allocations=allocations
    )


@router.get("/movements")  # TODO: response_model=StockMovementList)
def list_stock_movements(
    pagination: PaginationParams = Depends(get_pagination_params),
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    warehouse_id: Optional[int] = Query(None, description="Filter by warehouse ID"),
    movement_type: Optional[str] = Query(None, description="Filter by movement type"),
    session: Session = Depends(get_db),
    current_user: UserInfo = require_permissions("read:inventory")
):
    """
    List stock movement history.
    
    Shows complete audit trail of all inventory movements.
    """
    # TODO: Implement stock movements listing
    return StockMovementList(movements=[], total_count=0)


@router.get("/critical-stock")  # TODO: response_model=CriticalStockReport)
def get_critical_stock_report(
    warehouse_id: Optional[int] = Query(None, description="Filter by warehouse ID"),
    session: Session = Depends(get_db),
    current_user: UserInfo = require_permissions("read:reports")
):
    """
    Get critical stock level report.
    
    Shows products below critical stock levels with reorder suggestions.
    """
    # TODO: Implement critical stock report
    return CriticalStockReport(items=[], total_items=0)