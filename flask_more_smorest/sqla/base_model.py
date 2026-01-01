"""Base model for SQLAlchemy models with automatic schema generation.

This module provides BaseModel, a base class for all SQLAlchemy models
that includes automatic Marshmallow schema generation and common CRUD operations.
"""

import datetime as dt
import uuid
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from typing import Any, Self, TypeAlias, cast

import sqlalchemy as sa
from flask import request
from marshmallow import fields, pre_load
from marshmallow_sqlalchemy import ModelConverter, SQLAlchemyAutoSchema
from sqlalchemy.orm import DeclarativeMeta, Mapped, MapperProperty, class_mapper, make_transient, mapped_column
from sqlalchemy.orm.collections import InstrumentedList
from sqlalchemy.orm.state import InstanceState

from ..error.exceptions import NotFoundError
from .database import db

PropertyOrColumn: TypeAlias = MapperProperty | sa.Column


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
    def pre_load(self, data: dict[str, str | int | float | bool], **kwargs: Any) -> dict[str, str | int | float | bool]:
        """Pre-load hook to handle UUID conversion and view_args injection.

        Automatically injects URL parameters from Flask's request.view_args
        into the data being loaded, allowing schemas to access route parameters.

        Args:
            data: The input data dictionary
            **kwargs: Additional keyword arguments from Marshmallow

        Returns:
            The modified data dictionary with view_args injected
        """

        if request and (args := getattr(request, "view_args")):
            for view_arg, val in args.items():
                if view_arg not in self.fields or self.fields[view_arg].dump_only or data.get(view_arg) is not None:
                    continue
                # TODO: Consider restricting automatic injection to fields marked as required.
                #       This would ensure that only mandatory identifiers (for example, IDs coming
                #       from the URL path) are populated from view_args, while optional fields
                #       remain controlled by the client payload. Changing this behavior could
                #       affect how partial updates are interpreted and may reduce surprising
                #       cases where non-required fields are implicitly filled from the route.
                data[view_arg] = val

        return data


class BaseModelConverter(ModelConverter):
    """Model converter for BaseModel-based SQLAlchemy models."""

    def _add_relationship_kwargs(self, kwargs: dict[str, Any], prop: PropertyOrColumn) -> None:
        """Add keyword arguments to kwargs (in-place) based on the passed in
        relationship `Property`.
        Copied and adapted from marshmallow_sqlalchemy.convert.ModelConverter.
        """
        required = False
        allow_none = True
        for pair in prop.local_remote_pairs:
            if not pair[0].nullable:
                if prop.uselist is True or self.DIRECTION_MAPPING[prop.direction.name] is False:
                    allow_none = False
                    # Do not make required if a default is provided:
                    if not pair[0].default and not pair[0].server_default:
                        required = True
        # NOTE: always set dump_only to True for relationships (can be overriden in schema)
        kwargs.update({"allow_none": allow_none, "required": required, "dump_only": True})


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

        schema_cls = type(
            f"{cls.__name__}AutoSchema",
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
                        "model_converter": BaseModelConverter,
                        "dump_only": ("id", "created_at", "updated_at"),
                    },
                )
            },
        )
        # Cache it so it doesn't regenerate
        setattr(cls, "Schema", schema_cls)

        return schema_cls

    def __getattr__(cls, name: str) -> Any:
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


class BaseModel(db.Model, metaclass=BaseModelMeta):  # type: ignore[name-defined]
    """Base model for all application models.

    This base class provides:
    - Automatic UUID primary key generation
    - Automatic created_at and updated_at timestamps
    - Automatic Marshmallow schema generation
    - Common CRUD operations (get, save, update, delete)
    - Lifecycle hooks (on_before_create, on_after_create, etc.)

    All models should inherit from this class to get these features.

    Attributes:
        id: UUID primary key (automatically generated)
        created_at: Timestamp of creation
        updated_at: Timestamp of last update

    Example:
        >>> class Article(BaseModel):
        ...     __tablename__ = 'articles'
        ...     title: Mapped[str] = mapped_column(sa.String(200))
        ...     content: Mapped[str] = mapped_column(sa.Text)
    """

    __abstract__ = True

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

    def __init__(self, **kwargs: object) -> None:
        """Initialize the model.

        Args:
            **kwargs: Field values to initialize the model with

        Raises:
            RuntimeError: If database session is not active
        """
        try:
            session_proxy = db.session
        except RuntimeError as exc:  # Raised if init_db/app context not configured
            raise RuntimeError("In order to use BaseModel, you must import init_db from sqla and run it.") from exc

        if session_proxy is None:
            raise RuntimeError("In order to use BaseModel, you must import init_db from sqla and run it.")

        super().__init__(**kwargs)

    # @cached_property
    @property
    def is_writable(self) -> bool:
        """Return whether the instance is writable.

        BaseModel does not enforce permissions, so instances are
        considered writable by default. Permission-aware subclasses
        can override this property.
        """
        return True

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
                if not isinstance(val, (str, uuid.UUID)):
                    raise TypeError(f"Expected str or UUID for field {key}, got {type(val)}")
                normalized[key] = cls._to_uuid(val)
        return normalized

    @classmethod
    def get_by(cls, **kwargs: str | int | uuid.UUID | bool | None) -> Self | None:
        """Get resource by field values.

        Converts UUID strings to UUID objects automatically for UUID columns.

        Args:
            **kwargs: Field name and value pairs to filter by

        Returns:
            The matching model instance, or None if not found

        Raises:
            TypeError: If ID is not a valid UUID string or UUID object

        Example:
            >>> user = User.get_by(email='test@example.com')
            >>> article = Article.get_by(id='123e4567-e89b-12d3-a456-426614174000')
        """
        kwargs = cls._normalize_uuid_fields(kwargs)

        # don't automatically flush the session to avoid side effects
        with db.session.no_autoflush:
            result = db.session.execute(db.select(cls).filter_by(**kwargs)).scalar_one_or_none()

        return result

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

    @classmethod
    @contextmanager
    def bypass_perms(cls) -> Iterator[None]:
        """No-op context manager for base class (overridden in perms model)."""
        yield

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

        state = cast(InstanceState[Any], sa.inspect(self))
        is_transient = getattr(state, "transient", False)
        is_pending = getattr(state, "pending", False)
        is_new = is_transient or is_pending

        if is_new:
            self.on_before_create()
        else:
            self.on_before_update()

        db.session.add(self)
        if commit:
            self.commit(is_create=is_new)

        return self

    def commit(self, is_delete: bool = False, *, is_create: bool | None = None) -> None:
        """Commit the session and call appropriate lifecycle hooks.

        Args:
            is_delete: Whether this is a delete operation (default: False)
            is_create: Explicit flag indicating whether this commit corresponds to a creation
        """
        if is_create is None:
            state = cast(InstanceState[Any], sa.inspect(self))
            is_create = getattr(state, "pending", False) and not getattr(state, "deleted", False)

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
        # Refresh state if this instance is bound to the session; ignore otherwise.
        if self in db.session:
            db.session.refresh(self)

        self.on_before_delete()
        db.session.delete(self)
        if commit:
            self.commit(is_delete=True, is_create=False)

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

    def check_create(self, val: list | set | tuple | object) -> None:
        """Recursively validate nested models before creating them.

        Ensures nested BaseModel instances have an opportunity to perform
        their own permission checks (for example, BasePermsModel subclasses).
        """
        if isinstance(val, BaseModel):
            if val is self:
                return
            val.check_create(val)
            return

        if isinstance(val, dict):
            iterable: Iterable[object] = val.values()
        elif isinstance(val, Iterable) and not isinstance(val, (str, bytes)):
            iterable = val
        else:
            return

        for item in iterable:
            self.check_create(item)

    def __repr__(self) -> str:
        """Return string representation of the model.

        Returns:
            String in format "<ModelName id=...>"
        """
        return "<" + self.__class__.__name__ + " id=" + str(self.id) + ">"
