"""Enhanced MRP features: stock reservations, production dependencies, component status tracking

Revision ID: 0002_enhanced_mrp_features  
Revises: 0001_initial_schema
Create Date: 2025-08-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '0002_enhanced_mrp_features'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    """Add enhanced MRP features to the database."""
    
    # Create stock_reservations table
    op.create_table(
        'stock_reservations',
        sa.Column('reservation_id', sa.Integer, primary_key=True),
        sa.Column('product_id', sa.Integer, sa.ForeignKey('products.product_id', ondelete='CASCADE'), nullable=False),
        sa.Column('warehouse_id', sa.Integer, sa.ForeignKey('warehouses.warehouse_id', ondelete='CASCADE'), nullable=False),
        sa.Column('reserved_quantity', sa.DECIMAL(15, 4), nullable=False),
        sa.Column('reserved_for_type', sa.String(30), nullable=False),
        sa.Column('reserved_for_id', sa.Integer, nullable=False),
        sa.Column('reservation_date', sa.DateTime, nullable=False),
        sa.Column('expiry_date', sa.DateTime, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='ACTIVE'),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('reserved_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime, default=sa.func.current_timestamp()),
    )
    
    # Add constraints to stock_reservations
    op.create_check_constraint(
        'chk_stock_reservation_quantity',
        'stock_reservations',
        'reserved_quantity > 0'
    )
    op.create_check_constraint(
        'chk_stock_reservation_type',
        'stock_reservations',
        "reserved_for_type IN ('PRODUCTION_ORDER', 'PLANNING', 'FORECAST')"
    )
    op.create_check_constraint(
        'chk_stock_reservation_status',
        'stock_reservations',
        "status IN ('ACTIVE', 'CONSUMED', 'RELEASED', 'EXPIRED')"
    )
    op.create_check_constraint(
        'chk_stock_reservation_dates',
        'stock_reservations',
        'expiry_date IS NULL OR expiry_date > reservation_date'
    )
    
    # Create indexes for stock_reservations
    op.create_index(
        'idx_stock_reservations_product',
        'stock_reservations',
        ['product_id', 'warehouse_id', 'status']
    )
    op.create_index(
        'idx_stock_reservations_reference',
        'stock_reservations',
        ['reserved_for_type', 'reserved_for_id']
    )
    op.create_index(
        'idx_stock_reservations_expiry',
        'stock_reservations',
        ['expiry_date', 'status']
    )
    
    # Create production_dependencies table
    op.create_table(
        'production_dependencies',
        sa.Column('dependency_id', sa.Integer, primary_key=True),
        sa.Column('parent_production_order_id', sa.Integer, 
                 sa.ForeignKey('production_orders.production_order_id', ondelete='CASCADE'), nullable=False),
        sa.Column('dependent_production_order_id', sa.Integer, 
                 sa.ForeignKey('production_orders.production_order_id', ondelete='CASCADE'), nullable=False),
        sa.Column('dependency_type', sa.String(20), nullable=False, default='COMPONENT'),
        sa.Column('dependency_quantity', sa.DECIMAL(15, 4), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='PENDING'),
        sa.Column('required_by_date', sa.DateTime, nullable=True),
        sa.Column('satisfied_at', sa.DateTime, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime, default=sa.func.current_timestamp()),
    )
    
    # Add constraints to production_dependencies
    op.create_check_constraint(
        'chk_production_dependency_quantity',
        'production_dependencies',
        'dependency_quantity > 0'
    )
    op.create_check_constraint(
        'chk_production_dependency_type',
        'production_dependencies',
        "dependency_type IN ('COMPONENT', 'SEQUENCE', 'RESOURCE', 'SETUP')"
    )
    op.create_check_constraint(
        'chk_production_dependency_status',
        'production_dependencies',
        "status IN ('PENDING', 'SATISFIED', 'BLOCKED', 'CANCELLED')"
    )
    op.create_check_constraint(
        'chk_production_dependency_different_orders',
        'production_dependencies',
        'parent_production_order_id != dependent_production_order_id'
    )
    
    # Create indexes for production_dependencies
    op.create_index(
        'idx_production_dependencies_parent',
        'production_dependencies',
        ['parent_production_order_id']
    )
    op.create_index(
        'idx_production_dependencies_dependent',
        'production_dependencies',
        ['dependent_production_order_id']
    )
    op.create_index(
        'idx_production_dependencies_status',
        'production_dependencies',
        ['status', 'dependency_type']
    )
    
    # Add component-level status tracking fields to production_order_components
    op.add_column(
        'production_order_components',
        sa.Column('component_status', sa.String(20), nullable=False, default='NOT_STARTED')
    )
    op.add_column(
        'production_order_components',
        sa.Column('started_at', sa.DateTime, nullable=True)
    )
    op.add_column(
        'production_order_components',
        sa.Column('completed_at', sa.DateTime, nullable=True)
    )
    
    # Add constraint for component status
    op.create_check_constraint(
        'chk_po_component_status',
        'production_order_components',
        "component_status IN ('NOT_STARTED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')"
    )


def downgrade():
    """Remove enhanced MRP features from the database."""
    
    # Remove component status fields from production_order_components
    op.drop_constraint('chk_po_component_status', 'production_order_components')
    op.drop_column('production_order_components', 'completed_at')
    op.drop_column('production_order_components', 'started_at')
    op.drop_column('production_order_components', 'component_status')
    
    # Drop production_dependencies table
    op.drop_index('idx_production_dependencies_status', 'production_dependencies')
    op.drop_index('idx_production_dependencies_dependent', 'production_dependencies')
    op.drop_index('idx_production_dependencies_parent', 'production_dependencies')
    op.drop_constraint('chk_production_dependency_different_orders', 'production_dependencies')
    op.drop_constraint('chk_production_dependency_status', 'production_dependencies')
    op.drop_constraint('chk_production_dependency_type', 'production_dependencies')
    op.drop_constraint('chk_production_dependency_quantity', 'production_dependencies')
    op.drop_table('production_dependencies')
    
    # Drop stock_reservations table
    op.drop_index('idx_stock_reservations_expiry', 'stock_reservations')
    op.drop_index('idx_stock_reservations_reference', 'stock_reservations')
    op.drop_index('idx_stock_reservations_product', 'stock_reservations')
    op.drop_constraint('chk_stock_reservation_dates', 'stock_reservations')
    op.drop_constraint('chk_stock_reservation_status', 'stock_reservations')
    op.drop_constraint('chk_stock_reservation_type', 'stock_reservations')
    op.drop_constraint('chk_stock_reservation_quantity', 'stock_reservations')
    op.drop_table('stock_reservations')