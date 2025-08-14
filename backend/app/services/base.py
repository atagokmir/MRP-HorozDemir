"""
Base service class for common business logic operations.
Provides shared functionality for all service classes.
"""

from typing import Any, Dict, List, Optional, Type, TypeVar, Generic
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from app.exceptions import NotFoundError, ValidationError
from app.schemas.base import PaginationParams, FilterParams


T = TypeVar('T')  # Generic type for models


class BaseService(Generic[T]):
    """Base service class with common CRUD operations."""
    
    def __init__(self, model: Type[T]):
        self.model = model
    
    async def get_by_id(
        self,
        session: AsyncSession,
        id_value: int,
        load_relationships: Optional[List[str]] = None
    ) -> T:
        """
        Get entity by ID with optional relationship loading.
        
        Args:
            session: Database session
            id_value: Entity ID
            load_relationships: List of relationship names to eager load
            
        Returns:
            Entity instance
            
        Raises:
            NotFoundError: If entity not found
        """
        query = select(self.model)
        
        # Add relationship loading
        if load_relationships:
            for rel in load_relationships:
                query = query.options(selectinload(getattr(self.model, rel)))
        
        # Assume primary key is the first column ending with '_id'
        pk_column = None
        for column in self.model.__table__.columns:
            if column.name.endswith('_id'):
                pk_column = column
                break
        
        if pk_column is None:
            raise ValueError(f"No primary key found for {self.model.__name__}")
        
        query = query.where(pk_column == id_value)
        result = await session.execute(query)
        entity = result.scalar_one_or_none()
        
        if entity is None:
            raise NotFoundError(self.model.__name__, id_value)
        
        return entity
    
    async def list_with_filters(
        self,
        session: AsyncSession,
        pagination: PaginationParams,
        filters: Optional[FilterParams] = None,
        additional_filters: Optional[List[Any]] = None,
        load_relationships: Optional[List[str]] = None
    ) -> tuple[List[T], int]:
        """
        List entities with filtering, pagination and optional relationship loading.
        
        Args:
            session: Database session
            pagination: Pagination parameters
            filters: Common filter parameters
            additional_filters: Additional SQLAlchemy filter conditions
            load_relationships: List of relationship names to eager load
            
        Returns:
            Tuple of (entities list, total count)
        """
        # Build base query
        query = select(self.model)
        count_query = select(func.count()).select_from(self.model)
        
        # Apply filters
        conditions = []
        
        # Active only filter (if model has is_active column)
        if filters and filters.active_only and hasattr(self.model, 'is_active'):
            conditions.append(self.model.is_active == True)
        
        # Search filter (basic text search on name columns)
        if filters and filters.search:
            search_conditions = []
            for column in self.model.__table__.columns:
                if 'name' in column.name.lower() or 'code' in column.name.lower():
                    search_conditions.append(
                        column.ilike(f"%{filters.search}%")
                    )
            if search_conditions:
                conditions.append(or_(*search_conditions))
        
        # Additional custom filters
        if additional_filters:
            conditions.extend(additional_filters)
        
        # Apply all conditions
        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))
        
        # Apply sorting
        if filters and filters.sort_by and hasattr(self.model, filters.sort_by):
            sort_column = getattr(self.model, filters.sort_by)
            if filters.sort_order == "desc":
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())
        
        # Add relationship loading
        if load_relationships:
            for rel in load_relationships:
                query = query.options(selectinload(getattr(self.model, rel)))
        
        # Apply pagination
        query = query.offset(pagination.offset).limit(pagination.page_size)
        
        # Execute queries
        result = await session.execute(query)
        entities = result.scalars().all()
        
        count_result = await session.execute(count_query)
        total_count = count_result.scalar()
        
        return list(entities), total_count
    
    async def create(
        self,
        session: AsyncSession,
        entity_data: Dict[str, Any],
        user_id: Optional[int] = None
    ) -> T:
        """
        Create new entity.
        
        Args:
            session: Database session
            entity_data: Entity data dictionary
            user_id: User ID for audit trail
            
        Returns:
            Created entity
        """
        # Add audit fields if model supports them
        if hasattr(self.model, 'created_by') and user_id:
            entity_data['created_by'] = user_id
        if hasattr(self.model, 'updated_by') and user_id:
            entity_data['updated_by'] = user_id
        
        entity = self.model(**entity_data)
        session.add(entity)
        await session.flush()  # Get ID without committing
        await session.refresh(entity)
        return entity
    
    async def update(
        self,
        session: AsyncSession,
        id_value: int,
        update_data: Dict[str, Any],
        user_id: Optional[int] = None
    ) -> T:
        """
        Update existing entity.
        
        Args:
            session: Database session
            id_value: Entity ID
            update_data: Update data dictionary
            user_id: User ID for audit trail
            
        Returns:
            Updated entity
        """
        entity = await self.get_by_id(session, id_value)
        
        # Update fields
        for key, value in update_data.items():
            if value is not None and hasattr(entity, key):
                setattr(entity, key, value)
        
        # Add audit fields if model supports them
        if hasattr(entity, 'updated_by') and user_id:
            entity.updated_by = user_id
        
        await session.flush()
        await session.refresh(entity)
        return entity
    
    async def delete(
        self,
        session: AsyncSession,
        id_value: int,
        soft_delete: bool = True,
        user_id: Optional[int] = None
    ) -> bool:
        """
        Delete entity (soft delete by default).
        
        Args:
            session: Database session
            id_value: Entity ID
            soft_delete: Use soft delete if model supports it
            user_id: User ID for audit trail
            
        Returns:
            True if deleted successfully
        """
        entity = await self.get_by_id(session, id_value)
        
        if soft_delete and hasattr(entity, 'is_active'):
            # Soft delete
            entity.is_active = False
            if hasattr(entity, 'updated_by') and user_id:
                entity.updated_by = user_id
            await session.flush()
        else:
            # Hard delete
            await session.delete(entity)
        
        return True
    
    def validate_decimal_field(
        self,
        value: Optional[Decimal],
        field_name: str,
        min_value: Optional[Decimal] = None,
        max_value: Optional[Decimal] = None,
        required: bool = False
    ) -> None:
        """
        Validate decimal field value.
        
        Args:
            value: Value to validate
            field_name: Field name for error messages
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            required: Whether field is required
            
        Raises:
            ValidationError: If validation fails
        """
        if required and value is None:
            raise ValidationError(f"{field_name} is required", field_name.lower())
        
        if value is not None:
            if min_value is not None and value < min_value:
                raise ValidationError(
                    f"{field_name} must be at least {min_value}",
                    field_name.lower()
                )
            
            if max_value is not None and value > max_value:
                raise ValidationError(
                    f"{field_name} must not exceed {max_value}",
                    field_name.lower()
                )
    
    def validate_string_field(
        self,
        value: Optional[str],
        field_name: str,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        required: bool = False,
        pattern: Optional[str] = None
    ) -> None:
        """
        Validate string field value.
        
        Args:
            value: Value to validate
            field_name: Field name for error messages
            min_length: Minimum string length
            max_length: Maximum string length
            required: Whether field is required
            pattern: Regex pattern to match
            
        Raises:
            ValidationError: If validation fails
        """
        if required and not value:
            raise ValidationError(f"{field_name} is required", field_name.lower())
        
        if value:
            if min_length and len(value) < min_length:
                raise ValidationError(
                    f"{field_name} must be at least {min_length} characters",
                    field_name.lower()
                )
            
            if max_length and len(value) > max_length:
                raise ValidationError(
                    f"{field_name} must not exceed {max_length} characters",
                    field_name.lower()
                )
            
            if pattern:
                import re
                if not re.match(pattern, value):
                    raise ValidationError(
                        f"{field_name} format is invalid",
                        field_name.lower()
                    )


class AuditableService(BaseService[T]):
    """Service for auditable entities with created_by/updated_by fields."""
    
    async def create_with_audit(
        self,
        session: AsyncSession,
        entity_data: Dict[str, Any],
        user_id: int
    ) -> T:
        """Create entity with automatic audit trail."""
        return await self.create(session, entity_data, user_id)
    
    async def update_with_audit(
        self,
        session: AsyncSession,
        id_value: int,
        update_data: Dict[str, Any],
        user_id: int
    ) -> T:
        """Update entity with automatic audit trail."""
        return await self.update(session, id_value, update_data, user_id)