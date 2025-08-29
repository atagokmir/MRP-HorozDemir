#!/usr/bin/env python3
"""
Create database tables and admin user for the MRP system.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.base import Base
from models.auth import User
from models.master_data import Product, Warehouse, Supplier, ProductSupplier
from models.inventory import InventoryItem, StockMovement
from models.bom import BillOfMaterials, BomComponent, BomCostCalculation
from models.production import ProductionOrder, StockReservation, ProductionOrderComponent, StockAllocation, ProductionDependency
from models.procurement import PurchaseOrder, PurchaseOrderItem
from models.reporting import CriticalStockAlert, CostCalculationHistory
from passlib.context import CryptContext

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_database():
    """Create all database tables."""
    engine = create_engine("sqlite:///test_mrp.db", echo=True)
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully!")
    return engine

def create_admin_user(engine):
    """Create admin user."""
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    try:
        # Check if admin user already exists
        existing_user = session.query(User).filter(User.username == "admin").first()
        if existing_user:
            print("ℹ️ Admin user already exists")
            return True
        
        # Hash the password
        hashed_password = pwd_context.hash("admin123")
        
        # Create admin user
        admin_user = User(
            username="admin",
            email="admin@horozdemir.com",
            hashed_password=hashed_password,
            full_name="System Administrator",
            role="admin",
            is_active=True,
            is_verified=True,
            permissions={
                "users": ["create", "read", "update", "delete"],
                "products": ["create", "read", "update", "delete"],
                "warehouses": ["create", "read", "update", "delete"],
                "inventory": ["create", "read", "update", "delete"],
                "production": ["create", "read", "update", "delete"],
                "bom": ["create", "read", "update", "delete"],
                "suppliers": ["create", "read", "update", "delete"],
                "procurement": ["create", "read", "update", "delete"],
                "reports": ["create", "read", "update", "delete"]
            }
        )
        
        session.add(admin_user)
        session.commit()
        
        print("✅ Admin user created successfully!")
        print("   Username: admin")
        print("   Password: admin123")
        return True
        
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        session.rollback()
        return False
        
    finally:
        session.close()

if __name__ == "__main__":
    print("🔧 Creating Database and Admin User")
    print("=" * 40)
    
    try:
        # Create database tables
        engine = create_database()
        
        # Create admin user
        success = create_admin_user(engine)
        
        if success:
            print("\n🎉 Database setup completed successfully!")
            print("You can now log in with:")
            print("   Username: admin")
            print("   Password: admin123")
        else:
            print("\n❌ Database setup failed!")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        sys.exit(1)