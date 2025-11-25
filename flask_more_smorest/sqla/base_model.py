"""Base model for SQLAlchemy models with automatic schema generation.

This module provides BaseModel, a base class for all SQLAlchemy models
that includes automatic Marshmallow schema generation, permission checking,
and common CRUD operations.
"""

import datetime as dt
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Self

import sqlalchemy as sa
from flask import current_app, request
from marshmallow import fields, pre_load
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from sqlalchemy.orm import DeclarativeMeta, Mapped, class_mapper, make_transient, mapped_column
from sqlalchemy.orm.collections import InstrumentedList

from ..error.exceptions import ForbiddenError, NotFoundError
from .database import Base, db

if TYPE_CHECKING:
    from flask import Flask  # noqa: F401


class BaseSchema(SQLAlchemyAutoSchema):
    """Base schema for all Marshmallow schemas.

    This schema extends SQLAlchemyAutoSchema with automatic view_args
    injection for URL parameters and adds an is_writable field for
    permission checking.

    Attributes:
        is_writable: Read-only boolean field indicating if current user
                     can write to the resource
    """

    is_writable = fields.Boolean(dump_only=True)

    @pre_load
    def pre_load(
        self, data: dict[str, str | int | float | bool], **kwargs: dict
    ) -> dict[str, str | int | float | bool]:
        """Pre-load hook to handle UUID conversion and view_args injection.

        Automatically injects URL parameters from Flask's request.view_args
        into the data being loaded, allowing schemas to access route parameters.

        Args:
            data: The input data dictionary
            **kwargs: Additional keyword arguments from Marshmallow

        Returns:
            The modified data dictionary with view_args injected
        """

        if request and hasattr(request, "view_args"):
            assert isinstance(request.view_args, dict)
            for view_arg, val in request.view_args.items():
                if view_arg not in self.fields or self.fields[view_arg].dump_only or data.get(view_arg) is not None:
                    continue
                # Should we only replace if view_arg is required?
                data[view_arg] = val

        return data


class BaseModelMeta(DeclarativeMeta):
    """Metaclass for BaseModel that provides automatic schema generation.

    This metaclass automatically generates a Marshmallow schema for each
    model class, with proper configuration for relationships, foreign keys,
    and dump-only fields.
    """

    def _set_schema_cls(cls) -> type[BaseSchema]:
        """Dynamically generate the Schema class for the model.

        Returns:
            The generated schema class for this model
        """

        # Dump all relationships
        dump_only = tuple(c.key for c in getattr(cls.__mapper__, "relationships", []))

        schema_cls = type(
            f"{cls.__name__}SchemaBase",
            (BaseSchema,),
            {
                "Meta": type(
                    "Meta",
                    (object,),
                    {
                        "model": cls,
                        "include_relationships": True,
                        "include_fk": True,
                        "load_instance": True,
                        "sqla_session": db.session,
                        "dump_only": ("id", "created_at", "updated_at") + dump_only,
                    },
                )
            },
        )
        # Cache it so it doesn't regenerate
        setattr(cls, "Schema", schema_cls)

        return schema_cls

    def __getattr__(cls, name: str) -> type[BaseSchema]:
        """Get attribute with lazy schema generation.

        Args:
            name: Attribute name to retrieve

        Returns:
            The schema class if name is 'Schema', otherwise raises AttributeError

        Raises:
            AttributeError: If the attribute doesn't exist
        """
        if name == "Schema" and hasattr(cls, "__table__"):
            # Generate the schema class dynamically, to ensure models are fully generated
            # (avoid issues with circular imports in Models)
            return cls._set_schema_cls()

        raise AttributeError(f"type object '{cls.__name__}' has no attribute '{name}'")

    def __init__(cls, name: str, bases: tuple[type, ...], attrs: dict[str, object]) -> None:
        """Initialize the metaclass.

        Args:
            name: Name of the class being created
            bases: Tuple of base classes
            attrs: Dictionary of class attributes
        """
        pass


class BaseModel(db.Model, Base, metaclass=BaseModelMeta):
    """Base model for all application models.

    This base class provides:
    - Automatic UUID primary key generation
    - Automatic created_at and updated_at timestamps
    - Automatic Marshmallow schema generation
    - Common CRUD operations (get, save, update, delete)
    - Permission checking hooks (can_read, can_write, can_create)
    - Lifecycle hooks (on_before_create, on_after_create, etc.)

    All models should inherit from this class to get these features.

    Attributes:
        id: UUID primary key (automatically generated)
        created_at: Timestamp of creation
        updated_at: Timestamp of last update
        perms_disabled: Whether permission checks are disabled (default: True)

    Example:
        >>> class Article(BaseModel):
        ...     __tablename__ = 'articles'
        ...     title: Mapped[str] = mapped_column(sa.String(200))
        ...     content: Mapped[str] = mapped_column(sa.Text)
    """

    __abstract__ = True
    perms_disabled = True  # Default to True, overridden in perms model

    id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        sort_order=-10,
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=dt.datetime.now, server_default=sa.func.now(), sort_order=10
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=dt.datetime.now,
        server_default=sa.func.now(),
        onupdate=dt.datetime.now,
        sort_order=11,
    )

    def __init__(self, **kwargs) -> None:
        """Initialize the model.

        Args:
            **kwargs: Field values to initialize the model with

        Raises:
            RuntimeError: If database session is not active
        """
        if not db.session or not db.session.is_active:
            raise RuntimeError("In order to use BaseModel, you must import init_db from sqla and run it.")

        super().__init__(**kwargs)

    # @cached_property
    @property
    def is_writable(self) -> bool:
        """Check if the object is writable by the current user.

        Returns:
            True if the current user can write to this object, False otherwise
        """
        try:
            return self.can_write()
        except Exception:
            return False

    @classmethod
    def _to_uuid(cls, value: str | uuid.UUID) -> uuid.UUID:
        """Convert string or UUID value to UUID object.

        Args:
            value: String representation or UUID object

        Returns:
            UUID object

        Raises:
            TypeError: If value is not a valid UUID string or UUID object
        """
        if isinstance(value, str):
            try:
                return uuid.UUID(value)
            except ValueError:
                raise TypeError(f"ID must be a valid UUID string, not {value}")
        if not isinstance(value, uuid.UUID):
            raise TypeError(f"ID must be a string or UUID, not {type(value)}")
        return value

    @classmethod
    def _normalize_uuid_fields(
        cls, fields: dict[str, str | int | uuid.UUID | bool | None]
    ) -> dict[str, str | int | uuid.UUID | bool | None]:
        """Convert UUID string fields to UUID objects based on column types.

        Args:
            fields: Dictionary of field names and values

        Returns:
            Dictionary with UUID strings converted to UUID objects
        """
        normalized = fields.copy()
        for key, val in fields.items():
            col = class_mapper(cls).columns[key]
            if isinstance(col.type, sa.types.Uuid) and val is not None:
                assert isinstance(val, (str, uuid.UUID)), f"Expected str or UUID for field {key}, got {type(val)}"
                normalized[key] = cls._to_uuid(val)
        return normalized

    @classmethod
    def get_by(cls, **kwargs: str | int | uuid.UUID | bool | None) -> Self | None:
        """Get resource by field values.

        Converts UUID strings to UUID objects automatically for UUID columns.

        Args:
            **kwargs: Field name and value pairs to filter by

        Returns:
            The matching model instance, or None if not found or access denied

        Raises:
            TypeError: If ID is not a valid UUID string or UUID object
            ForbiddenError: If user doesn't have read permission and
                           RETURN_404_ON_ACCESS_DENIED is False

        Example:
            >>> user = User.get_by(email='test@example.com')
            >>> article = Article.get_by(id='123e4567-e89b-12d3-a456-426614174000')
        """
        kwargs = cls._normalize_uuid_fields(kwargs)

        # don't automatically flush the session to avoid side effects
        with db.session.no_autoflush:
            res = db.session.execute(db.select(cls).filter_by(**kwargs)).scalar_one_or_none()

        if res and not cls.perms_disabled and not res.can_read():
            if current_app.config.get("RETURN_404_ON_ACCESS_DENIED"):
                # If the resource exists but the user cannot read it, return None (raises 404)
                return None
            raise ForbiddenError(f"User not allowed to read this resource: {res}")

        return res

    @classmethod
    def get_by_or_404(cls, **kwargs: str | int | uuid.UUID | bool | None) -> Self:
        """Get resource by field values or raise 404.

        Args:
            **kwargs: Field name and value pairs to filter by

        Returns:
            The matching model instance

        Raises:
            NotFoundError: If no matching resource is found
            TypeError: If ID field has invalid UUID format
            ForbiddenError: If user doesn't have read permission

        Example:
            >>> user = User.get_by_or_404(email='test@example.com')
        """
        resource = cls.get_by(**kwargs)
        if not resource:
            raise NotFoundError(f"{cls.__name__} with {kwargs} doesn't exist")
        return resource

    @classmethod
    def get(cls, id: uuid.UUID | str) -> Self | None:
        """Get resource by ID.

        Args:
            id: Resource ID (UUID or UUID string)

        Returns:
            The matching model instance, or None if not found

        Example:
            >>> user = User.get('123e4567-e89b-12d3-a456-426614174000')
        """
        return cls.get_by(id=id)

    @classmethod
    def get_or_404(cls, id: uuid.UUID | str) -> Self:
        """Get resource by ID or raise 404.

        Args:
            id: Resource ID (UUID or UUID string)

        Returns:
            The matching model instance

        Raises:
            NotFoundError: If no matching resource is found

        Example:
            >>> user = User.get_or_404('123e4567-e89b-12d3-a456-426614174000')
        """
        resource = cls.get(id)
        if not resource:
            raise NotFoundError(f"{cls.__name__} id {id} doesn't exist")
        return resource

    @classmethod
    def check_exists(cls, id: uuid.UUID | str) -> None:
        """Check if resource exists and throw 404 otherwise.

        Args:
            id: Resource ID to check

        Raises:
            NotFoundError: If resource doesn't exist
        """
        if not cls.get(id):
            raise NotFoundError(f"{cls.__name__} id {id} doesn't exist")

    def _check_permission(self, operation: str) -> None:
        """Check if user has permission for specified operation.

        Args:
            operation: Operation type ('write', 'create', 'delete')

        Raises:
            ForbiddenError: If user doesn't have permission for the operation
        """
        permission_methods = {
            "write": (self.can_write, "modify"),
            "create": (self.can_create, "create"),
            "delete": (self.can_write, "delete"),
        }

        check_method, action = permission_methods[operation]
        if not check_method():
            raise ForbiddenError(f"User not allowed to {action} this resource: {self}")

    def save(self, commit: bool = True) -> Self:
        """Save the record: add to session and optionally commit.

        Args:
            commit: Whether to commit the transaction (default: True)

        Returns:
            The saved model instance (self)

        Raises:
            ForbiddenError: If user doesn't have permission to create/modify

        Example:
            >>> user = User(email='test@example.com')
            >>> user.save()
        """

        if self.id is not None:
            self._check_permission("write")
            # TODO: should we move on_before_update to the update method?
            self.on_before_update()
        else:
            self._check_permission("create")
            self.on_before_create()

        db.session.add(self)
        if commit:
            self.commit()

        return self

    def commit(self, is_delete: bool = False) -> None:
        """Commit the session and call appropriate lifecycle hooks.

        Args:
            is_delete: Whether this is a delete operation (default: False)
        """
        is_create = self.id is None
        db.session.commit()
        if is_create:
            self.on_after_create()
        elif is_delete:
            self.on_after_delete()
        else:
            self.on_after_update()

    def update(self, commit: bool = True, **kwargs: str | int | float | bool | bytes | None) -> None:
        """Update model fields using key-value pairs.

        Supports updating relationships and recursively checks create permissions
        for nested objects.

        Args:
            commit: Whether to commit the transaction (default: True)
            **kwargs: Field names and values to update

        Raises:
            AttributeError: If field doesn't exist on the model
            ForbiddenError: If user doesn't have permission to modify

        Example:
            >>> user.update(email='new@example.com', is_active=False)
        """

        # NOTE: query version doesn't work with relationships:
        # stmt = sa.update(self.__class__).where(self.__class__.id == self.id).values(**kwargs)
        # db.session.execute(stmt)

        # recursively ensure that all kwargs sub-models can be created:
        self.check_create(kwargs.values())

        for key, val in kwargs.items():
            if hasattr(self, key):
                # TODO: use class to check for relationships:
                if isinstance(getattr(self, key), InstrumentedList):
                    # Clean up relationships first:
                    setattr(self, key, [])
                    db.session.flush()
                setattr(self, key, val)
            else:
                raise AttributeError(f"{self.__class__.__name__} has no attribute {key}")
        self.save(commit=commit)

    def delete(self, commit: bool = True) -> None:
        """Delete the record from the database.

        Args:
            commit: Whether to commit the transaction (default: True)

        Raises:
            ForbiddenError: If user doesn't have permission to delete

        Example:
            >>> user = User.get(user_id)
            >>> user.delete()
        """
        self._check_permission("delete")

        # Ensure the object is up to date to prevent issues with cascading:
        db.session.refresh(self)
        self.on_before_delete()
        db.session.delete(self)
        if commit:
            self.commit(is_delete=True)

    def get_clone(self) -> Self:
        """Return a copy of the object with a new ID.

        Creates a detached copy of this instance with ID set to None,
        suitable for creating a duplicate record.

        Returns:
            A new instance with the same field values but no ID

        Example:
            >>> original = User.get(user_id)
            >>> clone = original.get_clone()
            >>> clone.save()  # Creates new record
        """

        # remove the object from the session (set its state to detached)
        db.session.expunge(self)

        make_transient(self)
        setattr(self, "id", None)

        return self

    def on_before_create(self) -> None:
        """Hook to be called before creating the object.

        Override this method to add custom logic before object creation.
        """
        pass

    def on_after_create(self) -> None:
        """Hook to be called after creating the object.

        Override this method to add custom logic after object creation.
        """
        pass

    def on_before_update(self) -> None:
        """Hook to be called before updating the object.

        Override this method to add custom logic before object updates.
        """
        pass

    def on_after_update(self) -> None:
        """Hook to be called after updating the object.

        Override this method to add custom logic after object updates.
        """
        pass

    def on_before_delete(self) -> None:
        """Hook to be called before deleting the object.

        Override this method to add custom logic before object deletion.
        """
        pass

    def on_after_delete(self) -> None:
        """Hook to be called after deleting the object.

        Override this method to add custom logic after object deletion.
        """
        pass

    @classmethod
    @contextmanager
    def bypass_perms(cls) -> Iterator[None]:
        """No-op context manager for base class (overridden in perms model).

        Yields:
            None
        """
        yield

    def can_write(self) -> bool:
        """Check if current user can write to this object.

        No-op for base class (overridden in perms model).

        Returns:
            True (always allows writes in base model)
        """
        return True

    def can_read(self) -> bool:
        """Check if current user can read this object.

        No-op for base class (overridden in perms model).

        Returns:
            True (always allows reads in base model)
        """
        return True

    def can_create(self) -> bool:
        """Check if current user can create this object.

        No-op for base class (overridden in perms model).

        Returns:
            True (always allows creation in base model)
        """
        return True

    @classmethod
    def is_current_user_admin(cls) -> bool:
        """Check if current user is an admin.

        No-op for base class (overridden in perms model).

        Returns:
            False (no admin concept in base model)
        """
        return False

    def check_create(self, val: object) -> bool:
        """Check if nested objects can be created.

        No-op for base class (overridden in perms model).

        Args:
            val: Value to check (can be any object)

        Returns:
            True (always allows in base model)
        """
        return True

    def __repr__(self) -> str:
        """Return string representation of the model.

        Returns:
            String in format "<ModelName id=...>"
        """
        return "<" + self.__class__.__name__ + " id=" + str(self.id) + ">"
