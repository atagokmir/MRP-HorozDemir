"""
Master Data API endpoints for warehouses, products, and suppliers.
Handles CRUD operations for core system entities.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.dependencies import (
    get_db, get_current_active_user, require_permissions,
    get_pagination_params, get_filter_params, PaginationParams, FilterParams
)
from app.schemas.base import PaginatedResponse, IDResponse, MessageResponse
from app.schemas.auth import UserInfo
from app.schemas.master_data import (
    # Warehouse schemas
    WarehouseCreate, WarehouseUpdate, Warehouse, WarehouseList,
    # Product schemas  
    ProductCreate, ProductUpdate, Product, ProductSummary, ProductList,
    # Supplier schemas
    SupplierCreate, SupplierUpdate, Supplier, SupplierSummary, SupplierList,
    # Product-Supplier schemas
    ProductSupplierCreate, ProductSupplierUpdate, ProductSupplier, ProductSupplierList
)
from app.services.base import BaseService
from app.exceptions import NotFoundError, ValidationError, ConflictError
from models.master_data import Warehouse as WarehouseModel, Product as ProductModel, Supplier as SupplierModel


router = APIRouter()

# Service instances
warehouse_service = BaseService[WarehouseModel](WarehouseModel)
product_service = BaseService[ProductModel](ProductModel)
supplier_service = BaseService[SupplierModel](SupplierModel)


# =============================================================================
# WAREHOUSE ENDPOINTS
# =============================================================================

@router.get("/warehouses", response_model=PaginatedResponse[Warehouse])
async def list_warehouses(
    pagination: PaginationParams = Depends(get_pagination_params),
    filters: FilterParams = Depends(get_filter_params),
    warehouse_type: Optional[str] = Query(None, description="Filter by warehouse type"),
    session: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(require_permissions("read:warehouses"))
):
    """
    List warehouses with filtering and pagination.
    
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 20, max: 100)
    - **search**: Search in warehouse name/code
    - **sort_by**: Field to sort by
    - **sort_order**: Sort direction (asc/desc)
    - **active_only**: Show only active warehouses
    - **warehouse_type**: Filter by warehouse type
    """
    additional_filters = []
    
    # Type filter
    if warehouse_type:
        additional_filters.append(WarehouseModel.warehouse_type == warehouse_type)
    
    warehouses, total_count = await warehouse_service.list_with_filters(
        session, pagination, filters, additional_filters
    )
    
    return PaginatedResponse(
        items=[Warehouse.from_orm(w) for w in warehouses],
        pagination={
            "total_count": total_count,
            "page": pagination.page,
            "page_size": pagination.page_size,
            "total_pages": (total_count + pagination.page_size - 1) // pagination.page_size,
            "has_next": pagination.page * pagination.page_size < total_count,
            "has_previous": pagination.page > 1
        }
    )


@router.get("/warehouses/{warehouse_id}", response_model=Warehouse)
async def get_warehouse(
    warehouse_id: int = Path(..., description="Warehouse ID"),
    session: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(require_permissions("read:warehouses"))
):
    """Get warehouse by ID."""
    warehouse = await warehouse_service.get_by_id(session, warehouse_id)
    return Warehouse.from_orm(warehouse)


@router.post("/warehouses", response_model=IDResponse)
async def create_warehouse(
    warehouse_create: WarehouseCreate,
    session: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(require_permissions("write:warehouses"))
):
    """
    Create new warehouse.
    
    - **warehouse_code**: Unique warehouse code (2-10 chars)
    - **warehouse_name**: Warehouse name
    - **warehouse_type**: Type (RAW_MATERIALS, SEMI_FINISHED, FINISHED_PRODUCTS, PACKAGING)
    - **location**: Physical location (optional)
    - **manager_name**: Manager name (optional)
    """
    # Check for duplicate warehouse code
    query = select(WarehouseModel).where(
        WarehouseModel.warehouse_code == warehouse_create.warehouse_code.upper()
    )
    result = await session.execute(query)
    if result.scalar_one_or_none():
        raise ConflictError(f"Warehouse code '{warehouse_create.warehouse_code}' already exists")
    
    warehouse = await warehouse_service.create(
        session, 
        warehouse_create.dict(),
        current_user.user_id
    )
    await session.commit()
    
    return IDResponse(
        id=warehouse.warehouse_id,
        message=f"Warehouse '{warehouse.warehouse_name}' created successfully"
    )


@router.put("/warehouses/{warehouse_id}", response_model=Warehouse)
async def update_warehouse(
    warehouse_id: int = Path(..., description="Warehouse ID"),
    warehouse_update: WarehouseUpdate = ...,
    session: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(require_permissions("write:warehouses"))
):
    """Update warehouse information."""
    warehouse = await warehouse_service.update(
        session,
        warehouse_id,
        {k: v for k, v in warehouse_update.dict().items() if v is not None},
        current_user.user_id
    )
    await session.commit()
    return Warehouse.from_orm(warehouse)


@router.delete("/warehouses/{warehouse_id}", response_model=MessageResponse)
async def delete_warehouse(
    warehouse_id: int = Path(..., description="Warehouse ID"),
    session: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(require_permissions("write:warehouses"))
):
    """Soft delete warehouse (sets is_active to false)."""
    await warehouse_service.delete(session, warehouse_id, user_id=current_user.user_id)
    await session.commit()
    
    return MessageResponse(message=f"Warehouse {warehouse_id} deleted successfully")


# =============================================================================
# PRODUCT ENDPOINTS  
# =============================================================================

@router.get("/products", response_model=PaginatedResponse[Product])
async def list_products(
    pagination: PaginationParams = Depends(get_pagination_params),
    filters: FilterParams = Depends(get_filter_params),
    product_type: Optional[str] = Query(None, description="Filter by product type"),
    session: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(require_permissions("read:products"))
):
    """
    List products with filtering and pagination.
    
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 20, max: 100)
    - **search**: Search in product name/code
    - **sort_by**: Field to sort by
    - **sort_order**: Sort direction (asc/desc)
    - **active_only**: Show only active products
    - **product_type**: Filter by product type
    """
    additional_filters = []
    
    # Type filter
    if product_type:
        additional_filters.append(ProductModel.product_type == product_type)
    
    products, total_count = await product_service.list_with_filters(
        session, pagination, filters, additional_filters
    )
    
    return PaginatedResponse(
        items=[Product.from_orm(p) for p in products],
        pagination={
            "total_count": total_count,
            "page": pagination.page,
            "page_size": pagination.page_size,
            "total_pages": (total_count + pagination.page_size - 1) // pagination.page_size,
            "has_next": pagination.page * pagination.page_size < total_count,
            "has_previous": pagination.page > 1
        }
    )


@router.get("/products/summary", response_model=List[ProductSummary])
async def get_products_summary(
    product_type: Optional[str] = Query(None, description="Filter by product type"),
    session: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(require_permissions("read:products"))
):
    """Get product summary list for dropdowns and selection."""
    query = select(ProductModel).where(ProductModel.is_active == True)
    
    if product_type:
        query = query.where(ProductModel.product_type == product_type)
    
    query = query.order_by(ProductModel.product_code)
    
    result = await session.execute(query)
    products = result.scalars().all()
    
    return [ProductSummary.from_orm(p) for p in products]


@router.get("/products/{product_id}", response_model=Product)
async def get_product(
    product_id: int = Path(..., description="Product ID"),
    session: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(require_permissions("read:products"))
):
    """Get product by ID."""
    product = await product_service.get_by_id(session, product_id)
    return Product.from_orm(product)


@router.post("/products", response_model=IDResponse)
async def create_product(
    product_create: ProductCreate,
    session: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(require_permissions("write:products"))
):
    """
    Create new product.
    
    - **product_code**: Unique product code (3-20 chars)
    - **product_name**: Product name
    - **product_type**: Type (RAW_MATERIAL, SEMI_FINISHED, FINISHED_PRODUCT, PACKAGING)
    - **unit_of_measure**: Unit (kg, pcs, m, etc.)
    - **standard_cost**: Standard cost per unit (optional)
    - **critical_stock_level**: Critical stock level (optional)
    """
    # Check for duplicate product code
    query = select(ProductModel).where(
        ProductModel.product_code == product_create.product_code.upper()
    )
    result = await session.execute(query)
    if result.scalar_one_or_none():
        raise ConflictError(f"Product code '{product_create.product_code}' already exists")
    
    product = await product_service.create(
        session,
        product_create.dict(),
        current_user.user_id
    )
    await session.commit()
    
    return IDResponse(
        id=product.product_id,
        message=f"Product '{product.product_name}' created successfully"
    )


@router.put("/products/{product_id}", response_model=Product)
async def update_product(
    product_id: int = Path(..., description="Product ID"),
    product_update: ProductUpdate = ...,
    session: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(require_permissions("write:products"))
):
    """Update product information."""
    product = await product_service.update(
        session,
        product_id,
        {k: v for k, v in product_update.dict().items() if v is not None},
        current_user.user_id
    )
    await session.commit()
    return Product.from_orm(product)


@router.delete("/products/{product_id}", response_model=MessageResponse)
async def delete_product(
    product_id: int = Path(..., description="Product ID"),
    session: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(require_permissions("write:products"))
):
    """Soft delete product (sets is_active to false)."""
    await product_service.delete(session, product_id, user_id=current_user.user_id)
    await session.commit()
    
    return MessageResponse(message=f"Product {product_id} deleted successfully")


# =============================================================================
# SUPPLIER ENDPOINTS
# =============================================================================

@router.get("/suppliers", response_model=PaginatedResponse[Supplier])
async def list_suppliers(
    pagination: PaginationParams = Depends(get_pagination_params),
    filters: FilterParams = Depends(get_filter_params),
    session: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(require_permissions("read:suppliers"))
):
    """
    List suppliers with filtering and pagination.
    
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 20, max: 100)
    - **search**: Search in supplier name/code
    - **sort_by**: Field to sort by
    - **sort_order**: Sort direction (asc/desc)
    - **active_only**: Show only active suppliers
    """
    suppliers, total_count = await supplier_service.list_with_filters(
        session, pagination, filters
    )
    
    return PaginatedResponse(
        items=[Supplier.from_orm(s) for s in suppliers],
        pagination={
            "total_count": total_count,
            "page": pagination.page,
            "page_size": pagination.page_size,
            "total_pages": (total_count + pagination.page_size - 1) // pagination.page_size,
            "has_next": pagination.page * pagination.page_size < total_count,
            "has_previous": pagination.page > 1
        }
    )


@router.get("/suppliers/summary", response_model=List[SupplierSummary])
async def get_suppliers_summary(
    session: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(require_permissions("read:suppliers"))
):
    """Get supplier summary list for dropdowns and selection."""
    query = select(SupplierModel).where(
        SupplierModel.is_active == True
    ).order_by(SupplierModel.supplier_code)
    
    result = await session.execute(query)
    suppliers = result.scalars().all()
    
    return [SupplierSummary.from_orm(s) for s in suppliers]


@router.get("/suppliers/{supplier_id}", response_model=Supplier)
async def get_supplier(
    supplier_id: int = Path(..., description="Supplier ID"),
    session: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(require_permissions("read:suppliers"))
):
    """Get supplier by ID."""
    supplier = await supplier_service.get_by_id(session, supplier_id)
    return Supplier.from_orm(supplier)


@router.post("/suppliers", response_model=IDResponse)
async def create_supplier(
    supplier_create: SupplierCreate,
    session: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(require_permissions("write:suppliers"))
):
    """
    Create new supplier.
    
    - **supplier_code**: Unique supplier code (2-20 chars)
    - **supplier_name**: Company name
    - **contact_person**: Contact person name (optional)
    - **email**: Contact email (optional)
    - **phone**: Contact phone (optional)
    - **address**: Company address (optional)
    """
    # Check for duplicate supplier code
    query = select(SupplierModel).where(
        SupplierModel.supplier_code == supplier_create.supplier_code.upper()
    )
    result = await session.execute(query)
    if result.scalar_one_or_none():
        raise ConflictError(f"Supplier code '{supplier_create.supplier_code}' already exists")
    
    supplier = await supplier_service.create(
        session,
        supplier_create.dict(),
        current_user.user_id
    )
    await session.commit()
    
    return IDResponse(
        id=supplier.supplier_id,
        message=f"Supplier '{supplier.supplier_name}' created successfully"
    )


@router.put("/suppliers/{supplier_id}", response_model=Supplier)
async def update_supplier(
    supplier_id: int = Path(..., description="Supplier ID"),
    supplier_update: SupplierUpdate = ...,
    session: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(require_permissions("write:suppliers"))
):
    """Update supplier information."""
    supplier = await supplier_service.update(
        session,
        supplier_id,
        {k: v for k, v in supplier_update.dict().items() if v is not None},
        current_user.user_id
    )
    await session.commit()
    return Supplier.from_orm(supplier)


@router.delete("/suppliers/{supplier_id}", response_model=MessageResponse)
async def delete_supplier(
    supplier_id: int = Path(..., description="Supplier ID"),
    session: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(require_permissions("write:suppliers"))
):
    """Soft delete supplier (sets is_active to false)."""
    await supplier_service.delete(session, supplier_id, user_id=current_user.user_id)
    await session.commit()
    
    return MessageResponse(message=f"Supplier {supplier_id} deleted successfully")