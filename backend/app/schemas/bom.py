"""
Pydantic schemas for BOM (Bill of Materials) API endpoints.
Handles request/response validation and documentation.
"""

from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import date, datetime
from pydantic import BaseModel, Field, validator, ConfigDict

from .base import TimestampMixin


class BomComponentBase(BaseModel):
    """Base schema for BOM component."""
    component_product_id: int = Field(..., description="ID of the component product")
    sequence_number: int = Field(..., gt=0, description="Assembly sequence order")
    quantity_required: Decimal = Field(..., gt=0, description="Required quantity of component")
    unit_of_measure: str = Field(..., max_length=20, description="Unit of measurement")
    scrap_percentage: Optional[Decimal] = Field(None, ge=0, le=50, description="Expected scrap percentage")
    is_phantom: bool = Field(False, description="True for phantom assemblies")
    substitute_group: Optional[str] = Field(None, max_length=20, description="Substitute group identifier")
    notes: Optional[str] = Field(None, description="Component-specific notes")


class BomComponentCreate(BomComponentBase):
    """Schema for creating BOM components."""
    pass


class BomComponentUpdate(BomComponentBase):
    """Schema for updating BOM components."""
    component_product_id: Optional[int] = Field(None, description="ID of the component product")
    sequence_number: Optional[int] = Field(None, gt=0, description="Assembly sequence order")
    quantity_required: Optional[Decimal] = Field(None, gt=0, description="Required quantity of component")
    unit_of_measure: Optional[str] = Field(None, max_length=20, description="Unit of measurement")


class BomComponentResponse(BomComponentBase, TimestampMixin):
    """Schema for BOM component response."""
    model_config = ConfigDict(from_attributes=True)
    
    bom_component_id: int
    bom_id: int
    effective_quantity: Optional[Decimal] = Field(None, description="Quantity including scrap")
    
    # Related objects (when included)
    component_product: Optional[Dict[str, Any]] = None


class BillOfMaterialsBase(BaseModel):
    """Base schema for BOM."""
    parent_product_id: int = Field(..., description="ID of the parent product")
    bom_version: str = Field("1.0", pattern=r"^\d+\.\d+$", description="Version in format X.Y")
    bom_name: str = Field(..., max_length=200, description="Descriptive name for BOM")
    effective_date: date = Field(default_factory=date.today, description="Effective date")
    expiry_date: Optional[date] = Field(None, description="Expiry date (optional)")
    status: str = Field("ACTIVE", pattern="^(DRAFT|ACTIVE|INACTIVE|OBSOLETE)$", description="BOM status")
    base_quantity: Decimal = Field(Decimal('1'), gt=0, description="Base production quantity")
    yield_percentage: Decimal = Field(Decimal('100.00'), gt=0, le=100, description="Yield percentage")
    labor_cost_per_unit: Optional[Decimal] = Field(Decimal('0'), ge=0, description="Labor cost per unit")
    overhead_cost_per_unit: Optional[Decimal] = Field(Decimal('0'), ge=0, description="Overhead cost per unit")
    notes: Optional[str] = Field(None, description="Additional notes")

    @validator('expiry_date')
    def expiry_after_effective(cls, v, values):
        if v and 'effective_date' in values and v <= values['effective_date']:
            raise ValueError('expiry_date must be after effective_date')
        return v


class BillOfMaterialsCreate(BillOfMaterialsBase):
    """Schema for creating BOM."""
    bom_components: List[BomComponentCreate] = Field(..., min_items=1, description="BOM components")


class BillOfMaterialsUpdate(BillOfMaterialsBase):
    """Schema for updating BOM."""
    parent_product_id: Optional[int] = Field(None, description="ID of the parent product")
    bom_name: Optional[str] = Field(None, max_length=200, description="Descriptive name for BOM")
    bom_components: Optional[List[BomComponentCreate]] = Field(None, description="Updated BOM components")


class BillOfMaterialsResponse(BillOfMaterialsBase, TimestampMixin):
    """Schema for BOM response."""
    model_config = ConfigDict(from_attributes=True)
    
    bom_id: int
    component_count: Optional[int] = None
    is_active: Optional[bool] = None
    current_cost: Optional[Decimal] = None
    
    # Related objects (when included)
    parent_product: Optional[Dict[str, Any]] = None
    bom_components: Optional[List[BomComponentResponse]] = None


# BOM Cost Calculation Schemas
class BomCostCalculationResponse(BaseModel):
    """Schema for BOM cost calculation response."""
    model_config = ConfigDict(from_attributes=True)
    
    bom_cost_id: int
    bom_id: int
    calculation_date: datetime
    material_cost: Decimal
    labor_cost: Decimal
    overhead_cost: Decimal
    total_cost: Decimal
    cost_basis: str = Field(..., pattern="^(FIFO|STANDARD|AVERAGE|ACTUAL)$")
    is_current: bool
    
    # Cost breakdown
    cost_breakdown: Optional[Dict[str, float]] = None


# BOM Explosion Schemas
class BomExplosionItem(BaseModel):
    """Schema for exploded BOM item."""
    product_id: int
    product_code: str
    product_name: str
    required_quantity: Decimal
    unit_of_measure: str
    level: int = Field(..., description="BOM level (0=parent, 1=direct component, etc.)")
    path: str = Field(..., description="Path in BOM hierarchy")
    is_leaf: bool = Field(..., description="True if this is a leaf component (raw material)")


class BomExplosionResponse(BaseModel):
    """Schema for BOM explosion response."""
    bom_id: int
    quantity_multiplier: Decimal
    explosion_items: List[BomExplosionItem]
    total_material_cost: Decimal
    total_labor_cost: Decimal
    total_overhead_cost: Decimal
    total_cost: Decimal
    explosion_date: datetime = Field(default_factory=datetime.now)


# Filter Schemas
class BOMFilters(BaseModel):
    """Schema for BOM filtering parameters."""
    product_id: Optional[int] = Field(None, description="Filter by product ID")
    status: Optional[str] = Field(None, pattern="^(DRAFT|ACTIVE|INACTIVE|OBSOLETE)$", description="Filter by status")
    search: Optional[str] = Field(None, description="Search in BOM name or product name")
    is_active: Optional[bool] = Field(None, description="Filter by active status")


# Legacy compatibility schemas (matching frontend expectations)
class BOMItem(BaseModel):
    """Legacy BOM item schema for frontend compatibility."""
    product_id: int
    quantity: Decimal
    notes: Optional[str] = None


class BOM(BaseModel):
    """Legacy BOM schema for frontend compatibility."""
    bom_id: int
    product_id: int
    bom_code: str
    bom_name: str
    description: Optional[str] = None
    version: str
    total_cost: Optional[Decimal] = None
    is_active: bool
    created_at: str
    updated_at: str
    
    # Related objects
    product: Optional[Dict[str, Any]] = None
    bom_items: Optional[List[Dict[str, Any]]] = None


class CreateBOMRequest(BaseModel):
    """Legacy create BOM request schema for frontend compatibility."""
    product_id: int
    bom_code: str
    bom_name: str
    description: Optional[str] = None
    version: str = "1.0"
    bom_items: List[BOMItem]


class UpdateBOMRequest(BaseModel):
    """Legacy update BOM request schema for frontend compatibility."""
    bom_code: Optional[str] = None
    bom_name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    bom_items: Optional[List[BOMItem]] = None


class BOMCostCalculation(BaseModel):
    """Legacy BOM cost calculation schema for frontend compatibility."""
    bom_id: int
    total_cost: Decimal
    detailed_costs: List[Dict[str, Any]] = []