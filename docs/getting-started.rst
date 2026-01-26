Getting Started
===============

Installation
------------

Install flask-more-smorest using pip:

.. code-block:: bash

   pip install flask-more-smorest

Quick Start
-----------

Here's a minimal example to get you started:

.. code-block:: python

   from flask import Flask
   from flask_more_smorest import BaseModel, CRUDBlueprint, init_db
   from flask_more_smorest.perms import Api
   from flask_more_smorest.sqla import db
   from sqlalchemy.orm import Mapped, mapped_column

   # Create Flask app
   app = Flask(__name__)
   app.config.update(
       API_TITLE="My API",
       API_VERSION="v1",
       OPENAPI_VERSION="3.0.2",
       SQLALCHEMY_DATABASE_URI="sqlite:///app.db",
       SECRET_KEY="change-me",
       JWT_SECRET_KEY="change-me-too",
   )

   # Define your model
   class Critter(BaseModel):
       name: Mapped[str] = mapped_column(db.String(100))
       species: Mapped[str] = mapped_column(db.String(50))
       cuteness_level: Mapped[int] = mapped_column(db.Integer, default=10)

   # Initialize database
   init_db(app)

   # Create API instance with JWT and permission hooks
   api = Api(app)

   # Create a CRUD blueprint using model class
   critters = CRUDBlueprint(
       "critters",
       __name__,
       model=Critter,           # Use class (preferred over string)
       schema=Critter.Schema,   # Auto-generated schema
       url_prefix="/api/critters/",
   )

   # Register blueprint
   api.register_blueprint(critters)

   if __name__ == "__main__":
       app.run(debug=True)

This automatically creates the following endpoints:

- ``GET /api/critters/`` - List all critters (with pagination and filtering)
- ``POST /api/critters/`` - Create a new critter
- ``GET /api/critters/<id>`` - Get a specific critter
- ``PATCH /api/critters/<id>`` - Update a critter
- ``DELETE /api/critters/<id>`` - Delete a critter
- ``GET /health`` - Health check endpoint (automatically added)

Creating Models
---------------

Use ``BaseModel`` to create models with automatic features:

.. code-block:: python

   from flask_more_smorest import BaseModel
   from flask_more_smorest.sqla import db
   from sqlalchemy.orm import Mapped, mapped_column

   class Critter(BaseModel):
       name: Mapped[str] = mapped_column(db.String(100), nullable=False)
       species: Mapped[str] = mapped_column(db.String(50), nullable=False)
       cuteness_level: Mapped[int] = mapped_column(db.Integer, default=10)

``BaseModel`` automatically provides:

- UUID primary key (``id``)
- Timestamps (``created_at``, ``updated_at``)
- CRUD helper methods (``save()``, ``update()``, ``delete()``, ``get_by()``, ``get_by_or_404()``)
- **Auto-generated Marshmallow schema** (``Critter.Schema``) - no need to define custom schemas

Controlling CRUD Endpoints
---------------------------

By default, all CRUD methods are enabled. Customize which endpoints are created:

.. code-block:: python

   from flask_more_smorest.crud.crud_blueprint import CRUDMethod

   # Read-only endpoints
   read_only = CRUDBlueprint(
       "critters",
       __name__,
       model=Critter,
       schema=Critter.Schema,
       methods=[CRUDMethod.INDEX, CRUDMethod.GET],  # Only list and get
   )

   # Disable specific methods
   no_delete = CRUDBlueprint(
       "critters",
       __name__,
       model=Critter,
       schema=Critter.Schema,
       skip_methods=[CRUDMethod.DELETE],  # All except delete
   )

For advanced configuration (custom schemas per method, admin-only endpoints, etc.), see :doc:`crud`.

User Authentication
-------------------

Get instant authentication with ``UserBlueprint``:

.. code-block:: python

   from flask_more_smorest import UserBlueprint
   from flask_more_smorest.perms import init_fms
   from flask_more_smorest.perms.models.defaults import (
       DefaultDomain,
       DefaultToken,
       DefaultUser,
       DefaultUserRole,
       DefaultUserSetting,
   )

   # Register default models explicitly
   init_fms(user=
       user=DefaultUser,
       role=DefaultUserRole,
       token=DefaultToken,
       domain=DefaultDomain,
       setting=DefaultUserSetting,
   )

   # Instant login and profile endpoints
   user_bp = UserBlueprint(register=False)
   api.register_blueprint(user_bp)

This automatically provides:

- ``POST /api/users/login/`` - JWT authentication endpoint
- ``GET /api/users/me/`` - Current user profile endpoint
- Full CRUD for user management with role-based permissions

Enable public registration:

.. code-block:: python

   from flask_more_smorest import UserBlueprint
   from flask_more_smorest.perms.models.defaults import DefaultUser

   class PublicUser(DefaultUser):
       PUBLIC_REGISTRATION = True  # Allow unauthenticated user creation

   public_bp = UserBlueprint(model=PublicUser, register=False)
   api.register_blueprint(public_bp)

Filtering and Pagination
-------------------------

CRUD endpoints automatically support filtering and pagination:

.. code-block:: bash

   # Filter by field values
   GET /api/critters/?species=cat&cuteness_level=10

   # Date range filtering
   GET /api/critters/?created_at__from=2024-01-01&created_at__to=2024-12-31

   # Pagination
   GET /api/critters/?page=2&page_size=20

   # String matching
   GET /api/critters/?name__like=%fluffy%

Error Handling
--------------

All errors follow the `RFC 7807 Problem Details <https://datatracker.ietf.org/doc/html/rfc7807>`_ standard:

.. code-block:: json

   {
     "type": "/errors/not_found_error",
     "title": "Not Found",
     "status": 404,
     "detail": "Critter with id abc123 doesn't exist",
     "instance": "/api/critters/abc123"
   }

In debug/testing mode, additional debug information is included. See :doc:`configuration` for details.

Health Checks
-------------

A built-in health check endpoint is available at ``/health`` for load balancers and monitoring:

.. code-block:: json

   {
     "status": "healthy",
     "timestamp": "2026-01-11T08:30:00+00:00",
     "version": "0.6.0",
     "database": "connected"
   }

Configure the path or disable it via ``HEALTH_ENDPOINT_PATH`` and ``HEALTH_ENDPOINT_ENABLED``.

Performance Monitoring
----------------------

Enable SQLAlchemy performance monitoring to identify slow queries:

.. code-block:: python

   app.config.update(
       SQLALCHEMY_PERFORMANCE_MONITORING=True,
       SQLALCHEMY_SLOW_QUERY_THRESHOLD=0.5,  # Log queries over 500ms
   )

This logs slow queries and provides per-request statistics. See :doc:`configuration` for details.

Next Steps
----------

- Review :doc:`configuration` for all available options
- Learn about :doc:`permissions` for access control
- Explore :doc:`crud` for advanced CRUD configuration
- See :doc:`user-models` for authentication and authorization
- Check the :doc:`api` reference for detailed documentation
