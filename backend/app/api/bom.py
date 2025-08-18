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
    # Legacy compatibility schemas
    BOM, CreateBOMRequest, UpdateBOMRequest, BOMCostCalculation
)
from app.exceptions import NotFoundError, CircularBOMError, InvalidBOMError
from models.bom import BillOfMaterials, BomComponent, BomCostCalculation as BomCostModel
from models.master_data import Product

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


@router.get("/{bom_id}/cost-calculation")  # TODO: # response_model=BOMCostCalculation
def calculate_bom_cost(
    bom_id: int = Path(..., description="BOM ID"),
    quantity: Decimal = Query(Decimal('1'), description="Quantity for calculation"),
    session: Session = Depends(get_db),
    current_user: UserInfo = require_permissions("read:bom")
):
    """
    Calculate BOM cost based on current inventory.
    
    Uses FIFO costing for accurate material cost calculation.
    """
    # TODO: Implement BOM cost calculation with FIFO
    return {
        "bom_id": bom_id,
        "quantity": float(quantity),
        "material_cost": 0.0,
        "labor_cost": 0.0,
        "overhead_cost": 0.0,
        "total_cost": 0.0,
        "status": "success",
        "message": "BOM cost calculation completed (placeholder)",
        "timestamp": datetime.now().isoformat()
    }


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