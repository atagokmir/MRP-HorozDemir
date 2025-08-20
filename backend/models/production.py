"""
Production Management Models for Horoz Demir MRP System.
This module contains SQLAlchemy models for production orders, components, and FIFO stock allocations.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict

from sqlalchemy import (
    Column, Integer, String, Date, DateTime, DECIMAL, Text, Boolean,
    ForeignKey, CheckConstraint, Index, Computed
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from .base import BaseModel, AuditMixin, CurrencyColumn, QuantityColumn


class ProductionOrder(BaseModel, AuditMixin):
    """
    Main production order tracking for manufacturing semi-finished and finished products.
    Includes status tracking and progress monitoring.
    """
    __tablename__ = 'production_orders'
    __table_args__ = (
        CheckConstraint(
            "status IN ('PLANNED', 'RELEASED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'ON_HOLD')",
            name='chk_production_order_status'
        ),
        CheckConstraint(
            "planned_quantity > 0 AND completed_quantity >= 0 AND scrapped_quantity >= 0 AND "
            "(completed_quantity + scrapped_quantity) <= planned_quantity",
            name='chk_production_order_quantities'
        ),
        CheckConstraint("priority >= 1 AND priority <= 10", name='chk_production_order_priority'),
        CheckConstraint("estimated_cost >= 0 AND actual_cost >= 0", name='chk_production_order_costs'),
        CheckConstraint(
            "(planned_start_date IS NULL OR planned_start_date >= order_date) AND "
            "(planned_completion_date IS NULL OR planned_start_date IS NULL OR "
            "planned_completion_date >= planned_start_date) AND "
            "(actual_start_date IS NULL OR actual_start_date >= order_date) AND "
            "(actual_completion_date IS NULL OR actual_start_date IS NULL OR "
            "actual_completion_date >= actual_start_date)",
            name='chk_production_order_dates'
        ),
        # Regex constraints are PostgreSQL-specific, removed for SQLite compatibility
        # Performance indexes
        Index('idx_production_orders_status', 'status', 'planned_start_date'),
        Index('idx_production_orders_product', 'product_id', 'order_date'),
        Index('idx_production_orders_scheduling', 'status', 'planned_start_date', 'priority',
              postgresql_where="status IN ('PLANNED', 'RELEASED', 'IN_PROGRESS')"),
    )
    
    production_order_id = Column(Integer, primary_key=True)
    order_number = Column(String(50), unique=True, nullable=False,
                         comment="Unique production order number in format PO######")
    product_id = Column(Integer, ForeignKey('products.product_id', ondelete='CASCADE'), 
                       nullable=False)
    bom_id = Column(Integer, ForeignKey('bill_of_materials.bom_id', ondelete='CASCADE'), 
                   nullable=False)
    warehouse_id = Column(Integer, ForeignKey('warehouses.warehouse_id', ondelete='CASCADE'), 
                         nullable=False)
    
    order_date = Column(Date, nullable=False, default=date.today)
    planned_start_date = Column(Date, nullable=True)
    planned_completion_date = Column(Date, nullable=True)
    actual_start_date = Column(Date, nullable=True)
    actual_completion_date = Column(Date, nullable=True)
    
    planned_quantity = QuantityColumn.create('planned_quantity', nullable=False)
    completed_quantity = QuantityColumn.create('completed_quantity', default=Decimal('0'))
    scrapped_quantity = QuantityColumn.create('scrapped_quantity', default=Decimal('0'))
    
    status = Column(String(20), default='PLANNED',
                   comment="Order status: PLANNED, RELEASED, IN_PROGRESS, COMPLETED, CANCELLED, ON_HOLD")
    priority = Column(Integer, default=5,
                     comment="Production priority from 1 (highest) to 10 (lowest)")
    
    estimated_cost = CurrencyColumn.create('estimated_cost', default=Decimal('0'))
    actual_cost = CurrencyColumn.create('actual_cost', default=Decimal('0'))
    
    notes = Column(Text, comment="Additional notes about the production order")
    
    # Relationships
    product = relationship("Product", back_populates="production_orders")
    bom = relationship("BillOfMaterials", back_populates="production_orders")
    warehouse = relationship("Warehouse", back_populates="production_orders")
    production_order_components = relationship("ProductionOrderComponent", 
                                             back_populates="production_order",
                                             cascade="all, delete-orphan")
    stock_allocations = relationship("StockAllocation", back_populates="production_order",
                                   cascade="all, delete-orphan")
    
    # New relationships for advanced MRP functionality
    stock_reservations = relationship("StockReservation", 
                                    primaryjoin="and_(ProductionOrder.production_order_id == foreign(StockReservation.reserved_for_id), "
                                              "StockReservation.reserved_for_type == 'PRODUCTION_ORDER')",
                                    viewonly=True)
    dependent_orders = relationship("ProductionDependency", 
                                  foreign_keys="ProductionDependency.parent_production_order_id",
                                  back_populates="parent_production_order",
                                  cascade="all, delete-orphan")
    dependency_orders = relationship("ProductionDependency", 
                                   foreign_keys="ProductionDependency.dependent_production_order_id",
                                   back_populates="dependent_production_order")
    
    @validates('status')
    def validate_status(self, key, status):
        valid_statuses = {'PLANNED', 'RELEASED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'ON_HOLD'}
        if status not in valid_statuses:
            raise ValueError(f"status must be one of: {valid_statuses}")
        return status
    
    @validates('order_number')
    def validate_order_number(self, key, order_number):
        import re
        if not re.match(r'^PO\d{6}$', order_number):
            raise ValueError("order_number must be in format PO######")
        return order_number
    
    @validates('priority')
    def validate_priority(self, key, priority):
        if priority is not None and (priority < 1 or priority > 10):
            raise ValueError("priority must be between 1 and 10")
        return priority
    
    @validates('planned_quantity', 'completed_quantity', 'scrapped_quantity')
    def validate_quantities(self, key, value):
        if value is not None and value < 0:
            raise ValueError(f"{key} must be non-negative")
        if key == 'planned_quantity' and (value is None or value <= 0):
            raise ValueError("planned_quantity must be greater than zero")
        return value
    
    @validates('estimated_cost', 'actual_cost')
    def validate_costs(self, key, value):
        if value is not None and value < 0:
            raise ValueError(f"{key} must be non-negative")
        return value
    
    @hybrid_property
    def remaining_quantity(self):
        """Calculate remaining quantity to complete"""
        return self.planned_quantity - (self.completed_quantity + self.scrapped_quantity)
    
    @hybrid_property
    def completion_percentage(self):
        """Calculate completion percentage"""
        if not self.planned_quantity or self.planned_quantity == 0:
            return Decimal('0')
        return ((self.completed_quantity + self.scrapped_quantity) / self.planned_quantity) * 100
    
    @hybrid_property
    def is_overdue(self):
        """Check if production order is overdue"""
        return (self.planned_completion_date is not None and 
                self.planned_completion_date < date.today() and
                self.status not in ('COMPLETED', 'CANCELLED'))
    
    @hybrid_property
    def is_ready_for_production(self):
        """Check if all components are allocated and order can start production"""
        return (self.status == 'RELEASED' and 
                all(component.allocation_status == 'FULLY_ALLOCATED' 
                    for component in self.production_order_components))
    
    def start_production(self):
        """Start production (change status and set start date)"""
        if self.status != 'RELEASED':
            raise ValueError("Can only start production from RELEASED status")
        
        self.status = 'IN_PROGRESS'
        if self.actual_start_date is None:
            self.actual_start_date = date.today()
    
    def complete_production(self, completed_qty: Decimal, scrapped_qty: Decimal = Decimal('0')):
        """Complete production with specified quantities"""
        if self.status not in ('IN_PROGRESS', 'RELEASED'):
            raise ValueError("Can only complete production from IN_PROGRESS or RELEASED status")
        
        if (completed_qty + scrapped_qty) > self.remaining_quantity:
            raise ValueError("Cannot complete more than remaining quantity")
        
        self.completed_quantity += completed_qty
        self.scrapped_quantity += scrapped_qty
        
        if self.remaining_quantity <= 0:
            self.status = 'COMPLETED'
            if self.actual_completion_date is None:
                self.actual_completion_date = date.today()
    
    def __repr__(self):
        return (f"<ProductionOrder(id={self.production_order_id}, "
                f"number='{self.order_number}', status='{self.status}', "
                f"qty={self.planned_quantity})>")


class ProductionOrderComponent(BaseModel):
    """
    Component requirements and consumption tracking for production orders.
    Links production orders to specific material requirements.
    """
    __tablename__ = 'production_order_components'
    __table_args__ = (
        CheckConstraint(
            "required_quantity > 0 AND allocated_quantity >= 0 AND consumed_quantity >= 0 AND "
            "consumed_quantity <= allocated_quantity AND allocated_quantity <= required_quantity",
            name='chk_po_component_quantities'
        ),
        CheckConstraint(
            "allocation_status IN ('NOT_ALLOCATED', 'PARTIALLY_ALLOCATED', 'FULLY_ALLOCATED', 'CONSUMED')",
            name='chk_po_component_allocation_status'
        ),
        CheckConstraint("unit_cost >= 0", name='chk_po_component_unit_cost'),
        # Performance indexes
        Index('idx_po_components_production_order', 'production_order_id'),
        Index('idx_po_components_product', 'component_product_id'),
        Index('idx_po_components_allocation_status', 'allocation_status',
              postgresql_where="allocation_status IN ('NOT_ALLOCATED', 'PARTIALLY_ALLOCATED')"),
    )
    
    po_component_id = Column(Integer, primary_key=True)
    production_order_id = Column(Integer, 
                                ForeignKey('production_orders.production_order_id', ondelete='CASCADE'), 
                                nullable=False)
    component_product_id = Column(Integer, ForeignKey('products.product_id', ondelete='CASCADE'), 
                                 nullable=False)
    
    required_quantity = QuantityColumn.create('required_quantity', nullable=False)
    allocated_quantity = QuantityColumn.create('allocated_quantity', default=Decimal('0'))
    consumed_quantity = QuantityColumn.create('consumed_quantity', default=Decimal('0'))
    
    unit_cost = CurrencyColumn.create('unit_cost', default=Decimal('0'))
    total_cost = Column(
        DECIMAL(15, 4),
        Computed('consumed_quantity * unit_cost'),
        comment="Calculated field: consumed_quantity * unit_cost"
    )
    
    allocation_status = Column(String(20), default='NOT_ALLOCATED',
                              comment="Allocation status: NOT_ALLOCATED, PARTIALLY_ALLOCATED, FULLY_ALLOCATED, CONSUMED")
    
    # Enhanced component-level tracking fields
    component_status = Column(String(20), default='NOT_STARTED',
                             comment="Component production status: NOT_STARTED, IN_PROGRESS, COMPLETED, CANCELLED")
    started_at = Column(DateTime, nullable=True,
                       comment="When component production started")
    completed_at = Column(DateTime, nullable=True,
                         comment="When component production completed")
    
    # Relationships
    production_order = relationship("ProductionOrder", back_populates="production_order_components")
    component_product = relationship("Product", back_populates="production_order_components")
    
    @validates('required_quantity', 'allocated_quantity', 'consumed_quantity')
    def validate_quantities(self, key, value):
        if value is not None and value < 0:
            raise ValueError(f"{key} must be non-negative")
        if key == 'required_quantity' and (value is None or value <= 0):
            raise ValueError("required_quantity must be greater than zero")
        return value
    
    @validates('allocation_status')
    def validate_allocation_status(self, key, allocation_status):
        valid_statuses = {'NOT_ALLOCATED', 'PARTIALLY_ALLOCATED', 'FULLY_ALLOCATED', 'CONSUMED'}
        if allocation_status not in valid_statuses:
            raise ValueError(f"allocation_status must be one of: {valid_statuses}")
        return allocation_status
    
    @validates('component_status')
    def validate_component_status(self, key, component_status):
        valid_statuses = {'NOT_STARTED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED'}
        if component_status not in valid_statuses:
            raise ValueError(f"component_status must be one of: {valid_statuses}")
        return component_status
    
    @validates('unit_cost')
    def validate_unit_cost(self, key, unit_cost):
        if unit_cost is not None and unit_cost < 0:
            raise ValueError("unit_cost must be non-negative")
        return unit_cost
    
    @hybrid_property
    def remaining_allocation(self):
        """Calculate remaining quantity to allocate"""
        return self.required_quantity - self.allocated_quantity
    
    @hybrid_property
    def remaining_consumption(self):
        """Calculate remaining allocated quantity to consume"""
        return self.allocated_quantity - self.consumed_quantity
    
    @hybrid_property
    def allocation_percentage(self):
        """Calculate allocation percentage"""
        if not self.required_quantity or self.required_quantity == 0:
            return Decimal('0')
        return (self.allocated_quantity / self.required_quantity) * 100
    
    @hybrid_property
    def consumption_percentage(self):
        """Calculate consumption percentage of allocated quantity"""
        if not self.allocated_quantity or self.allocated_quantity == 0:
            return Decimal('0')
        return (self.consumed_quantity / self.allocated_quantity) * 100
    
    def allocate_quantity(self, quantity: Decimal):
        """Allocate additional quantity"""
        if quantity <= 0:
            raise ValueError("Allocation quantity must be positive")
        
        if (self.allocated_quantity + quantity) > self.required_quantity:
            raise ValueError("Cannot allocate more than required quantity")
        
        self.allocated_quantity += quantity
        self._update_allocation_status()
    
    def consume_quantity(self, quantity: Decimal, unit_cost: Decimal = None):
        """Consume allocated quantity"""
        if quantity <= 0:
            raise ValueError("Consumption quantity must be positive")
        
        if (self.consumed_quantity + quantity) > self.allocated_quantity:
            raise ValueError("Cannot consume more than allocated quantity")
        
        self.consumed_quantity += quantity
        if unit_cost is not None:
            self.unit_cost = unit_cost
        self._update_allocation_status()
    
    def _update_allocation_status(self):
        """Update allocation status based on current quantities"""
        if self.allocated_quantity == 0:
            self.allocation_status = 'NOT_ALLOCATED'
        elif self.consumed_quantity == self.allocated_quantity:
            self.allocation_status = 'CONSUMED'
        elif self.allocated_quantity < self.required_quantity:
            self.allocation_status = 'PARTIALLY_ALLOCATED'
        else:
            self.allocation_status = 'FULLY_ALLOCATED'
    
    def start_component(self):
        """Start component production"""
        if self.component_status != 'NOT_STARTED':
            raise ValueError(f"Cannot start component in {self.component_status} status")
        self.component_status = 'IN_PROGRESS'
        self.started_at = datetime.now()
    
    def complete_component(self):
        """Complete component production"""
        if self.component_status != 'IN_PROGRESS':
            raise ValueError(f"Cannot complete component in {self.component_status} status")
        self.component_status = 'COMPLETED'
        self.completed_at = datetime.now()
    
    def cancel_component(self):
        """Cancel component production"""
        self.component_status = 'CANCELLED'
    
    @hybrid_property
    def is_component_completed(self):
        """Check if component is completed"""
        return self.component_status == 'COMPLETED'
    
    @hybrid_property
    def component_duration(self):
        """Calculate component production duration in hours"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() / 3600
        elif self.started_at:
            return (datetime.now() - self.started_at).total_seconds() / 3600
        return None
    
    def __repr__(self):
        return (f"<ProductionOrderComponent(id={self.po_component_id}, "
                f"po_id={self.production_order_id}, product_id={self.component_product_id}, "
                f"required={self.required_quantity}, allocated={self.allocated_quantity})>")


class StockAllocation(BaseModel):
    """
    FIFO-based stock allocation tracking - reserves specific inventory batches
    for production orders based on entry date (first in, first out).
    """
    __tablename__ = 'stock_allocations'
    __table_args__ = (
        CheckConstraint(
            "allocated_quantity > 0 AND consumed_quantity >= 0 AND consumed_quantity <= allocated_quantity",
            name='chk_stock_allocation_quantities'
        ),
        CheckConstraint(
            "status IN ('ALLOCATED', 'PARTIALLY_CONSUMED', 'FULLY_CONSUMED', 'RELEASED')",
            name='chk_stock_allocation_status'
        ),
        CheckConstraint(
            "consumption_date IS NULL OR consumption_date >= allocation_date",
            name='chk_stock_allocation_dates'
        ),
        # Performance indexes
        Index('idx_stock_allocations_production_order', 'production_order_id'),
        Index('idx_stock_allocations_inventory_item', 'inventory_item_id'),
        Index('idx_stock_allocations_status', 'status',
              postgresql_where="status IN ('ALLOCATED', 'PARTIALLY_CONSUMED')"),
        Index('idx_production_fifo_lookup', 'production_order_id', 'inventory_item_id',
              postgresql_where="status IN ('ALLOCATED', 'PARTIALLY_CONSUMED')"),
    )
    
    allocation_id = Column(Integer, primary_key=True)
    production_order_id = Column(Integer, 
                                ForeignKey('production_orders.production_order_id', ondelete='CASCADE'), 
                                nullable=False)
    inventory_item_id = Column(Integer, 
                              ForeignKey('inventory_items.inventory_item_id', ondelete='CASCADE'), 
                              nullable=False)
    
    allocated_quantity = QuantityColumn.create('allocated_quantity', nullable=False)
    consumed_quantity = QuantityColumn.create('consumed_quantity', default=Decimal('0'))
    remaining_allocation = Column(
        DECIMAL(15, 4),
        Computed('allocated_quantity - consumed_quantity'),
        comment="Calculated field: allocated_quantity - consumed_quantity"
    )
    
    allocation_date = Column(DateTime, nullable=False, default=datetime.now)
    consumption_date = Column(DateTime, nullable=True)
    
    status = Column(String(20), default='ALLOCATED',
                   comment="Allocation status: ALLOCATED, PARTIALLY_CONSUMED, FULLY_CONSUMED, RELEASED")
    
    # Relationships
    production_order = relationship("ProductionOrder", back_populates="stock_allocations")
    inventory_item = relationship("InventoryItem", back_populates="stock_allocations")
    
    @validates('allocated_quantity', 'consumed_quantity')
    def validate_quantities(self, key, value):
        if value is not None and value < 0:
            raise ValueError(f"{key} must be non-negative")
        if key == 'allocated_quantity' and (value is None or value <= 0):
            raise ValueError("allocated_quantity must be greater than zero")
        return value
    
    @validates('status')
    def validate_status(self, key, status):
        valid_statuses = {'ALLOCATED', 'PARTIALLY_CONSUMED', 'FULLY_CONSUMED', 'RELEASED'}
        if status not in valid_statuses:
            raise ValueError(f"status must be one of: {valid_statuses}")
        return status
    
    @validates('consumption_date')
    def validate_consumption_date(self, key, consumption_date):
        if (consumption_date and self.allocation_date and 
            consumption_date < self.allocation_date):
            raise ValueError("consumption_date cannot be before allocation_date")
        return consumption_date
    
    @hybrid_property
    def is_fully_consumed(self):
        """Check if allocation is fully consumed"""
        return self.consumed_quantity == self.allocated_quantity
    
    @hybrid_property
    def is_partially_consumed(self):
        """Check if allocation is partially consumed"""
        return 0 < self.consumed_quantity < self.allocated_quantity
    
    @hybrid_property
    def consumption_percentage(self):
        """Calculate consumption percentage"""
        if not self.allocated_quantity or self.allocated_quantity == 0:
            return Decimal('0')
        return (self.consumed_quantity / self.allocated_quantity) * 100
    
    def consume_allocation(self, quantity: Decimal):
        """Consume from this allocation"""
        if quantity <= 0:
            raise ValueError("Consumption quantity must be positive")
        
        if (self.consumed_quantity + quantity) > self.allocated_quantity:
            raise ValueError("Cannot consume more than allocated quantity")
        
        self.consumed_quantity += quantity
        
        if self.consumption_date is None:
            self.consumption_date = datetime.now()
        
        self._update_status()
    
    def release_allocation(self):
        """Release this allocation (make it available again)"""
        self.status = 'RELEASED'
        self.consumed_quantity = Decimal('0')
        self.consumption_date = None
    
    def _update_status(self):
        """Update status based on consumption"""
        if self.consumed_quantity == 0:
            self.status = 'ALLOCATED'
        elif self.consumed_quantity < self.allocated_quantity:
            self.status = 'PARTIALLY_CONSUMED'
        else:
            self.status = 'FULLY_CONSUMED'
    
    def __repr__(self):
        return (f"<StockAllocation(id={self.allocation_id}, "
                f"po_id={self.production_order_id}, item_id={self.inventory_item_id}, "
                f"allocated={self.allocated_quantity}, consumed={self.consumed_quantity})>")


# Additional indexes for production scheduling and capacity planning
Index('idx_production_capacity_planning', 
      ProductionOrder.warehouse_id, ProductionOrder.planned_start_date, 
      ProductionOrder.planned_completion_date, ProductionOrder.status,
      postgresql_where="status IN ('PLANNED', 'RELEASED', 'IN_PROGRESS')")

Index('idx_production_completion_tracking', 
      ProductionOrder.actual_completion_date.desc(), ProductionOrder.status,
      postgresql_where="status IN ('COMPLETED', 'IN_PROGRESS')")


class StockReservation(BaseModel, AuditMixin):
    """
    Stock reservations for production planning and advanced MRP functionality.
    Reserves specific quantities of inventory for production orders before actual allocation.
    """
    __tablename__ = 'stock_reservations'
    __table_args__ = (
        CheckConstraint(
            "reserved_quantity > 0",
            name='chk_stock_reservation_quantity'
        ),
        CheckConstraint(
            "reserved_for_type IN ('PRODUCTION_ORDER', 'PLANNING', 'FORECAST')",
            name='chk_stock_reservation_type'
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'CONSUMED', 'RELEASED', 'EXPIRED')",
            name='chk_stock_reservation_status'
        ),
        CheckConstraint(
            "expiry_date IS NULL OR expiry_date > reservation_date",
            name='chk_stock_reservation_dates'
        ),
        # Performance indexes
        Index('idx_stock_reservations_product', 'product_id', 'warehouse_id', 'status'),
        Index('idx_stock_reservations_reference', 'reserved_for_type', 'reserved_for_id'),
        Index('idx_stock_reservations_expiry', 'expiry_date', 'status',
              postgresql_where="status = 'ACTIVE'"),
    )
    
    reservation_id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.product_id', ondelete='CASCADE'), 
                       nullable=False)
    warehouse_id = Column(Integer, ForeignKey('warehouses.warehouse_id', ondelete='CASCADE'), 
                         nullable=False)
    reserved_quantity = QuantityColumn.create('reserved_quantity', nullable=False)
    
    reserved_for_type = Column(String(30), nullable=False,
                              comment="Type of entity this reservation is for: PRODUCTION_ORDER, PLANNING, FORECAST")
    reserved_for_id = Column(Integer, nullable=False,
                            comment="ID of the entity this reservation is for")
    
    reservation_date = Column(DateTime, nullable=False, default=datetime.now)
    expiry_date = Column(DateTime, nullable=True,
                        comment="When this reservation expires (optional)")
    status = Column(String(20), default='ACTIVE',
                   comment="Reservation status: ACTIVE, CONSUMED, RELEASED, EXPIRED")
    
    notes = Column(Text, comment="Additional notes about this reservation")
    reserved_by = Column(String(100), comment="User who created this reservation")
    
    # Relationships
    product = relationship("Product", back_populates="stock_reservations")
    warehouse = relationship("Warehouse", back_populates="stock_reservations")
    
    @validates('reserved_quantity')
    def validate_reserved_quantity(self, key, reserved_quantity):
        if reserved_quantity is None or reserved_quantity <= 0:
            raise ValueError("reserved_quantity must be greater than zero")
        return reserved_quantity
    
    @validates('reserved_for_type')
    def validate_reserved_for_type(self, key, reserved_for_type):
        valid_types = {'PRODUCTION_ORDER', 'PLANNING', 'FORECAST'}
        if reserved_for_type not in valid_types:
            raise ValueError(f"reserved_for_type must be one of: {valid_types}")
        return reserved_for_type
    
    @validates('status')
    def validate_status(self, key, status):
        valid_statuses = {'ACTIVE', 'CONSUMED', 'RELEASED', 'EXPIRED'}
        if status not in valid_statuses:
            raise ValueError(f"status must be one of: {valid_statuses}")
        return status
    
    @validates('expiry_date')
    def validate_expiry_date(self, key, expiry_date):
        if expiry_date and self.reservation_date and expiry_date <= self.reservation_date:
            raise ValueError("expiry_date must be after reservation_date")
        return expiry_date
    
    @hybrid_property
    def is_expired(self):
        """Check if reservation is expired"""
        return (self.expiry_date is not None and 
                self.expiry_date <= datetime.now())
    
    @hybrid_property
    def days_until_expiry(self):
        """Calculate days until expiry"""
        if self.expiry_date:
            return (self.expiry_date - datetime.now()).days
        return None
    
    def release_reservation(self):
        """Release this reservation (make quantity available again)"""
        self.status = 'RELEASED'
        self.updated_at = datetime.now()
    
    def consume_reservation(self):
        """Mark this reservation as consumed"""
        self.status = 'CONSUMED'
        self.updated_at = datetime.now()
    
    def extend_expiry(self, new_expiry_date: datetime):
        """Extend the expiry date of this reservation"""
        if new_expiry_date <= datetime.now():
            raise ValueError("New expiry date must be in the future")
        self.expiry_date = new_expiry_date
        self.updated_at = datetime.now()
    
    def __repr__(self):
        return (f"<StockReservation(id={self.reservation_id}, "
                f"product_id={self.product_id}, qty={self.reserved_quantity}, "
                f"status='{self.status}')>")


class ProductionDependency(BaseModel):
    """
    Production dependencies for nested production orders in complex MRP scenarios.
    Tracks relationships between production orders where one depends on another.
    """
    __tablename__ = 'production_dependencies'
    __table_args__ = (
        CheckConstraint(
            "dependency_quantity > 0",
            name='chk_production_dependency_quantity'
        ),
        CheckConstraint(
            "dependency_type IN ('COMPONENT', 'SEQUENCE', 'RESOURCE', 'SETUP')",
            name='chk_production_dependency_type'
        ),
        CheckConstraint(
            "status IN ('PENDING', 'SATISFIED', 'BLOCKED', 'CANCELLED')",
            name='chk_production_dependency_status'
        ),
        CheckConstraint(
            "parent_production_order_id != dependent_production_order_id",
            name='chk_production_dependency_different_orders'
        ),
        # Performance indexes
        Index('idx_production_dependencies_parent', 'parent_production_order_id'),
        Index('idx_production_dependencies_dependent', 'dependent_production_order_id'),
        Index('idx_production_dependencies_status', 'status', 'dependency_type'),
    )
    
    dependency_id = Column(Integer, primary_key=True)
    parent_production_order_id = Column(Integer, 
                                       ForeignKey('production_orders.production_order_id', ondelete='CASCADE'), 
                                       nullable=False)
    dependent_production_order_id = Column(Integer, 
                                          ForeignKey('production_orders.production_order_id', ondelete='CASCADE'), 
                                          nullable=False)
    
    dependency_type = Column(String(20), default='COMPONENT',
                            comment="Type of dependency: COMPONENT, SEQUENCE, RESOURCE, SETUP")
    dependency_quantity = QuantityColumn.create('dependency_quantity', nullable=False)
    
    status = Column(String(20), default='PENDING',
                   comment="Dependency status: PENDING, SATISFIED, BLOCKED, CANCELLED")
    
    required_by_date = Column(DateTime, nullable=True,
                             comment="When this dependency must be satisfied")
    satisfied_at = Column(DateTime, nullable=True,
                         comment="When this dependency was satisfied")
    
    notes = Column(Text, comment="Additional notes about this dependency")
    
    # Relationships
    parent_production_order = relationship("ProductionOrder", 
                                          foreign_keys=[parent_production_order_id],
                                          back_populates="dependent_orders")
    dependent_production_order = relationship("ProductionOrder", 
                                             foreign_keys=[dependent_production_order_id],
                                             back_populates="dependency_orders")
    
    @validates('dependency_quantity')
    def validate_dependency_quantity(self, key, dependency_quantity):
        if dependency_quantity is None or dependency_quantity <= 0:
            raise ValueError("dependency_quantity must be greater than zero")
        return dependency_quantity
    
    @validates('dependency_type')
    def validate_dependency_type(self, key, dependency_type):
        valid_types = {'COMPONENT', 'SEQUENCE', 'RESOURCE', 'SETUP'}
        if dependency_type not in valid_types:
            raise ValueError(f"dependency_type must be one of: {valid_types}")
        return dependency_type
    
    @validates('status')
    def validate_status(self, key, status):
        valid_statuses = {'PENDING', 'SATISFIED', 'BLOCKED', 'CANCELLED'}
        if status not in valid_statuses:
            raise ValueError(f"status must be one of: {valid_statuses}")
        return status
    
    @validates('required_by_date')
    def validate_required_by_date(self, key, required_by_date):
        if required_by_date and required_by_date <= datetime.now():
            raise ValueError("required_by_date must be in the future")
        return required_by_date
    
    @hybrid_property
    def is_overdue(self):
        """Check if dependency is overdue"""
        return (self.required_by_date is not None and 
                self.required_by_date < datetime.now() and
                self.status == 'PENDING')
    
    @hybrid_property
    def is_satisfied(self):
        """Check if dependency is satisfied"""
        return self.status == 'SATISFIED'
    
    def satisfy_dependency(self):
        """Mark this dependency as satisfied"""
        self.status = 'SATISFIED'
        self.satisfied_at = datetime.now()
    
    def block_dependency(self, reason: str = None):
        """Mark this dependency as blocked"""
        self.status = 'BLOCKED'
        if reason:
            current_notes = self.notes or ""
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            block_note = f"\n[{timestamp}] Blocked: {reason}"
            self.notes = current_notes + block_note
    
    def cancel_dependency(self):
        """Cancel this dependency"""
        self.status = 'CANCELLED'
    
    def __repr__(self):
        return (f"<ProductionDependency(id={self.dependency_id}, "
                f"parent={self.parent_production_order_id}, "
                f"dependent={self.dependent_production_order_id}, "
                f"type='{self.dependency_type}', status='{self.status}')>")