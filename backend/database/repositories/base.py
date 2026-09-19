"""
Generic Base Repository for SQLAlchemy 2.x CRUD operations.
"""

from typing import Any, Generic, Optional, Type, TypeVar
from sqlalchemy import Select, delete, select
from sqlalchemy.orm import Session

from backend.database.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Generic CRUD repository for SQLAlchemy models."""

    def __init__(self, model: Type[ModelType], session: Session):
        self.model = model
        self.session = session

    def create(self, **kwargs: Any) -> ModelType:
        """Create and persist a new model instance."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        self.session.commit()
        self.session.refresh(instance)
        return instance

    def get_by_id(self, id_: str) -> Optional[ModelType]:
        """Fetch single instance by primary key."""
        return self.session.get(self.model, id_)

    def list_all(self, limit: int = 100, offset: int = 0) -> list[ModelType]:
        """Fetch list of instances with pagination."""
        stmt: Select = select(self.model).limit(limit).offset(offset)
        return list(self.session.scalars(stmt).all())

    def update(self, id_: str, **kwargs: Any) -> Optional[ModelType]:
        """Update existing instance attributes."""
        instance = self.get_by_id(id_)
        if instance is None:
            return None
        for key, value in kwargs.items():
            if hasattr(instance, key) and value is not None:
                setattr(instance, key, value)
        self.session.commit()
        self.session.refresh(instance)
        return instance

    def delete(self, id_: str) -> bool:
        """Delete instance by primary key."""
        stmt = delete(self.model).where(self.model.id == id_)
        result = self.session.execute(stmt)
        self.session.commit()
        return result.rowcount > 0
