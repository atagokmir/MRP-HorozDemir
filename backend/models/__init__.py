"""
Horoz Demir MRP System - SQLAlchemy ORM Models
============================================

This package contains all SQLAlchemy ORM models for the Horoz Demir MRP system.
The models are organized by functional area and support:

- FIFO inventory management
- Nested Bill of Materials (BOM) hierarchies
- Production order management with stock allocations
- Procurement and purchase order tracking
- Critical stock monitoring and cost calculation history

Model Organization:
- base: Base classes and mixins for all models
- master_data: Warehouses, products, suppliers, and relationships
- inventory: FIFO inventory tracking and stock movements
- bom: Bill of materials with nested hierarchy support
- production: Production orders, components, and stock allocations
- procurement: Purchase orders and supplier management
- reporting: Critical stock alerts and cost calculation history

Usage:
    from backend.models import (
        Warehouse, Product, Supplier, ProductSupplier,
        InventoryItem, StockMovement,
        BillOfMaterials, BomComponent, BomCostCalculation,
        ProductionOrder, ProductionOrderComponent, StockAllocation,
        PurchaseOrder, PurchaseOrderItem,
        CriticalStockAlert, CostCalculationHistory
    )
"""

# Import base components
from .base import (
    Base, 
    BaseModel, 
    TimestampMixin, 
    ActiveRecordMixin, 
    AuditMixin,
    set_session_user,
    validate_decimal_range,
    validate_percentage,
    validate_rating,
    PercentageColumn,
    RatingColumn,
    CurrencyColumn,
    QuantityColumn
)

# Import master data models
from .master_data import (
    Warehouse,
    Product,
    Supplier,
    ProductSupplier
)

# Import inventory models
from .inventory import (
    InventoryItem,
    StockMovement
)

# Import BOM models
from .bom import (
    BillOfMaterials,
    BomComponent,
    BomCostCalculation
)

# Import production models
from .production import (
    ProductionOrder,
    ProductionOrderComponent,
    StockAllocation
)

# Import procurement models
from .procurement import (
    PurchaseOrder,
    PurchaseOrderItem
)

# Import reporting models
from .reporting import (
    CriticalStockAlert,
    CostCalculationHistory
)

# Model registry for easy access
MODEL_REGISTRY = {
    # Master Data
    'warehouse': Warehouse,
    'product': Product,
    'supplier': Supplier,
    'product_supplier': ProductSupplier,
    
    # Inventory
    'inventory_item': InventoryItem,
    'stock_movement': StockMovement,
    
    # BOM
    'bill_of_materials': BillOfMaterials,
    'bom_component': BomComponent,
    'bom_cost_calculation': BomCostCalculation,
    
    # Production
    'production_order': ProductionOrder,
    'production_order_component': ProductionOrderComponent,
    'stock_allocation': StockAllocation,
    
    # Procurement
    'purchase_order': PurchaseOrder,
    'purchase_order_item': PurchaseOrderItem,
    
    # Reporting
    'critical_stock_alert': CriticalStockAlert,
    'cost_calculation_history': CostCalculationHistory,
}

# Export all models for convenient importing
__all__ = [
    # Base components
    'Base',
    'BaseModel',
    'TimestampMixin',
    'ActiveRecordMixin', 
    'AuditMixin',
    'set_session_user',
    'validate_decimal_range',
    'validate_percentage',
    'validate_rating',
    'PercentageColumn',
    'RatingColumn',
    'CurrencyColumn',
    'QuantityColumn',
    
    # Master Data Models
    'Warehouse',
    'Product', 
    'Supplier',
    'ProductSupplier',
    
    # Inventory Models
    'InventoryItem',
    'StockMovement',
    
    # BOM Models
    'BillOfMaterials',
    'BomComponent', 
    'BomCostCalculation',
    
    # Production Models
    'ProductionOrder',
    'ProductionOrderComponent',
    'StockAllocation',
    
    # Procurement Models
    'PurchaseOrder',
    'PurchaseOrderItem',
    
    # Reporting Models
    'CriticalStockAlert',
    'CostCalculationHistory',
    
    # Registry
    'MODEL_REGISTRY',
]

# Version information
__version__ = '1.0.0'
__author__ = 'Database Schema Architect'
__description__ = 'SQLAlchemy ORM models for Horoz Demir MRP System'


def get_model_by_name(name: str):
    """
    Get a model class by its registry name.
    
    Args:
        name: Model name from MODEL_REGISTRY
        
    Returns:
        Model class or None if not found
    """
    return MODEL_REGISTRY.get(name.lower())


def list_all_models():
    """
    Get a list of all model classes.
    
    Returns:
        List of all model classes
    """
    return list(MODEL_REGISTRY.values())


def list_model_names():
    """
    Get a list of all model registry names.
    
    Returns:
        List of model names
    """
    return list(MODEL_REGISTRY.keys())


# Import order validation - ensure all models are imported correctly
def validate_model_imports():
    """Validate that all models are properly imported and registered."""
    missing_models = []
    
    for name, model_class in MODEL_REGISTRY.items():
        if not hasattr(model_class, '__tablename__'):
            missing_models.append(f"{name}: Missing __tablename__ attribute")
        
        if not hasattr(model_class, '__table_args__'):
            # This is optional, so just log a warning
            pass
    
    if missing_models:
        raise ImportError(f"Model import validation failed: {missing_models}")
    
    return True


# Validate imports when module is loaded
try:
    validate_model_imports()
except ImportError as e:
    print(f"Warning: Model validation failed: {e}")


# Database relationship validation
def validate_relationships():
    """
    Validate that all foreign key relationships are properly defined.
    This should be called after all models are loaded.
    """
    relationship_errors = []
    
    # Validate key relationships
    test_relationships = [
        (InventoryItem, 'product'),
        (InventoryItem, 'warehouse'),
        (ProductionOrder, 'product'),
        (ProductionOrder, 'bom'),
        (BomComponent, 'bom'),
        (BomComponent, 'component_product'),
        (PurchaseOrderItem, 'purchase_order'),
        (StockAllocation, 'production_order'),
        (StockAllocation, 'inventory_item'),
    ]
    
    for model, relationship_name in test_relationships:
        if not hasattr(model, relationship_name):
            relationship_errors.append(f"{model.__name__}.{relationship_name}")
    
    if relationship_errors:
        raise ValueError(f"Missing relationships: {relationship_errors}")
    
    return True