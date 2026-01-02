Permissions System
==================

Flask-More-Smorest provides a powerful permissions system based on ``BasePermsModel`` that integrates seamlessly with CRUD operations.

Overview
--------

The permissions system allows you to:

- Control who can read, write, create, and delete resources
- Implement custom permission logic via hooks
- Use pre-built mixins for common patterns (user ownership, role-based access)
- Return 404 instead of 403 for unauthorized access (security by obscurity)
- Bypass permissions when needed (e.g., for system operations)

BasePermsModel
--------------

``BasePermsModel`` extends ``BaseModel`` with permission checking:

.. code-block:: python

   from flask_more_smorest.perms import BasePermsModel
   from flask_more_smorest.sqla import db
   from sqlalchemy.orm import Mapped, mapped_column

   class Critter(BasePermsModel):
       # Table name automatically set to "critter"
       
       name: Mapped[str] = mapped_column(db.String(100), nullable=False)
       species: Mapped[str] = mapped_column(db.String(50), nullable=False)
       is_adoptable: Mapped[bool] = mapped_column(db.Boolean, default=True)

       def _can_write(self) -> bool:
           """Custom write permission logic"""
           return self.is_current_user_admin()

       def _can_read(self) -> bool:
           """Custom read permission logic"""
           # Anyone can read adoptable critters
           if self.is_adoptable:
               return True
           # Only admin can see non-adoptable ones
           return self.is_current_user_admin()

Permission Hooks
----------------

Override these methods to implement custom permission logic:

- ``_can_read() -> bool``: Called when reading a resource
- ``_can_write() -> bool``: Called when updating a resource
- ``_can_create() -> bool``: Called when creating a resource (class method)
- ``_can_delete() -> bool``: Called when deleting a resource

Public API methods that enforce permissions:

- ``can_read() -> bool``: Check if current user can read this resource
- ``can_write() -> bool``: Check if current user can write to this resource
- ``can_create() -> bool``: Check if current user can create resources (class method)
- ``get_by(**filters) -> Self | None``: Get resource with permission check
- ``get_by_or_404(**filters) -> Self``: Get resource or return 404 if not found or no permission

Return 404 vs 403
-----------------

By default, when a user doesn't have permission to access a resource, a 404 is returned instead of 403. This prevents information leakage (security by obscurity).

You can control this behavior:

.. code-block:: python

   from flask import Flask
   
   app = Flask(__name__)
   app.config["RETURN_404_ON_ACCESS_DENIED"] = True  # Default
   # Or set to False to return 403

You can also override this per-request:

.. code-block:: python

   from flask import request
   
   # In your view or blueprint
   request.environ["RETURN_404_ON_ACCESS_DENIED"] = False

Permission Mixins
-----------------

Flask-More-Smorest includes several pre-built mixins for common permission patterns:

HasUserMixin
^^^^^^^^^^^^

Adds a ``user_id`` foreign key and ``user`` relationship:

.. code-block:: python

   from flask_more_smorest.perms import BasePermsModel, HasUserMixin

   class Critter(HasUserMixin, BasePermsModel):
       # Table name automatically set to "critter"
       
       name: Mapped[str] = mapped_column(db.String(100))
       species: Mapped[str] = mapped_column(db.String(50))
       # user_id and user relationship automatically added

UserOwnershipMixin
^^^^^^^^^^^^^^^^^^

Unified mixin for user-owned resources with two configurable modes:

**Simple Ownership Mode** (default, ``__delegate_to_user__ = False``):

.. code-block:: python

   from flask_more_smorest.perms import BasePermsModel, UserOwnershipMixin

   class Toy(UserOwnershipMixin, BasePermsModel):
       # Uses default: __delegate_to_user__ = False
       
       name: Mapped[str] = mapped_column(db.String(100))
       color: Mapped[str] = mapped_column(db.String(50))
       # Users can read/write only their own toys (simple user_id check)
       # Admins can access all toys (admin bypass in BasePermsModel)

**Implementation**: Checks if ``user_id == current_user_id``

**Use for**: Simple user-owned resources (toys, notes, posts, comments)

**Delegated Permissions Mode** (``__delegate_to_user__ = True``):

.. code-block:: python

   from flask_more_smorest.perms import (
       BasePermsModel, 
       HasUserMixin, 
       UserOwnershipMixin
   )

   class UserToken(HasUserMixin, UserOwnershipMixin, BasePermsModel):
       __delegate_to_user__ = True
       
       token: Mapped[str] = mapped_column(db.String(500))
       # Delegates to user's _can_write() and _can_read() methods
       # If user has custom permission logic, resource inherits it
       # Admins can access all tokens (admin bypass in BasePermsModel)

**Implementation**: Calls ``self.user._can_write()`` to delegate to user's permissions

**Use for**: Resources that extend the user (tokens, settings, API keys)

.. note::

   **Configuration Options**:
   
   - ``__delegate_to_user__``: Set to ``True`` for delegated permissions, ``False`` for simple ownership (default: ``False``)
   - ``__user_id_nullable__``: Set to ``True`` to allow nullable user_id (default: ``False``)
   
   Both modes benefit from the **admin bypass** built into ``BasePermsModel``, 
   so admins can access all resources regardless of ownership.

Combining Mixins
^^^^^^^^^^^^^^^^

You can combine multiple mixins:

.. code-block:: python

   from flask_more_smorest.perms import (
       BasePermsModel,
       HasUserMixin,
       UserOwnershipMixin,
       ProfileMixin,
   )

   class UserProfile(
       HasUserMixin, 
       UserOwnershipMixin, 
       ProfileMixin, 
       BasePermsModel
   ):
       __delegate_to_user__ = True  # Inherit user's permissions
       
       bio: Mapped[str] = mapped_column(db.Text, nullable=True)
       # Has user relationship, delegated permissions, and profile fields

Bypassing Permissions
---------------------

Sometimes you need to bypass permissions (e.g., system operations, migrations):

Context Manager
^^^^^^^^^^^^^^^

.. code-block:: python

   from flask_more_smorest.perms import bypass_perms

   with bypass_perms():
       # All permission checks are disabled in this block
       user = User.get_by(email="system@example.com")
       user.update(is_active=False)

Decorator
^^^^^^^^^

.. code-block:: python

   from flask_more_smorest.perms import bypass_perms

   @bypass_perms()
   def system_cleanup():
       # Permissions disabled for this entire function
       inactive_users = User.query.filter_by(is_active=False).all()
       for user in inactive_users:
           user.delete()

Instance Attribute
^^^^^^^^^^^^^^^^^^

.. code-block:: python

   user = User.get_by(id=some_id)
   user.perms_disabled = True
   # Now all operations on this specific instance bypass permissions
   user.update(some_field="value")

Helper Methods
--------------

Permission Models provide several helper methods:

.. code-block:: python

   # Check if current user is admin
   if article.is_current_user_admin():
       # Do admin stuff
       pass

   # Check if current user is the owner
   if article.is_current_user_owner():
       # User owns this resource
       pass

   # Get current user from JWT
   current_user = article.get_current_user()

Integration with CRUD Blueprints
---------------------------------

CRUD Blueprints automatically enforce permissions:

.. code-block:: python

   from flask_more_smorest.perms import CRUDBlueprint

   # All operations will enforce permissions
   articles = CRUDBlueprint(
       "articles",
       __name__,
       model="Article",  # Must be a BasePermsModel subclass
       schema="ArticleSchema",
   )

   # You can mark specific operations as admin-only
   articles = CRUDBlueprint(
       "articles",
       __name__,
       model="Article",
       schema="ArticleSchema",
       methods={
           CRUDMethod.DELETE: {"admin_only": True},
       },
   )

Example: Blog with Permissions
-------------------------------

Here's a complete example of a blog with permission controls:

.. code-block:: python

   from flask_more_smorest.perms import (
       BasePermsModel,
       HasUserMixin,
       UserOwnershipMixin,
   )
   from flask_more_smorest.sqla import db
   from sqlalchemy.orm import Mapped, mapped_column

   class Critter(HasUserMixin, BasePermsModel):
       # Table name automatically set to "critter"

       name: Mapped[str] = mapped_column(db.String(100), nullable=False)
       species: Mapped[str] = mapped_column(db.String(50), nullable=False)
       is_adoptable: Mapped[bool] = mapped_column(db.Boolean, default=True)

       def _can_read(self) -> bool:
           # Anyone can read adoptable critters
           if self.is_adoptable:
               return True
           # Owners and admins can see non-adoptable ones
           return self.is_current_user_owner() or self.is_current_user_admin()

       def _can_write(self) -> bool:
           # Only owner or admin can edit
           return self.is_current_user_owner() or self.is_current_user_admin()

       def _can_delete(self) -> bool:
           # Only admin can delete
           return self.is_current_user_admin()

       @classmethod
       def _can_create(cls) -> bool:
           # Any authenticated user can create articles
           return cls.get_current_user() is not None


   class Comment(HasUserMixin, UserOwnershipMixin, BasePermsModel):
       # Table name automatically set to "comment"
       # Uses default: __delegate_to_user__ = False (simple ownership)

       article_id: Mapped[uuid.UUID] = mapped_column(
           db.ForeignKey("article.id"), nullable=False
       )
       text: Mapped[str] = mapped_column(db.Text, nullable=False)

       # UserOwnershipMixin provides:
       # - Users can only read/write their own comments
       # - Admins can access all comments

Next Steps
----------

- See :doc:`user-models` for authentication and user management
- Check :doc:`crud` for integrating permissions with CRUD operations
- Review the :doc:`api` reference for detailed method signatures
