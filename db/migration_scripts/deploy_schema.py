#!/usr/bin/env python3
"""
Schema deployment script for Horoz Demir MRP System.
This script handles database schema deployment using either Alembic migrations
or direct SQL script execution.
"""

import os
import sys
import argparse
import logging
import subprocess
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent.parent / 'backend'
sys.path.insert(0, str(backend_dir))

from database import (
    init_database, 
    check_database_connection, 
    get_database_info,
    health_check,
    config as db_config
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_sql_script(script_path: Path, description: str = None):
    """
    Execute a SQL script file.
    
    Args:
        script_path: Path to the SQL script file
        description: Description of what the script does
    """
    if not script_path.exists():
        logger.error(f"SQL script not found: {script_path}")
        return False
    
    logger.info(f"Executing SQL script: {script_path.name}")
    if description:
        logger.info(f"Description: {description}")
    
    try:
        # Use psql command to execute the script
        cmd = [
            'psql',
            db_config.database_url,
            '-f', str(script_path),
            '-v', 'ON_ERROR_STOP=1'
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info(f"Successfully executed {script_path.name}")
        if result.stdout:
            logger.debug(f"Output: {result.stdout}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to execute {script_path.name}: {e}")
        if e.stderr:
            logger.error(f"Error: {e.stderr}")
        return False
    
    except FileNotFoundError:
        logger.error("psql command not found. Please ensure PostgreSQL client is installed.")
        return False


def deploy_via_sql_scripts():
    """Deploy schema using direct SQL scripts."""
    logger.info("Deploying schema using SQL scripts...")
    
    # Get the SQL scripts directory
    sql_scripts_dir = Path(__file__).parent.parent / 'sql_scripts'
    
    # Define the scripts in execution order
    scripts_to_execute = [
        ('01_create_master_data_tables.sql', 'Master data tables (warehouses, products, suppliers)'),
        ('02_create_inventory_tables.sql', 'Inventory management with FIFO support'),
        ('03_create_bom_tables.sql', 'Bill of Materials with nested hierarchies'),
        ('04_create_production_tables.sql', 'Production management tables'),
        ('05_create_procurement_tables.sql', 'Procurement and purchase order tables'),
        ('06_create_reporting_tables.sql', 'Reporting and analytics tables'),
        ('07_create_indexes.sql', 'Performance indexes and additional constraints'),
    ]
    
    success_count = 0
    total_count = len(scripts_to_execute)
    
    for script_name, description in scripts_to_execute:
        script_path = sql_scripts_dir / script_name
        
        if run_sql_script(script_path, description):
            success_count += 1
        else:
            logger.error(f"Failed to execute {script_name}, stopping deployment")
            break
    
    if success_count == total_count:
        logger.info("✅ All SQL scripts executed successfully!")
        return True
    else:
        logger.error(f"❌ Only {success_count}/{total_count} scripts executed successfully")
        return False


def deploy_via_alembic():
    """Deploy schema using Alembic migrations."""
    logger.info("Deploying schema using Alembic migrations...")
    
    alembic_dir = backend_dir / 'alembic'
    if not alembic_dir.exists():
        logger.error("Alembic directory not found")
        return False
    
    try:
        # Change to backend directory for alembic commands
        original_cwd = os.getcwd()
        os.chdir(backend_dir)
        
        # Run alembic upgrade
        cmd = ['alembic', 'upgrade', 'head']
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info("✅ Alembic migration completed successfully!")
        if result.stdout:
            logger.info(f"Output: {result.stdout}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Alembic migration failed: {e}")
        if e.stderr:
            logger.error(f"Error: {e.stderr}")
        return False
    
    except FileNotFoundError:
        logger.error("Alembic command not found. Please install alembic: pip install alembic")
        return False
    
    finally:
        # Restore original working directory
        os.chdir(original_cwd)


def verify_deployment():
    """Verify the deployment was successful."""
    logger.info("Verifying deployment...")
    
    try:
        # Check database connection
        if not check_database_connection():
            logger.error("❌ Database connection failed")
            return False
        
        logger.info("✅ Database connection successful")
        
        # Get database info
        db_info = get_database_info()
        logger.info(f"Database: {db_info['database_name']}")
        logger.info(f"PostgreSQL: {db_info['postgres_version']}")
        logger.info(f"User: {db_info['current_user']}")
        
        # Run health check
        health = health_check()
        
        if health['database_connection']:
            logger.info("✅ Database health check passed")
        else:
            logger.error("❌ Database health check failed")
            return False
        
        if health['essential_data_present']:
            logger.info("✅ Essential data present")
        else:
            logger.warning("⚠️  Essential data not found")
        
        logger.info(f"Query performance: {health['query_performance']}")
        
        # Check table count
        from database import database_session
        with database_session() as session:
            result = session.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            table_count = result.scalar()
            logger.info(f"✅ Created {table_count} tables")
            
            if table_count < 10:
                logger.warning("⚠️  Expected more tables, deployment may be incomplete")
                return False
        
        logger.info("🎉 Deployment verification completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Deployment verification failed: {e}")
        return False


def main():
    """Main deployment function."""
    parser = argparse.ArgumentParser(
        description='Deploy Horoz Demir MRP System database schema'
    )
    parser.add_argument(
        '--method',
        choices=['alembic', 'sql', 'both'],
        default='alembic',
        help='Deployment method (default: alembic)'
    )
    parser.add_argument(
        '--skip-verify',
        action='store_true',
        help='Skip deployment verification'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force deployment even if connection fails initially'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("=" * 60)
    logger.info("Horoz Demir MRP System - Schema Deployment")
    logger.info("=" * 60)
    
    # Initial connection check
    logger.info("Checking database connection...")
    
    if not check_database_connection():
        if args.force:
            logger.warning("Database connection failed, but continuing due to --force flag")
        else:
            logger.error("Database connection failed. Please check your connection settings.")
            logger.info("Use --force to continue anyway")
            return 1
    else:
        logger.info("✅ Database connection successful")
    
    # Execute deployment
    deployment_success = False
    
    if args.method in ['alembic', 'both']:
        deployment_success = deploy_via_alembic()
        
        if not deployment_success and args.method == 'both':
            logger.info("Alembic failed, trying SQL scripts...")
            deployment_success = deploy_via_sql_scripts()
    
    elif args.method == 'sql':
        deployment_success = deploy_via_sql_scripts()
    
    if not deployment_success:
        logger.error("❌ Schema deployment failed")
        return 1
    
    # Verify deployment
    if not args.skip_verify:
        verification_success = verify_deployment()
        if not verification_success:
            logger.error("❌ Deployment verification failed")
            return 1
    
    logger.info("=" * 60)
    logger.info("🎉 Schema deployment completed successfully!")
    logger.info("=" * 60)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())