from typing import Self
import uuid
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
import datetime as dt
from contextlib import contextmanager

from flask import request, current_app, has_request_context
from sqlalchemy.orm import DeclarativeMeta, Mapped, mapped_column, class_mapper, make_transient
from sqlalchemy.orm.collections import InstrumentedList
import sqlalchemy as sa
from flask_jwt_extended import verify_jwt_in_request, exceptions
from werkzeug.exceptions import Unauthorized
from flask_smorest import abort
from marshmallow import pre_load, fields

from .exceptions import NotFoundError, ForbiddenError, UnauthorizedError
from .user import current_user
from .database import db, Base

class BaseSchema(SQLAlchemyAutoSchema):
    """Base schema for all schemas."""

    is_writable = fields.Boolean(dump_only=True)

    @pre_load
    def pre_load(self, data, **kwargs):
        """Pre-load hook to handle UUID conversion."""

        if request and hasattr(request, "view_args"):
            assert isinstance(request.view_args, dict)
            for view_arg, val in request.view_args.items():
                if view_arg not in self.fields or self.fields[view_arg].dump_only or data.get(view_arg) is not None:
                    continue
                # Should we only replace if view_arg is required?
                data[view_arg] = val

        return data


class BaseModelMeta(DeclarativeMeta):
    """Metaclass for BaseModel."""

    def _set_schema_cls(cls) -> type:
        # Dump all relationships
        dump_only = tuple(c.key for c in cls.__mapper__.relationships)

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

    def __getattr__(cls, name):
        if name == "Schema" and hasattr(cls, "__table__"):
            # Generate the schema class dynamically, to ensure models are fully generated
            # (avoid issues with circular imports in Models)
            return cls._set_schema_cls()

        raise AttributeError(f"type object '{cls.__name__}' has no attribute '{name}'")

    def __init__(cls, name, bases, attrs):
        pass


class BaseModel(db.Model, Base, metaclass=BaseModelMeta):
    """Base model for all Iao models."""

    __abstract__ = True
    perms_disabled = False

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

    def __init__(self, **kwargs):
        """Initialize the model after checking that all sub fields can be created."""

        check_create(kwargs.values())
        super().__init__(**kwargs)

    # @cached_property
    @property
    def is_writable(self) -> bool:
        """Check if the object is writable."""
        try:
            return self.can_write()
        except Exception:
            return False

    @classmethod
    @contextmanager
    def bypass_perms(cls_self):  # type: ignore
        """Context manager to bypass permissions for the class."""
        original = cls_self.perms_disabled
        cls_self.perms_disabled = True
        try:
            yield
        finally:
            cls_self.perms_disabled = original

    def can_write(self):
        """Does current user have write permission on object."""

        if self.perms_disabled or not has_request_context():
            return True

        is_admin = getattr(self, "is_admin", False)
        is_role_instance = type(self).__name__ == "UserRole"
        if not is_role_instance and not is_admin and self.is_current_user_admin():
            return True

        try:
            if self.id is None:
                return self._can_create()
            return self._can_write()
        except RuntimeError:
            raise UnauthorizedError("User must be authenticated")
        except Exception as e:
            print("DEBUG: can_write() ***EXCEPTION:", e)
            pass

        return False

    def can_read(self):
        """Does current user have read permissions on object."""

        if self.perms_disabled or not has_request_context():
            return True

        if self.id is None or self.is_current_user_admin():
            return True
        try:
            if self._can_read():
                return True
        except RuntimeError:
            raise UnauthorizedError("User must be authenticated")
        except Exception as e:
            print("DEBUG: can_read() ***EXCEPTION:", e)
            pass

        return False

    def can_create(self):
        """Can current user create object."""

        if self.perms_disabled or not has_request_context():
            return True
        is_admin = getattr(self, "is_admin", False)
        is_role_instance = type(self).__name__ == "UserRole"
        if not is_role_instance and not is_admin and self.is_current_user_admin():
            return True

        return self._can_create()

    def _can_write(self):
        """Permission helper: override in subclasses."""
        return False

    def _can_create(self):
        """Permission helper: override in subclasses."""
        return True  # adding new records is allowed by default

    def _can_read(self):
        """Permission helper: override in subclasses."""
        return self._can_write()


    @classmethod
    def is_current_user_admin(cls):
        try:
            verify_jwt_in_request()
            if current_user.is_admin:
                return True
        except exceptions.JWTExtendedException:
            return False
        except Unauthorized:
            return False
        return False

    @classmethod
    def get_by(cls, **kwargs) -> Self | None:
        """Get resource by kwargs (main call)."""

        # Convert UUID strings to UUID objects if necessary:
        for key, val in kwargs.items():
            col = class_mapper(cls).columns[key]
            if type(col.type) != sa.types.Uuid:
                continue
            if type(val) is str:
                try:
                    val = uuid.UUID(val)
                except ValueError:
                    raise TypeError(f"ID must be a valid UUID string, not {val}")
            if type(val) is not uuid.UUID:
                raise TypeError(f"ID must be a string or UUID, not {type(val)}")
            kwargs[key] = val

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
    def get_by_or_404(cls, **kwargs) -> Self:
        """Get resource by kwargs or raise 404."""
        resource = cls.get_by(**kwargs)
        if not resource:
            raise NotFoundError(f"{cls.__name__} with {kwargs} doesn't exist")
        return resource

    @classmethod
    def get(cls, id) -> Self | None:
        """Get resource by ID."""
        return cls.get_by(id=id)

    @classmethod
    def get_or_404(cls, id) -> Self:
        """Get resource by ID or raise 404."""
        resource = cls.get(id)
        if not resource:
            raise NotFoundError(f"{cls.__name__} id {id} doesn't exist")
        return resource

    @classmethod
    def check_exists(cls, id) -> None:
        """Check if resource exists and throw 404 otherwise."""
        if not cls.get(id):
            raise NotFoundError(f"{cls.__name__} id {id} doesn't exist")

    def save(self, commit=True) -> Self:
        """Save the record: add to session and optionally commit."""

        if self.id is not None:
            if not self.can_write():
                raise ForbiddenError(f"User not allowed to modify this resource: {self}")
            # TODO: should we move on_before_update to the update method?
            self.on_before_update()
        else:
            if not self.can_create():
                raise ForbiddenError(f"User not allowed to create resource: {self}")
            self.on_before_create()

        db.session.add(self)
        if commit:
            self.commit()

        return self

    def commit(self, is_delete: bool = False):
        """Commit the session."""
        is_create = self.id is None
        db.session.commit()
        if is_create:
            self.on_after_create()
        elif is_delete:
            self.on_after_delete()
        else:
            self.on_after_update()

    def update(self, commit: bool = True, **kwargs):
        """Update using key-values."""

        # NOTE: query version doesn't work with relationships:
        # stmt = sa.update(self.__class__).where(self.__class__.id == self.id).values(**kwargs)
        # db.session.execute(stmt)

        # recursively ensure that all kwargs IaoModels can be created:
        check_create(kwargs.values())

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

    def delete(self, commit: bool = True):
        """Delete the record."""
        if not self.can_write():
            raise ForbiddenError(f"User not allowed to delete this resource: {self}")

        # Ensure the object is up to date to prevent issues with cascading:
        db.session.refresh(self)
        self.on_before_delete()
        db.session.delete(self)
        if commit:
            self.commit(is_delete=True)

    def get_clone(self) -> Self:
        """Return a copy of the object with a new ID."""

        # remove the object from the session (set its state to detached)
        db.session.expunge(self)

        make_transient(self)
        setattr(self, "id", None)

        return self

    def on_before_create(self):
        """Hook to be called before creating the object."""
        pass

    def on_after_create(self):
        """Hook to be called after creating the object."""
        pass

    def on_before_update(self):
        """Hook to be called before updating the object."""
        pass

    def on_after_update(self):
        """Hook to be called after updating the object."""
        pass

    def on_before_delete(self):
        """Hook to be called before deleting the object."""
        pass

    def on_after_delete(self):
        """Hook to be called after deleting the object."""
        pass

    def __repr__(self):
        return "<" + self.__class__.__name__ + " id=" + str(self.id) + ">"


def check_create(val):
    """Recursively check that all BaseModel instances can be created."""
    for x in val:
        if isinstance(x, BaseModel):
            if x.id is None and not x.can_create():
                raise ForbiddenError(f"User not allowed to create resource: {x}")
        elif isinstance(x, list):
            check_create(x)
