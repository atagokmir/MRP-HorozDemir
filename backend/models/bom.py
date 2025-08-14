"""
Bill of Materials (BOM) Models for Horoz Demir MRP System.
This module contains SQLAlchemy models for nested BOM hierarchies and cost calculations.
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional, Dict, Any

from sqlalchemy import (
    Column, Integer, String, Date, DECIMAL, Text, Boolean,
    ForeignKey, CheckConstraint, Index, UniqueConstraint, Computed
)
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from .base import BaseModel, AuditMixin, CurrencyColumn, QuantityColumn, PercentageColumn


class BillOfMaterials(BaseModel, AuditMixin):
    """
    BOM header table defining BOMs for semi-finished and finished products.
    Supports versioning and effective date management.
    """
    __tablename__ = 'bill_of_materials'
    __table_args__ = (
        UniqueConstraint('parent_product_id', 'bom_version', name='uk_bom_product_version'),
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'INACTIVE', 'OBSOLETE')",
            name='chk_bom_status'
        ),
        CheckConstraint("base_quantity > 0", name='chk_bom_base_quantity'),
        CheckConstraint(
            "yield_percentage > 0 AND yield_percentage <= 100",
            name='chk_bom_yield_percentage'
        ),
        CheckConstraint("labor_cost_per_unit >= 0", name='chk_bom_labor_cost'),
        CheckConstraint("overhead_cost_per_unit >= 0", name='chk_bom_overhead_cost'),
        CheckConstraint("bom_version ~ '^\\d+\\.\\d+$'", name='chk_bom_version_format'),
        CheckConstraint(
            "expiry_date IS NULL OR expiry_date > effective_date",
            name='chk_bom_effective_dates'
        ),
        # Performance indexes
        Index('idx_bom_parent_product', 'parent_product_id', 'status',
              postgresql_where="status = 'ACTIVE'"),
        Index('idx_bom_effective_dates', 'effective_date', 'expiry_date', 'status',
              postgresql_where="status = 'ACTIVE'"),
    )
    
    bom_id = Column(Integer, primary_key=True)
    parent_product_id = Column(Integer, ForeignKey('products.product_id', ondelete='CASCADE'), 
                              nullable=False)
    bom_version = Column(String(10), nullable=False, default='1.0',
                        comment="Version number in format X.Y for BOM revisions")
    bom_name = Column(String(200), nullable=False,
                     comment="Descriptive name for this BOM")
    effective_date = Column(Date, nullable=False, default=date.today,
                           comment="Date when this BOM becomes effective")
    expiry_date = Column(Date, nullable=True,
                        comment="Date when this BOM expires (optional)")
    status = Column(String(20), default='ACTIVE',
                   comment="BOM status: DRAFT, ACTIVE, INACTIVE, OBSOLETE")
    
    base_quantity = QuantityColumn.create('base_quantity', nullable=False, default=Decimal('1'))
    yield_percentage = PercentageColumn.create('yield_percentage', default=Decimal('100.00'))
    labor_cost_per_unit = CurrencyColumn.create('labor_cost_per_unit', default=Decimal('0'))
    overhead_cost_per_unit = CurrencyColumn.create('overhead_cost_per_unit', default=Decimal('0'))
    
    notes = Column(Text, comment="Additional notes about this BOM")
    
    # Relationships
    parent_product = relationship("Product", back_populates="boms_as_parent")
    bom_components = relationship("BomComponent", back_populates="bom", 
                                 cascade="all, delete-orphan", order_by="BomComponent.sequence_number")
    cost_calculations = relationship("BomCostCalculation", back_populates="bom",
                                   cascade="all, delete-orphan")
    production_orders = relationship("ProductionOrder", back_populates="bom")
    
    @validates('status')
    def validate_status(self, key, status):
        valid_statuses = {'DRAFT', 'ACTIVE', 'INACTIVE', 'OBSOLETE'}
        if status not in valid_statuses:
            raise ValueError(f"status must be one of: {valid_statuses}")
        return status
    
    @validates('bom_version')
    def validate_bom_version(self, key, bom_version):
        import re
        if not re.match(r'^\d+\.\d+$', bom_version):
            raise ValueError("bom_version must be in format X.Y (e.g., 1.0, 2.1)")
        return bom_version
    
    @validates('base_quantity')
    def validate_base_quantity(self, key, base_quantity):
        if base_quantity is None or base_quantity <= 0:
            raise ValueError("base_quantity must be greater than zero")
        return base_quantity
    
    @validates('yield_percentage')
    def validate_yield_percentage(self, key, yield_percentage):
        if yield_percentage is None or yield_percentage <= 0 or yield_percentage > 100:
            raise ValueError("yield_percentage must be between 0 and 100")
        return yield_percentage
    
    @validates('labor_cost_per_unit', 'overhead_cost_per_unit')
    def validate_cost_fields(self, key, value):
        if value is not None and value < 0:
            raise ValueError(f"{key} must be non-negative")
        return value
    
    @validates('effective_date')
    def validate_effective_date(self, key, effective_date):
        if self.expiry_date and effective_date and effective_date >= self.expiry_date:
            raise ValueError("effective_date must be before expiry_date")
        return effective_date
    
    @validates('expiry_date')
    def validate_expiry_date(self, key, expiry_date):
        if expiry_date and self.effective_date and expiry_date <= self.effective_date:
            raise ValueError("expiry_date must be after effective_date")
        return expiry_date
    
    @hybrid_property
    def is_active(self):
        """Check if BOM is currently active"""
        today = date.today()
        return (self.status == 'ACTIVE' and 
                self.effective_date <= today and
                (self.expiry_date is None or self.expiry_date > today))
    
    @hybrid_property
    def component_count(self):
        """Get number of components in this BOM"""
        return len(self.bom_components) if self.bom_components else 0
    
    def get_current_cost(self) -> Optional[Decimal]:
        """
        Get current total cost for this BOM.
        
        Returns:
            Current total cost or None if no calculation available
        """
        current_calc = next(
            (calc for calc in self.cost_calculations if calc.is_current), 
            None
        )
        return current_calc.total_cost if current_calc else None
    
    def get_scaled_component_quantities(self, production_quantity: Decimal) -> Dict[int, Decimal]:
        """
        Calculate component quantities for a given production quantity.
        
        Args:
            production_quantity: Quantity to produce
            
        Returns:
            Dictionary mapping component_product_id to required quantity
        """
        scale_factor = production_quantity / self.base_quantity
        
        return {
            component.component_product_id: component.effective_quantity * scale_factor
            for component in self.bom_components
        }
    
    def activate(self):
        """Activate this BOM and deactivate other versions"""
        self.status = 'ACTIVE'
        # Note: In practice, this would deactivate other versions of the same product
    
    def __repr__(self):
        return (f"<BillOfMaterials(id={self.bom_id}, "
                f"product_id={self.parent_product_id}, version='{self.bom_version}', "
                f"status='{self.status}')>")


class BomComponent(BaseModel):
    """
    Components within each BOM - supports nested semi-finished products.
    Each component can be raw material, semi-finished, or packaging.
    """
    __tablename__ = 'bom_components'
    __table_args__ = (
        UniqueConstraint('bom_id', 'component_product_id', name='uk_bom_component'),
        CheckConstraint("quantity_required > 0", name='chk_bom_component_quantity'),
        CheckConstraint("sequence_number > 0", name='chk_bom_component_sequence'),
        CheckConstraint(
            "scrap_percentage >= 0 AND scrap_percentage <= 50",
            name='chk_bom_component_scrap'
        ),
        # Performance indexes
        Index('idx_bom_components_bom', 'bom_id', 'sequence_number'),
        Index('idx_bom_components_product', 'component_product_id'),
        Index('idx_bom_explosion', 'component_product_id',
              postgresql_where="component_product_id IN (SELECT product_id FROM products WHERE product_type = 'SEMI_FINISHED')"),
    )
    
    bom_component_id = Column(Integer, primary_key=True)
    bom_id = Column(Integer, ForeignKey('bill_of_materials.bom_id', ondelete='CASCADE'), 
                   nullable=False)
    component_product_id = Column(Integer, ForeignKey('products.product_id', ondelete='CASCADE'), 
                                 nullable=False)
    sequence_number = Column(Integer, nullable=False,
                            comment="Assembly sequence order for production")
    
    quantity_required = QuantityColumn.create('quantity_required', nullable=False)
    unit_of_measure = Column(String(20), nullable=False,
                           comment="Unit of measurement for this component")
    scrap_percentage = PercentageColumn.create('scrap_percentage', default=Decimal('0.00'))
    effective_quantity = Column(
        DECIMAL(15, 4),
        Computed('quantity_required * (1 + scrap_percentage/100)'),
        comment="Calculated quantity including scrap percentage"
    )
    
    is_phantom = Column(Boolean, default=False,
                       comment="True for phantom assemblies that are not physically stocked")
    substitute_group = Column(String(20), nullable=True,
                             comment="Group identifier for alternative/substitute components")
    notes = Column(Text, comment="Component-specific notes")
    
    # Relationships
    bom = relationship("BillOfMaterials", back_populates="bom_components")
    component_product = relationship("Product", back_populates="bom_components")
    
    @validates('quantity_required')
    def validate_quantity_required(self, key, quantity_required):
        if quantity_required is None or quantity_required <= 0:
            raise ValueError("quantity_required must be greater than zero")
        return quantity_required
    
    @validates('sequence_number')
    def validate_sequence_number(self, key, sequence_number):
        if sequence_number is None or sequence_number <= 0:
            raise ValueError("sequence_number must be greater than zero")
        return sequence_number
    
    @validates('scrap_percentage')
    def validate_scrap_percentage(self, key, scrap_percentage):
        if scrap_percentage is not None and (scrap_percentage < 0 or scrap_percentage > 50):
            raise ValueError("scrap_percentage must be between 0 and 50")
        return scrap_percentage
    
    @hybrid_property
    def is_semi_finished_component(self):
        """Check if this component is a semi-finished product (enabling nested BOM)"""
        return (self.component_product and 
                self.component_product.product_type == 'SEMI_FINISHED')
    
    @hybrid_property
    def has_sub_bom(self):
        """Check if this component has its own BOM"""
        return (self.is_semi_finished_component and 
                bool(self.component_product.boms_as_parent))
    
    def get_total_requirement(self, parent_quantity: Decimal) -> Decimal:
        """
        Calculate total requirement for this component given parent quantity.
        
        Args:
            parent_quantity: Quantity of parent product being produced
            
        Returns:
            Total quantity required of this component
        """
        return self.effective_quantity * parent_quantity
    
    def __repr__(self):
        return (f"<BomComponent(id={self.bom_component_id}, "
                f"bom_id={self.bom_id}, product_id={self.component_product_id}, "
                f"seq={self.sequence_number}, qty={self.quantity_required})>")


class BomCostCalculation(BaseModel):
    """
    Stores calculated costs for BOMs with rollup from component costs.
    Supports different costing methods (FIFO, Standard, Average).
    """
    __tablename__ = 'bom_cost_calculations'
    __table_args__ = (
        CheckConstraint(
            "material_cost >= 0 AND labor_cost >= 0 AND overhead_cost >= 0",
            name='chk_bom_cost_values'
        ),
        CheckConstraint(
            "cost_basis IN ('FIFO', 'STANDARD', 'AVERAGE', 'ACTUAL')",
            name='chk_bom_cost_basis'
        ),
        # Performance indexes
        Index('idx_bom_cost_current', 'bom_id', 'is_current',
              postgresql_where="is_current = TRUE"),
        Index('idx_bom_cost_date', 'calculation_date DESC'),
    )
    
    bom_cost_id = Column(Integer, primary_key=True)
    bom_id = Column(Integer, ForeignKey('bill_of_materials.bom_id', ondelete='CASCADE'), 
                   nullable=False)
    calculation_date = Column('calculation_date', 'TIMESTAMP', 
                             nullable=False, default='CURRENT_TIMESTAMP')
    
    material_cost = CurrencyColumn.create('material_cost', default=Decimal('0'))
    labor_cost = CurrencyColumn.create('labor_cost', default=Decimal('0'))
    overhead_cost = CurrencyColumn.create('overhead_cost', default=Decimal('0'))
    total_cost = Column(
        DECIMAL(15, 4),
        Computed('material_cost + labor_cost + overhead_cost'),
        comment="Calculated total: material + labor + overhead"
    )
    
    cost_basis = Column(String(20), default='FIFO',
                       comment="Costing method used: FIFO, STANDARD, AVERAGE, ACTUAL")
    is_current = Column(Boolean, default=True,
                       comment="Indicates the current/active cost calculation")
    
    # Relationships
    bom = relationship("BillOfMaterials", back_populates="cost_calculations")
    
    @validates('cost_basis')
    def validate_cost_basis(self, key, cost_basis):
        valid_bases = {'FIFO', 'STANDARD', 'AVERAGE', 'ACTUAL'}
        if cost_basis not in valid_bases:
            raise ValueError(f"cost_basis must be one of: {valid_bases}")
        return cost_basis
    
    @validates('material_cost', 'labor_cost', 'overhead_cost')
    def validate_cost_values(self, key, value):
        if value is not None and value < 0:
            raise ValueError(f"{key} must be non-negative")
        return value
    
    @hybrid_property
    def unit_material_cost(self):
        """Material cost per unit of the parent product"""
        return self.material_cost or Decimal('0')
    
    @hybrid_property
    def unit_labor_cost(self):
        """Labor cost per unit of the parent product"""
        return self.labor_cost or Decimal('0')
    
    @hybrid_property
    def unit_overhead_cost(self):
        """Overhead cost per unit of the parent product"""
        return self.overhead_cost or Decimal('0')
    
    @hybrid_property
    def cost_breakdown(self):
        """Get cost breakdown as percentages"""
        total = self.total_cost or Decimal('0')
        if total == 0:
            return {'material': 0, 'labor': 0, 'overhead': 0}
        
        return {
            'material': float((self.material_cost / total) * 100) if self.material_cost else 0,
            'labor': float((self.labor_cost / total) * 100) if self.labor_cost else 0,
            'overhead': float((self.overhead_cost / total) * 100) if self.overhead_cost else 0
        }
    
    def make_current(self):
        """Make this calculation the current one for the BOM"""
        # In practice, this would set is_current=False for other calculations
        self.is_current = True
    
    def __repr__(self):
        return (f"<BomCostCalculation(id={self.bom_cost_id}, "
                f"bom_id={self.bom_id}, total_cost={self.total_cost}, "
                f"basis='{self.cost_basis}', current={self.is_current})>")


# Additional indexes for BOM hierarchy queries
Index('idx_bom_semi_finished_lookup', BillOfMaterials.parent_product_id, BillOfMaterials.status,
      postgresql_where="parent_product_id IN (SELECT product_id FROM products WHERE product_type = 'SEMI_FINISHED')")

Index('idx_bom_explosion_optimization', BomComponent.bom_id, BomComponent.component_product_id, 
      BomComponent.sequence_number)