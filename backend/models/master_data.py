"""
Master Data Models for Horoz Demir MRP System.
This module contains SQLAlchemy models for warehouses, products, suppliers, and their relationships.
"""

from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Column, Integer, String, Boolean, DECIMAL, Text, 
    ForeignKey, UniqueConstraint, CheckConstraint, Index, JSON
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from .base import BaseModel, ActiveRecordMixin, AuditMixin, PercentageColumn, RatingColumn, CurrencyColumn


class Warehouse(BaseModel, ActiveRecordMixin):
    """
    Warehouse model representing the 4 main storage locations.
    Supports: RAW_MATERIALS, SEMI_FINISHED, FINISHED_PRODUCTS, PACKAGING
    """
    __tablename__ = 'warehouses'
    __table_args__ = (
        CheckConstraint(
            "warehouse_type IN ('RAW_MATERIALS', 'SEMI_FINISHED', 'FINISHED_PRODUCTS', 'PACKAGING')",
            name='chk_warehouse_type'
        ),
        # Regex constraints are PostgreSQL-specific, removed for SQLite compatibility
        Index('idx_warehouses_type', 'warehouse_type'),
        Index('idx_warehouses_active', 'is_active', postgresql_where='is_active = true'),
    )
    
    warehouse_id = Column(Integer, primary_key=True)
    warehouse_code = Column(String(10), unique=True, nullable=False, 
                          comment="Unique warehouse identifier code")
    warehouse_name = Column(String(100), nullable=False,
                          comment="Human-readable warehouse name")
    warehouse_type = Column(String(20), nullable=False,
                          comment="Warehouse type: RAW_MATERIALS, SEMI_FINISHED, FINISHED_PRODUCTS, PACKAGING")
    location = Column(String(200), comment="Physical location description")
    manager_name = Column(String(100), comment="Warehouse manager name")
    
    # Relationships
    inventory_items = relationship("InventoryItem", back_populates="warehouse", cascade="all, delete-orphan")
    production_orders = relationship("ProductionOrder", back_populates="warehouse")
    purchase_orders = relationship("PurchaseOrder", back_populates="warehouse")
    critical_stock_alerts = relationship("CriticalStockAlert", back_populates="warehouse")
    
    @validates('warehouse_type')
    def validate_warehouse_type(self, key, warehouse_type):
        valid_types = {'RAW_MATERIALS', 'SEMI_FINISHED', 'FINISHED_PRODUCTS', 'PACKAGING'}
        if warehouse_type not in valid_types:
            raise ValueError(f"warehouse_type must be one of: {valid_types}")
        return warehouse_type
    
    @validates('warehouse_code')
    def validate_warehouse_code(self, key, warehouse_code):
        if not warehouse_code or len(warehouse_code) < 2 or len(warehouse_code) > 10:
            raise ValueError("warehouse_code must be 2-10 characters")
        if not warehouse_code.replace('-', '').replace('_', '').isalnum():
            raise ValueError("warehouse_code must contain only alphanumeric characters, hyphens, and underscores")
        return warehouse_code.upper()
    
    def __repr__(self):
        return f"<Warehouse(id={self.warehouse_id}, code='{self.warehouse_code}', type='{self.warehouse_type}')>"


class Product(BaseModel, ActiveRecordMixin):
    """
    Product model for all items in the system including raw materials,
    semi-finished products, finished products, and packaging materials.
    """
    __tablename__ = 'products'
    __table_args__ = (
        CheckConstraint(
            "product_type IN ('RAW_MATERIAL', 'SEMI_FINISHED', 'FINISHED_PRODUCT', 'PACKAGING')",
            name='chk_product_type'
        ),
        CheckConstraint(
            "minimum_stock_level >= 0 AND critical_stock_level >= 0 AND critical_stock_level <= minimum_stock_level",
            name='chk_stock_levels'
        ),
        CheckConstraint("standard_cost >= 0", name='chk_standard_cost'),
        # Regex constraints are PostgreSQL-specific, removed for SQLite compatibility
        Index('idx_products_type_active', 'product_type', 'is_active', postgresql_where='is_active = true'),
        Index('idx_products_stock_levels', 'product_type', 'minimum_stock_level', 'critical_stock_level', 
              postgresql_where='is_active = true'),
    )
    
    product_id = Column(Integer, primary_key=True)
    product_code = Column(String(50), unique=True, nullable=False,
                         comment="Unique product identifier code")
    product_name = Column(String(200), nullable=False,
                         comment="Product name")
    product_type = Column(String(20), nullable=False,
                         comment="Product category: RAW_MATERIAL, SEMI_FINISHED, FINISHED_PRODUCT, PACKAGING")
    unit_of_measure = Column(String(20), nullable=False,
                           comment="Unit of measurement (e.g., KG, PCS, LITER)")
    minimum_stock_level = CurrencyColumn.create('minimum_stock_level', default=Decimal('0'))
    critical_stock_level = CurrencyColumn.create('critical_stock_level', default=Decimal('0'))
    standard_cost = CurrencyColumn.create('standard_cost', default=Decimal('0'))
    description = Column(Text, comment="Product description")
    specifications = Column(JSON, comment="JSON field for flexible product specifications")
    
    # Relationships
    inventory_items = relationship("InventoryItem", back_populates="product", cascade="all, delete-orphan")
    boms_as_parent = relationship("BillOfMaterials", back_populates="parent_product", 
                                 foreign_keys="BillOfMaterials.parent_product_id")
    bom_components = relationship("BomComponent", back_populates="component_product",
                                foreign_keys="BomComponent.component_product_id")
    product_suppliers = relationship("ProductSupplier", back_populates="product", cascade="all, delete-orphan")
    production_orders = relationship("ProductionOrder", back_populates="product")
    production_order_components = relationship("ProductionOrderComponent", back_populates="component_product")
    purchase_order_items = relationship("PurchaseOrderItem", back_populates="product")
    critical_stock_alerts = relationship("CriticalStockAlert", back_populates="product")
    cost_calculation_history = relationship("CostCalculationHistory", back_populates="product")
    
    @validates('product_type')
    def validate_product_type(self, key, product_type):
        valid_types = {'RAW_MATERIAL', 'SEMI_FINISHED', 'FINISHED_PRODUCT', 'PACKAGING'}
        if product_type not in valid_types:
            raise ValueError(f"product_type must be one of: {valid_types}")
        return product_type
    
    @validates('product_code')
    def validate_product_code(self, key, product_code):
        if not product_code or len(product_code) < 3 or len(product_code) > 50:
            raise ValueError("product_code must be 3-50 characters")
        return product_code.upper()
    
    @validates('minimum_stock_level', 'standard_cost')
    def validate_positive_decimal(self, key, value):
        if value is not None and value < 0:
            raise ValueError(f"{key} must be non-negative")
        return value
    
    @validates('critical_stock_level')
    def validate_critical_stock_level(self, key, critical_stock_level):
        # Check for non-negative value
        if critical_stock_level is not None and critical_stock_level < 0:
            raise ValueError("critical_stock_level must be non-negative")
        
        # Check critical level doesn't exceed minimum level
        if (critical_stock_level is not None and 
            self.minimum_stock_level is not None and 
            critical_stock_level > self.minimum_stock_level):
            raise ValueError("critical_stock_level cannot exceed minimum_stock_level")
        
        return critical_stock_level
    
    @hybrid_property
    def is_producible(self):
        """Check if this product can have production orders"""
        return self.product_type in ('SEMI_FINISHED', 'FINISHED_PRODUCT')
    
    @hybrid_property
    def needs_bom(self):
        """Check if this product requires a BOM"""
        return self.product_type in ('SEMI_FINISHED', 'FINISHED_PRODUCT')
    
    def get_current_stock(self, warehouse_id: Optional[int] = None) -> Decimal:
        """
        Get current available stock for this product.
        
        Args:
            warehouse_id: Specific warehouse ID, None for all warehouses
            
        Returns:
            Total available quantity
        """
        query_filter = [
            self.inventory_items.any(quality_status='APPROVED'),
            self.inventory_items.any(available_quantity > 0)
        ]
        
        if warehouse_id:
            query_filter.append(self.inventory_items.any(warehouse_id=warehouse_id))
        
        # This would need to be implemented with a proper query in the service layer
        return Decimal('0')  # Placeholder
    
    def __repr__(self):
        return f"<Product(id={self.product_id}, code='{self.product_code}', type='{self.product_type}')>"


class Supplier(BaseModel, ActiveRecordMixin, AuditMixin):
    """
    Supplier model for vendor management and supplier information.
    Includes performance ratings and contact details.
    """
    __tablename__ = 'suppliers'
    __table_args__ = (
        CheckConstraint("lead_time_days >= 0", name='chk_lead_time'),
        CheckConstraint("quality_rating >= 0.0 AND quality_rating <= 5.0", name='chk_quality_rating'),
        CheckConstraint("delivery_rating >= 0.0 AND delivery_rating <= 5.0", name='chk_delivery_rating'),
        CheckConstraint("price_rating >= 0.0 AND price_rating <= 5.0", name='chk_price_rating'),
        # Regex constraints are PostgreSQL-specific, removed for SQLite compatibility
        Index('idx_suppliers_performance', 'quality_rating', 'delivery_rating', 'price_rating',
              postgresql_where='is_active = true'),
    )
    
    supplier_id = Column(Integer, primary_key=True)
    supplier_code = Column(String(20), unique=True, nullable=False,
                          comment="Unique supplier identifier code")
    supplier_name = Column(String(200), nullable=False,
                          comment="Supplier company name")
    contact_person = Column(String(100), comment="Primary contact person")
    email = Column(String(100), comment="Primary email address")
    phone = Column(String(20), comment="Primary phone number")
    address = Column(Text, comment="Supplier address")
    tax_number = Column(String(20), comment="Tax identification number")
    payment_terms = Column(String(100), comment="Payment terms and conditions")
    currency = Column(String(3), default="TRY", comment="Default currency")
    city = Column(String(50), comment="City")
    country = Column(String(50), comment="Country")
    lead_time_days = Column(Integer, default=0, comment="Standard lead time in days")
    quality_rating = RatingColumn.create('quality_rating')
    delivery_rating = RatingColumn.create('delivery_rating')  
    price_rating = RatingColumn.create('price_rating')
    
    # Relationships
    product_suppliers = relationship("ProductSupplier", back_populates="supplier", cascade="all, delete-orphan")
    inventory_items = relationship("InventoryItem", back_populates="supplier")
    purchase_orders = relationship("PurchaseOrder", back_populates="supplier")
    
    @validates('supplier_code')
    def validate_supplier_code(self, key, supplier_code):
        if not supplier_code or len(supplier_code) < 2 or len(supplier_code) > 20:
            raise ValueError("supplier_code must be 2-20 characters")
        return supplier_code.upper()
    
    @validates('quality_rating', 'delivery_rating', 'price_rating')
    def validate_rating(self, key, rating):
        if rating is not None and (rating < 0 or rating > 5):
            raise ValueError(f"{key} must be between 0.0 and 5.0")
        return rating
    
    @validates('lead_time_days')
    def validate_lead_time(self, key, lead_time):
        if lead_time is not None and lead_time < 0:
            raise ValueError("lead_time_days must be non-negative")
        return lead_time
    
    @hybrid_property
    def overall_rating(self):
        """Calculate overall supplier rating as average of quality, delivery, and price"""
        ratings = [self.quality_rating, self.delivery_rating, self.price_rating]
        valid_ratings = [r for r in ratings if r is not None and r > 0]
        return sum(valid_ratings) / len(valid_ratings) if valid_ratings else Decimal('0')
    
    def update_performance_ratings(self, quality: Optional[Decimal] = None, 
                                 delivery: Optional[Decimal] = None,
                                 price: Optional[Decimal] = None):
        """
        Update supplier performance ratings.
        
        Args:
            quality: Quality rating (0.0-5.0)
            delivery: Delivery performance rating (0.0-5.0)
            price: Price competitiveness rating (0.0-5.0)
        """
        if quality is not None:
            self.quality_rating = quality
        if delivery is not None:
            self.delivery_rating = delivery
        if price is not None:
            self.price_rating = price
    
    def __repr__(self):
        return f"<Supplier(id={self.supplier_id}, code='{self.supplier_code}', name='{self.supplier_name}')>"


class ProductSupplier(BaseModel, ActiveRecordMixin):
    """
    Many-to-many relationship between products and suppliers.
    Manages supplier-specific pricing, lead times, and preferences.
    """
    __tablename__ = 'product_suppliers'
    __table_args__ = (
        UniqueConstraint('product_id', 'supplier_id', name='uk_product_supplier'),
        CheckConstraint("unit_price > 0", name='chk_unit_price'),
        CheckConstraint("minimum_order_qty >= 0", name='chk_minimum_order_qty'),
        CheckConstraint("lead_time_days >= 0", name='chk_lead_time_days'),
        Index('idx_product_suppliers_product', 'product_id', postgresql_where='is_active = true'),
        Index('idx_product_suppliers_supplier', 'supplier_id', postgresql_where='is_active = true'),
        Index('idx_product_suppliers_preferred', 'product_id', 'is_preferred', 
              postgresql_where='is_preferred = true AND is_active = true'),
    )
    
    product_supplier_id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.product_id', ondelete='CASCADE'), nullable=False)
    supplier_id = Column(Integer, ForeignKey('suppliers.supplier_id', ondelete='CASCADE'), nullable=False)
    supplier_product_code = Column(String(50), comment="Product code used by the supplier")
    unit_price = CurrencyColumn.create('unit_price', nullable=False)
    minimum_order_qty = CurrencyColumn.create('minimum_order_qty', default=Decimal('0'))
    lead_time_days = Column(Integer, default=0, comment="Lead time specific to this product-supplier combination")
    is_preferred = Column(Boolean, default=False, comment="Preferred supplier for this product")
    
    # Relationships
    product = relationship("Product", back_populates="product_suppliers")
    supplier = relationship("Supplier", back_populates="product_suppliers")
    
    @validates('unit_price')
    def validate_unit_price(self, key, unit_price):
        if unit_price is None or unit_price <= 0:
            raise ValueError("unit_price must be greater than zero")
        return unit_price
    
    @validates('minimum_order_qty')
    def validate_minimum_order_qty(self, key, minimum_order_qty):
        if minimum_order_qty is not None and minimum_order_qty < 0:
            raise ValueError("minimum_order_qty must be non-negative")
        return minimum_order_qty
    
    @validates('lead_time_days')
    def validate_lead_time_days(self, key, lead_time_days):
        if lead_time_days is not None and lead_time_days < 0:
            raise ValueError("lead_time_days must be non-negative")
        return lead_time_days
    
    @hybrid_property
    def effective_lead_time(self):
        """Get effective lead time (product-specific or supplier default)"""
        return self.lead_time_days if self.lead_time_days else self.supplier.lead_time_days
    
    def calculate_order_total(self, quantity: Decimal) -> Decimal:
        """
        Calculate total cost for ordering specified quantity.
        
        Args:
            quantity: Quantity to order
            
        Returns:
            Total cost including minimum order quantity adjustment
        """
        effective_quantity = max(quantity, self.minimum_order_qty or Decimal('0'))
        return effective_quantity * self.unit_price
    
    def __repr__(self):
        return (f"<ProductSupplier(id={self.product_supplier_id}, "
                f"product_id={self.product_id}, supplier_id={self.supplier_id}, "
                f"preferred={self.is_preferred})>")


# Indexes for performance optimization
Index('idx_products_fulltext', Product.product_name, Product.description, postgresql_using='gin')
Index('idx_suppliers_fulltext', Supplier.supplier_name, Supplier.city, Supplier.country, postgresql_using='gin')