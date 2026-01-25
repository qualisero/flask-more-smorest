"""Type stub for AbstractUserSetting."""

from typing import TYPE_CHECKING, Any, ClassVar
from uuid import UUID
from sqlalchemy.orm import Mapped

if TYPE_CHECKING:
    from .abstract_user import AbstractUser

class AbstractUserSetting:
    __abstract__: bool
    __tablename__: str
    __table_args__: ClassVar[dict[str, bool] | tuple[Any, ...]]

    user_id: Mapped[UUID]
    key: Mapped[str]
    value: Mapped[str | None]

    @property
    def user(self) -> Any: ...
