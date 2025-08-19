"""
BOM (Bill of Materials) API endpoints with explosion and costing algorithms.
Handles BOM management, component relationships, and cost calculations.
"""

from typing import List, Optional
from decimal import Decimal
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Path, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.dependencies import (
    get_db, get_current_active_user, require_permissions,
    get_pagination_params, PaginationParams
)
from app.schemas.base import MessageResponse, IDResponse, PaginatedResponse
from app.schemas.auth import UserInfo
from app.schemas.bom import (
    BillOfMaterialsCreate, BillOfMaterialsUpdate, BillOfMaterialsResponse,
    BomCostCalculationResponse, BomExplosionResponse, BOMFilters,
    EnhancedBomCostCalculation, ComponentCost, FifoBatch,
    # Legacy compatibility schemas
    BOM, CreateBOMRequest, UpdateBOMRequest, BOMCostCalculation
)
from app.exceptions import NotFoundError, CircularBOMError, InvalidBOMError
from models.bom import BillOfMaterials, BomComponent, BomCostCalculation as BomCostModel
from models.master_data import Product
from models.inventory import InventoryItem

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[BOM])
def list_boms(
    pagination: PaginationParams = Depends(get_pagination_params),
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in BOM name"),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("read:bom"))  # Temporarily disabled for testing
):
    """
    List BOMs with filtering and pagination.
    
    Shows all BOMs with their status and effective dates.
    """
    # Build query
    query = session.query(BillOfMaterials)
    
    # Apply filters
    if product_id:
        query = query.filter(BillOfMaterials.parent_product_id == product_id)
    
    if status:
        query = query.filter(BillOfMaterials.status == status)
    
    if search:
        query = query.filter(
            or_(
                BillOfMaterials.bom_name.ilike(f"%{search}%"),
                BillOfMaterials.notes.ilike(f"%{search}%")
            )
        )
    
    # Get total count before pagination
    total_count = query.count()
    
    # Apply pagination
    offset = (pagination.page - 1) * pagination.page_size
    boms = query.offset(offset).limit(pagination.page_size).all()
    
    # Convert to legacy format for frontend compatibility
    items = []
    for bom in boms:
        item = {
            "bom_id": bom.bom_id,
            "id": bom.bom_id,  # For compatibility
            "product_id": bom.parent_product_id,
            "bom_code": f"BOM-{bom.bom_id:04d}",  # Generate code
            "code": f"BOM-{bom.bom_id:04d}",  # For compatibility
            "bom_name": bom.bom_name,
            "name": bom.bom_name,  # For compatibility
            "description": bom.notes,
            "version": bom.bom_version,
            "total_cost": float(bom.get_current_cost()) if bom.get_current_cost() else 0.0,
            "is_active": bom.status == 'ACTIVE',
            "created_at": bom.created_at.isoformat() if bom.created_at else datetime.now().isoformat(),
            "updated_at": bom.updated_at.isoformat() if bom.updated_at else datetime.now().isoformat(),
        }
        
        # Add product info if available
        if bom.parent_product:
            item["product"] = {
                "product_id": bom.parent_product.product_id,
                "product_code": bom.parent_product.product_code,
                "product_name": bom.parent_product.product_name,
                "product_type": bom.parent_product.product_type,
                "unit_of_measure": bom.parent_product.unit_of_measure
            }
        
        # Add BOM items (components) to match frontend expectations
        bom_items = []
        for component in bom.bom_components:
            bom_item = {
                "bom_item_id": component.bom_component_id,
                "bom_id": component.bom_id,
                "product_id": component.component_product_id,
                "quantity": float(component.quantity_required),
                "unit_cost": 0.0,  # TODO: Calculate from inventory
                "total_cost": 0.0,  # TODO: Calculate
                "notes": component.notes,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            
            # Add product info for component
            if component.component_product:
                bom_item["product"] = {
                    "product_id": component.component_product.product_id,
                    "product_code": component.component_product.product_code,
                    "product_name": component.component_product.product_name,
                    "product_type": component.component_product.product_type,
                    "unit_of_measure": component.component_product.unit_of_measure
                }
            
            bom_items.append(bom_item)
        
        item["bom_items"] = bom_items
        items.append(item)
    
    # Calculate pagination info
    total_pages = (total_count + pagination.page_size - 1) // pagination.page_size
    
    return PaginatedResponse(
        items=items,
        pagination={
            "total_count": total_count,
            "page": pagination.page,
            "page_size": pagination.page_size,
            "total_pages": total_pages,
            "has_next": pagination.page < total_pages,
            "has_previous": pagination.page > 1
        }
    )


@router.get("/{bom_id}", response_model=BOM)
def get_bom(
    bom_id: int = Path(..., description="BOM ID"),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("read:bom"))  # Temporarily disabled for testing
):
    """Get BOM by ID with components."""
    bom = session.query(BillOfMaterials).filter(BillOfMaterials.bom_id == bom_id).first()
    
    if not bom:
        raise NotFoundError("BOM", bom_id)
    
    # Convert to legacy format
    result = {
        "bom_id": bom.bom_id,
        "id": bom.bom_id,
        "product_id": bom.parent_product_id,
        "bom_code": f"BOM-{bom.bom_id:04d}",
        "code": f"BOM-{bom.bom_id:04d}",
        "bom_name": bom.bom_name,
        "name": bom.bom_name,
        "description": bom.notes,
        "version": bom.bom_version,
        "total_cost": float(bom.get_current_cost()) if bom.get_current_cost() else 0.0,
        "is_active": bom.status == 'ACTIVE',
        "created_at": bom.created_at.isoformat() if bom.created_at else datetime.now().isoformat(),
        "updated_at": bom.updated_at.isoformat() if bom.updated_at else datetime.now().isoformat(),
    }
    
    # Add product info
    if bom.parent_product:
        result["product"] = {
            "product_id": bom.parent_product.product_id,
            "product_code": bom.parent_product.product_code,
            "product_name": bom.parent_product.product_name,
            "product_type": bom.parent_product.product_type,
            "unit_of_measure": bom.parent_product.unit_of_measure
        }
    
    # Add BOM items
    bom_items = []
    for component in bom.bom_components:
        item = {
            "bom_item_id": component.bom_component_id,
            "bom_id": component.bom_id,
            "product_id": component.component_product_id,
            "quantity": float(component.quantity_required),
            "unit_cost": 0.0,  # TODO: Calculate from inventory
            "total_cost": 0.0,  # TODO: Calculate
            "notes": component.notes,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        
        # Add product info
        if component.component_product:
            item["product"] = {
                "product_id": component.component_product.product_id,
                "product_code": component.component_product.product_code,
                "product_name": component.component_product.product_name,
                "product_type": component.component_product.product_type,
                "unit_of_measure": component.component_product.unit_of_measure
            }
        
        bom_items.append(item)
    
    result["bom_items"] = bom_items
    
    return result


@router.post("/", response_model=BOM)
def create_bom(
    bom_create: CreateBOMRequest,
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("write:bom"))  # Temporarily disabled for testing
):
    """
    Create new BOM with components.
    
    Validates components and checks for circular references.
    """
    try:
        # Verify parent product exists
        parent_product = session.query(Product).filter(Product.product_id == bom_create.product_id).first()
        if not parent_product:
            raise HTTPException(status_code=404, detail=f"Product with ID {bom_create.product_id} not found")
        
        # Create BOM
        bom = BillOfMaterials(
            parent_product_id=bom_create.product_id,
            bom_version=bom_create.version,
            bom_name=bom_create.bom_name,
            notes=bom_create.description,
            status='ACTIVE',
            base_quantity=Decimal('1'),
            yield_percentage=Decimal('100.00'),
            labor_cost_per_unit=Decimal('0'),
            overhead_cost_per_unit=Decimal('0')
        )
        
        session.add(bom)
        session.flush()  # Get BOM ID
        
        # Add components
        sequence_number = 1
        for item in bom_create.bom_items:
            # Verify component product exists
            component_product = session.query(Product).filter(Product.product_id == item.product_id).first()
            if not component_product:
                raise HTTPException(status_code=404, detail=f"Component product with ID {item.product_id} not found")
            
            # Check for circular reference (basic check - product can't contain itself)
            if item.product_id == bom_create.product_id:
                raise HTTPException(status_code=400, detail="Circular reference detected: product cannot contain itself")
            
            component = BomComponent(
                bom_id=bom.bom_id,
                component_product_id=item.product_id,
                sequence_number=sequence_number,
                quantity_required=item.quantity,
                unit_of_measure=component_product.unit_of_measure,
                scrap_percentage=Decimal('0'),
                is_phantom=False,
                notes=item.notes
            )
            
            session.add(component)
            sequence_number += 1
        
        session.commit()
        
        # Return created BOM in legacy format
        return {
            "bom_id": bom.bom_id,
            "id": bom.bom_id,
            "product_id": bom.parent_product_id,
            "bom_code": f"BOM-{bom.bom_id:04d}",
            "code": f"BOM-{bom.bom_id:04d}",
            "bom_name": bom.bom_name,
            "name": bom.bom_name,
            "description": bom.notes,
            "version": bom.bom_version,
            "total_cost": 0.0,
            "is_active": True,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "product": {
                "product_id": parent_product.product_id,
                "product_code": parent_product.product_code,
                "product_name": parent_product.product_name,
                "product_type": parent_product.product_type,
                "unit_of_measure": parent_product.unit_of_measure
            },
            "bom_items": [
                {
                    "product_id": item.product_id,
                    "quantity": float(item.quantity),
                    "notes": item.notes
                }
                for item in bom_create.bom_items
            ]
        }
        
    except Exception as e:
        session.rollback()
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Failed to create BOM: {str(e)}")


@router.put("/{bom_id}", response_model=BOM)
def update_bom(
    bom_update: UpdateBOMRequest,
    bom_id: int = Path(..., description="BOM ID"),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("write:bom"))  # Temporarily disabled for testing
):
    """Update BOM information and components."""
    try:
        # Get existing BOM
        bom = session.query(BillOfMaterials).filter(BillOfMaterials.bom_id == bom_id).first()
        if not bom:
            raise NotFoundError("BOM", bom_id)
        
        # Update basic fields
        if bom_update.bom_name:
            bom.bom_name = bom_update.bom_name
        if bom_update.description is not None:
            bom.notes = bom_update.description
        if bom_update.version:
            bom.bom_version = bom_update.version
        
        # Update components if provided
        if bom_update.bom_items is not None:
            # Remove existing components
            session.query(BomComponent).filter(BomComponent.bom_id == bom_id).delete()
            
            # Add new components
            sequence_number = 1
            for item in bom_update.bom_items:
                # Verify component product exists
                component_product = session.query(Product).filter(Product.product_id == item.product_id).first()
                if not component_product:
                    raise HTTPException(status_code=404, detail=f"Component product with ID {item.product_id} not found")
                
                # Check for circular reference
                if item.product_id == bom.parent_product_id:
                    raise HTTPException(status_code=400, detail="Circular reference detected: product cannot contain itself")
                
                component = BomComponent(
                    bom_id=bom.bom_id,
                    component_product_id=item.product_id,
                    sequence_number=sequence_number,
                    quantity_required=item.quantity,
                    unit_of_measure=component_product.unit_of_measure,
                    scrap_percentage=Decimal('0'),
                    is_phantom=False,
                    notes=item.notes
                )
                
                session.add(component)
                sequence_number += 1
        
        # Update timestamp
        bom.updated_at = datetime.now()
        
        session.commit()
        
        # Return updated BOM (reload to get fresh data)
        return get_bom(bom_id, session)
        
    except Exception as e:
        session.rollback()
        if isinstance(e, HTTPException):
            raise
        if isinstance(e, NotFoundError):
            raise
        raise HTTPException(status_code=500, detail=f"Failed to update BOM: {str(e)}")


@router.get("/{bom_id}/explosion")  # TODO: # response_model=BOMExplosion
def explode_bom(
    bom_id: int = Path(..., description="BOM ID"),
    quantity: Decimal = Query(Decimal('1'), description="Quantity multiplier"),
    session: Session = Depends(get_db),
    current_user: UserInfo = require_permissions("read:bom")
):
    """
    Explode BOM to all raw material requirements.
    
    Recursively processes nested BOMs to create flattened material list.
    """
    # TODO: Implement BOM explosion algorithm
    return BOMExplosion(
        bom_id=bom_id,
        quantity_multiplier=quantity,
        raw_materials=[],
        total_material_cost=Decimal('0'),
        total_labor_cost=Decimal('0'),
        total_overhead_cost=Decimal('0'),
        total_cost=Decimal('0')
    )


@router.get("/{bom_id}/cost-calculation", response_model=EnhancedBomCostCalculation)
def calculate_bom_cost(
    bom_id: int = Path(..., description="BOM ID"),
    quantity: Decimal = Query(Decimal('1'), description="Quantity for calculation"),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("read:bom"))  # Temporarily disabled for testing
):
    """
    Calculate BOM cost based on current inventory using FIFO pricing.
    
    This endpoint:
    1. Fetches BOM components and required quantities
    2. Checks inventory availability for each component
    3. Calculates costs using FIFO (First-In-First-Out) pricing
    4. Returns detailed breakdown including batch information
    5. Identifies components with insufficient stock
    """
    try:
        # Get BOM and verify it exists
        bom = session.query(BillOfMaterials).filter(BillOfMaterials.bom_id == bom_id).first()
        if not bom:
            raise NotFoundError("BOM", bom_id)
        
        # Get BOM components with product information
        components = session.query(BomComponent).filter(
            BomComponent.bom_id == bom_id
        ).all()
        
        if not components:
            raise HTTPException(
                status_code=400, 
                detail=f"BOM {bom_id} has no components defined"
            )
        
        component_costs = []
        missing_components = []
        total_material_cost = Decimal('0')
        components_with_stock = 0
        components_missing_stock = 0
        
        # Process each component
        for component in components:
            # Calculate required quantity for this production quantity
            required_quantity = component.quantity_required * quantity
            
            # Get inventory items for this component (FIFO order)
            inventory_items = session.query(InventoryItem).filter(
                and_(
                    InventoryItem.product_id == component.component_product_id,
                    InventoryItem.quality_status == 'APPROVED',
                    InventoryItem.quantity_in_stock > InventoryItem.reserved_quantity
                )
            ).order_by(
                InventoryItem.entry_date.asc(),  # FIFO: oldest first
                InventoryItem.inventory_item_id.asc()  # Secondary sort for consistency
            ).all()
            
            # Calculate available quantity across all batches
            total_available = sum(
                item.available_quantity for item in inventory_items
            )
            
            # Calculate FIFO cost
            fifo_batches = []
            component_cost = Decimal('0')
            remaining_needed = required_quantity
            
            has_sufficient_stock = total_available >= required_quantity
            
            if has_sufficient_stock:
                components_with_stock += 1
                # Calculate cost using FIFO batches
                for item in inventory_items:
                    if remaining_needed <= 0:
                        break
                    
                    available_from_batch = item.available_quantity
                    quantity_to_use = min(remaining_needed, available_from_batch)
                    
                    if quantity_to_use > 0:
                        batch_cost = quantity_to_use * item.unit_cost
                        component_cost += batch_cost
                        
                        fifo_batches.append(FifoBatch(
                            batch_number=item.batch_number,
                            quantity_used=quantity_to_use,
                            unit_cost=item.unit_cost,
                            entry_date=item.entry_date
                        ))
                        
                        remaining_needed -= quantity_to_use
                
                # Calculate average unit cost for this component
                unit_cost = component_cost / required_quantity if required_quantity > 0 else Decimal('0')
                total_material_cost += component_cost
                
            else:
                components_missing_stock += 1
                # Use available inventory for partial costing if any exists
                for item in inventory_items:
                    if remaining_needed <= 0:
                        break
                    
                    available_from_batch = item.available_quantity
                    quantity_to_use = min(remaining_needed, available_from_batch)
                    
                    if quantity_to_use > 0:
                        batch_cost = quantity_to_use * item.unit_cost
                        component_cost += batch_cost
                        
                        fifo_batches.append(FifoBatch(
                            batch_number=item.batch_number,
                            quantity_used=quantity_to_use,
                            unit_cost=item.unit_cost,
                            entry_date=item.entry_date
                        ))
                        
                        remaining_needed -= quantity_to_use
                
                unit_cost = (component_cost / (required_quantity - remaining_needed) 
                           if (required_quantity - remaining_needed) > 0 else Decimal('0'))
                
                # Add to missing components list
                missing_components.append({
                    "product_id": component.component_product_id,
                    "product_name": component.component_product.product_name if component.component_product else "Unknown",
                    "product_code": component.component_product.product_code if component.component_product else "Unknown",
                    "quantity_required": float(required_quantity),
                    "quantity_available": float(total_available),
                    "quantity_missing": float(remaining_needed)
                })
            
            # Create component cost record
            component_cost_record = ComponentCost(
                product_id=component.component_product_id,
                product_name=component.component_product.product_name if component.component_product else "Unknown",
                product_code=component.component_product.product_code if component.component_product else "Unknown",
                quantity_required=required_quantity,
                quantity_available=total_available,
                unit_cost=unit_cost,
                total_cost=component_cost,
                has_sufficient_stock=has_sufficient_stock,
                fifo_batches=fifo_batches
            )
            
            component_costs.append(component_cost_record)
        
        # Determine if BOM is calculable (all components have sufficient stock)
        calculable = components_missing_stock == 0
        
        # Calculate stock coverage percentage
        total_components = len(components)
        stock_coverage_percentage = (components_with_stock / total_components * 100) if total_components > 0 else 0
        
        # Create response
        response = EnhancedBomCostCalculation(
            bom_id=bom_id,
            quantity=quantity,
            calculable=calculable,
            total_material_cost=total_material_cost,
            component_costs=component_costs,
            missing_components=missing_components,
            calculation_date=datetime.now(),
            cost_basis="FIFO",
            components_with_stock=components_with_stock,
            components_missing_stock=components_missing_stock,
            stock_coverage_percentage=stock_coverage_percentage
        )
        
        return response
        
    except NotFoundError:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to calculate BOM cost: {str(e)}"
        )


@router.delete("/{bom_id}", response_model=MessageResponse)
def delete_bom(
    bom_id: int = Path(..., description="BOM ID"),
    session: Session = Depends(get_db),
    # current_user: UserInfo = Depends(require_permissions("delete:bom"))  # Temporarily disabled for testing
):
    """Delete BOM and its components."""
    try:
        # Get existing BOM
        bom = session.query(BillOfMaterials).filter(BillOfMaterials.bom_id == bom_id).first()
        if not bom:
            raise NotFoundError("BOM", bom_id)
        
        # Check if BOM is used in production orders (if that model exists)
        # TODO: Add check for production orders when implemented
        
        # Delete BOM (components will be deleted by cascade)
        session.delete(bom)
        session.commit()
        
        return MessageResponse(
            message=f"BOM {bom_id} deleted successfully",
            status="success"
        )
        
    except Exception as e:
        session.rollback()
        if isinstance(e, NotFoundError):
            raise
        raise HTTPException(status_code=500, detail=f"Failed to delete BOM: {str(e)}")


@router.put("/{bom_id}/status")  # TODO: # response_model=BOM
def update_bom_status(
    bom_id: int = Path(..., description="BOM ID"),
    status: str = Query(..., description="New status"),
    session: Session = Depends(get_db),
    current_user: UserInfo = require_permissions("write:bom")
):
    """
    Update BOM status (activate, obsolete, etc.).
    
    Manages BOM lifecycle and version control.
    """
    # TODO: Implement BOM status update
    raise NotFoundError("BOM", bom_id)