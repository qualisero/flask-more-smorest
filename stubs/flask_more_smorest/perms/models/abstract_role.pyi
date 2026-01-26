"""Type stub for AbstractUserRole and AbstractDomain."""

from typing import TYPE_CHECKING, Any, ClassVar
from uuid import UUID

from sqlalchemy.orm import Mapped

if TYPE_CHECKING:
    pass

class AbstractDomain:
    __abstract__: bool
    __tablename__: str
    __table_args__: ClassVar[dict[str, bool] | tuple[Any, ...]]

    name: Mapped[str]
    display_name: Mapped[str]
    active: Mapped[bool]

class AbstractUserRole:
    __abstract__: bool
    __tablename__: str
    __table_args__: ClassVar[dict[str, bool] | tuple[Any, ...]]

    user_id: Mapped[UUID]
    domain_id: Mapped[UUID | None]
    _role: Mapped[str]

    @property
    def role(self) -> str: ...
    @property
    def user(self) -> Any: ...
    @property
    def domain(self) -> Any: ...
    def __init__(
        self,
        domain_id: UUID | str | None = None,
        role: str | Any | None = None,
        **kwargs: Any,
    ) -> None: ...
