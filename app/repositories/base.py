# app/repositories/base.py
"""Base repository class providing common CRUD operations for all entities."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from app.database import Base

# Generic type for model classes
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base repository class providing common database operations.

    Args:
        model: The SQLAlchemy model class
        session: The async database session
    """

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        """Initialize repository with model and session."""
        self.model = model
        self.session = session

    async def create(self, **kwargs) -> ModelType:
        """Create a new record.

        Args:
            **kwargs: Field values for the new record

        Returns:
            The created model instance
        """
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def get_by_id(
        self, id: uuid.UUID, load_relationships: List[str] = None
    ) -> Optional[ModelType]:
        """Get a record by its ID.

        Args:
            id: The record ID
            load_relationships: List of relationship names to eager load

        Returns:
            The model instance or None if not found
        """
        query = select(self.model).where(self.model.id == id)

        if load_relationships:
            for relationship in load_relationships:
                query = query.options(selectinload(getattr(self.model, relationship)))

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_field(
        self, field_name: str, field_value: Any, load_relationships: List[str] = None
    ) -> Optional[ModelType]:
        """Get a record by a specific field value.

        Args:
            field_name: Name of the field to search by
            field_value: Value to search for
            load_relationships: List of relationship names to eager load

        Returns:
            The model instance or None if not found
        """
        query = select(self.model).where(getattr(self.model, field_name) == field_value)

        if load_relationships:
            for relationship in load_relationships:
                query = query.options(selectinload(getattr(self.model, relationship)))

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Dict[str, Any] = None,
        search: str = None,
        search_fields: List[str] = None,
        order_by: str = None,
        order_desc: bool = False,
        load_relationships: List[str] = None,
    ) -> tuple[List[ModelType], int]:
        """Get multiple records with pagination, filtering, and search.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Dictionary of field filters
            search: Search term
            search_fields: List of fields to search in
            order_by: Field name to order by
            order_desc: Whether to order in descending order
            load_relationships: List of relationship names to eager load

        Returns:
            Tuple of (records list, total count)
        """
        query = select(self.model)

        # Apply filters
        if filters:
            conditions = []
            for field, value in filters.items():
                if hasattr(self.model, field) and value is not None:
                    conditions.append(getattr(self.model, field) == value)
            if conditions:
                query = query.where(and_(*conditions))

        # Apply search
        if search and search_fields:
            search_conditions = []
            search_term = f"%{search}%"
            for field in search_fields:
                if hasattr(self.model, field):
                    field_attr = getattr(self.model, field)
                    search_conditions.append(field_attr.ilike(search_term))
            if search_conditions:
                query = query.where(or_(*search_conditions))

        # Get total count before pagination
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar()

        # Apply ordering
        if order_by and hasattr(self.model, order_by):
            order_field = getattr(self.model, order_by)
            if order_desc:
                query = query.order_by(order_field.desc())
            else:
                query = query.order_by(order_field)
        else:
            # Default ordering by created_at if available
            if hasattr(self.model, "created_at"):
                query = query.order_by(self.model.created_at.desc())

        # Apply pagination
        query = query.offset(skip).limit(limit)

        # Apply relationship loading
        if load_relationships:
            for relationship in load_relationships:
                if hasattr(self.model, relationship):
                    query = query.options(
                        selectinload(getattr(self.model, relationship))
                    )

        result = await self.session.execute(query)
        records = result.scalars().all()

        return list(records), total

    async def update(self, id: uuid.UUID, **kwargs) -> Optional[ModelType]:
        """Update a record by ID.

        Args:
            id: The record ID
            **kwargs: Fields to update

        Returns:
            The updated model instance or None if not found
        """
        instance = await self.get_by_id(id)
        if not instance:
            return None

        for field, value in kwargs.items():
            if hasattr(instance, field):
                setattr(instance, field, value)

        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def delete(self, id: uuid.UUID) -> bool:
        """Delete a record by ID.

        Args:
            id: The record ID

        Returns:
            True if deleted, False if not found
        """
        instance = await self.get_by_id(id)
        if not instance:
            return False

        await self.session.delete(instance)
        await self.session.flush()
        return True

    async def exists(self, **kwargs) -> bool:
        """Check if a record exists with the given criteria.

        Args:
            **kwargs: Field criteria

        Returns:
            True if record exists, False otherwise
        """
        conditions = []
        for field, value in kwargs.items():
            if hasattr(self.model, field):
                conditions.append(getattr(self.model, field) == value)

        if not conditions:
            return False

        query = select(self.model).where(and_(*conditions))
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def count(self, filters: Dict[str, Any] = None) -> int:
        """Count records with optional filters.

        Args:
            filters: Dictionary of field filters

        Returns:
            Number of matching records
        """
        query = select(func.count(self.model.id))

        if filters:
            conditions = []
            for field, value in filters.items():
                if hasattr(self.model, field) and value is not None:
                    conditions.append(getattr(self.model, field) == value)
            if conditions:
                query = query.where(and_(*conditions))

        result = await self.session.execute(query)
        return result.scalar()

    def _build_query(
        self,
        filters: Dict[str, Any] = None,
        search: str = None,
        search_fields: List[str] = None,
        load_relationships: List[str] = None,
    ) -> Select:
        """Build a base query with common filters and relationships.

        Args:
            filters: Dictionary of field filters
            search: Search term
            search_fields: List of fields to search in
            load_relationships: List of relationship names to eager load

        Returns:
            SQLAlchemy Select query
        """
        query = select(self.model)

        # Apply filters
        if filters:
            conditions = []
            for field, value in filters.items():
                if hasattr(self.model, field) and value is not None:
                    conditions.append(getattr(self.model, field) == value)
            if conditions:
                query = query.where(and_(*conditions))

        # Apply search
        if search and search_fields:
            search_conditions = []
            search_term = f"%{search}%"
            for field in search_fields:
                if hasattr(self.model, field):
                    field_attr = getattr(self.model, field)
                    search_conditions.append(field_attr.ilike(search_term))
            if search_conditions:
                query = query.where(or_(*search_conditions))

        # Apply relationship loading
        if load_relationships:
            for relationship in load_relationships:
                if hasattr(self.model, relationship):
                    query = query.options(
                        selectinload(getattr(self.model, relationship))
                    )

        return query
