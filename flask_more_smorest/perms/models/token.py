"""Token model for API authentication."""

from __future__ import annotations

from .abstract_token import AbstractToken


class Token(AbstractToken):
    """API tokens for user authentication.

    This is a concrete implementation of AbstractToken. For customization,
    subclass AbstractToken instead of this class.

    Permission checks are delegated to the owning user (inherited from AbstractToken).

    Example:
        from sqlalchemy.orm import Mapped, mapped_column

        class CustomToken(AbstractToken):
            __tablename__ = "token"
            custom_field: Mapped[str] = mapped_column(sa.String(100))
    """
