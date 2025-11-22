import logging
import uuid
import enum

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import db
from .models import BaseModel
from .utils import check_password_hash, generate_password_hash
from .exceptions import UnprocessableEntity
from .user import get_current_user

from flask_jwt_extended import verify_jwt_in_request, current_user as jwt_current_user, exceptions

logger = logging.getLogger(__name__)

current_user: "User" = jwt_current_user


def get_current_user() -> "User":
    """Get the current user from flask_jwt_extended."""
    return current_user


def get_current_user_id() -> uuid.UUID | None:
    """Get current user ID."""
    try:
        verify_jwt_in_request()
        return current_user.id
    except exceptions.JWTDecodeError:
        return None
    except Exception as e:
        # TODO: specifically handle being called outside of a request context
        logger.exception("Error getting current user ID: %s", e)
        return None

class User(BaseModel):
    """Registered app user."""

    email: Mapped[str] = mapped_column(db.String(128), unique=True, nullable=False)
    password: Mapped[bytes | None] = mapped_column(db.LargeBinary(128), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(db.Boolean(), default=True, info={"write": "admin"})

    roles: Mapped[list["UserRole"]] = relationship(
        "UserRole",
        back_populates="user",
        uselist=True,
        cascade="all, delete-orphan",
    )
    settings: Mapped[list["UserSetting"]] = relationship(
        "UserSetting",
        back_populates="user",
        uselist=True,
        cascade="all, delete-orphan",
    )

    def __init__(self, **kwargs):
        """Create new user."""

        password = kwargs.pop("password", None)
        super().__init__(**kwargs)
        if password:
            self.set_password(password)

    def update(self, commit=True, **kwargs):
        password = kwargs.pop("password", None)
        old_password = kwargs.pop("old_password", None)
        if password and not self.perms_disabled:
            if old_password is None:
                raise UnprocessableEntity(
                    fields={"old_password": "Cannot be empty"},
                    message="Must provide old_password to set new password",
                )
            if not self.is_password_correct(old_password):
                raise UnprocessableEntity(
                    message=f"Old password is incorrect",
                    fields={"old_password": "Old password is incorrect"},
                    location="json",
                )

        super().update(commit=False, **kwargs)
        if password:
            self.set_password(password)
        return self.save(commit=commit)

    def set_password(self, password):
        """Set password."""
        self.password = generate_password_hash(password)

    def is_password_correct(self, value):
        """Check password."""
        if self.password is None:
            return False
        return isinstance(value, str) and check_password_hash(password=value, hashed=self.password)

    def _can_write(self):
        """Does current user have write permissions on object."""
        return self.id == get_current_user().id

    def _can_create(self):
        """Does current user have the right to create new objects."""
        return get_current_user().is_admin

    @property
    def is_admin(self):
        return self.has_role(UserRole.Role.ADMIN) or self.is_superadmin

    @property
    def is_superadmin(self):
        return self.has_role(UserRole.Role.SUPERADMIN)

    def has_role(self, role) -> bool:
        return any(
            r.role == role
            for r in self.roles
        )


"""
██████   ██████  ██      ███████ ███████
██   ██ ██    ██ ██      ██      ██
██████  ██    ██ ██      █████   ███████
██   ██ ██    ██ ██      ██           ██
██   ██  ██████  ███████ ███████ ███████
"""


class UserRole(BaseModel):
    """User roles."""

    class Role(str, enum.Enum):
        SUPERADMIN = "superadmin"
        ADMIN = "admin"
        EDITOR = "editor"
        USER = "user"

    user_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), db.ForeignKey(User.id), nullable=False)

    user: Mapped["User"] = relationship(User, back_populates="roles")
    role: Mapped[Role] = mapped_column(sa.types.Enum(Role, native_enum=False), nullable=False)


    def _can_write(self):
        """Does current user have write permissions on role object."""
        if self.role == self.Role.SUPERADMIN or self.role == self.Role.ADMIN:
            return get_current_user().is_superadmin
        return get_current_user().is_admin

    def _can_create(self):
        """Does current user have the right to create new roles."""
        if self.role == self.Role.SUPERADMIN or self.role == self.Role.ADMIN:
            return get_current_user().is_superadmin
        return get_current_user().is_admin

    def _can_read(self):
        """Does current user have read permissions on role object."""
        return self.user.can_read()



"""
███████ ███████ ████████ ████████ ██ ███    ██  ██████  ███████
██      ██         ██       ██    ██ ████   ██ ██       ██
███████ █████      ██       ██    ██ ██ ██  ██ ██   ███ ███████
     ██ ██         ██       ██    ██ ██  ██ ██ ██    ██      ██
███████ ███████    ██       ██    ██ ██   ████  ██████  ███████
"""


class UserSetting(BaseModel):
    """User-specific settings."""

    user_id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(as_uuid=True), db.ForeignKey(User.id), nullable=False)
    user: Mapped["User"] = relationship(User, back_populates="settings")
    key: Mapped[str] = mapped_column(db.String(80), nullable=False)
    value: Mapped[str | None] = mapped_column(db.String(1024), nullable=True)

    __table_args__ = (db.UniqueConstraint(user_id, key),)

    def _can_write(self):
        """Does current user have write permissions on setting object."""
        return self.user.can_write()

    def _can_create(self):
        """Does current user have the right to create new settings."""
        return self.user.can_write()

    def _can_read(self):
        """Does current user have read permissions on setting object."""
        return self.user.can_read()

