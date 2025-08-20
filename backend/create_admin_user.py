#!/usr/bin/env python3
"""
Script to create an admin user for the Horoz Demir MRP System.
This script creates an admin user with full permissions and proper password hashing.
"""

import sys
import os
from datetime import datetime

# Add the current directory to the Python path to import local modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, engine
from models.auth import User
from app.dependencies import get_password_hash
from sqlalchemy import select


def create_admin_user(username="admin", password="admin123", email="admin@horozdemir.com"):
    """
    Create an admin user with the specified credentials.
    
    Args:
        username (str): Username for the admin user
        password (str): Plain text password (will be hashed)
        email (str): Email address for the admin user
    
    Returns:
        bool: True if user was created successfully, False otherwise
    """
    session = SessionLocal()
    
    try:
        # Check if admin user already exists
        existing_user_query = select(User).where(User.username == username.lower())
        existing_user = session.execute(existing_user_query).scalar_one_or_none()
        
        if existing_user:
            print(f"User '{username}' already exists!")
            print(f"User ID: {existing_user.user_id}")
            print(f"Full Name: {existing_user.full_name}")
            print(f"Email: {existing_user.email}")
            print(f"Role: {existing_user.role}")
            print(f"Active: {existing_user.is_active}")
            print(f"Created: {existing_user.created_at}")
            return False
        
        # Hash the password
        hashed_password = get_password_hash(password)
        
        # Create the admin user
        admin_user = User(
            username=username.lower(),
            email=email.lower() if email else None,
            hashed_password=hashed_password,
            full_name="System Administrator",
            role="admin",  # This gives all permissions
            is_active=True,
            is_verified=True,  # Pre-verified admin account
            failed_login_attempts=0,
            permissions=[],  # Empty because admin role gets all permissions automatically
            settings={
                "theme": "light",
                "language": "en",
                "notifications_enabled": True
            },
            notes="Default admin user created by setup script",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Add to session and commit
        session.add(admin_user)
        session.commit()
        session.refresh(admin_user)
        
        print("✅ Admin user created successfully!")
        print(f"Username: {admin_user.username}")
        print(f"Password: {password}")  # Show the plain password for reference
        print(f"Email: {admin_user.email}")
        print(f"Full Name: {admin_user.full_name}")
        print(f"Role: {admin_user.role}")
        print(f"User ID: {admin_user.user_id}")
        print(f"Created: {admin_user.created_at}")
        
        # Show the permissions this user will have
        permissions = admin_user.get_role_permissions()
        print(f"\nAdmin permissions ({len(permissions)} total):")
        for perm in permissions:
            print(f"  - {perm}")
        
        return True
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error creating admin user: {e}")
        return False
    finally:
        session.close()


def verify_admin_user(username="admin", password="admin123"):
    """
    Verify that the admin user can be authenticated.
    
    Args:
        username (str): Username to verify
        password (str): Password to verify
    
    Returns:
        bool: True if verification successful, False otherwise
    """
    from app.dependencies import verify_password
    
    session = SessionLocal()
    
    try:
        # Find user by username
        query = select(User).where(User.username == username.lower())
        user = session.execute(query).scalar_one_or_none()
        
        if not user:
            print(f"❌ User '{username}' not found!")
            return False
        
        # Verify password
        if not verify_password(password, user.hashed_password):
            print("❌ Password verification failed!")
            return False
        
        # Check if user is active and has admin role
        if not user.is_active:
            print("❌ User account is not active!")
            return False
        
        if user.role != "admin":
            print(f"❌ User role is '{user.role}', not 'admin'!")
            return False
        
        print("✅ Admin user verification successful!")
        print(f"Username: {user.username}")
        print(f"Role: {user.role}")
        print(f"Active: {user.is_active}")
        print(f"Permissions: {len(user.get_role_permissions())} total")
        
        return True
        
    except Exception as e:
        print(f"❌ Error verifying admin user: {e}")
        return False
    finally:
        session.close()


def main():
    """Main function to create and verify admin user."""
    print("Creating admin user for Horoz Demir MRP System...")
    print("=" * 50)
    
    # Create admin user
    success = create_admin_user(
        username="admin",
        password="admin123", 
        email="admin@horozdemir.com"
    )
    
    if success:
        print("\n" + "=" * 50)
        print("Verifying admin user...")
        verify_admin_user("admin", "admin123")
        
        print("\n" + "=" * 50)
        print("🎉 Setup completed successfully!")
        print("\nYou can now log in with:")
        print("  Username: admin")
        print("  Password: admin123")
        print("\nAPI Login endpoint: POST http://localhost:8000/api/v1/auth/login")
    else:
        print("\n❌ Admin user creation failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()