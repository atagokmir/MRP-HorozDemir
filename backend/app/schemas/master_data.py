"""
Master data schemas for warehouses, products, and suppliers.
Defines data structures for core system entities.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import Field, validator
from app.schemas.base import (
    BaseSchema, TimestampMixin, ProductType, WarehouseType,
    validate_product_code, validate_warehouse_code, validate_non_negative_decimal
)


# Warehouse schemas
class WarehouseBase(BaseSchema):
    """Base warehouse schema."""
    warehouse_code: str = Field(..., description="Unique warehouse code")
    warehouse_name: str = Field(..., min_length=1, max_length=100, description="Warehouse name")
    warehouse_type: WarehouseType = Field(..., description="Type of warehouse")
    location: Optional[str] = Field(None, max_length=200, description="Warehouse location/address")
    manager_name: Optional[str] = Field(None, max_length=100, description="Warehouse manager name")
    description: Optional[str] = Field(None, max_length=500, description="Additional description")
    
    @validator('warehouse_code')
    def validate_warehouse_code_field(cls, v):
        return validate_warehouse_code(v)


class WarehouseCreate(WarehouseBase):
    """Create warehouse request."""
    pass


class WarehouseUpdate(BaseSchema):
    """Update warehouse request."""
    warehouse_name: Optional[str] = Field(None, min_length=1, max_length=100)
    warehouse_type: Optional[WarehouseType] = None
    location: Optional[str] = Field(None, max_length=200)
    manager_name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class Warehouse(WarehouseBase, TimestampMixin):
    """Full warehouse information."""
    warehouse_id: int
    is_active: bool = True


class WarehouseList(BaseSchema):
    """Warehouse list response."""
    warehouses: List[Warehouse]
    total_count: int


# Product schemas
class ProductBase(BaseSchema):
    """Base product schema."""
    product_code: str = Field(..., description="Unique product code")
    product_name: str = Field(..., min_length=1, max_length=200, description="Product name")
    product_type: ProductType = Field(..., description="Type of product")
    unit_of_measure: str = Field(..., max_length=10, description="Unit of measurement (kg, pcs, etc.)")
    standard_cost: Optional[Decimal] = Field(None, ge=0, description="Standard cost per unit")
    minimum_stock_level: Optional[Decimal] = Field(None, ge=0, description="Minimum stock level")
    critical_stock_level: Optional[Decimal] = Field(None, ge=0, description="Critical stock level")
    description: Optional[str] = Field(None, max_length=1000, description="Product description")
    specifications: Optional[str] = Field(None, max_length=2000, description="Technical specifications")
    
    @validator('product_code')
    def validate_product_code_field(cls, v):
        return validate_product_code(v)
    
    @validator('standard_cost')
    def validate_standard_cost(cls, v):
        """Validate standard cost."""
        return validate_non_negative_decimal(v, "Standard cost")
    
    @validator('minimum_stock_level')
    def validate_minimum_stock_level(cls, v):
        """Validate minimum stock level."""
        return validate_non_negative_decimal(v, "Minimum stock level")
    
    @validator('critical_stock_level')
    def validate_critical_stock_level(cls, v):
        """Validate critical stock level."""
        return validate_non_negative_decimal(v, "Critical stock level")


class ProductCreate(ProductBase):
    """Create product request."""
    pass


class ProductUpdate(BaseSchema):
    """Update product request."""
    product_name: Optional[str] = Field(None, min_length=1, max_length=200)
    product_type: Optional[ProductType] = None
    unit_of_measure: Optional[str] = Field(None, max_length=10)
    standard_cost: Optional[Decimal] = Field(None, ge=0)
    critical_stock_level: Optional[Decimal] = Field(None, ge=0)
    description: Optional[str] = Field(None, max_length=1000)
    specifications: Optional[str] = Field(None, max_length=2000)
    is_active: Optional[bool] = None
    
    @validator('standard_cost')
    def validate_standard_cost(cls, v):
        """Validate standard cost."""
        return validate_non_negative_decimal(v, "Standard cost") if v is not None else v
    
    @validator('critical_stock_level')
    def validate_critical_stock_level(cls, v):
        """Validate critical stock level."""
        return validate_non_negative_decimal(v, "Critical stock level") if v is not None else v


class Product(ProductBase, TimestampMixin):
    """Full product information."""
    product_id: int
    is_active: bool = True


class ProductSummary(BaseSchema):
    """Product summary for dropdowns."""
    product_id: int
    product_code: str
    product_name: str
    product_type: ProductType
    unit_of_measure: str


class ProductList(BaseSchema):
    """Product list response."""
    products: List[Product]
    total_count: int


# Supplier schemas
class SupplierBase(BaseSchema):
    """Base supplier schema."""
    supplier_code: str = Field(..., min_length=2, max_length=20, description="Unique supplier code")
    supplier_name: str = Field(..., min_length=1, max_length=200, description="Supplier company name")
    contact_person: Optional[str] = Field(None, max_length=100, description="Contact person name")
    email: Optional[str] = Field(None, max_length=100, description="Contact email")
    phone: Optional[str] = Field(None, max_length=20, description="Contact phone")
    address: Optional[str] = Field(None, max_length=500, description="Supplier address")
    tax_number: Optional[str] = Field(None, max_length=20, description="Tax identification number")
    payment_terms: Optional[str] = Field(None, max_length=100, description="Payment terms")
    currency: str = Field("TRY", max_length=3, description="Default currency")
    
    @validator('supplier_code')
    def validate_supplier_code(cls, v):
        """Validate supplier code format."""
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Supplier code can only contain letters, numbers, hyphens, and underscores')
        return v.upper()
    
    @validator('email')
    def validate_email(cls, v):
        """Basic email validation."""
        if v and '@' not in v:
            raise ValueError('Invalid email format')
        return v.lower() if v else v


class SupplierCreate(SupplierBase):
    """Create supplier request."""
    pass


class SupplierUpdate(BaseSchema):
    """Update supplier request."""
    supplier_name: Optional[str] = Field(None, min_length=1, max_length=200)
    contact_person: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = Field(None, max_length=500)
    tax_number: Optional[str] = Field(None, max_length=20)
    payment_terms: Optional[str] = Field(None, max_length=100)
    currency: Optional[str] = Field(None, max_length=3)
    is_active: Optional[bool] = None
    
    @validator('email')
    def validate_email(cls, v):
        """Basic email validation."""
        if v and '@' not in v:
            raise ValueError('Invalid email format')
        return v.lower() if v else v


class Supplier(SupplierBase, TimestampMixin):
    """Full supplier information."""
    supplier_id: int
    is_active: bool = True


class SupplierSummary(BaseSchema):
    """Supplier summary for dropdowns."""
    supplier_id: int
    supplier_code: str
    supplier_name: str
    contact_person: Optional[str] = None


class SupplierList(BaseSchema):
    """Supplier list response."""
    suppliers: List[Supplier]
    total_count: int


# Product-Supplier relationship schemas
class ProductSupplierBase(BaseSchema):
    """Base product-supplier relationship."""
    product_id: int
    supplier_id: int
    supplier_product_code: Optional[str] = Field(None, max_length=50, description="Supplier's product code")
    unit_price: Optional[Decimal] = Field(None, ge=0, description="Unit price from supplier")
    minimum_order_quantity: Optional[Decimal] = Field(None, ge=0, description="Minimum order quantity")
    lead_time_days: Optional[int] = Field(None, ge=0, description="Lead time in days")
    is_preferred: bool = Field(False, description="Is this the preferred supplier")
    
    @validator('unit_price')
    def validate_unit_price(cls, v):
        """Validate unit price."""
        return validate_non_negative_decimal(v, "Unit price")
    
    @validator('minimum_order_quantity')
    def validate_minimum_order_quantity(cls, v):
        """Validate minimum order quantity."""
        return validate_non_negative_decimal(v, "Minimum order quantity")


class ProductSupplierCreate(ProductSupplierBase):
    """Create product-supplier relationship."""
    pass


class ProductSupplierUpdate(BaseSchema):
    """Update product-supplier relationship."""
    supplier_product_code: Optional[str] = Field(None, max_length=50)
    unit_price: Optional[Decimal] = Field(None, ge=0)
    minimum_order_quantity: Optional[Decimal] = Field(None, ge=0)
    lead_time_days: Optional[int] = Field(None, ge=0)
    is_preferred: Optional[bool] = None
    is_active: Optional[bool] = None


class ProductSupplier(ProductSupplierBase, TimestampMixin):
    """Full product-supplier relationship."""
    product_supplier_id: int
    product: ProductSummary
    supplier: SupplierSummary
    is_active: bool = True


class ProductSupplierList(BaseSchema):
    """Product-supplier list response."""
    relationships: List[ProductSupplier]
    total_count: int