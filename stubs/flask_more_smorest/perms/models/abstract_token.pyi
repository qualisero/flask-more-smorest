"""Type stub for AbstractToken."""

from typing import TYPE_CHECKING, Any, ClassVar
from uuid import UUID
import datetime as dt
from sqlalchemy.orm import Mapped

if TYPE_CHECKING:
    from .abstract_user import AbstractUser

class AbstractToken:
    __abstract__: bool
    __tablename__: str
    __table_args__: ClassVar[dict[str, bool] | tuple[Any, ...]]

    token: Mapped[str]
    description: Mapped[str | None]
    expires_at: Mapped[dt.datetime | None]
    revoked: Mapped[bool]
    revoked_at: Mapped[dt.datetime | None]

    @property
    def user(self) -> Any: ...
