Permissions System
==================

Flask-More-Smorest provides a permissions system via ``BasePermsModel`` that integrates with CRUD operations.

Overview
--------

Control who can read, write, create, and delete resources by overriding permission hooks.

BasePermsModel
--------------

Extends ``BaseModel`` with permission checking:

.. code-block:: python

   from flask_more_smorest.perms import BasePermsModel
   from flask_more_smorest.sqla import db
   from sqlalchemy.orm import Mapped, mapped_column

   class Article(BasePermsModel):
       title: Mapped[str] = mapped_column(db.String(100))
       content: Mapped[str] = mapped_column(db.Text)

       def _can_write(self, current_user) -> bool:
           """Only owner or admin can write."""
           if not current_user:
               return False
           return self.user_id == current_user.id or current_user.is_admin

       def _can_read(self, current_user) -> bool:
           """Anyone can read public articles."""
           if self.is_public:
               return True
           return self.user_id == current_user.id if current_user else False

Permission Hooks
----------------

Override these methods to implement custom permissions. The ``current_user`` parameter contains the authenticated user or ``None``.

- ``_can_read(self, current_user) -> bool``: Called when reading a resource
- ``_can_write(self, current_user) -> bool``: Called when updating a resource
- ``_can_create(self, current_user) -> bool``: Called when creating a resource (class method)

Public API methods that enforce permissions:

- ``can_read() -> bool``: Check if current user can read this resource
- ``can_write() -> bool``: Check if current user can write to this resource
- ``can_create() -> bool``: Check if current user can create resources (class method)
- ``get_by(**filters) -> Self | None``: Get resource with permission check

Return 404 vs 403
-----------------

By default, when a user lacks permission, a 404 is returned instead of 403. This prevents information leakage.

Configure this behavior:

.. code-block:: python

   app.config["RETURN_404_ON_ACCESS_DENIED"] = True  # Default

Permission Mixins
-----------------

HasUserMixin
~~~~~~~~~~~~

Adds ``user_id`` foreign key and ``user`` relationship:

.. code-block:: python

   from flask_more_smorest.perms import BasePermsModel, HasUserMixin

   class Comment(HasUserMixin, BasePermsModel):
       content: Mapped[str] = mapped_column(db.Text)
       # user_id and user relationship automatically added

UserOwnershipMixin
~~~~~~~~~~~~~~~~~~

Unified mixin with two configurable modes:

**Simple Ownership** (default, ``__delegate_to_user__ = False``):

.. code-block:: python

   class Note(UserOwnershipMixin, BasePermsModel):
       title: Mapped[str] = mapped_column(db.String(100))
       # Users can read/write only their own notes
       # Admins can access all notes

**Implementation**: Checks if ``user_id == current_user.id``

**Delegated Permissions** (``__delegate_to_user__ = True``):

.. code-block:: python

   class Token(UserOwnershipMixin, BasePermsModel):
       __delegate_to_user__ = True
       token: Mapped[str] = mapped_column(db.String(500))
       # Delegates to user's _can_write() and _can_read() methods

**Implementation**: Calls ``self.user._can_write(current_user)`` to delegate to user's permissions

.. note::

   Both modes benefit from **admin bypass** in ``BasePermsModel``,
   so admins can access all resources.

Bypassing Permissions
---------------------

Context Manager
~~~~~~~~~~~~~~~

.. code-block:: python

   with Article.bypass_perms():
       article.delete()  # No permission check

Per-Instance
~~~~~~~~~~~~

.. code-block:: python

   article.perms_disabled = True
   article.delete()  # No permission check

Integration with CRUD
---------------------

CRUDBlueprint automatically enforces permissions:

.. code-block:: python

   from flask_more_smorest.perms import CRUDBlueprint

   articles = CRUDBlueprint(
       "articles",
       __name__,
       model=Article,
       schema=Article.Schema,
   )

   # All operations enforce Article's permission methods

Configure route-level options:

.. code-block:: python

   from flask_more_smorest.perms import CRUDBlueprint, MethodConfig

   articles = CRUDBlueprint(
       "articles",
       __name__,
       model=Article,
       schema=Article.Schema,
       methods={
           CRUDMethod.INDEX: MethodConfig(public=True),  # No auth required
           CRUDMethod.DELETE: MethodConfig(admin_only=True),  # Admins only
       },
   )

Example: Blog with Permissions
-------------------------------

.. code-block:: python

   from flask_more_smorest.perms import (
       BasePermsModel,
       HasUserMixin,
       UserOwnershipMixin,
   )

   class Article(HasUserMixin, BasePermsModel):
       title: Mapped[str] = mapped_column(db.String(100))
       content: Mapped[str] = mapped_column(db.Text)
       is_published: Mapped[bool] = mapped_column(db.Boolean, default=False)

       def _can_read(self, current_user) -> bool:
           # Published articles: anyone can read
           if self.is_published:
               return True
           # Drafts: only owner or admin
           if not current_user:
               return False
           return self.user_id == current_user.id or current_user.is_admin

       def _can_write(self, current_user) -> bool:
           # Only owner or admin can write
           if not current_user:
               return False
           return self.user_id == current_user.id or current_user.is_admin

       def _can_delete(self, current_user) -> bool:
           # Only admin can delete
           return current_user is not None and current_user.is_admin


   class Comment(UserOwnershipMixin, BasePermsModel):
       article_id: Mapped[uuid.UUID] = mapped_column(db.ForeignKey("article.id"))
       content: Mapped[str] = mapped_column(db.Text)
       # UserOwnershipMixin provides: users can only read/write their own comments
