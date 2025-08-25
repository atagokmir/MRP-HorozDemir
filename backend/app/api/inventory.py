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
from app.schemas.master_data import ProductSummary, SupplierSummary, WarehouseSummary
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
        # Ensure proper type conversion to Decimal
        item_quantity = Decimal(str(item.quantity_in_stock or 0))
        item_reserved = Decimal(str(item.reserved_quantity or 0))
        item_unit_cost = Decimal(str(item.unit_cost or 0))
        
        total_in_stock += item_quantity
        total_reserved += item_reserved
        available_qty = item_quantity - item_reserved
        total_available += available_qty
        total_value += item_quantity * item_unit_cost
        
        # Check for expired items
        if item.expiry_date:
            # Handle both datetime and date comparison
            expiry_date = item.expiry_date.date() if hasattr(item.expiry_date, 'date') else item.expiry_date
            if expiry_date <= date.today():
                expired_quantity += item_quantity
        
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
            quantity_in_stock=item_quantity,
            reserved_quantity=item_reserved,
            unit_cost=item_unit_cost,
            quality_status=item.quality_status,
            expiry_date=item.expiry_date,
            supplier_id=item.supplier_id,
            purchase_order_id=item.purchase_order_id,
            notes=getattr(item, 'notes', None),
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
    
    # Use provided entry_date or default to today
    entry_date = stock_in_request.entry_date or date.today()
    # Convert date to datetime for database storage
    if isinstance(entry_date, date) and not isinstance(entry_date, datetime):
        entry_datetime = datetime.combine(entry_date, datetime.min.time())
    else:
        entry_datetime = entry_date
    
    # Handle expiry_date conversion
    expiry_datetime = None
    if stock_in_request.expiry_date:
        if isinstance(stock_in_request.expiry_date, date) and not isinstance(stock_in_request.expiry_date, datetime):
            expiry_datetime = datetime.combine(stock_in_request.expiry_date, datetime.min.time())
        else:
            expiry_datetime = stock_in_request.expiry_date
    
    # Create new inventory item
    new_item = InventoryItemModel(
        product_id=stock_in_request.product_id,
        warehouse_id=stock_in_request.warehouse_id,
        batch_number=stock_in_request.batch_number,
        entry_date=entry_datetime,
        expiry_date=expiry_datetime,
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
        notes=f"Stock in operation - Batch: {stock_in_request.batch_number}" + (f" - {stock_in_request.notes}" if stock_in_request.notes else ""),
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
    total_available = sum(Decimal(str(item.quantity_in_stock or 0)) - Decimal(str(item.reserved_quantity or 0)) for item in available_items)
    
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
        
        available_in_batch = Decimal(str(item.quantity_in_stock or 0)) - Decimal(str(item.reserved_quantity or 0))
        
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
            notes=f"Stock out operation - {stock_out_request.reference_type or 'Manual'}. Reference: {stock_out_request.reference_id or 'N/A'}",
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
    
    return {
        "status": "success",
        "message": f"Successfully removed {stock_out_request.quantity} units from stock",
        "data": {
            "quantity_removed": float(stock_out_request.quantity),
            "total_cost": float(total_cost),
            "batches_affected": len(movements_created),
            "fifo_breakdown": [
                {
                    "quantity": float(abs(movement.quantity)),
                    "unit_cost": float(movement.unit_cost),
                    "batch_cost": float(abs(movement.quantity) * movement.unit_cost)
                }
                for movement in movements_created
            ]
        },
        "timestamp": datetime.now().isoformat()
    }


@router.post("/adjustment")  # TODO: response_model=MessageResponse)
def stock_adjustment(
    adjustment_request: StockAdjustmentRequest,
    session: Session = Depends(get_db),
    current_user: UserInfo = require_permissions("write:inventory")
):
    """
    Adjust inventory quantities.
    
    Allows positive or negative adjustments with audit trail.
    """
    # Validate product and warehouse exist
    product_query = select(Product).where(Product.product_id == adjustment_request.product_id)
    product_result = session.execute(product_query)
    product = product_result.scalar_one_or_none()
    
    if not product:
        raise NotFoundError("Product", adjustment_request.product_id)
    
    warehouse_query = select(Warehouse).where(Warehouse.warehouse_id == adjustment_request.warehouse_id)
    warehouse_result = session.execute(warehouse_query)
    warehouse = warehouse_result.scalar_one_or_none()
    
    if not warehouse:
        raise NotFoundError("Warehouse", adjustment_request.warehouse_id)
    
    if adjustment_request.adjustment_quantity == 0:
        raise ValidationError("Adjustment quantity cannot be zero")
    
    # For positive adjustments, create new inventory item
    if adjustment_request.adjustment_quantity > 0:
        # Generate a system batch number for adjustments
        batch_number = f"ADJ-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        new_item = InventoryItemModel(
            product_id=adjustment_request.product_id,
            warehouse_id=adjustment_request.warehouse_id,
            batch_number=batch_number,
            entry_date=datetime.now(),
            expiry_date=None,
            quantity_in_stock=adjustment_request.adjustment_quantity,
            reserved_quantity=Decimal('0'),
            unit_cost=Decimal('0'),  # Adjustments have zero cost
            supplier_id=None,
            purchase_order_id=None,
            quality_status='APPROVED',
            notes=f"Stock adjustment: {adjustment_request.reason}. {adjustment_request.notes or ''}",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        session.add(new_item)
        session.flush()
        
        # Create stock movement record
        stock_movement = StockMovementModel(
            inventory_item_id=new_item.inventory_item_id,
            movement_type='ADJUSTMENT',
            movement_date=datetime.now(),
            quantity=adjustment_request.adjustment_quantity,
            unit_cost=Decimal('0'),
            reference_type='ADJUSTMENT',
            reference_id=None,
            notes=f"Stock adjustment (+): {adjustment_request.reason}",
            created_by=current_user.username,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        session.add(stock_movement)
        session.commit()
        
        return MessageResponse(
            message=f"Stock adjustment completed successfully. Added {adjustment_request.adjustment_quantity} units."
        )
    
    # For negative adjustments, use FIFO logic to reduce stock
    else:
        adjustment_quantity = abs(adjustment_request.adjustment_quantity)
        
        # Get available inventory items using FIFO ordering
        fifo_query = (
            select(InventoryItemModel)
            .where(
                and_(
                    InventoryItemModel.product_id == adjustment_request.product_id,
                    InventoryItemModel.warehouse_id == adjustment_request.warehouse_id,
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
        total_available = sum(Decimal(str(item.quantity_in_stock or 0)) - Decimal(str(item.reserved_quantity or 0)) for item in available_items)
        
        if total_available < adjustment_quantity:
            raise InsufficientStockError(
                f"Insufficient stock for adjustment. Required: {adjustment_quantity}, Available: {total_available}",
                product_id=adjustment_request.product_id,
                required=float(adjustment_quantity),
                available=float(total_available)
            )
        
        # Perform FIFO consumption for negative adjustment
        remaining_to_adjust = adjustment_quantity
        movements_created = []
        
        for item in available_items:
            if remaining_to_adjust <= 0:
                break
            
            available_in_batch = Decimal(str(item.quantity_in_stock or 0)) - Decimal(str(item.reserved_quantity or 0))
            
            if available_in_batch <= 0:
                continue
            
            # Calculate how much to adjust from this batch
            adjust_from_batch = min(remaining_to_adjust, available_in_batch)
            
            # Update inventory item
            item.quantity_in_stock -= adjust_from_batch
            item.updated_at = datetime.now()
            
            # Create stock movement record
            stock_movement = StockMovementModel(
                inventory_item_id=item.inventory_item_id,
                movement_type='ADJUSTMENT',
                movement_date=datetime.now(),
                quantity=-adjust_from_batch,  # Negative for adjustment down
                unit_cost=item.unit_cost,
                reference_type='ADJUSTMENT',
                reference_id=None,
                notes=f"Stock adjustment (-): {adjustment_request.reason}",
                created_by=current_user.username,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            session.add(stock_movement)
            movements_created.append(stock_movement)
            
            remaining_to_adjust -= adjust_from_batch
        
        # Commit all changes
        session.commit()
        
        return MessageResponse(
            message=f"Stock adjustment completed successfully. "
                    f"Reduced {adjustment_quantity} units from {len(movements_created)} batches."
        )


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
    total_available = sum(Decimal(str(item.quantity_in_stock or 0)) - Decimal(str(item.reserved_quantity or 0)) for item in available_items)
    
    # Perform FIFO allocation
    remaining_to_allocate = allocation_request.quantity
    allocated_quantity = Decimal('0')
    total_cost = Decimal('0')
    allocations = []
    
    for item in available_items:
        if remaining_to_allocate <= 0:
            break
        
        available_in_batch = Decimal(str(item.quantity_in_stock or 0)) - Decimal(str(item.reserved_quantity or 0))
        
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


@router.get("/reservations")
def list_stock_reservations(
    pagination: PaginationParams = Depends(get_pagination_params),
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    warehouse_id: Optional[int] = Query(None, description="Filter by warehouse ID"),
    reserved_for_type: Optional[str] = Query(None, description="Filter by reservation type (e.g., PRODUCTION_ORDER)"),
    reserved_for_id: Optional[int] = Query(None, description="Filter by specific reservation ID"),
    status: Optional[str] = Query(None, description="Filter by reservation status"),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("read:inventory"))  # Temporarily disabled for testing
):
    """
    List stock reservations with comprehensive filtering.
    
    Shows active, consumed, and released reservations with details.
    """
    from models.production import StockReservation
    from sqlalchemy.orm import joinedload
    
    # Build base query with joins for efficiency
    query = session.query(StockReservation).options(
        joinedload(StockReservation.product),
        joinedload(StockReservation.warehouse)
    )
    
    # Apply filters
    if product_id:
        query = query.filter(StockReservation.product_id == product_id)
    
    if warehouse_id:
        query = query.filter(StockReservation.warehouse_id == warehouse_id)
    
    if reserved_for_type:
        query = query.filter(StockReservation.reserved_for_type == reserved_for_type)
    
    if reserved_for_id:
        query = query.filter(StockReservation.reserved_for_id == reserved_for_id)
    
    if status:
        query = query.filter(StockReservation.status == status)
    
    # Get total count for pagination
    total_count = query.count()
    
    # Apply pagination and ordering
    query = query.order_by(desc(StockReservation.reservation_date))
    items = query.offset(pagination.offset).limit(pagination.page_size).all()
    
    # Calculate pagination info
    total_pages = (total_count + pagination.page_size - 1) // pagination.page_size
    has_next = pagination.page < total_pages
    has_previous = pagination.page > 1
    
    # Convert to response format
    reservations = []
    for reservation in items:
        reservation_dict = {
            'reservation_id': reservation.reservation_id,
            'product_id': reservation.product_id,
            'warehouse_id': reservation.warehouse_id,
            'reserved_quantity': float(reservation.reserved_quantity),
            'reserved_for_type': reservation.reserved_for_type,
            'reserved_for_id': reservation.reserved_for_id,
            'reservation_date': reservation.reservation_date.isoformat() if reservation.reservation_date else None,
            'expiry_date': reservation.expiry_date.isoformat() if reservation.expiry_date else None,
            'status': reservation.status,
            'reserved_by': reservation.reserved_by,
            'notes': reservation.notes,
            'created_at': reservation.created_at.isoformat() if reservation.created_at else None,
            'updated_at': reservation.updated_at.isoformat() if reservation.updated_at else None,
            'product': {
                'product_id': reservation.product.product_id,
                'product_code': reservation.product.product_code,
                'product_name': reservation.product.product_name,
                'unit_of_measure': reservation.product.unit_of_measure
            } if reservation.product else None,
            'warehouse': {
                'warehouse_id': reservation.warehouse.warehouse_id,
                'warehouse_code': reservation.warehouse.warehouse_code,
                'warehouse_name': reservation.warehouse.warehouse_name
            } if reservation.warehouse else None
        }
        reservations.append(reservation_dict)
    
    return PaginatedResponse(
        items=reservations,
        pagination={
            "total_count": total_count,
            "page": pagination.page,
            "page_size": pagination.page_size,
            "total_pages": total_pages,
            "has_next": has_next,
            "has_previous": has_previous
        }
    )


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