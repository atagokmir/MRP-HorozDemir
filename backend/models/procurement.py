"""
Procurement Models for Horoz Demir MRP System.
This module contains SQLAlchemy models for purchase orders and supplier management.
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Column, Integer, String, Date, DECIMAL, Text, Boolean,
    ForeignKey, CheckConstraint, Index, Computed
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from .base import BaseModel, AuditMixin, CurrencyColumn, QuantityColumn


class PurchaseOrder(BaseModel, AuditMixin):
    """
    Purchase order tracking for material procurement from suppliers.
    Supports multiple currencies and delivery tracking.
    """
    __tablename__ = 'purchase_orders'
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'SENT', 'CONFIRMED', 'PARTIALLY_RECEIVED', 'FULLY_RECEIVED', 'CANCELLED')",
            name='chk_purchase_order_status'
        ),
        CheckConstraint("total_amount >= 0", name='chk_purchase_order_total'),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name='chk_purchase_order_currency'),
        CheckConstraint(
            "(expected_delivery_date IS NULL OR expected_delivery_date >= order_date) AND "
            "(actual_delivery_date IS NULL OR actual_delivery_date >= order_date)",
            name='chk_purchase_order_dates'
        ),
        CheckConstraint("po_number ~ '^PUR[0-9]{6}$'", name='chk_purchase_order_number_format'),
        # Performance indexes
        Index('idx_purchase_orders_supplier', 'supplier_id', 'order_date'),
        Index('idx_purchase_orders_status', 'status', 'order_date'),
        Index('idx_purchase_orders_delivery_date', 'expected_delivery_date',
              postgresql_where="status IN ('SENT', 'CONFIRMED', 'PARTIALLY_RECEIVED')"),
        Index('idx_purchase_orders_warehouse', 'warehouse_id', 'status'),
    )
    
    purchase_order_id = Column(Integer, primary_key=True)
    po_number = Column(String(50), unique=True, nullable=False,
                      comment="Unique purchase order number in format PUR######")
    supplier_id = Column(Integer, ForeignKey('suppliers.supplier_id', ondelete='CASCADE'), 
                        nullable=False)
    warehouse_id = Column(Integer, ForeignKey('warehouses.warehouse_id', ondelete='CASCADE'), 
                         nullable=False)
    
    order_date = Column(Date, nullable=False, default=date.today)
    expected_delivery_date = Column(Date, nullable=True)
    actual_delivery_date = Column(Date, nullable=True)
    
    total_amount = CurrencyColumn.create('total_amount', default=Decimal('0'))
    currency = Column(String(3), default='USD', 
                     comment="3-letter ISO currency code (e.g., USD, EUR, GBP)")
    payment_terms = Column(String(100), comment="Payment terms and conditions")
    
    status = Column(String(20), default='DRAFT',
                   comment="Order status: DRAFT, SENT, CONFIRMED, PARTIALLY_RECEIVED, FULLY_RECEIVED, CANCELLED")
    notes = Column(Text, comment="Additional notes about the purchase order")
    
    # Relationships
    supplier = relationship("Supplier", back_populates="purchase_orders")
    warehouse = relationship("Warehouse", back_populates="purchase_orders")
    purchase_order_items = relationship("PurchaseOrderItem", back_populates="purchase_order",
                                      cascade="all, delete-orphan")
    
    @validates('status')
    def validate_status(self, key, status):
        valid_statuses = {'DRAFT', 'SENT', 'CONFIRMED', 'PARTIALLY_RECEIVED', 'FULLY_RECEIVED', 'CANCELLED'}
        if status not in valid_statuses:
            raise ValueError(f"status must be one of: {valid_statuses}")
        return status
    
    @validates('po_number')
    def validate_po_number(self, key, po_number):
        import re
        if not re.match(r'^PUR\d{6}$', po_number):
            raise ValueError("po_number must be in format PUR######")
        return po_number
    
    @validates('currency')
    def validate_currency(self, key, currency):
        if currency and len(currency) != 3:
            raise ValueError("currency must be a 3-letter ISO code")
        return currency.upper() if currency else currency
    
    @validates('total_amount')
    def validate_total_amount(self, key, total_amount):
        if total_amount is not None and total_amount < 0:
            raise ValueError("total_amount must be non-negative")
        return total_amount
    
    @validates('expected_delivery_date')
    def validate_expected_delivery_date(self, key, expected_delivery_date):
        if expected_delivery_date and self.order_date and expected_delivery_date < self.order_date:
            raise ValueError("expected_delivery_date cannot be before order_date")
        return expected_delivery_date
    
    @validates('actual_delivery_date')
    def validate_actual_delivery_date(self, key, actual_delivery_date):
        if actual_delivery_date and self.order_date and actual_delivery_date < self.order_date:
            raise ValueError("actual_delivery_date cannot be before order_date")
        return actual_delivery_date
    
    @hybrid_property
    def item_count(self):
        """Get number of items in this purchase order"""
        return len(self.purchase_order_items) if self.purchase_order_items else 0
    
    @hybrid_property
    def is_overdue(self):
        """Check if purchase order is overdue"""
        return (self.expected_delivery_date is not None and 
                self.expected_delivery_date < date.today() and
                self.status not in ('FULLY_RECEIVED', 'CANCELLED'))
    
    @hybrid_property
    def delivery_delay_days(self):
        """Calculate delivery delay in days"""
        if not self.expected_delivery_date:
            return None
        
        comparison_date = self.actual_delivery_date or date.today()
        return (comparison_date - self.expected_delivery_date).days if comparison_date > self.expected_delivery_date else 0
    
    @hybrid_property
    def completion_percentage(self):
        """Calculate completion percentage based on received items"""
        if not self.purchase_order_items:
            return Decimal('0')
        
        total_items = len(self.purchase_order_items)
        fully_received_items = sum(1 for item in self.purchase_order_items 
                                 if item.delivery_status == 'FULLY_RECEIVED')
        
        return Decimal(fully_received_items * 100) / Decimal(total_items)
    
    def send_to_supplier(self):
        """Mark purchase order as sent to supplier"""
        if self.status != 'DRAFT':
            raise ValueError("Can only send purchase orders from DRAFT status")
        
        self.status = 'SENT'
    
    def confirm_order(self):
        """Confirm purchase order with supplier"""
        if self.status != 'SENT':
            raise ValueError("Can only confirm purchase orders from SENT status")
        
        self.status = 'CONFIRMED'
    
    def calculate_total(self):
        """Recalculate total amount from line items"""
        if self.purchase_order_items:
            self.total_amount = sum(item.total_price for item in self.purchase_order_items)
        else:
            self.total_amount = Decimal('0')
    
    def __repr__(self):
        return (f"<PurchaseOrder(id={self.purchase_order_id}, "
                f"number='{self.po_number}', status='{self.status}', "
                f"total={self.total_amount})>")


class PurchaseOrderItem(BaseModel):
    """
    Individual line items within purchase orders.
    Tracks ordering, receiving, and delivery status for each item.
    """
    __tablename__ = 'purchase_order_items'
    __table_args__ = (
        CheckConstraint(
            "quantity_ordered > 0 AND quantity_received >= 0 AND quantity_received <= quantity_ordered",
            name='chk_po_item_quantities'
        ),
        CheckConstraint("unit_price > 0", name='chk_po_item_unit_price'),
        CheckConstraint(
            "delivery_status IN ('PENDING', 'PARTIALLY_RECEIVED', 'FULLY_RECEIVED', 'CANCELLED')",
            name='chk_po_item_delivery_status'
        ),
        # Performance indexes
        Index('idx_po_items_purchase_order', 'purchase_order_id'),
        Index('idx_po_items_product', 'product_id'),
        Index('idx_po_items_delivery_status', 'delivery_status',
              postgresql_where="delivery_status IN ('PENDING', 'PARTIALLY_RECEIVED')"),
        Index('idx_po_items_receiving', 'purchase_order_id', 'delivery_status', 'product_id',
              postgresql_where="delivery_status IN ('PENDING', 'PARTIALLY_RECEIVED')"),
    )
    
    po_item_id = Column(Integer, primary_key=True)
    purchase_order_id = Column(Integer, 
                              ForeignKey('purchase_orders.purchase_order_id', ondelete='CASCADE'), 
                              nullable=False)
    product_id = Column(Integer, ForeignKey('products.product_id', ondelete='CASCADE'), 
                       nullable=False)
    
    quantity_ordered = QuantityColumn.create('quantity_ordered', nullable=False)
    quantity_received = QuantityColumn.create('quantity_received', default=Decimal('0'))
    
    unit_price = CurrencyColumn.create('unit_price', nullable=False)
    total_price = Column(
        DECIMAL(15, 4),
        Computed('quantity_ordered * unit_price'),
        comment="Calculated field: quantity_ordered * unit_price"
    )
    
    delivery_status = Column(String(20), default='PENDING',
                            comment="Delivery status: PENDING, PARTIALLY_RECEIVED, FULLY_RECEIVED, CANCELLED")
    
    # Relationships
    purchase_order = relationship("PurchaseOrder", back_populates="purchase_order_items")
    product = relationship("Product", back_populates="purchase_order_items")
    
    @validates('quantity_ordered', 'quantity_received')
    def validate_quantities(self, key, value):
        if value is not None and value < 0:
            raise ValueError(f"{key} must be non-negative")
        if key == 'quantity_ordered' and (value is None or value <= 0):
            raise ValueError("quantity_ordered must be greater than zero")
        return value
    
    @validates('quantity_received')
    def validate_quantity_received(self, key, quantity_received):
        if (quantity_received is not None and 
            self.quantity_ordered is not None and 
            quantity_received > self.quantity_ordered):
            raise ValueError("quantity_received cannot exceed quantity_ordered")
        return quantity_received
    
    @validates('unit_price')
    def validate_unit_price(self, key, unit_price):
        if unit_price is None or unit_price <= 0:
            raise ValueError("unit_price must be greater than zero")
        return unit_price
    
    @validates('delivery_status')
    def validate_delivery_status(self, key, delivery_status):
        valid_statuses = {'PENDING', 'PARTIALLY_RECEIVED', 'FULLY_RECEIVED', 'CANCELLED'}
        if delivery_status not in valid_statuses:
            raise ValueError(f"delivery_status must be one of: {valid_statuses}")
        return delivery_status
    
    @hybrid_property
    def remaining_quantity(self):
        """Calculate remaining quantity to receive"""
        return self.quantity_ordered - self.quantity_received
    
    @hybrid_property
    def receipt_percentage(self):
        """Calculate receipt percentage"""
        if not self.quantity_ordered or self.quantity_ordered == 0:
            return Decimal('0')
        return (self.quantity_received / self.quantity_ordered) * 100
    
    @hybrid_property
    def is_fully_received(self):
        """Check if item is fully received"""
        return self.quantity_received == self.quantity_ordered
    
    @hybrid_property
    def is_partially_received(self):
        """Check if item is partially received"""
        return 0 < self.quantity_received < self.quantity_ordered
    
    def receive_quantity(self, quantity: Decimal):
        """Receive a quantity of this item"""
        if quantity <= 0:
            raise ValueError("Received quantity must be positive")
        
        if (self.quantity_received + quantity) > self.quantity_ordered:
            raise ValueError("Cannot receive more than ordered quantity")
        
        self.quantity_received += quantity
        self._update_delivery_status()
    
    def _update_delivery_status(self):
        """Update delivery status based on received quantity"""
        if self.quantity_received == 0:
            self.delivery_status = 'PENDING'
        elif self.quantity_received < self.quantity_ordered:
            self.delivery_status = 'PARTIALLY_RECEIVED'
        else:
            self.delivery_status = 'FULLY_RECEIVED'
    
    def __repr__(self):
        return (f"<PurchaseOrderItem(id={self.po_item_id}, "
                f"po_id={self.purchase_order_id}, product_id={self.product_id}, "
                f"ordered={self.quantity_ordered}, received={self.quantity_received})>")


# Additional indexes for supplier performance analysis
Index('idx_supplier_performance_analysis', 
      PurchaseOrder.supplier_id, PurchaseOrder.order_date.desc(), 
      PurchaseOrder.status, PurchaseOrder.actual_delivery_date)

Index('idx_procurement_inventory_integration', 
      PurchaseOrderItem.product_id, PurchaseOrderItem.delivery_status, 
      PurchaseOrderItem.updated_at)

Index('idx_purchase_orders_overdue', 
      PurchaseOrder.expected_delivery_date, PurchaseOrder.status,
      postgresql_where="expected_delivery_date < CURRENT_DATE AND status NOT IN ('FULLY_RECEIVED', 'CANCELLED')")