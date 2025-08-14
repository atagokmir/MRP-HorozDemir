"""
Inventory Management Models for Horoz Demir MRP System.
This module contains SQLAlchemy models for FIFO inventory tracking and stock movements.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Column, Integer, String, DateTime, DECIMAL, Text, Boolean, 
    ForeignKey, CheckConstraint, Index, Computed, event
)
from sqlalchemy.orm import relationship, validates, Session
from sqlalchemy.ext.hybrid import hybrid_property

from .base import BaseModel, CurrencyColumn, QuantityColumn


class InventoryItem(BaseModel):
    """
    Core FIFO inventory tracking model with batch-level stock management.
    Each record represents a specific batch/lot of inventory with entry date
    for FIFO consumption ordering.
    """
    __tablename__ = 'inventory_items'
    __table_args__ = (
        CheckConstraint(
            "quantity_in_stock >= 0 AND reserved_quantity >= 0 AND reserved_quantity <= quantity_in_stock",
            name='chk_inventory_quantities'
        ),
        CheckConstraint("unit_cost >= 0", name='chk_inventory_unit_cost'),
        CheckConstraint(
            "quality_status IN ('PENDING', 'APPROVED', 'REJECTED', 'QUARANTINE')",
            name='chk_inventory_quality_status'
        ),
        CheckConstraint(
            "batch_number ~ '^[A-Z0-9\\-]{3,50}$'",
            name='chk_inventory_batch_format'
        ),
        CheckConstraint("entry_date <= CURRENT_TIMESTAMP", name='chk_inventory_entry_date'),
        CheckConstraint(
            "expiry_date IS NULL OR expiry_date > entry_date",
            name='chk_inventory_expiry_date'
        ),
        CheckConstraint(
            "NOT (product_id, warehouse_id, batch_number, entry_date) IS NULL",
            name='uk_inventory_batch'
        ),
        # FIFO performance indexes
        Index('idx_inventory_fifo_order', 'product_id', 'warehouse_id', 'entry_date', 'inventory_item_id',
              postgresql_where="quality_status = 'APPROVED' AND available_quantity > 0"),
        Index('idx_inventory_available', 'product_id', 'warehouse_id', 'available_quantity',
              postgresql_where="available_quantity > 0"),
        Index('idx_inventory_quality', 'quality_status', 'product_id', 'warehouse_id',
              postgresql_where="quality_status = 'APPROVED'"),
        Index('idx_inventory_batch_lookup', 'batch_number', 'entry_date'),
    )
    
    inventory_item_id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.product_id', ondelete='CASCADE'), 
                       nullable=False)
    warehouse_id = Column(Integer, ForeignKey('warehouses.warehouse_id', ondelete='CASCADE'), 
                         nullable=False)
    batch_number = Column(String(50), nullable=False, 
                         comment="Unique batch identifier for traceability")
    entry_date = Column(DateTime, nullable=False,
                       comment="Critical for FIFO ordering - first entry date consumed first")
    expiry_date = Column(DateTime, nullable=True,
                        comment="Product expiry date (if applicable)")
    
    quantity_in_stock = QuantityColumn.create('quantity_in_stock', nullable=False)
    reserved_quantity = QuantityColumn.create('reserved_quantity', default=Decimal('0'))
    available_quantity = Column(
        DECIMAL(15, 4),
        Computed('quantity_in_stock - reserved_quantity'),
        comment="Calculated field: quantity_in_stock - reserved_quantity"
    )
    
    unit_cost = CurrencyColumn.create('unit_cost', nullable=False)
    total_cost = Column(
        DECIMAL(15, 4),
        Computed('quantity_in_stock * unit_cost'),
        comment="Calculated field: quantity_in_stock * unit_cost"
    )
    
    supplier_id = Column(Integer, ForeignKey('suppliers.supplier_id', ondelete='SET NULL'),
                        nullable=True)
    purchase_order_id = Column(Integer, nullable=True,
                              comment="Reference to purchase order (if applicable)")
    location_in_warehouse = Column(String(50), comment="Physical location within warehouse")
    quality_status = Column(String(20), default='APPROVED',
                           comment="Quality control status: PENDING, APPROVED, REJECTED, QUARANTINE")
    
    # Relationships
    product = relationship("Product", back_populates="inventory_items")
    warehouse = relationship("Warehouse", back_populates="inventory_items")
    supplier = relationship("Supplier", back_populates="inventory_items")
    stock_movements = relationship("StockMovement", back_populates="inventory_item", 
                                 cascade="all, delete-orphan")
    stock_allocations = relationship("StockAllocation", back_populates="inventory_item")
    
    @validates('batch_number')
    def validate_batch_number(self, key, batch_number):
        if not batch_number or len(batch_number) < 3:
            raise ValueError("batch_number must be at least 3 characters")
        return batch_number.upper()
    
    @validates('entry_date')
    def validate_entry_date(self, key, entry_date):
        if entry_date and entry_date > datetime.now():
            raise ValueError("entry_date cannot be in the future")
        return entry_date
    
    @validates('expiry_date')
    def validate_expiry_date(self, key, expiry_date):
        if expiry_date and self.entry_date and expiry_date <= self.entry_date:
            raise ValueError("expiry_date must be after entry_date")
        return expiry_date
    
    @validates('quantity_in_stock', 'reserved_quantity', 'unit_cost')
    def validate_positive_values(self, key, value):
        if value is not None and value < 0:
            raise ValueError(f"{key} must be non-negative")
        return value
    
    @validates('reserved_quantity')
    def validate_reserved_vs_stock(self, key, reserved_quantity):
        if (reserved_quantity is not None and 
            self.quantity_in_stock is not None and 
            reserved_quantity > self.quantity_in_stock):
            raise ValueError("reserved_quantity cannot exceed quantity_in_stock")
        return reserved_quantity
    
    @validates('quality_status')
    def validate_quality_status(self, key, quality_status):
        valid_statuses = {'PENDING', 'APPROVED', 'REJECTED', 'QUARANTINE'}
        if quality_status not in valid_statuses:
            raise ValueError(f"quality_status must be one of: {valid_statuses}")
        return quality_status
    
    @hybrid_property
    def is_available(self):
        """Check if inventory item has available quantity"""
        return (self.available_quantity or 0) > 0 and self.quality_status == 'APPROVED'
    
    @hybrid_property
    def is_expired(self):
        """Check if inventory item is expired"""
        return self.expiry_date is not None and self.expiry_date <= datetime.now()
    
    @hybrid_property  
    def days_in_stock(self):
        """Calculate number of days this batch has been in stock"""
        if self.entry_date:
            return (datetime.now() - self.entry_date).days
        return 0
    
    def consume_quantity(self, quantity: Decimal, reason: str = "CONSUMPTION") -> bool:
        """
        Consume quantity from this inventory item.
        
        Args:
            quantity: Quantity to consume
            reason: Reason for consumption (for stock movement tracking)
            
        Returns:
            True if consumption was successful
        """
        if quantity <= 0:
            raise ValueError("Consumption quantity must be positive")
            
        if quantity > self.available_quantity:
            raise ValueError("Cannot consume more than available quantity")
        
        self.quantity_in_stock -= quantity
        return True
    
    def reserve_quantity(self, quantity: Decimal) -> bool:
        """
        Reserve quantity for production or allocation.
        
        Args:
            quantity: Quantity to reserve
            
        Returns:
            True if reservation was successful
        """
        if quantity <= 0:
            raise ValueError("Reservation quantity must be positive")
            
        if (self.reserved_quantity + quantity) > self.quantity_in_stock:
            raise ValueError("Cannot reserve more than available quantity")
        
        self.reserved_quantity += quantity
        return True
    
    def release_reservation(self, quantity: Decimal) -> bool:
        """
        Release reserved quantity.
        
        Args:
            quantity: Quantity to release from reservation
            
        Returns:
            True if release was successful
        """
        if quantity <= 0:
            raise ValueError("Release quantity must be positive")
            
        if quantity > self.reserved_quantity:
            raise ValueError("Cannot release more than reserved quantity")
        
        self.reserved_quantity -= quantity
        return True
    
    def __repr__(self):
        return (f"<InventoryItem(id={self.inventory_item_id}, "
                f"product_id={self.product_id}, batch='{self.batch_number}', "
                f"available={self.available_quantity})>")


class StockMovement(BaseModel):
    """
    Complete audit trail of all stock movements for inventory tracking.
    Records every IN, OUT, TRANSFER, ADJUSTMENT, PRODUCTION, and RETURN operation.
    """
    __tablename__ = 'stock_movements'
    __table_args__ = (
        CheckConstraint(
            "movement_type IN ('IN', 'OUT', 'TRANSFER', 'ADJUSTMENT', 'PRODUCTION', 'RETURN')",
            name='chk_movement_type'
        ),
        CheckConstraint("quantity != 0", name='chk_movement_quantity'),
        CheckConstraint("unit_cost >= 0", name='chk_movement_unit_cost'),
        CheckConstraint(
            "reference_type IS NULL OR reference_type IN "
            "('PURCHASE_ORDER', 'PRODUCTION_ORDER', 'TRANSFER', 'ADJUSTMENT', 'RETURN', 'SALE')",
            name='chk_movement_reference_type'
        ),
        CheckConstraint(
            "movement_date <= CURRENT_TIMESTAMP + INTERVAL '1 hour'",
            name='chk_movement_date'
        ),
        CheckConstraint(
            "(movement_type != 'TRANSFER') OR "
            "(movement_type = 'TRANSFER' AND from_warehouse_id IS NOT NULL AND to_warehouse_id IS NOT NULL)",
            name='chk_transfer_warehouses'
        ),
        # Performance indexes
        Index('idx_stock_movements_item_date', 'inventory_item_id', 'movement_date DESC'),
        Index('idx_stock_movements_type_date', 'movement_type', 'movement_date DESC'),
        Index('idx_stock_movements_reference', 'reference_type', 'reference_id'),
    )
    
    movement_id = Column(Integer, primary_key=True)
    inventory_item_id = Column(Integer, ForeignKey('inventory_items.inventory_item_id', ondelete='CASCADE'), 
                              nullable=False)
    movement_type = Column(String(20), nullable=False,
                          comment="Type of movement: IN, OUT, TRANSFER, ADJUSTMENT, PRODUCTION, RETURN")
    movement_date = Column(DateTime, nullable=False, default=datetime.now,
                          comment="Date and time of the movement")
    
    quantity = QuantityColumn.create('quantity', nullable=False)
    unit_cost = CurrencyColumn.create('unit_cost', nullable=False)
    total_cost = Column(
        DECIMAL(15, 4),
        Computed('ABS(quantity) * unit_cost'),
        comment="Calculated field: ABS(quantity) * unit_cost"
    )
    
    reference_type = Column(String(30), nullable=True,
                           comment="Type of document causing movement: PURCHASE_ORDER, PRODUCTION_ORDER, etc.")
    reference_id = Column(Integer, nullable=True,
                         comment="ID of the reference document")
    
    from_warehouse_id = Column(Integer, ForeignKey('warehouses.warehouse_id', ondelete='SET NULL'),
                              nullable=True)
    to_warehouse_id = Column(Integer, ForeignKey('warehouses.warehouse_id', ondelete='SET NULL'),
                            nullable=True)
    
    notes = Column(Text, comment="Additional notes about the movement")
    created_by = Column(String(100), comment="User who created this movement")
    
    # Relationships
    inventory_item = relationship("InventoryItem", back_populates="stock_movements")
    from_warehouse = relationship("Warehouse", foreign_keys=[from_warehouse_id])
    to_warehouse = relationship("Warehouse", foreign_keys=[to_warehouse_id])
    
    @validates('movement_type')
    def validate_movement_type(self, key, movement_type):
        valid_types = {'IN', 'OUT', 'TRANSFER', 'ADJUSTMENT', 'PRODUCTION', 'RETURN'}
        if movement_type not in valid_types:
            raise ValueError(f"movement_type must be one of: {valid_types}")
        return movement_type
    
    @validates('quantity')
    def validate_quantity(self, key, quantity):
        if quantity is None or quantity == 0:
            raise ValueError("quantity cannot be zero")
        return quantity
    
    @validates('unit_cost')
    def validate_unit_cost(self, key, unit_cost):
        if unit_cost is not None and unit_cost < 0:
            raise ValueError("unit_cost must be non-negative")
        return unit_cost
    
    @validates('movement_date')
    def validate_movement_date(self, key, movement_date):
        if movement_date and movement_date > datetime.now():
            # Allow some tolerance for timestamp differences
            from datetime import timedelta
            if movement_date > (datetime.now() + timedelta(hours=1)):
                raise ValueError("movement_date cannot be too far in the future")
        return movement_date
    
    @hybrid_property
    def is_increase(self):
        """Check if this movement increases inventory"""
        return self.movement_type in ('IN', 'RETURN', 'ADJUSTMENT') and self.quantity > 0
    
    @hybrid_property
    def is_decrease(self):
        """Check if this movement decreases inventory"""
        return self.movement_type in ('OUT', 'PRODUCTION', 'TRANSFER') or self.quantity < 0
    
    @hybrid_property
    def absolute_quantity(self):
        """Get absolute value of quantity"""
        return abs(self.quantity) if self.quantity else Decimal('0')
    
    def __repr__(self):
        return (f"<StockMovement(id={self.movement_id}, "
                f"type='{self.movement_type}', quantity={self.quantity}, "
                f"date='{self.movement_date}')>")


# Event listeners for automatic stock movement tracking
@event.listens_for(InventoryItem, 'after_insert')
def track_inventory_insert(mapper, connection, target):
    """Automatically create stock movement for new inventory"""
    stock_movement = StockMovement(
        inventory_item_id=target.inventory_item_id,
        movement_type='IN',
        quantity=target.quantity_in_stock,
        unit_cost=target.unit_cost,
        reference_type='PURCHASE_ORDER',
        reference_id=target.purchase_order_id,
        notes=f'Initial inventory entry for batch {target.batch_number}'
    )
    
    # This would be handled by the service layer in practice
    # connection.execute(stock_movements.insert().values(**stock_movement.to_dict()))


@event.listens_for(InventoryItem.quantity_in_stock, 'set')
def track_quantity_change(target, value, oldvalue, initiator):
    """Track quantity changes for stock movement audit"""
    if oldvalue is not None and oldvalue != value:
        quantity_change = value - oldvalue
        movement_type = 'IN' if quantity_change > 0 else 'OUT'
        
        # This would create a stock movement record
        # The actual implementation would be in the service layer
        pass


# Additional indexes for performance optimization
Index('idx_inventory_product_warehouse', InventoryItem.product_id, InventoryItem.warehouse_id, 
      InventoryItem.quality_status, postgresql_where="quantity_in_stock > 0")

Index('idx_stock_movements_audit_trail', StockMovement.movement_date.desc(), 
      StockMovement.movement_type, StockMovement.inventory_item_id)