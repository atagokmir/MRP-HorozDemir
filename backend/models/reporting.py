"""
Reporting and Analytics Models for Horoz Demir MRP System.
This module contains SQLAlchemy models for critical stock alerts and cost calculation history.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Date, DateTime, DECIMAL, Text, Boolean,
    ForeignKey, CheckConstraint, Index
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from .base import BaseModel, CurrencyColumn, QuantityColumn


class CriticalStockAlert(BaseModel):
    """
    Monitors products that fall below minimum or critical stock levels.
    Generates alerts for procurement and inventory management.
    """
    __tablename__ = 'critical_stock_alerts'
    __table_args__ = (
        CheckConstraint(
            "alert_type IN ('MINIMUM', 'CRITICAL', 'OUT_OF_STOCK')",
            name='chk_critical_stock_alert_type'
        ),
        CheckConstraint(
            "current_stock >= 0 AND minimum_level >= 0 AND critical_level >= 0 AND "
            "critical_level <= minimum_level",
            name='chk_critical_stock_levels'
        ),
        CheckConstraint(
            "(is_resolved = FALSE AND resolved_date IS NULL AND resolved_by IS NULL) OR "
            "(is_resolved = TRUE AND resolved_date IS NOT NULL)",
            name='chk_critical_stock_resolution'
        ),
        CheckConstraint(
            "resolved_date IS NULL OR resolved_date >= alert_date",
            name='chk_critical_stock_alert_dates'
        ),
        # Performance indexes
        Index('idx_critical_stock_alerts_product_warehouse', 'product_id', 'warehouse_id'),
        Index('idx_critical_stock_alerts_unresolved', 'alert_type', 'is_resolved', 'alert_date',
              postgresql_where='is_resolved = FALSE'),
        Index('idx_critical_stock_alerts_date', 'alert_date'),
        Index('idx_critical_stock_alerts_resolution', 'resolved_date',
              postgresql_where='is_resolved = TRUE'),
    )
    
    alert_id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.product_id', ondelete='CASCADE'), 
                       nullable=False)
    warehouse_id = Column(Integer, ForeignKey('warehouses.warehouse_id', ondelete='CASCADE'), 
                         nullable=False)
    
    current_stock = QuantityColumn.create('current_stock', nullable=False)
    minimum_level = QuantityColumn.create('minimum_level', nullable=False)
    critical_level = QuantityColumn.create('critical_level', nullable=False)
    
    alert_type = Column(String(20), nullable=False,
                       comment="Alert severity: MINIMUM (below min level), CRITICAL (below critical level), OUT_OF_STOCK (zero stock)")
    alert_date = Column(DateTime, nullable=False, default=datetime.now,
                       comment="Date and time when alert was generated")
    
    is_resolved = Column(Boolean, default=False, 
                        comment="Whether the alert has been resolved")
    resolved_date = Column(DateTime, nullable=True,
                          comment="Date and time when alert was resolved")
    resolved_by = Column(String(100), nullable=True,
                        comment="User who resolved the alert")
    resolution_notes = Column(Text, comment="Notes about how the alert was resolved")
    
    # Relationships
    product = relationship("Product", back_populates="critical_stock_alerts")
    warehouse = relationship("Warehouse", back_populates="critical_stock_alerts")
    
    @validates('alert_type')
    def validate_alert_type(self, key, alert_type):
        valid_types = {'MINIMUM', 'CRITICAL', 'OUT_OF_STOCK'}
        if alert_type not in valid_types:
            raise ValueError(f"alert_type must be one of: {valid_types}")
        return alert_type
    
    @validates('current_stock', 'minimum_level')
    def validate_stock_levels(self, key, value):
        if value is not None and value < 0:
            raise ValueError(f"{key} must be non-negative")
        return value
    
    @validates('critical_level')
    def validate_critical_level(self, key, critical_level):
        # Check for non-negative value
        if critical_level is not None and critical_level < 0:
            raise ValueError("critical_level must be non-negative")
        
        # Check critical doesn't exceed minimum
        if (critical_level is not None and 
            self.minimum_level is not None and 
            critical_level > self.minimum_level):
            raise ValueError("critical_level cannot exceed minimum_level")
        
        return critical_level
    
    @validates('resolved_date')
    def validate_resolved_date(self, key, resolved_date):
        if resolved_date and self.alert_date and resolved_date < self.alert_date:
            raise ValueError("resolved_date cannot be before alert_date")
        return resolved_date
    
    @hybrid_property
    def severity_order(self):
        """Get numeric severity for ordering (lower number = higher severity)"""
        severity_map = {'OUT_OF_STOCK': 1, 'CRITICAL': 2, 'MINIMUM': 3}
        return severity_map.get(self.alert_type, 4)
    
    @hybrid_property
    def days_outstanding(self):
        """Calculate number of days the alert has been outstanding"""
        end_date = self.resolved_date or datetime.now()
        return (end_date - self.alert_date).days if self.alert_date else 0
    
    @hybrid_property
    def stock_deficit(self):
        """Calculate how much stock is below the minimum level"""
        return max(Decimal('0'), self.minimum_level - self.current_stock)
    
    @hybrid_property
    def stock_deficit_percentage(self):
        """Calculate stock deficit as percentage of minimum level"""
        if not self.minimum_level or self.minimum_level == 0:
            return Decimal('0')
        return (self.stock_deficit / self.minimum_level) * 100
    
    def resolve(self, resolved_by: str, notes: Optional[str] = None):
        """Resolve the alert"""
        self.is_resolved = True
        self.resolved_date = datetime.now()
        self.resolved_by = resolved_by
        if notes:
            self.resolution_notes = notes
    
    def reopen(self, reason: Optional[str] = None):
        """Reopen a resolved alert"""
        self.is_resolved = False
        self.resolved_date = None
        self.resolved_by = None
        if reason:
            self.resolution_notes = f"Reopened: {reason}"
    
    def __repr__(self):
        return (f"<CriticalStockAlert(id={self.alert_id}, "
                f"product_id={self.product_id}, type='{self.alert_type}', "
                f"current={self.current_stock}, resolved={self.is_resolved})>")


class CostCalculationHistory(BaseModel):
    """
    Historical cost calculations for trend analysis and reporting.
    Supports multiple cost calculation methods (FIFO, Standard, Average, Actual).
    """
    __tablename__ = 'cost_calculation_history'
    __table_args__ = (
        CheckConstraint(
            "cost_type IN ('FIFO', 'STANDARD', 'AVERAGE', 'ACTUAL')",
            name='chk_cost_calculation_type'
        ),
        CheckConstraint(
            "material_cost >= 0 AND labor_cost >= 0 AND overhead_cost >= 0 AND quantity_basis > 0",
            name='chk_cost_calculation_values'
        ),
        CheckConstraint(
            "source_type IS NULL OR source_type IN "
            "('BOM_CALCULATION', 'INVENTORY_VALUATION', 'PRODUCTION_ORDER', 'PURCHASE_ORDER', 'MANUAL_ENTRY')",
            name='chk_cost_calculation_source_type'
        ),
        CheckConstraint("calculation_date <= CURRENT_DATE", name='chk_cost_calculation_date'),
        # Unique constraint to prevent duplicate calculations
        CheckConstraint(
            "NOT (product_id, calculation_date, cost_type) IS NULL",
            name='uk_cost_calculation'
        ),
        # Performance indexes
        Index('idx_cost_calculation_history_product_date', 'product_id', 'calculation_date'),
        Index('idx_cost_calculation_history_type_date', 'cost_type', 'calculation_date'),
        Index('idx_cost_calculation_history_source', 'source_type', 'source_id'),
        Index('idx_cost_trend_analysis', 'product_id', 'calculation_date', 'cost_type'),
    )
    
    cost_history_id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.product_id', ondelete='CASCADE'), 
                       nullable=False)
    calculation_date = Column(Date, nullable=False, default=date.today,
                             comment="Date of cost calculation")
    cost_type = Column(String(20), nullable=False,
                      comment="Cost calculation method: FIFO, STANDARD, AVERAGE, ACTUAL")
    
    material_cost = CurrencyColumn.create('material_cost', default=Decimal('0'))
    labor_cost = CurrencyColumn.create('labor_cost', default=Decimal('0'))
    overhead_cost = CurrencyColumn.create('overhead_cost', default=Decimal('0'))
    total_unit_cost = Column(
        DECIMAL(15, 4),
        nullable=False, 
        comment="Total unit cost: material + labor + overhead (computed in database)"
    )
    
    quantity_basis = QuantityColumn.create('quantity_basis', nullable=False, default=Decimal('1'))
    
    source_type = Column(String(30), nullable=True,
                        comment="Source of cost calculation: BOM_CALCULATION, INVENTORY_VALUATION, etc.")
    source_id = Column(Integer, nullable=True,
                      comment="ID of the source record")
    calculation_method = Column(Text, comment="Description of calculation method or formula used")
    
    # Relationships
    product = relationship("Product", back_populates="cost_calculation_history")
    
    @validates('cost_type')
    def validate_cost_type(self, key, cost_type):
        valid_types = {'FIFO', 'STANDARD', 'AVERAGE', 'ACTUAL'}
        if cost_type not in valid_types:
            raise ValueError(f"cost_type must be one of: {valid_types}")
        return cost_type
    
    @validates('material_cost', 'labor_cost', 'overhead_cost')
    def validate_cost_values(self, key, value):
        if value is not None and value < 0:
            raise ValueError(f"{key} must be non-negative")
        return value
    
    @validates('quantity_basis')
    def validate_quantity_basis(self, key, quantity_basis):
        if quantity_basis is None or quantity_basis <= 0:
            raise ValueError("quantity_basis must be greater than zero")
        return quantity_basis
    
    @validates('source_type')
    def validate_source_type(self, key, source_type):
        if source_type is not None:
            valid_types = {'BOM_CALCULATION', 'INVENTORY_VALUATION', 'PRODUCTION_ORDER', 
                          'PURCHASE_ORDER', 'MANUAL_ENTRY'}
            if source_type not in valid_types:
                raise ValueError(f"source_type must be one of: {valid_types}")
        return source_type
    
    @validates('calculation_date')
    def validate_calculation_date(self, key, calculation_date):
        if calculation_date and calculation_date > date.today():
            raise ValueError("calculation_date cannot be in the future")
        return calculation_date
    
    @hybrid_property
    def cost_per_unit(self):
        """Calculate cost per unit based on quantity basis"""
        if not self.quantity_basis or self.quantity_basis == 0:
            return self.total_unit_cost or Decimal('0')
        return (self.total_unit_cost or Decimal('0')) / self.quantity_basis
    
    @hybrid_property
    def material_cost_percentage(self):
        """Calculate material cost as percentage of total"""
        if not self.total_unit_cost or self.total_unit_cost == 0:
            return Decimal('0')
        return ((self.material_cost or Decimal('0')) / self.total_unit_cost) * 100
    
    @hybrid_property
    def labor_cost_percentage(self):
        """Calculate labor cost as percentage of total"""
        if not self.total_unit_cost or self.total_unit_cost == 0:
            return Decimal('0')
        return ((self.labor_cost or Decimal('0')) / self.total_unit_cost) * 100
    
    @hybrid_property
    def overhead_cost_percentage(self):
        """Calculate overhead cost as percentage of total"""
        if not self.total_unit_cost or self.total_unit_cost == 0:
            return Decimal('0')
        return ((self.overhead_cost or Decimal('0')) / self.total_unit_cost) * 100
    
    @property
    def cost_breakdown(self):
        """Get cost breakdown as dictionary"""
        return {
            'material': float(self.material_cost or 0),
            'labor': float(self.labor_cost or 0),
            'overhead': float(self.overhead_cost or 0),
            'total': float(self.total_unit_cost or 0)
        }
    
    @property
    def cost_percentages(self):
        """Get cost percentages as dictionary"""
        return {
            'material': float(self.material_cost_percentage),
            'labor': float(self.labor_cost_percentage),
            'overhead': float(self.overhead_cost_percentage)
        }
    
    def calculate_variance(self, other_calculation):
        """
        Calculate variance between this and another cost calculation.
        
        Args:
            other_calculation: Another CostCalculationHistory instance
            
        Returns:
            Dictionary with variance information
        """
        if not other_calculation or not other_calculation.total_unit_cost:
            return None
        
        base_cost = other_calculation.total_unit_cost
        current_cost = self.total_unit_cost or Decimal('0')
        
        variance_amount = current_cost - base_cost
        variance_percentage = (variance_amount / base_cost) * 100 if base_cost else Decimal('0')
        
        return {
            'variance_amount': float(variance_amount),
            'variance_percentage': float(variance_percentage),
            'base_cost': float(base_cost),
            'current_cost': float(current_cost)
        }
    
    def __repr__(self):
        return (f"<CostCalculationHistory(id={self.cost_history_id}, "
                f"product_id={self.product_id}, type='{self.cost_type}', "
                f"date='{self.calculation_date}', cost={self.total_unit_cost})>")


# Additional indexes for reporting performance
Index('idx_critical_stock_dashboard', 
      CriticalStockAlert.is_resolved, CriticalStockAlert.alert_type, 
      CriticalStockAlert.alert_date.desc())

Index('idx_cost_history_variance_analysis', 
      CostCalculationHistory.calculation_date, CostCalculationHistory.cost_type, 
      CostCalculationHistory.total_unit_cost)