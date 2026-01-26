"""Type stub for AbstractUserSetting."""

from typing import TYPE_CHECKING, Any, ClassVar
from uuid import UUID

from sqlalchemy.orm import Mapped

from flask_more_smorest.perms.base_perms_model import BasePermsModel

if TYPE_CHECKING:
    pass

class AbstractUserSetting(BasePermsModel):
    __abstract__: bool
    __tablename__: str
    __table_args__: ClassVar[dict[str, bool] | tuple[Any, ...]]

    user_id: Mapped[UUID]
    key: Mapped[str]
    value: Mapped[str | None]

    @property
    def user(self) -> Any: ...
