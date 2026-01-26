"""Type stub for AbstractToken."""

import datetime as dt
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy.orm import Mapped

from flask_more_smorest.perms.base_perms_model import BasePermsModel

if TYPE_CHECKING:
    pass

class AbstractToken(BasePermsModel):
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
