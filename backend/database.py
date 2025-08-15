"""
Database configuration and session management for Horoz Demir MRP System.
This module provides SQLAlchemy database connectivity, session management,
and database initialization functions.
"""

import os
import logging
from typing import Generator, Optional
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.pool import QueuePool
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

# Import all models to ensure they are registered with the Base metadata
from models import Base, set_session_user

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Database configuration settings"""
    
    def __init__(self):
        # Database configuration from app settings
        from app.config import settings
        self.database_url = settings.DATABASE_URL
        
        # Connection pool settings
        self.pool_size = int(os.getenv('DB_POOL_SIZE', '10'))
        self.max_overflow = int(os.getenv('DB_MAX_OVERFLOW', '20'))
        self.pool_pre_ping = os.getenv('DB_POOL_PRE_PING', 'true').lower() == 'true'
        self.pool_recycle = int(os.getenv('DB_POOL_RECYCLE', '3600'))  # 1 hour
        
        # Query settings
        self.echo_sql = os.getenv('DB_ECHO', 'false').lower() == 'true'
        self.query_timeout = int(os.getenv('DB_QUERY_TIMEOUT', '30'))
        
        # Environment settings
        self.environment = os.getenv('ENVIRONMENT', 'development')
        self.is_production = self.environment.lower() == 'production'


# Global configuration instance
config = DatabaseConfig()


def create_database_engine(database_url: Optional[str] = None) -> Engine:
    """
    Create and configure the SQLAlchemy database engine.
    
    Args:
        database_url: Optional database URL override
        
    Returns:
        Configured SQLAlchemy engine
    """
    url = database_url or config.database_url
    
    # Engine configuration
    engine_kwargs = {
        'poolclass': QueuePool,
        'pool_size': config.pool_size,
        'max_overflow': config.max_overflow,
        'pool_pre_ping': config.pool_pre_ping,
        'pool_recycle': config.pool_recycle,
        'echo': config.echo_sql,
        'echo_pool': config.echo_sql and not config.is_production,
        'future': True,  # Use SQLAlchemy 2.0 style
    }
    
    # Add database-specific connection args
    if url.startswith('postgresql'):
        # PostgreSQL-specific settings
        if config.is_production:
            engine_kwargs.update({
                'connect_args': {
                    'connect_timeout': config.query_timeout,
                    'application_name': 'horoz_demir_mrp',
                    'options': '-c statement_timeout=30000'  # 30 second statement timeout
                }
            })
        else:
            engine_kwargs.update({
                'connect_args': {
                    'connect_timeout': config.query_timeout,
                    'application_name': 'horoz_demir_mrp_dev'
                }
            })
    elif url.startswith('sqlite'):
        # SQLite-specific settings
        engine_kwargs.update({
            'connect_args': {
                'check_same_thread': False,  # Allow SQLite to be used across threads
                'timeout': config.query_timeout
            }
        })
    
    engine = create_engine(url, **engine_kwargs)
    
    # Configure event listeners
    configure_engine_events(engine)
    
    logger.info(f"Created database engine for {config.environment} environment")
    return engine


def configure_engine_events(engine: Engine):
    """Configure database engine event listeners for optimization and monitoring."""
    
    @event.listens_for(engine, "connect")
    def set_database_session_config(dbapi_connection, connection_record):
        """Set database-specific session configuration"""
        if engine.url.drivername.startswith('postgresql'):
            # PostgreSQL-specific configuration
            with dbapi_connection.cursor() as cursor:
                # Set search path
                cursor.execute("SET search_path TO public")
                
                # Set timezone
                cursor.execute("SET timezone TO 'UTC'")
                
                # Set statement timeout for safety
                if config.is_production:
                    cursor.execute("SET statement_timeout = '30s'")
                
                # Enable parallel queries for better performance
                cursor.execute("SET max_parallel_workers_per_gather = 2")
                
                logger.debug("Configured PostgreSQL session settings")
        elif engine.url.drivername.startswith('sqlite'):
            # SQLite-specific configuration
            with dbapi_connection:
                # Enable foreign key constraints
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.close()
                
                logger.debug("Configured SQLite session settings")
    
    @event.listens_for(engine, "before_cursor_execute")
    def log_slow_queries(conn, cursor, statement, parameters, context, executemany):
        """Log execution start time for slow query monitoring"""
        context._query_start_time = time.time()
    
    @event.listens_for(engine, "after_cursor_execute")
    def log_slow_queries_end(conn, cursor, statement, parameters, context, executemany):
        """Log slow queries for performance monitoring"""
        if hasattr(context, '_query_start_time'):
            execution_time = time.time() - context._query_start_time
            
            # Log queries taking more than 1 second
            if execution_time > 1.0:
                logger.warning(
                    f"Slow query detected: {execution_time:.2f}s - "
                    f"{statement[:200]}{'...' if len(statement) > 200 else ''}"
                )


# Create the global engine instance
engine = create_database_engine()

# Create session factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    future=True
)

# Create scoped session for thread-local sessions
ScopedSession = scoped_session(SessionLocal)


def get_database_session() -> Generator[Session, None, None]:
    """
    Get a database session using dependency injection pattern.
    
    Yields:
        SQLAlchemy database session
        
    Usage:
        with get_database_session() as session:
            # Use session here
            pass
    """
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def database_session(user_id: Optional[str] = None) -> Generator[Session, None, None]:
    """
    Context manager for database sessions with automatic user tracking.
    
    Args:
        user_id: Optional user ID for audit trail
        
    Yields:
        SQLAlchemy database session
        
    Usage:
        with database_session('user123') as session:
            # Session has user_id set for audit trail
            session.add(some_model)
            session.commit()
    """
    session = SessionLocal()
    
    # Set user ID for audit trail
    if user_id:
        set_session_user(session, user_id)
    
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_all_tables(engine: Optional[Engine] = None):
    """
    Create all database tables based on SQLAlchemy models.
    
    Args:
        engine: Optional engine override
    """
    target_engine = engine or globals()['engine']
    
    logger.info("Creating all database tables...")
    Base.metadata.create_all(bind=target_engine)
    logger.info("Successfully created all database tables")


def drop_all_tables(engine: Optional[Engine] = None):
    """
    Drop all database tables. Use with caution!
    
    Args:
        engine: Optional engine override
    """
    target_engine = engine or globals()['engine']
    
    if config.is_production:
        raise ValueError("Cannot drop tables in production environment")
    
    logger.warning("Dropping all database tables...")
    Base.metadata.drop_all(bind=target_engine)
    logger.warning("Successfully dropped all database tables")


def init_database(engine: Optional[Engine] = None, drop_existing: bool = False):
    """
    Initialize the database with tables and essential data.
    
    Args:
        engine: Optional engine override
        drop_existing: Whether to drop existing tables first
    """
    target_engine = engine or globals()['engine']
    
    if drop_existing:
        drop_all_tables(target_engine)
    
    create_all_tables(target_engine)
    
    # Insert essential data
    insert_essential_data(target_engine)


def insert_essential_data(engine: Optional[Engine] = None):
    """
    Insert essential master data required for system operation.
    
    Args:
        engine: Optional engine override
    """
    target_engine = engine or globals()['engine']
    
    logger.info("Inserting essential master data...")
    
    with database_session('SYSTEM') as session:
        # Import models locally to avoid circular imports
        from models import Warehouse
        
        # Check if warehouses already exist
        existing_warehouses = session.query(Warehouse).count()
        
        if existing_warehouses == 0:
            # Insert the 4 required warehouse types
            warehouses = [
                Warehouse(
                    warehouse_code='RM01',
                    warehouse_name='Raw Materials Warehouse',
                    warehouse_type='RAW_MATERIALS',
                    location='Building A - Ground Floor'
                ),
                Warehouse(
                    warehouse_code='SF01',
                    warehouse_name='Semi-Finished Products Warehouse',
                    warehouse_type='SEMI_FINISHED',
                    location='Building A - First Floor'
                ),
                Warehouse(
                    warehouse_code='FP01',
                    warehouse_name='Finished Products Warehouse',
                    warehouse_type='FINISHED_PRODUCTS',
                    location='Building B - Ground Floor'
                ),
                Warehouse(
                    warehouse_code='PK01',
                    warehouse_name='Packaging Materials Warehouse',
                    warehouse_type='PACKAGING',
                    location='Building C - Storage Area'
                )
            ]
            
            session.add_all(warehouses)
            session.commit()
            logger.info("Inserted 4 essential warehouses")
        else:
            logger.info("Essential warehouses already exist, skipping")


def check_database_connection() -> bool:
    """
    Check if database connection is working.
    
    Returns:
        True if connection is successful
    """
    try:
        with database_session() as session:
            result = session.execute(text("SELECT 1"))
            return result.scalar() == 1
    except SQLAlchemyError as e:
        logger.error(f"Database connection failed: {e}")
        return False


def get_database_info() -> dict:
    """
    Get database connection and configuration information.
    
    Returns:
        Dictionary with database information
    """
    with database_session() as session:
        # Get PostgreSQL version
        version_result = session.execute(text("SELECT version()"))
        postgres_version = version_result.scalar()
        
        # Get database name
        db_result = session.execute(text("SELECT current_database()"))
        database_name = db_result.scalar()
        
        # Get current user
        user_result = session.execute(text("SELECT current_user"))
        current_user = user_result.scalar()
        
        return {
            'database_name': database_name,
            'postgres_version': postgres_version,
            'current_user': current_user,
            'environment': config.environment,
            'pool_size': config.pool_size,
            'echo_sql': config.echo_sql
        }


def optimize_database():
    """Run database optimization commands."""
    logger.info("Running database optimization...")
    
    with database_session() as session:
        # Update table statistics
        session.execute(text("ANALYZE;"))
        
        # Reindex if needed (be careful in production)
        if not config.is_production:
            session.execute(text("REINDEX DATABASE current_database();"))
        
        session.commit()
    
    logger.info("Database optimization completed")


# Import time for event listeners
import time

# Health check function
def health_check() -> dict:
    """
    Perform a comprehensive database health check.
    
    Returns:
        Dictionary with health check results
    """
    health_status = {
        'database_connection': False,
        'essential_data_present': False,
        'query_performance': None,
        'connection_pool_status': None,
        'error_details': None
    }
    
    try:
        # Test basic connection
        start_time = time.time()
        connection_ok = check_database_connection()
        query_time = time.time() - start_time
        
        health_status['database_connection'] = connection_ok
        health_status['query_performance'] = f"{query_time:.3f}s"
        
        if connection_ok:
            # Check essential data
            with database_session() as session:
                from models import Warehouse
                warehouse_count = session.query(Warehouse).count()
                health_status['essential_data_present'] = warehouse_count >= 4
        
        # Check connection pool
        pool = engine.pool
        health_status['connection_pool_status'] = {
            'size': pool.size(),
            'checked_in': pool.checkedin(),
            'checked_out': pool.checkedout(),
            'overflow': pool.overflow(),
            'invalid': pool.invalid()
        }
        
    except Exception as e:
        health_status['error_details'] = str(e)
        logger.error(f"Database health check failed: {e}")
    
    return health_status


# Export commonly used components
__all__ = [
    'engine',
    'SessionLocal', 
    'ScopedSession',
    'get_database_session',
    'database_session',
    'create_all_tables',
    'drop_all_tables', 
    'init_database',
    'check_database_connection',
    'get_database_info',
    'optimize_database',
    'health_check',
    'DatabaseConfig',
    'config'
]