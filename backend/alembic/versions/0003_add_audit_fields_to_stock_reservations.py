"""Add audit fields to stock_reservations table

Revision ID: 0003_add_audit_fields_to_stock_reservations
Revises: 0002_enhanced_mrp_features
Create Date: 2025-08-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0003_add_audit_fields_to_stock_reservations'
down_revision = '0002_enhanced_mrp_features'
branch_labels = None
depends_on = None


def upgrade():
    """Add audit fields (created_by, updated_by) to stock_reservations table."""
    
    # Add audit trail columns to stock_reservations table
    op.add_column(
        'stock_reservations',
        sa.Column('created_by', sa.String(100), nullable=True, comment="User who created the record")
    )
    op.add_column(
        'stock_reservations',
        sa.Column('updated_by', sa.String(100), nullable=True, comment="User who last updated the record")
    )


def downgrade():
    """Remove audit fields from stock_reservations table."""
    
    # Remove audit trail columns from stock_reservations table
    op.drop_column('stock_reservations', 'updated_by')
    op.drop_column('stock_reservations', 'created_by')