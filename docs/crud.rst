CRUD Blueprints
===============

Flask-More-Smorest's ``CRUDBlueprint`` automatically generates RESTful endpoints for your SQLAlchemy models with minimal configuration.

Basic Usage
-----------

Create a CRUD blueprint by specifying a model and schema:

.. code-block:: python

   from flask_more_smorest.crud.crud_blueprint import CRUDBlueprint

   users = CRUDBlueprint(
       "critters",                    # Blueprint name
       __name__,                   # Import name
       model="Critter",               # Model class or string
       schema="CritterSchema",        # Schema class or string
       url_prefix="/api/users/",   # URL prefix
   )

This creates five endpoints:

- ``GET /api/users/`` - List all users (INDEX)
- ``POST /api/users/`` - Create a new user (POST)
- ``GET /api/users/<id>`` - Get a specific user (GET)
- ``PATCH /api/users/<id>`` - Update a user (PATCH)
- ``DELETE /api/users/<id>`` - Delete a user (DELETE)

Configuration Options
---------------------

Model and Schema Resolution
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Models and schemas can be specified as:

1. **Strings** (resolved from default import paths):

   .. code-block:: python

      CRUDBlueprint(
          "critters",
          __name__,
          model="Critter",        # Resolves to models.Critter
          schema="CritterSchema", # Resolves to schemas.CritterSchema
      )

2. **Classes** (direct reference):

   .. code-block:: python

      from myapp.models import Critter
      from myapp.schemas import CritterSchema

      CRUDBlueprint(
          "critters",
          __name__,
          model=Critter,
          schema=CritterSchema,
      )

3. **Custom import paths**:

   .. code-block:: python

      CRUDBlueprint(
          "critters",
          __name__,
          model="Critter",
          schema="CritterSchema",
          model_import_name="myapp.resources.models",
          schema_import_name="myapp.resources.schemas",
      )

Controlling Methods
^^^^^^^^^^^^^^^^^^^

Enable only specific methods using a list:

.. code-block:: python

   from flask_more_smorest.crud.crud_blueprint import CRUDMethod

   # Only create list and get endpoints
   users = CRUDBlueprint(
       "critters",
       __name__,
       model="Critter",
       schema="CritterSchema",
       methods=[CRUDMethod.INDEX, CRUDMethod.GET],
   )

Configure methods using a dict (all methods enabled by default):

.. code-block:: python

   users = CRUDBlueprint(
       "critters",
       __name__,
       model="Critter",
       schema="CritterSchema",
       methods={
           CRUDMethod.POST: {"schema": "UserWriteSchema"},   # Custom schema
           CRUDMethod.DELETE: {"admin_only": True},          # Admin-only
           CRUDMethod.PATCH: False,                          # Disable
           # INDEX and GET not specified, so enabled with defaults
       },
   )

**When using a dict, all methods are enabled by default.** Specify ``False`` to disable a method.

Available methods:

- ``CRUDMethod.INDEX`` - List resources (``GET /resource/``)
- ``CRUDMethod.GET`` - Get single resource (``GET /resource/<id>``)
- ``CRUDMethod.POST`` - Create resource (``POST /resource/``)
- ``CRUDMethod.PATCH`` - Update resource (``PATCH /resource/<id>``)
- ``CRUDMethod.DELETE`` - Delete resource (``DELETE /resource/<id>``)

Custom Resource ID
^^^^^^^^^^^^^^^^^^

By default, resources are accessed by ``id``. You can customize this:

.. code-block:: python

   users = CRUDBlueprint(
       "critters",
       __name__,
       model="Critter",
       schema="CritterSchema",
       res_id="username",           # Field name on model
       res_id_param="user_name",    # Parameter name in URL
   )

   # Creates URLs like: /api/users/<user_name>

Query Filtering
---------------

CRUD INDEX endpoints automatically support advanced filtering:

Field Equality
^^^^^^^^^^^^^^

.. code-block:: bash

   GET /api/users/?username=john&is_active=true

Date Range Filtering
^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   # From date
   GET /api/users/?created_at__from=2024-01-01

   # To date
   GET /api/users/?created_at__to=2024-12-31

   # Range
   GET /api/users/?created_at__from=2024-01-01&created_at__to=2024-12-31

Numeric Filtering
^^^^^^^^^^^^^^^^^

.. code-block:: bash

   # Greater than
   GET /api/users/?age__gt=18

   # Less than
   GET /api/users/?age__lt=65

   # Greater than or equal
   GET /api/users/?age__gte=21

   # Less than or equal
   GET /api/users/?age__lte=60

String Matching
^^^^^^^^^^^^^^^

.. code-block:: bash

   # SQL LIKE pattern
   GET /api/users/?email__like=%@example.com

   # Case-insensitive LIKE
   GET /api/users/?username__ilike=john%

Boolean Filtering
^^^^^^^^^^^^^^^^^

.. code-block:: bash

   GET /api/users/?is_active=true
   GET /api/users/?is_admin=false

Pagination
----------

INDEX endpoints support automatic pagination:

.. code-block:: bash

   # Default page 1, page_size from config (typically 25)
   GET /api/users/

   # Specific page
   GET /api/users/?page=2

   # Custom page size
   GET /api/users/?page=1&page_size=50

   # Combine with filters
   GET /api/users/?page=2&page_size=10&is_active=true

Response includes pagination metadata:

.. code-block:: json

   {
       "data": [...],
       "pagination": {
           "page": 2,
           "page_size": 10,
           "total": 47,
           "total_pages": 5
       }
   }

Custom Schemas
--------------

Use different schemas for different operations:

.. code-block:: python

   users = CRUDBlueprint(
       "critters",
       __name__,
       model="Critter",
       schema="CritterSchema",  # Default schema for most operations
       methods={
           CRUDMethod.INDEX: {"schema": "UserListSchema"},    # List view
           CRUDMethod.GET: {"schema": "UserDetailSchema"},    # Detail view
           CRUDMethod.POST: {"schema": "UserCreateSchema"},   # Creation
           CRUDMethod.PATCH: {
               "schema": "UserUpdateSchema",                  # Update response
               "arg_schema": "UserUpdateArgsSchema",          # Update input
           },
       },
   )

Admin-Only Endpoints
--------------------

Mark specific endpoints as admin-only:

.. code-block:: python

   from flask_more_smorest.perms import CRUDBlueprint

   users = CRUDBlueprint(
       "critters",
       __name__,
       model="Critter",
       schema="CritterSchema",
       methods={
           CRUDMethod.DELETE: {"admin_only": True},
           CRUDMethod.PATCH: {"admin_only": True},
       },
   )

**Note:** Your blueprint must inherit from ``PermsBlueprintMixin`` (which ``flask_more_smorest.perms.CRUDBlueprint`` does) for this to work.

Nested Resources
----------------

Create nested resource routes:

.. code-block:: python

   # Parent resource
   users = CRUDBlueprint(
       "critters",
       __name__,
       model="Critter",
       schema="CritterSchema",
       url_prefix="/api/users/",
   )

   # Nested resource
   user_posts = CRUDBlueprint(
       "user_posts",
       __name__,
       model="Post",
       schema="PostSchema",
       url_prefix="/api/users/<uuid:user_id>/posts/",
   )

This creates URLs like:

- ``GET /api/users/<user_id>/posts/`` - List user's posts
- ``POST /api/users/<user_id>/posts/`` - Create post for user
- ``GET /api/users/<user_id>/posts/<id>`` - Get specific post

The ``user_id`` from the URL is automatically passed to queries as a filter.

Custom Endpoints
----------------

Add custom endpoints to your CRUD blueprint:

.. code-block:: python

   users = CRUDBlueprint(
       "critters",
       __name__,
       model="Critter",
       schema="CritterSchema",
   )

   @users.route("/stats/")
   def user_stats():
       """Custom endpoint: /api/users/stats/"""
       return {
           "total": User.query.count(),
           "active": User.query.filter_by(is_active=True).count(),
       }

   @users.route("/<uuid:user_id>/activate/", methods=["POST"])
   @users.response(200, CritterSchema)
   def activate_user(user_id):
       """Custom endpoint: POST /api/users/<user_id>/activate/"""
       user = User.get_by_or_404(id=user_id)
       user.update(is_active=True)
       return user

Public Endpoints
----------------

Mark endpoints as public (no authentication required):

.. code-block:: python

   from flask_more_smorest.perms import CRUDBlueprint

   articles = CRUDBlueprint(
       "articles",
       __name__,
       model="Article",
       schema="ArticleSchema",
   )

   @articles.public_endpoint
   @articles.route("/featured/")
   def featured_articles():
       """Public endpoint - no auth required"""
       return Article.query.filter_by(featured=True).all()

Operation IDs
-------------

CRUD endpoints automatically generate OpenAPI operation IDs:

- ``INDEX`` → ``list{ModelName}`` (e.g., ``listUser``)
- ``GET`` → ``get{ModelName}`` (e.g., ``getUser``)
- ``POST`` → ``create{ModelName}`` (e.g., ``createUser``)
- ``PATCH`` → ``update{ModelName}`` (e.g., ``updateUser``)
- ``DELETE`` → ``delete{ModelName}`` (e.g., ``deleteUser``)

These IDs are useful for client code generation and API documentation.

Example: Complete CRUD Blueprint
---------------------------------

Here's a comprehensive example:

.. code-block:: python

   from flask import Flask
   from flask_more_smorest import init_db
   from flask_more_smorest.perms import Api, CRUDBlueprint
   from flask_more_smorest.crud.crud_blueprint import CRUDMethod

   app = Flask(__name__)
   app.config.update(
       API_TITLE="Blog API",
       API_VERSION="v1",
       OPENAPI_VERSION="3.0.2",
       SQLALCHEMY_DATABASE_URI="sqlite:///blog.db",
       SECRET_KEY="secret",
       JWT_SECRET_KEY="jwt-secret",
   )

   init_db(app)
   api = Api(app)

   # Articles CRUD with custom configuration
   articles = CRUDBlueprint(
       "articles",
       __name__,
       model="Article",
       schema="ArticleSchema",
       url_prefix="/api/articles/",
       methods={
           # List uses summary schema
           CRUDMethod.INDEX: {"schema": "ArticleSummarySchema"},
           # Detail uses full schema
           CRUDMethod.GET: {"schema": "ArticleDetailSchema"},
           # Create requires write schema
           CRUDMethod.POST: {"schema": "ArticleWriteSchema"},
           # Update requires write schema for input
           CRUDMethod.PATCH: {
               "schema": "ArticleDetailSchema",
               "arg_schema": "ArticleWriteSchema",
           },
           # Only admins can delete
           CRUDMethod.DELETE: {"admin_only": True},
       },
   )

   @articles.public_endpoint
   @articles.route("/published/")
   @articles.response(200, ArticleSummarySchema(many=True))
   def published_articles():
       """List published articles - public endpoint"""
       return Article.query.filter_by(published=True).all()

   api.register_blueprint(articles)

Next Steps
----------

- Learn about :doc:`permissions` for access control
- See :doc:`getting-started` for basic setup
- Check the :doc:`api` reference for detailed documentation
